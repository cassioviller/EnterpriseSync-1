#!/usr/bin/env python3
"""Runbook da Fase 3 do ciclo de compras (alçadas avançadas), PELA TELA, por script.

Uso:
    python scripts/runbook_fase3.py              # semeia e roda
    python scripts/runbook_fase3.py --sem-semear

Pré-requisito: o app de pé em http://localhost:5000.

⚠️ ESTE É DIFERENTE DOS DA FASE 1 E 2, e vale saber por quê. Aqueles cobriam
runbooks que NUNCA tinham sido percorridos. 📖 O runbook das alçadas
(`2026-08-15-alcadas-design.md:720`) registra: *"15/08, EXECUÇÃO: o runbook foi
RODADO inteiro num tenant de dev, do 0a ao Rollback, pela tela e por SQL cru"* —
e aquela execução achou um defeito que nenhum teste da fase pegava. **Aqui o
valor é REGRESSÃO, não descoberta.** Quem esperar achado novo vai se decepcionar,
e é melhor saber disso antes de rodar.

ESCOPO — os passos 3a, 3c e 3e do runbook. Ficam DE FORA, e não por descuido:

  3b (fornecedor novo)   o degrau só é COBRADO na emissão, e o que o operador vê
                         é a guarda 2 recusando quem aprovou — exige duas voltas
                         com fornecedor conhecido e novo para o contraste valer.
  3d (acima de 30k com   precisa de um mapa de concorrência com três fornecedores,
      3 cotações)        que é cenário próprio.

O QUE ESTE SCRIPT CRIA, e por que pela tela: as requisições nascem em
`/compras/requisicoes/nova`, não no seed. O anti-fracionamento é sobre o que o
time faz na tela, e 📖 `_criterios_da_etapa_na_janela` decidiu que **etapa NULA é
um grupo** ("omitir a etapa é a forma mais fácil de dividir uma compra") — que é
exatamente o que a tela produz, porque ela não oferece seletor de etapa.

A flag `alcadas_avancadas_ativa` nasce OFF no cenário do manual. Este script a
liga e a **devolve ao estado em que a achou** no fim, para não deixar o cenário
do manual visual diferente do que o manual mostra.
"""
import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

from runbook_comum import (BASE, VIEWPORT, Runbook, _pessoas_e_obra, abrir,
                           entrar, frescos, nova_requisicao,
                           preparar_bibliotecas, rodar_python, ligar_cadeia,
                           semear, unico)

RAIZ = Path(__file__).resolve().parent.parent
rb = Runbook('DA FASE 3 — ALÇADAS AVANÇADAS')

# 3 × R$ 4.900: a SEGUNDA é que cruza os R$ 5.000 do acumulado (9.800), não a
# terceira. 📖 É a correção `← EXEC` do passo 3c do runbook, escrita depois de
# alguém executá-lo e descobrir que o texto original errava a conta.
VALOR_FATIA = Decimal('4900.00')


def _flag(script, admin_id, *args):
    p = rodar_python([sys.executable, f'scripts/{script}', str(admin_id), *args], RAIZ)
    return p.returncode == 0, (p.stdout + p.stderr)


