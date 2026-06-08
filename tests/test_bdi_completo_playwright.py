"""Bloco 3 — Playwright e2e do BDI completo (padrão TCU) no browser real.

Cobre, no DOM, as superfícies internas introduzidas pelo Bloco 3:

  1. Configurações » Empresa — os 7 campos de BDI renderizam com os valores
     salvos; editar + salvar persiste (read + write path pela UI).
  2. Composição do serviço — o card "Composição do preço (BDI)" exibe o split
     Custo direto + Indiretos (5 componentes) + Tributos + Lucro = Preço, com
     os números corretos (custo 1000, ΣBDI 25%, T+L 20% → preço 1.562,50).
  3. Guarda-corpo (D3) — faixas ok / aviso / bloqueio refletidas no badge e na
     mensagem, conforme T+L do serviço (20% ok, 65% aviso, 95% bloqueio→preço 0).
  4. Proposta — a seção opcional "BDI desta proposta" (override) existe no form.

Pré-requisito: servidor Flask em http://localhost:5000 (workflow "Start
application"). Uso direto:

    python tests/test_bdi_completo_playwright.py
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app import app, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402
from models import (  # noqa: E402
    ComposicaoServico, ConfiguracaoEmpresa, Insumo, PrecoBaseInsumo,
    Servico, TipoUsuario, Usuario,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'


def _suf() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def seed_dados():
    """Admin + ConfiguracaoEmpresa (BDI 25%) + serviço com custo 1000."""
    suf = _suf()
    email = f'bdipw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f'bdipw_{suf}', email=email, nome='BDI PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id

        cfg = ConfiguracaoEmpresa(
            admin_id=admin_id, nome_empresa=f'__BDI PW {suf}',
            # campos numéricos que o handler de salvar faz int()/float() —
            # sem eles o template renderiza vazio e o save inteiro dá rollback.
            prazo_entrega_padrao=90, validade_padrao=7,
            percentual_nota_fiscal_padrao=Decimal('13.5'),
            imposto_pct_padrao=Decimal('8'), lucro_pct_padrao=Decimal('10'),
            bdi_ac_pct=Decimal('20'), bdi_seguro_pct=Decimal('1'),
            bdi_risco_pct=Decimal('1'), bdi_garantia_pct=Decimal('1'),
            bdi_desp_financeiras_pct=Decimal('2'),
            bdi_tl_aviso_pct=Decimal('60'), bdi_tl_bloqueio_pct=Decimal('90'),
        )
        db.session.add(cfg)

        ins = Insumo(admin_id=admin_id, nome=f'__bdi_ins_{suf}',
                     tipo='MATERIAL', unidade='un')
        db.session.add(ins)
        db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=admin_id, insumo_id=ins.id, valor=Decimal('500.0000'),
            vigencia_inicio=date(2020, 1, 1)))
        svc = Servico(
            admin_id=admin_id, nome=f'__bdi_svc_{suf}', categoria='Teste BDI',
            unidade_medida='un', imposto_pct=Decimal('15'),
            margem_lucro_pct=Decimal('5'),  # T+L = 20% (faixa ok)
        )
        db.session.add(svc)
        db.session.flush()
        db.session.add(ComposicaoServico(
            admin_id=admin_id, servico_id=svc.id, insumo_id=ins.id,
            coeficiente=Decimal('2.0')))  # custo = 2 × 500 = 1000
        db.session.commit()
        return {'email': email, 'admin_id': admin_id, 'cfg_id': cfg.id,
                'svc_id': svc.id, 'ins_id': ins.id}


def _set_tl(svc_id, imposto, margem):
    """Ajusta T/L do serviço entre cenários do guarda-corpo."""
    with app.app_context():
        svc = db.session.get(Servico, svc_id)
        svc.imposto_pct = Decimal(str(imposto))
        svc.margem_lucro_pct = Decimal(str(margem))
        db.session.commit()


def cleanup(ctx):
    if not ctx:
        return
    with app.app_context():
        try:
            ComposicaoServico.query.filter_by(servico_id=ctx['svc_id']).delete()
            PrecoBaseInsumo.query.filter_by(insumo_id=ctx['ins_id']).delete()
            for model, key in ((Servico, 'svc_id'), (Insumo, 'ins_id'),
                               (ConfiguracaoEmpresa, 'cfg_id'), (Usuario, 'admin_id')):
                obj = db.session.get(model, ctx[key])
                if obj:
                    db.session.delete(obj)
            db.session.commit()
        except Exception as e:  # pragma: no cover
            log.warning(f'Cleanup falhou: {e}')
            db.session.rollback()


def main():
    ctx = seed_dados()
    log.info(f'Seed: admin={ctx["admin_id"]} svc={ctx["svc_id"]}')
    passed: list[str] = []
    failed: list[str] = []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    comp_url = f'{BASE_URL}/catalogo/servicos/{ctx["svc_id"]}/composicao'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()

            # ---- Login --------------------------------------------------
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, f'login redirecionou (url={page.url})')

            # ---- 1. Form da empresa: campos de BDI (read path) ----------
            page.goto(f'{BASE_URL}/configuracoes/empresa', wait_until='networkidle')
            for campo, esperado in (
                ('bdi_ac_pct', 20), ('bdi_seguro_pct', 1), ('bdi_risco_pct', 1),
                ('bdi_garantia_pct', 1), ('bdi_desp_financeiras_pct', 2),
                ('bdi_tl_aviso_pct', 60), ('bdi_tl_bloqueio_pct', 90),
            ):
                loc = page.locator(f'input[name="{campo}"]')
                val = loc.input_value() if loc.count() else None
                _ok(loc.count() == 1 and abs(float(val) - esperado) < 0.01,
                    f'empresa: {campo} = {esperado} (got {val})')

            # ---- 2. Form da empresa: editar + salvar (write path) -------
            page.fill('input[name="bdi_risco_pct"]', '7')
            # form.submit() ignora a validação HTML5 de campos `required` não
            # relacionados (o handler já foi validado isolado); posta o form real.
            page.eval_on_selector('form[action*="empresa/salvar"]', 'f => f.submit()')
            page.wait_for_load_state('networkidle')
            page.goto(f'{BASE_URL}/configuracoes/empresa', wait_until='networkidle')
            val_risco = page.locator('input[name="bdi_risco_pct"]').input_value()
            _ok(abs(float(val_risco) - 7) < 0.01,
                f'empresa: bdi_risco_pct persistiu = 7 (got {val_risco})')
            # restaura para 1 antes do split (mantém ΣBDI = 25)
            with app.app_context():
                c = db.session.get(ConfiguracaoEmpresa, ctx['cfg_id'])
                c.bdi_risco_pct = Decimal('1')
                db.session.commit()

            # ---- 3. Composição: split do preço (faixa ok) --------------
            page.goto(comp_url, wait_until='networkidle')
            body = page.locator('body').inner_text()
            _ok('Composição do preço (BDI)' in body, 'split: card BDI presente')
            for rotulo in ('Custo direto', 'Indiretos', 'Tributos', 'Lucro', 'Preço'):
                _ok(rotulo in body, f'split: linha "{rotulo}" presente')
            _ok('1.562,50' in body, 'split: preço = R$ 1.562,50 (custo 1000, ΣBDI 25%, T+L 20%)')
            _ok('250,00' in body, 'split: indiretos = R$ 250,00 (BDI aplicado)')
            _ok(page.locator('.badge', has_text='aviso').count() == 0
                and page.locator('.badge', has_text='bloqueio').count() == 0,
                'split: faixa ok sem badge de aviso/bloqueio')

            # ---- 4. Guarda-corpo: faixa de aviso (T+L = 65) ------------
            _set_tl(ctx['svc_id'], 40, 25)
            page.goto(comp_url, wait_until='networkidle')
            _ok(page.locator('.badge', has_text='aviso').count() >= 1,
                'guarda-corpo: badge "aviso" em T+L = 65%')

            # ---- 5. Guarda-corpo: bloqueio (T+L = 95) ------------------
            _set_tl(ctx['svc_id'], 50, 45)
            page.goto(comp_url, wait_until='networkidle')
            _ok(page.locator('.badge', has_text='bloqueio').count() >= 1,
                'guarda-corpo: badge "bloqueio" em T+L = 95%')
            body_bloq = page.locator('body').inner_text()
            _ok('ajuste os percentuais' in body_bloq,
                'guarda-corpo: mensagem de bloqueio exibida')
            # restaura faixa ok
            _set_tl(ctx['svc_id'], 15, 5)

            # ---- 6. Proposta: seção de override de BDI ------------------
            page.goto(f'{BASE_URL}/propostas/nova', wait_until='networkidle')
            body_prop = page.locator('body').inner_text()
            _ok('BDI desta proposta' in body_prop,
                'proposta: seção "BDI desta proposta" presente')
            _ok(page.locator('input[name="bdi_ac_pct"]').count() >= 1,
                'proposta: input bdi_ac_pct (override) presente')

            browser.close()
    finally:
        cleanup(ctx)

    log.info('=' * 70)
    log.info(f'PASSED: {len(passed)}  FAILED: {len(failed)}')
    for f in failed:
        log.error(f'  ✗ {f}')
    log.info('=' * 70)
    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
