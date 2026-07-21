"""M07 — Playwright e2e: fluxo completo dos DOIS modos de apontamento no
Novo RDO (spec §17).

P1. Tarefa quantitativa mostra campo de quantidade (e NÃO o de %).
P2. Tarefa sem quantitativo mostra campo de % ACUMULADO (e NÃO o de qty).
P3. Marco mostra toggle binário "Marco concluído".
P4. Preview ao vivo: qty → "X% acumulado"; % → "incremento +Y pp".
P5. Filtro por nome esconde as tarefas que não casam.
P6. Salvar grava os dois modos com a semântica M02 (quantitativo com
    snapshot; percentual com quantidade 0.0) + marco 100.

Pré-requisito: servidor Flask em http://localhost:5000.
Uso direto:  python tests/test_rdo_dois_modos_playwright.py
"""
import logging
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from app import app, db
from werkzeug.security import generate_password_hash
from models import (
    Cliente,
    Obra,
    RDO,
    RDOApontamentoCronograma,
    TarefaCronograma,
    TipoUsuario,
    Usuario,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'


def seed_dados():
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    email = f'm07pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f'm07pw_{suf}', email=email, nome='M07 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(admin_id=admin.id, nome=f'Cli M07 {suf}',
                      email=f'cli07_{suf[:6]}@test.local', telefone='119')
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra M07 {suf}', codigo=f'M07-{suf[:6]}',
            admin_id=admin.id, status='Em andamento',
            data_inicio=date.today() - timedelta(days=30), cliente_id=cli.id,
        )
        db.session.add(obra); db.session.flush()

        base = dict(admin_id=admin.id, obra_id=obra.id, responsavel='empresa',
                    is_cliente=False,
                    data_inicio=date.today() - timedelta(days=10),
                    data_fim=date.today() + timedelta(days=10))
        t_q = TarefaCronograma(nome_tarefa=f'Alvenaria Quant {suf[:6]}',
                               ordem=1, duracao_dias=10,
                               quantidade_total=100.0, unidade_medida='m2',
                               **base)
        t_p = TarefaCronograma(nome_tarefa=f'Projeto Percentual {suf[:6]}',
                               ordem=2, duracao_dias=10, **base)
        t_m = TarefaCronograma(nome_tarefa=f'Marco Entrega {suf[:6]}',
                               ordem=3, duracao_dias=0, is_marco=True,
                               **{**base,
                                  'data_fim': date.today() - timedelta(days=10)})
        db.session.add_all([t_q, t_p, t_m])
        db.session.commit()
        return dict(email=email, admin_id=admin.id, obra_id=obra.id,
                    cli_id=cli.id, tq=t_q.id, tp=t_p.id, tm=t_m.id,
                    nome_tp=t_p.nome_tarefa)


def cleanup(ctx):
    with app.app_context():
        rdos = RDO.query.filter_by(obra_id=ctx['obra_id']).all()
        for r in rdos:
            RDOApontamentoCronograma.query.filter_by(rdo_id=r.id).delete()
            db.session.delete(r)
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        Obra.query.filter_by(id=ctx['obra_id']).delete()
        Cliente.query.filter_by(id=ctx['cli_id']).delete()
        Usuario.query.filter_by(id=ctx['admin_id']).delete()
        db.session.commit()


