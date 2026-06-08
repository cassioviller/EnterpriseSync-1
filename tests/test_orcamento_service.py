"""
tests/test_orcamento_service.py — Task #82

Valida o cálculo paramétrico do preço de venda do serviço a partir da
composição de insumos com imposto e margem de lucro.

Cenário canônico:
    - Insumo A: preço R$ 90,00/h    coef 0,463
    - Insumo B: preço R$ 50,00/un   coef 0,020
    - Insumo C: preço R$ 15,00/un   coef 1,000
    custo = 41,67 + 1,00 + 15,00 = 57,67
    imposto = 8% + lucro = 12% → divisor = 0,80
    preco = 57,67 / 0,80 = 72,09

Executa em transação isolada (rollback no fim) para não poluir o banco.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db
from models import (
    Servico, Insumo, PrecoBaseInsumo, ComposicaoServico, Usuario,
)
from services.orcamento_service import (
    calcular_precos_servico, recalcular_servico_preco,
)


def _pick_admin_id():
    u = Usuario.query.filter_by(tipo_usuario='ADMIN').first()
    if u is None:
        u = Usuario.query.first()
    if u is None:
        pytest.skip('Sem usuário admin no banco')
    return u.id


@pytest.fixture(scope='function')
def admin_id():
    """Pega o primeiro admin disponível e abre transação que será revertida."""
    with app.app_context():
        aid = _pick_admin_id()
        try:
            yield aid
        finally:
            db.session.rollback()


@pytest.fixture(scope='function')
def servico_canonico(admin_id):
    """Constroi o serviço com 3 insumos e composição canônica."""
    ins_a = Insumo(admin_id=admin_id, nome='__test_mao_obra', tipo='MAO_OBRA', unidade='h')
    ins_b = Insumo(admin_id=admin_id, nome='__test_solda', tipo='MATERIAL', unidade='un')
    ins_c = Insumo(admin_id=admin_id, nome='__test_consumivel', tipo='MATERIAL', unidade='un')
    db.session.add_all([ins_a, ins_b, ins_c])
    db.session.flush()
    db.session.add_all([
        PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_a.id, valor=90, vigencia_inicio=date(2020, 1, 1)),
        PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_b.id, valor=50, vigencia_inicio=date(2020, 1, 1)),
        PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_c.id, valor=15, vigencia_inicio=date(2020, 1, 1)),
    ])
    svc = Servico(
        admin_id=admin_id,
        nome='__test_svc_orcamento',
        categoria='Teste',
        unidade_medida='un',
        imposto_pct=8,
        margem_lucro_pct=12,
    )
    db.session.add(svc)
    db.session.flush()
    db.session.add_all([
        ComposicaoServico(admin_id=admin_id, servico_id=svc.id, insumo_id=ins_a.id, coeficiente='0.463'),
        ComposicaoServico(admin_id=admin_id, servico_id=svc.id, insumo_id=ins_b.id, coeficiente='0.020'),
        ComposicaoServico(admin_id=admin_id, servico_id=svc.id, insumo_id=ins_c.id, coeficiente='1.000'),
    ])
    db.session.flush()
    return svc


def test_calcular_precos_servico_canonico(servico_canonico):
    r = calcular_precos_servico(servico_canonico)
    assert str(r['custo_unitario']) == '57.67', f"custo esperado 57.67, obtido {r['custo_unitario']}"
    assert str(r['preco_venda']) == '72.09', f"preco esperado 72.09, obtido {r['preco_venda']}"
    assert len(r['detalhamento']) == 3
    assert r['erro'] is None


def test_calcular_precos_falha_quando_imposto_mais_lucro_excede_100(servico_canonico):
    servico_canonico.imposto_pct = 60
    servico_canonico.margem_lucro_pct = 50
    r = calcular_precos_servico(servico_canonico)
    assert r['erro'] is not None
    assert str(r['preco_venda']) == '0.00'


def test_calcular_precos_servico_sem_composicao(admin_id):
    """Edge case: serviço sem ComposicaoServico → custo=0, preco=0, sem erro."""
    svc = Servico(
        admin_id=admin_id, nome='__test_svc_vazio',
        categoria='Teste', unidade_medida='un',
        imposto_pct=8, margem_lucro_pct=12,
    )
    db.session.add(svc)
    db.session.flush()
    r = calcular_precos_servico(svc)
    assert str(r['custo_unitario']) == '0.00'
    assert str(r['preco_venda']) == '0.00'
    assert r['detalhes'] == []
    assert r['erro'] is None
    # split também deve ser 0
    assert str(r['custo_material']) == '0.00'
    assert str(r['custo_mao_obra']) == '0.00'


def test_calcular_precos_servico_sem_preco_vigente(admin_id):
    """Edge case: insumo sem PrecoBaseInsumo → preco_vigente=0 → custo=0."""
    ins = Insumo(admin_id=admin_id, nome='__test_sem_preco', tipo='MATERIAL', unidade='un')
    db.session.add(ins)
    db.session.flush()
    svc = Servico(
        admin_id=admin_id, nome='__test_svc_sem_preco',
        categoria='Teste', unidade_medida='un',
        imposto_pct=8, margem_lucro_pct=12,
    )
    db.session.add(svc)
    db.session.flush()
    db.session.add(ComposicaoServico(
        admin_id=admin_id, servico_id=svc.id, insumo_id=ins.id, coeficiente='2.0',
    ))
    db.session.flush()
    r = calcular_precos_servico(svc)
    assert str(r['custo_unitario']) == '0.00', f"sem preço vigente, custo deve ser 0; obtido {r['custo_unitario']}"
    assert str(r['preco_venda']) == '0.00'
    assert len(r['detalhes']) == 1
    assert r['detalhes'][0]['preco_unitario'] == 0
    assert r['detalhes'][0]['subtotal'] == 0
    assert r['erro'] is None


def test_recalcular_servico_persiste_preco(servico_canonico):
    servico_canonico.imposto_pct = 8
    servico_canonico.margem_lucro_pct = 12
    recalcular_servico_preco(servico_canonico)
    assert str(servico_canonico.preco_venda_unitario) == '72.09'


def test_recalcular_item_coeficiente_como_consumo_por_unidade(admin_id):
    """Task #163 — coeficiente é consumo por unidade do serviço.

    Cenário concreto descrito pelo usuário:
      - Drywall:  coef 0,347 placa/m² × R$ 50,00 × 10 m² = R$ 173,50
      - Mão obra: coef 0,500 h/m²    × R$ 15,00 × 10 m² = R$  75,00
      Custo total do item de 10 m² = R$ 248,50
    """
    from models import Orcamento, OrcamentoItem
    from services.orcamento_view_service import recalcular_item

    orc = Orcamento(
        admin_id=admin_id,
        numero='__t163-orc',
        titulo='Task #163 coeficiente test',
        cliente_nome='Cliente teste',
        criado_por=admin_id,
        status='rascunho',
        imposto_pct_global=Decimal('0'),
        margem_pct_global=Decimal('0'),
    )
    db.session.add(orc)
    db.session.flush()

    item = OrcamentoItem(
        admin_id=admin_id,
        orcamento_id=orc.id,
        ordem=1,
        descricao='Parede drywall',
        unidade='m2',
        quantidade=Decimal('10'),
        composicao_snapshot=[
            {
                'tipo': 'MATERIAL', 'insumo_id': None,
                'nome': 'Placa drywall',
                'unidade': 'placa',
                'coeficiente': 0.347,
                'preco_unitario': 50.0,
                'subtotal_unitario': 0.0,
            },
            {
                'tipo': 'MAO_OBRA', 'insumo_id': None,
                'nome': 'Hora homem',
                'unidade': 'h',
                'coeficiente': 0.5,
                'preco_unitario': 15.0,
                'subtotal_unitario': 0.0,
            },
        ],
    )
    db.session.add(item)
    db.session.flush()

    r = recalcular_item(item, orc)
    assert r['erro'] is None
    # custo unitário do serviço = 0,347*50 + 0,5*15 = 17,35 + 7,50 = 24,85
    assert str(item.custo_unitario) == '24.8500'
    # custo total do item (10 m²) = 248,50; drywall sozinho = 173,50; MO = 75,00
    assert str(item.custo_total) == '248.50'
    assert float(Decimal('0.347') * Decimal('50') * Decimal('10')) == 173.5
    assert float(Decimal('0.5') * Decimal('15') * Decimal('10')) == 75.0


def test_subtotal_compra_com_fator_comercial(admin_id):
    """Task #46 — subtotal de compra usa nº de pacotes, não qtd_técnica total.

    Cenário canônico do bug:
      - Parafuso: coef=14.8148, qtd=100, fator=100, preço=R$46,00
      - qtd_tecnica = 1481.48
      - qtd_compra  = ceil(1481.48/100)*100 = 1500 (15 pacotes × 100 unidades)
      - subtotal CORRETO = 15 × 46 = R$ 690,00
      - subtotal ERRADO  = 1500 × 46 = R$ 69 000,00
    """
    from models import Orcamento, OrcamentoItem
    from services.orcamento_view_service import recalcular_item

    orc = Orcamento(
        admin_id=admin_id,
        numero='__t46-orc',
        titulo='Task #46 fator_comercial test',
        cliente_nome='Cliente teste',
        criado_por=admin_id,
        status='rascunho',
        imposto_pct_global=Decimal('0'),
        margem_pct_global=Decimal('0'),
    )
    db.session.add(orc)
    db.session.flush()

    item = OrcamentoItem(
        admin_id=admin_id,
        orcamento_id=orc.id,
        ordem=1,
        descricao='Fixação com parafuso',
        unidade='m2',
        quantidade=Decimal('100'),
        composicao_snapshot=[
            {
                'tipo': 'MATERIAL', 'insumo_id': None,
                'nome': 'Parafuso',
                'unidade': 'un',
                'coeficiente': 14.8148,
                'preco_unitario': 46.0,
                'subtotal_unitario': 0.0,
                'fator_comercial': 100,
                'unidade_comercial': 'pct',
            },
        ],
    )
    db.session.add(item)
    db.session.flush()

    r = recalcular_item(item, orc)
    assert r['erro'] is None

    snap = item.composicao_snapshot
    assert len(snap) == 1
    linha = snap[0]

    assert linha['quantidade_tecnica'] == pytest.approx(1481.48, rel=1e-3)
    assert linha['quantidade_compra'] == pytest.approx(1500.0, rel=1e-3)
    assert linha['subtotal_compra'] == pytest.approx(690.0, rel=1e-2), (
        f"subtotal_compra esperado ~690, obtido {linha['subtotal_compra']} "
        "(bug: multiplicar por qtd_compra=1500 em vez de nº pacotes=15)"
    )


def test_subtotal_compra_sem_fator_comercial_inalterado(admin_id):
    """Task #46 — itens sem embalagem (fator=1) devem continuar inalterados.

    Cenário: coef=2, qtd=10, fator=1, preço=R$5 → subtotal = 20 × 5 = R$100
    """
    from models import Orcamento, OrcamentoItem
    from services.orcamento_view_service import recalcular_item

    orc = Orcamento(
        admin_id=admin_id,
        numero='__t46-orc-nofator',
        titulo='Task #46 sem fator test',
        cliente_nome='Cliente teste',
        criado_por=admin_id,
        status='rascunho',
        imposto_pct_global=Decimal('0'),
        margem_pct_global=Decimal('0'),
    )
    db.session.add(orc)
    db.session.flush()

    item = OrcamentoItem(
        admin_id=admin_id,
        orcamento_id=orc.id,
        ordem=1,
        descricao='Material sem embalagem',
        unidade='m2',
        quantidade=Decimal('10'),
        composicao_snapshot=[
            {
                'tipo': 'MATERIAL', 'insumo_id': None,
                'nome': 'Tinta',
                'unidade': 'L',
                'coeficiente': 2.0,
                'preco_unitario': 5.0,
                'subtotal_unitario': 0.0,
                'fator_comercial': 1,
                'unidade_comercial': None,
            },
        ],
    )
    db.session.add(item)
    db.session.flush()

    r = recalcular_item(item, orc)
    assert r['erro'] is None

    linha = item.composicao_snapshot[0]
    assert linha['quantidade_tecnica'] == pytest.approx(20.0)
    assert linha['quantidade_compra'] == pytest.approx(20.0)
    assert linha['subtotal_compra'] == pytest.approx(100.0), (
        f"subtotal_compra esperado 100.0, obtido {linha['subtotal_compra']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Task #47 — calcular_precos_servico_por_quantidade
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def servico_com_fator(admin_id):
    """Serviço com 1 insumo em embalagem (barra de 6 m, R$60/barra, coef=1/m).

    Cálculo esperado para qtd=2 m:
        qtd_tecnica = 1 × 2 = 2 m
        pacotes     = ceil(2 / 6) = 1 barra
        qtd_compra  = 1 × 6 = 6 m
        custo_real  = 1 × R$60 = R$60
        custo_tecnico = 2 × (60/6) = 2 × 10 = R$20 (proporcional)

    Cálculo esperado para qtd=7 m:
        qtd_tecnica = 7 m
        pacotes     = ceil(7/6) = 2 barras
        qtd_compra  = 12 m
        custo_real  = 2 × R$60 = R$120
    """
    ins = Insumo(
        admin_id=admin_id,
        nome='__test_barra_aco',
        tipo='MATERIAL',
        unidade='m',
        fator_comercial=Decimal('6'),
        unidade_comercial='barra',
    )
    db.session.add(ins)
    db.session.flush()
    db.session.add(PrecoBaseInsumo(
        admin_id=admin_id, insumo_id=ins.id,
        valor=60, vigencia_inicio=date(2020, 1, 1),
    ))
    svc = Servico(
        admin_id=admin_id,
        nome='__test_svc_fator',
        categoria='Teste',
        unidade_medida='m',
        imposto_pct=0,
        margem_lucro_pct=0,
    )
    db.session.add(svc)
    db.session.flush()
    db.session.add(ComposicaoServico(
        admin_id=admin_id, servico_id=svc.id,
        insumo_id=ins.id, coeficiente='1.0',
    ))
    db.session.flush()
    return svc


def test_calcular_por_quantidade_fator1_igual_proporcional(admin_id):
    """Task #47 — fator=1: cálculo real = cálculo técnico proporcional."""
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    ins = Insumo(
        admin_id=admin_id, nome='__test_t47_tinta',
        tipo='MATERIAL', unidade='L', fator_comercial=Decimal('1'),
    )
    db.session.add(ins)
    db.session.flush()
    db.session.add(PrecoBaseInsumo(
        admin_id=admin_id, insumo_id=ins.id,
        valor=10, vigencia_inicio=date(2020, 1, 1),
    ))
    svc = Servico(
        admin_id=admin_id, nome='__test_svc_t47_fator1',
        categoria='Teste', unidade_medida='m2',
        imposto_pct=0, margem_lucro_pct=0,
    )
    db.session.add(svc)
    db.session.flush()
    db.session.add(ComposicaoServico(
        admin_id=admin_id, servico_id=svc.id,
        insumo_id=ins.id, coeficiente='2.0',
    ))
    db.session.flush()

    r = calcular_precos_servico_por_quantidade(svc, Decimal('5'))
    assert r['erro'] is None
    assert r['quantidade'] == Decimal('5')
    assert not r['quantidade_fallback']
    # fator=1 → custo_real = coef × qtd × preço = 2 × 5 × 10 = 100
    assert float(r['custo_real_total']) == pytest.approx(100.0, rel=1e-4)
    # custo_medio = 100 / 5 = 20
    assert float(r['custo_medio_real_unitario']) == pytest.approx(20.0, rel=1e-4)
    # sem imposto/margem → preco_venda_total = custo_real = 100
    assert float(r['preco_venda_total']) == pytest.approx(100.0, rel=1e-2)
    assert float(r['preco_venda_medio']) == pytest.approx(20.0, rel=1e-4)
    d = r['detalhamento'][0]
    assert d['pacotes'] == pytest.approx(10.0)  # 10 L técnicos = 10 pacotes de 1 L
    assert d['quantidade_compra'] == pytest.approx(10.0)
    assert d['custo_real'] == pytest.approx(100.0, rel=1e-4)


