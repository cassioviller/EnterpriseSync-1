"""M08 — Playwright e2e: jornada completa de importação na página da obra.

P1. Aba Cronograma mostra a seção de importações (flag on).
P2. Upload de .xml MSPDI pelo modal → linha aparece processada.
P3. Prévia abre com resumo e 1 pendência (ambígua) → Aplicar desabilitado.
P4. Decisão manual no modal (casar) zera pendências e habilita Aplicar.
P5. Aplicar (com confirmação) → página de resultado.
P6. Banco: renomeada atualizada in-place, removida arquivada (nunca
    apagada), nova inserida, ambígua casada conforme a decisão.

Pré-requisito: servidor Flask em http://localhost:5000.
Uso direto:  python tests/test_cronograma_importacao_obra_playwright.py
"""
import logging
import os
import sys
import tempfile
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from app import app, db
from werkzeug.security import generate_password_hash
from models import (
    Cliente,
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    CronogramaTarefaMapeamento,
    CronogramaTarefaSnapshot,
    CronogramaVersao,
    Obra,
    TarefaCronograma,
    TipoUsuario,
    Usuario,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'


def _task_xml(uid, tid, nome, wbs, inicio, fim, horas, outline=1):
    return f"""    <Task>
      <UID>{uid}</UID><ID>{tid}</ID><Name>{nome}</Name><WBS>{wbs}</WBS>
      <OutlineLevel>{outline}</OutlineLevel><Milestone>0</Milestone>
      <Summary>0</Summary>
      <Start>{inicio}T08:00:00</Start><Finish>{fim}T17:00:00</Finish>
      <Duration>PT{horas}H0M0S</Duration>
      <PercentComplete>0</PercentComplete>
    </Task>"""


def _montar_xml():
    """MSPDI mínimo: rename do uid 200; uid 201 ausente (removida);
    uid 202 nova; 203/204 'Pintura Interna 1/2' → ambíguas vs a tarefa
    sem uid da obra."""
    tarefas = '\n'.join([
        _task_xml(200, 1, 'Alvenaria Terreo Revisada', '1',
                  '2026-08-03', '2026-08-14', 80),
        _task_xml(202, 2, 'Impermeabilizacao Nova', '2',
                  '2026-08-17', '2026-08-21', 40),
        _task_xml(203, 3, 'Pintura Interna 1', '3',
                  '2026-07-01', '2026-07-10', 64),
        _task_xml(204, 4, 'Pintura Interna 2', '4',
                  '2026-07-01', '2026-07-10', 64),
    ])
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<Project xmlns="http://schemas.microsoft.com/project">\n'
            f'  <Name>importacao_e2e.xml</Name>\n'
            f'  <Title>Importacao E2E</Title>\n'
            f'  <Tasks>\n{tarefas}\n  </Tasks>\n</Project>\n')


def seed_dados():
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    email = f'm08pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f'm08pw_{suf}', email=email, nome='M08 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(admin_id=admin.id, nome=f'Cli M08 {suf}',
                      email=f'cli08_{suf[:6]}@test.local', telefone='119')
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra M08 {suf}', codigo=f'M08-{suf[:6]}',
            admin_id=admin.id, status='Em andamento',
            data_inicio=date.today() - timedelta(days=30), cliente_id=cli.id,
        )
        db.session.add(obra); db.session.flush()

        # M10: flag de rollout ligada — sem ela a seção não renderiza.
        from scripts.flag_cronograma_mpp import definir_flag
        definir_flag(admin.id, True)

        base = dict(admin_id=admin.id, obra_id=obra.id, responsavel='empresa',
                    is_cliente=False)
        t1 = TarefaCronograma(nome_tarefa='Alvenaria Terreo', ordem=1,
                              mpp_uid=200, duracao_dias=10,
                              data_inicio=date(2026, 7, 1),
                              data_fim=date(2026, 7, 14), **base)
        t2 = TarefaCronograma(nome_tarefa='Cobertura Antiga', ordem=2,
                              mpp_uid=201, duracao_dias=5,
                              data_inicio=date(2026, 7, 15),
                              data_fim=date(2026, 7, 21), **base)
        t3 = TarefaCronograma(nome_tarefa='Pintura Interna', ordem=3,
                              duracao_dias=8,
                              data_inicio=date(2026, 7, 1),
                              data_fim=date(2026, 7, 10), **base)
        db.session.add_all([t1, t2, t3])
        db.session.commit()
        return dict(email=email, admin_id=admin.id, obra_id=obra.id,
                    cli_id=cli.id, t1=t1.id, t2=t2.id, t3=t3.id)


def cleanup(ctx):
    with app.app_context():
        imps = CronogramaImportacao.query.filter_by(
            obra_id=ctx['obra_id']).all()
        for imp in imps:
            CronogramaTarefaMapeamento.query.filter_by(
                importacao_id=imp.id).delete()
            CronogramaImportacaoEvento.query.filter_by(
                importacao_id=imp.id).delete()
        versoes = CronogramaVersao.query.filter_by(
            obra_id=ctx['obra_id']).all()
        for v in versoes:
            CronogramaTarefaSnapshot.query.filter_by(versao_id=v.id).delete()
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).update(
            {'versao_criacao_id': None})
        db.session.flush()
        for v in versoes:
            db.session.delete(v)
        db.session.flush()      # versões antes das importações (FK)
        for imp in imps:
            db.session.delete(imp)
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        Obra.query.filter_by(id=ctx['obra_id']).delete()
        Cliente.query.filter_by(id=ctx['cli_id']).delete()
        Usuario.query.filter_by(id=ctx['admin_id']).delete()
        db.session.commit()


