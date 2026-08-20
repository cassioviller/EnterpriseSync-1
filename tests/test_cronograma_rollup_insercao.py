"""Caracterização do rollup de percentual quando entram tarefas novas.

Cenário relatado na reunião de 2026-08-20: uma fase em ~98% recebe 5
tarefas novas zeradas e o percentual do grupo quase não se move. Este
módulo NÃO corrige — ele mede, para que a escolha da fórmula (ponderada
por duração x média simples por item) seja feita sobre número real.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TarefaCronograma
from services.cronograma_scheduler import recalcular_obra
from utils.cronograma_engine import calcular_data_fim, get_calendario
from test_cronograma_versao_service import (_ambiente, _rdo_com_apontamento,
                                            _tarefa)

pytestmark = pytest.mark.integration


def _fim(admin, inicio, duracao):
    """`data_fim` coerente com `duracao_dias` pelo calendário do tenant.

    `recalcular_obra` reescreve `duracao_dias` a partir do resultado do
    agendamento (`services/cronograma_scheduler.py`, bloco
    `if int(t.duracao_dias or 0) != int(r.duracao or 0)`), e o agendamento
    deriva a duração das DATAS. Uma folha com `data_inicio == data_fim` mas
    `duracao_dias=15` teria a duração colapsada para 1 no primeiro
    recálculo, destruindo o peso que este teste mede. Por isso data_fim é
    sempre derivada da duração com o mesmo helper que `cronograma_views.
    criar_tarefa` usa (`utils.cronograma_engine.calcular_data_fim`, linha
    ~686), em vez de fixada como no brief original.
    """
    cal = get_calendario(admin.id)
    return calcular_data_fim(inicio, duracao, cal.considerar_sabado,
                             cal.considerar_domingo)


def _folha(obra, admin, pai, nome, *, ordem, duracao, pct=None):
    """Folha sob `pai`. Com `pct`, ganha apontamento de RDO nesse percentual.

    Sem `quantidade_total`, o engine lê `percentual_realizado` do apontamento
    direto — sem passar pela divisão quantidade/total.
    """
    inicio = date(2026, 7, 1)
    t = _tarefa(obra, admin, nome, ordem=ordem,
                duracao_dias=duracao,
                data_inicio=inicio,
                data_fim=_fim(admin, inicio, duracao),
                tarefa_pai_id=pai.id)
    if pct is not None:
        _rdo_com_apontamento(obra, admin, t, acumulada=pct, pct=pct)
    return t


def _fase_com_filhas(pcts_e_duracoes):
    """Obra com um pai 'Primeira Fase' e uma folha por par (pct, duracao).

    `pct=None` = folha recém-inserida, sem apontamento — o engine a lê como 0.
    Devolve (admin_id, obra_id, pai_id).
    """
    with app.app_context():
        admin, obra = _ambiente()
        inicio = date(2026, 7, 1)
        pai = _tarefa(obra, admin, 'Primeira Fase', ordem=0,
                      duracao_dias=1, data_inicio=inicio,
                      data_fim=_fim(admin, inicio, 1))
        for i, (pct, dur) in enumerate(pcts_e_duracoes, start=1):
            _folha(obra, admin, pai, f'Item {i}',
                   ordem=i, duracao=dur, pct=pct)
        return admin.id, obra.id, pai.id


def _pct_do_pai(pai_id):
    with app.app_context():
        return TarefaCronograma.query.get(pai_id).percentual_concluido


def test_rollup_pondera_por_duracao_e_nao_por_contagem():
    """20 itens de 15 dias em 98% + 5 itens novos de 1 dia sem apontamento.

    Ponderado por duração: 98 * 300 / 305 = 96.39.
    Média simples por item seria 98 * 20 / 25 = 78.40.
    Este assert grava QUAL das duas está em vigor.
    """
    admin_id, obra_id, pai_id = _fase_com_filhas(
        [(98.0, 15)] * 20 + [(None, 1)] * 5)

    with app.app_context():
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)

    assert _pct_do_pai(pai_id) == pytest.approx(96.39, abs=0.01)


def test_rollup_roda_no_caminho_de_insercao():
    """Inserir uma folha sem apontamento num pai que estava em 100%.

    Prova que o rollup NÃO deixa de rodar na criação — a suspeita inicial
    da reunião. Duas folhas de 5 dias: uma em 100%, a nova em 0% ⇒ 50%.
    """
    admin_id, obra_id, pai_id = _fase_com_filhas([(100.0, 5)])

    with app.app_context():
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)
    assert _pct_do_pai(pai_id) == pytest.approx(100.0, abs=0.01)

    with app.app_context():
        # `ordem = max + 1` é o que o caminho "anexar no fim" de
        # `criar_tarefa` grava numa filha (cronograma_views.py:676).
        db.session.add(TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, nome_tarefa='Item novo',
            ordem=99, duracao_dias=5,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 5),
            tarefa_pai_id=pai_id, percentual_concluido=0.0, is_cliente=False))
        db.session.commit()
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)

    assert _pct_do_pai(pai_id) == pytest.approx(50.0, abs=0.01)
