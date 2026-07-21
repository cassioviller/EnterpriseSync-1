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


# ---------------------------------------------------------------------------
# Task 3 — cenário completo da baia: canônico → .mpp → aplicar →
# equivalência → rollback (spec §4.1; marker java: sobe a JVM/MPXJ)
# ---------------------------------------------------------------------------

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_BAIA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'fixtures', 'cronograma_fisico_financeiro_baias.json')
MPP_0607 = os.path.join(RAIZ, 'CRONOGRAMA 06.07.mpp')

from services.mpp_parser import java_disponivel  # noqa: E402

requer_java = pytest.mark.skipif(not java_disponivel(),
                                 reason='JVM indisponível')
requer_fixture = pytest.mark.skipif(
    not (os.path.exists(FIXTURE_BAIA) and os.path.exists(MPP_0607)),
    reason='fixture canônica ou CRONOGRAMA 06.07.mpp ausentes')


def _client_como(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@requer_java
@requer_fixture
@pytest.mark.java
def test_migracao_completa_da_baia_com_equivalencia_e_rollback(
        tmp_path, monkeypatch):
    import json

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))

    # 1) Criação inicial pela fixture canônica (101 tarefas, 19 RDOs).
    with app.app_context():
        admin, _ = _ambiente()
        aid = admin.id
        payload = json.load(open(FIXTURE_BAIA, encoding='utf-8'))
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        estado_a = capturar_estado(oid, aid)
        versao_pre = CronogramaVersao.query.filter_by(
            obra_id=oid, status='ativa').one()
        versao_pre_id = versao_pre.id
    assert estado_a['n_tarefas_ativas'] == 101
    assert len(estado_a['rdos']) == 19
    assert estado_a['n_apontamentos'] > 0

    # 2) Upload do .mpp REAL de origem pelo pipeline novo (M03).
    c = _client_como(aid)
    with open(MPP_0607, 'rb') as fh:
        r = c.post(f'/obras/{oid}/cronograma/importacoes',
                   data={'arquivo': (fh, 'CRONOGRAMA 06.07.mpp')},
                   content_type='multipart/form-data')
    assert r.status_code == 201, r.get_json()
    iid = r.get_json()['importacao_id']

    # 3) Reconciliação: mesma origem ⇒ matching alto (spec §16).
    r = c.post(f'/obras/{oid}/cronograma/importacoes/{iid}/reconciliar')
    assert r.status_code == 200, r.get_json()
    resumo = r.get_json()['resumo']
    casadas = resumo['exatas'] + resumo['renomeadas']
    assert casadas >= 90, f'matching baixo demais: {resumo}'
    assert resumo['removidas'] <= 3, resumo

    # 4) Decidir pendências programaticamente (equivalente assistido do
    # antigo REMAP): ambígua/revisão casa com o candidato de nome idêntico
    # (senão o de maior score); 'nova' envolvida em split/merge confirma.
    r = c.get(f'/obras/{oid}/cronograma/importacoes/{iid}/diff')
    mapeamentos = r.get_json()['mapeamentos']
    with app.app_context():
        nomes_atuais = {t.id: t.nome_tarefa for t in TarefaCronograma.query
                        .filter_by(obra_id=oid, is_cliente=False).all()}
    chaves_livres = [m['chave_nova'] for m in mapeamentos
                     if m['chave_nova'] and m['tarefa_atual_id'] is None]
    for m in mapeamentos:
        if not m['decisao_requerida'] or m['decisao']:
            continue
        if m['tarefa_atual_id'] is not None:
            candidatos = [c_['chave_nova'] for c_ in m['candidatos']] or \
                chaves_livres
            corpo = {'acao': 'casar', 'chave_nova': candidatos[0]}
        else:
            corpo = {'acao': 'nova'}
        rr = c.patch(f'/obras/{oid}/cronograma/importacoes/{iid}'
                     f"/mapeamentos/{m['id']}", json=corpo)
        assert rr.status_code == 200, rr.get_json()

    # 5) Aplicar ⇒ uids gravados, ids preservados.
    r = c.post(f'/obras/{oid}/cronograma/importacoes/{iid}/aplicar')
    assert r.status_code == 200, r.get_json()

    with app.app_context():
        estado_b = capturar_estado(oid, aid)
        vivas = (TarefaCronograma.query
                 .filter_by(obra_id=oid, is_cliente=False)
                 .filter(TarefaCronograma.ativa.is_(True)).all())
        com_uid = sum(1 for t in vivas if t.mpp_uid is not None)
    # Equivalência A≈B (gate §4.1.3): RDOs/apontamentos/fotos/percentuais.
    resultado = comparar_estados(estado_a, estado_b)
    assert resultado['equivalente'], resultado['divergencias']
    # Identidades gravadas para as próximas importações.
    assert com_uid >= 95, f'uids gravados: {com_uid}/101'

    # 6) Rollback ensaiado: restaurar a versão pré-migração e re-verificar.
    r = c.post(f'/obras/{oid}/cronograma/versoes/{versao_pre_id}/restaurar')
    assert r.status_code == 200, r.get_json()
    with app.app_context():
        estado_c = capturar_estado(oid, aid)
    resultado = comparar_estados(estado_a, estado_c)
    assert resultado['equivalente'], resultado['divergencias']