def test_calcular_por_quantidade_compra_1_barra(servico_com_fator):
    """Task #47 — fator=6 (barra 6 m): 2 m → 1 barra → custo real = R$60."""
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    r = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('2'))
    assert r['erro'] is None
    d = r['detalhamento'][0]
    assert d['quantidade_tecnica'] == pytest.approx(2.0)
    assert d['pacotes'] == pytest.approx(1.0), 'deve comprar 1 barra (6 m) para 2 m técnicos'
    assert d['quantidade_compra'] == pytest.approx(6.0)
    assert d['custo_real'] == pytest.approx(60.0), 'custo real = 1 barra × R$60'
    assert float(r['custo_real_total']) == pytest.approx(60.0)
    assert float(r['custo_medio_real_unitario']) == pytest.approx(30.0)  # 60/2


def test_calcular_por_quantidade_compra_2_barras(servico_com_fator):
    """Task #47 — fator=6 (barra 6 m): 7 m → ceil(7/6)=2 barras → custo R$120."""
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    r = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('7'))
    assert r['erro'] is None
    d = r['detalhamento'][0]
    assert d['quantidade_tecnica'] == pytest.approx(7.0)
    assert d['pacotes'] == pytest.approx(2.0), 'deve comprar 2 barras para 7 m técnicos'
    assert d['quantidade_compra'] == pytest.approx(12.0)
    assert d['custo_real'] == pytest.approx(120.0), 'custo real = 2 barras × R$60'
    assert float(r['custo_real_total']) == pytest.approx(120.0)
    assert float(r['custo_medio_real_unitario']) == pytest.approx(
        120.0 / 7.0, rel=1e-3
    )


