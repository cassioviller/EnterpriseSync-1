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
    """Fase 0 / R2 — trava INVERTIDA.

    No M01 este teste garantia que o bypass global não fosse mexido (o
    saneamento estava fora do escopo daquele módulo). A Fase 0 saneou:
    `decorators.admin_required` e `decorators.login_required` agora delegam
    para as implementações reais. O teste passa a impedir a regressão
    contrária — que alguém devolva o `return f(*args, **kwargs)` solto.
    """
    import inspect

    import decorators

    for nome, esperado in (('admin_required', 'auth import admin_required'),
                           ('login_required', 'flask_login import login_required')):
        fonte = inspect.getsource(getattr(decorators, nome))
        assert 'bypass para todos' not in fonte, (
            f'{nome} voltou a ser no-op — 31 rotas de configuração e ponto '
            f'ficam sem autorização'
        )
        assert esperado in fonte, (
            f'{nome} deveria delegar para a implementação real ({esperado})'
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
