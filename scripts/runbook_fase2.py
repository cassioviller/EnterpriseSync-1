#!/usr/bin/env python3
"""Roda o runbook da Fase 2 do ciclo de compras PELA TELA, por script.

Uso:
    python scripts/runbook_fase2.py              # semeia e roda o ciclo inteiro
    python scripts/runbook_fase2.py --sem-semear # aproveita o cenário que está lá

Pré-requisito: o app de pé em http://localhost:5000.

POR QUE ESTE ARQUIVO EXISTE. O runbook da Fase 2 mora em
📖 `docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md:326-364`
e pede o ciclo (a) a (g) numa obra piloto, com TRÊS pessoas diferentes. Ele
nunca foi rodado: o `ESTADO-ATUAL.md` registra desde 17/08 que "ninguém abriu o
navegador", e foi ao preparar essa rodada que apareceu o 500 de
`/financeiro/fechamento-pagamentos`, parado desde 22/07.

A SUÍTE NÃO SUBSTITUI ISTO, e a razão é precisa. O `test_client` percorre rotas
que o teste escolhe e monta o POST no código do teste. Ele responde "a rota
funciona quando chamada". A pergunta do runbook é outra: **existe caminho pela
tela?** Um botão que não é renderizado, um formulário que a permissão esconde ou
um serviço sem chamador de produção passam pelo `test_client` inteiros — foi
exatamente assim que `liberar()` ficou testado e inalcançável até 17/08.

Por isso aqui cada passo:

  1. ACHA O CONTROLE NO DOM antes de agir. Botão ausente é FALHA do passo, com
     o nome do passo — não um POST na URL que o operador não teria como chamar.
  2. Preenche o formulário QUE ESTÁ NA TELA e submete pelo navegador, então o
     CSRF, o `required` e o que o JS mexe entram na conta.
  3. CONFERE NO BANCO, com a coluna que a tabela do runbook nomeia.

A REGRA DESTE ARQUIVO, herdada de `capturar_manual_compras.py`: falhou, fica
registrado e o processo sai com código ≠ 0. Mas ao contrário da captura, aqui um
passo que falha NÃO derruba a rodada: um runbook que para no primeiro tropeço
esconde os outros seis, e quem retoma precisa da lista inteira.

As três pessoas do runbook são quatro, porque o ciclo tem quatro atos:
    comprador (Diego)  emite o pedido
    gestor (Paula)     atesta o recebimento
    admin (Ana)        lança a nota, libera, e FECHA o lote
    financeiro (Helena) monta o lote e paga
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

# `preparar_bibliotecas` resolve as cinco .so do Chromium no nix store. Está lá
# e não aqui porque a captura do manual a descobriu primeiro; duplicá-la seria
# criar duas listas para divergir.
from capturar_manual_compras import preparar_bibliotecas

BASE = os.environ.get('SIGE_BASE', 'http://localhost:5000')
RAIZ = Path(__file__).resolve().parent.parent
VIEWPORT = {'width': 1440, 'height': 950}

# Quanto do pedido é atestado. MENOR que o pedido de propósito: é o que faz o
# passo (f) ter o que conferir — `liberar()` derruba a conta para o valor do que
# chegou e escreve a diferença na observação.
QTD_PEDIDA = Decimal('120')
QTD_ATESTADA = Decimal('100')


# ── o registro da rodada ────────────────────────────────────────────────────
class Runbook:
    """Acumula o resultado de cada conferência, sem parar na primeira falha."""

    def __init__(self):
        self.linhas = []
        self.passo_atual = '—'

    def passo(self, nome):
        self.passo_atual = nome
        print(f'\n── {nome}')

    def conferir(self, o_que, condicao, detalhe=''):
        ok = bool(condicao)
        self.linhas.append((self.passo_atual, o_que, ok, detalhe))
        marca = 'ok  ' if ok else 'FALHA'
        print(f'   [{marca}] {o_que}' + (f' — {detalhe}' if detalhe else ''))
        return ok

    def quebrou(self, o_que, erro):
        self.linhas.append((self.passo_atual, o_que, False, f'{type(erro).__name__}: {erro}'))
        print(f'   [FALHA] {o_que} — {type(erro).__name__}: {erro}')

    @property
    def falhas(self):
        return [l for l in self.linhas if not l[2]]

    def relatorio(self):
        print('\n' + '=' * 72)
        total, falhas = len(self.linhas), len(self.falhas)
        print(f'RUNBOOK DA FASE 2 — {total - falhas} de {total} conferências passaram')
        if falhas:
            print(f'\n{falhas} FALHA(S):')
            passo_anterior = None
            for passo, o_que, _ok, detalhe in self.falhas:
                if passo != passo_anterior:
                    print(f'\n  {passo}')
                    passo_anterior = passo
                print(f'    - {o_que}')
                if detalhe:
                    print(f'      {detalhe}')
        print('=' * 72)
        return 1 if falhas else 0


rb = Runbook()


# ── o banco, lido de fora do servidor ───────────────────────────────────────
# Processo separado do que atende as telas: por isso todo bloco de conferência
# começa por `frescos()`. Sem isso a sessão desta ponta continuaria dentro da
# transação em que abriu e leria o estado de antes do clique — o defeito que
# faria este script aprovar uma tela que não gravou nada.
def frescos():
    from app import db
    db.session.rollback()
    db.session.expire_all()


def _pessoas_e_obra():
    from models import Obra, Usuario
    from seed_manual_compras import MARCA, PESSOAS
    pessoas = {}
    for chave, username, _nome, _cargo in PESSOAS:
        u = Usuario.query.filter_by(username=username).first()
        if u is None:
            raise SystemExit(f'cenário ausente: usuário {username} não existe. '
                             f'Rode `python scripts/seed_manual_compras.py`.')
        pessoas[chave] = u
    admin = pessoas['admin']
    obra = Obra.query.filter_by(admin_id=admin.id).order_by(Obra.id).first()
    if obra is None:
        raise SystemExit('cenário ausente: o tenant do manual não tem obra.')
    return pessoas, obra


# ── o navegador ─────────────────────────────────────────────────────────────
def entrar(page, username, senha):
    page.goto(f'{BASE}/login', wait_until='domcontentloaded', timeout=30000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', senha)
    page.click('button[type="submit"]')
    page.wait_for_load_state('domcontentloaded')
    if '/login' in page.url:
        raise SystemExit(f'login falhou para {username} — URL final {page.url}')


def abrir(page, rota):
    """Vai até a rota e devolve o status. Cair no login é falha, não redirect."""
    resp = page.goto(f'{BASE}{rota}', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(400)
    status = resp.status if resp is not None else 0
    if '/login' in page.url:
        raise RuntimeError(f'{rota} devolveu o login — sem sessão ou sem permissão')
    return status


def avisos(page):
    """O texto dos flashes da página. É por eles que a tela recusa."""
    return ' | '.join(t.strip() for t in page.eval_on_selector_all(
        '.alert, .toast-body', 'ns => ns.map(n => n.innerText)') if t.strip())


def submeter(page, seletor_form):
    """Clica o botão de submit DO formulário indicado.

    Não é preciosismo de seletor: 📖 `templates/compras/nota.html:150` tem
    `<button class="btn btn-primary">` SEM `type`, que é submit por default do
    HTML mas não casa com `button[type="submit"]` — e a tela ainda tem um
    segundo formulário (excluir nota) acima dele. Um seletor solto ou não acha
    nada ou aperta o botão errado.
    """
    botao = page.query_selector(f'{seletor_form} button[type="submit"]') \
        or page.query_selector(f'{seletor_form} button:not([type="button"])')
    if botao is None:
        raise RuntimeError(f'nenhum botão de submit em {seletor_form}')
    botao.click()
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_timeout(700)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sem-semear', action='store_true',
                    help='não recria o cenário antes de rodar')
    args = ap.parse_args()

    preparar_bibliotecas()

    # ── 0. o cenário ────────────────────────────────────────────────────────
    if not args.sem_semear:
        print('semeando o cenário (scripts/seed_manual_compras.py)…')
        p = subprocess.run([sys.executable, 'scripts/seed_manual_compras.py'],
                           cwd=RAIZ, capture_output=True, text=True)
        if p.returncode != 0:
            print(p.stdout[-3000:])
            print(p.stderr[-3000:])
            raise SystemExit('o seed falhou — o runbook não roda sem cenário')
        print('   cenário pronto')

    from app import app, db
    from models import (ContaPagar, FechamentoPagamento, PedidoCompra,
                        RequisicaoCompra)
    from seed_manual_compras import MARCA, SENHA

    with app.app_context():
        pessoas, obra = _pessoas_e_obra()
        admin = pessoas['admin']
        admin_id = admin.id
        ids = {k: u.id for k, u in pessoas.items()}
        nomes = {k: u.nome for k, u in pessoas.items()}
        usuarios = {k: f'{MARCA}_{k}' for k in pessoas}

        # 🔬 O runbook exige TRÊS pessoas diferentes. Conferido aqui, no início,
        # porque um cenário em que duas chaves apontam para a mesma linha faria
        # a segregação passar por acidente.
        rb.passo('0 — o cenário')
        rb.conferir('quem emite, quem monta e quem fecha são pessoas distintas',
                    len({ids['comprador'], ids['financeiro'], ids['admin']}) == 3,
                    f"{nomes['comprador']} / {nomes['financeiro']} / {nomes['admin']}")

        req = RequisicaoCompra.query.filter_by(
            admin_id=admin_id, numero='RC-2026-0004').first()
        rb.conferir('a requisição aprovada do cenário existe', req is not None,
                    f'RC-2026-0004 em {req.estado.name if req else "—"}')
        if req is None:
            return rb.relatorio()
        req_id = req.id

        # As duas flags, na ordem em que dependem uma da outra. O passo 0 do
        # runbook chama o regime de recebimento de PRÉ-REQUISITO DURO: sem ele
        # a conta do Fluxo A nasce bloqueada e não há caminho para liberar.
        from scripts.flag_financeiro_dois_fluxos import financeiro_dois_fluxos_ativo
        from scripts.flag_recebimento_atesto import recebimento_atesto_ativo
        rb.conferir('recebimento_atesto_ativo (pré-requisito duro)',
                    bool(recebimento_atesto_ativo(admin_id)))
        rb.conferir('financeiro_dois_fluxos_ativo',
                    bool(financeiro_dois_fluxos_ativo(admin_id)))

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        paginas = {}

        def pagina(chave):
            if chave not in paginas:
                ctx = navegador.new_context(viewport=VIEWPORT)
                pg = ctx.new_page()
                entrar(pg, usuarios[chave], SENHA)
                paginas[chave] = pg
            return paginas[chave]

        with app.app_context():
            pedido_id = conta_id = None
            venc = None

            # ── (a) emitir → a conta nasce bloqueada ────────────────────────
            rb.passo('(a) emitir o pedido — o comprador, pela tela da requisição')
            try:
                pg = pagina('comprador')
                abrir(pg, f'/compras/requisicoes/{req_id}')
                form = pg.query_selector('form[action*="emitir-pedido"]')
                rb.conferir('o formulário "Emitir pedido de compra" está na tela',
                            form is not None,
                            'ausente = quem tem papel de comprador não tem caminho'
                            if form is None else '')
                if form is not None:
                    opcoes = pg.eval_on_selector_all(
                        'form[action*="emitir-pedido"] select[name="fornecedor_id"] option',
                        'ns => ns.map(n => n.value).filter(v => v)')
                    pg.select_option('form[action*="emitir-pedido"] select[name="fornecedor_id"]',
                                     opcoes[0])
                    # '30d', não '30_dias': as chaves são as de
                    # 📖 `compras_views.CONDICOES:59-66`, e o seletor recusa
                    # em silêncio o que não está lá.
                    pg.select_option('form[action*="emitir-pedido"] select[name="condicao_pagamento"]',
                                     '30d')
                    pg.fill('form[action*="emitir-pedido"] input[name="data_compra"]',
                            date.today().isoformat())
                    pg.click('form[action*="emitir-pedido"] button[type="submit"], '
                             'form[action*="emitir-pedido"] button:not([type])')
                    pg.wait_for_load_state('domcontentloaded')
                    pg.wait_for_timeout(600)

                    frescos()
                    ped = PedidoCompra.query.filter_by(
                        admin_id=admin_id, requisicao_id=req_id).first()
                    rb.conferir('o pedido foi criado', ped is not None, avisos(pg)[:200])
                    if ped is not None:
                        pedido_id = ped.id
                        venc = ped.data_vencimento_primeira_parcela
                        rb.conferir('o pedido exige atesto', bool(ped.exige_atesto))
                        rb.conferir("fluxo_pagamento do pedido novo = 'faturado'",
                                    ped.fluxo_pagamento == 'faturado',
                                    f'fluxo_pagamento = {ped.fluxo_pagamento}')
                        conta = ContaPagar.query.filter_by(
                            admin_id=admin_id, pedido_compra_id=ped.id).first()
                        rb.conferir('a ContaPagar nasceu junto', conta is not None)
                        if conta is not None:
                            conta_id = conta.id
                            venc = conta.data_vencimento or venc
                            rb.conferir("situacao_liberacao da conta nova = 'bloqueada'",
                                        conta.situacao_liberacao == 'bloqueada',
                                        f'situacao_liberacao = {conta.situacao_liberacao}'
                                        " — 'liberada' no Fluxo A = o carimbo do fluxo não pegou")
            except Exception as e:
                rb.quebrou('o passo (a) chegou ao fim', e)

            if conta_id is None:
                print('\n!! sem conta, o resto do runbook não tem sujeito')
                return rb.relatorio()

            # ── (b) pagar → RECUSA nomeando a perna ─────────────────────────
            rb.passo('(b) tentar pagar — o financeiro, com a tríade aberta')
            try:
                pg = pagina('financeiro')
                st = abrir(pg, f'/financeiro/contas-pagar/{conta_id}/pagar')
                rb.conferir('a tela de baixa abre para o financeiro', st < 400,
                            f'HTTP {st}')
                if st < 400:
                    pg.fill('input[name="valor_pago"]', '100.00')
                    pg.fill('input[name="data_pagamento"]', date.today().isoformat())
                    submeter(pg, 'form:has(input[name="valor_pago"])')
                    texto = avisos(pg)
                    frescos()
                    conta = db.session.get(ContaPagar, conta_id)
                    rb.conferir('a baixa foi RECUSADA',
                                (conta.status or '').upper() != 'PAGO',
                                f'status = {conta.status}')
                    rb.conferir('a recusa NOMEIA a perna que falta',
                                'nota' in texto.lower() or 'atesto' in texto.lower(),
                                texto[:220] or '(nenhum aviso na tela)')
            except Exception as e:
                rb.quebrou('o passo (b) chegou ao fim', e)

            # ── (c) atestar ────────────────────────────────────────────────
            rb.passo('(c) atestar o recebimento — o gestor, no portão da obra')
            try:
                pg = pagina('gestor')
                abrir(pg, f'/compras/{pedido_id}')
                link = pg.query_selector(f'a[href*="/compras/{pedido_id}/recebimento"]')
                rb.conferir('o botão de registrar recebimento está na tela do pedido',
                            link is not None)
                st = abrir(pg, f'/compras/{pedido_id}/recebimento')
                rb.conferir('a tela de recebimento abre', st < 400, f'HTTP {st}')
                if st < 400:
                    campo = pg.query_selector('input[name^="qtd_"]')
                    rb.conferir('a tela traz campo de quantidade por item',
                                campo is not None)
                    if campo is not None:
                        campo.fill(str(QTD_ATESTADA))
                        pg.fill('input[name="data_recebimento"]', date.today().isoformat())
                        submeter(pg, 'form:has(input[name="data_recebimento"])')
                        frescos()
                        from services.recebimento_pedido import valor_atestado
                        ped = db.session.get(PedidoCompra, pedido_id)
                        atestado = Decimal(str(valor_atestado(ped) or 0))
                        rb.conferir('valor_atestado > 0', atestado > 0,
                                    f'valor_atestado = {atestado} '
                                    f'({QTD_ATESTADA} de {QTD_PEDIDA} — parcial de propósito)')
            except Exception as e:
                rb.quebrou('o passo (c) chegou ao fim', e)

            # ── (d) lançar nota ────────────────────────────────────────────
            rb.passo('(d) lançar a nota — pela tela do pedido (17/08)')
            try:
                pg = pagina('admin')
                abrir(pg, f'/compras/{pedido_id}')
                link = pg.query_selector(f'a[href*="/compras/{pedido_id}/nota"]')
                rb.conferir('o botão "Notas fiscais" está no painel da tríade',
                            link is not None,
                            'até 17/08 este passo só existia no shell'
                            if link is None else '')
                st = abrir(pg, f'/compras/{pedido_id}/nota')
                rb.conferir('a tela da nota abre', st < 400, f'HTTP {st}')
                if st < 400:
                    frescos()
                    ped = db.session.get(PedidoCompra, pedido_id)
                    pg.fill('input[name="numero"]', '990001')
                    pg.fill('input[name="valor_total"]',
                            f'{Decimal(str(ped.valor_total or 0)):.2f}')
                    pg.fill('input[name="data_emissao"]', date.today().isoformat())
                    pg.fill('input[name="data_vencimento"]',
                            (date.today() + timedelta(days=30)).isoformat())
                    submeter(pg, 'form:has(input[name="numero"])')
                    frescos()
                    from services.financeiro_compra import valor_das_notas
                    ped = db.session.get(PedidoCompra, pedido_id)
                    rb.conferir('a nota foi lançada',
                                Decimal(str(valor_das_notas(ped) or 0)) > 0,
                                avisos(pg)[:200])
            except Exception as e:
                rb.quebrou('o passo (d) chegou ao fim', e)

            # ── (d2) liberar ───────────────────────────────────────────────
            rb.passo('(d2) liberar — o passo que FALTAVA na lista até 17/08')
            try:
                pg = pagina('admin')
                abrir(pg, f'/compras/{pedido_id}')
                form = pg.query_selector(f'form[action*="/compras/{pedido_id}/liberar"]')
                rb.conferir('o botão de liberar está na tela do pedido',
                            form is not None,
                            'ausente = a conta fica bloqueada para sempre'
                            if form is None else '')
                if form is not None:
                    pg.click(f'form[action*="/compras/{pedido_id}/liberar"] button')
                    pg.wait_for_load_state('domcontentloaded')
                    pg.wait_for_timeout(600)
                    frescos()
                    conta = db.session.get(ContaPagar, conta_id)
                    rb.conferir("a conta passou a 'liberada'",
                                conta.situacao_liberacao == 'liberada',
                                f'situacao_liberacao = {conta.situacao_liberacao} '
                                f'| {avisos(pg)[:160]}')
            except Exception as e:
                rb.quebrou('o passo (d2) chegou ao fim', e)

            # ── (f) o valor caiu para o atestado ───────────────────────────
            rb.passo('(f) o valor da conta caiu para o atestado, com a diferença na observação')
            try:
                frescos()
                from services.recebimento_pedido import valor_atestado
                ped = db.session.get(PedidoCompra, pedido_id)
                conta = db.session.get(ContaPagar, conta_id)
                atestado = Decimal(str(valor_atestado(ped) or 0))
                valor = Decimal(str(conta.valor_original or 0))
                rb.conferir('valor_original da conta == valor atestado',
                            valor == atestado,
                            f'conta = {valor} | atestado = {atestado} '
                            f'| pedido = {ped.valor_total}')
                rb.conferir('a diferença está escrita na observação',
                            'valor ajustado' in (conta.observacoes or ''),
                            (conta.observacoes or '(observação vazia)')[-160:])
            except Exception as e:
                rb.quebrou('o passo (f) chegou ao fim', e)

            # ── (e) o lote, e a segregação de função ───────────────────────
            rb.passo('(e) montar o lote (financeiro) e pedir a OUTRA pessoa que feche (admin)')
            fech_id = None
            try:
                frescos()
                conta = db.session.get(ContaPagar, conta_id)
                data_lote = (conta.data_vencimento or date.today()).isoformat()

                pg = pagina('financeiro')
                st = abrir(pg, f'/financeiro/fechamento-pagamentos?data_fechamento={data_lote}')
                # 🔬 Esta é a tela que respondeu 500 de 22/07 a 18/08. A
                # conferência fica aqui, no caminho, e não num teste à parte:
                # é o passo do runbook que ela travava.
                rb.conferir('a tela do fechamento de pagamentos abre', st < 400,
                            f'HTTP {st} (500 aqui foi o defeito de 22/07)')
                if st < 400:
                    caixa = pg.query_selector(f'input[name="conta_ids"][value="{conta_id}"]')
                    rb.conferir('a conta liberada aparece na lista do ciclo',
                                caixa is not None,
                                f'conta {conta_id}, vencimento {data_lote}')
                    if caixa is not None:
                        caixa.check()
                        pg.fill('#formFechamento input[name="descricao"]',
                                'Runbook da Fase 2 — rodado por script')
                        pg.click('#formFechamento button[type="submit"]')
                        pg.wait_for_load_state('domcontentloaded')
                        pg.wait_for_timeout(700)

                        frescos()
                        conta = db.session.get(ContaPagar, conta_id)
                        rb.conferir('a conta entrou num lote',
                                    conta.fechamento_id is not None,
                                    avisos(pg)[:200])
                        if conta.fechamento_id:
                            fech_id = conta.fechamento_id
                            fech = db.session.get(FechamentoPagamento, fech_id)
                            rb.conferir(
                                'criado_por_id do lote = quem o montou',
                                fech.criado_por_id == ids['financeiro'],
                                f"criado_por_id = {fech.criado_por_id}, esperado "
                                f"{ids['financeiro']} ({nomes['financeiro']}) — "
                                f"NULL deixa a segregação sem o lado de quem monta")
            except Exception as e:
                rb.quebrou('montar o lote chegou ao fim', e)

            # (e-ii) a MESMA pessoa tenta fechar — tem de ser recusada
            if fech_id:
                try:
                    pg = pagina('financeiro')
                    abrir(pg, f'/financeiro/fechamento-pagamentos?data_fechamento={data_lote}')
                    botao = pg.query_selector(
                        f'form:has(input[name="fechamento_id"][value="{fech_id}"]) '
                        f'input[name="action"][value="fechar"]')
                    if botao is not None:
                        pg.eval_on_selector(
                            f'form:has(input[name="fechamento_id"][value="{fech_id}"]):'
                            f'has(input[value="fechar"])',
                            'f => { f.onsubmit = null; f.submit(); }')
                        pg.wait_for_load_state('domcontentloaded')
                        pg.wait_for_timeout(700)
                    frescos()
                    fech = db.session.get(FechamentoPagamento, fech_id)
                    rb.conferir(
                        'quem montou o lote é RECUSADO ao tentar fechá-lo',
                        fech.status == 'ABERTO',
                        f'status = {fech.status}, fechado_por_id = {fech.fechado_por_id} '
                        f'— a segregação de função é o motivo de o lote existir')
                except Exception as e:
                    rb.quebrou('a tentativa da mesma pessoa chegou ao fim', e)

                # (e-iii) a OUTRA pessoa fecha
                try:
                    frescos()
                    fech = db.session.get(FechamentoPagamento, fech_id)
                    if fech.status != 'ABERTO':
                        # Só chega aqui se a recusa acima não veio. Reabre para
                        # que o passo seguinte ainda possa ser medido — o que
                        # falhou já está registrado.
                        pg = pagina('admin')
                        abrir(pg, f'/financeiro/fechamento-pagamentos?data_fechamento={data_lote}')
                        pg.eval_on_selector(
                            f'form:has(input[name="fechamento_id"][value="{fech_id}"]):'
                            f'has(input[value="reabrir"])',
                            'f => f.submit()')
                        pg.wait_for_load_state('domcontentloaded')
                        pg.wait_for_timeout(700)

                    pg = pagina('admin')
                    abrir(pg, f'/financeiro/fechamento-pagamentos?data_fechamento={data_lote}')
                    pg.eval_on_selector(
                        f'form:has(input[name="fechamento_id"][value="{fech_id}"]):'
                        f'has(input[value="fechar"])',
                        'f => { f.onsubmit = null; f.submit(); }')
                    pg.wait_for_load_state('domcontentloaded')
                    pg.wait_for_timeout(700)
                    frescos()
                    fech = db.session.get(FechamentoPagamento, fech_id)
                    rb.conferir('o lote foi fechado', fech.status == 'FECHADO',
                                f'status = {fech.status}')
                    rb.conferir(
                        'fechado_por_id do lote = quem fechou',
                        fech.fechado_por_id == ids['admin'],
                        f"fechado_por_id = {fech.fechado_por_id}, esperado "
                        f"{ids['admin']} ({nomes['admin']}) — NULL, diz a tabela do "
                        f"runbook, significa que a segregação não valeu")
                except Exception as e:
                    rb.quebrou('o fechamento pela outra pessoa chegou ao fim', e)

            # ── (g) pagar → passa ──────────────────────────────────────────
            rb.passo('(g) pagar — agora a baixa tem de passar')
            try:
                frescos()
                conta = db.session.get(ContaPagar, conta_id)
                valor = Decimal(str(conta.saldo or conta.valor_original or 0))
                pg = pagina('financeiro')
                st = abrir(pg, f'/financeiro/contas-pagar/{conta_id}/pagar')
                rb.conferir('a tela de baixa abre', st < 400, f'HTTP {st}')
                if st < 400:
                    pg.fill('input[name="valor_pago"]', f'{valor:.2f}')
                    pg.fill('input[name="data_pagamento"]', date.today().isoformat())
                    submeter(pg, 'form:has(input[name="valor_pago"])')
                    frescos()
                    conta = db.session.get(ContaPagar, conta_id)
                    rb.conferir('a conta foi PAGA',
                                (conta.status or '').upper() in ('PAGO', 'PARCIAL'),
                                f'status = {conta.status}, valor_pago = {conta.valor_pago} '
                                f'| {avisos(pg)[:160]}')
            except Exception as e:
                rb.quebrou('o passo (g) chegou ao fim', e)

        navegador.close()

    # ── 3. o sensor ─────────────────────────────────────────────────────────
    rb.passo('(3) o sensor de consistência, depois do piloto')
    p = subprocess.run(
        [sys.executable, 'scripts/verificar_consistencia_financeiro.py', str(admin_id)],
        cwd=RAIZ, capture_output=True, text=True)
    # O ruído de import (SAWarning, INFO de blueprint) enterra a saída do
    # sensor — e sensor que ninguém lê é sensor que não existe.
    RUIDO = ('SAWarning', 'return cls.query_class', 'INFO:', 'WARNING:', 'tensorflow')
    saida = (p.stdout or '') + (p.stderr or '')
    uteis = [l for l in saida.strip().splitlines()
             if l.strip() and not any(r in l for r in RUIDO)]
    for linha in uteis[-20:]:
        print(f'   | {linha}')
    rb.conferir('o sensor não acusa drift', p.returncode == 0,
                f'exit {p.returncode}')

    return rb.relatorio()


if __name__ == '__main__':
    sys.exit(main())
