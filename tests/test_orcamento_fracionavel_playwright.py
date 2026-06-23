"""
Task #75 — Playwright e2e: fracionavel=False força arredondamento para cima mesmo quando fator=1.

Três cenários:

  A) Insumo NÃO fracionável (peça), fator=1, qtd_tec=0,57
     → compra 1 peça, custo = 1 × preço (NÃO 0,57 × preço)

  B) Insumo fracionável (kg), fator=1, qtd_tec=0,57
     → compra 0,57 kg, custo = 0,57 × preço (sem arredondamento)

  C) Insumo NÃO fracionável (un), fator=1, qtd_tec=1,25
     → compra 2 un, custo = 2 × preço (ceil de 1,25)

Esses cenários cobrem o bug da planilha:
  Perfil F530: qtd_tec=0,57 peça → deveria comprar 1 peça, não 0,5667 peça.

Pré-requisito: servidor Flask rodando em http://localhost:5000.

Uso:
    python tests/test_orcamento_fracionavel_playwright.py
"""
from __future__ import annotations

import logging
import math
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

PRECO_PECA = 11.35   # R$ 11,35/peça (Perfil F530)
PRECO_KG   = 5.00    # R$ 5,00/kg
PRECO_UN   = 8.00    # R$ 8,00/un

QTD_SERVICO = 1.0    # 1 m² de serviço

# coeficientes para ter qtd_tec quebrada
COEF_PECA  = 0.57    # 0,57 peças/m²  → ceil → 1 peça
COEF_KG    = 0.57    # 0,57 kg/m²     → mantém 0,57 kg
COEF_UN    = 1.25    # 1,25 un/m²     → ceil → 2 un