def test_calcular_por_quantidade_custo_tecnico_referencia(servico_com_fator):
    """Task #47 — custo_tecnico_unitario preservado como referência proporcional."""
    from services.orcamento_service import (
        calcular_precos_servico_por_quantidade, calcular_precos_servico,
    )

    r = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('2'))
    r_tec = calcular_precos_servico(servico_com_fator)
    # custo técnico unitário: coef × (60/6) = 1 × 10 = R$10
    assert float(r['custo_tecnico_unitario']) == pytest.approx(
        float(r_tec['custo_unitario']), rel=1e-3
    )
    # custo real total é MAIOR que técnico para qtd=2 (compra 6m, usa 2m)
    assert float(r['custo_real_total']) > float(r['custo_tecnico_unitario'])


def test_calcular_por_quantidade_preco_venda_com_markup(servico_com_fator):
    """Task #47 — preço de venda correto com imposto+margem para qtd=2 m.

    custo_real = R$60, imposto=8%, margem=12%, divisor=0.80
    preco_venda_total = 60 / 0.80 = R$75.00
    preco_venda_medio = 75 / 2 = R$37.50
    """
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    servico_com_fator.imposto_pct = 8
    servico_com_fator.margem_lucro_pct = 12

    r = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('2'))
    assert r['erro'] is None
    assert float(r['preco_venda_total']) == pytest.approx(75.0, rel=1e-3)
    assert float(r['preco_venda_medio']) == pytest.approx(37.5, rel=1e-3)


