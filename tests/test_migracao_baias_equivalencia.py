"""M09 — migração das baias: versionamento do importador e equivalência.

Parte 1 (Task 2): o importador físico-financeiro registra versão nº1 +
snapshots + CronogramaImportacao(origem='json_canonico'); reimport
canônico segue permitido em obra ainda-canônica; obra migrada pelo fluxo
novo (upload .xml/.mpp aplicado) recusa o caminho destrutivo.
Parte 2 (Task 3): cenário completo da baia — fixture canônica → upload do
.mpp real → reconciliar → aplicar → equivalência → rollback.

Asserts NOVOS somente aqui — os 46 testes de
test_importacao_fisico_financeiro.py não mudam (spec §19).
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints (upload M03 na Task 3)
from app import app, db
from models import (
    CronogramaImportacao,
    CronogramaTarefaSnapshot,
    CronogramaVersao,
    TarefaCronograma,
)
from scripts.verificar_equivalencia_obra import (
    capturar_estado,
    comparar_estados,
)
from services.importacao_fisico_financeiro import importar_fisico_financeiro
from test_cronograma_versao_service import _ambiente

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-migracao-baias'
    yield


def _payload_minimo(suf):
    return {
        '_meta': {'arquivo': f'canonico_{suf}.json'},
        'obra': {'nome': f'Obra Canonica {suf}',
                 'codigo_obra': f'CAN-{suf}',
                 'cliente': f'Cliente Canonico {suf}'},
        'contrato': {'valor_venda': 1000.0, 'data_inicio': '2026-07-01'},
        'cronograma_tarefas': [
            {'id': 1, 'nome': 'ETAPA A', 'nivel': 1,
             'inicio': '2026-07-01', 'fim': '2026-07-10', 'dias': 8,
             'pct_fisico': 0},
            {'id': 2, 'nome': 'Servico A1', 'nivel': 2,
             'inicio': '2026-07-01', 'fim': '2026-07-05', 'dias': 4,
             'pct_fisico': 50},
        ],
    }


def _importar(suf=None):
    with app.app_context():
        suf = suf or uuid.uuid4().hex[:8]
        admin, _ = _ambiente()
        res = importar_fisico_financeiro(_payload_minimo(suf), admin.id)
        return {'admin_id': admin.id, 'obra_id': res['obra_id'], 'suf': suf}


# ---------------------------------------------------------------------------
# Task 2 — registro de versão na criação inicial + recusa destrutiva
# ---------------------------------------------------------------------------

def test_importador_registra_versao_snapshots_e_importacao_canonica():
    ctx = _importar()
    with app.app_context():
        v = CronogramaVersao.query.filter_by(
            obra_id=ctx['obra_id'], status='ativa').one()
        assert v.numero == 1
        assert v.observacao == 'importação físico-financeira (json_canonico)'
        imp = db.session.get(CronogramaImportacao, v.importacao_id)
        assert imp.origem == 'json_canonico'
        assert imp.status == 'aplicado'
        assert imp.arquivo_nome.startswith('canonico_')
        n_snaps = CronogramaTarefaSnapshot.query.filter_by(
            versao_id=v.id).count()
        n_vivas = (TarefaCronograma.query
                   .filter_by(obra_id=ctx['obra_id'], is_cliente=False)
                   .filter(TarefaCronograma.ativa.is_(True)).count())
        assert n_snaps == n_vivas == 2


def test_reimport_canonico_em_obra_apenas_canonica_segue_permitido():
    ctx = _importar()
    with app.app_context():
        # Mesmo código de obra ⇒ reimport destrutivo clássico: permitido,
        # arquiva a versão nº1 e vira a nº2 (disciplina M05, sem DELETE).
        importar_fisico_financeiro(_payload_minimo(ctx['suf']),
                                   ctx['admin_id'])
        versoes = (CronogramaVersao.query
                   .filter_by(obra_id=ctx['obra_id'])
                   .order_by(CronogramaVersao.numero).all())
        assert [v.numero for v in versoes] == [1, 2]
        assert [v.status for v in versoes] == ['arquivada', 'ativa']


def test_recusa_reimport_destrutivo_em_obra_migrada():
    ctx = _importar()
    with app.app_context():
        # Simula a migração: versão aplicada por importação de UPLOAD.
        imp_nova = CronogramaImportacao(
            obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
            arquivo_nome='cronograma.xml', origem='upload_mspdi',
            status='aplicado')
        db.session.add(imp_nova)
        db.session.flush()
        ativa = CronogramaVersao.query.filter_by(
            obra_id=ctx['obra_id'], status='ativa').one()
        ativa.status = 'arquivada'
        db.session.add(CronogramaVersao(
            obra_id=ctx['obra_id'], admin_id=ctx['admin_id'], numero=2,
            status='ativa', importacao_id=imp_nova.id))
        db.session.commit()

        with pytest.raises(ValueError) as exc:
            importar_fisico_financeiro(_payload_minimo(ctx['suf']),
                                       ctx['admin_id'])
        assert 'aba Cronograma' in str(exc.value)
        db.session.rollback()
        # Nada mudou: obra continua com as 2 versões e as tarefas vivas.
        assert CronogramaVersao.query.filter_by(
            obra_id=ctx['obra_id']).count() == 2
        assert (TarefaCronograma.query
                .filter_by(obra_id=ctx['obra_id'], is_cliente=False)
                .filter(TarefaCronograma.ativa.is_(True)).count()) == 2
