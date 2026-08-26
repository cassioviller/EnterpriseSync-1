"""Onda 2 — o tenant para de vazar.

O arreio é `tests/helpers_tenant.py` (`dois_tenants`, `cliente_de`), que existe
desde o p1. A regra dele: nada é compartilhado entre A e B, e a busca é PELA
MARCA — contar dá o mesmo número quando cada tenant tem um registro.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda2-tenant'
    yield


def _usuario_com_papel(papel, admin_id):
    """Um usuário do papel pedido, pendurado num admin que NÃO é ele."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'onda2_{suf}', email=f'onda2_{suf}@test.local',
        nome=f'Papel {papel.value} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=papel, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.flush()
    return u


# ---------------------------------------------------------------------------
# Task 2 — a raiz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('papel', [TipoUsuario.GESTOR_EQUIPES,
                                   TipoUsuario.ALMOXARIFE])
def test_gestor_e_almoxarife_resolvem_o_tenant_do_dono(papel):
    """🔴 `multitenant_helper.py:25` devolvia `current_user.id` para estes dois.

    Um gestor com id=42 e admin_id=7 escrevia tudo em admin_id=42 — um tenant
    que não existe. Invisível para o admin 7, e leitura vazia de volta.
    """
    from multitenant_helper import get_admin_id
    from utils.tenant import get_tenant_admin_id

    with app.app_context():
        a, _b = dois_tenants('onda2_raiz', com_fatos=False)
        usuario = _usuario_com_papel(papel, admin_id=a.admin_id)
        db.session.commit()
        uid, esperado = usuario.id, a.admin_id

    assert uid != esperado, 'o fixture precisa distinguir id de admin_id'

    cliente = cliente_de(uid)
    with cliente.session_transaction():
        pass
    with app.test_request_context():
        from flask_login import login_user
        login_user(Usuario.query.get(uid))
        assert get_admin_id() == esperado, (
            f'{papel.value}: get_admin_id devolveu o próprio id, não o do dono')
        # e os dois resolvedores passam a concordar, que é o ponto da task
        assert get_admin_id() == get_tenant_admin_id()


@pytest.mark.parametrize('papel', [TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN])
def test_admin_e_super_admin_nao_mudam(papel):
    """A delegação não pode mexer nos papéis que já estavam certos."""
    from multitenant_helper import get_admin_id

    with app.app_context():
        suf = uuid.uuid4().hex[:8]
        u = Usuario(username=f'onda2adm_{suf}',
                    email=f'onda2adm_{suf}@test.local', nome='Adm',
                    password_hash=generate_password_hash('Senha@2026'),
                    tipo_usuario=papel, ativo=True, versao_sistema='v2')
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with app.test_request_context():
        from flask_login import login_user
        login_user(Usuario.query.get(uid))
        assert get_admin_id() == uid


def test_sem_request_context_devolve_none_em_vez_de_levantar():
    """A casca defensiva de hoje precisa sobreviver à delegação.

    `get_tenant_admin_id` acessa `current_user` direto e levanta fora de
    request; `get_admin_id` é chamado de job, seed e CLI.
    """
    from multitenant_helper import get_admin_id
    assert get_admin_id() is None