def test_calcular_por_quantidade_zero_usa_fallback(servico_com_fator):
    """Task #47 — quantidade 0 ou negativa usa qtd=1 e sinaliza quantidade_fallback."""
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    r0 = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('0'))
    assert r0['quantidade_fallback'] is True
    assert r0['quantidade'] == Decimal('1')

    r_neg = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('-5'))
    assert r_neg['quantidade_fallback'] is True


def test_calcular_por_quantidade_imposto_mais_margem_100(servico_com_fator):
    """Task #47 — imposto+margem >= 100% sinaliza erro sem crashar."""
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    servico_com_fator.imposto_pct = 60
    servico_com_fator.margem_lucro_pct = 50

    r = calcular_precos_servico_por_quantidade(servico_com_fator, Decimal('2'))
    assert r['erro'] is not None
    assert float(r['preco_venda_total']) == 0.0


def test_calcular_por_quantidade_escala_linear_sem_fator(admin_id):
    """Task #47 — sem fator, custo_real escala linearmente com a quantidade."""
    from services.orcamento_service import calcular_precos_servico_por_quantidade

    ins = Insumo(
        admin_id=admin_id, nome='__test_t47_escala',
        tipo='MATERIAL', unidade='L', fator_comercial=Decimal('1'),
    )
    db.session.add(ins)
    db.session.flush()
    db.session.add(PrecoBaseInsumo(
        admin_id=admin_id, insumo_id=ins.id,
        valor=20, vigencia_inicio=date(2020, 1, 1),
    ))
    svc = Servico(
        admin_id=admin_id, nome='__test_svc_t47_escala',
        categoria='Teste', unidade_medida='un',
        imposto_pct=0, margem_lucro_pct=0,
    )
    db.session.add(svc)
    db.session.flush()
    db.session.add(ComposicaoServico(
        admin_id=admin_id, servico_id=svc.id,
        insumo_id=ins.id, coeficiente='3.0',
    ))
    db.session.flush()

    r1 = calcular_precos_servico_por_quantidade(svc, Decimal('1'))
    r10 = calcular_precos_servico_por_quantidade(svc, Decimal('10'))
    # sem fator: custo real deve escalar linearmente
    assert float(r10['custo_real_total']) == pytest.approx(
        float(r1['custo_real_total']) * 10, rel=1e-4
    )
    # custo médio unitário deve ser igual independente da quantidade
    assert float(r10['custo_medio_real_unitario']) == pytest.approx(
        float(r1['custo_medio_real_unitario']), rel=1e-4
    )


