"""Fase 5 — assinatura do RDO.

Antes desta fase não existia assinatura nenhuma: o PDF imprimia uma
LINHA EM BRANCO para caneta (services/rdo_pdf_service.py:798-865) e o
único vínculo com uma pessoa era `RDO.criado_por_id` → `usuario.id`,
sem papel, sem carimbo de tempo, sem integridade.

Decisão jurídica adotada (ver seção "A decisão jurídica" do plano):
registro de autoria + integridade (hash SHA-256 + timestamp + IP),
NÃO ICP-Brasil. Base: MP 2.200-2/2001, art. 10, §2º. `provedor` nasce
'interno' para que Clicksign/D4Sign entre depois sem migração.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, Obra, PapelObra, RDO, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-assinatura'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin F5A'):
    suf = _sfx()
    u = Usuario(
        username=f'f5s_{suf}', email=f'f5s_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _funcionario(admin_id, nome='Encarregado'):
    suf = _sfx()
    f = Funcionario(
        codigo=f'F5{suf[:6].upper()}', nome=f'{nome} {suf}',
        cpf=suf.ljust(14, '0')[:14], email=f'f5f_{suf}@test.local',
        data_admissao=date(2025, 1, 1), admin_id=admin_id, ativo=True,
    )
    db.session.add(f)
    db.session.commit()
    return f


def _operador(admin_id, funcionario, nome='Apontador'):
    """Usuário FUNCIONARIO já vinculado à pessoa de RH (Fase 1)."""
    suf = _sfx()
    u = Usuario(
        username=f'f5o_{suf}', email=f'f5o_{suf}@test.local', nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, funcionario_id=funcionario.id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F5A'):
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5A-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'OA5{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cli.id, valor_contrato=250000,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _vincular(usuario, obra, papel):
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id, papel=papel,
                    admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def _rdo(obra, admin_id, criado_por_id=None):
    suf = _sfx()
    r = RDO(
        numero_rdo=f'RDO-F5A-{suf}', data_relatorio=date(2026, 6, 22),
        obra_id=obra.id, admin_id=admin_id, criado_por_id=criado_por_id,
        comentario_geral='Montagem dos perfis de aço do painel P3.',
        clima_geral='Ensolarado', temperatura_media='28°C',
    )
    db.session.add(r)
    db.session.commit()
    return r


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def test_modelo_de_assinatura_existe_e_persiste():
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id, criado_por_id=op.id)

        a = RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, cargo_signatario='Encarregado',
            hash_conteudo='a' * 64, algoritmo='sha256', provedor='interno',
            ip='203.0.113.9', user_agent='pytest/1.0',
        )
        db.session.add(a)
        db.session.commit()
        aid = a.id

    with app.app_context():
        r = db.session.get(RDOAssinatura, aid)
        assert r.papel == 'executor'
        assert r.algoritmo == 'sha256'
        assert r.provedor == 'interno'
        assert r.assinado_em is not None
        assert r.hash_conteudo == 'a' * 64


def test_uma_assinatura_por_papel_por_rdo():
    """O mesmo papel não assina duas vezes o mesmo RDO."""
    from sqlalchemy.exc import IntegrityError

    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)

        for i in range(2):
            db.session.add(RDOAssinatura(
                rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
                funcionario_id=func.id, papel='executor',
                nome_signatario=op.nome, hash_conteudo='b' * 64,
                algoritmo='sha256', provedor='interno'))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_assinatura_e_apagada_junto_com_o_rdo():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import escrita_de_ciclo_de_vida

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, hash_conteudo='c' * 64,
            algoritmo='sha256', provedor='interno'))
        db.session.commit()
        rid = rdo.id
        # O RDO ainda está em rascunho, então a guarda não bloqueia o delete.
        db.session.delete(rdo)
        db.session.commit()
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0
