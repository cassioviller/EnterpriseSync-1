"""
Task #188 — Cobertura e2e para formato BR (R$ 1.234,56) nas telas de Orçamento.

Estende a Task #181/#189 cobrindo:
  1. /orcamentos (lista) — colunas Custo / Venda / Lucro em R$ N.NNN,NN.
  2. /orcamentos/<id>/editar — cards de totais, inputs de imposto/margem,
     inputs de quantidade/coeficiente/preço (composição), e os subtotais
     server-rendered por linha (`js-subtotal-tot` / `js-consumo-tot` /
     `js-subtotal-unit`).
  3. /orcamentos/novo — defaults `imposto_pct_padrao` / `lucro_pct_padrao`
     vindos de ConfiguracaoEmpresa renderizados como BR.

Para cada tela:
  * Existe pelo menos um valor visível em formato BR
    (R$ N.NNN,NN ou N,NN).
  * Nenhum texto visível casa o padrão americano /\\d+\\.\\d{2}\\b/
    (ex.: 1234.56) — bloqueia retorno de toFixed(2)/'%.2f'|format.
  * Inputs (texto) também são lidos via `input_value()` para garantir
    que não estejam em US.
  * Após digitar nova quantidade, o JS recalcula `js-subtotal-tot`
    em formato BR (espelha fmtBRL do template).

Pré-requisito: servidor Flask rodando em http://localhost:5000.

Uso:
    python tests/test_orcamento_formato_br_e2e.py
"""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import app, db  # noqa: E402
from models import (  # noqa: E402
    ComposicaoServico,
    ConfiguracaoEmpresa,
    Insumo,
    Orcamento,
    OrcamentoItem,
    PrecoBaseInsumo,
    Servico,
    TipoUsuario,
    Usuario,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'

PADRAO_BRL = re.compile(r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}')
PADRAO_NUM_BR_2 = re.compile(r'\b\d{1,3}(?:\.\d{3})*,\d{2}\b')
PADRAO_US_2D = re.compile(r'\d+\.\d{2}\b')


def _suf() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def seed_dados():
    """Cria admin + ConfiguracaoEmpresa + serviço com composição + orçamento.

    Calibrado para gerar valores ≥ R$ 1.000 em totais e custo unit, exigindo
    o separador de milhar (testa o caminho 'R$ 1.234,56' tanto em cards
    quanto em inputs).
    """
    suf = _suf()
    email = f't188pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f't188pw_{suf}',
            email=email,
            nome='T188 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id

        # ConfiguracaoEmpresa fornece os defaults usados em /orcamentos/novo.
        # 13,00 / 20,00 são valores que claramente diferem de "13.00".
        cfg = ConfiguracaoEmpresa(
            admin_id=admin_id,
            nome_empresa=f'Empresa T188 {suf[-6:]}',
            imposto_pct_padrao=Decimal('13.00'),
            lucro_pct_padrao=Decimal('20.00'),
        )
        db.session.add(cfg)

        # Insumos (com preço base) — coef × preço gera valores grandes.
        ins_a = Insumo(admin_id=admin_id, nome=f'__t188_aco_{suf}',
                       tipo='MATERIAL', unidade='kg')
        ins_b = Insumo(admin_id=admin_id, nome=f'__t188_mo_{suf}',
                       tipo='MAO_OBRA', unidade='h')
        db.session.add_all([ins_a, ins_b])
        db.session.flush()
        db.session.add_all([
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_a.id,
                            valor=Decimal('35.0000'),
                            vigencia_inicio=datetime(2020, 1, 1).date()),
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_b.id,
                            valor=Decimal('170.0000'),
                            vigencia_inicio=datetime(2020, 1, 1).date()),
        ])

        svc = Servico(
            admin_id=admin_id,
            nome=f'__t188_svc_{suf}',
            categoria='Teste',
            unidade_medida='m2',
            custo_unitario=Decimal('5308.99'),
            imposto_pct=Decimal('13.00'),
            margem_lucro_pct=Decimal('20.00'),
            preco_venda_unitario=Decimal('7199.06'),
        )
        db.session.add(svc)
        db.session.flush()
        db.session.add_all([
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_a.id,
                              coeficiente=Decimal('150.0000')),
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_b.id,
                              coeficiente=Decimal('0.3471')),
        ])

        # Orçamento com 1 item (qtd=2,5 m²) — totais exibíveis com milhar.
        # custo_unit ≈ 35*150 + 170*0,3471 = 5.250 + 59,007 = 5.309,007
        # preco_unit = 5.309,007 / (1 - 0,13 - 0,20) = 5.309,007 / 0,67
        #            = 7.924,9358...
        # custo_tot  = 5.309,007 * 2,5 = 13.272,52 (snapshot quantize 0.01)
        # venda_tot  = 7.924,9358 * 2,5 ≈ 19.812,34
        # lucro_tot  = 19.812,34 - 13.272,52 = 6.539,82
        # NOTA: confirmação exata de cada total é deixada ao backend (rota
        # /atualizar-item recalcula). Aqui semeamos snapshot consistente.
        orc = Orcamento(
            admin_id=admin_id,
            criado_por=admin_id,
            numero=f'ORC-T188-{suf[-6:]}',
            titulo=f'Orçamento T188 {suf[-6:]}',
            descricao='Teste BR — Task #188',
            cliente_nome='Cliente Orçamento 188',
            imposto_pct_global=Decimal('13.00'),
            margem_pct_global=Decimal('20.00'),
            custo_total=Decimal('13272.52'),
            venda_total=Decimal('19812.34'),
            lucro_total=Decimal('6539.82'),
            status='rascunho',
        )
        db.session.add(orc)
        db.session.flush()

        item = OrcamentoItem(
            admin_id=admin_id,
            orcamento_id=orc.id,
            ordem=1,
            servico_id=svc.id,
            descricao=f'Item __t188_{suf}',
            unidade='m2',
            quantidade=Decimal('2.5000'),
            imposto_pct=Decimal('13.00'),
            margem_pct=Decimal('20.00'),
            custo_unitario=Decimal('5309.0070'),
            preco_venda_unitario=Decimal('7924.9358'),
            custo_total=Decimal('13272.52'),
            venda_total=Decimal('19812.34'),
            lucro_total=Decimal('6539.82'),
            composicao_snapshot=[
                {
                    'tipo': 'MATERIAL',
                    'insumo_id': ins_a.id,
                    'nome': ins_a.nome,
                    'unidade': 'kg',
                    'coeficiente': '150.0000',
                    'preco_unitario': '35.0000',
                    'subtotal_unitario': '5250.0000',
                },
                {
                    'tipo': 'MAO_OBRA',
                    'insumo_id': ins_b.id,
                    'nome': ins_b.nome,
                    'unidade': 'h',
                    'coeficiente': '0.3471',
                    'preco_unitario': '170.0000',
                    'subtotal_unitario': '59.0070',
                },
            ],
        )
        db.session.add(item)
        db.session.commit()

        return {
            'email': email,
            'admin_id': admin_id,
            'cfg_id': cfg.id,
            'svc_id': svc.id,
            'ins_a_id': ins_a.id,
            'ins_b_id': ins_b.id,
            'orc_id': orc.id,
            'item_id': item.id,
            'orc_numero': orc.numero,
            'orc_titulo': orc.titulo,
            'svc_nome': svc.nome,
        }