# Permite rodar como script para CI legacy (`python tests/test_orcamento_service.py`)
def run():
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        aid = u.id if u else 1
        try:
            ins_a = Insumo(admin_id=aid, nome='__test_mao_obra', tipo='MAO_OBRA', unidade='h')
            ins_b = Insumo(admin_id=aid, nome='__test_solda', tipo='MATERIAL', unidade='un')
            ins_c = Insumo(admin_id=aid, nome='__test_consumivel', tipo='MATERIAL', unidade='un')
            db.session.add_all([ins_a, ins_b, ins_c])
            db.session.flush()
            db.session.add_all([
                PrecoBaseInsumo(admin_id=aid, insumo_id=ins_a.id, valor=90, vigencia_inicio=date(2020, 1, 1)),
                PrecoBaseInsumo(admin_id=aid, insumo_id=ins_b.id, valor=50, vigencia_inicio=date(2020, 1, 1)),
                PrecoBaseInsumo(admin_id=aid, insumo_id=ins_c.id, valor=15, vigencia_inicio=date(2020, 1, 1)),
            ])
            svc = Servico(
                admin_id=aid, nome='__test_svc_orcamento', categoria='Teste',
                unidade_medida='un', imposto_pct=8, margem_lucro_pct=12,
            )
            db.session.add(svc)
            db.session.flush()
            db.session.add_all([
                ComposicaoServico(admin_id=aid, servico_id=svc.id, insumo_id=ins_a.id, coeficiente='0.463'),
                ComposicaoServico(admin_id=aid, servico_id=svc.id, insumo_id=ins_b.id, coeficiente='0.020'),
                ComposicaoServico(admin_id=aid, servico_id=svc.id, insumo_id=ins_c.id, coeficiente='1.000'),
            ])
            db.session.flush()
            r = calcular_precos_servico(svc)
            assert str(r['custo_unitario']) == '57.67'
            assert str(r['preco_venda']) == '72.09'
            print('OK — orcamento_service: custo=57.67, preco=72.09 (8%+12%)')
        finally:
            db.session.rollback()


