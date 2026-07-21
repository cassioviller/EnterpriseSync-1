"""M07 Task 1 — modos de apontamento com semântica M02 e validações.

Cobre o que a caracterização do M1 não trava: campos semânticos gravados
nos dois modos, snapshot blindando o histórico, sobre-execução percentual
com confirmação, marco binário e modo_da_tarefa (contrato da UI).
"""
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import RDO, RDOApontamentoCronograma, TarefaCronograma
from services.cronograma_apontamento_service import (
    MarcoApenasZeroOuCem,
    SobreexecucaoNaoConfirmada,
    modo_da_tarefa,
    registrar_apontamento,
)
from test_cronograma_apontamento_service import ctx  # noqa: F401 — fixture

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-modos-apontamento'
    yield


def _client_como(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _tarefa(ctx, **kw):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa M07 {_suffix()}', ordem=1,
        responsavel='empresa',
        duracao_dias=kw.pop('duracao_dias', 10),
        data_inicio=kw.pop('data_inicio', D0 - timedelta(days=30)),
        data_fim=kw.pop('data_fim', D0 - timedelta(days=20)),
        **kw,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _rdo(ctx, data_rdo):
    r = RDO(
        numero_rdo=f'RM-{_suffix()[4:]}'[:20],
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        data_relatorio=data_rdo, local='Campo', status='Finalizado',
    )
    db.session.add(r)
    db.session.commit()
    return r


# ---------------------------------------------------------------------------
# modo_da_tarefa — contrato que a UI consome
# ---------------------------------------------------------------------------

def test_modo_da_tarefa(ctx):
    quant = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    sem_unidade = _tarefa(ctx, quantidade_total=100.0, unidade_medida=None)
    sem_qtd = _tarefa(ctx, quantidade_total=None)
    marco = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    is_marco=True, duracao_dias=0)
    assert modo_da_tarefa(quant) == 'quantidade'
    assert modo_da_tarefa(sem_unidade) == 'percentual'   # qty sem unidade
    assert modo_da_tarefa(sem_qtd) == 'percentual'
    assert modo_da_tarefa(marco) == 'percentual'         # marco: binário


# ---------------------------------------------------------------------------
# Campos semânticos (M02) gravados nos dois modos
# ---------------------------------------------------------------------------

def test_quantitativo_grava_semantica_e_snapshot(ctx):
    t = _tarefa(ctx, quantidade_total=200.0, unidade_medida='m2')
    ap = registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=50.0,
                               admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap.tipo_apontamento == 'quantitativo'
    assert ap.quantidade_total_snapshot == 200.0
    assert ap.unidade_snapshot == 'm2'
    assert ap.percentual_acumulado == 25.0
    assert ap.percentual_incremento_dia == 25.0
    # Legado intacto (dupla escrita).
    assert ap.quantidade_executada_dia == 50.0
    assert ap.quantidade_acumulada == 50.0
    assert ap.percentual_realizado == 25.0


