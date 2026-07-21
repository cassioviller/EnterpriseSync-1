"""M06 Task 4 — replanejamento determinístico das curvas (spec §4.3).

Propriedades centrais: mudar as datas das tarefas e replanejar recalcula o
`percentual_planejado` de cada apontamento COM A DATA DO PRÓPRIO RDO,
enquanto todo o realizado permanece byte-idêntico; o relatório lista
arquivadas com apontamento (histórico não reconciliado); a aplicação de
versão (M05) dispara o replanejamento e audita num evento `replanejado`.
"""
import os
import sys
import uuid
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    RDO,
    RDOApontamentoCronograma,
    CronogramaImportacaoEvento,
    TarefaCronograma,
)
from utils.cronograma_engine import (
    calcular_progresso_geral_obra_v2,
    replanejar_curvas_obra,
    verificar_consistencia_progresso,
)
from test_cronograma_versao_service import (
    _ambiente,
    _importacao_pronta,
    _nt,
    _tarefa,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-replanejamento'
    with app.app_context():
        yield


def _rdo_apontado(obra, admin, tarefa, dia, qtd_dia, acumulada, pct,
                  planejado=None):
    rdo = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:12]}',
              data_relatorio=dia, obra_id=obra.id, admin_id=admin.id)
    db.session.add(rdo)
    db.session.flush()
    ap = RDOApontamentoCronograma(
        rdo_id=rdo.id,
        tarefa_cronograma_id=tarefa.id,
        quantidade_executada_dia=qtd_dia,
        quantidade_acumulada=acumulada,
        percentual_realizado=pct,
        percentual_planejado=planejado,
        admin_id=admin.id,
    )
    db.session.add(ap)
    db.session.commit()
    return ap


def _realizado(ap):
    """Tupla com TODOS os campos de realizado que o replanejamento não pode
    tocar."""
    return (ap.quantidade_executada_dia, ap.quantidade_acumulada,
            ap.percentual_realizado, ap.percentual_acumulado)


def test_replaneja_planejado_por_data_de_rdo_e_preserva_realizado():
    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Alvenaria', ordem=0, duracao_dias=10,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 14),
                quantidade_total=100.0, unidade_medida='m2')
    # 3 RDOs com planejado snapshotado do plano ANTIGO.
    aps = [
        _rdo_apontado(obra, admin, t, date(2026, 7, 2), 20, 20, 20, 20.0),
        _rdo_apontado(obra, admin, t, date(2026, 7, 6), 30, 50, 50, 40.0),
        _rdo_apontado(obra, admin, t, date(2026, 7, 10), 30, 80, 80, 80.0),
    ]
    antes = [_realizado(ap) for ap in aps]

    # Versão nova empurrou a tarefa para agosto.
    t.data_inicio = date(2026, 8, 3)
    t.data_fim = date(2026, 8, 14)
    db.session.commit()

    rel = replanejar_curvas_obra(obra.id, admin.id)

    for ap in aps:
        db.session.refresh(ap)
    # Todos os RDOs são anteriores ao novo início ⇒ planejado 0 em todos.
    assert [ap.percentual_planejado for ap in aps] == [0.0, 0.0, 0.0]
    # Realizado byte-idêntico.
    assert [_realizado(ap) for ap in aps] == antes
    assert rel['apontamentos_replanejados'] == 3
    assert rel['tarefas_sem_historico_reconciliado'] == []
    assert isinstance(rel['progresso_antes'], float)
    assert isinstance(rel['progresso_depois'], float)


def test_replaneja_com_datas_vigentes_intermediarias():
    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Pintura', ordem=0, duracao_dias=10,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 14))
    ap = _rdo_apontado(obra, admin, t, date(2026, 7, 8), 0, 0, 30, 99.0)

    rel = replanejar_curvas_obra(obra.id, admin.id)
    db.session.refresh(ap)
    # 01→08/07 (sem fds): 6 dias úteis de 10 ⇒ 60%.
    assert ap.percentual_planejado == 60.0
    assert rel['apontamentos_replanejados'] == 1
    # Idempotente: segunda execução não muda nada.
    assert replanejar_curvas_obra(
        obra.id, admin.id)['apontamentos_replanejados'] == 0


