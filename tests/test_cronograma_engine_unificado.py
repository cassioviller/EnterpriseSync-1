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


# ---------------------------------------------------------------------------
# Task 2 — tabela normativa §12: marcos
# ---------------------------------------------------------------------------

def test_marco_planejado_degrau_e_realizado_binario():
    from utils.cronograma_engine import calcular_progresso_rdo

    admin, obra = _ambiente()
    marco = _tarefa(obra, admin, 'Entrega Estrutura', ordem=0, is_marco=True,
                    data_inicio=date(2026, 7, 10), data_fim=date(2026, 7, 10),
                    duracao_dias=0)
    db.session.commit()

    antes = calcular_progresso_rdo(marco.id, date(2026, 7, 9), admin.id)
    depois = calcular_progresso_rdo(marco.id, date(2026, 7, 10), admin.id)
    assert antes['percentual_planejado'] == 0.0     # degrau: ainda não
    assert depois['percentual_planejado'] == 100.0  # degrau: na data

    # Apontamento parcial (40%) NÃO conta: marco é binário → 0.
    r = _rdo(obra, admin, date(2026, 7, 10))
    ap = _apontar(r, marco, admin, 0.0, 0.0, 40.0)
    db.session.commit()
    assert calcular_progresso_rdo(
        marco.id, date(2026, 7, 10), admin.id)['percentual_realizado'] == 0.0
    ap.percentual_realizado = 100.0
    db.session.commit()
    assert calcular_progresso_rdo(
        marco.id, date(2026, 7, 10), admin.id)['percentual_realizado'] == 100.0


def test_duracao_zero_nao_marco_tratada_como_marco():
    from utils.cronograma_engine import calcular_progresso_rdo

    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Vistoria', ordem=0, is_marco=False,
                data_inicio=date(2026, 7, 10), data_fim=date(2026, 7, 10),
                duracao_dias=0)
    db.session.commit()
    assert calcular_progresso_rdo(
        t.id, date(2026, 7, 9), admin.id)['percentual_planejado'] == 0.0
    assert calcular_progresso_rdo(
        t.id, date(2026, 7, 12), admin.id)['percentual_planejado'] == 100.0


def test_marco_tem_peso_zero_no_agregado():
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2

    admin, obra = _ambiente()
    folha = _tarefa(obra, admin, 'Alvenaria', ordem=0, duracao_dias=10,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 14))
    _tarefa(obra, admin, 'Marco Concluído', ordem=1, is_marco=True,
            duracao_dias=0, data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 1))
    r = _rdo(obra, admin, date(2026, 7, 10))
    _apontar(r, folha, admin, 0.0, 0.0, 50.0)   # folha sem qtd → 50%
    db.session.commit()

    agg = calcular_progresso_geral_obra_v2(obra.id, date(2026, 7, 10), admin.id)
    # Marco (mesmo 100% no planejado) pesa 0: progresso == o da folha.
    # Com peso 1 (comportamento antigo) seria (50*10 + 0*1)/11 ≈ 45.5.
    assert agg['progresso_geral_pct'] == 50.0


# ---------------------------------------------------------------------------
# Task 2 — tabela §12: unidade homogênea no peso quantitativo
# ---------------------------------------------------------------------------

def test_usar_qtd_exige_unidade_homogenea():
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2

    def _obra_com_unidades(u1, u2):
        admin, obra = _ambiente()
        f1 = _tarefa(obra, admin, 'Painéis', ordem=0, duracao_dias=5,
                     quantidade_total=100.0, unidade_medida=u1,
                     data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        _tarefa(obra, admin, 'Parafusos', ordem=1, duracao_dias=5,
                quantidade_total=300.0, unidade_medida=u2,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        r = _rdo(obra, admin, date(2026, 7, 5))
        _apontar(r, f1, admin, 100.0, 100.0, 100.0)   # f1 = 100%, f2 = 0%
        db.session.commit()
        return admin, obra

    # Mesma unidade: peso = quantidade → (100*100 + 0*300)/400 = 25%.
    admin, obra = _obra_com_unidades('m2', 'm2')
    assert calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 5), admin.id)['progresso_geral_pct'] == 25.0

    # Unidades mistas: NUNCA soma m2+un — peso cai p/ duração (5,5) → 50%.
    admin, obra = _obra_com_unidades('m2', 'un')
    assert calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 5), admin.id)['progresso_geral_pct'] == 50.0


# ---------------------------------------------------------------------------
# Task 2 — tabela §12: arquivadas históricas (curva de avanço)
# ---------------------------------------------------------------------------

