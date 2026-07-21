"""M08 — interface de cronograma na obra: endpoints de apoio e páginas.

Task 1: listas de importações/versões, status (polling) e cancelamento —
sempre tenant-scoped, objeto de outra obra → 404.

NOTA de harness: os requests dos test clients rodam FORA de app_context
mantido aberto. Com um app context externo ativo, o Flask reutiliza o
mesmo `g` em todos os requests e o Flask-Login cacheia `g._login_user` —
o primeiro usuário resolvido "congela" para todos os clients (causa raiz
do fenômeno contornado nos fechos M05/M07; artefato de teste, não bug de
produção). Setup/asserts de banco entram em `with app.app_context()`
próprios; requests ficam do lado de fora.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    Obra,
)
from test_cronograma_versao_service import _ambiente, _nt, _tarefa
from test_cronograma_endpoints_m05 import _client_como, _imp_normalizada

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-interface-obra'
    yield


def _setup_obra_com_importacao(*tarefas_norm, tarefa_kw=None):
    """Cria admin/obra/tarefa + importação 'normalizado'. Devolve ids."""
    with app.app_context():
        admin, obra = _ambiente()
        _tarefa(obra, admin, tarefa_kw.pop('nome', 'Fundação')
                if tarefa_kw else 'Fundação',
                ordem=0, **(tarefa_kw or {'mpp_uid': 1}))
        imp = _imp_normalizada(obra, admin, *tarefas_norm)
        return {'admin_id': admin.id, 'obra_id': obra.id,
                'obra_nome': obra.nome, 'cliente_id': obra.cliente_id,
                'imp_id': imp.id}


def test_listas_importacoes_e_versoes_escopadas():
    ctx = _setup_obra_com_importacao(_nt('uid:1', 'Fundação', uid=1))
    with app.app_context():
        outro, _ = _ambiente()
        outro_id = outro.id

    base = f"/obras/{ctx['obra_id']}/cronograma"
    c = _client_como(ctx['admin_id'])
    assert c.post(f"{base}/importacoes/{ctx['imp_id']}/reconciliar"
                  ).status_code == 200
    assert c.post(f"{base}/importacoes/{ctx['imp_id']}/aplicar"
                  ).status_code == 200

    r = c.get(f'{base}/importacoes')
    assert r.status_code == 200
    corpo = r.get_json()
    assert corpo['obra_nome'] == ctx['obra_nome']
    assert len(corpo['importacoes']) == 1
    assert corpo['importacoes'][0]['status'] == 'aplicado'

    r = c.get(f'{base}/versoes')
    assert r.status_code == 200
    versoes = r.get_json()['versoes']
    assert len(versoes) == 1
    assert versoes[0]['status'] == 'ativa'
    assert versoes[0]['arquivo_nome'] == 'novo.xml'
    assert versoes[0]['n_snapshots'] == 1
    assert versoes[0]['restauravel'] is False       # ativa não se restaura

    # Outro tenant: 404 nas duas listas (client próprio, g por request).
    c2 = _client_como(outro_id)
    assert c2.get(f'{base}/importacoes').status_code == 404
    assert c2.get(f'{base}/versoes').status_code == 404


def test_lista_expoe_pendencias_da_revisao():
    ctx = _setup_obra_com_importacao(
        _nt('n1', 'Pintura Interna 1',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0),
        _nt('n2', 'Pintura Interna 2',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0),
        tarefa_kw={'nome': 'Pintura Interna',
                   'data_inicio': date(2026, 7, 1),
                   'data_fim': date(2026, 7, 10), 'duracao_dias': 8})
    c = _client_como(ctx['admin_id'])
    base = f"/obras/{ctx['obra_id']}/cronograma"
    c.post(f"{base}/importacoes/{ctx['imp_id']}/reconciliar")
    corpo = c.get(f'{base}/importacoes').get_json()
    linha = corpo['importacoes'][0]
    assert linha['status'] == 'aguardando_revisao'
    assert linha['pendencias'] == 1


def test_status_polling_e_cancelamento():
    ctx = _setup_obra_com_importacao(_nt('uid:1', 'Fundação', uid=1))
    c = _client_como(ctx['admin_id'])
    base = f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}"

    r = c.get(f'{base}/status')
    assert r.status_code == 200
    assert r.get_json() == {'importacao_id': ctx['imp_id'],
                            'status': 'normalizado', 'erro': None}

    # Cancelar em estado pré-aplicação: ok + evento.
    assert c.post(f'{base}/cancelar').status_code == 200
    with app.app_context():
        imp = db.session.get(CronogramaImportacao, ctx['imp_id'])
        assert imp.status == 'cancelado'
        assert CronogramaImportacaoEvento.query.filter_by(
            importacao_id=imp.id, evento='cancelado').count() == 1
    # Cancelar de novo: 409 (terminal).
    assert c.post(f'{base}/cancelar').status_code == 409


def test_cancelar_aplicada_e_409_e_outra_obra_404():
    ctx = _setup_obra_com_importacao(_nt('uid:1', 'Fundação', uid=1))
    c = _client_como(ctx['admin_id'])
    base = f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}"
    c.post(f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}"
           f'/reconciliar')
    c.post(f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}"
           f'/aplicar')
    assert c.post(f'{base}/cancelar').status_code == 409

    # Importação existente mas em OUTRA obra do MESMO tenant → 404.
    with app.app_context():
        outra = Obra(nome='Obra B', codigo=f"B-{ctx['obra_id']}",
                     admin_id=ctx['admin_id'], cliente_id=ctx['cliente_id'],
                     status='Em andamento', data_inicio=date(2026, 7, 1))
        db.session.add(outra)
        db.session.commit()
        outra_id = outra.id
    assert c.get(f"/obras/{outra_id}/cronograma/importacoes/{ctx['imp_id']}"
                 f'/status').status_code == 404


# ---------------------------------------------------------------------------
# Task 2 — seção na aba Cronograma da página da obra (atrás de flag)
# ---------------------------------------------------------------------------

def test_secao_visivel_para_v2_e_ausente_sem_v2():
    ctx = _setup_obra_com_importacao(_nt('uid:1', 'Fundação', uid=1))
    with app.app_context():
        from werkzeug.security import generate_password_hash
        from models import Cliente, TipoUsuario, Usuario
        import uuid
        suf = uuid.uuid4().hex[:8]
        v1 = Usuario(username=f'v1_{suf}', email=f'v1_{suf}@test.local',
                     nome='Admin V1',
                     password_hash=generate_password_hash('Senha@2026'),
                     tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                     versao_sistema='v1')
        db.session.add(v1)
        db.session.flush()
        cli = Cliente(admin_id=v1.id, nome=f'Cli {suf}',
                      email=f'c_{suf}@test.local', telefone='119')
        db.session.add(cli)
        db.session.flush()
        obra_v1 = Obra(nome=f'Obra V1 {suf}', codigo=f'V1-{suf}',
                       admin_id=v1.id, cliente_id=cli.id,
                       status='Em andamento', data_inicio=date(2026, 7, 1))
        db.session.add(obra_v1)
        db.session.commit()
        v1_id, obra_v1_id = v1.id, obra_v1.id

    # Admin V2: seção presente com o aviso de escopo por obra.
    c = _client_como(ctx['admin_id'])
    r = c.get(f"/obras/{ctx['obra_id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'secaoCronogramaMpp' in html
    assert 'altera somente a obra' in html
    assert 'cronograma_importacao.js' in html

    # Admin V1 (flag desligada): página renderiza SEM a seção.
    c2 = _client_como(v1_id)
    r = c2.get(f'/obras/{obra_v1_id}')
    assert r.status_code == 200
    assert 'secaoCronogramaMpp' not in r.get_data(as_text=True)
