"""
Task #181 — Playwright e2e: composição de serviço exibe valores em formato BR
(R$ 1.234,56 / 1.234,5678) e nenhum valor em formato americano.

Cobre o "Done looks like" da task no DOM real (browser):
  - Cards "Custo Unitário" e "Preço de Venda" exibem `R$ N.NNN,NN`.
  - Coluna "Custo / un" e linha de total seguem o mesmo padrão.
  - Coluna "Preço (R$)" usa formato BR de 4 casas.
  - Nenhum texto visível na página termina em "ponto + 2 dígitos" (formato US,
    ex.: 5309.02). Inputs HTML5 numéricos são ignorados (pois eles exigem ".").

Pré-requisito: o servidor Flask precisa estar rodando em http://localhost:5000
(workflow "Start application").

Uso direto:
    python tests/test_composicao_formato_br_playwright.py
"""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app import app, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402
from models import (  # noqa: E402
    ComposicaoServico,
    Insumo,
    PrecoBaseInsumo,
    Servico,
    TipoUsuario,
    Usuario,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'

# Padrão "número com vírgula como separador decimal" (formato BR).
PADRAO_BRL = re.compile(r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}')
PADRAO_NUM_BR = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2,4}')
# Formato americano: "ponto + exatamente 2 dígitos no fim de uma palavra".
# Ex.: 5309.02, 1234.56. Cobre o caso do bug original.
PADRAO_US_2D = re.compile(r'\d+\.\d{2}\b')


def _suf() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def seed_dados():
    """Cria admin + 2 insumos com preço + serviço com 2 linhas de composição."""
    suf = _suf()
    email = f't181pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f't181pw_{suf}',
            email=email,
            nome='T181 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id

        ins_a = Insumo(admin_id=admin_id, nome=f'__t181_aco_{suf}',
                       tipo='MATERIAL', unidade='kg')
        ins_b = Insumo(admin_id=admin_id, nome=f'__t181_mo_{suf}',
                       tipo='MAO_OBRA', unidade='h')
        db.session.add_all([ins_a, ins_b])
        db.session.flush()
        # preços que produzem valores grandes (>= R$ 1.000) para exercitar
        # o separador de milhar.
        db.session.add_all([
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_a.id,
                            valor=Decimal('35.0000'),
                            vigencia_inicio=date(2020, 1, 1)),
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_b.id,
                            valor=Decimal('170.0000'),
                            vigencia_inicio=date(2020, 1, 1)),
        ])
        svc = Servico(
            admin_id=admin_id,
            nome=f'__t181_svc_{suf}',
            categoria='Teste',
            unidade_medida='un',
            imposto_pct=Decimal('13.00'),
            margem_lucro_pct=Decimal('20.00'),
        )
        db.session.add(svc)
        db.session.flush()
        # 150 kg × 35 + 0,3471... — o ponto chave é gerar custo > 1000
        db.session.add_all([
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_a.id,
                              coeficiente=Decimal('150.0000')),
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_b.id,
                              coeficiente=Decimal('0.3471')),
        ])
        db.session.commit()
        return {
            'email': email,
            'admin_id': admin_id,
            'svc_id': svc.id,
            'ins_a_id': ins_a.id,
            'ins_b_id': ins_b.id,
        }


def cleanup(ctx):
    if not ctx:
        return
    with app.app_context():
        try:
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
            adm = db.session.get(Usuario, ctx['admin_id'])
            if adm:
                db.session.delete(adm)
            db.session.commit()
        except Exception as e:  # pragma: no cover
            log.warning(f'Cleanup falhou: {e}')
            db.session.rollback()


def main():
    ctx = seed_dados()
    log.info(f'Dados semeados: svc={ctx["svc_id"]}')
    failed: list[str] = []
    passed: list[str] = []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 900})
            page = context.new_page()

            # 1. Login
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url,
                f'login redirecionou (url={page.url})')

            # 2. Composição do serviço
            url = f'{BASE_URL}/catalogo/servicos/{ctx["svc_id"]}/composicao'
            page.goto(url, wait_until='networkidle')
            _ok(page.locator('table').count() >= 1,
                'página de composição renderizada')

            # 3. Cards "CUSTO UNITÁRIO" e "PREÇO DE VENDA" devem
            #    estar em formato BR (R$ N.NNN,NN).
            custo_card_text = page.locator('h3').nth(0).inner_text().strip()
            preco_card_text = page.locator('h3').nth(1).inner_text().strip()
            _ok(bool(PADRAO_BRL.search(custo_card_text)),
                f'card CUSTO UNITÁRIO em formato BR (got "{custo_card_text}")')
            _ok(bool(PADRAO_BRL.search(preco_card_text)),
                f'card PREÇO DE VENDA em formato BR (got "{preco_card_text}")')

            # Nenhum dos cards pode terminar em ".NN" (formato americano).
            _ok(not PADRAO_US_2D.search(custo_card_text),
                f'card CUSTO sem formato US (got "{custo_card_text}")')
            _ok(not PADRAO_US_2D.search(preco_card_text),
                f'card PREÇO sem formato US (got "{preco_card_text}")')

            # 4. Linha de total (tfoot) também em formato BR.
            tfoot_text = page.locator('tfoot').inner_text().strip()
            _ok(bool(PADRAO_BRL.search(tfoot_text)),
                f'tfoot total em formato BR (got "{tfoot_text}")')
            _ok(not PADRAO_US_2D.search(tfoot_text),
                f'tfoot sem formato US (got "{tfoot_text}")')

            # 5. Conteúdo das células (tbody td) — colunas Preço/Custo.
            #    Inspecionar todas as células de texto (excluindo <input>).
            # Filtra apenas células cujo texto é "puramente numérico" no
            # sentido visual (dígitos, ponto, vírgula, R$ e espaço). Assim
            # evitamos comparar com nomes que tenham dígitos no sufixo.
            celulas = page.evaluate(
                """() => Array.from(document.querySelectorAll('tbody td'))
                    .filter(td => !td.querySelector('input'))
                    .map(td => td.innerText.trim())
                    .filter(t => /^[R\\$\\s\\d.,]+$/.test(t) && /\\d/.test(t))
                """
            )
            log.info(f'Células numéricas: {celulas}')
            _ok(len(celulas) > 0, 'células numéricas existem na composição')

            for txt in celulas:
                _ok(not PADRAO_US_2D.search(txt),
                    f'célula sem formato US ".NN" (got "{txt}")')
                # Toda célula numérica deve ter vírgula como separador decimal
                # (BR). Pode ser "35,0000", "170,0000", "5.250,00", "59,02", etc.
                _ok(',' in txt,
                    f'célula contém vírgula decimal (got "{txt}")')

            # 6. Smoke check: também verifica o texto inteiro do <body> não
            #    contém o padrão americano "número.NN " (espaço/limite),
            #    excluindo conteúdo de inputs (que ficam fora do innerText
            #    para a maioria dos browsers).
            body_text = page.locator('body').inner_text()
            ofensores = PADRAO_US_2D.findall(body_text)
            # Filtro: inputs HTML5 number rendem dentro de body em alguns
            # casos; ignoramos strings que coincidem com algum value de input
            # de coeficiente (que precisam ser ".NNNN" → não casa com .NN, ok).
            _ok(not ofensores,
                f'body sem nenhum valor em formato americano '
                f'(ofensores={ofensores[:5]})')

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
