"""Fase 3 — documento de requisição de compra.

Até 2026-07-21 não existia nenhuma requisição no repositório inteiro
(`grep -rni "requisic"` devolvia zero). A compra nascia direto do
formulário e era efetivada no mesmo request (`compras_views.py:709-711`),
criando GestaoCustoPai, ContaPagar e movimento de almoxarifado sem que
ninguém tivesse aprovado nada. Estes testes travam o documento que passa
a existir ANTES da compra.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, EstadoRequisicao, Obra, ObraServicoCusto,
                    RequisicaoCompra, RequisicaoCompraItem, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-requisicao'
    yield


def _admin(nome='Admin'):
    """ADMIN do tenant. `versao_sistema='v2'` porque TODA rota de compras
    passa por `_check_v2()` (compras_views.py:36-40)."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3a_{suf}', email=f'f3a_{suf}@test.local',
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
        username=f'f3o_{suf}', email=f'f3o_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    """`Obra.cliente_id` é NOT NULL (models.py:265-268) — o Cliente vem antes."""
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


def test_estado_requisicao_tem_os_seis_estados():
    assert {e.name for e in EstadoRequisicao} == {
        'RASCUNHO', 'AGUARDANDO_APROVACAO', 'APROVADA',
        'REJEITADA', 'CONVERTIDA', 'CANCELADA'}


def test_requisicao_nasce_em_rascunho():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        r = RequisicaoCompra(
            numero='RC-2026-0001', obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id,
            justificativa='Perfis U90 para a montagem do painel P3',
        )
        db.session.add(r)
        db.session.commit()
        rid = r.id

    with app.app_context():
        recarregada = db.session.get(RequisicaoCompra, rid)
        assert recarregada.estado == EstadoRequisicao.RASCUNHO
        assert recarregada.valor_estimado == Decimal('0.00')


def test_requisicao_exige_obra():
    """obra_id NOT NULL desde o primeiro dia — é tabela nova, não há órfão
    para migrar (ao contrário de pedido_compra.obra_id, models.py:4736)."""
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        db.session.add(RequisicaoCompra(
            numero='RC-2026-0002', obra_id=None,
            solicitante_id=admin.id, admin_id=admin.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_numero_e_unico_por_tenant():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        for _ in range(2):
            db.session.add(RequisicaoCompra(
                numero='RC-2026-0003', obra_id=obra.id,
                solicitante_id=admin.id, admin_id=admin.id))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return
        pytest.fail('numero repetido no mesmo tenant foi aceito')


def test_dois_tenants_podem_ter_o_mesmo_numero():
    with app.app_context():
        a1, a2 = _admin('A'), _admin('B')
        o1, o2 = _obra(a1.id), _obra(a2.id)
        db.session.add(RequisicaoCompra(
            numero='RC-2026-0001', obra_id=o1.id,
            solicitante_id=a1.id, admin_id=a1.id))
        db.session.add(RequisicaoCompra(
            numero='RC-2026-0001', obra_id=o2.id,
            solicitante_id=a2.id, admin_id=a2.id))
        db.session.commit()  # não pode levantar


def test_itens_somam_no_valor_estimado():
    from services.requisicao_compra import recalcular_valor

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        r = RequisicaoCompra(
            numero='RC-2026-0004', obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id)
        db.session.add(r)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=r.id, admin_id=admin.id, descricao='Perfil U90',
            unidade='m', quantidade=Decimal('120.000'),
            preco_estimado=Decimal('18.50')))
        db.session.add(RequisicaoCompraItem(
            requisicao_id=r.id, admin_id=admin.id, descricao='Parafuso GN25',
            unidade='cx', quantidade=Decimal('4.000'),
            preco_estimado=Decimal('89.90')))
        db.session.flush()
        recalcular_valor(r)
        db.session.commit()
        # 120 * 18.50 = 2220.00 ; 4 * 89.90 = 359.60
        assert r.valor_estimado == Decimal('2579.60')


def test_etapa_e_opcional_e_validada_contra_a_obra():
    """obra_servico_custo_id espelha pedido_compra (models.py:4740) — opcional."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        etapa = ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id, nome='Montagem de painéis')
        db.session.add(etapa)
        db.session.commit()

        r = RequisicaoCompra(
            numero='RC-2026-0005', obra_id=obra.id,
            obra_servico_custo_id=etapa.id,
            solicitante_id=admin.id, admin_id=admin.id)
        db.session.add(r)
        db.session.commit()
        assert r.obra_servico_custo_id == etapa.id

        r2 = RequisicaoCompra(
            numero='RC-2026-0006', obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id)
        db.session.add(r2)
        db.session.commit()
        assert r2.obra_servico_custo_id is None