def test_replaneja_marco_como_degrau_e_sem_datas_como_none():
    admin, obra = _ambiente()
    marco = _tarefa(obra, admin, 'Entrega', ordem=0, is_marco=True,
                    duracao_dias=0, data_inicio=date(2026, 7, 20),
                    data_fim=date(2026, 7, 20))
    solta = _tarefa(obra, admin, 'Sem Plano', ordem=1, duracao_dias=5,
                    data_inicio=None, data_fim=None)
    ap_m = _rdo_apontado(obra, admin, marco, date(2026, 7, 10),
                         0, 0, 0, 55.0)
    ap_s = _rdo_apontado(obra, admin, solta, date(2026, 7, 10),
                         0, 0, 10, 33.0)
    replanejar_curvas_obra(obra.id, admin.id)
    db.session.refresh(ap_m)
    db.session.refresh(ap_s)
    assert ap_m.percentual_planejado == 0.0    # degrau: antes de 20/07
    assert ap_s.percentual_planejado is None   # sem plano ≠ 0%


def test_relatorio_lista_arquivadas_com_apontamento():
    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Demolição', ordem=0, duracao_dias=5,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
    _rdo_apontado(obra, admin, t, date(2026, 7, 3), 0, 0, 50, None)
    t.ativa = False
    t.arquivada_em = datetime(2026, 7, 15)
    db.session.commit()

    rel = replanejar_curvas_obra(obra.id, admin.id)
    assert rel['tarefas_sem_historico_reconciliado'] == [t.id]


def test_aplicar_versao_replaneja_e_audita_evento():
    from services.cronograma_versao_service import aplicar_versao

    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Alvenaria', ordem=0, mpp_uid=1,
                duracao_dias=10, data_inicio=date(2026, 7, 1),
                data_fim=date(2026, 7, 14))
    ap = _rdo_apontado(obra, admin, t, date(2026, 7, 8), 0, 0, 30, 60.0)
    realizado_antes = _realizado(ap)

    # Nova versão empurra a tarefa para setembro.
    imp, _ = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Alvenaria', uid=1,
            inicio='2026-09-01', fim='2026-09-14', dias=10.0))
    versao = aplicar_versao(imp.id, {}, admin.id)

    db.session.refresh(ap)
    assert ap.percentual_planejado == 0.0          # replanejado (RDO < início)
    assert _realizado(ap) == realizado_antes       # realizado intocado
    ev = CronogramaImportacaoEvento.query.filter_by(
        importacao_id=imp.id, evento='replanejado').one()
    assert ev.detalhes['versao_numero'] == versao.numero
    assert ev.detalhes['apontamentos_replanejados'] >= 1
    # Monotonicidade preservada pós-replanejamento.
    p1 = calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 8), admin.id)['progresso_geral_pct']
    p2 = calcular_progresso_geral_obra_v2(
        obra.id, date(2026, 7, 20), admin.id)['progresso_geral_pct']
    assert 0 < p1 <= p2


def test_verificar_consistencia_progresso_detecta_e_confirma_drift():
    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Cobertura', ordem=0, duracao_dias=5,
                quantidade_total=100.0, unidade_medida='m2',
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
    _rdo_apontado(obra, admin, t, date(2026, 7, 3), 30, 30, 30, None)
    t.percentual_concluido = 99.0        # drift plantado
    db.session.commit()

    rel = verificar_consistencia_progresso(obra.id, admin.id)
    assert rel['tarefas_verificadas'] == 1
    assert rel['divergencias'] == [
        {'tarefa_id': t.id, 'persistido': 99.0, 'recalculado': 30.0}]

    # Após sincronizar, o drift desaparece.
    from utils.cronograma_engine import sincronizar_percentuais_obra
    sincronizar_percentuais_obra(obra.id, admin.id)
    assert verificar_consistencia_progresso(
        obra.id, admin.id)['divergencias'] == []