def _suf() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def seed_dados() -> dict:
    suf = _suf()
    email = f't75pw_{suf}@test.local'

    with app.app_context():
        admin = Usuario(
            username=f't75pw_{suf}',
            email=email,
            nome='T75 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id

        # Cenário A: peça não fracionável
        ins_peca = Insumo(admin_id=admin_id, nome=f'__t75_peca_{suf}',
                          tipo='MATERIAL', unidade='pç',
                          fracionavel=False)
        # Cenário B: kg fracionável
        ins_kg = Insumo(admin_id=admin_id, nome=f'__t75_kg_{suf}',
                        tipo='MATERIAL', unidade='kg',
                        fracionavel=True)
        # Cenário C: unidade não fracionável
        ins_un = Insumo(admin_id=admin_id, nome=f'__t75_un_{suf}',
                        tipo='MATERIAL', unidade='un',
                        fracionavel=False)
        db.session.add_all([ins_peca, ins_kg, ins_un])
        db.session.flush()
        db.session.add_all([
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_peca.id,
                            valor=Decimal(str(PRECO_PECA)),
                            vigencia_inicio=date(2020, 1, 1)),
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_kg.id,
                            valor=Decimal(str(PRECO_KG)),
                            vigencia_inicio=date(2020, 1, 1)),
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_un.id,
                            valor=Decimal(str(PRECO_UN)),
                            vigencia_inicio=date(2020, 1, 1)),
        ])

        svc = Servico(admin_id=admin_id, nome=f'__t75_svc_{suf}',
                      categoria='Teste T75', unidade_medida='m2',
                      imposto_pct=Decimal('0'), margem_lucro_pct=Decimal('0'))
        db.session.add(svc)
        db.session.flush()
        db.session.add_all([
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_peca.id,
                              coeficiente=Decimal(str(COEF_PECA))),
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_kg.id,
                              coeficiente=Decimal(str(COEF_KG))),
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_un.id,
                              coeficiente=Decimal(str(COEF_UN))),
        ])
        db.session.commit()

        svc = db.session.get(Servico, svc.id)
        from services.orcamento_view_service import snapshot_from_servico, recalcular_item

        orc = Orcamento(admin_id=admin_id, numero=f'T75-{suf}',
                        titulo=f'Teste Task #75 fracionavel')
        db.session.add(orc)
        db.session.flush()

        item = OrcamentoItem(
            admin_id=admin_id, orcamento_id=orc.id, ordem=1,
            servico_id=svc.id, descricao=svc.nome, unidade='m2',
            quantidade=Decimal(str(QTD_SERVICO)),
            composicao_snapshot=snapshot_from_servico(svc),
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
            'ins_peca_id': ins_peca.id,
            'ins_kg_id': ins_kg.id,
            'ins_un_id': ins_un.id,
            'svc_id': svc.id,
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
            for k in ('ins_peca_id', 'ins_kg_id', 'ins_un_id'):
                PrecoBaseInsumo.query.filter_by(insumo_id=ctx[k]).delete()
                ins = db.session.get(Insumo, ctx[k])
                if ins:
                    db.session.delete(ins)
            adm = db.session.get(Usuario, ctx['admin_id'])
            if adm:
                db.session.delete(adm)
            db.session.commit()
        except Exception as exc:
            log.warning(f'Cleanup falhou: {exc}')
            db.session.rollback()


def _fmtBR(n: float, decimals: int = 2) -> str:
    """Formata número em pt-BR para comparação (ex: 11,35)."""
    s = f'{n:.{decimals}f}'.replace('.', ',')
    return s


def main() -> None:
    ctx = None
    try:
        ctx = seed_dados()
    except Exception as exc:
        log.error(f'Seed falhou: {exc}')
        sys.exit(1)

    log.info(f'Dados: orc_id={ctx["orc_id"]}')
    passed: list[str] = []
    failed: list[str] = []

    def _ok(cond: bool, label: str) -> None:
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    # Valores esperados
    qtd_tec_peca = COEF_PECA * QTD_SERVICO                      # 0,57
    qtd_com_peca = math.ceil(qtd_tec_peca)                       # 1
    custo_peca   = qtd_com_peca * PRECO_PECA                      # 11,35

    qtd_tec_kg   = COEF_KG * QTD_SERVICO                        # 0,57
    qtd_com_kg   = qtd_tec_kg                                     # 0,57 (fracionável)
    custo_kg     = round(qtd_com_kg * PRECO_KG, 2)               # 2,85

    qtd_tec_un   = COEF_UN * QTD_SERVICO                        # 1,25
    qtd_com_un   = math.ceil(qtd_tec_un)                          # 2
    custo_un     = qtd_com_un * PRECO_UN                          # 16,00

    custo_total  = round(custo_peca + custo_kg + custo_un, 2)    # 30,20

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            bctx = browser.new_context(viewport={'width': 1280, 'height': 900})
            page = bctx.new_page()

            # --- Login ---
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, f'login OK — url={page.url}')

            # --- Abre orçamento ---
            url = f'{BASE_URL}/orcamentos/{ctx["orc_id"]}/editar'
            page.goto(url, wait_until='networkidle')
            _ok(page.locator('.comp-tbody').count() >= 1, 'tabela renderizada')

            sub_tots = page.locator('.js-subtotal-tot').all()
            qtd_coms = page.locator('.js-qtd-comercial').all()
            _ok(len(sub_tots) >= 3, f'3 linhas de subtotal ({len(sub_tots)} encontradas)')

            # Os índices 0,1,2 correspondem à ordem de inserção dos insumos.
            # Ordem: peca(0), kg(1), un(2) — mesma ordem do ComposicaoServico.

            # --- Cenário A: peça não fracionável ---
            sub_peca = sub_tots[0].inner_text().strip() if len(sub_tots) > 0 else ''
            qtd_peca = qtd_coms[0].inner_text().strip() if len(qtd_coms) > 0 else ''
            peca_str = _fmtBR(custo_peca)  # "11,35"
            _ok(
                peca_str in sub_peca,
                f'[A peça] subtotal_compra = R${peca_str}  —  got "{sub_peca}"',
            )
            _ok(
                '1,' in qtd_peca or qtd_peca.startswith('1'),
                f'[A peça] qtd_compra = 1 (ceil de 0,57)  —  got "{qtd_peca}"',
            )
            # Valor errado = 0,57 × 11,35 = 6,47
            _ok(
                '6,47' not in sub_peca and '6,43' not in sub_peca,
                f'[A peça] NÃO usa qty fracionada  —  got "{sub_peca}"',
            )

            # --- Cenário B: kg fracionável ---
            sub_kg = sub_tots[1].inner_text().strip() if len(sub_tots) > 1 else ''
            qtd_kg_txt = qtd_coms[1].inner_text().strip() if len(qtd_coms) > 1 else ''
            kg_str = _fmtBR(custo_kg)  # "2,85"
            _ok(
                kg_str in sub_kg,
                f'[B kg] subtotal_compra = R${kg_str}  —  got "{sub_kg}"',
            )
            _ok(
                '0,57' in qtd_kg_txt or '0,5700' in qtd_kg_txt,
                f'[B kg] qtd_compra = 0,57 (fracionável)  —  got "{qtd_kg_txt}"',
            )

            # --- Cenário C: unidade não fracionável ---
            sub_un = sub_tots[2].inner_text().strip() if len(sub_tots) > 2 else ''
            qtd_un_txt = qtd_coms[2].inner_text().strip() if len(qtd_coms) > 2 else ''
            un_str = _fmtBR(custo_un)  # "16,00"
            _ok(
                un_str in sub_un,
                f'[C un] subtotal_compra = R${un_str}  —  got "{sub_un}"',
            )
            _ok(
                '2,' in qtd_un_txt or qtd_un_txt.startswith('2'),
                f'[C un] qtd_compra = 2 (ceil de 1,25)  —  got "{qtd_un_txt}"',
            )

            # --- Custo total ---
            custo_span = page.locator('.js-custo').first.inner_text().strip()
            custo_str = _fmtBR(custo_total)  # "30,20"
            _ok(
                custo_str in custo_span,
                f'custo_total = R${custo_str}  —  got "{custo_span}"',
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


import pytest

pytestmark = pytest.mark.browser


def test_orcamento_fracionavel_e2e():
    """Entrypoint pytest (browser): fracionavel=False força ceil (Task #75) no
    DOM. Requer servidor. Cobertura preservada."""
    try:
        main()
    except SystemExit as e:
        assert e.code in (0, None), f"E2E fracionável falhou (exit code={e.code})"


if __name__ == '__main__':
    main()
