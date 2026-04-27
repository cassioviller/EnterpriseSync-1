"""
Task #143 — Playwright e2e: validar que o "Progresso geral" exibido nos
cards da listagem `/funcionario/rdo/consolidado?obra_id=<obra>` é
monotonicamente NÃO-DECRESCENTE no tempo (ordem cronológica) para uma
obra que opera em modo V2 (cronograma).

Cobre o "Done looks like" da Task #143:
  P1. A listagem renderiza ao menos 3 cards (.rdo-card) para a obra
      semeada (3 RDOs Finalizados).
  P2. Cada card contém o bloco `.rdo-progress > .progress-header > strong`
      com o valor "X.X%".
  P3. O label da barra é "Progresso geral" (rota V2) — confirma que
      `is_v2_progresso=True` foi aplicado.
  P4. Em ordem CRONOLÓGICA crescente das datas dos RDOs, os percentuais
      são NÃO-DECRESCENTES (cada novo RDO ≥ o anterior).
  P5. O percentual do último RDO bate (±0.5%) com a soma esperada de
      `quantidade_acumulada / quantidade_total * 100` da única tarefa
      semeada.

Pré-requisito: o servidor Flask precisa estar rodando em
http://localhost:5000 (workflow "Start application").

Uso direto:
    python tests/test_rdo_progresso_monotonico_playwright.py
"""
import os
import sys
import re
import logging
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from app import app, db
from werkzeug.security import generate_password_hash
from models import (
    Usuario, TipoUsuario, Obra, Cliente, TarefaCronograma,
    RDO, RDOApontamentoCronograma,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'


# ─────────────────────────────────────────────────────────────────────────
# Seed
# ─────────────────────────────────────────────────────────────────────────
def seed_dados():
    """Cria admin + obra + 1 tarefa V2 + 3 RDOs Finalizados com apontamentos
    crescentes (20%, 50%, 80% acumulado).
    Retorna dict com ids/email/percentuais esperados.
    """
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    email = f't143pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f't143pw_{suf}', email=email, nome='T143 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        admin_id = admin.id

        cli = Cliente(
            admin_id=admin_id, nome=f'Cli T143 {suf}',
            email=f'cli143_{suf[:6]}@test.local', telefone='119',
        )
        db.session.add(cli); db.session.flush()

        obra = Obra(
            nome=f'Obra T143 {suf}', codigo=f'T143-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today() - timedelta(days=30),
            cliente_id=cli.id,
        )
        db.session.add(obra); db.session.flush()

        # Tarefa V2 com plano (data_inicio + duração) → engine produz
        # progresso_geral_pct = realizado_acumulado / quantidade_total.
        tarefa = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id,
            nome_tarefa=f'Alvenaria T143 {suf}',
            ordem=1, duracao_dias=10,
            data_inicio=date.today() - timedelta(days=10),
            quantidade_total=100.0, unidade_medida='m2',
            responsavel='empresa', is_cliente=False,
        )
        db.session.add(tarefa); db.session.flush()

        # 3 RDOs Finalizados em datas crescentes com apontamentos crescentes.
        rdos_info = []
        cronologia = [
            # (dias_atras, acumulado_no_dia)
            (5, 20.0),
            (3, 50.0),
            (1, 80.0),
        ]
        for i, (delta, acum) in enumerate(cronologia, start=1):
            d = date.today() - timedelta(days=delta)
            rdo = RDO(
                numero_rdo=f'RDO-T143-{suf[:6]}-{i:03d}',
                obra_id=obra.id, admin_id=admin_id,
                criado_por_id=admin_id,
                data_relatorio=d, status='Finalizado',
                local='Campo', clima_geral='Ensolarado',
            )
            db.session.add(rdo); db.session.flush()

            # qtd_dia = delta sobre o anterior; primeiro = acum direto
            anterior = cronologia[i-2][1] if i > 1 else 0.0
            qtd_dia = acum - anterior
            ap = RDOApontamentoCronograma(
                admin_id=admin_id,
                rdo_id=rdo.id,
                tarefa_cronograma_id=tarefa.id,
                quantidade_executada_dia=qtd_dia,
                quantidade_acumulada=acum,
                percentual_realizado=acum,  # tarefa de 100 → percentual = acum
            )
            db.session.add(ap)
            rdos_info.append({'rdo_id': rdo.id, 'data': d, 'acum': acum})

        db.session.commit()

        return dict(
            email=email,
            admin_id=admin_id,
            obra_id=obra.id,
            cli_id=cli.id,
            tarefa_id=tarefa.id,
            rdos=rdos_info,           # ordem cronológica crescente
            esperado_ultimo_pct=80.0, # quantidade_acumulada / 100 * 100
        )