# ---------------------------------------------------------------------------
# Bloco 3 — P5: guarda-corpo nas camadas de escrita.
# ---------------------------------------------------------------------------

def test_recalcular_nao_persiste_preco_em_bloqueio(servico_canonico):
    """T+L ≥ bloqueio (default 90) → status='bloqueio'; o preço de venda
    persistido NÃO é sobrescrito."""
    servico_canonico.preco_venda_unitario = Decimal('99.99')
    db.session.flush()
    servico_canonico.imposto_pct = 50
    servico_canonico.margem_lucro_pct = 45   # T+L = 95

    r = recalcular_servico_preco(servico_canonico, persistir=True)

    assert r['status'] == 'bloqueio'
    assert str(r['preco_venda']) == '0.00'
    # preço intacto — não gravou 0 nem recalculou
    assert str(servico_canonico.preco_venda_unitario) == '99.99'


def test_recalcular_persiste_preco_em_aviso(servico_canonico):
    """aviso ≤ T+L < bloqueio → calcula e PERSISTE normalmente, sinalizando."""
    servico_canonico.imposto_pct = 40
    servico_canonico.margem_lucro_pct = 25   # T+L = 65 (faixa de aviso)

    r = recalcular_servico_preco(servico_canonico, persistir=True)

    assert r['status'] == 'aviso'
    assert r['mensagem']
    assert Decimal(str(r['preco_venda'])) > 0
    assert servico_canonico.preco_venda_unitario == r['preco_venda']


if __name__ == '__main__':
    run()
