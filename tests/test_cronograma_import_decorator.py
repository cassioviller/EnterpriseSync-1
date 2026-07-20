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


def test_decorators_legados_intactos():
    """M01 §4: o bypass global NÃO muda neste módulo (risco amplo)."""
    import inspect
    import decorators
    for nome in ('admin_required', 'login_required'):
        fonte = inspect.getsource(getattr(decorators, nome))
        assert 'bypass' in fonte, (
            f'{nome} mudou — fora do escopo do M01, reverta'
        )
