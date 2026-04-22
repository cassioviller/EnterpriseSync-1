"""
Task #154 — Playwright e2e: subgrupo aninhado no card "Apontamento de
Produção — Cronograma" do RDO V2.

Cobre o "Done looks like" da task no DOM real (browser):
  P1. Tanto a raiz quanto o subgrupo intermediário renderizam como
      cartão de subgrupo (data-is-pai="1") com badge de contagem.
  P2. Subgrupos NÃO contêm input[type=number], botão "btn-equipe-*",
      nem texto "Total:" / "Acum:".
  P3. Subgrupos contêm a barra "Planejado / Realizado" agregada.
  P4. Folhas contêm input[type=number] (medição).
  P5. Estado inicial: ambos colapsados (wrapper data-filhos-de com
      display:none).
  P6. Clique no header da raiz → expande; clique no header do subgrupo
      intermediário → expande as folhas.
  P7. Cascata visual: ao recolher a raiz, todo o sub-tree some.
  P8. Estado preservado: ao re-expandir a raiz, o subgrupo intermediário
      continua expandido (mostrando suas folhas).

Pré-requisito: o servidor Flask precisa estar rodando em
http://localhost:5000 (workflow "Start application").

Uso direto:
    python tests/test_rdo_subgrupo_aninhado_playwright.py
"""
import os
import sys
import logging
import subprocess
import re
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, expect

from app import app, db
from werkzeug.security import generate_password_hash
from models import Usuario, TipoUsuario, Obra, Cliente, TarefaCronograma

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'


def seed_dados():
    """Cria admin + obra + cronograma aninhado e retorna dict com ids/email."""
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    email = f't154pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f't154pw_{suf}', email=email, nome='T154 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        admin_id = admin.id
        cli = Cliente(admin_id=admin_id, nome=f'Cli PW {suf}',
                      email=f'cli_{suf}@test.local', telefone='119')
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra PW {suf}', codigo=f'PW-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today(), cliente_nome=cli.nome,
        )
        db.session.add(obra); db.session.flush()
        raiz = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, nome_tarefa='LSF PW',
            ordem=1, duracao_dias=10, data_inicio=date.today(),
            responsavel='empresa', is_cliente=False,
        )
        db.session.add(raiz); db.session.flush()
        sub = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=raiz.id,
            nome_tarefa='Estrutura PW', ordem=2, duracao_dias=10,
            data_inicio=date.today(), responsavel='empresa', is_cliente=False,
        )
        db.session.add(sub); db.session.flush()
        fa = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=sub.id,
            nome_tarefa='Aco Laminado PW', ordem=3, duracao_dias=4,
            data_inicio=date.today(), quantidade_total=100.0,
            unidade_medida='kg', responsavel='empresa', is_cliente=False,
        )
        fb = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=sub.id,
            nome_tarefa='Concretagem PW', ordem=4, duracao_dias=6,
            data_inicio=date.today(), quantidade_total=200.0,
            unidade_medida='m3', responsavel='empresa', is_cliente=False,
        )
        db.session.add_all([fa, fb])
        db.session.commit()
        return dict(
            email=email, obra_id=obra.id, raiz_id=raiz.id, sub_id=sub.id,
            fa_id=fa.id, fb_id=fb.id, admin_id=admin_id,
        )


def cleanup(ctx):
    with app.app_context():
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        Obra.query.filter_by(id=ctx['obra_id']).delete()
        Cliente.query.filter_by(admin_id=ctx['admin_id']).delete()
        Usuario.query.filter_by(id=ctx['admin_id']).delete()
        db.session.commit()


def card_locator(page, tarefa_id):
    return page.locator(f'#cronogramaTarefasRDO [data-tarefa-id="{tarefa_id}"]').first


def filhos_wrapper(page, pai_id):
    # querySelectorAll devolve filhos visíveis apenas se ancestral também estiver
    return page.locator(f'#cronogramaTarefasRDO [data-filhos-de="{pai_id}"]').first


def display_inline(handle):
    return handle.evaluate('(el) => el.style.display')