def cleanup(ctx):
    if not ctx:
        return
    with app.app_context():
        try:
            # Delete (cascata em itens).
            db.session.query(Orcamento).filter_by(id=ctx['orc_id']).delete()
            ComposicaoServico.query.filter_by(servico_id=ctx['svc_id']).delete()
            PrecoBaseInsumo.query.filter(
                PrecoBaseInsumo.insumo_id.in_([ctx['ins_a_id'], ctx['ins_b_id']])
            ).delete(synchronize_session=False)
            svc = db.session.get(Servico, ctx['svc_id'])
            if svc:
                db.session.delete(svc)
            for iid in (ctx['ins_a_id'], ctx['ins_b_id']):
                ins = db.session.get(Insumo, iid)
                if ins:
                    db.session.delete(ins)
            cfg = db.session.get(ConfiguracaoEmpresa, ctx['cfg_id'])
            if cfg:
                db.session.delete(cfg)
            adm = db.session.get(Usuario, ctx['admin_id'])
            if adm:
                db.session.delete(adm)
            db.session.commit()
        except Exception as e:  # pragma: no cover
            log.warning(f'Cleanup falhou: {e}')
            db.session.rollback()


def _scan_us(text: str, limit: int = 5) -> list[str]:
    """Retorna até `limit` matches do padrão americano em `text`.

    O padrão `\\d+\\.\\d{2}\\b` exige ponto + exatamente 2 dígitos seguido
    de fim de palavra. Isso já elimina por desenho falsos positivos comuns
    ('v9.0', '10.0', dates ISO 'YYYY-MM-DD'). Limita para não inflar a
    mensagem de erro do `_ok`.
    """
    return PADRAO_US_2D.findall(text)[:limit]


