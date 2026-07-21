"""M05 Task 3 — restauração de versão por snapshot (rollback).

Propriedade central (§ plano Task 3): aplicar vN+1 e restaurar vN devolve
as tarefas EXATAMENTE ao estado fotografado em vN — comparação por
reflexão sobre as colunas do snapshot, não por lista manual de campos.
"""
import os
import sys
from datetime import date

import pytest
from sqlalchemy import inspect as sa_inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    CronogramaImportacaoEvento,
    CronogramaTarefaSnapshot,
    CronogramaVersao,
    TarefaCronograma,
)
from services.cronograma_versao_service import (
    EstadoInvalido,
    aplicar_versao,
    restaurar_versao,
)
from test_cronograma_versao_service import (  # fixtures/helpers da Task 2
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
        app.secret_key = 'test-restaurar-versao'
    with app.app_context():
        yield


# Colunas do snapshot comparadas por reflexão. Excluídas apenas as de
# infraestrutura: id/versao_id (mudam por definição), admin_id (constante)
# e o self-FK de pai (comparado via mapeamento tarefa_id → tarefa_id).
_EXCLUIR = {'id', 'versao_id', 'admin_id', 'tarefa_pai_snapshot_id'}
_COLS = [c.key for c in sa_inspect(CronogramaTarefaSnapshot).columns
         if c.key not in _EXCLUIR]


def _foto(versao_id):
    """{tarefa_id: {coluna: valor}} + pai por tarefa_id, por reflexão."""
    snaps = CronogramaTarefaSnapshot.query.filter_by(
        versao_id=versao_id).all()
    por_snap_id = {s.id: s for s in snaps}
    out = {}
    for s in snaps:
        d = {c: getattr(s, c) for c in _COLS}
        pai = por_snap_id.get(s.tarefa_pai_snapshot_id)
        d['_pai_tarefa_id'] = pai.tarefa_id if pai else None
        out[s.tarefa_id] = d
    return out


def _cenario_com_v1():
    """Obra sem RDO, 3 tarefas com hierarquia/predecessora e versão nº1
    ativa (estilo backfill, ainda sem snapshot)."""
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Estrutura', ordem=0, mpp_uid=1,
                 data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10),
                 duracao_dias=8)
    t2 = _tarefa(obra, admin, 'Painéis Térreo', ordem=1, mpp_uid=2,
                 tarefa_pai_id=t1.id, quantidade_total=120.0,
                 unidade_medida='m2')
    t3 = _tarefa(obra, admin, 'Montagem', ordem=2, mpp_uid=3,
                 tarefa_pai_id=t1.id, predecessora_id=t2.id)
    t2.percentual_concluido = 35.0
    v1 = CronogramaVersao(obra_id=obra.id, admin_id=admin.id, numero=1,
                          status='ativa', observacao='backfill inicial')
    db.session.add(v1)
    db.session.commit()
    return admin, obra, v1, t1, t2, t3


def test_round_trip_aplicar_e_restaurar_volta_ao_snapshot():
    admin, obra, v1, t1, t2, t3 = _cenario_com_v1()

    # vN+1: renomeia t1, remove t3, insere uma nova.
    imp, _ = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Estrutura Metálica Revisada', uid=1,
            inicio='2026-08-01', fim='2026-08-15', dias=11.0),
        _nt('uid:2', 'Painéis Térreo', uid=2, pai_chave='uid:1'),
        _nt('uid:9', 'Cobertura Nova', uid=9))
    v2 = aplicar_versao(imp.id, {}, admin.id)
    assert v2.numero == 2

    foto_v1 = _foto(v1.id)          # gerada pelo aplicar, antes das mudanças
    assert set(foto_v1) == {t1.id, t2.id, t3.id}

    v3 = restaurar_versao(v1.id, admin.id)
    assert v3.numero == 3
    assert v3.status == 'ativa'
    assert v3.observacao == 'rollback da v1'
    db.session.refresh(v2)
    assert v2.status == 'arquivada'

    # Reflexão: cada tarefa viva == snapshot de v1, coluna a coluna.
    vivas = {t.id: t for t in TarefaCronograma.query.filter_by(
        obra_id=obra.id, ativa=True).all()}
    assert set(vivas) == set(foto_v1)
    equivalencia = {          # coluna do snapshot → atributo da tarefa
        'nome_tarefa': 'nome_tarefa', 'ordem': 'ordem',
        'data_inicio': 'data_inicio', 'data_fim': 'data_fim',
        'duracao_dias': 'duracao_dias',
        'quantidade_total': 'quantidade_total',
        'unidade_medida': 'unidade_medida', 'is_marco': 'is_marco',
        'mpp_uid': 'mpp_uid', 'wbs_codigo': 'wbs_codigo',
        'percentual_concluido_no_momento': 'percentual_concluido',
    }
    for tid, snap in foto_v1.items():
        t = vivas[tid]
        for col, attr in equivalencia.items():
            assert getattr(t, attr) == snap[col], (
                f'tarefa {tid}: {attr} = {getattr(t, attr)!r}, '
                f'snapshot v1 tinha {snap[col]!r}')
        assert t.tarefa_pai_id == snap['_pai_tarefa_id']

    # Predecessora única reconstruída da lista tipada.
    db.session.refresh(t3)
    assert t3.predecessora_id == t2.id
    # A tarefa criada na v2 foi arquivada (nunca deletada).
    nova = TarefaCronograma.query.filter_by(
        obra_id=obra.id, nome_tarefa='Cobertura Nova').one()
    assert nova.ativa is False
    assert nova.arquivada_em is not None

    # Round-trip dos snapshots: a foto de v3 == foto de v1 (reflexão),
    # exceto pct (v3 fotografa o estado restaurado — igual por construção).
    foto_v3 = _foto(v3.id)
    assert foto_v1 == foto_v3


def test_restaurar_versao_ativa_ou_sem_snapshot_e_invalido():
    admin, obra, v1, *_ = _cenario_com_v1()
    # v1 está ativa: nada a restaurar.
    with pytest.raises(EstadoInvalido):
        restaurar_versao(v1.id, admin.id)
    # Versão arquivada mas sem foto: não restaurável.
    v1.status = 'arquivada'
    v0 = CronogramaVersao(obra_id=obra.id, admin_id=admin.id, numero=2,
                          status='ativa')
    db.session.add(v0)
    db.session.commit()
    with pytest.raises(EstadoInvalido):
        restaurar_versao(v1.id, admin.id)


def test_restaurar_nao_deleta_e_registra_evento():
    admin, obra, v1, t1, t2, t3 = _cenario_com_v1()
    imp, _ = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Estrutura', uid=1),
        _nt('uid:2', 'Painéis Térreo', uid=2, pai_chave='uid:1'))
    aplicar_versao(imp.id, {}, admin.id)   # arquiva t3 (removida)
    total_antes = TarefaCronograma.query.filter_by(obra_id=obra.id).count()

    restaurar_versao(v1.id, admin.id)

    assert TarefaCronograma.query.filter_by(
        obra_id=obra.id).count() == total_antes
    db.session.refresh(t3)
    assert t3.ativa is True                # reativada pela restauração
    assert t3.arquivada_em is None
    ev = CronogramaImportacaoEvento.query.filter_by(
        importacao_id=imp.id, evento='rollback').one()
    assert ev.detalhes['versao_alvo_numero'] == 1
    assert ev.detalhes['restauradas'] == 3
    # Exatamente uma versão ativa no fim (índice parcial respeitado).
    assert CronogramaVersao.query.filter_by(
        obra_id=obra.id, status='ativa').count() == 1