def main():
    ctx = seed_dados()
    log.info(f'Seed: obra={ctx["obra_id"]} tq={ctx["tq"]} tp={ctx["tp"]} '
             f'tm={ctx["tm"]}')
    failed, passed = [], []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            page = browser.new_context(
                viewport={'width': 1280, 'height': 900}).new_page()

            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, 'login redirecionou')

            page.goto(f'{BASE_URL}/rdo/novo', wait_until='networkidle')
            page.select_option('#obra_id', str(ctx['obra_id']))
            page.wait_for_selector(f'#qty_tarefa_{ctx["tq"]}', timeout=15000)

            # P1/P2/P3 — campo certo por modo, nunca os dois.
            _ok(page.locator(f'#qty_tarefa_{ctx["tq"]}').count() == 1
                and page.locator(f'#pct_tarefa_{ctx["tq"]}').count() == 0,
                'P1 quantitativa tem só campo de quantidade')
            _ok(page.locator(f'#pct_tarefa_{ctx["tp"]}').count() == 1
                and page.locator(f'#qty_tarefa_{ctx["tp"]}').count() == 0,
                'P2 percentual tem só campo de % acumulado')
            _ok(page.locator(f'#chk_marco_{ctx["tm"]}').count() == 1,
                'P3 marco tem toggle binário')

            # P4 — previews ao vivo espelhando o backend.
            page.fill(f'#qty_tarefa_{ctx["tq"]}', '30')
            page.locator(f'#qty_tarefa_{ctx["tq"]}').dispatch_event('change')
            prev_q = page.locator(f'#preview_tarefa_{ctx["tq"]}').inner_text()
            _ok('30.0% acumulado' in prev_q,
                f'P4 preview quantitativo (texto="{prev_q}")')
            page.fill(f'#pct_tarefa_{ctx["tp"]}', '40')
            page.locator(f'#pct_tarefa_{ctx["tp"]}').dispatch_event('change')
            prev_p = page.locator(f'#preview_tarefa_{ctx["tp"]}').inner_text()
            _ok('+40.0 pp' in prev_p,
                f'P4 preview percentual (texto="{prev_p}")')
            page.check(f'#chk_marco_{ctx["tm"]}')

            # P5 — filtro por nome esconde o que não casa.
            page.fill('#filtroTarefasRDO', 'Percentual')
            page.wait_for_timeout(300)
            _ok(not page.locator(
                    f'[data-tarefa-id="{ctx["tq"]}"]').first.is_visible(),
                'P5 filtro esconde a quantitativa')
            _ok(page.locator(
                    f'[data-tarefa-id="{ctx["tp"]}"]').first.is_visible(),
                'P5 filtro mantém a percentual')
            page.fill('#filtroTarefasRDO', '')

            # P6 — salvar grava os dois modos. expect_navigation: o submit
            # navega assíncrono — sem isso a query abaixo corre contra o POST.
            with page.expect_navigation(wait_until='networkidle',
                                        timeout=30000):
                page.evaluate(
                    "document.getElementById('formNovoRDO').submit()")

            with app.app_context():
                aps = {ap.tarefa_cronograma_id: ap
                       for ap in RDOApontamentoCronograma.query.join(
                           RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
                       .filter(RDO.obra_id == ctx['obra_id']).all()}
                aq, ap_, am = (aps.get(ctx['tq']), aps.get(ctx['tp']),
                               aps.get(ctx['tm']))
                _ok(aq is not None and aq.tipo_apontamento == 'quantitativo'
                    and aq.quantidade_acumulada == 30.0
                    and aq.percentual_realizado == 30.0
                    and aq.quantidade_total_snapshot == 100.0,
                    f'P6 quantitativo gravado (ap={aq and aq.id})')
                _ok(ap_ is not None and ap_.tipo_apontamento == 'percentual'
                    and ap_.percentual_acumulado == 40.0
                    and ap_.quantidade_executada_dia == 0.0,
                    f'P6 percentual gravado sem abuso de quantidade '
                    f'(ap={ap_ and ap_.id})')
                _ok(am is not None and am.percentual_acumulado == 100.0
                    and am.percentual_realizado == 100.0,
                    f'P6 marco gravado como 100 (ap={am and am.id})')

            browser.close()
    finally:
        cleanup(ctx)

    log.info('=' * 70)
    log.info(f'PASSED: {len(passed)}  FAILED: {len(failed)}')
    for f in failed:
        log.error(f' ✗ {f}')
    log.info('=' * 70)
    sys.exit(0 if not failed else 1)


import pytest

pytestmark = pytest.mark.browser


def test_rdo_dois_modos_e2e():
    """Entrypoint pytest (browser): fluxo completo dos dois modos (M07).
    Requer servidor."""
    try:
        main()
    except SystemExit as e:
        assert e.code in (0, None), f'E2E dois modos falhou (exit code={e.code})'


if __name__ == '__main__':
    main()
