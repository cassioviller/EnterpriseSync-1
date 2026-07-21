"""M10 Task 4 — métricas por importação e logs estruturados (spec §4.3).

As métricas NÃO ganham tabela nova: são consolidadas de
`cronograma_importacao_evento.detalhes` (trilha do M02) por
`services.cronograma_observabilidade.metricas_da_importacao`, e servidas
na lista da aba Cronograma (M08) para o suporte.

Cobre a jornada mínima upload→reconciliar→aplicar→rollback, sem JVM (a
importação entra já normalizada, como nos testes do M05).
"""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    CronogramaImportacaoEvento,
    CronogramaVersao,
)
from services.cronograma_observabilidade import (
    log_transicao,
    metricas_da_importacao,
)
from test_cronograma_endpoints_m05 import _client_como, _imp_normalizada
from test_cronograma_versao_service import _ambiente, _nt, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-metricas-cronograma'
    yield


def _cenario():
    """Obra com 2 tarefas, versão nº1 e importação que renomeia uma delas."""
    with app.app_context():
        admin, obra = _ambiente()
        _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
        _tarefa(obra, admin, 'Alvenaria', ordem=1, mpp_uid=2)
        imp = _imp_normalizada(
            obra, admin,
            _nt('uid:1', 'Fundação', uid=1),
            _nt('uid:2', 'Alvenaria Estrutural', uid=2))
        v1 = CronogramaVersao(obra_id=obra.id, admin_id=admin.id, numero=1,
                              status='ativa', observacao='backfill inicial')
        db.session.add(v1)
        db.session.commit()
        return {'admin_id': admin.id, 'obra_id': obra.id, 'imp_id': imp.id,
                'versao_inicial_id': v1.id}


def _base(ctx):
    return (f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}")


# ---------------------------------------------------------------------------
# Consolidação a partir dos eventos
# ---------------------------------------------------------------------------

def test_reconciliar_persiste_matching_auto_e_conflitos():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.post(f'{_base(ctx)}/reconciliar').status_code == 200

    with app.app_context():
        ev = CronogramaImportacaoEvento.query.filter_by(
            importacao_id=ctx['imp_id'], evento='reconciliado').one()
        det = ev.detalhes
        # Chaves ANTIGAS preservadas (nada renomeado — aditivo).
        assert 'resumo' in det and 'pendencias' in det
        # Chaves novas da §4.3.
        assert det['matches_por_nivel'] == {'mpp_uid': 2}
        assert det['n_auto'] == 2
        assert det['n_conflitos'] == 0

        m = metricas_da_importacao(ctx['imp_id'])
        assert m['matches_por_nivel'] == {'mpp_uid': 2}
        assert m['n_auto'] == 2
        assert m['n_conflitos'] == 0
        assert m['rollbacks'] == 0


def test_aplicar_registra_tempo_total_e_decisoes():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.post(f'{_base(ctx)}/reconciliar').status_code == 200
    assert c.post(f'{_base(ctx)}/aplicar').status_code == 200

    with app.app_context():
        m = metricas_da_importacao(ctx['imp_id'])
        assert m['tempo_total_ms'] is not None
        assert m['tempo_total_ms'] >= 0
        assert m['n_manuais'] == 0
        assert m['matches_por_nivel'] == {'mpp_uid': 2}


def test_rollback_incrementa_o_contador_da_importacao():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.post(f'{_base(ctx)}/reconciliar').status_code == 200
    assert c.post(f'{_base(ctx)}/aplicar').status_code == 200

    with app.app_context():
        assert metricas_da_importacao(ctx['imp_id'])['rollbacks'] == 0

    r = c.post(f"/obras/{ctx['obra_id']}/cronograma/versoes/"
               f"{ctx['versao_inicial_id']}/restaurar")
    assert r.status_code == 200, r.get_data(as_text=True)

    with app.app_context():
        m = metricas_da_importacao(ctx['imp_id'])
        assert m['rollbacks'] == 1
        ev = CronogramaImportacaoEvento.query.filter_by(
            importacao_id=ctx['imp_id'], evento='rollback').one()
        assert ev.detalhes['rollbacks'] == 1


def test_metricas_sao_parciais_enquanto_a_jornada_nao_termina():
    """Importação só normalizada: sem tempo_total_ms nem matching."""
    ctx = _cenario()
    with app.app_context():
        m = metricas_da_importacao(ctx['imp_id'])
        assert 'tempo_total_ms' not in m
        assert 'matches_por_nivel' not in m
        assert m['rollbacks'] == 0


# ---------------------------------------------------------------------------
# Exposição para o suporte (lista da aba Cronograma)
# ---------------------------------------------------------------------------

def test_lista_de_importacoes_expoe_as_metricas():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.post(f'{_base(ctx)}/reconciliar').status_code == 200
    assert c.post(f'{_base(ctx)}/aplicar').status_code == 200

    r = c.get(f"/obras/{ctx['obra_id']}/cronograma/importacoes")
    assert r.status_code == 200
    item = next(i for i in r.get_json()['importacoes']
                if i['id'] == ctx['imp_id'])
    assert 'metricas' in item
    assert item['metricas']['n_manuais'] == 0
    assert item['metricas']['tempo_total_ms'] is not None
    assert item['metricas']['matches_por_nivel'] == {'mpp_uid': 2}


# ---------------------------------------------------------------------------
# Log estruturado
# ---------------------------------------------------------------------------

def test_transicoes_logam_no_logger_cronograma_importacao(caplog):
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    with caplog.at_level(logging.INFO, logger='cronograma.importacao'):
        assert c.post(f'{_base(ctx)}/reconciliar').status_code == 200
        assert c.post(f'{_base(ctx)}/aplicar').status_code == 200

    linhas = [r.message for r in caplog.records
              if r.name == 'cronograma.importacao']
    assert any(f"evento=reconciliado importacao_id={ctx['imp_id']}" in ln
               for ln in linhas), linhas
    assert any(f"evento=aplicado importacao_id={ctx['imp_id']}" in ln
               for ln in linhas), linhas
    # Toda linha carrega o importacao_id — é a chave de busca do suporte.
    assert all('importacao_id=' in ln for ln in linhas)
    assert all(f"obra_id={ctx['obra_id']}" in ln for ln in linhas)


def test_log_transicao_nunca_levanta():
    class Explosivo:
        def __repr__(self):
            raise RuntimeError('boom')

    # Não deve propagar: observabilidade não derruba o fluxo de negócio.
    log_transicao('aplicado', 1, obra_id=2, campo=Explosivo())


def test_metricas_de_importacao_inexistente_e_vazia():
    with app.app_context():
        assert metricas_da_importacao(99_999_999) == {'rollbacks': 0}
