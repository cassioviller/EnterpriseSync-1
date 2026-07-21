"""Versão nº1 da obra cujo cronograma nasce FORA do fluxo de importação.

Buraco fechado aqui: `aplicar_versao` só fotografa o estado anterior
quando já existe versão ativa (`cronograma_versao_service.py`, "Snapshot
da versão ativa atual, se existir"). Uma obra criada por aprovação de
proposta ou pelo gate de revisão inicial não tinha versão nenhuma — logo
o PRIMEIRO import era irreversível: a versão nº1 nascia já com o estado
pós-import e o botão Restaurar não tinha destino.

O teste central é `test_primeiro_import_passa_a_ser_reversivel`: sem a
versão inicial ele falha por não haver estado anterior a restaurar.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    CronogramaTarefaSnapshot,
    CronogramaVersao,
    TarefaCronograma,
)
from services.cronograma_versao_service import (
    registrar_versao_inicial,
    restaurar_versao,
)
from test_cronograma_endpoints_m05 import _client_como, _imp_normalizada
from test_cronograma_versao_service import _ambiente, _nt, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-versao-inicial'
    yield


def _obra_materializada():
    """Obra com tarefas mas SEM versão — estado de quem nasceu de proposta."""
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1,
            data_inicio=date(2026, 8, 3), data_fim=date(2026, 8, 7))
    _tarefa(obra, admin, 'Alvenaria', ordem=1, mpp_uid=2,
            data_inicio=date(2026, 8, 10), data_fim=date(2026, 8, 14))
    assert CronogramaVersao.query.filter_by(obra_id=obra.id).count() == 0
    return admin, obra


# ---------------------------------------------------------------------------
# O helper
# ---------------------------------------------------------------------------

def test_registra_versao_um_com_snapshots():
    with app.app_context():
        admin, obra = _obra_materializada()
        versao = registrar_versao_inicial(
            obra.id, admin.id, observacao='cronograma inicial (teste)')
        db.session.commit()

        assert versao is not None
        assert versao.numero == 1
        assert versao.status == 'ativa'
        assert versao.importacao_id is None  # não veio de import
        snaps = CronogramaTarefaSnapshot.query.filter_by(
            versao_id=versao.id).all()
        assert len(snaps) == 2
        assert {s.nome_tarefa for s in snaps} == {'Fundação', 'Alvenaria'}
        # A foto preserva a identidade M04 e as datas do momento.
        por_nome = {s.nome_tarefa: s for s in snaps}
        assert por_nome['Fundação'].mpp_uid == 1
        assert por_nome['Fundação'].data_inicio == date(2026, 8, 3)


def test_e_idempotente_em_obra_ja_versionada():
    with app.app_context():
        admin, obra = _obra_materializada()
        registrar_versao_inicial(obra.id, admin.id, observacao='primeira')
        db.session.commit()

        assert registrar_versao_inicial(
            obra.id, admin.id, observacao='segunda') is None
        db.session.commit()
        versoes = CronogramaVersao.query.filter_by(obra_id=obra.id).all()
        assert len(versoes) == 1
        assert versoes[0].observacao == 'primeira'


def test_obra_sem_tarefas_nao_gera_versao_vazia():
    with app.app_context():
        admin, obra = _ambiente()
        assert registrar_versao_inicial(
            obra.id, admin.id, observacao='vazia') is None
        db.session.commit()
        assert CronogramaVersao.query.filter_by(obra_id=obra.id).count() == 0


def test_tarefa_do_cronograma_cliente_fica_fora_da_foto():
    with app.app_context():
        admin, obra = _obra_materializada()
        clone = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, nome_tarefa='Clone Cliente',
            ordem=2, duracao_dias=5, data_inicio=date(2026, 8, 3),
            data_fim=date(2026, 8, 7), is_cliente=True)
        db.session.add(clone)
        db.session.commit()

        versao = registrar_versao_inicial(
            obra.id, admin.id, observacao='só interno')
        db.session.commit()
        nomes = {s.nome_tarefa for s in CronogramaTarefaSnapshot.query
                 .filter_by(versao_id=versao.id).all()}
        assert nomes == {'Fundação', 'Alvenaria'}


# ---------------------------------------------------------------------------
# O que o buraco causava — regressão central
# ---------------------------------------------------------------------------

def test_primeiro_import_passa_a_ser_reversivel():
    """Obra nascida de materialização → import → Restaurar volta ao inicial.

    Sem a versão inicial, `aplicar_versao` criaria a nº1 já com o estado
    pós-import e não haveria versão anterior com snapshot para restaurar.
    """
    with app.app_context():
        admin, obra = _obra_materializada()
        registrar_versao_inicial(
            obra.id, admin.id,
            observacao='cronograma inicial (aprovação da proposta)')
        db.session.commit()
        # O import renomeia a primeira tarefa e insere uma terceira.
        imp = _imp_normalizada(
            obra, admin,
            _nt('uid:1', 'Fundação Radier', uid=1),
            _nt('uid:2', 'Alvenaria', uid=2),
            _nt('uid:9', 'Cobertura', uid=9))
        ctx = {'admin_id': admin.id, 'obra_id': obra.id, 'imp_id': imp.id}

    base = (f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}")
    c = _client_como(ctx['admin_id'])
    assert c.post(f'{base}/reconciliar').status_code == 200
    r = c.post(f'{base}/aplicar')
    assert r.status_code == 200, r.get_data(as_text=True)

    with app.app_context():
        # A aplicação virou a nº2 — a nº1 é o cronograma de nascimento.
        versoes = {v.numero: v for v in CronogramaVersao.query
                   .filter_by(obra_id=ctx['obra_id']).all()}
        assert set(versoes) == {1, 2}
        assert versoes[1].status == 'arquivada'
        assert versoes[2].status == 'ativa'
        # E a nº1 tem foto — é o que dá destino ao Restaurar.
        assert CronogramaTarefaSnapshot.query.filter_by(
            versao_id=versoes[1].id).count() == 2

        nomes_pos = sorted(t.nome_tarefa for t in TarefaCronograma.query
                           .filter_by(obra_id=ctx['obra_id'], ativa=True,
                                      is_cliente=False).all())
        assert nomes_pos == ['Alvenaria', 'Cobertura', 'Fundação Radier']

        # Rollback ao cronograma de nascimento.
        restaurar_versao(versoes[1].id, ctx['admin_id'])
        db.session.commit()
        nomes_final = sorted(t.nome_tarefa for t in TarefaCronograma.query
                             .filter_by(obra_id=ctx['obra_id'], ativa=True,
                                        is_cliente=False).all())
        assert nomes_final == ['Alvenaria', 'Fundação']


# ---------------------------------------------------------------------------
# Backfill 212
# ---------------------------------------------------------------------------

def test_migration_212_versiona_obra_orfa_e_e_idempotente():
    from migrations import _migration_212_backfill_versao_inicial_obras_novas

    with app.app_context():
        admin, obra = _obra_materializada()
        obra_id = obra.id
        db.session.commit()

    with app.app_context():
        _migration_212_backfill_versao_inicial_obras_novas()
        versoes = CronogramaVersao.query.filter_by(obra_id=obra_id).all()
        assert len(versoes) == 1
        assert versoes[0].numero == 1
        assert versoes[0].status == 'ativa'
        assert CronogramaTarefaSnapshot.query.filter_by(
            versao_id=versoes[0].id).count() == 2

    with app.app_context():
        _migration_212_backfill_versao_inicial_obras_novas()
        assert CronogramaVersao.query.filter_by(obra_id=obra_id).count() == 1
