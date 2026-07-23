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


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def _requisicao(admin_id, obra_id, solicitante_id, valor='1000.00'):
    from services.requisicao_compra import proximo_numero
    r = RequisicaoCompra(
        numero=proximo_numero(admin_id), obra_id=obra_id,
        solicitante_id=solicitante_id, admin_id=admin_id,
        valor_estimado=Decimal(valor),
        justificativa='Material da semana')
    db.session.add(r)
    db.session.commit()
    return r


def test_transicao_valida_grava_historico():
    from models import RequisicaoTransicao
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id, valor='2579.60')

        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, op,
                     motivo='enviada para aprovação')
        db.session.commit()

        assert r.estado == EstadoRequisicao.AGUARDANDO_APROVACAO
        t = RequisicaoTransicao.query.filter_by(requisicao_id=r.id).one()
        assert t.de_estado == EstadoRequisicao.RASCUNHO
        assert t.para_estado == EstadoRequisicao.AGUARDANDO_APROVACAO
        assert t.usuario_id == op.id
        # o valor no momento da transição é o dado que a auditoria precisa:
        # a requisição pode ser editada depois, e o histórico não pode mentir
        assert t.valor_no_momento == Decimal('2579.60')
        assert t.criado_em is not None


def test_transicao_invalida_e_recusada():
    from services.requisicao_compra import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        # RASCUNHO → CONVERTIDA pula a aprovação inteira
        with pytest.raises(TransicaoInvalida):
            transicionar(r, EstadoRequisicao.CONVERTIDA, op)
        db.session.rollback()


def test_estado_terminal_nao_transiciona():
    from services.requisicao_compra import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        transicionar(r, EstadoRequisicao.CANCELADA, op, motivo='desistiu')
        db.session.commit()
        with pytest.raises(TransicaoInvalida):
            transicionar(r, EstadoRequisicao.RASCUNHO, op)
        db.session.rollback()


def test_rejeitada_volta_para_rascunho():
    """Rejeitar não é matar: o solicitante corrige e reenvia. É o único
    caminho de volta de um estado de decisão."""
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, op)
        transicionar(r, EstadoRequisicao.REJEITADA, admin, motivo='sem verba')
        transicionar(r, EstadoRequisicao.RASCUNHO, op, motivo='corrigindo')
        db.session.commit()
        assert r.estado == EstadoRequisicao.RASCUNHO


def test_historico_fica_em_ordem_e_completo():
    from models import RequisicaoTransicao
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, op)
        transicionar(r, EstadoRequisicao.APROVADA, admin, motivo='ok')
        db.session.commit()

        trilha = (RequisicaoTransicao.query
                  .filter_by(requisicao_id=r.id)
                  .order_by(RequisicaoTransicao.id).all())
        assert [t.para_estado for t in trilha] == [
            EstadoRequisicao.AGUARDANDO_APROVACAO, EstadoRequisicao.APROVADA]
        assert [t.usuario_id for t in trilha] == [op.id, admin.id]


# ---------------------------------------------------------------------------
# Flag de rollout
# ---------------------------------------------------------------------------

def test_governanca_nasce_desligada():
    """Ligada por padrão, o deploy quebraria o registro de compra de todo
    mundo no mesmo minuto."""
    from scripts.flag_compras_governanca import governanca_ativa

    with app.app_context():
        admin = _admin()
        assert governanca_ativa(admin.id) is False


def test_governanca_liga_e_desliga():
    from scripts.flag_compras_governanca import definir_flag, governanca_ativa

    with app.app_context():
        admin = _admin()
        definir_flag(admin.id, True)
        assert governanca_ativa(admin.id) is True
        definir_flag(admin.id, False)
        assert governanca_ativa(admin.id) is False


def test_flag_ilegivel_e_tratada_como_desligada():
    """Falha para o lado do comportamento antigo, não para o lado de
    travar o registro de compra de uma empresa em obra."""
    from scripts.flag_compras_governanca import governanca_ativa

    with app.app_context():
        assert governanca_ativa(None) is False
        assert governanca_ativa(-1) is False


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@pytest.mark.parametrize('rota', [
    '/compras/requisicoes',
    '/compras/requisicoes/nova',
])
def test_rotas_de_requisicao_exigem_login(rota):
    anon = app.test_client()
    r = anon.get(rota, follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'{rota} devolveu {r.status_code} para anônimo')


def test_listagem_abre_para_admin():
    with app.app_context():
        admin = _admin()
        aid = admin.id
    r = _cliente_de(aid).get('/compras/requisicoes')
    assert r.status_code == 200


def test_criar_requisicao_gera_numero_e_itens():
    from models import RequisicaoCompraItem

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        aid, oid = admin.id, obra.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'justificativa': 'Perfis para o painel P3',
        'data_necessidade': '2026-08-15',
        'item_descricao[]': ['Perfil U90', 'Parafuso GN25'],
        'item_unidade[]': ['m', 'cx'],
        'item_quantidade[]': ['120', '4'],
        'item_preco[]': ['18,50', '89,90'],
        'item_almoxarifado_id[]': ['', ''],
    }, follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        assert req.numero.startswith('RC-')
        assert req.obra_id == oid
        assert req.estado == EstadoRequisicao.RASCUNHO
        assert req.valor_estimado == Decimal('2579.60')
        assert RequisicaoCompraItem.query.filter_by(
            requisicao_id=req.id).count() == 2


def test_requisicao_sem_obra_e_recusada():
    with app.app_context():
        admin = _admin()
        aid = admin.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': '',
        'justificativa': 'sem obra',
        'item_descricao[]': ['Qualquer'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['10'],
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=aid).count() == 0


def test_obra_de_outro_tenant_e_recusada():
    with app.app_context():
        a1, a2 = _admin('A'), _admin('B')
        obra_b = _obra(a2.id)
        aid, oid_b = a1.id, obra_b.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid_b),
        'justificativa': 'atravessando tenant',
        'item_descricao[]': ['X'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['10'],
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=aid).count() == 0


def test_detalhe_de_requisicao_de_outro_tenant_devolve_404():
    with app.app_context():
        a1, a2 = _admin('A'), _admin('B')
        obra_b = _obra(a2.id)
        req = RequisicaoCompra(numero='RC-2026-0001', obra_id=obra_b.id,
                               solicitante_id=a2.id, admin_id=a2.id)
        db.session.add(req)
        db.session.commit()
        aid, rid = a1.id, req.id

    r = _cliente_de(aid).get(f'/compras/requisicoes/{rid}')
    assert r.status_code == 404


def test_enviar_para_aprovacao_muda_o_estado():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        from services.requisicao_compra import proximo_numero
        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=op.id, admin_id=admin.id,
            valor_estimado=Decimal('100.00'))
        db.session.add(req)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=req.id, admin_id=admin.id, descricao='Item',
            quantidade=Decimal('1'), preco_estimado=Decimal('100.00')))
        db.session.commit()
        opid, rid = op.id, req.id

    r = _cliente_de(opid).post(f'/compras/requisicoes/{rid}/enviar',
                               follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).estado == \
            EstadoRequisicao.AGUARDANDO_APROVACAO


def test_requisicao_sem_item_nao_vai_para_aprovacao():
    """Requisição vazia aprovada é assinatura em branco."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        from services.requisicao_compra import proximo_numero
        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id,
            valor_estimado=Decimal('0.00'))
        db.session.add(req)
        db.session.commit()
        aid, rid = admin.id, req.id

    _cliente_de(aid).post(f'/compras/requisicoes/{rid}/enviar',
                          follow_redirects=False)
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).estado == \
            EstadoRequisicao.RASCUNHO
