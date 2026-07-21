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
