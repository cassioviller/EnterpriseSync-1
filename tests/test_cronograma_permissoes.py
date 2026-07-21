"""M10 Task 3 — permissões das rotas de importação de cronograma (spec §15).

Tabela completa das 12 rotas de `views/cronograma_importacao.py` × três
atores que NÃO podem operá-las:

| ator                     | esperado | quem barra                          |
|--------------------------|----------|-------------------------------------|
| anônimo                  | 401      | `cronograma_import_required`        |
| funcionário do tenant    | 403      | `cronograma_import_required` (tipo) |
| admin de OUTRO tenant    | 404      | escopo por `admin_id` na rota       |

O 404 (e não 403) para o tenant vizinho é deliberado: a existência de uma
obra/importação alheia não vaza. As rotas novas usam o decorator REAL do
M01 — os bypasses legados de `decorators.py` não valem aqui (travados por
`test_cronograma_import_decorator.py`).

NOTA de harness: requests dos test clients ficam FORA de app_context
aberto (Flask-Login cacheia `g._login_user` e "congela" o primeiro usuário
resolvido) — mesma disciplina dos fechos M05/M07/M08.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    CronogramaTarefaMapeamento,
    CronogramaVersao,
    TipoUsuario,
    Usuario,
)
from test_cronograma_endpoints_m05 import _client_como, _imp_normalizada
from test_cronograma_versao_service import _ambiente, _nt, _tarefa

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-permissoes-cronograma'
    yield


def _funcionario(admin_id):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'func_{suf}', email=f'func_{suf}@test.local',
        nome=f'Func {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _super_admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'super_{suf}', email=f'super_{suf}@test.local',
        nome=f'Super {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.SUPER_ADMIN, ativo=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _cenario():
    """Tenant A com obra, importação reconciliada, versão e mapeamento;
    tenant B (vizinho) e um funcionário de A. Devolve só ids."""
    with app.app_context():
        admin, obra = _ambiente()
        _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
        imp = _imp_normalizada(obra, admin,
                               _nt('uid:1', 'Fundação', uid=1),
                               _nt('uid:2', 'Alvenaria', uid=2))
        versao = CronogramaVersao.query.filter_by(obra_id=obra.id).first()
        if versao is None:
            versao = CronogramaVersao(obra_id=obra.id, admin_id=admin.id,
                                      numero=1, status='ativa',
                                      observacao='cenário de permissões')
            db.session.add(versao)
            db.session.commit()
        func = _funcionario(admin.id)
        vizinho, _obra_b = _ambiente()
        ctx = {'admin_id': admin.id, 'obra_id': obra.id, 'imp_id': imp.id,
               'versao_id': versao.id, 'func_id': func.id,
               'vizinho_id': vizinho.id}

    # Reconcilia como dono para materializar um mapeamento real.
    c = _client_como(ctx['admin_id'])
    r = c.post(f"/obras/{ctx['obra_id']}/cronograma/importacoes/"
               f"{ctx['imp_id']}/reconciliar")
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        mp = CronogramaTarefaMapeamento.query.filter_by(
            importacao_id=ctx['imp_id']).first()
        ctx['mapeamento_id'] = mp.id if mp else None
    assert ctx['mapeamento_id'] is not None
    return ctx


def _rotas(ctx):
    """(método, url, corpo_json) das 12 rotas, com ids que EXISTEM em A."""
    base = f"/obras/{ctx['obra_id']}/cronograma"
    imp = f"{base}/importacoes/{ctx['imp_id']}"
    return [
        ('post', f'{base}/importacoes', None),
        ('post', f'{imp}/reconciliar', None),
        ('get', f'{imp}/diff', None),
        ('patch', f"{imp}/mapeamentos/{ctx['mapeamento_id']}",
         {'acao': 'casar', 'chave_nova': 'uid:2'}),
        ('post', f'{imp}/aplicar', None),
        ('post', f"{base}/versoes/{ctx['versao_id']}/restaurar", None),
        ('get', f'{base}/importacoes', None),
        ('get', f'{base}/versoes', None),
        ('get', f'{imp}/status', None),
        ('post', f'{imp}/cancelar', None),
        ('get', f'{imp}/previa', None),
        ('get', f'{imp}/resultado', None),
    ]


def _chamar(client, metodo, url, corpo):
    fn = getattr(client, metodo)
    return fn(url, json=corpo) if corpo is not None else fn(url)


# ---------------------------------------------------------------------------
# A tabela
# ---------------------------------------------------------------------------

def test_anonimo_recebe_401_em_todas_as_rotas():
    ctx = _cenario()
    anon = app.test_client()
    for metodo, url, corpo in _rotas(ctx):
        r = _chamar(anon, metodo, url, corpo)
        assert r.status_code == 401, f'{metodo.upper()} {url} → {r.status_code}'


def test_funcionario_do_proprio_tenant_recebe_403():
    """Importar/substituir cronograma é operação administrativa."""
    ctx = _cenario()
    c = _client_como(ctx['func_id'])
    for metodo, url, corpo in _rotas(ctx):
        r = _chamar(c, metodo, url, corpo)
        assert r.status_code == 403, f'{metodo.upper()} {url} → {r.status_code}'


def test_admin_de_outro_tenant_recebe_404_sem_vazar_existencia():
    ctx = _cenario()
    c = _client_como(ctx['vizinho_id'])
    for metodo, url, corpo in _rotas(ctx):
        r = _chamar(c, metodo, url, corpo)
        assert r.status_code == 404, f'{metodo.upper()} {url} → {r.status_code}'
        # 404 uniforme: o corpo não diz se a obra/importação existe alhures.
        corpo_txt = r.get_data(as_text=True).lower()
        assert 'traceback' not in corpo_txt


def test_super_admin_nao_alcanca_dados_de_tenant():
    """SUPER_ADMIN passa o decorator (tipo permitido), mas get_tenant_admin_id
    devolve o id DELE — não há travessia para o tenant do admin."""
    ctx = _cenario()
    with app.app_context():
        sid = _super_admin().id
    c = _client_como(sid)
    for metodo, url, corpo in _rotas(ctx):
        r = _chamar(c, metodo, url, corpo)
        assert r.status_code == 404, f'{metodo.upper()} {url} → {r.status_code}'


# ---------------------------------------------------------------------------
# Objetos filhos: o id do vizinho não atravessa nem dentro da própria obra
# ---------------------------------------------------------------------------

def test_mapeamento_de_outra_importacao_nao_e_aceito():
    """PATCH com mapeamento_id válido, mas de OUTRA importação → 404."""
    a = _cenario()
    b = _cenario()
    c = _client_como(a['admin_id'])
    url = (f"/obras/{a['obra_id']}/cronograma/importacoes/{a['imp_id']}"
           f"/mapeamentos/{b['mapeamento_id']}")
    r = c.patch(url, json={'acao': 'casar', 'chave_nova': 'uid:2'})
    assert r.status_code == 404


def test_versao_de_outra_obra_nao_restaura():
    a = _cenario()
    b = _cenario()
    c = _client_como(a['admin_id'])
    r = c.post(f"/obras/{a['obra_id']}/cronograma/versoes/"
               f"{b['versao_id']}/restaurar")
    assert r.status_code == 404


def test_importacao_de_outra_obra_do_mesmo_tenant_nao_e_alcancavel():
    """Mesmo dono, obras diferentes: o escopo é por obra, não só por tenant."""
    ctx = _cenario()
    with app.app_context():
        from test_cronograma_versao_service import _ambiente as _amb
        _admin2, outra_obra = _amb()
        outra_obra_id = outra_obra.id
    c = _client_como(ctx['admin_id'])
    r = c.get(f"/obras/{outra_obra_id}/cronograma/importacoes/"
              f"{ctx['imp_id']}/diff")
    assert r.status_code == 404
