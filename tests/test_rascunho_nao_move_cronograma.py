"""RDO em rascunho não move o percentual do cronograma.

Plano: docs/superpowers/plans/2026-08-24-rascunho-nao-move-cronograma.md

Em 21/08 o custo de mão de obra parou de vazar de RDO em rascunho
(`services.rdo_ciclo_vida.publica_custos`). O avanço físico não: o percentual
da tarefa continuava saindo de apontamento de RDO que ninguém submeteu.

O que estes testes travam é o ciclo inteiro, não só o filtro:

1. rascunho não conta;
2. **Submeter faz contar** — e este é o caso perigoso, porque a única escrita
   de percentual acontece no salvar, enquanto o RDO ainda é rascunho. Filtrar
   sem recalcular no Submeter não deixaria o avanço mais correto, deixaria o
   avanço morto, em silêncio;
3. Reabrir tira de volta.
"""
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import RDO, TarefaCronograma
from services.cronograma_apontamento_service import registrar_apontamento
from services.rdo_ciclo_vida import PREENCHIDO, RASCUNHO, transicionar
from test_cronograma_apontamento_service import ctx  # noqa: F401 — fixture

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rascunho-cronograma'
    yield


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _tarefa(ctx):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa RNC {_suffix()}', ordem=1,
        responsavel='empresa', quantidade_total=100.0, unidade_medida='m2',
        duracao_dias=10,
        data_inicio=D0 - timedelta(days=30),
        data_fim=D0 - timedelta(days=20),
    )
    db.session.add(t)
    db.session.commit()
    return t


def _rdo_rascunho(ctx):
    """RDO como a tela o cria: `status='Finalizado'` (a coluna legada, que
    models.py faz nascer assim para todo RDO) e `estado` no default —
    `rascunho`. É exatamente o RDO que o encarregado deixa aberto durante o
    dia."""
    r = RDO(
        numero_rdo=f'RNC-{_suffix()[4:]}'[:20],
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        data_relatorio=D0, local='Campo', status='Finalizado',
    )
    db.session.add(r)
    db.session.commit()
    assert r.estado == RASCUNHO, 'a fixture precisa nascer em rascunho'
    return r


def _pct(tarefa_id):
    return float(TarefaCronograma.query.get(tarefa_id).percentual_concluido or 0.0)


def test_rascunho_nao_move_o_percentual_da_tarefa(ctx):
    """50 m² de 100 apontados num RDO nunca submetido ⇒ a tarefa fica em 0."""
    from utils.cronograma_engine import atualizar_percentual_tarefa

    t = _tarefa(ctx)
    r = _rdo_rascunho(ctx)
    registrar_apontamento(r, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    db.session.commit()

    atualizar_percentual_tarefa(t.id, ctx['admin_id'])

    assert _pct(t.id) == pytest.approx(0.0), (
        'apontamento de RDO em rascunho não pode mover o cronograma — '
        'é o dia que "não conta" da norma (capítulo 23a, §7)')


def test_submeter_faz_o_apontamento_contar(ctx):
    """O caso que impede o fix ingênuo: depois do Submeter, o avanço aparece.

    Se este teste falhar, o filtro foi aplicado sem o recálculo na transição —
    e o avanço deixou de existir em vez de ficar correto.
    """
    from services.cronograma_apontamento_service import (
        recalcular_percentuais_do_rdo,
    )

    t = _tarefa(ctx)
    r = _rdo_rascunho(ctx)
    registrar_apontamento(r, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    db.session.commit()

    transicionar(r, PREENCHIDO)
    db.session.commit()
    recalcular_percentuais_do_rdo(r.id, ctx['admin_id'])

    assert _pct(t.id) == pytest.approx(50.0), (
        'submeter o RDO tem de publicar o avanço que ele carrega')


def test_reabrir_devolve_o_percentual(ctx):
    """Reabrir é o inverso do Submeter: o dia volta a não contar."""
    from services.cronograma_apontamento_service import (
        recalcular_percentuais_do_rdo,
    )

    t = _tarefa(ctx)
    r = _rdo_rascunho(ctx)
    registrar_apontamento(r, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    db.session.commit()
    transicionar(r, PREENCHIDO)
    db.session.commit()
    recalcular_percentuais_do_rdo(r.id, ctx['admin_id'])
    assert _pct(t.id) == pytest.approx(50.0), 'pré-condição do teste'

    transicionar(r, RASCUNHO, motivo='correção de efetivo')
    db.session.commit()
    recalcular_percentuais_do_rdo(r.id, ctx['admin_id'])

    assert _pct(t.id) == pytest.approx(0.0), (
        'reabrir devolve o RDO para rascunho — o avanço dele sai junto')


def test_apontamento_de_outro_rdo_submetido_sobrevive(ctx):
    """A guarda contra o efeito colateral: reabrir UM RDO não pode apagar o
    avanço que veio de OUTRO, já submetido.

    Sem isto, o recálculo do teste anterior poderia estar zerando a tarefa por
    força bruta em vez de recalcular a partir dos RDOs que ainda valem.
    """
    from services.cronograma_apontamento_service import (
        recalcular_percentuais_do_rdo,
    )

    t = _tarefa(ctx)

    antigo = RDO(
        numero_rdo=f'RNC-A{_suffix()[5:]}'[:20],
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        data_relatorio=D0 - timedelta(days=1), local='Campo',
        status='Finalizado',
    )
    db.session.add(antigo)
    db.session.commit()
    registrar_apontamento(antigo, t, quantidade_dia=30.0,
                          admin_id=ctx['admin_id'])
    db.session.commit()
    transicionar(antigo, PREENCHIDO)
    db.session.commit()
    recalcular_percentuais_do_rdo(antigo.id, ctx['admin_id'])
    assert _pct(t.id) == pytest.approx(30.0), 'pré-condição do teste'

    novo = _rdo_rascunho(ctx)
    registrar_apontamento(novo, t, quantidade_dia=20.0,
                          admin_id=ctx['admin_id'])
    db.session.commit()
    recalcular_percentuais_do_rdo(novo.id, ctx['admin_id'])

    assert _pct(t.id) == pytest.approx(30.0), (
        'o rascunho de hoje não conta, mas o RDO submetido de ontem continua '
        'valendo — o percentual é 30, não 0 nem 50')


def test_rascunho_nao_zera_percentual_importado_do_ms_project(ctx):
    """O buraco que o filtro quase abriu.

    Obra recém-importada: a tarefa carrega `percentual_concluido` vindo do
    `pct_project` (services/cronograma_versao_service.py:615-622) e NUNCA teve
    apontamento. Alguém abre o RDO do dia e aponta — em rascunho.

    Antes, o rascunho sobrescrevia com o valor dele. Agora ele não conta — mas
    "não contar" tem de significar **deixar como estava**, e não zerar. Zerar
    apagaria o avanço importado e é o bug que a guarda de
    `atualizar_percentual_tarefa` existe para impedir desde o primeiro registro
    de efetivo de terceiro.
    """
    from utils.cronograma_engine import atualizar_percentual_tarefa

    t = _tarefa(ctx)
    t.percentual_concluido = 40.0   # carga inicial do MS Project
    db.session.commit()

    r = _rdo_rascunho(ctx)
    registrar_apontamento(r, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    db.session.commit()

    atualizar_percentual_tarefa(t.id, ctx['admin_id'])

    assert _pct(t.id) == pytest.approx(40.0), (
        'rascunho não conta — mas não contar é NÃO MEXER, não é zerar o '
        'avanço que veio da importação')
