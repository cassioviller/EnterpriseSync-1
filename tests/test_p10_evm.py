"""p10 — EVM por composição (a Fase 7 reescrita).

A Fase 7 do plano de 21/07 mandava construir `TarefaPredecessora`,
`utils/cpm.py`, `cronograma_cpm_service` e uma baseline própria. Três dias
depois o editor v2 entregou tudo isso. O que sobrou da fase é o EVM — e as
três séries dele já existiam vivas.

Os dois erros que este pacote existe para não cometer:

* **BAC não é `valor_contrato`.** Contrato é venda; EVM compara custo com
  custo. Venda como BAC daria CPI sempre favorável — o vício que o p3 fechou;
* **EV usa progresso FÍSICO, não financeiro.** Medir avanço pelo dinheiro
  gasto é medir esforço, não entrega, e faz o SPI mentir exatamente quando a
  obra atrasa gastando.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (GestaoCustoFilho, GestaoCustoPai, ObraServicoCusto,
                    ObraServicoCustoItem, TarefaCronograma)
from helpers_tenant import dois_tenants
from services.evm import calcular_evm

pytestmark = pytest.mark.integration

DATA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p10'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('evm', DATA)
    return a


def _custo_orcado(t, valor, linhas=()):
    osc = ObraServicoCusto(obra_id=t.obra_id, admin_id=t.admin_id,
                           nome=f'Serviço {uuid4().hex[:6]}',
                           valor_orcado=Decimal(str(valor)),
                           realizado_material=0, realizado_mao_obra=0,
                           realizado_outros=0)
    db.session.add(osc)
    db.session.flush()
    for v in linhas:
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=t.admin_id,
            descricao='linha', valor=Decimal(str(v))))
    db.session.commit()
    return osc


def _tarefa(t, pct, duracao=10):
    tarefa = TarefaCronograma(
        obra_id=t.obra_id, admin_id=t.admin_id,
        nome_tarefa=f'Tarefa {uuid4().hex[:6]}', ordem=0, duracao_dias=duracao,
        percentual_concluido=pct, ativa=True, is_cliente=False,
        data_inicio=DATA, data_fim=DATA)
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def _custo_realizado(t, valor, data=DATA):
    pai = GestaoCustoPai(tipo_categoria='MATERIAL', entidade_nome='Fornecedor',
                         admin_id=t.admin_id, obra_id=t.obra_id,
                         status='PENDENTE')
    db.session.add(pai)
    db.session.flush()
    db.session.add(GestaoCustoFilho(
        pai_id=pai.id, admin_id=t.admin_id, obra_id=t.obra_id,
        data_referencia=data, descricao='Compra', valor=Decimal(str(valor)),
        origem_tabela='compra', origem_id=0))
    db.session.commit()


# ---------------------------------------------------------------------------
# As grandezas
# ---------------------------------------------------------------------------

def test_obra_sem_custo_orcado_nao_inventa_evm():
    """Índice zero seria lido como desempenho nulo; `tem_dados=False` diz que
    não há base para calcular."""
    t = _tenant()
    evm = calcular_evm(t.obra_id, t.admin_id)
    assert evm['tem_dados'] is False
    assert evm['cpi'] is None and evm['spi'] is None


def test_bac_vem_do_custo_e_nao_do_contrato():
    """O contrato da obra semeada é 100.000; o custo orçado é 60.000."""
    t = _tenant()
    _custo_orcado(t, 100000, linhas=(60000,))

    evm = calcular_evm(t.obra_id, t.admin_id)
    assert evm['bac'] == 60000.0, (
        'BAC pegou venda em vez de custo — o vício que o p3 fechou')


def test_ev_e_progresso_fisico_vezes_bac():
    t = _tenant()
    _custo_orcado(t, 100000, linhas=(60000,))
    _tarefa(t, 50)

    evm = calcular_evm(t.obra_id, t.admin_id)
    assert evm['pct_fisico'] == 50.0
    assert evm['ev'] == 30000.0


def test_cpi_abaixo_de_um_quando_gasta_mais_do_que_entrega():
    """Entregou 30.000 em valor e gastou 40.000: CPI 0,75."""
    t = _tenant()
    _custo_orcado(t, 100000, linhas=(60000,))
    _tarefa(t, 50)
    _custo_realizado(t, 40000)

    evm = calcular_evm(t.obra_id, t.admin_id)
    assert evm['ac'] == 40000.0
    assert evm['cpi'] == pytest.approx(0.75, abs=0.001)
    assert evm['cv'] == pytest.approx(-10000.0, abs=0.01)


def test_eac_projeta_o_desperdicio_observado():
    """EAC = BAC / CPI: se o ritmo de desperdício continuar, a obra custa
    80.000 em vez dos 60.000 orçados."""
    t = _tenant()
    _custo_orcado(t, 100000, linhas=(60000,))
    _tarefa(t, 50)
    _custo_realizado(t, 40000)

    evm = calcular_evm(t.obra_id, t.admin_id)
    assert evm['eac'] == pytest.approx(80000.0, abs=0.01)
    assert evm['etc'] == pytest.approx(40000.0, abs=0.01)
    assert evm['vac'] == pytest.approx(-20000.0, abs=0.01)


def test_sem_custo_realizado_o_eac_e_o_proprio_orcamento():
    """Sem AC não há CPI — e a melhor projeção disponível é o orçamento."""
    t = _tenant()
    _custo_orcado(t, 100000, linhas=(60000,))
    _tarefa(t, 20)

    evm = calcular_evm(t.obra_id, t.admin_id)
    assert evm['cpi'] is None
    assert evm['eac'] == 60000.0


def test_o_evm_nao_atravessa_tenants():
    a, b = dois_tenants('evm2', DATA)
    osc = ObraServicoCusto(obra_id=b.obra_id, admin_id=b.admin_id,
                           nome='Do outro', valor_orcado=Decimal('50000'),
                           realizado_material=0, realizado_mao_obra=0,
                           realizado_outros=0)
    db.session.add(osc)
    db.session.commit()

    assert calcular_evm(a.obra_id, a.admin_id)['tem_dados'] is False


# ---------------------------------------------------------------------------
# A entrega: o painel serve o EVM
# ---------------------------------------------------------------------------

def test_o_painel_financeiro_expoe_a_chave_evm():
    """A chave é aditiva — quem já consome o painel não vê diferença."""
    from models import Obra
    from services.cronograma_fisico_financeiro import painel_financeiro

    t = _tenant()
    _custo_orcado(t, 100000, linhas=(60000,))
    _tarefa(t, 50)

    painel = painel_financeiro(db.session.get(Obra, t.obra_id))
    assert 'evm' in painel
    assert painel['evm']['bac'] == 60000.0
    assert painel['evm']['ev'] == 30000.0
    # o resto do painel continua lá
    assert 'kpis' in painel and 'curva_s' in painel and 'etapas' in painel