def cleanup(ctx):
    with app.app_context():
        for r in ctx['rdos']:
            RDOApontamentoCronograma.query.filter_by(rdo_id=r['rdo_id']).delete()
            RDO.query.filter_by(id=r['rdo_id']).delete()
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        Obra.query.filter_by(id=ctx['obra_id']).delete()
        Cliente.query.filter_by(id=ctx['cli_id']).delete()
        Usuario.query.filter_by(id=ctx['admin_id']).delete()
        db.session.commit()


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────
_PCT_RE = re.compile(r'([\-\d]+(?:[.,]\d+)?)\s*%')


def parse_card_pct(card_text: str):
    m = _PCT_RE.search(card_text)
    if not m:
        return None
    return float(m.group(1).replace(',', '.'))


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def main():
    ctx = seed_dados()
    log.info(f'Dados semeados: obra_id={ctx["obra_id"]} '
             f'rdos={[r["rdo_id"] for r in ctx["rdos"]]}')
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

            # 1) Login
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, f"login redirecionou (url={page.url})")

            # 2) Lista RDO consolidada filtrada pela obra
            url = f'{BASE_URL}/funcionario/rdo/consolidado?obra_id={ctx["obra_id"]}'
            page.goto(url, wait_until='networkidle')

            # P1 — pelo menos 3 cards renderizados
            cards = page.locator('.rdos-grid .rdo-card')
            n_cards = cards.count()
            _ok(n_cards >= 3,
                f'P1 listagem renderizou ≥3 cards (n={n_cards})')

            # Coleta {(data_str, pct, label)} por card.
            # A rota lista por RDO.data_relatorio.desc() → ordem DOM = mais
            # novo primeiro. Preservamos essa ordem e invertemos depois.
            colhidos = []
            for i in range(n_cards):
                c = cards.nth(i)
                data_txt = c.locator('.rdo-date span').first.inner_text().strip()
                prog_block = c.locator('.rdo-progress')
                # P2 — bloco de progresso presente
                _ok(prog_block.count() == 1,
                    f'P2 card[{i}] tem .rdo-progress')
                # Texto bruto para parser tolerante.
                strong_txt = prog_block.locator('.progress-header strong').first.inner_text()
                pct = parse_card_pct(strong_txt)
                _ok(pct is not None,
                    f'P2 card[{i}] tem percentual em <strong> '
                    f'(strong="{strong_txt}", pct={pct})')
                # P3 — label "Progresso geral" (V2)
                header_txt = prog_block.locator('.progress-header').first.inner_text()
                _ok('progresso geral' in header_txt.lower(),
                    f'P3 card[{i}] usa label "Progresso geral" '
                    f'(header="{header_txt!r}")')
                colhidos.append({
                    'idx': i,
                    'data_txt': data_txt,
                    'pct': pct or 0.0,
                })

            # P4 — invertendo a ordem DOM (desc) → ordem cronológica asc.
            ordem_cronologica = list(reversed(colhidos))
            log.info(
                'Ordem cronológica detectada (asc): '
                + ', '.join(
                    f'{c["data_txt"]}={c["pct"]:.1f}%' for c in ordem_cronologica
                )
            )
            ok_monotonico = True
            for j in range(1, len(ordem_cronologica)):
                if ordem_cronologica[j]['pct'] + 1e-6 < ordem_cronologica[j-1]['pct']:
                    ok_monotonico = False
                    log.error(
                        f'P4 violação: card[{ordem_cronologica[j-1]["idx"]}] '
                        f'({ordem_cronologica[j-1]["data_txt"]}, '
                        f'{ordem_cronologica[j-1]["pct"]:.1f}%) > '
                        f'card[{ordem_cronologica[j]["idx"]}] '
                        f'({ordem_cronologica[j]["data_txt"]}, '
                        f'{ordem_cronologica[j]["pct"]:.1f}%)'
                    )
            _ok(ok_monotonico,
                f'P4 progressos não-decrescentes em ordem cronológica '
                f'(seq={[round(c["pct"],1) for c in ordem_cronologica]})')

            # P5 — último ponto bate com o esperado pela engine.
            ultimo_pct = ordem_cronologica[-1]['pct']
            esperado = ctx['esperado_ultimo_pct']
            _ok(abs(ultimo_pct - esperado) <= 0.5,
                f'P5 último RDO ≈ esperado (ultimo={ultimo_pct:.1f}%, '
                f'esperado≈{esperado:.1f}%)')

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
