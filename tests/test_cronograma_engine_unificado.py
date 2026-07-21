"""M06 — motor de cálculo unificado.

Parte 1 (Task 1): caracterização dos caminhos de progresso ANTES da
unificação — trava o comportamento vigente de:
  D — calcular_progresso_real_servico (último registro por subatividade, AVG);
  rollup de tarefas_rdo (pai = média ponderada por duração das filhas);
  _atualizar_percentual_com_subempreitada (qty empresa+sub / total).
O caminho B (FÓRMULA SIMPLES do KPI) é inline na view de detalhes da obra e
não é chamável isolado — ganha teste quando for extraído para o engine
(Task 3, `_progresso_fallback_subatividades`, mesma fórmula).

Partes seguintes (Tasks 2-5) acrescentam os testes da tabela normativa §12,
rollup/subempreitada/KPI no engine e convergência entre fontes.
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    RDO,
    RDOApontamentoCronograma,
    RDOServicoSubatividade,
    RDOSubempreitadaApontamento,
    Servico,
    Subempreiteiro,
    TarefaCronograma,
)
from test_cronograma_versao_service import _ambiente, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-engine-unificado'
    with app.app_context():
        yield


def _rdo(obra, admin, dia):
    r = RDO(
        numero_rdo=f'RDO-{uuid.uuid4().hex[:12]}',
        data_relatorio=dia,
        obra_id=obra.id,
        admin_id=admin.id,
    )
    db.session.add(r)
    db.session.flush()
    return r


def _apontar(rdo, tarefa, admin, qtd_dia, acumulada, pct):
    ap = RDOApontamentoCronograma(
        rdo_id=rdo.id,
        tarefa_cronograma_id=tarefa.id,
        quantidade_executada_dia=qtd_dia,
        quantidade_acumulada=acumulada,
        percentual_realizado=pct,
        admin_id=admin.id,
    )
    db.session.add(ap)
    db.session.flush()
    return ap


def _client_como(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# Caracterização D — progresso por serviço (views/obras.py:652)
# ---------------------------------------------------------------------------

def test_caracterizacao_progresso_real_servico_ultimo_de_cada_subatividade():
    """D usa o ÚLTIMO percentual de CADA subatividade (max id) e tira a
    média — contexto "por serviço", não progresso da obra."""
    from views.obras import calcular_progresso_real_servico

    admin, obra = _ambiente()
    servico = Servico(nome=f'Montagem {uuid.uuid4().hex[:6]}',
                      categoria='Estrutura', unidade_medida='m2',
                      admin_id=admin.id)
    db.session.add(servico)
    db.session.flush()

    r1 = _rdo(obra, admin, date(2026, 7, 10))
    r2 = _rdo(obra, admin, date(2026, 7, 11))
    for rdo, corte, solda in ((r1, 30.0, 20.0), (r2, 60.0, None)):
        db.session.add(RDOServicoSubatividade(
            rdo_id=rdo.id, servico_id=servico.id,
            nome_subatividade='Corte', percentual_conclusao=corte,
            admin_id=admin.id))
        if solda is not None:
            db.session.add(RDOServicoSubatividade(
                rdo_id=rdo.id, servico_id=servico.id,
                nome_subatividade='Solda', percentual_conclusao=solda,
                admin_id=admin.id))
    db.session.commit()

    # Corte: último = 60 (r2); Solda: último = 20 (r1) ⇒ média 40.
    assert calcular_progresso_real_servico(obra.id, servico.id) == 40.0


# ---------------------------------------------------------------------------
# Caracterização — rollup do endpoint tarefas_rdo (cronograma_views ~:919)
# ---------------------------------------------------------------------------

def test_caracterizacao_rollup_tarefas_rdo_pai_pondera_por_duracao():
    admin, obra = _ambiente()
    pai = _tarefa(obra, admin, 'Estrutura', ordem=0, duracao_dias=10)
    f1 = _tarefa(obra, admin, 'Fabricação', ordem=1, tarefa_pai_id=pai.id,
                 duracao_dias=2, quantidade_total=100.0, unidade_medida='m2',
                 data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 2))
    f2 = _tarefa(obra, admin, 'Montagem', ordem=2, tarefa_pai_id=pai.id,
                 duracao_dias=8, quantidade_total=100.0, unidade_medida='m2',
                 data_inicio=date(2026, 7, 3), data_fim=date(2026, 7, 14))
    r = _rdo(obra, admin, date(2026, 7, 10))
    _apontar(r, f1, admin, 50.0, 50.0, 50.0)     # f1: 50%
    _apontar(r, f2, admin, 100.0, 100.0, 100.0)  # f2: 100%
    db.session.commit()

    c = _client_como(admin.id)
    resp = c.get(f'/cronograma/obra/{obra.id}/tarefas-rdo?data=2026-07-10')
    assert resp.status_code == 200
    itens = {i['nome_tarefa']: i for i in resp.get_json()['tarefas']}
    assert itens['Fabricação']['percentual_realizado'] == 50.0
    assert itens['Montagem']['percentual_realizado'] == 100.0
    # Pai: (50*2 + 100*8) / 10 = 90.
    assert itens['Estrutura']['is_pai'] is True
    assert itens['Estrutura']['percentual_realizado'] == 90.0


# ---------------------------------------------------------------------------
# Caracterização — subempreitada (cronograma_views:1106)
# ---------------------------------------------------------------------------

def test_caracterizacao_subempreitada_soma_empresa_e_sub():
    from cronograma_views import _atualizar_percentual_com_subempreitada

    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Pintura', ordem=0,
                quantidade_total=100.0, unidade_medida='m2')
    sub = Subempreiteiro(nome=f'Sub {uuid.uuid4().hex[:6]}', admin_id=admin.id)
    db.session.add(sub)
    db.session.flush()
    r = _rdo(obra, admin, date(2026, 7, 10))
    _apontar(r, t, admin, 30.0, 30.0, 30.0)
    db.session.add(RDOSubempreitadaApontamento(
        rdo_id=r.id, tarefa_cronograma_id=t.id, subempreiteiro_id=sub.id,
        qtd_pessoas=2, horas_trabalhadas=8.0, quantidade_produzida=20.0,
        admin_id=admin.id))
    db.session.commit()

    _atualizar_percentual_com_subempreitada(t.id, admin.id)
    db.session.refresh(t)
    # (30 empresa + 20 sub) / 100 = 50%.
    assert t.percentual_concluido == 50.0
