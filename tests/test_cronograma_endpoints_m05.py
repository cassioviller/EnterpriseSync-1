"""M05 Task 4 — endpoints de reconciliação, decisão, aplicação e rollback.

POST .../importacoes/<iid>/reconciliar · GET .../diff ·
PATCH .../mapeamentos/<mid> · POST .../aplicar · POST .../versoes/<vid>/restaurar
Todos com cronograma_import_required + tenant-scope.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints no app
from app import app, db
from models import (
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    CronogramaTarefaMapeamento,
    CronogramaVersao,
    TarefaCronograma,
)
from test_cronograma_versao_service import _ambiente, _nt, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-endpoints-m05'
    with app.app_context():
        yield


def _client_como(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _imp_normalizada(obra, admin, *tarefas_norm):
    """Importação no estado 'normalizado' (saída do M03+M04) — o diff é
    responsabilidade do endpoint de reconciliação."""
    ts = list(tarefas_norm)
    for ordem, t in enumerate(ts):
        t['ordem'] = ordem
    imp = CronogramaImportacao(
        obra_id=obra.id,
        admin_id=admin.id,
        arquivo_nome='novo.xml',
        origem='upload_mspdi',
        status='normalizado',
        json_normalizado={'tarefas': ts},
        criado_por_id=admin.id,
    )
    db.session.add(imp)
    db.session.commit()
    return imp


def _base(obra, imp=None):
    b = f'/obras/{obra.id}/cronograma/importacoes'
    return b if imp is None else f'{b}/{imp.id}'


def test_fluxo_completo_reconciliar_diff_aplicar():
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp = _imp_normalizada(
        obra, admin,
        _nt('uid:1', 'Fundação Radier', uid=1),
        _nt('uid:2', 'Cobertura', uid=2))
    c = _client_como(admin.id)

    r = c.post(f'{_base(obra, imp)}/reconciliar')
    assert r.status_code == 200, r.get_json()
    corpo = r.get_json()
    assert corpo['status'] == 'aguardando_revisao'
    assert corpo['resumo']['renomeadas'] == 1
    assert corpo['resumo']['novas'] == 1
    assert corpo['pendencias'] == 0
    # Mapeamentos persistidos com ligação id_temp.
    mps = CronogramaTarefaMapeamento.query.filter_by(
        importacao_id=imp.id).all()
    assert len(mps) == 2
    assert all((mp.detalhes or {}).get('id_temp') is not None for mp in mps)
    assert CronogramaImportacaoEvento.query.filter_by(
        importacao_id=imp.id, evento='reconciliado').count() == 1

    r = c.get(f'{_base(obra, imp)}/diff')
    assert r.status_code == 200
    diff = r.get_json()
    assert diff['relatorio_diff']['resumo']['renomeadas'] == 1
    assert len(diff['mapeamentos']) == 2

    r = c.post(f'{_base(obra, imp)}/aplicar')
    assert r.status_code == 200, r.get_json()
    corpo = r.get_json()
    assert corpo['status'] == 'aplicado'
    db.session.refresh(t1)
    assert t1.nome_tarefa == 'Fundação Radier'
    versao = db.session.get(CronogramaVersao, corpo['versao_id'])
    assert versao.status == 'ativa'
    assert versao.numero == corpo['versao_numero']


def test_pendencia_bloqueia_aplicar_e_patch_resolve():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Pintura Interna', ordem=0,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10),
            duracao_dias=8)
    imp = _imp_normalizada(
        obra, admin,
        _nt('n1', 'Pintura Interna 1',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0),
        _nt('n2', 'Pintura Interna 2',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0))
    c = _client_como(admin.id)

    r = c.post(f'{_base(obra, imp)}/reconciliar')
    assert r.status_code == 200
    assert r.get_json()['pendencias'] == 1

    # Ambíguo NUNCA se auto-aplica.
    r = c.post(f'{_base(obra, imp)}/aplicar')
    assert r.status_code == 422
    assert r.get_json()['pendencias']

    pend = [m for m in CronogramaTarefaMapeamento.query.filter_by(
        importacao_id=imp.id).all()
        if (m.detalhes or {}).get('decisao_requerida')]
    assert len(pend) == 1
    mid = pend[0].id

    # Decisões malformadas.
    r = c.patch(f'{_base(obra, imp)}/mapeamentos/{mid}',
                json={'acao': 'explodir'})
    assert r.status_code == 422
    r = c.patch(f'{_base(obra, imp)}/mapeamentos/{mid}',
                json={'acao': 'casar'})
    assert r.status_code == 422

    r = c.patch(f'{_base(obra, imp)}/mapeamentos/{mid}',
                json={'acao': 'casar', 'chave_nova': 'n1'})
    assert r.status_code == 200
    corpo = r.get_json()
    assert corpo['decisao'] == {'acao': 'casar', 'chave_nova': 'n1'}
    assert corpo['origem_decisao'] == 'manual'
    assert CronogramaImportacaoEvento.query.filter_by(
        importacao_id=imp.id, evento='revisao_alterada').count() == 1

    r = c.post(f'{_base(obra, imp)}/aplicar')
    assert r.status_code == 200, r.get_json()
    nomes = sorted(t.nome_tarefa for t in TarefaCronograma.query.filter_by(
        obra_id=obra.id, ativa=True).all())
    assert nomes == ['Pintura Interna 1', 'Pintura Interna 2']


def test_patch_em_mapeamento_sem_pendencia_e_422():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp = _imp_normalizada(obra, admin, _nt('uid:1', 'Fundação', uid=1))
    c = _client_como(admin.id)
    c.post(f'{_base(obra, imp)}/reconciliar')
    mp = CronogramaTarefaMapeamento.query.filter_by(
        importacao_id=imp.id).one()
    r = c.patch(f'{_base(obra, imp)}/mapeamentos/{mp.id}',
                json={'acao': 'arquivar'})
    assert r.status_code == 422


def test_estados_invalidos():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp = _imp_normalizada(obra, admin, _nt('uid:1', 'Fundação', uid=1))
    c = _client_como(admin.id)

    # Diff antes de reconciliar; aplicar antes de reconciliar.
    assert c.get(f'{_base(obra, imp)}/diff').status_code == 409
    assert c.post(f'{_base(obra, imp)}/aplicar').status_code == 409

    # Reconciliar em status não-normalizado.
    imp.status = 'parseado'
    db.session.commit()
    assert c.post(f'{_base(obra, imp)}/reconciliar').status_code == 409
    imp.status = 'normalizado'
    db.session.commit()

    c.post(f'{_base(obra, imp)}/reconciliar')
    assert c.post(f'{_base(obra, imp)}/aplicar').status_code == 200
    # Aplicada: reconciliar e aplicar de novo falham limpo.
    assert c.post(f'{_base(obra, imp)}/reconciliar').status_code == 409
    assert c.post(f'{_base(obra, imp)}/aplicar').status_code == 409


def test_tenant_scope_e_autenticacao():
    admin, obra = _ambiente()
    outro_admin, outra_obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp = _imp_normalizada(obra, admin, _nt('uid:1', 'Fundação', uid=1))

    # Outro tenant: 404 em todas (nem existência é revelada).
    c2 = _client_como(outro_admin.id)
    assert c2.post(f'{_base(obra, imp)}/reconciliar').status_code == 404
    assert c2.get(f'{_base(obra, imp)}/diff').status_code == 404
    assert c2.post(f'{_base(obra, imp)}/aplicar').status_code == 404
    assert c2.post(f'/obras/{obra.id}/cronograma/versoes/1/restaurar'
                   ).status_code == 404

    # Sem login: 401 — validado direto no decorator (test_request_context),
    # como em test_cronograma_import_decorator: um request anônimo via
    # test_client congela o estado de autenticação do processo (bypass
    # legado de dev) e derrubaria os testes seguintes da suíte.
    from decorators import cronograma_import_required

    @cronograma_import_required
    def _protegida():
        return 'ok'

    from flask_login import logout_user
    with app.test_request_context(f'{_base(obra, imp)}/reconciliar'):
        logout_user()
        resp, status = _protegida()
        assert status == 401


def test_restaurar_endpoint():
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    v1 = CronogramaVersao(obra_id=obra.id, admin_id=admin.id, numero=1,
                          status='ativa', observacao='backfill inicial')
    db.session.add(v1)
    db.session.commit()
    imp = _imp_normalizada(
        obra, admin, _nt('uid:1', 'Fundação Revisada', uid=1))
    c = _client_como(admin.id)
    c.post(f'{_base(obra, imp)}/reconciliar')
    assert c.post(f'{_base(obra, imp)}/aplicar').status_code == 200
    db.session.refresh(t1)
    assert t1.nome_tarefa == 'Fundação Revisada'

    r = c.post(f'/obras/{obra.id}/cronograma/versoes/{v1.id}/restaurar')
    assert r.status_code == 200, r.get_json()
    corpo = r.get_json()
    assert corpo['restaurada_de'] == 1
    db.session.refresh(t1)
    assert t1.nome_tarefa == 'Fundação'

    # Restaurar a versão já ativa: 409.
    ativa_id = corpo['versao_id']
    r = c.post(f'/obras/{obra.id}/cronograma/versoes/{ativa_id}/restaurar')
    assert r.status_code == 409
