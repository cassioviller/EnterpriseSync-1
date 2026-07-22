"""Fase 0 / R3 — furos de autenticação e de isolamento de tenant.

Três buracos independentes, todos verificados no código antes da correção:

1. `/funcionario/rdo/consolidado` (`views/rdo.py`) não tinha
   `@login_required` — e não há `before_request` global no app. Com
   `get_admin_id_dinamico` caindo numa cascata de heurísticas para
   anônimo (admin com mais funcionários → mais serviços → o primeiro →
   `return 1`), a rota entregava RDOs de uma empresa arbitrária.
2. `/usuarios/<id>/editar` (`views/users.py`) fazia
   `Usuario.query.get_or_404(user_id)` sem predicado de `admin_id`: um
   ADMIN da empresa A editava usuário da empresa B só sabendo o id.
3. Os relatórios `dashboard-executivo`, `progresso-obras` e
   `rentabilidade` (`relatorios_funcionais.py`) agregavam TODAS as
   empresas do banco.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase0-autz'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f0_{suf}', email=f'f0_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# 1 — rota anônima
# ---------------------------------------------------------------------------

def test_rdo_consolidado_exige_autenticacao():
    anon = app.test_client()
    r = anon.get('/funcionario/rdo/consolidado', follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'rota anônima devolveu {r.status_code} — deveria exigir login')
    if r.status_code == 302:
        assert '/login' in r.headers.get('Location', '')


@pytest.mark.parametrize('rota', [
    # F2 — blueprint /prod: 6 rotas anônimas com tenant por heurística
    '/prod/safe-funcionarios',
    '/prod/safe-dashboard',
    '/prod/safe-obras',
    '/prod/debug-info',
    # F3 — api_funcionarios: `utils.auth_utils` não existe, o except era o
    # único caminho e o ramo anônimo caía em `return 10`
    '/api/funcionarios-ativos',
    '/api/funcionarios/buscar',
    # F6 — decorator comentado "temporariamente" e nunca restaurado
    '/funcionarios',
])
def test_rotas_anonimas_de_tenant_exigem_login(rota):
    anon = app.test_client()
    r = anon.get(rota, follow_redirects=False)
    assert r.status_code in (302, 401, 403), (
        f'{rota} respondeu {r.status_code} para anônimo — deveria exigir login')


def test_categoria_servicos_nao_grava_sem_login():
    """F4 — POST/DELETE sem auth gravavam no tenant 10 chumbado."""
    anon = app.test_client()
    r = anon.post('/categorias-servicos/api/criar',
                  json={'nome': 'INVASOR'}, follow_redirects=False)
    assert r.status_code in (302, 401, 403), (
        f'criação de categoria aceita sem login (status {r.status_code})')


def test_resolvedores_de_tenant_nao_tem_mais_fallback_chumbado():
    """Nenhum resolvedor pode devolver um tenant concreto (1, 2 ou 10)."""
    from api_funcionarios import get_admin_id as admin_id_api
    from categoria_servicos import get_admin_id as admin_id_cat
    from views.helpers import get_admin_id_dinamico

    with app.test_request_context('/'):
        assert admin_id_api() is None
        assert admin_id_cat() is None
        assert get_admin_id_dinamico() is None


def test_resolucao_de_tenant_sem_usuario_nao_chuta_empresa():
    """`get_admin_id_dinamico` não pode mais auto-detectar tenant."""
    from views.helpers import get_admin_id_dinamico

    with app.test_request_context('/'):
        assert get_admin_id_dinamico() is None, (
            'sem usuário autenticado a resolução de tenant deve falhar '
            'segura, nunca escolher uma empresa por heurística')


# ---------------------------------------------------------------------------
# 2 — edição de usuário atravessando tenant
# ---------------------------------------------------------------------------

def test_admin_nao_edita_usuario_de_outro_tenant():
    with app.app_context():
        admin_a = _admin('Empresa A')
        admin_b = _admin('Empresa B')
        # Funcionário pertencente ao tenant B.
        suf = uuid.uuid4().hex[:8]
        alvo = Usuario(
            username=f'alvo_{suf}', email=f'alvo_{suf}@test.local',
            nome='Alvo do tenant B',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin_b.id,
        )
        db.session.add(alvo)
        db.session.commit()
        a_id, alvo_id, nome_original = admin_a.id, alvo.id, alvo.nome

    c = _cliente_de(a_id)
    r = c.get(f'/usuarios/{alvo_id}/editar', follow_redirects=False)
    assert r.status_code == 404, (
        f'admin do tenant A alcançou usuário do tenant B (status {r.status_code})')

    # E o POST também não passa.
    r = c.post(f'/usuarios/{alvo_id}/editar', data={
        'nome': 'INVADIDO', 'email': 'x@x.com', 'username': 'x',
        'tipo_usuario': 'FUNCIONARIO',
    }, follow_redirects=False)
    assert r.status_code == 404

    with app.app_context():
        assert db.session.get(Usuario, alvo_id).nome == nome_original


def test_admin_edita_usuario_do_proprio_tenant():
    """Guarda de não-regressão: o escopo não pode bloquear o caso legítimo."""
    with app.app_context():
        admin = _admin('Empresa Propria')
        suf = uuid.uuid4().hex[:8]
        meu = Usuario(
            username=f'meu_{suf}', email=f'meu_{suf}@test.local',
            nome='Funcionario proprio',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(meu)
        db.session.commit()
        admin_id, meu_id = admin.id, meu.id

    c = _cliente_de(admin_id)
    r = c.get(f'/usuarios/{meu_id}/editar', follow_redirects=False)
    assert r.status_code == 200, (
        f'admin não conseguiu editar usuário do próprio tenant ({r.status_code})')


# ---------------------------------------------------------------------------
# 3 — relatórios consolidando todas as empresas
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4 — tenant vindo do FORMULÁRIO (escrita entre tenants)
# ---------------------------------------------------------------------------

def test_salvar_rdo_ignora_admin_id_do_formulario():
    """`/salvar-rdo-flexivel` aceitava `admin_id_form` do POST.

    `session['admin_id']` só era gravado dentro da própria função, então na
    primeira gravação o tenant vinha do campo oculto do formulário — e
    `@funcionario_required` (auth.py:36) só checa autenticação. Qualquer
    usuário logado escrevia RDO no tenant alheio.
    """
    from datetime import date

    from models import RDO, Cliente, Obra

    with app.app_context():
        atacante = _admin('Atacante')
        vitima = _admin('Vitima')
        suf = uuid.uuid4().hex[:8]
        cli = Cliente(admin_id=vitima.id, nome=f'Cli {suf}',
                      email=f'c_{suf}@test.local', telefone='119')
        db.session.add(cli)
        db.session.flush()
        obra_vitima = Obra(nome=f'Obra Vitima {suf}', codigo=f'VT-{suf}',
                           admin_id=vitima.id, cliente_id=cli.id,
                           status='Em andamento', data_inicio=date(2026, 7, 1))
        db.session.add(obra_vitima)
        db.session.commit()
        atacante_id, vitima_id = atacante.id, vitima.id
        obra_vitima_id = obra_vitima.id
        rdos_antes = RDO.query.filter_by(admin_id=vitima_id).count()

    c = _cliente_de(atacante_id)
    r = c.post('/salvar-rdo-flexivel', data={
        'admin_id_form': str(vitima_id),      # o tenant alheio
        'obra_id': str(obra_vitima_id),       # a obra alheia
        'data_relatorio': '2026-07-21',
        'local': 'Campo',
    }, follow_redirects=False)

    # Não importa o código exato (403/404/302) — importa que NADA foi gravado
    # no tenant da vítima.
    with app.app_context():
        assert RDO.query.filter_by(admin_id=vitima_id).count() == rdos_antes, (
            f'RDO gravado no tenant alheio via admin_id_form (status {r.status_code})')


def test_relatorios_consolidados_sao_escopados_por_tenant():
    from models import Obra, Cliente
    from datetime import date

    def _obra_de(admin, nome):
        suf = uuid.uuid4().hex[:8]
        cli = Cliente(admin_id=admin.id, nome=f'Cli {suf}',
                      email=f'c_{suf}@test.local', telefone='119')
        db.session.add(cli)
        db.session.flush()
        o = Obra(nome=nome, codigo=f'F0-{suf}', admin_id=admin.id,
                 cliente_id=cli.id, status='Em andamento',
                 data_inicio=date(2026, 7, 1), ativo=True, orcamento=1000.0)
        db.session.add(o)
        db.session.commit()
        return o

    with app.app_context():
        admin_a = _admin('Rel A')
        admin_b = _admin('Rel B')
        _obra_de(admin_a, 'OBRA-VISIVEL-A')
        _obra_de(admin_b, 'OBRA-SECRETA-B')
        a_id = admin_a.id

    c = _cliente_de(a_id)
    for tipo in ('progresso-obras', 'rentabilidade'):
        r = c.post(f'/relatorios/gerar/{tipo}', json={})
        assert r.status_code == 200, f'{tipo} → {r.status_code}'
        html = r.get_json()['html']
        assert 'OBRA-VISIVEL-A' in html, f'{tipo} não mostrou a obra do tenant'
        assert 'OBRA-SECRETA-B' not in html, (
            f'{tipo} VAZOU obra de outro tenant')


def test_dashboard_executivo_conta_apenas_o_proprio_tenant():
    from models import Obra, Cliente
    from datetime import date

    with app.app_context():
        admin_a = _admin('Exec A')
        admin_b = _admin('Exec B')
        for admin, n in ((admin_a, 1), (admin_b, 5)):
            for i in range(n):
                suf = uuid.uuid4().hex[:8]
                cli = Cliente(admin_id=admin.id, nome=f'Cli {suf}',
                              email=f'c_{suf}@test.local', telefone='119')
                db.session.add(cli)
                db.session.flush()
                db.session.add(Obra(
                    nome=f'Obra {i} {suf}', codigo=f'EX-{suf}',
                    admin_id=admin.id, cliente_id=cli.id,
                    status='Em andamento', data_inicio=date(2026, 7, 1),
                    ativo=True))
        db.session.commit()
        a_id = admin_a.id

    c = _cliente_de(a_id)
    r = c.post('/relatorios/gerar/dashboard-executivo', json={})
    assert r.status_code == 200
    html = r.get_json()['html']
    # O tenant A tem exatamente 1 obra ativa; se o filtro sumir, o número
    # explode (o banco tem milhares de obras de outros tenants).
    assert '<h2 class="text-success">1</h2>' in html, (
        'contagem de obras do dashboard executivo não está escopada por '
        f'tenant. HTML: {html[:400]}')
