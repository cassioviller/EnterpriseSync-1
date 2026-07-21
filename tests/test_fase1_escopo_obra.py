"""Fase 1 — escopo por obra.

Até 2026-07-21 o único eixo de isolamento era `admin_id` (tenant): quem
entrava via qualquer papel enxergava TODAS as obras da empresa. Estes
testes travam o segundo eixo — o vínculo usuário↔obra.
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
from models import Cliente, Obra, PapelObra, TipoUsuario, Usuario, UsuarioObra

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-escopo'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1e_{suf}', email=f'f1e_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1o_{suf}', email=f'f1o_{suf}@test.local',
        nome=f'{nome} {suf}', password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'O{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id, ativo=True,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_papel_obra_tem_os_tres_valores_da_fase_1():
    assert {p.name for p in PapelObra} == {'GESTOR', 'APONTADOR', 'LEITOR'}


def test_vinculo_usuario_obra_persiste():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        v = UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                        papel=PapelObra.GESTOR, admin_id=admin.id)
        db.session.add(v)
        db.session.commit()
        vid = v.id

    with app.app_context():
        recarregado = db.session.get(UsuarioObra, vid)
        assert recarregado.papel == PapelObra.GESTOR
        assert recarregado.ativo is True


def test_usuario_nao_se_vincula_duas_vezes_a_mesma_obra():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id))
        db.session.commit()
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