def main():
    ctx = seed_dados()
    log.info(f'Seed: obra={ctx["obra_id"]}')
    failed, passed = [], []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    xml_path = os.path.join(tempfile.gettempdir(),
                            f'importacao_e2e_{ctx["obra_id"]}.xml')
    with open(xml_path, 'w', encoding='utf-8') as fh:
        fh.write(_montar_xml())

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            page = browser.new_context(
                viewport={'width': 1360, 'height': 900}).new_page()
            page.on('dialog', lambda d: d.accept())

            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')

            # P1 — seção na aba Cronograma.
            page.goto(f'{BASE_URL}/obras/{ctx["obra_id"]}',
                      wait_until='networkidle')
            page.click('button[data-bs-target="#tab-cronograma"]')
            page.wait_for_selector('#secaoCronogramaMpp', timeout=10000)
            _ok(page.locator('#cronMppStatusVersao').inner_text() != '',
                'P1 seção visível na aba Cronograma')

            # P2 — upload pelo modal.
            page.click('#btnAbrirModalImportarCronograma')
            page.wait_for_selector('#inputArquivoCronograma', state='visible')
            page.set_input_files('#inputArquivoCronograma', xml_path)
            page.click('#btnEnviarCronograma')
            page.wait_for_selector(
                '#uploadCronogramaFeedback .fa-check, '
                '#uploadCronogramaFeedback.text-success', timeout=20000)
            page.keyboard.press('Escape')
            page.wait_for_selector('a[href$="/previa"]', timeout=10000)
            _ok(True, 'P2 upload processado e listado')

            # P3 — prévia com pendência.
            with page.expect_navigation(wait_until='networkidle'):
                page.click('a[href$="/previa"]')
            page.wait_for_selector('#previaCorpo tr', timeout=10000)
            pend = page.locator('#previaPendencias').inner_text().strip()
            _ok(pend == '1', f'P3 prévia com 1 pendência (={pend})')
            _ok(page.locator('#btnAplicarVersao').is_disabled(),
                'P3 Aplicar desabilitado com pendência')

            # P4 — decidir a ambígua: casar com 'Pintura Interna 1'.
            page.click('[data-decidir]')
            page.wait_for_selector('#modalDecisao.show', timeout=5000)
            page.check('#acaoCasar')
            page.select_option('#decisaoChave', index=0)
            page.click('#btnSalvarDecisao')
            page.wait_for_function(
                "document.getElementById('previaPendencias').textContent.trim() === '0'",
                timeout=10000)
            _ok(not page.locator('#btnAplicarVersao').is_disabled(),
                'P4 decisão manual habilitou o Aplicar')

            # P5 — aplicar (confirm auto-aceito) → resultado.
            with page.expect_navigation(wait_until='networkidle',
                                        timeout=60000):
                page.click('#btnAplicarVersao')
            _ok(page.url.endswith('/resultado'),
                f'P5 redirecionou ao resultado (url={page.url})')
            _ok('aplicada' in page.locator('body').inner_text().lower(),
                'P5 resultado confirma a aplicação')

            browser.close()

        # P6 — banco: efeitos da aplicação.
        with app.app_context():
            t1 = db.session.get(TarefaCronograma, ctx['t1'])
            t2 = db.session.get(TarefaCronograma, ctx['t2'])
            t3 = db.session.get(TarefaCronograma, ctx['t3'])
            nova = TarefaCronograma.query.filter_by(
                obra_id=ctx['obra_id'],
                nome_tarefa='Impermeabilizacao Nova').first()
            _ok(t1 is not None and t1.nome_tarefa == 'Alvenaria Terreo Revisada'
                and t1.ativa, 'P6 renomeada atualizada in-place')
            _ok(t2 is not None and t2.ativa is False
                and t2.arquivada_em is not None,
                'P6 removida arquivada (nunca apagada)')
            _ok(nova is not None and nova.ativa,
                'P6 nova tarefa inserida')
            _ok(t3 is not None and t3.ativa
                and t3.nome_tarefa == 'Pintura Interna 1',
                f'P6 ambígua casada pela decisão (nome={t3 and t3.nome_tarefa})')
            versao = CronogramaVersao.query.filter_by(
                obra_id=ctx['obra_id'], status='ativa').first()
            _ok(versao is not None, 'P6 versão ativa criada')
    finally:
        try:
            os.unlink(xml_path)
        except OSError:
            pass
        cleanup(ctx)

    log.info('=' * 70)
    log.info(f'PASSED: {len(passed)}  FAILED: {len(failed)}')
    for f in failed:
        log.error(f' ✗ {f}')
    log.info('=' * 70)
    sys.exit(0 if not failed else 1)


import pytest

pytestmark = pytest.mark.browser


def test_importacao_cronograma_na_obra_e2e():
    """Entrypoint pytest (browser): jornada completa de importação na obra
    (M08). Requer servidor."""
    try:
        main()
    except SystemExit as e:
        assert e.code in (0, None), f'E2E importação na obra falhou (exit={e.code})'


if __name__ == '__main__':
    main()