def test_arquivada_entra_no_historico_e_sai_do_presente():
    from datetime import datetime as _dt

    from utils.cronograma_engine import calcular_progresso_geral_obra_v2

    admin, obra = _ambiente()
    a = _tarefa(obra, admin, 'Demolição', ordem=0, duracao_dias=5,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
    _tarefa(obra, admin, 'Alvenaria', ordem=1, duracao_dias=5,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
    r = _rdo(obra, admin, date(2026, 7, 10))
    _apontar(r, a, admin, 0.0, 0.0, 100.0)          # trabalho feito em A
    a.ativa = False
    a.arquivada_em = _dt(2026, 7, 15, 12, 0)        # arquivada dia 15
    db.session.commit()

    # Default (pós-M05): arquivada fora sempre — comportamento preservado.
    assert calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 10), admin.id)['progresso_geral_pct'] == 0.0

    # Curva histórica: em 10/07 A ainda estava viva → o 100% dela conta.
    hist = calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 10), admin.id, com_arquivadas_historicas=True)
    assert hist['progresso_geral_pct'] == 50.0
    # Em 20/07 (após arquivamento) ela sai — só a viva conta.
    assert calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 20), admin.id,
        com_arquivadas_historicas=True)['progresso_geral_pct'] == 0.0


# ---------------------------------------------------------------------------
# Task 3 — rollup, subempreitada e KPI unificados no engine
# ---------------------------------------------------------------------------

def test_rollup_realizado_funcao_pura_com_hierarquia_aninhada():
    from utils.cronograma_engine import rollup_realizado

    itens = [
        {'id': 1, 'tarefa_pai_id': None, 'ordem': 0, 'duracao_dias': 10,
         'percentual_realizado': 0.0},                       # avô
        {'id': 2, 'tarefa_pai_id': 1, 'ordem': 1, 'duracao_dias': 10,
         'percentual_realizado': 0.0},                       # pai
        {'id': 3, 'tarefa_pai_id': 2, 'ordem': 2, 'duracao_dias': 2,
         'percentual_realizado': 50.0},
        {'id': 4, 'tarefa_pai_id': 2, 'ordem': 3, 'duracao_dias': 8,
         'percentual_realizado': 100.0},
    ]
    resultado = rollup_realizado(itens)
    # pai: (50*2 + 100*8)/10 = 90; avô herda o agregado do pai (não o 0 cru).
    assert resultado[2] == 90.0
    assert resultado[1] == 90.0


def test_subempreitada_agora_no_atualizar_percentual_tarefa():
    from utils.cronograma_engine import atualizar_percentual_tarefa

    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Cobertura', ordem=0,
                quantidade_total=100.0, unidade_medida='m2')
    sub = Subempreiteiro(nome=f'Sub {uuid.uuid4().hex[:6]}', admin_id=admin.id)
    db.session.add(sub)
    db.session.flush()
    r = _rdo(obra, admin, date(2026, 7, 10))
    db.session.add(RDOSubempreitadaApontamento(
        rdo_id=r.id, tarefa_cronograma_id=t.id, subempreiteiro_id=sub.id,
        qtd_pessoas=2, horas_trabalhadas=8.0, quantidade_produzida=20.0,
        admin_id=admin.id))
    db.session.commit()

    # SÓ subempreitada (sem apontamento da empresa): 20/100 = 20%.
    atualizar_percentual_tarefa(t.id, admin.id)
    db.session.refresh(t)
    assert t.percentual_concluido == 20.0

    # Empresa acumula 30 → 50% (soma, não substitui).
    _apontar(r, t, admin, 30.0, 30.0, 30.0)
    db.session.commit()
    atualizar_percentual_tarefa(t.id, admin.id)
    db.session.refresh(t)
    assert t.percentual_concluido == 50.0


def test_kpi_usa_v2_com_cronograma_e_fallback_sem():
    from utils.cronograma_engine import (
        calcular_progresso_geral_obra_v2,
        progresso_geral_para_kpi,
    )

    # Obra COM cronograma: KPI == v2 de hoje (convergência).
    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Alvenaria', ordem=0, duracao_dias=10,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 14))
    r = _rdo(obra, admin, date(2026, 7, 10))
    _apontar(r, t, admin, 0.0, 0.0, 40.0)
    db.session.commit()
    v2_hoje = calcular_progresso_geral_obra_v2(
        obra.id, date.today(), admin.id)['progresso_geral_pct']
    assert progresso_geral_para_kpi(obra.id, admin.id) == v2_hoje == 40.0

    # Obra SEM cronograma: fallback C — média simples das subatividades do
    # último RDO (a antiga FÓRMULA SIMPLES do KPI, agora extraída — trava B).
    admin2, obra2 = _ambiente()
    r1 = _rdo(obra2, admin2, date(2026, 7, 10))
    r2 = _rdo(obra2, admin2, date(2026, 7, 11))
    db.session.add(RDOServicoSubatividade(
        rdo_id=r1.id, nome_subatividade='Corte', percentual_conclusao=90.0,
        admin_id=admin2.id))
    for nome, pct in (('Corte', 30.0), ('Solda', 60.0)):
        db.session.add(RDOServicoSubatividade(
            rdo_id=r2.id, nome_subatividade=nome, percentual_conclusao=pct,
            admin_id=admin2.id))
    db.session.commit()
    # Último RDO (r2): (30+60)/2 = 45 — r1 ignorado (fórmula B vigente).
    assert progresso_geral_para_kpi(obra2.id, admin2.id) == 45.0
