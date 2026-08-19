#!/usr/bin/env python3
"""Roda o runbook da Fase 1 do ciclo de compras (recebimento e atesto) PELA TELA.

Uso:
    python scripts/runbook_fase1.py              # semeia e roda o ciclo inteiro
    python scripts/runbook_fase1.py --sem-semear # aproveita o cenário que está lá

Pré-requisito: o app de pé em http://localhost:5000.

O runbook mora em 📖 `docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md`,
seção "Runbook — ligar a flag num tenant". Ele nunca foi rodado: o mesmo aviso que
valia para a Fase 2 até 19/08 vale para esta.

POR QUE ELA VALE A PENA. O runbook da Fase 2, rodado por script em 19/08, achou um
controle inteiro desligado em produção na primeira execução — e o preparo dele, em
18/08, tinha achado uma tela em 500 desde 22/07. Duas rodadas, dois defeitos que
nenhum gate pegava, porque gate cobre a REGRA e não o CAMINHO.

A DIFERENÇA DESTE PARA O DA FASE 2. Aqui o regime é carimbado na EMISSÃO, então a
conferência mais importante — "pedido emitido antes de ligar continua no regime
antigo" — exige emitir um pedido com a flag DESLIGADA. Este script desliga, emite,
religa e emite de novo, e é isso que torna o passo 6 do runbook verificável em vez
de declarado.

A maquinaria (Runbook, entrar, abrir, submeter, frescos) vem de `runbook_comum.py`.
"""
import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

from runbook_comum import (BASE, VIEWPORT, Runbook, _pessoas_e_obra, abrir,
                           avisos, entrar, frescos, preparar_bibliotecas,
                           rodar_python, semear, submeter, unico)

RAIZ = Path(__file__).resolve().parent.parent
rb = Runbook('DA FASE 1 — RECEBIMENTO E ATESTO')


def _flag(script, admin_id, acao):
    """Liga/desliga pela FERRAMENTA, não pela coluna.

    📖 A lição de 18/08 do seed do manual: gravar a flag direto na coluna passa
    por cima do guarda do script — e o guarda é onde a pré-condição mora
    (`--ligar` recusa tenant sem AlmoxarifadoItem, porque ali o pedido nasceria
    impossível de receber).
    """
    p = rodar_python([sys.executable, f'scripts/{script}', str(admin_id), acao], RAIZ)
    return p.returncode == 0, (p.stdout + p.stderr)[-400:]