def main():
    ctx = seed_dados()
    log.info(f'Dados semeados: {ctx}')
    failed = []
    passed = []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()

            # 1. Login
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            csrf = page.input_value('input[name="csrf_token"]') if page.locator('input[name="csrf_token"]').count() else ''
            log.info(f'csrf_token presente: {bool(csrf)}')
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, f"login redirecionou (url={page.url})")

            # 2. Abrir RDO novo
            page.goto(f'{BASE_URL}/rdo/novo?obra_id={ctx["obra_id"]}',
                      wait_until='networkidle')

            # Aguardar o fetch de tarefas-rdo popular o container
            page.wait_for_selector(
                f'#cronogramaTarefasRDO [data-tarefa-id="{ctx["raiz_id"]}"]',
                timeout=15000,
            )

            # P1 — pais marcados, folhas não
            for pid in (ctx['raiz_id'], ctx['sub_id']):
                attr = card_locator(page, pid).get_attribute('data-is-pai')
                _ok(attr == '1', f'P1 cartão {pid} é pai (data-is-pai={attr})')
            for fid in (ctx['fa_id'], ctx['fb_id']):
                attr = card_locator(page, fid).get_attribute('data-is-pai')
                _ok(attr == '0', f'P1 cartão folha {fid} (data-is-pai={attr})')

            # Para inspecionar conteúdo dos pais SEM influenciar contagem de
            # descendentes, isolamos o header (1º filho do cartão) — esse é o
            # único trecho exclusivo do próprio nó (o restante é o wrapper de
            # filhos que pode conter inputs/equipes de folhas).
            for pid, label in [(ctx['raiz_id'], 'raiz'),
                               (ctx['sub_id'], 'subgrupo aninhado')]:
                card = card_locator(page, pid)
                # P2 — header do pai não contém medição/equipe/total
                header_html = card.evaluate(
                    "(el) => el.querySelector('.d-flex.align-items-center')?.outerHTML || ''"
                )
                _ok('type="number"' not in header_html,
                    f'P2 {label} ({pid}): sem input numérico no header')
                _ok('btn-equipe-' not in header_html,
                    f'P2 {label} ({pid}): sem botão de equipe no header')
                # 'Total:' e 'Acum:' não devem aparecer em nenhum lugar do
                # próprio cartão (excluindo o wrapper de filhos que está fora).
                # O wrapper de filhos é IRMÃO do cartão, logo basta inspecionar
                # o innerText do próprio cartão.
                inner_text = card.inner_text()
                _ok('Total:' not in inner_text,
                    f'P2 {label} ({pid}): sem texto "Total:"')
                _ok('Acum:' not in inner_text,
                    f'P2 {label} ({pid}): sem texto "Acum:"')
                # P3 — barra Planejado/Realizado presente
                _ok('Planejado' in inner_text and 'Realizado' in inner_text,
                    f'P3 {label} ({pid}): barra Planejado/Realizado presente')

            # P4 — folhas têm input[type=number]
            for fid in (ctx['fa_id'], ctx['fb_id']):
                inputs = card_locator(page, fid).locator('input[type="number"]').count()
                _ok(inputs >= 1, f'P4 folha {fid} tem input numérico (n={inputs})')

            # P5 — wrappers iniciam colapsados
            w_raiz = filhos_wrapper(page, ctx['raiz_id'])
            w_sub = filhos_wrapper(page, ctx['sub_id'])
            _ok(display_inline(w_raiz) == 'none',
                f"P5 wrapper raiz colapsado (display={display_inline(w_raiz)})")
            _ok(display_inline(w_sub) == 'none',
                f"P5 wrapper subgrupo colapsado (display={display_inline(w_sub)})")

            # P6 — expandir raiz
            card_locator(page, ctx['raiz_id']).locator('.rdo-tarefa-pai-header').first.click()
            page.wait_for_function(
                f'document.querySelector(\'[data-filhos-de="{ctx["raiz_id"]}"]\').style.display !== "none"',
                timeout=3000,
            )
            _ok(display_inline(w_raiz) != 'none',
                f"P6 raiz expandida (display={display_inline(w_raiz)})")
            # Subgrupo intermediário visível (mas seu próprio wrapper ainda colapsado)
            sub_visible = card_locator(page, ctx['sub_id']).is_visible()
            _ok(sub_visible, 'P6 cartão subgrupo intermediário aparece após expandir raiz')

            # P6b — expandir subgrupo intermediário
            card_locator(page, ctx['sub_id']).locator('.rdo-tarefa-pai-header').first.click()
            page.wait_for_function(
                f'document.querySelector(\'[data-filhos-de="{ctx["sub_id"]}"]\').style.display !== "none"',
                timeout=3000,
            )
            _ok(display_inline(w_sub) != 'none',
                f"P6 subgrupo intermediário expandido (display={display_inline(w_sub)})")
            for fid in (ctx['fa_id'], ctx['fb_id']):
                _ok(card_locator(page, fid).is_visible(),
                    f'P6 folha {fid} visível após expandir intermediário')

            # P7 — cascata: recolher raiz oculta tudo
            card_locator(page, ctx['raiz_id']).locator('.rdo-tarefa-pai-header').first.click()
            page.wait_for_function(
                f'document.querySelector(\'[data-filhos-de="{ctx["raiz_id"]}"]\').style.display === "none"',
                timeout=3000,
            )
            _ok(display_inline(w_raiz) == 'none',
                f"P7 raiz colapsou (display={display_inline(w_raiz)})")
            _ok(not card_locator(page, ctx['sub_id']).is_visible(),
                'P7 subgrupo intermediário invisível por cascata')
            for fid in (ctx['fa_id'], ctx['fb_id']):
                _ok(not card_locator(page, fid).is_visible(),
                    f'P7 folha {fid} invisível por cascata')

            # P8 — re-expandir raiz preserva estado do subgrupo intermediário
            card_locator(page, ctx['raiz_id']).locator('.rdo-tarefa-pai-header').first.click()
            page.wait_for_function(
                f'document.querySelector(\'[data-filhos-de="{ctx["raiz_id"]}"]\').style.display !== "none"',
                timeout=3000,
            )
            _ok(display_inline(w_sub) != 'none',
                f"P8 subgrupo intermediário continua expandido após reabrir raiz "
                f"(display={display_inline(w_sub)})")
            for fid in (ctx['fa_id'], ctx['fb_id']):
                _ok(card_locator(page, fid).is_visible(),
                    f'P8 folha {fid} visível (estado preservado)')

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
