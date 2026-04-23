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


if __name__ == '__main__':
    run()