def _emitir_pela_tela(pg, req_id, quando):
    """Percorre a tela da requisição e emite o pedido. Devolve (ok, detalhe)."""
    abrir(pg, f'/compras/requisicoes/{req_id}')
    form = pg.query_selector('form[action*="emitir-pedido"]')
    if form is None:
        return False, 'o formulário de emitir não está na tela'
    opcoes = pg.eval_on_selector_all(
        'form[action*="emitir-pedido"] select[name="fornecedor_id"] option',
        'ns => ns.map(n => n.value).filter(v => v)')
    if not opcoes:
        return False, 'não há fornecedor no seletor'
    pg.select_option('form[action*="emitir-pedido"] select[name="fornecedor_id"]', opcoes[0])
    pg.select_option('form[action*="emitir-pedido"] select[name="condicao_pagamento"]', '30d')
    pg.fill('form[action*="emitir-pedido"] input[name="data_compra"]', quando.isoformat())
    submeter(pg, 'form[action*="emitir-pedido"]')
    return True, avisos(pg)[:160]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sem-semear', action='store_true')
    args = ap.parse_args()

    preparar_bibliotecas()

    if not args.sem_semear:
        print('semeando o cenário…')
        if not semear(RAIZ, rb):
            return rb.relatorio()

    from app import app, db
    from models import (AlmoxarifadoEstoque, AlmoxarifadoMovimento, PedidoCompra,
                        PedidoCompraItem, RequisicaoCompra)
    from seed_manual_compras import MARCA, SENHA

    with app.app_context():
        pessoas, obra = _pessoas_e_obra()
        admin_id = pessoas['admin'].id
        usuarios = {k: f'{MARCA}_{k}' for k in pessoas}

        rb.passo('0 — o cenário e as flags')
        req_legado = RequisicaoCompra.query.filter_by(
            admin_id=admin_id, numero='RC-2026-0002').first()
        req_nova = RequisicaoCompra.query.filter_by(
            admin_id=admin_id, numero='RC-2026-0004').first()
        rb.conferir('a requisição AGUARDANDO existe (vira o pedido legado)',
                    req_legado is not None,
                    req_legado.estado.name if req_legado else '—')
        rb.conferir('a requisição APROVADA existe (vira o pedido novo)',
                    req_nova is not None,
                    req_nova.estado.name if req_nova else '—')
        if not (req_legado and req_nova):
            return rb.relatorio()
        id_legado, id_nova = req_legado.id, req_nova.id

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        paginas = {}

        def pagina(chave):
            if chave not in paginas:
                pg = navegador.new_context(viewport=VIEWPORT).new_page()
                entrar(pg, usuarios[chave], SENHA)
                paginas[chave] = pg
            return paginas[chave]

        with app.app_context():
            ped_legado_id = ped_novo_id = None

            # ── 1. o pedido LEGADO: emitido com a flag DESLIGADA ───────────
            rb.passo('(1) com a flag DESLIGADA, o pedido nasce no regime antigo')
            try:
                # A ordem importa: `financeiro_dois_fluxos` depende de
                # `recebimento_atesto`, então ele sai primeiro e volta por último.
                _flag('flag_financeiro_dois_fluxos.py', admin_id, '--desligar')
                ok, saida = _flag('flag_recebimento_atesto.py', admin_id, '--desligar')
                rb.conferir('a flag foi desligada pela ferramenta', ok, saida[-120:])

                pg = pagina('gestor')
                abrir(pg, f'/compras/requisicoes/{id_legado}')
                # `unico` e não `query_selector`: a ratificação da emergência usa
                # a MESMA rota `/aprovar`, então dois formulários podem casar.
                fa = unico(pg, 'form[action*="/aprovar"]',
                           'o formulário de aprovar')
                rb.conferir('o botão de aprovar está na tela do gestor', fa is not None)
                submeter(pg, 'form[action*="/aprovar"]')
                # Conferir o ESTADO, não o clique: a primeira rodada seguiu em
                # frente achando que tinha aprovado e só descobriu o contrário
                # dois passos depois, como "o formulário de emitir não está na
                # tela" — sintoma longe da causa.
                # 🔬 19/08: a faixa deste tenant exige DUAS aprovações, uma
                # delas de administrador — a tela disse isso na primeira rodada
                # ("faltam 1 aprovação(ões) de 2; falta a aprovação de um
                # administrador"). A alçada funcionando é o motivo, não um
                # obstáculo: o runbook precisa de duas pessoas aqui.
                pa = pagina('admin')
                abrir(pa, f'/compras/requisicoes/{id_legado}')
                if pa.query_selector('form[action*="/aprovar"]') is not None:
                    submeter(pa, 'form[action*="/aprovar"]')

                frescos()
                rq = db.session.get(RequisicaoCompra, id_legado)
                rb.conferir('a requisição ficou APROVADA',
                            rq.estado.name == 'APROVADA',
                            f'estado = {rq.estado.name} | {avisos(pg)[:140]}')

                pg = pagina('comprador')
                ok, det = _emitir_pela_tela(pg, id_legado, date.today())
                rb.conferir('o pedido legado foi emitido pela tela', ok, det)

                frescos()
                pl = PedidoCompra.query.filter_by(
                    admin_id=admin_id, requisicao_id=id_legado).first()
                rb.conferir('o pedido legado existe', pl is not None)
                if pl is not None:
                    ped_legado_id = pl.id
                    rb.conferir('exige_atesto = FALSE no pedido legado',
                                not pl.exige_atesto,
                                'o regime é carimbado na linha, na emissão')
            except Exception as e:
                rb.quebrou('o passo (1) chegou ao fim', e)

            # ── 2. ligar, e o pedido NOVO nasce no regime novo ─────────────
            rb.passo('(2) com a flag LIGADA, o pedido novo nasce sem estoque')
            try:
                ok1, s1 = _flag('flag_recebimento_atesto.py', admin_id, '--ligar')
                rb.conferir('recebimento_atesto religado', ok1, s1[-120:])
                ok2, s2 = _flag('flag_financeiro_dois_fluxos.py', admin_id, '--ligar')
                rb.conferir('financeiro_dois_fluxos religado (a cadeia)', ok2, s2[-120:])

                pg = pagina('comprador')
                ok, det = _emitir_pela_tela(pg, id_nova, date.today())
                rb.conferir('o pedido novo foi emitido pela tela', ok, det)

                frescos()
                pn = PedidoCompra.query.filter_by(
                    admin_id=admin_id, requisicao_id=id_nova).first()
                rb.conferir('o pedido novo existe', pn is not None)
                if pn is not None:
                    ped_novo_id = pn.id
                    rb.conferir('exige_atesto = TRUE', bool(pn.exige_atesto))
                    rb.conferir("situacao_recebimento = 'nao_recebido'",
                                pn.situacao_recebimento == 'nao_recebido',
                                f'situacao = {pn.situacao_recebimento}')
                    ent = AlmoxarifadoMovimento.query.filter_by(
                        pedido_compra_id=pn.id, tipo_movimento='ENTRADA').count()
                    rb.conferir('ZERO movimentos de ENTRADA na emissão', ent == 0,
                                f'{ent} entradas — o estoque agora nasce do ATESTO, '
                                f'e este era o ponto da dupla escrita da Fase 1')
            except Exception as e:
                rb.quebrou('o passo (2) chegou ao fim', e)

            if ped_novo_id is None:
                return rb.relatorio()

            # ── 3. a tela do pedido leva ao recebimento ────────────────────
            rb.passo('(3) o botão da tela do pedido leva ao atesto, não ao POST antigo')
            try:
                pg = pagina('gestor')
                abrir(pg, f'/compras/{ped_novo_id}')
                link = pg.query_selector(f'a[href*="/compras/{ped_novo_id}/recebimento"]')
                rb.conferir('o botão aponta para /compras/<id>/recebimento',
                            link is not None,
                            'ausente = a tela ainda manda para a rota antiga')
            except Exception as e:
                rb.quebrou('o passo (3) chegou ao fim', e)

            # ── 4 e 5. recebimento parcial e depois o resto ────────────────
            quando = date.today() - timedelta(days=2)   # data DIFERENTE de hoje
            for etapa, (rotulo, fracao, seq, situacao) in enumerate(
                    [('(4) recebimento PARCIAL', Decimal('0.6'), 1, 'parcial'),
                     ('(5) o RESTO', None, 2, 'recebido')], start=1):
                rb.passo(f'{rotulo} — ENTRADA + SAIDA pareadas, lote /{seq}')
                try:
                    frescos()
                    item = PedidoCompraItem.query.filter_by(pedido_id=ped_novo_id).first()
                    total = Decimal(str(item.quantidade or 0))
                    ja = sum(Decimal(str(m.quantidade or 0)) for m in
                             AlmoxarifadoMovimento.query.filter_by(
                                 pedido_compra_id=ped_novo_id,
                                 tipo_movimento='ENTRADA').all())
                    qtd = (total * fracao).quantize(Decimal('1')) if fracao else total - ja
                    # SEM ponto: 📖 `_quantidade_do_form` RECUSA decimal ambíguo
                    # ("48.000" pode ser 48 mil ou 48,0), e foi assim que a
                    # primeira rodada teve o segundo recebimento silenciosamente
                    # recusado — a tela abriu, o campo existia, e nada gravou.
                    texto_qtd = f'{qtd.normalize():f}'.rstrip('0').rstrip('.') or '0'

                    pg = pagina('gestor')
                    st = abrir(pg, f'/compras/{ped_novo_id}/recebimento')
                    rb.conferir('a tela de recebimento abre', st < 400, f'HTTP {st}')
                    campo = pg.query_selector(f'input[name="qtd_{item.id}"]')
                    rb.conferir('o campo de quantidade do item está na tela',
                                campo is not None)
                    if campo is None:
                        continue
                    campo.fill(texto_qtd)
                    pg.fill('input[name="data_recebimento"]', quando.isoformat())
                    submeter(pg, 'form:has(input[name="data_recebimento"])')
                    aviso = avisos(pg)
                    rb.conferir('a tela ACEITOU o recebimento',
                                'recus' not in aviso.lower()
                                and 'inválid' not in aviso.lower()
                                and 'ambígu' not in aviso.lower(),
                                aviso[:180])

                    frescos()
                    ped = db.session.get(PedidoCompra, ped_novo_id)
                    # 📖 `services/recebimento_pedido.py:315` usa
                    # `pedido.numero or f"PC-{pedido.id}"`: pedido emitido pela
                    # tela sem preencher "Nº da NF/recibo" nasce SEM numero, e
                    # foi assim que a primeira rodada procurou o lote `None/1`.
                    lote = f'{ped.numero or f"PC-{ped.id}"}/{seq}'
                    # 📖 O lote mora no ESTOQUE (a prateleira), não na coluna
                    # do movimento: a ENTRADA aponta para ele por `estoque_id`
                    # e só a SAIDA copia o rótulo. A primeira rodada procurou
                    # `AlmoxarifadoMovimento.lote` na ENTRADA, achou NULL e
                    # quase reportou "saída sem entrada pareada" — que teria
                    # sido um alarme falso sério.
                    est = AlmoxarifadoEstoque.query.filter(
                        AlmoxarifadoEstoque.lote == lote).first()
                    entradas = ([db.session.get(AlmoxarifadoMovimento,
                                                est.entrada_movimento_id)]
                                if est and est.entrada_movimento_id else [])
                    saidas = AlmoxarifadoMovimento.query.filter_by(
                        pedido_compra_id=ped_novo_id, tipo_movimento='SAIDA',
                        estoque_id=est.id).all() if est else []
                    rb.conferir(f'ENTRADA de {qtd} no lote {lote}',
                                len(entradas) == 1
                                and Decimal(str(entradas[0].quantidade)) == qtd,
                                f'{len(entradas)} entrada(s)')
                    rb.conferir(f'SAIDA pareada de {qtd} (o pedido tem obra)',
                                len(saidas) == 1
                                and Decimal(str(saidas[0].quantidade)) == qtd,
                                f'{len(saidas)} saída(s) — sem ela o lote fica '
                                f'disponível para uma segunda baixa')
                    rb.conferir(f"situacao_recebimento = '{situacao}'",
                                ped.situacao_recebimento == situacao,
                                f'situacao = {ped.situacao_recebimento}')
                    if entradas:
                        rb.conferir(f'o lote {lote} ficou CONSUMIDO',
                                    est is not None and est.status == 'CONSUMIDO',
                                    f'status = {est.status if est else "sem lote"}')
                        rb.conferir('data_movimento = a data INFORMADA, não hoje',
                                    entradas[0].data_movimento.date() == quando,
                                    f'gravado {entradas[0].data_movimento.date()}, '
                                    f'informado {quando}')
                except Exception as e:
                    rb.quebrou(f'o passo {rotulo} chegou ao fim', e)

            # ── 6. o pedido legado NÃO mudou de regime ─────────────────────
            rb.passo('(6) o pedido emitido ANTES de ligar segue no regime antigo')
            try:
                frescos()
                if ped_legado_id:
                    pl = db.session.get(PedidoCompra, ped_legado_id)
                    rb.conferir('exige_atesto continua FALSE depois de ligar a flag',
                                not pl.exige_atesto,
                                'ligar a flag NÃO reescreve pedido já emitido — '
                                'é o ponto do carimbo na linha')
                    pg = pagina('gestor')
                    st = abrir(pg, f'/compras/{ped_legado_id}/recebimento')
                    texto = avisos(pg)
                    rb.conferir('a tela de atesto RECUSA o pedido legado, com a razão',
                                'regime antigo' in texto.lower()
                                or 'dobro' in texto.lower(),
                                texto[:200] or '(sem aviso — no-op silencioso é pior '
                                               'que recusa)')
            except Exception as e:
                rb.quebrou('o passo (6) chegou ao fim', e)

        navegador.close()

    # ── 7. o sensor ─────────────────────────────────────────────────────────
    rb.passo('(7) o sensor de consistência do recebimento')
    p = rodar_python([sys.executable, 'scripts/verificar_consistencia_recebimento.py', str(admin_id)], RAIZ)
    RUIDO = ('SAWarning', 'return cls.query_class', 'INFO:', 'WARNING:', 'tensorflow')
    saida = (p.stdout or '') + (p.stderr or '')
    for linha in [l for l in saida.strip().splitlines()
                  if l.strip() and not any(r in l for r in RUIDO)][-15:]:
        print(f'   | {linha}')
    rb.conferir('o sensor não acusa drift', p.returncode == 0, f'exit {p.returncode}')

    return rb.relatorio()


if __name__ == '__main__':
    sys.exit(main())
