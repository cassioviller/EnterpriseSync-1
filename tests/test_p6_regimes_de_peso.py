"""p6 — dois regimes de peso conviviam, e um deles não conseguia medir.

`calcular_percentual_item` **normaliza** os pesos (`peso / total_peso`), então
a medição sai correta em qualquer escala. Mas `gerar_medicao_quinzenal` exigia
soma **exatamente 100** e recusava a obra inteira.

Quem gravava o quê:

* **import físico-financeiro** — `peso = dias` da tarefa no .mpp
  (`importacao_fisico_financeiro.py:239`). Soma 47, 112, o que a obra tiver;
* **Task #102** (aprovação da proposta) — pesos somando 100 por construção;
* **cadastro manual** — a UI distribui 100 pontos e só bloqueia soma > 100.

Resultado: o import passava no cálculo e **quebrava na geração da medição**.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
                    TarefaCronograma)
from helpers_tenant import dois_tenants
from services.medicao_service import (calcular_percentual_item,
                                      gerar_medicao_quinzenal,
                                      validar_pesos_item)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p6'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('p6')
    return a


def _tarefa(t, nome, pct, duracao):
    tarefa = TarefaCronograma(
        obra_id=t.obra_id, admin_id=t.admin_id, nome_tarefa=nome,
        ordem=0, duracao_dias=duracao, percentual_concluido=pct,
        data_inicio=date(2026, 6, 1), data_fim=date(2026, 6, 10), ativa=True)
    db.session.add(tarefa)
    db.session.flush()
    return tarefa


def _item_com_pesos(t, pares):
    """`pares` = [(tarefa, peso)] — a escala do peso é o que este teste varia."""
    item = ItemMedicaoComercial(
        admin_id=t.admin_id, obra_id=t.obra_id, nome=f'Item {uuid4().hex[:6]}',
        valor_comercial=Decimal('10000'), status='PENDENTE')
    db.session.add(item)
    db.session.flush()
    for tarefa, peso in pares:
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=item.id, cronograma_tarefa_id=tarefa.id,
            admin_id=t.admin_id, peso=peso))
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# O cálculo sempre foi agnóstico à escala
# ---------------------------------------------------------------------------

def test_peso_em_dias_e_peso_em_pontos_dao_o_mesmo_percentual():
    """3 e 7 dias distribuem igual a 30 e 70 pontos — o cálculo normaliza."""
    t = _tenant()
    a = _tarefa(t, 'Fundação', 100, 3)
    b = _tarefa(t, 'Estrutura', 0, 7)

    em_dias = _item_com_pesos(t, [(a, 3), (b, 7)])
    em_pontos = _item_com_pesos(t, [(a, 30), (b, 70)])

    assert calcular_percentual_item(em_dias) == calcular_percentual_item(em_pontos)
    assert calcular_percentual_item(em_dias) == Decimal('30.00')


# ---------------------------------------------------------------------------
# O gate que recusava a obra inteira
# ---------------------------------------------------------------------------

def test_medicao_gera_com_peso_em_dias():
    """Era aqui que o import quebrava: soma 10, gate exigia 100."""
    t = _tenant()
    a = _tarefa(t, 'Fundação', 100, 3)
    b = _tarefa(t, 'Estrutura', 0, 7)
    _item_com_pesos(t, [(a, 3), (b, 7)])

    medicao, erro = gerar_medicao_quinzenal(t.obra_id, t.admin_id)
    assert erro is None, f'a geração recusou peso em dias: {erro}'
    assert medicao is not None


def test_peso_somando_100_continua_gerando():
    t = _tenant()
    a = _tarefa(t, 'Fundação', 50, 5)
    _item_com_pesos(t, [(a, 100)])

    medicao, erro = gerar_medicao_quinzenal(t.obra_id, t.admin_id)
    assert erro is None
    assert medicao is not None


def test_peso_zero_continua_recusando():
    """Sem peso não há como distribuir o avanço — este gate é o que sobra, e
    é o único que o cálculo realmente exige."""
    t = _tenant()
    a = _tarefa(t, 'Fundação', 100, 3)
    _item_com_pesos(t, [(a, 0)])

    medicao, erro = gerar_medicao_quinzenal(t.obra_id, t.admin_id)
    assert medicao is None
    assert erro is not None and 'ZERO' in erro


def test_a_convencao_de_100_continua_disponivel_para_a_ui():
    """`validar_pesos_item` não sumiu: a tela de cadastro manual continua
    pensando em distribuir 100 pontos. O que ela deixou de fazer é decidir se
    a medição pode ser gerada."""
    t = _tenant()
    a = _tarefa(t, 'Fundação', 100, 3)
    item_100 = _item_com_pesos(t, [(a, 100)])
    item_dias = _item_com_pesos(t, [(a, 3)])

    ok_100, total_100 = validar_pesos_item(item_100.id)
    ok_dias, total_dias = validar_pesos_item(item_dias.id)

    assert ok_100 is True and total_100 == Decimal('100')
    assert ok_dias is False and total_dias == Decimal('3')
