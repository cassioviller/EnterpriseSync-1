"""Fase 1 — identidade estável Usuario ↔ Funcionario.

Antes desta fase, "qual Funcionario é o usuário logado" era decidido por
substring de nome (`views/employees.py:686`), por e-mail chumbado
(`crud_rdo_completo.py:30`) e, no último fallback, pelo primeiro
funcionário ativo do banco inteiro (`views/employees.py:704`). Estes
testes travam a FK que substitui tudo isso.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Funcionario, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-identidade'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1a_{suf}', email=f'f1a_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _funcionario_registro(admin_id, email=None):
    """Cria a linha de RH (Funcionario), sem login."""
    suf = uuid.uuid4().hex[:8]
    f = Funcionario(
        codigo=f'F{suf[:6].upper()}',
        nome=f'Funcionario {suf}',
        cpf=f'{suf[:11]}',
        email=email or f'f1f_{suf}@test.local',
        data_admissao=date(2026, 1, 1),
        admin_id=admin_id,
        ativo=True,
    )
    db.session.add(f)
    db.session.commit()
    return f


def test_usuario_tem_coluna_funcionario_id():
    with app.app_context():
        assert hasattr(Usuario, 'funcionario_id'), (
            'Usuario.funcionario_id não existe — a identidade continua '
            'sendo adivinhada por e-mail/substring')


def test_vinculo_usuario_funcionario_persiste():
    with app.app_context():
        admin = _admin()
        func = _funcionario_registro(admin.id)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1u_{suf}', email=f'f1u_{suf}@test.local',
            nome='Operador', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, funcionario_id=func.id,
        )
        db.session.add(u)
        db.session.commit()
        uid, fid = u.id, func.id

    with app.app_context():
        recarregado = db.session.get(Usuario, uid)
        assert recarregado.funcionario_id == fid
        assert recarregado.funcionario is not None
        assert recarregado.funcionario.id == fid


def test_dois_usuarios_nao_compartilham_o_mesmo_funcionario():
    """UNIQUE: uma pessoa de RH tem no máximo um login."""
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        func = _funcionario_registro(admin.id)
        for i in range(2):
            suf = uuid.uuid4().hex[:8]
            db.session.add(Usuario(
                username=f'f1d{i}_{suf}', email=f'f1d{i}_{suf}@test.local',
                nome=f'Dup {i}', password_hash=generate_password_hash('x'),
                tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
                admin_id=admin.id, funcionario_id=func.id,
            ))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_funcionario_id_e_opcional():
    """Admin da construtora não é funcionário; não pode ser obrigatório."""
    with app.app_context():
        admin = _admin()
        assert admin.funcionario_id is None


# ---------------------------------------------------------------------------
# Resolver de identidade
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_vincular_funcionario_recusa_cross_tenant():
    """O invariante que a FK sozinha não consegue expressar."""
    from utils.identidade import VinculoInvalido, vincular_funcionario

    with app.app_context():
        admin_a = _admin('A')
        admin_b = _admin('B')
        func_b = _funcionario_registro(admin_b.id)
        suf = uuid.uuid4().hex[:8]
        u_a = Usuario(
            username=f'f1x_{suf}', email=f'f1x_{suf}@test.local',
            nome='Do tenant A', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin_a.id,
        )
        db.session.add(u_a)
        db.session.commit()

        with pytest.raises(VinculoInvalido):
            vincular_funcionario(u_a, func_b)

        db.session.rollback()
        assert db.session.get(Usuario, u_a.id).funcionario_id is None


def test_vincular_funcionario_aceita_mesmo_tenant():
    from utils.identidade import vincular_funcionario

    with app.app_context():
        admin = _admin()
        func = _funcionario_registro(admin.id)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1y_{suf}', email=f'f1y_{suf}@test.local',
            nome='Operador', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()

        vincular_funcionario(u, func)
        db.session.commit()
        assert db.session.get(Usuario, u.id).funcionario_id == func.id


def test_funcionario_do_usuario_devolve_none_sem_vinculo():
    """Falha fechada: sem vínculo é None, NUNCA o primeiro do banco."""
    from utils.identidade import funcionario_do_usuario

    with app.app_context():
        admin = _admin()
        _funcionario_registro(admin.id)  # existe funcionário no banco
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1z_{suf}', email=f'f1z_{suf}@test.local',
            nome='Sem vinculo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    cliente = _cliente_de(uid)
    with cliente:
        cliente.get('/dashboard')
        assert funcionario_do_usuario() is None


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def test_backfill_casa_por_email_exato_no_mesmo_tenant():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'casa_{uuid.uuid4().hex[:8]}@test.local'
        func = _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1b_{suf}', email=email.upper(),  # caixa diferente
            nome='Casa por email', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid, fid = u.id, func.id

        relatorio = executar_backfill(dry_run=False, admin_id=admin.id)
        assert relatorio['casados'] >= 1
        assert db.session.get(Usuario, uid).funcionario_id == fid


def test_backfill_nao_casa_entre_tenants():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin_a = _admin('A')
        admin_b = _admin('B')
        email = f'mesmo_{uuid.uuid4().hex[:8]}@test.local'
        _funcionario_registro(admin_b.id, email=email)  # RH no tenant B
        suf = uuid.uuid4().hex[:8]
        u_a = Usuario(
            username=f'f1c_{suf}', email=email,  # mesmo e-mail, tenant A
            nome='Do tenant A', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin_a.id,
        )
        db.session.add(u_a)
        db.session.commit()
        uid = u_a.id

        executar_backfill(dry_run=False, admin_id=admin_a.id)
        assert db.session.get(Usuario, uid).funcionario_id is None, (
            'backfill casou entre tenants — vazamento de identidade')


def test_backfill_dry_run_nao_escreve():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'dry_{uuid.uuid4().hex[:8]}@test.local'
        _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1e_{suf}', email=email,
            nome='Dry run', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

        relatorio = executar_backfill(dry_run=True, admin_id=admin.id)
        assert relatorio['casados'] >= 1  # conta o que casaria
        assert db.session.get(Usuario, uid).funcionario_id is None


def test_backfill_e_idempotente():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'idem_{uuid.uuid4().hex[:8]}@test.local'
        func = _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1g_{suf}', email=email,
            nome='Idempotente', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid, fid = u.id, func.id

        executar_backfill(dry_run=False, admin_id=admin.id)
        segunda = executar_backfill(dry_run=False, admin_id=admin.id)
        assert segunda['casados'] == 0, 'segunda passada não deve recasar'
        assert db.session.get(Usuario, uid).funcionario_id == fid


def test_backfill_recusa_email_ambiguo():
    """Dois funcionários com o mesmo e-mail no tenant: não escolher."""
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'ambig_{uuid.uuid4().hex[:8]}@test.local'
        _funcionario_registro(admin.id, email=email)
        _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1h_{suf}', email=email,
            nome='Ambiguo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

        relatorio = executar_backfill(dry_run=False, admin_id=admin.id)
        assert db.session.get(Usuario, uid).funcionario_id is None
        assert any(p['motivo'] == 'ambiguo' for p in relatorio['pendentes'])