def test_snapshot_blinda_historico_contra_mudanca_de_total(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    ap1 = registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=50.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap1.percentual_realizado == 50.0   # 50/100

    # Total da tarefa dobra DEPOIS do primeiro apontamento.
    t.quantidade_total = 200.0
    db.session.commit()

    ap2 = registrar_apontamento(_rdo(ctx, D0 + timedelta(days=1)), t,
                                quantidade_dia=50.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    # Linha antiga imutável (snapshot 100); nova linha usa o total novo.
    assert ap1.quantidade_total_snapshot == 100.0
    assert ap1.percentual_realizado == 50.0
    assert ap2.quantidade_total_snapshot == 200.0
    assert ap2.percentual_realizado == 50.0   # 100/200


# ---------------------------------------------------------------------------
# Sobre-execução e marco
# ---------------------------------------------------------------------------

def test_percentual_acima_de_100_exige_confirmacao(ctx):
    t = _tarefa(ctx, quantidade_total=None)
    rdo = _rdo(ctx, D0)
    with pytest.raises(SobreexecucaoNaoConfirmada):
        registrar_apontamento(rdo, t, percentual_acumulado=105.0,
                              admin_id=ctx['admin_id'])
    db.session.rollback()

    ap = registrar_apontamento(rdo, t, percentual_acumulado=105.0,
                               admin_id=ctx['admin_id'],
                               permitir_sobreexecucao=True)
    db.session.commit()
    # Raw preservado; agregado clampa em 100 (spec §12).
    assert ap.percentual_acumulado == 105.0
    assert ap.percentual_realizado == 100.0


def test_sobreexecucao_quantitativa_mantem_clamp_legado(ctx):
    """Overshoot quantitativo NÃO exige confirmação (caracterização):
    percentual clampa em 100 com aviso; acumulada real fica registrada."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='un')
    ap = registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=130.0,
                               admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap.quantidade_acumulada == 130.0
    assert ap.percentual_realizado == 100.0
    assert ap.percentual_acumulado == 100.0


def test_marco_so_aceita_zero_ou_cem(ctx):
    marco = _tarefa(ctx, quantidade_total=None, is_marco=True,
                    duracao_dias=0, data_fim=D0 - timedelta(days=30))
    rdo = _rdo(ctx, D0)
    with pytest.raises(MarcoApenasZeroOuCem):
        registrar_apontamento(rdo, marco, percentual_acumulado=50.0,
                              admin_id=ctx['admin_id'])
    db.session.rollback()

    ap = registrar_apontamento(rdo, marco, percentual_acumulado=100.0,
                               admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap.percentual_acumulado == 100.0
    assert ap.percentual_realizado == 100.0


# ---------------------------------------------------------------------------
# Task 3 — contrato tarefas_rdo e apontar_producao percentual via HTTP
# ---------------------------------------------------------------------------

def test_tarefas_rdo_expoe_contrato_de_modos(ctx):
    """O JSON de tarefas_rdo carrega tipo_modo/is_marco/anterior/saldo —
    a UI não decide fórmula, só exibe (spec §4.2)."""
    t_q = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    t_p = _tarefa(ctx, quantidade_total=None)
    t_m = _tarefa(ctx, quantidade_total=None, is_marco=True, duracao_dias=0)
    r0 = RDO(numero_rdo=f'RH-{_suffix()[4:]}'[:20], obra_id=ctx['obra_id'],
             admin_id=ctx['admin_id'], data_relatorio=D0, local='Campo',
             status='Finalizado')
    db.session.add(r0)
    db.session.commit()
    registrar_apontamento(r0, t_q, quantidade_dia=30.0,
                          admin_id=ctx['admin_id'])
    registrar_apontamento(r0, t_p, percentual_acumulado=40.0,
                          admin_id=ctx['admin_id'])
    db.session.commit()

    c = _client_como(ctx['admin_id'])
    dia_seguinte = (D0 + timedelta(days=1)).isoformat()
    resp = c.get(f"/cronograma/obra/{ctx['obra_id']}/tarefas-rdo"
                 f'?data={dia_seguinte}')
    assert resp.status_code == 200
    itens = {i['id']: i for i in resp.get_json()['tarefas']}

    q = itens[t_q.id]
    assert q['tipo_modo'] == 'quantidade'
    assert q['is_marco'] is False
    assert q['percentual_acumulado_anterior'] == 30.0
    assert q['saldo'] == 70.0                    # 100 − 30

    p = itens[t_p.id]
    assert p['tipo_modo'] == 'percentual'
    assert p['percentual_acumulado_anterior'] == 40.0
    assert p['saldo'] is None

    m = itens[t_m.id]
    assert m['tipo_modo'] == 'percentual'
    assert m['is_marco'] is True


def test_apontar_producao_percentual_via_http(ctx):
    t = _tarefa(ctx, quantidade_total=None)
    r1 = RDO(numero_rdo=f'RH-{_suffix()[4:]}'[:20], obra_id=ctx['obra_id'],
             admin_id=ctx['admin_id'], data_relatorio=D0, local='Campo',
             status='Finalizado')
    db.session.add(r1)
    db.session.commit()
    c = _client_como(ctx['admin_id'])

    resp = c.post(f'/cronograma/rdo/{r1.id}/apontar', json={
        'tarefa_cronograma_id': t.id, 'percentual_acumulado': 35.0})
    assert resp.status_code == 200, resp.get_json()
    ap = db.session.get(RDOApontamentoCronograma,
                        resp.get_json()['apontamento']['id'])
    assert ap.tipo_apontamento == 'percentual'
    assert ap.percentual_acumulado == 35.0
    assert ap.quantidade_executada_dia == 0.0

    # Retrocesso sem justificativa → 422 com mensagem acionável.
    r2 = RDO(numero_rdo=f'RH-{_suffix()[4:]}'[:20], obra_id=ctx['obra_id'],
             admin_id=ctx['admin_id'], data_relatorio=D0 + timedelta(days=1),
             local='Campo', status='Finalizado')
    db.session.add(r2)
    db.session.commit()
    resp = c.post(f'/cronograma/rdo/{r2.id}/apontar', json={
        'tarefa_cronograma_id': t.id, 'percentual_acumulado': 20.0})
    assert resp.status_code == 422
    assert 'justificativa' in resp.get_json()['msg'].lower()

    # Com retrocesso autorizado → 200.
    resp = c.post(f'/cronograma/rdo/{r2.id}/apontar', json={
        'tarefa_cronograma_id': t.id, 'percentual_acumulado': 20.0,
        'permitir_retrocesso': True, 'justificativa': 'medição refeita'})
    assert resp.status_code == 200, resp.get_json()


def test_salvar_rdo_flexivel_modo_percentual_via_form(ctx):
    """Task 4: o formulário do Novo RDO envia cronograma_tarefa_pct_<id>
    (+ justificativa/confirmação) e o flexivel delega ao serviço."""
    t = _tarefa(ctx, quantidade_total=None)
    c = _client_como(ctx['admin_id'])

    r = c.post('/salvar-rdo-flexivel', data={
        'obra_id': str(ctx['obra_id']),
        'admin_id_form': str(ctx['admin_id']),
        'data_relatorio': D0.isoformat(),
        'observacoes_gerais': 'RDO M07 percentual',
        f'cronograma_tarefa_pct_{t.id}': '45.5',
    })
    assert r.status_code in (200, 302, 303)
    ap = RDOApontamentoCronograma.query.filter_by(
        tarefa_cronograma_id=t.id).one()
    assert ap.tipo_apontamento == 'percentual'
    assert ap.percentual_acumulado == 45.5
    assert ap.percentual_incremento_dia == 45.5
    assert ap.quantidade_executada_dia == 0.0
    db.session.refresh(t)
    assert t.percentual_concluido == 45.5

    # Correção retroativa via form: pct menor + justificativa → aceita e
    # grava incremento negativo.
    r = c.post('/salvar-rdo-flexivel', data={
        'obra_id': str(ctx['obra_id']),
        'admin_id_form': str(ctx['admin_id']),
        'data_relatorio': (D0 + timedelta(days=1)).isoformat(),
        'observacoes_gerais': 'RDO M07 correção',
        f'cronograma_tarefa_pct_{t.id}': '30.0',
        f'retrocesso_justificativa_{t.id}': 'medição refeita em campo',
    })
    assert r.status_code in (200, 302, 303)
    aps = (RDOApontamentoCronograma.query
           .filter_by(tarefa_cronograma_id=t.id)
           .order_by(RDOApontamentoCronograma.id).all())
    assert len(aps) == 2
    assert aps[1].percentual_acumulado == 30.0
    assert aps[1].percentual_incremento_dia == -15.5
    db.session.refresh(t)
    assert t.percentual_concluido == 30.0