def main():
    ctx = seed_dados()
    log.info(f'Seed: orc={ctx["orc_id"]} item={ctx["item_id"]} '
             f'svc={ctx["svc_id"]}')
    failed: list[str] = []
    passed: list[str] = []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1366, 'height': 900})
            page = context.new_page()

            # ── 1. Login ───────────────────────────────────────────────
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url,
                f'login redirecionou (url={page.url})')

            # ── 2. /orcamentos (lista) ─────────────────────────────────
            page.goto(f'{BASE_URL}/orcamentos/', wait_until='networkidle')

            row_loc = page.locator('table tbody tr', has_text=ctx['orc_numero'])
            _ok(row_loc.count() == 1,
                f'lista: linha do nosso orçamento (count={row_loc.count()})')

            row_text = row_loc.first.inner_text()
            log.info(f'[lista] linha: {row_text!r}')

            _ok('R$ 13.272,52' in row_text,
                f'lista: custo R$ 13.272,52 ({row_text!r})')
            _ok('R$ 19.812,34' in row_text,
                f'lista: venda R$ 19.812,34 ({row_text!r})')
            _ok('R$ 6.539,82' in row_text,
                f'lista: lucro R$ 6.539,82 ({row_text!r})')

            body_text = page.locator('body').inner_text()
            ofensores = _scan_us(body_text)
            _ok(not ofensores,
                f'lista: body sem formato US (ofensores={ofensores})')

            # ── 3. /orcamentos/novo ────────────────────────────────────
            page.goto(f'{BASE_URL}/orcamentos/novo', wait_until='networkidle')

            imp_v = page.locator('input[name="imposto_pct_global"]').input_value()
            mar_v = page.locator('input[name="margem_pct_global"]').input_value()
            log.info(f'[novo] imposto_default={imp_v!r} margem_default={mar_v!r}')
            _ok(imp_v == '13,00',
                f'novo: imposto_pct_global default = "13,00" (got "{imp_v}")')
            _ok(mar_v == '20,00',
                f'novo: margem_pct_global default = "20,00" (got "{mar_v}")')
            _ok(not PADRAO_US_2D.search(imp_v),
                f'novo: imposto sem formato US (got "{imp_v}")')
            _ok(not PADRAO_US_2D.search(mar_v),
                f'novo: margem sem formato US (got "{mar_v}")')

            body_text = page.locator('body').inner_text()
            ofensores = _scan_us(body_text)
            _ok(not ofensores,
                f'novo: body sem formato US (ofensores={ofensores})')

            # ── 4. /orcamentos/<id>/editar ─────────────────────────────
            page.goto(
                f'{BASE_URL}/orcamentos/{ctx["orc_id"]}/editar',
                wait_until='networkidle',
            )

            # 4a. Cards de totais (custo / venda / lucro / margem).
            # NOTA: o template recalcula os 4 cards via JS (recalcAll) no
            # DOMContentLoaded a partir do snapshot da composição, NÃO dos
            # campos venda_total / lucro_total persistidos. Por isso os
            # esperados refletem a fórmula canônica:
            #   custoUnit = 150·35 + 0,3471·170 = 5309,007
            #   custoTot  = 5309,007 · 2,5  = 13.272,52
            #   precoUnit = round(5309,007 / 0,67, 4) = 7923,8910
            #   vendaTot  = 7923,8910 · 2,5 = 19.809,73
            #   lucroTot  = 19.809,73 - 13.272,52 = 6.537,21
            cards = page.locator('.row.g-3.mb-3 h5').all_inner_texts()
            log.info(f'[editar] cards: {cards}')
            _ok(len(cards) >= 4,
                f'editar: 4 cards de totais presentes (got {len(cards)})')
            cards_blob = ' | '.join(cards)
            _ok('R$ 13.272,52' in cards_blob,
                f'editar: card custo R$ 13.272,52 ({cards_blob!r})')
            _ok('R$ 19.809,73' in cards_blob,
                f'editar: card venda R$ 19.809,73 ({cards_blob!r})')
            _ok('R$ 6.537,21' in cards_blob,
                f'editar: card lucro R$ 6.537,21 ({cards_blob!r})')
            # Margem efetiva = 6537,21 / 19809,73 * 100 = 33,0%.
            _ok('33,0%' in cards_blob,
                f'editar: margem efetiva 33,0% ({cards_blob!r})')

            # 4b. Inputs do cabeçalho do orçamento (imposto/margem global).
            imp_global = page.locator('input[name="imposto_pct_global"]').input_value()
            mar_global = page.locator('input[name="margem_pct_global"]').input_value()
            log.info(f'[editar] imp_global={imp_global!r} mar_global={mar_global!r}')
            _ok(imp_global == '13,00',
                f'editar: imp_global = "13,00" (got "{imp_global}")')
            _ok(mar_global == '20,00',
                f'editar: mar_global = "20,00" (got "{mar_global}")')

            # 4c. Inputs do item (quantidade / imposto / margem).
            # IMPORTANTE: existem 2 inputs name="quantidade" no DOM — um do
            # form "Adicionar item" (vazio/"1") e outro dentro de cada
            # `.item-form`. Escopamos para `.item-form` para pegar o real.
            item_form = page.locator('.item-form').first
            qtd_v = item_form.locator('input[name="quantidade"]').input_value()
            log.info(f'[editar] quantidade input = {qtd_v!r}')
            _ok(qtd_v == '2,5000',
                f'editar: quantidade input = "2,5000" (got "{qtd_v}")')
            _ok(not PADRAO_US_2D.search(qtd_v),
                f'editar: quantidade input sem US (got "{qtd_v}")')

            imp_item = item_form.locator('input[name="imposto_pct"]').input_value()
            mar_item = item_form.locator('input[name="margem_pct"]').input_value()
            _ok(imp_item == '13,00',
                f'editar: imposto_pct (item) = "13,00" (got "{imp_item}")')
            _ok(mar_item == '20,00',
                f'editar: margem_pct (item) = "20,00" (got "{mar_item}")')

            # 4d. Inputs da composição (coeficiente, preço unit). 2 linhas.
            coef_inputs = item_form.locator('input[name="comp_coeficiente"]')
            preco_inputs = item_form.locator('input[name="comp_preco_unitario"]')
            n_coef = coef_inputs.count()
            _ok(n_coef == 2,
                f'editar: 2 linhas de composição (got {n_coef})')
            for i in range(n_coef):
                cv = coef_inputs.nth(i).input_value()
                pv = preco_inputs.nth(i).input_value()
                log.info(f'[editar] comp[{i}] coef={cv!r} preco={pv!r}')
                _ok(',' in cv,
                    f'editar: coef[{i}] usa vírgula decimal (got "{cv}")')
                _ok(',' in pv,
                    f'editar: preco[{i}] usa vírgula decimal (got "{pv}")')
                _ok(not PADRAO_US_2D.search(cv),
                    f'editar: coef[{i}] sem US (got "{cv}")')
                _ok(not PADRAO_US_2D.search(pv),
                    f'editar: preco[{i}] sem US (got "{pv}")')

            # Linha 1: 150,0000 / 35,0000
            _ok(coef_inputs.nth(0).input_value() == '150,0000',
                f'editar: coef[0] = "150,0000" '
                f'(got "{coef_inputs.nth(0).input_value()}")')
            _ok(preco_inputs.nth(0).input_value() == '35,0000',
                f'editar: preco[0] = "35,0000" '
                f'(got "{preco_inputs.nth(0).input_value()}")')

            # 4e. Subtotais server-rendered (.js-subtotal-tot).
            subtot_cells = page.locator('.js-subtotal-tot').all_inner_texts()
            log.info(f'[editar] subtotais render: {subtot_cells}')
            for txt in subtot_cells:
                _ok(bool(PADRAO_BRL.search(txt)),
                    f'editar: js-subtotal-tot em BR ("{txt}")')
                _ok(not PADRAO_US_2D.search(txt),
                    f'editar: js-subtotal-tot sem US ("{txt}")')

            # Linha 1: coef=150 × preco=35 × qtd=2,5 = R$ 13.125,00
            _ok(any('R$ 13.125,00' in t for t in subtot_cells),
                f'editar: subtotal[0] = R$ 13.125,00 ({subtot_cells})')

            # 4f. Subtotal unitário (server) já vem com 4 casas e R$.
            sub_unit = page.locator('.js-subtotal-unit').all_inner_texts()
            log.info(f'[editar] sub-unit: {sub_unit}')
            for t in sub_unit:
                _ok(t.strip().startswith('R$'),
                    f'editar: js-subtotal-unit começa com R$ ("{t}")')
                _ok(',' in t,
                    f'editar: js-subtotal-unit usa vírgula ("{t}")')
                _ok(not PADRAO_US_2D.search(t),
                    f'editar: js-subtotal-unit sem US ("{t}")')

            # 4g. Painel lateral por item (Custo / Venda / Lucro).
            # Tal como os cards (4a), esses spans são atualizados pelo
            # recalcAll via JS no DOMContentLoaded — refletem a fórmula
            # canônica sobre o snapshot, não os campos persistidos.
            custo_side = item_form.locator('.js-custo').inner_text()
            venda_side = item_form.locator('.js-venda').inner_text()
            lucro_side = item_form.locator('.js-lucro').inner_text()
            log.info(f'[editar] side: c={custo_side!r} v={venda_side!r} '
                     f'l={lucro_side!r}')
            _ok('R$ 13.272,52' in custo_side,
                f'editar: side custo R$ 13.272,52 (got "{custo_side}")')
            _ok('R$ 19.809,73' in venda_side,
                f'editar: side venda R$ 19.809,73 (got "{venda_side}")')
            _ok('R$ 6.537,21' in lucro_side,
                f'editar: side lucro R$ 6.537,21 (got "{lucro_side}")')

            # 4h. Recalc JS — altera quantidade para 1 e confirma que o
            # JS recalcula em formato BR (espelha fmtBRL do template).
            # Escopamos ao .item-form porque há outro input name="quantidade"
            # no form "Adicionar item" (value="1") declarado antes no DOM.
            qtd_input = item_form.locator('input[name="quantidade"]')
            qtd_input.fill('1')
            qtd_input.dispatch_event('input')
            page.wait_for_timeout(200)  # debounce do listener

            subtot_after = page.locator('.js-subtotal-tot').all_inner_texts()
            log.info(f'[editar] subtotais após qtd=1: {subtot_after}')
            # Linha 1: 150 × 35 × 1 = R$ 5.250,00 (recalcAll via JS)
            _ok(any('R$ 5.250,00' in t for t in subtot_after),
                f'editar: subtotal[0] recalculado = R$ 5.250,00 ({subtot_after})')
            for t in subtot_after:
                _ok(not PADRAO_US_2D.search(t),
                    f'editar: subtotal recalc sem US ("{t}")')

            # Card de venda também recalculado (5.250 + 59,007) ≈ 5.309,01
            # → venda = 5.309,01 / 0,67 ≈ R$ 7.924,93 (com qtd=1).
            cards_after = page.locator('.row.g-3.mb-3 h5').all_inner_texts()
            log.info(f'[editar] cards após qtd=1: {cards_after}')
            cards_blob_after = ' | '.join(cards_after)
            for c in cards_after[:3]:  # custo, venda, lucro (4o é margem%)
                _ok(c.strip().startswith('R$'),
                    f'editar: card recalc começa com R$ ("{c}")')
                _ok(not PADRAO_US_2D.search(c),
                    f'editar: card recalc sem US ("{c}")')

            # 4i. Body inteiro sem formato US.
            body_text = page.locator('body').inner_text()
            ofensores = _scan_us(body_text)
            _ok(not ofensores,
                f'editar: body sem formato US (ofensores={ofensores})')

            browser.close()
    finally:
        cleanup(ctx)

    log.info('=' * 70)
    log.info(f'PASSED: {len(passed)}  FAILED: {len(failed)}')
    for f in failed:
        log.error(f' ✗ {f}')
    log.info('=' * 70)
    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
