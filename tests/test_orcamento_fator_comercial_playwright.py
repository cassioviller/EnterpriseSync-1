"""
Task #74 — Playwright e2e: fator_comercial > 1 separa custo técnico × custo real de compra.

Valida no browser (DOM real pós-JS) que, com fator=100, preco=R$50, coef=8, qty=1:

  CUSTO / UN. SERVIÇO (.js-subtotal-unit) = R$ 4,0000
      = coef × (preco_emb / fator) = 8 × (50/100) = 4,00
      Bug anterior: R$ 400,0000  (coef × preco_emb, inflado 100×)

  SUBTOTAL COMPRA (.js-subtotal-tot) = R$ 50,00
      = nº_pacotes × preco_emb = 1 × 50 = R$ 50,00
      Bug anterior: R$ 4,00  (custo_unit × qty = técnico × qtd)

  CUSTO TOTAL DO ITEM (.js-custo) = R$ 50,00
      = custo real de compra (custo_compra), não custo_tec × qty

Pré-requisito: servidor Flask rodando em http://localhost:5000.

Uso:
    python tests/test_orcamento_fator_comercial_playwright.py
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from app import app, db
from werkzeug.security import generate_password_hash
from models import (
    ComposicaoServico,
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

# Parâmetros do cenário (exemplo canônico do commit Task #74)
FATOR = 100           # fator_comercial — 100 parafusos por caixa
PRECO_EMB = 50.00     # preço da embalagem/caixa (R$)
COEF = 8.0            # coeficiente: 8 parafusos por m²
QTD = 1.0             # 1 m² de serviço no orçamento

# Valores esperados após o fix
CUSTO_TEC_UNITARIO = round(COEF * PRECO_EMB / FATOR, 4)  # 4.0000
CUSTO_COMPRA_TOTAL = PRECO_EMB                             # 50.00 (1 caixa)


def _suf() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def seed_dados() -> dict:
    """Cria admin + insumo (fator=100) + serviço + orçamento com 1 item (qty=1)."""
    suf = _suf()
    email = f't74pw_{suf}@test.local'

    with app.app_context():
        # --- usuário admin isolado para o teste ---
        admin = Usuario(
            username=f't74pw_{suf}',
            email=email,
            nome='T74 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id

        # --- insumo com fator_comercial=100 (ex: caixa de 100 parafusos) ---
        ins = Insumo(
            admin_id=admin_id,
            nome=f'__t74_parafuso_{suf}',
            tipo='MATERIAL',
            unidade='un',
            fator_comercial=Decimal(str(FATOR)),
            unidade_comercial='cx',
        )
        db.session.add(ins)
        db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=admin_id,
            insumo_id=ins.id,
            valor=Decimal(str(PRECO_EMB)),
            vigencia_inicio=date(2020, 1, 1),
        ))

        # --- serviço com composição: 8 parafusos/m² ---
        svc = Servico(
            admin_id=admin_id,
            nome=f'__t74_svc_{suf}',
            categoria='Teste T74',
            unidade_medida='m2',
            imposto_pct=Decimal('10'),
            margem_lucro_pct=Decimal('20'),
        )
        db.session.add(svc)
        db.session.flush()
        db.session.add(ComposicaoServico(
            admin_id=admin_id,
            servico_id=svc.id,
            insumo_id=ins.id,
            coeficiente=Decimal(str(COEF)),
        ))

        # commit parcial para que snapshot_from_servico enxergue relações e preço
        db.session.commit()
        svc_id = svc.id
        ins_id = ins.id

        # --- recarrega svc para lazy-load de composicoes + insumo funcionar ---
        svc = db.session.get(Servico, svc_id)

        from services.orcamento_view_service import snapshot_from_servico, recalcular_item

        snap = snapshot_from_servico(svc)

        orc = Orcamento(
            admin_id=admin_id,
            numero=f'T74-{suf}',
            titulo=f'Teste Task #74 fator={FATOR}',
        )
        db.session.add(orc)
        db.session.flush()

        item = OrcamentoItem(
            admin_id=admin_id,
            orcamento_id=orc.id,
            ordem=1,
            servico_id=svc_id,
            descricao=svc.nome,
            unidade='m2',
            quantidade=Decimal(str(QTD)),
            composicao_snapshot=snap,
        )
        db.session.add(item)
        db.session.flush()

        recalcular_item(item, orc)
        db.session.commit()

        return {
            'email': email,
            'admin_id': admin_id,
            'orc_id': orc.id,
            'item_id': item.id,
            'ins_id': ins_id,
            'svc_id': svc_id,
        }


def cleanup(ctx: dict | None) -> None:
    if not ctx:
        return
    with app.app_context():
        try:
            OrcamentoItem.query.filter_by(orcamento_id=ctx['orc_id']).delete()
            Orcamento.query.filter_by(id=ctx['orc_id']).delete()
            ComposicaoServico.query.filter_by(servico_id=ctx['svc_id']).delete()
            svc = db.session.get(Servico, ctx['svc_id'])
            if svc:
                db.session.delete(svc)
            PrecoBaseInsumo.query.filter_by(insumo_id=ctx['ins_id']).delete()
            ins = db.session.get(Insumo, ctx['ins_id'])
            if ins:
                db.session.delete(ins)
            adm = db.session.get(Usuario, ctx['admin_id'])
            if adm:
                db.session.delete(adm)
            db.session.commit()
        except Exception as exc:
            log.warning(f'Cleanup falhou: {exc}')
            db.session.rollback()


def main() -> None:
    ctx = None
    try:
        ctx = seed_dados()
    except Exception as exc:
        log.error(f'Seed falhou: {exc}')
        sys.exit(1)

    log.info(f'Dados: orc_id={ctx["orc_id"]}  item_id={ctx["item_id"]}')
    log.info(f'Cenário: fator={FATOR}  preco=R${PRECO_EMB}  coef={COEF}  qty={QTD}')
    log.info(f'Esperado: custo_tec_unit=R${CUSTO_TEC_UNITARIO}  custo_compra=R${CUSTO_COMPRA_TOTAL}')

    passed: list[str] = []
    failed: list[str] = []

    def _ok(cond: bool, label: str) -> None:
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            bctx = browser.new_context(viewport={'width': 1280, 'height': 900})
            page = bctx.new_page()

            # --- 1. Login ---
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, f'login OK — url={page.url}')

            # --- 2. Abre orçamento para edição ---
            url = f'{BASE_URL}/orcamentos/{ctx["orc_id"]}/editar'
            page.goto(url, wait_until='networkidle')
            _ok(
                page.locator('.comp-tbody').count() >= 1,
                'tabela de composição renderizada',
            )

            # --- 3. "Custo / un. serviço" = R$ 4,0000 ---
            # JS calcula: sub = coef × preco_emb / fator = 8 × 50 / 100 = 4,0000
            # Bug anterior: sub = coef × preco_emb = 8 × 50 = 400,0000
            sub_unit_txt = page.locator('.js-subtotal-unit').first.inner_text().strip()
            _ok(
                '4,0000' in sub_unit_txt,
                f'custo_tec/un correto = R$ 4,0000  —  got "{sub_unit_txt}"',
            )
            _ok(
                '400' not in sub_unit_txt,
                f'custo_tec/un NÃO inflado (sem "400")  —  got "{sub_unit_txt}"',
            )

            # --- 4. "Qtd. Compra" = 100,0000 cx (ceil(8/100)×100 = 100) ---
            qtd_com_txt = page.locator('.js-qtd-comercial').first.inner_text().strip()
            _ok(
                '100' in qtd_com_txt,
                f'qtd_comercial = 100 (1 caixa de 100)  —  got "{qtd_com_txt}"',
            )

            # --- 5. "Subtotal compra" = R$ 50,00 (1 pacote × R$50) ---
            # Bug anterior: subTot = custo_unit × qty = 4,00 × 1 = R$ 4,00
            sub_tot_txt = page.locator('.js-subtotal-tot').first.inner_text().strip()
            _ok(
                '50,00' in sub_tot_txt,
                f'subtotal_compra = R$ 50,00  —  got "{sub_tot_txt}"',
            )
            _ok(
                sub_tot_txt.replace('\xa0', ' ') not in ('R$ 4,00', 'R$ 4,0000'),
                f'subtotal_compra NÃO é R$ 4,00  —  got "{sub_tot_txt}"',
            )

            # --- 6. Custo total do item (.js-custo) = R$ 50,00 ---
            custo_txt = page.locator('.js-custo').first.inner_text().strip()
            _ok(
                '50,00' in custo_txt,
                f'custo_total = R$ 50,00  —  got "{custo_txt}"',
            )

            # --- 7. Smoke: nenhum valor "R$ 400" visível na página ---
            body_txt = page.locator('body').inner_text()
            _ok(
                'R$ 400' not in body_txt and '400,0000' not in body_txt,
                'body não contém valor inflado "R$ 400" / "400,0000"',
            )

            browser.close()

    finally:
        cleanup(ctx)

    log.info('=' * 70)
    log.info(f'PASSED: {len(passed)}   FAILED: {len(failed)}')
    for f in failed:
        log.error(f'  ✗ {f}')
    log.info('=' * 70)
    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
