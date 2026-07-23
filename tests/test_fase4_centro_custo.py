"""Fase 4 — centro de custo administrativo por tenant.

`centro_custo.codigo` era UNIQUE GLOBAL (`models.py:712`; constraint
`centro_custo_codigo_key` no banco, conferida em 2026-07-21). Num sistema
multi-tenant isso significa que o primeiro tenant a criar o código 'ADM'
impede todos os outros. Como a Fase 4 precisa de exatamente um centro
administrativo POR TENANT, a unicidade tem de ser (admin_id, codigo).
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints
from app import app, db
from models import CentroCusto, Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase4-centro-custo'
    yield


def _admin(prefixo='f4'):
    suf = uuid.uuid4().hex[:10]
    u = Usuario(
        username=f'{prefixo}a_{suf}', email=f'{prefixo}a_{suf}@test.local',
        nome=f'Empresa {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F4'):
    """Obra.cliente_id é NOT NULL (models.py:265) — o cliente vem junto."""
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'F4{suf[:6].upper()}',
        cliente_id=cli.id, admin_id=admin_id,
        data_inicio=date(2026, 1, 1), ativo=True,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_dois_tenants_podem_ter_o_mesmo_codigo_de_centro_custo():
    with app.app_context():
        a1 = _admin()
        a2 = _admin()
        db.session.add(CentroCusto(
            admin_id=a1.id, codigo='ADM', nome='Administracao 1',
            tipo='administrativo', ativo=True))
        db.session.commit()
        db.session.add(CentroCusto(
            admin_id=a2.id, codigo='ADM', nome='Administracao 2',
            tipo='administrativo', ativo=True))
        db.session.commit()

        achados = CentroCusto.query.filter(
            CentroCusto.codigo == 'ADM',
            CentroCusto.admin_id.in_([a1.id, a2.id]),
        ).count()
        assert achados == 2, (
            'centro_custo.codigo ainda é único global — um tenant bloqueia o '
            'outro')


def test_mesmo_tenant_nao_repete_codigo_de_centro_custo():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        a = _admin()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='CC900', nome='Um', tipo='obra', ativo=True))
        db.session.commit()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='CC900', nome='Dois', tipo='obra', ativo=True))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_um_unico_centro_administrativo_por_tenant():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        a = _admin()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='ADM', nome='Adm', tipo='administrativo',
            ativo=True))
        db.session.commit()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='ADM2', nome='Adm bis',
            tipo='administrativo', ativo=True))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Resolver do centro administrativo
# ---------------------------------------------------------------------------

def test_centro_administrativo_cria_uma_vez_e_reaproveita():
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a = _admin()
        cc1 = centro_custo_administrativo(a.id)
        db.session.commit()
        cc2 = centro_custo_administrativo(a.id)
        db.session.commit()

        assert cc1 is not None
        assert cc1.id == cc2.id
        assert cc1.codigo == 'ADM'
        assert cc1.tipo == 'administrativo'
        assert cc1.obra_id is None
        assert cc1.admin_id == a.id
        assert CentroCusto.query.filter_by(
            admin_id=a.id, tipo='administrativo').count() == 1


def test_centro_administrativo_nao_cria_quando_criar_false():
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a = _admin()
        assert centro_custo_administrativo(a.id, criar=False) is None
        assert CentroCusto.query.filter_by(admin_id=a.id).count() == 0


def test_centro_administrativo_e_por_tenant():
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a1 = _admin()
        a2 = _admin()
        cc1 = centro_custo_administrativo(a1.id)
        cc2 = centro_custo_administrativo(a2.id)
        db.session.commit()
        assert cc1.id != cc2.id
        assert cc1.admin_id == a1.id
        assert cc2.admin_id == a2.id


def test_centro_administrativo_devolve_none_sem_tenant():
    """Falha fechada: sem tenant não se inventa centro de custo."""
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        assert centro_custo_administrativo(None) is None


# ---------------------------------------------------------------------------
# gestao_custo_pai.obra_id — coluna DERIVADA (nullable de propósito)
# ---------------------------------------------------------------------------

def test_gestao_custo_pai_tem_coluna_obra_id():
    from models import GestaoCustoPai

    with app.app_context():
        assert hasattr(GestaoCustoPai, 'obra_id'), (
            'gestao_custo_pai.obra_id não existe — o pai continua sem eixo '
            'de obra e a listagem depende da subquery de '
            'gestao_custos_views.py:122')


def test_gestao_custo_pai_obra_id_persiste_e_resolve_relationship():
    from models import GestaoCustoPai

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn',
            valor_total=100, status='PENDENTE', obra_id=o.id)
        db.session.add(pai)
        db.session.commit()
        pid, oid = pai.id, o.id

    with app.app_context():
        recarregado = db.session.get(GestaoCustoPai, pid)
        assert recarregado.obra_id == oid
        assert recarregado.obra is not None
        assert recarregado.obra.id == oid


def test_gestao_custo_pai_obra_id_e_nullable_de_proposito():
    """Multi-obra e administrativo são legítimos — ver
    utils/financeiro_integration.py:118-131, que agrupa o pai por
    (admin, categoria, entidade) SEM obra."""
    from models import GestaoCustoPai

    with app.app_context():
        a = _admin()
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='Escritorio',
            valor_total=50, status='PENDENTE')
        db.session.add(pai)
        db.session.commit()
        assert pai.obra_id is None
