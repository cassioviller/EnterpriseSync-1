"""`atualizar_percentual_tarefa` não pode apagar o que não sabe recalcular.

Achado ao executar o plano `2026-08-20-rdo-efetivo-terceiros.md` (Task 4):
registrar efetivo de terceiro (11 pessoas, 0 produzido) numa tarefa em 40%
levava a tarefa para 0%.

Causa: o percentual é DERIVADO do último `RDOApontamentoCronograma` mais a
produção da subempreitada. Quando os 40% vieram da **carga inicial** do MS
Project (`pct_project`, gravado direto em `percentual_concluido` quando a obra
nunca teve RDO — `services/cronograma_versao_service.py:615-622`), não existe
apontamento nenhum: a derivação dá 0 e sobrescreve o valor importado.

O bug é anterior a este plano — só não aparecia porque o front desenhava o
botão de apontamento de subempreitada apenas em tarefas
`responsavel='subempreitada'`.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (RDO, RDOSubempreitadaApontamento, Subempreiteiro,
                    TarefaCronograma)
from test_cronograma_versao_service import _ambiente, _rdo_com_apontamento, _tarefa
from utils.cronograma_engine import atualizar_percentual_tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-percentual-carga-inicial'
    with app.app_context():
        yield


def _rdo_vazio(obra, admin):
    """RDO sem apontamento de empresa — só o continente do registro da sub."""
    rdo = RDO(numero_rdo=f'RDO-CI-{admin.id}', data_relatorio=date(2026, 7, 5),
              obra_id=obra.id, admin_id=admin.id, estado='preenchido')
    db.session.add(rdo)
    db.session.flush()
    return rdo


def _tarefa_quantitativa(obra, admin, pct):
    return _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=10,
                   data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10),
                   quantidade_total=100.0, unidade_medida='m3',
                   responsavel='empresa', percentual_concluido=pct)


def test_sem_apontamento_preserva_a_carga_inicial():
    """40% importado do MS Project, obra sem RDO: recalcular não pode zerar."""
    admin, obra = _ambiente()
    t = _tarefa_quantitativa(obra, admin, 40.0)

    atualizar_percentual_tarefa(t.id, admin.id)

    assert TarefaCronograma.query.get(t.id).percentual_concluido == pytest.approx(40.0)


def test_sem_apontamento_e_sem_carga_inicial_continua_zero():
    """Preservar o valor existente não inventa avanço onde não havia."""
    admin, obra = _ambiente()
    t = _tarefa_quantitativa(obra, admin, 0.0)

    atualizar_percentual_tarefa(t.id, admin.id)

    assert TarefaCronograma.query.get(t.id).percentual_concluido == pytest.approx(0.0)


def test_apontamento_de_efetivo_de_terceiro_nao_apaga_a_carga_inicial():
    """Efetivo puro (0 produzido) é presença, não produção: não move o avanço.

    Este é o caso do Abraão na fundação — o que motivou o achado.
    """
    admin, obra = _ambiente()
    t = _tarefa_quantitativa(obra, admin, 40.0)
    sub = Subempreiteiro(nome='Abraão', admin_id=admin.id, ativo=True)
    db.session.add(sub)
    db.session.flush()
    db.session.add(RDOSubempreitadaApontamento(
        rdo_id=_rdo_vazio(obra, admin).id, admin_id=admin.id,
        tarefa_cronograma_id=t.id, subempreiteiro_id=sub.id,
        qtd_pessoas=11, horas_trabalhadas=8.8, quantidade_produzida=0.0))
    db.session.commit()

    atualizar_percentual_tarefa(t.id, admin.id)

    assert TarefaCronograma.query.get(t.id).percentual_concluido == pytest.approx(40.0)


def test_apontamento_da_empresa_continua_mandando_no_percentual():
    """A derivação não pode virar 'nunca escreve': com apontamento, ela manda."""
    admin, obra = _ambiente()
    t = _tarefa_quantitativa(obra, admin, 40.0)
    _rdo_com_apontamento(obra, admin, t, acumulada=55.0, pct=55.0)

    atualizar_percentual_tarefa(t.id, admin.id)

    assert TarefaCronograma.query.get(t.id).percentual_concluido == pytest.approx(55.0)


def test_producao_da_subempreitada_continua_somando():
    """Produção de terceiro (não efetivo) segue convertida pelo total."""
    admin, obra = _ambiente()
    t = _tarefa_quantitativa(obra, admin, 0.0)
    sub = Subempreiteiro(nome='Abraão', admin_id=admin.id, ativo=True)
    db.session.add(sub)
    db.session.flush()
    db.session.add(RDOSubempreitadaApontamento(
        rdo_id=_rdo_vazio(obra, admin).id, admin_id=admin.id,
        tarefa_cronograma_id=t.id, subempreiteiro_id=sub.id,
        qtd_pessoas=11, horas_trabalhadas=8.8, quantidade_produzida=30.0))
    db.session.commit()

    atualizar_percentual_tarefa(t.id, admin.id)

    # 30 de 100 m³ = 30%
    assert TarefaCronograma.query.get(t.id).percentual_concluido == pytest.approx(30.0)
