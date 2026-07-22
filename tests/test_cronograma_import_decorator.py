"""Módulo 01 / passo 7 — decorator de autorização real para as rotas de
importação de cronograma (Módulos 3/5/8).

`decorators.py` inteiro é bypass ("Durante desenvolvimento, bypass para
todos"). O plano M01 §4/§15 pede um decorator NOVO — sem tocar os
existentes — que exija usuário autenticado com `admin_id` resolvido via
`utils.tenant.get_tenant_admin_id`. Como as rotas consumidoras são
administrativas (upload/prévia/aplicação de importação), o decorator
também exige tipo ADMIN ou SUPER_ADMIN.

Testado chamando a função decorada direto em `test_request_context`
(registrar rota nova aqui quebraria com a suíte inteira: o Flask trava
blueprints após o primeiro request).
"""
from datetime import datetime

import pytest
from flask_login import login_user
from werkzeug.security import generate_password_hash

from app import app, db
from decorators import cronograma_import_required
from models import TipoUsuario, Usuario


@cronograma_import_required
def _vista_protegida():
    return 'conteudo-protegido'


def _criar_usuario(tipo, **extra):
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    u = Usuario(
        username=f'dec_{tipo.value}_{suf}',
        email=f'dec_{tipo.value}_{suf}@test.local',
        nome=f'Decorator {tipo.value}',
        password_hash=generate_password_hash('x'),
        tipo_usuario=tipo,
        ativo=True,
        **extra,
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture(scope='module', autouse=True)
def _config():
    app.config['TESTING'] = True
    yield


def test_anonimo_recebe_401():
    with app.app_context(), app.test_request_context('/x'):
        resp, status = _vista_protegida()
        assert status == 401


def test_admin_autenticado_passa():
    with app.app_context():
        admin = _criar_usuario(TipoUsuario.ADMIN)
        with app.test_request_context('/x'):
            login_user(admin)
            assert _vista_protegida() == 'conteudo-protegido'


def test_funcionario_recebe_403():
    """Importar cronograma é operação administrativa — funcionário não passa,
    mesmo autenticado e com admin_id resolvível."""
    with app.app_context():
        admin = _criar_usuario(TipoUsuario.ADMIN)
        func = _criar_usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id)
        with app.test_request_context('/x'):
            login_user(func)
            resp, status = _vista_protegida()
            assert status == 403


def test_decorators_legados_nao_sao_mais_no_op():
    """Fase 0 / R2 — trava INVERTIDA (atualizada na Fase 1).

    No M01 este teste garantia que o bypass global não fosse mexido (o
    saneamento estava fora do escopo daquele módulo). A Fase 0 saneou com
    shims que delegavam; a Fase 1 foi além e `decorators.admin_required`
    virou RE-EXPORT do real (`from auth import admin_required`) — identidade,
    não delegação. `inspect.getsource` sobre o re-export devolve o fonte de
    `auth.admin_required`, então a checagem de string do shim deixou de
    fazer sentido para ele. O teste passa a travar cada um pelo que é:
    identidade para `admin_required`, delegação para `login_required`.
    """
    import inspect

    import auth
    import decorators

    assert decorators.admin_required is auth.admin_required, (
        'decorators.admin_required deixou de ser o re-export de '
        'auth.admin_required — se voltou a ser definição própria, confira '
        'que não é o no-op ("bypass para todos") que deixava 31 rotas de '
        'configuração e ponto sem autorização'
    )

    fonte = inspect.getsource(decorators.login_required)
    assert 'bypass para todos' not in fonte, (
        'login_required voltou a ser no-op — 31 rotas de configuração e '
        'ponto ficam sem autorização'
    )
    assert 'flask_login import login_required' in fonte, (
        'login_required deveria delegar para a implementação real '
        '(flask_login import login_required)'
    )


def test_rotas_de_configuracao_exigem_admin():
    """A consequência prática de R2: funcionário não grava configuração."""
    import configuracoes_views  # noqa: F401 — registra o blueprint

    with app.app_context():
        func_id = _criar_usuario(TipoUsuario.FUNCIONARIO).id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(func_id)
        sess['_fresh'] = True
    r = c.get('/configuracoes/empresa', follow_redirects=False)
    # auth.admin_required redireciona (302) quem não é ADMIN.
    assert r.status_code == 302, (
        f'funcionário acessou /configuracoes/empresa (status {r.status_code})')

    anon = app.test_client()
    r = anon.get('/configuracoes/empresa', follow_redirects=False)
    assert r.status_code == 302
