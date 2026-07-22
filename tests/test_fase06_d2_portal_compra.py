"""Fase 0.6 / D2 — o POST anônimo do portal aprovava compra fora de escopo.

`aprovar_compra` e `recusar_compra` (`portal_obras_views.py:343,377`) são
anônimas por desenho: a identidade é o token da obra na URL. O problema não
era a autenticação — era a **ausência de precondição**. A query de ambas
filtrava só `id` e `obra_id`, e a escrita do novo status era incondicional.

Medido por execução em 2026-07-21, antes da correção:

| POST em                        | Resultado                                        |
|--------------------------------|--------------------------------------------------|
| `tipo_compra='normal'`         | `status='APROVADO'`, sem custo                    |
| compra já `RECUSADO`           | `APROVADO`, `processada=True`, GestaoCustoPai PAGO |

Duas consequências distintas:

1. **Compra interna vaza no portal.** `tipo_compra='normal'` nunca é oferecida
   ao cliente — a listagem de pendentes filtra `tipo_compra ==
   'aprovacao_cliente'` (`:165`). Mas `compras_resolvidas` (`:177`) filtra só
   por `status_aprovacao_cliente in ('APROVADO','RECUSADO')`, sem tipo: uma vez
   carimbada, a compra interna passa a aparecer para o cliente.
2. **Recusa é reversível por quem não deveria.** Uma compra que o cliente
   recusou voltava a APROVADO e aí sim era processada:
   `processar_compra_aprovada_cliente` cria `GestaoCustoPai` com
   `status='PAGO'` e movimenta o almoxarifado (`compras_views.py:275-366`).

Correção: as duas rotas passam a usar o mesmo padrão que as rotas de **mapa**
do próprio arquivo (`:432`, `:546`) já usavam — escopo de tenant na query,
filtro pelo que o portal de fato oferece, e transição de estado explícita.

Nota de procedência: o `ESTADO-ATUAL.md` afirmava que `tipo_compra='normal'`
criava custo PAGO. Não cria — `compras_views.py:296-300` levanta `ValueError`
para tipo diferente de `aprovacao_cliente`, e a rota nem chega lá (`:358`).
O caminho que cria custo indevido é o da compra **recusada**.
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
from models import (Cliente, Fornecedor, GestaoCustoPai, Obra, PedidoCompra,
                    TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase06-d2'
    yield


@pytest.fixture
def cenario():
    """Um tenant, uma obra com portal ligado, um fornecedor."""
    with app.app_context():
        s = uuid.uuid4().hex[:8]
        admin = Usuario(
            username=f'd2_{s}', email=f'd2_{s}@test.local', nome=f'Admin {s}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True,
        )
        db.session.add(admin)
        db.session.commit()
        cliente = Cliente(nome=f'Cliente {s}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(
            nome=f'Obra {s}', admin_id=admin.id, cliente_id=cliente.id,
            data_inicio=date(2026, 7, 1), token_cliente=f'tok-d2-{s}',
            portal_ativo=True,
        )
        db.session.add(obra)
        db.session.commit()
        fornecedor = Fornecedor(
            nome=f'Fornecedor {s}',
            cnpj=f'{uuid.uuid4().int % 10 ** 14:014d}', admin_id=admin.id,
        )
        db.session.add(fornecedor)
        db.session.commit()
        yield {
            'admin_id': admin.id, 'obra_id': obra.id,
            'token': obra.token_cliente, 'fornecedor_id': fornecedor.id,
        }


def _pedido(cenario, tipo, status):
    p = PedidoCompra(
        admin_id=cenario['admin_id'], obra_id=cenario['obra_id'],
        fornecedor_id=cenario['fornecedor_id'], tipo_compra=tipo,
        status_aprovacao_cliente=status, valor_total=1000.0,
        data_compra=date(2026, 7, 1),
    )
    db.session.add(p)
    db.session.commit()
    return p


def _anonimo():
    return app.test_client()


# ---------------------------------------------------------------------------
# O que o portal NÃO oferece, ele não aceita
# ---------------------------------------------------------------------------

def test_aprovar_compra_interna_e_404(cenario):
    """`tipo_compra='normal'` nunca aparece no portal — logo, não existe nele.

    404 e não 403: revelar que o id existe já é informação sobre a obra.
    """
    with app.app_context():
        pedido = _pedido(cenario, 'normal', None)

        r = _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{pedido.id}/aprovar")

        assert r.status_code == 404
        db.session.expire_all()
        assert db.session.get(PedidoCompra, pedido.id).status_aprovacao_cliente is None


def test_recusar_compra_interna_e_404(cenario):
    with app.app_context():
        pedido = _pedido(cenario, 'normal', None)

        r = _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{pedido.id}/recusar")

        assert r.status_code == 404
        db.session.expire_all()
        assert db.session.get(PedidoCompra, pedido.id).status_aprovacao_cliente is None


def test_compra_de_outro_tenant_no_mesmo_obra_id_e_404(cenario):
    """Escopo de tenant explícito, como as rotas de mapa já faziam (`:436`)."""
    with app.app_context():
        s = uuid.uuid4().hex[:8]
        outro = Usuario(
            username=f'd2b_{s}', email=f'd2b_{s}@test.local', nome='Outro',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True,
        )
        db.session.add(outro)
        db.session.commit()
        intruso = PedidoCompra(
            admin_id=outro.id, obra_id=cenario['obra_id'],
            fornecedor_id=cenario['fornecedor_id'],
            tipo_compra='aprovacao_cliente',
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE',
            valor_total=500.0, data_compra=date(2026, 7, 1),
        )
        db.session.add(intruso)
        db.session.commit()

        r = _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{intruso.id}/aprovar")

        assert r.status_code == 404
        db.session.expire_all()
        assert (db.session.get(PedidoCompra, intruso.id)
                .status_aprovacao_cliente == 'AGUARDANDO_APROVACAO_CLIENTE')


# ---------------------------------------------------------------------------
# A recusa do cliente não é reversível pelo próprio portal
# ---------------------------------------------------------------------------

def test_compra_recusada_nao_volta_a_aprovada_nem_gera_custo(cenario):
    """O caminho que criava custo indevido — o único que criava, de fato.

    Antes: `APROVADO`, `processada=True` e um `GestaoCustoPai` com
    `status='PAGO'` nascendo de um POST anônimo sobre algo que o cliente
    tinha recusado.
    """
    with app.app_context():
        pedido = _pedido(cenario, 'aprovacao_cliente', 'RECUSADO')
        antes = GestaoCustoPai.query.filter_by(admin_id=cenario['admin_id']).count()

        _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{pedido.id}/aprovar",
            follow_redirects=True)

        db.session.expire_all()
        p = db.session.get(PedidoCompra, pedido.id)
        assert p.status_aprovacao_cliente == 'RECUSADO'
        assert not p.processada_apos_aprovacao
        depois = GestaoCustoPai.query.filter_by(admin_id=cenario['admin_id']).count()
        assert depois == antes, 'custo criado a partir de compra recusada'


def test_compra_aprovada_e_processada_nao_volta_a_recusada(cenario):
    """Estornar uma compra já custeada é ação de gestor, não de portal."""
    with app.app_context():
        pedido = _pedido(cenario, 'aprovacao_cliente', 'APROVADO')
        pedido.processada_apos_aprovacao = True
        db.session.commit()

        _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{pedido.id}/recusar",
            follow_redirects=True)

        db.session.expire_all()
        assert (db.session.get(PedidoCompra, pedido.id)
                .status_aprovacao_cliente == 'APROVADO')


# ---------------------------------------------------------------------------
# O caminho legítimo continua funcionando
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status_inicial', [
    None, 'PENDENTE', 'AGUARDANDO_APROVACAO_CLIENTE',
])
def test_cliente_aprova_compra_pendente(cenario, status_inicial):
    with app.app_context():
        pedido = _pedido(cenario, 'aprovacao_cliente', status_inicial)

        _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{pedido.id}/aprovar",
            follow_redirects=True)

        db.session.expire_all()
        assert (db.session.get(PedidoCompra, pedido.id)
                .status_aprovacao_cliente == 'APROVADO')


@pytest.mark.parametrize('status_inicial', [
    None, 'PENDENTE', 'AGUARDANDO_APROVACAO_CLIENTE',
])
def test_cliente_recusa_compra_pendente(cenario, status_inicial):
    with app.app_context():
        pedido = _pedido(cenario, 'aprovacao_cliente', status_inicial)

        _anonimo().post(
            f"/portal/obra/{cenario['token']}/compra/{pedido.id}/recusar",
            follow_redirects=True)

        db.session.expire_all()
        assert (db.session.get(PedidoCompra, pedido.id)
                .status_aprovacao_cliente == 'RECUSADO')


def test_reaprovar_a_mesma_compra_e_idempotente(cenario):
    """Duplo clique do cliente não pode duplicar custo."""
    with app.app_context():
        pedido = _pedido(cenario, 'aprovacao_cliente', 'AGUARDANDO_APROVACAO_CLIENTE')
        url = f"/portal/obra/{cenario['token']}/compra/{pedido.id}/aprovar"

        _anonimo().post(url, follow_redirects=True)
        db.session.expire_all()
        custos_apos_1 = GestaoCustoPai.query.filter_by(
            admin_id=cenario['admin_id']).count()

        _anonimo().post(url, follow_redirects=True)
        db.session.expire_all()
        custos_apos_2 = GestaoCustoPai.query.filter_by(
            admin_id=cenario['admin_id']).count()

        assert custos_apos_2 == custos_apos_1
        assert (db.session.get(PedidoCompra, pedido.id)
                .status_aprovacao_cliente == 'APROVADO')