# A criação de requisição pela tela mora em `runbook_comum` desde 19/08 — esta
# cópia local era a original, e duas cópias divergem: a de lá aprendeu a vincular
# o item ao catálogo e a de cá não teria aprendido. Aqui a quantidade continua 1,
# que é o padrão: neste runbook o que importa é o VALOR da requisição.


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sem-semear', action='store_true')
    ap.add_argument('--piloto', action='store_true',
                    help='roda contra o cenário do PILOTO (janela limpa, dois '
                         'fornecedores) em vez do cenário do manual')
    args = ap.parse_args()

    preparar_bibliotecas()
    if not args.sem_semear:
        print('semeando o cenário…')
        if not semear(RAIZ, rb, 'seed_piloto_compras.py'
                      if args.piloto else 'seed_manual_compras.py'):
            return rb.relatorio()

    from app import app, db
    from models import ConfiguracaoEmpresa, RequisicaoCompra
    if args.piloto:
        from seed_piloto_compras import MARCA, SENHA
    else:
        from seed_manual_compras import MARCA, SENHA

    with app.app_context():
        pessoas, obra = (_pessoas_e_obra('piloto', 'PIL-A')
                         if args.piloto else _pessoas_e_obra())
        admin_id, obra_id = pessoas['admin'].id, obra.id
        usuarios = {k: f'{MARCA}_{k}' for k in pessoas}
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        estado_original = bool(getattr(cfg, 'alcadas_avancadas_ativa', False))

        if args.piloto:
            ligar_cadeia(RAIZ, admin_id, rb)

        rb.passo('0 — as flags, na ordem da cadeia')
        ok, saida = _flag('flag_alcadas_avancadas.py', admin_id, '--ligar')
        rb.conferir('a flag de alçadas avançadas liga', ok,
                    'RECUSADO' in saida and saida[-200:] or '')
        # 📖 A8: "LEIA A SAÍDA" — a linha `AVISO (não impede ligar):` significa
        # emergência SEM sanção, e é ela que decide se o passo 3e reproduz.
        sem_sancao = 'AVISO (não impede ligar)' in saida
        rb.conferir('a cadeia inteira está ligada (emergência COM sanção)',
                    not sem_sancao,
                    'há AVISO de cadeia incompleta — o passo 3e não reproduz'
                    if sem_sancao else '')

    try:
        with sync_playwright() as pw:
            nav = pw.chromium.launch(headless=True,
                                     args=['--no-sandbox', '--disable-dev-shm-usage'])
            paginas = {}

            def pagina(chave):
                if chave not in paginas:
                    pg = nav.new_context(viewport=VIEWPORT).new_page()
                    entrar(pg, usuarios[chave], SENHA)
                    paginas[chave] = pg
                return paginas[chave]

            with app.app_context():
                # ── 3a + 3c — o acumulado da janela ────────────────────────
                rb.passo('(3a/3c) três fatias de R$ 4.900 — a SEGUNDA cruza o teto')
                criadas, exigencias = [], []
                try:
                    pg = pagina('solicitante')
                    for i in (1, 2, 3):
                        antes = {r.id for r in RequisicaoCompra.query.filter_by(
                            admin_id=admin_id).all()}
                        aviso = nova_requisicao(
                            pg, obra_id,
                            f'Fatia {i} de material para o mesmo serviço.',
                            VALOR_FATIA)
                        frescos()
                        nova = [r for r in RequisicaoCompra.query.filter_by(
                            admin_id=admin_id).all() if r.id not in antes]
                        if not nova:
                            rb.conferir(f'a requisição {i} foi criada', False,
                                        aviso[:200])
                            break
                        r = nova[0]
                        criadas.append(r.id)
                        rb.conferir(f'a requisição {i} foi criada '
                                    f'({r.numero}, R$ {r.valor_estimado})', True)
                        # ⚠️ A DECISÃO É LIDA AGORA, não no fim. 📖 Requisição em
                        # RASCUNHO JÁ ACUMULA na janela ("inclusive em RASCUNHO,
                        # inclusive em regime simples", nota `← EXEC` do passo 4).
                        # Medir as três depois de criar as três faria todas verem
                        # o acumulado cheio — e até a primeira apareceria elevada,
                        # por construção do próprio script.
                        from services.alcada_compras import (acumulado_da_etapa,
                                                                decisao_de_alcada)
                        d = decisao_de_alcada(r)
                        exigencias.append((d.base.aprovacoes_necessarias,
                                           d.efetiva.aprovacoes_necessarias,
                                           list(d.condicoes or []),
                                           Decimal(str(acumulado_da_etapa(r) or 0))))

                    if len(exigencias) == 3:
                        (b1, n1, c1, a1), (b2, n2, c2, a2), (b3, n3, c3, a3) = exigencias
                        # ⚠️ A JANELA NÃO ESTÁ VAZIA, e o runbook do spec assume
                        # que está. 🔬 19/08: o seed acabou de criar sete
                        # requisições na MESMA obra com etapa NULA — e 📖
                        # `_criterios_da_etapa_na_janela` diz que "etapa NULA é um
                        # grupo". Então a PRIMEIRA fatia já entra com acumulado
                        # alto e já sobe. Isso é o sistema certo e o passo 3c do
                        # runbook escrito para um tenant limpo.
                        #
                        # Então não se afirma "a primeira fica na base" — mede-se
                        # o que É invariante: o acumulado cresce, e o degrau que
                        # as eleva é o do fracionamento.
                        rb.conferir('o acumulado da janela CRESCE a cada fatia',
                                    a1 < a2 < a3,
                                    f'{a1} → {a2} → {a3} (no cenário do manual '
                                    f'a janela já começa cheia, por causa das '
                                    f'irmãs na mesma obra e etapa NULA; no do '
                                    f'piloto ela começa na primeira fatia)')
                        # 🔬 19/08, e este é o achado do cenário de piloto: numa
                        # janela LIMPA a primeira NÃO sobe, e quem sobe é a
                        # SEGUNDA — 📖 exatamente a correção `← EXEC` do passo 3c
                        # ("com 3 × R$ 4.900 quem sobe é a SEGUNDA, 9.800 > 5.000,
                        # não a terceira"). No cenário do MANUAL isso é invisível,
                        # porque a janela já chega cheia e as três sobem. A
                        # conferência é portátil: vale nos dois.
                        rb.conferir('a SEGUNDA sobe, e o motivo é FRACIONAMENTO',
                                    n2 > b2 and 'fracionamento' in c2,
                                    f'base={b2} efetiva={n2} motivos={c2}')
                        rb.conferir('o degrau é monotônico — uma vez que sobe, '
                                    'não desce',
                                    n1 <= n2 <= n3,
                                    f'{n1} → {n2} → {n3}')
                        rb.conferir('fatia sem degrau tem motivo vazio, e com '
                                    'degrau tem fracionamento',
                                    all((('fracionamento' in c) == (n > b))
                                        for n, b, c in ((n1, b1, c1), (n2, b2, c2),
                                                        (n3, b3, c3))),
                                    f'({n1},{c1}) ({n2},{c2}) ({n3},{c3}) — '
                                    f'motivo sem degrau, ou degrau sem motivo, '
                                    f'seria trilha mentindo sobre a decisão')
                        rb.conferir('a faixa BASE das três é a mesma (mesmo valor)',
                                    b1 == b2 == b3,
                                    f'{b1}/{b2}/{b3} — o degrau é do acumulado, '
                                    f'não do valor da linha')
                except Exception as e:
                    rb.quebrou('o passo (3a/3c) chegou ao fim', e)

                # ── 3e — a emergência ──────────────────────────────────────
                rb.passo('(3e) emergência: aprova na hora, e a ratificação fica devendo')
                try:
                    # 🔬 19/08: com o SOLICITANTE a tela recusa, e com razão —
                    # "só um gestor desta obra ou um administrador pode invocar
                    # o rito de emergência". É a decisão D4 do spec (GESTOR da
                    # obra e ADMIN, 48h corridas). A primeira rodada deste script
                    # usou o solicitante e leu a recusa como falha do sistema.
                    pg = pagina('gestor')
                    antes = {r.id for r in RequisicaoCompra.query.filter_by(
                        admin_id=admin_id).all()}
                    aviso = nova_requisicao(
                        pg, obra_id, 'Bomba quebrou; concretagem para na obra.',
                        Decimal('2500.00'), emergencial=True)
                    frescos()
                    nova = [r for r in RequisicaoCompra.query.filter_by(
                        admin_id=admin_id).all() if r.id not in antes]
                    rb.conferir('a requisição emergencial foi criada', bool(nova),
                                aviso[:200])
                    if nova:
                        r = nova[0]
                        rb.conferir('ela nasce carimbada como emergencial',
                                    bool(getattr(r, 'emergencial', False)),
                                    'sem o carimbo o rito das 48h não existe')
                        rb.conferir('ela nasce SEM ratificação',
                                    getattr(r, 'ratificada_em', None) is None,
                                    'é a dívida que a emergência cria')
                except Exception as e:
                    rb.quebrou('o passo (3e) chegou ao fim', e)

            nav.close()
    finally:
        # ── Rollback: devolve a flag ao estado em que estava ───────────────
        with app.app_context():
            if not estado_original:
                _flag('flag_alcadas_avancadas.py', admin_id, '--desligar')
            rb.passo('rollback — a flag volta ao estado original')
            frescos()
            cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
            rb.conferir('a flag foi devolvida',
                        bool(getattr(cfg, 'alcadas_avancadas_ativa', False))
                        == estado_original,
                        f'original={estado_original}, agora='
                        f'{bool(getattr(cfg, "alcadas_avancadas_ativa", False))} — '
                        f'📖 desligar NÃO reescreve `regime_alcada` das que já '
                        f'nasceram avançadas, de propósito')

    # ── 4. o sensor ────────────────────────────────────────────────────────
    rb.passo('(4) o sensor de consistência das alçadas')
    p = rodar_python(
        [sys.executable, 'scripts/verificar_consistencia_alcadas.py', str(admin_id)],
        RAIZ)
    RUIDO = ('SAWarning', 'return cls.query_class', 'INFO:', 'WARNING:', 'tensorflow')
    for linha in [l for l in ((p.stdout or '') + (p.stderr or '')).splitlines()
                  if l.strip() and not any(x in l for x in RUIDO)][-15:]:
        print(f'   | {linha}')
    # 📖 EXEC: o achado 1 do sensor NÃO é sempre escrita por fora — ele recalcula
    # a faixa HOJE, e o acumulado da janela anda. Depois de criar três irmãs de
    # propósito, achado aqui é a janela andando, não incidente.
    rb.conferir('o sensor rodou', p.returncode in (0, 1), f'exit {p.returncode}')

    return rb.relatorio()


if __name__ == '__main__':
    sys.exit(main())
