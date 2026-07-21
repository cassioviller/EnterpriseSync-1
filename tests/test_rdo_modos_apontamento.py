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
from models import RDO, TarefaCronograma
from services.cronograma_apontamento_service import (
    MarcoApenasZeroOuCem,
    SobreexecucaoNaoConfirmada,
    modo_da_tarefa,
    registrar_apontamento,
)
from test_cronograma_apontamento_service import ctx  # noqa: F401 — fixture

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


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
