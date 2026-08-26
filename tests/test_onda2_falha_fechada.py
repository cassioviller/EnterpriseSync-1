"""Onda 2, Task 8 — falhar fechado, e apagar as armadilhas.

Nota do controller: este arquivo NÃO é o `tests/test_onda2_tenant_nao_vaza.py`
que o brief da Task 8 pede — esse nome pertence a outra trilha rodando em
paralelo na mesma onda. Os testes desta task vivem aqui, em
`test_onda2_falha_fechada.py`, para não colidir.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import Cliente, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda2-falha-fechada'
    yield


def _novo_admin(prefixo='onda2'):
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {prefixo} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    return admin


# ---------------------------------------------------------------------------
# Task 8 — falhar fechado, e apagar as armadilhas
# ---------------------------------------------------------------------------

def test_auditoria_de_vinculos_falha_fechada_sem_tenant():
    """🔴 `vinculos_audit_views.py:38` — `Usuario.admin_id` é nullable.

    Para funcionário sem `admin_id`, todo filtro degradava para
    `admin_id IS NULL` e a página abria sobre linhas órfãs em vez de 403.
    """
    import inspect

    import vinculos_audit_views
    fonte = inspect.getsource(vinculos_audit_views._admin_id)
    assert 'require_tenant' in fonte, (
        '_admin_id ainda devolve get_tenant_admin_id() direto, que pode ser '
        'None e vira admin_id IS NULL')


def test_helpers_mortos_de_auth_foram_apagados():
    """`get_tenant_filter` devolvia None para 'super admin vê tudo' E para
    'não autenticado'. O idiomático `if f: query.filter_by(admin_id=f)`
    serviria as linhas de todo tenant a um chamador anônimo.

    Zero consumidores — a mesma condição que justificou apagar
    `almoxarife_required` e irmãos na Fase 1.
    """
    import auth
    assert not hasattr(auth, 'get_tenant_filter')
    assert not hasattr(auth, 'can_access_data')


def test_cliente_resolver_recusa_cliente_id_de_outro_tenant():
    """`services/cliente_resolver.py:61` — FK explícita inválida precisa
    ERGUER, não cair no casamento difuso.

    O chamador (`event_manager.py:1244`) passa `proposta.cliente_id`
    acreditando que a regra 1 ("cliente_id explícito vence sempre") vale de
    verdade. Antes desta correção, um `cliente_id` de OUTRO tenant era
    silenciosamente ignorado e a função caía para o casamento por
    nome/e-mail — podendo criar um Cliente DUPLICADO, sem log nenhum.
    """
    from services.cliente_resolver import obter_ou_criar_cliente

    with app.app_context():
        admin_dono = _novo_admin('onda2_dono')
        admin_estranho = _novo_admin('onda2_estranho')
        cliente_do_dono = Cliente(
            admin_id=admin_dono.id, nome='Cliente do Dono',
            email='dono@test.local', telefone='11988887777')
        db.session.add(cliente_do_dono)
        db.session.commit()
        cliente_id = cliente_do_dono.id
        admin_estranho_id = admin_estranho.id

        antes = Cliente.query.filter_by(admin_id=admin_estranho_id).count()
        assert antes == 0

        with pytest.raises(ValueError):
            obter_ou_criar_cliente(
                admin_id=admin_estranho_id,
                nome='Cliente do Dono',
                email='dono@test.local',
                cliente_id=cliente_id,
            )

        depois = Cliente.query.filter_by(admin_id=admin_estranho_id).count()
        assert depois == 0, (
            'cliente_id de outro tenant não pode cair para o casamento '
            'difuso e criar Cliente duplicado')
