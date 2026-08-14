"""Financeiro em dois fluxos — fase 2 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md
Plano: docs/superpowers/plans/2026-08-14-plano-execucao-financeiro-dois-fluxos.md

A obrigação passa a nascer do que chegou, não do que foi pedido: no Fluxo A a
`ContaPagar` só é pagável com pedido + nota + atesto (a tríade), e no Fluxo B o
adiantamento fica numa lista de espera até o atesto baixá-lo.

Molde de tests/test_recebimento_atesto.py: fixtures locais, tenant por uuid4,
sem depender de seed.
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
from models import (Cliente, ContaPagar, Fornecedor, Obra, PedidoCompra,
                    PedidoCompraItem, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-financeiro-dois-fluxos'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'fin_{suf}', email=f'fin_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _fornecedor(admin_id):
    f = Fornecedor(nome='Forn Teste', cnpj=uuid.uuid4().hex[:14],
                   admin_id=admin_id, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _pedido(admin_id, obra_id, fornecedor_id):
    p = PedidoCompra(
        numero=f'PC-{uuid.uuid4().hex[:6].upper()}',
        fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1),
        obra_id=obra_id, condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1625.00'), tipo_compra='normal',
        processada_apos_aprovacao=False, admin_id=admin_id)
    db.session.add(p)
    db.session.commit()
    db.session.add(PedidoCompraItem(
        pedido_id=p.id, descricao='Cimento CP-II', quantidade=Decimal('50'),
        preco_unitario=Decimal('32.50'), subtotal=Decimal('1625.00'),
        admin_id=admin_id))
    db.session.commit()
    return p


# ---------------------------------------------------------------------------
# F1 — o esqueleto: modelos, constraints e os defaults do regime
# ---------------------------------------------------------------------------

def test_modelos_da_fase_existem():
    """As duas tabelas novas do spec são importáveis de `models`."""
    from models import AdiantamentoFornecedor, NotaFiscalPedido
    assert NotaFiscalPedido.__tablename__ == 'nota_fiscal_pedido'
    assert AdiantamentoFornecedor.__tablename__ == 'adiantamento_fornecedor'


def test_nota_do_pedido_aceita_chave_de_acesso_nula():
    """A diferença deliberada em relação à `NotaFiscal` legada.

    Lá `chave_acesso` é NOT NULL **e** UNIQUE global (models.py:2640) — herdar
    isso obrigaria a chave de 44 dígitos para poder pagar, e metade das compras
    de obra chega com recibo ou nota de serviço. Este teste existe para que
    ninguém "conserte" a coluna para NOT NULL sem ler o spec.
    """
    from models import NotaFiscalPedido
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        nf = NotaFiscalPedido(
            pedido_id=ped.id, admin_id=adm.id, fornecedor_id=forn.id,
            numero='1234', serie='1', chave_acesso=None,
            valor_total=Decimal('1625.00'), data_emissao=date(2026, 8, 5),
            data_vencimento=date(2026, 9, 5), lancada_por_id=adm.id)
        db.session.add(nf)
        db.session.commit()

        assert nf.id is not None
        assert nf.chave_acesso is None


def test_nota_duplicada_do_mesmo_fornecedor_recusa():
    """UNIQUE (admin_id, fornecedor_id, numero, serie) — a mesma nota não entra
    duas vezes, e é o que impede pagar o mesmo papel duas vezes."""
    from sqlalchemy.exc import IntegrityError
    from models import NotaFiscalPedido
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        def _nota():
            return NotaFiscalPedido(
                pedido_id=ped.id, admin_id=adm.id, fornecedor_id=forn.id,
                numero='9001', serie='1', valor_total=Decimal('100.00'),
                data_emissao=date(2026, 8, 5), data_vencimento=date(2026, 9, 5),
                lancada_por_id=adm.id)

        db.session.add(_nota())
        db.session.commit()

        db.session.add(_nota())
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_defaults_descrevem_o_registro_historico():
    """Pedido nasce `faturado`, conta nasce `liberada`.

    Qualquer outro default trancaria o parque no dia do deploy: toda conta que
    já existe é pagável hoje, e a migration não pode mudar isso.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        assert ped.fluxo_pagamento == 'faturado'

        cp = ContaPagar(
            fornecedor_id=forn.id, obra_id=obra.id, descricao='Conta de teste',
            valor_original=Decimal('1625.00'), saldo=Decimal('1625.00'),
            data_emissao=date(2026, 8, 1), data_vencimento=date(2026, 9, 1),
            admin_id=adm.id)
        db.session.add(cp)
        db.session.commit()

        assert cp.situacao_liberacao == 'liberada'
        assert cp.liberada_por_id is None
        assert cp.liberada_em is None


def test_fechamento_ganhou_a_trilha_que_faltava():
    """`FechamentoPagamento` já existia e não registrava quem fechou.

    Sem `fechado_por_id` não há segregação possível: a regra "quem montou o
    lote não fecha o lote" precisa saber quem foi.
    """
    from models import FechamentoPagamento
    cols = {c.name for c in FechamentoPagamento.__table__.columns}
    assert {'fechado_por_id', 'fechado_em', 'reaberto_por_id'} <= cols


def test_flag_e_tolerancia_nascem_na_configuracao():
    """A virada é por tenant, e a tolerância da D1 é dado, não constante."""
    from models import ConfiguracaoEmpresa
    cols = {c.name for c in ConfiguracaoEmpresa.__table__.columns}
    assert 'financeiro_dois_fluxos_ativo' in cols
    assert 'tolerancia_divergencia_nf_pct' in cols
