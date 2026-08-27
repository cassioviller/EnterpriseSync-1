"""Onda 3 — a ressalva para de zerar todas as parcelas (Task 7).

`services/financeiro_compra.py` tinha três defeitos correlatos em torno de
`liberar()` e do lote (`fechar_lote`/`reabrir_lote`):

1. `:433` — a rewrite proporcional rodava mesmo com `atestado == 0`, o que é
   justamente o caso da ressalva D6 (liberar SEM atesto). Toda parcela virava
   R$ 0,00.
2. `:420` — `liberar()` seleciona `ContaPagar` só por `pedido_compra_id`, sem
   filtrar `fechamento_id`: fechar um lote com a parcela 1 de 3 liberava as
   2 e 3, que nunca estiveram em lote fechado.
3. `:566` — `reabrir_lote` volta o `status` do lote para 'ABERTO' mas não
   reverte a `situacao_liberacao` que `fechar_lote` pôs em 'liberada'.

Molde de fixtures: tests/test_onda3_valor_nao_duplica.py (cabeçalho e
fixture `_config`) e tests/test_nota_e_liberacao.py / test_fechamento_
pagamentos_rota.py (pedido do Fluxo A, lote).
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import um_tenant  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-compras'
    yield


# ---------------------------------------------------------------------------
# o cenário — pedido do Fluxo A (regime novo, exige atesto)
# ---------------------------------------------------------------------------

def _cfg_tenant(admin_id, **flags):
    from models import ConfiguracaoEmpresa
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin_id, nome_empresa=f'Tenant {admin_id}')
        db.session.add(cfg)
    for k, v in flags.items():
        setattr(cfg, k, v)
    db.session.commit()
    return cfg


def _fornecedor(admin_id):
    from models import Fornecedor
    f = Fornecedor(nome='Forn Teste', cnpj=uuid.uuid4().hex[:14],
                   admin_id=admin_id, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _pedido_fluxo_a(admin_id, obra_id, fornecedor_id, *, parcelas=1,
                    condicao='a_vista', valor_total=Decimal('1625.00')):
    """Pedido faturado que exige atesto — nasce com `ContaPagar` bloqueada."""
    from models import PedidoCompra, PedidoCompraItem
    p = PedidoCompra(
        numero=f'PC-{uuid.uuid4().hex[:6].upper()}',
        fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1),
        obra_id=obra_id, condicao_pagamento=condicao, parcelas=parcelas,
        valor_total=valor_total, tipo_compra='normal',
        processada_apos_aprovacao=False, admin_id=admin_id,
        exige_atesto=True, fluxo_pagamento='faturado')
    db.session.add(p)
    db.session.commit()
    db.session.add(PedidoCompraItem(
        pedido_id=p.id, descricao='Cimento CP-II', quantidade=Decimal('50'),
        preco_unitario=(valor_total / Decimal('50')), subtotal=valor_total,
        admin_id=admin_id))
    db.session.commit()
    return p


def _tenant_regime_novo(marca, *, parcelas=1, condicao='a_vista',
                        valor_total=Decimal('1625.00')):
    """Tenant com as duas flags ligadas + pedido do Fluxo A."""
    from models import Usuario
    t = um_tenant(marca, com_fatos=False)
    _cfg_tenant(t.admin_id, recebimento_atesto_ativo=True,
                financeiro_dois_fluxos_ativo=True)
    forn = _fornecedor(t.admin_id)
    ped = _pedido_fluxo_a(t.admin_id, t.obra_id, forn.id, parcelas=parcelas,
                          condicao=condicao, valor_total=valor_total)
    adm = db.session.get(Usuario, t.admin_id)
    return t, adm, ped


def _atestar(pedido, admin, qtd=Decimal('50')):
    from services.recebimento_pedido import registrar_recebimento
    from models import PedidoCompraItem
    item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()
    registrar_recebimento(pedido, usuario=admin, data=date(2026, 8, 10),
                          linhas=[(item.id, qtd)])
    db.session.commit()


def _notar(pedido, admin, valor):
    from services.financeiro_compra import lancar_nota
    lancar_nota(pedido, numero=uuid.uuid4().hex[:8], serie='1',
                valor_total=valor, data_emissao=date(2026, 8, 10),
                data_vencimento=date(2026, 9, 10), usuario=admin)
    db.session.commit()


def _lote_aberto(admin_id, contas, criado_por_id=None):
    from models import FechamentoPagamento
    f = FechamentoPagamento(
        data_fechamento=date.today(), descricao='Lote de teste', status='ABERTO',
        admin_id=admin_id, criado_por_id=criado_por_id,
        total_selecionado=sum(Decimal(str(c.valor_original or 0)) for c in contas))
    db.session.add(f)
    db.session.flush()
    for c in contas:
        c.fechamento_id = f.id
    db.session.commit()
    return f


# ---------------------------------------------------------------------------
# 3a — a ressalva sem atesto não zera a parcela ('atestado > 0' faltava)
# ---------------------------------------------------------------------------

def test_liberar_com_ressalva_nao_zera_a_parcela_sem_atesto():
    """🔴 `services/financeiro_compra.py:433` — sem a guarda `atestado > 0`.

    A ressalva do D6 existe para liberar pagamento SEM atesto (`compras_views.
    py:1580`); com `atestado == 0`, o rateio proporcional reescrevia a única
    parcela para R$ 0,00 (`saldo = 0 - valor_pago`) — a "conta de R$ 0,00 que
    desaparece de toda projeção de caixa" que o docstring de `criar_obrigacao`
    diz evitar.
    """
    from models import ContaPagar
    from services.financeiro_compra import criar_obrigacao, liberar

    with app.app_context():
        t, adm, ped = _tenant_regime_novo('onda3_ressalva')
        criar_obrigacao(ped)
        db.session.commit()
        _notar(ped, adm, Decimal('1625.00'))   # nota sim, atesto NÃO

        RESSALVA = 'Material ainda nao conferido no canteiro, nota ja chegou.'
        contas = liberar(ped, usuario=adm, justificativa=RESSALVA)
        db.session.commit()

        assert len(contas) == 1
        cp = ContaPagar.query.filter_by(
            admin_id=t.admin_id, pedido_compra_id=ped.id).first()
        assert cp.situacao_liberacao == 'liberada'
        assert cp.valor_original == Decimal('1625.00'), (
            f'a parcela foi reescrita para {cp.valor_original} com atestado 0 '
            '— o rateio proporcional não devia rodar sem atesto')
        assert cp.saldo == Decimal('1625.00'), (
            f'saldo virou {cp.saldo} — a conta desapareceria da projeção de '
            'caixa')


# ---------------------------------------------------------------------------
# 3b — fechar um lote com a parcela 1 de 3 não libera as outras duas
# ---------------------------------------------------------------------------

def test_fechar_lote_nao_libera_parcelas_fora_dele():
    """🔴 `services/financeiro_compra.py:420` — `liberar()` seleciona por
    `pedido_compra_id` sem filtrar `fechamento_id`. Fechar um lote com a
    parcela 1 de 3 liberava as 2 e 3, que nunca estiveram em lote fechado.
    """
    from models import ContaPagar
    from services.financeiro_compra import criar_obrigacao, fechar_lote

    with app.app_context():
        t, adm, ped = _tenant_regime_novo(
            'onda3_lote3', parcelas=3, condicao='parcelado',
            valor_total=Decimal('3000.00'))
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        _notar(ped, adm, Decimal('3000.00'))

        contas = ContaPagar.query.filter_by(
            admin_id=t.admin_id, pedido_compra_id=ped.id).order_by(
                ContaPagar.parcela_numero).all()
        assert len(contas) == 3, 'pré-condição: o pedido tem 3 parcelas'
        assert all(c.situacao_liberacao == 'bloqueada' for c in contas), (
            'pré-condição: as três nascem bloqueadas')

        # só a parcela 1 vai para o lote — 2 e 3 ficam de fora
        lote = _lote_aberto(t.admin_id, [contas[0]])
        fechar_lote(lote, usuario=adm)
        db.session.commit()

        parcela1_id, parcela2_id, parcela3_id = (c.id for c in contas)

    with app.app_context():
        p1 = db.session.get(ContaPagar, parcela1_id)
        p2 = db.session.get(ContaPagar, parcela2_id)
        p3 = db.session.get(ContaPagar, parcela3_id)
        assert p1.situacao_liberacao == 'liberada', (
            'a parcela do lote fechado devia ter sido liberada')
        assert p2.situacao_liberacao == 'bloqueada', (
            'a parcela 2 nunca esteve num lote fechado e foi liberada junto')
        assert p3.situacao_liberacao == 'bloqueada', (
            'a parcela 3 nunca esteve num lote fechado e foi liberada junto')


# ---------------------------------------------------------------------------
# 3c — reabrir o lote reverte a liberação que o fechamento concedeu
# ---------------------------------------------------------------------------

def test_reabrir_lote_reverte_a_situacao_de_liberacao():
    """🔴 `services/financeiro_compra.py:566` — `reabrir_lote` volta o
    `status` para 'ABERTO' mas deixava a `situacao_liberacao` em 'liberada'.
    """
    from models import ContaPagar
    from services.financeiro_compra import (criar_obrigacao, fechar_lote,
                                             reabrir_lote)

    with app.app_context():
        t, adm, ped = _tenant_regime_novo('onda3_reabre')
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        _notar(ped, adm, Decimal('1625.00'))

        conta = ContaPagar.query.filter_by(
            admin_id=t.admin_id, pedido_compra_id=ped.id).first()
        lote = _lote_aberto(t.admin_id, [conta])
        fechar_lote(lote, usuario=adm)
        db.session.commit()
        assert conta.situacao_liberacao == 'liberada', 'pré-condição'

        conta_id, lote_id, adm_id = conta.id, lote.id, adm.id

    with app.app_context():
        from models import FechamentoPagamento, Usuario
        lote = db.session.get(FechamentoPagamento, lote_id)
        adm = db.session.get(Usuario, adm_id)
        reabrir_lote(lote, usuario=adm)
        db.session.commit()

        conta = db.session.get(ContaPagar, conta_id)
        assert lote.status == 'ABERTO'
        assert conta.situacao_liberacao == 'bloqueada', (
            f'reabrir o lote voltou o status mas deixou a conta '
            f'{conta.situacao_liberacao!r} — a liberação sobrevive ao '
            'fechamento que a concedeu')
