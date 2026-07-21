"""M07 Task 2 — recomputo em cadeia determinístico.

Criar/editar/excluir apontamento antigo reprocessa os RDOs posteriores da
tarefa em ordem (data_relatorio, id), na MESMA transação do caller, sem
tocar fatos brutos (quantidade do dia, % digitado, snapshots, planejado).
"""
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import RDO, RDOApontamentoCronograma, TarefaCronograma
from services.cronograma_apontamento_service import (
    recomputar_cadeia,
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
        app.secret_key = 'test-recomputo-cadeia'
    yield


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _tarefa(ctx, **kw):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa RC {_suffix()}', ordem=1,
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
        numero_rdo=f'RC-{_suffix()[4:]}'[:20],
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        data_relatorio=data_rdo, local='Campo', status='Finalizado',
    )
    db.session.add(r)
    db.session.commit()
    return r


def _linha(rdo_id, tarefa_id):
    return RDOApontamentoCronograma.query.filter_by(
        rdo_id=rdo_id, tarefa_cronograma_id=tarefa_id).one()


def test_rdo_retroativo_no_meio_da_serie_quantitativo(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    r1, r3 = _rdo(ctx, D0), _rdo(ctx, D0 + timedelta(days=2))
    registrar_apontamento(r1, t, quantidade_dia=10.0, admin_id=ctx['admin_id'])
    registrar_apontamento(r3, t, quantidade_dia=20.0, admin_id=ctx['admin_id'])
    db.session.commit()
    assert _linha(r3.id, t.id).quantidade_acumulada == 30.0

    # RDO retroativo NO MEIO (D0+1) com 30 unidades.
    r2 = _rdo(ctx, D0 + timedelta(days=1))
    registrar_apontamento(r2, t, quantidade_dia=30.0, admin_id=ctx['admin_id'])
    db.session.flush()
    alteradas = recomputar_cadeia(t.id, r2.data_relatorio, ctx['admin_id'])
    db.session.commit()

    l1, l2, l3 = _linha(r1.id, t.id), _linha(r2.id, t.id), _linha(r3.id, t.id)
    assert l1.quantidade_acumulada == 10.0        # anterior à janela: intacto
    assert l2.quantidade_acumulada == 40.0        # 10 + 30
    assert l3.quantidade_acumulada == 60.0        # recalculado (era 30)
    assert (l1.percentual_realizado, l2.percentual_realizado,
            l3.percentual_realizado) == (10.0, 40.0, 60.0)
    assert l3.percentual_incremento_dia == 20.0   # 60 - 40
    # Fatos brutos intocados.
    assert (l1.quantidade_executada_dia, l2.quantidade_executada_dia,
            l3.quantidade_executada_dia) == (10.0, 30.0, 20.0)
    assert alteradas >= 1                          # ao menos a linha de r3


def test_editar_apontamento_antigo_recalcula_posteriores(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    r1, r2 = _rdo(ctx, D0), _rdo(ctx, D0 + timedelta(days=1))
    registrar_apontamento(r1, t, quantidade_dia=10.0, admin_id=ctx['admin_id'])
    registrar_apontamento(r2, t, quantidade_dia=20.0, admin_id=ctx['admin_id'])
    db.session.commit()

    # Edição (UPSERT no mesmo RDO): 10 → 50.
    registrar_apontamento(r1, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    db.session.flush()
    recomputar_cadeia(t.id, r1.data_relatorio, ctx['admin_id'])
    db.session.commit()

    assert _linha(r1.id, t.id).quantidade_acumulada == 50.0
    l2 = _linha(r2.id, t.id)
    assert l2.quantidade_acumulada == 70.0
    assert l2.percentual_realizado == 70.0


def test_cadeia_percentual_recalcula_incrementos(ctx):
    t = _tarefa(ctx, quantidade_total=None)
    r1, r3 = _rdo(ctx, D0), _rdo(ctx, D0 + timedelta(days=2))
    registrar_apontamento(r1, t, percentual_acumulado=25.0,
                          admin_id=ctx['admin_id'])
    registrar_apontamento(r3, t, percentual_acumulado=50.0,
                          admin_id=ctx['admin_id'])
    db.session.commit()
    assert _linha(r3.id, t.id).percentual_incremento_dia == 25.0  # 50-25

    # Retroativo no meio: 40% em D0+1.
    r2 = _rdo(ctx, D0 + timedelta(days=1))
    registrar_apontamento(r2, t, percentual_acumulado=40.0,
                          admin_id=ctx['admin_id'])
    db.session.flush()
    recomputar_cadeia(t.id, r2.data_relatorio, ctx['admin_id'])
    db.session.commit()

    assert _linha(r2.id, t.id).percentual_incremento_dia == 15.0  # 40-25
    l3 = _linha(r3.id, t.id)
    assert l3.percentual_incremento_dia == 10.0                   # 50-40
    assert l3.percentual_acumulado == 50.0                        # digitado intacto
    assert l3.quantidade_executada_dia == 0.0                     # sem abuso


def test_mesma_data_desempata_por_id(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    ra = _rdo(ctx, D0)
    rb = _rdo(ctx, D0)          # mesmo dia, id maior
    registrar_apontamento(ra, t, quantidade_dia=10.0, admin_id=ctx['admin_id'])
    registrar_apontamento(rb, t, quantidade_dia=20.0, admin_id=ctx['admin_id'])
    db.session.flush()
    recomputar_cadeia(t.id, D0, ctx['admin_id'])
    db.session.commit()
    # Ordem estável (data, id): ra primeiro (10), rb depois (30).
    assert _linha(ra.id, t.id).quantidade_acumulada == 10.0
    assert _linha(rb.id, t.id).quantidade_acumulada == 30.0


def test_recomputo_respeita_snapshot_da_linha(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    r1 = _rdo(ctx, D0)
    registrar_apontamento(r1, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    db.session.commit()

    # Total da tarefa muda DEPOIS; recomputo não reinterpreta o histórico.
    t.quantidade_total = 200.0
    db.session.commit()
    recomputar_cadeia(t.id, D0, ctx['admin_id'])
    db.session.commit()
    l1 = _linha(r1.id, t.id)
    assert l1.quantidade_total_snapshot == 100.0
    assert l1.percentual_realizado == 50.0       # 50/100, NÃO 50/200


def test_apontar_producao_retroativo_via_http(ctx):
    """Integração: POST /cronograma/rdo/<id>/apontar num RDO retroativo
    devolve rdos_posteriores_recalculados e conserta o persistido."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    r1, r3 = _rdo(ctx, D0), _rdo(ctx, D0 + timedelta(days=2))
    registrar_apontamento(r1, t, quantidade_dia=10.0, admin_id=ctx['admin_id'])
    registrar_apontamento(r3, t, quantidade_dia=20.0, admin_id=ctx['admin_id'])
    db.session.commit()

    r2 = _rdo(ctx, D0 + timedelta(days=1))
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(ctx['admin_id'])
        sess['_fresh'] = True
    resp = c.post(f'/cronograma/rdo/{r2.id}/apontar', json={
        'tarefa_cronograma_id': t.id,
        'quantidade_executada_dia': 30.0,
    })
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body['rdos_posteriores_recalculados'] >= 1
    db.session.expire_all()
    assert _linha(r3.id, t.id).quantidade_acumulada == 60.0
    db.session.refresh(t)
    assert t.percentual_concluido == 60.0        # último RDO manda


def test_excluir_rdo_recalcula_cadeia_via_http(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    r1, r2, r3 = (_rdo(ctx, D0), _rdo(ctx, D0 + timedelta(days=1)),
                  _rdo(ctx, D0 + timedelta(days=2)))
    for r, q in ((r1, 10.0), (r2, 30.0), (r3, 20.0)):
        registrar_apontamento(r, t, quantidade_dia=q,
                              admin_id=ctx['admin_id'])
    db.session.flush()
    recomputar_cadeia(t.id, D0, ctx['admin_id'])
    db.session.commit()
    assert _linha(r3.id, t.id).quantidade_acumulada == 60.0

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(ctx['admin_id'])
        sess['_fresh'] = True
    resp = c.post(f'/rdo/excluir/{r2.id}')
    assert resp.status_code in (200, 302)
    db.session.expire_all()
    # RDO do meio saiu: r3 reacumulado 10+20=30; r1 intacto.
    assert RDOApontamentoCronograma.query.filter_by(rdo_id=r2.id).count() == 0
    assert _linha(r1.id, t.id).quantidade_acumulada == 10.0
    l3 = _linha(r3.id, t.id)
    assert l3.quantidade_acumulada == 30.0
    assert l3.percentual_realizado == 30.0
    db.session.refresh(t)
    assert t.percentual_concluido == 30.0
