"""Fase 1 (editor v2) — integração da API de vínculos tipados (plano E3).

Cobre o Step C do plano `2026-07-24-cronograma-fase1-plano.md`:

  * CRUD de vínculo (`/cronograma/obra/<id>/vinculo[...]`): criação com
    cascata, cross-tenant → 404, par duplicado → 400, ciclo → 400,
    auto-vínculo → 400, tarefa-resumo → 400, edição de tipo/lag, exclusão;
  * rotas de vínculo "não existem" (404) com a flag desligada;
  * PUT `duracao_dias` com flag on devolve a cascata em `tarefas_afetadas`;
  * PUT `data_inicio` de tarefa com apontamento de RDO → 400 (âncora);
  * PUT `predecessoras_texto` (formato Project) cria vínculos e congela
    `predecessora_id`;
  * DELETE de tarefa dispara recálculo (CASCADE mata os vínculos);
  * `/recalcular` despacha pelo flag (motor novo ↔ engine antigo);
  * dual-write com flag off: PUT `predecessora_id` espelha vínculo TI/0.

A flag é ligada/desligada por teste direto em
`ConfiguracaoEmpresa.cronograma_editor_v2` (a linha já existe: `_ambiente`
liga a flag do M08 via `definir_flag`, que cria a configuração).

NOTA de harness (mesma disciplina de `test_cronograma_permissoes.py`):
requests dos test clients ficam FORA de app_context aberto — Flask-Login
cacheia `g._login_user` e congela o primeiro usuário resolvido.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    ConfiguracaoEmpresa,
    Obra,
    TarefaCronograma,
    TarefaVinculo,
    Usuario,
)
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import (
    _ambiente,
    _rdo_com_apontamento,
    _tarefa,
)

pytestmark = pytest.mark.integration

MSG_INICIO_CONGELADO = ('Tarefa já iniciada por apontamento de RDO — '
                        'o início não pode ser alterado')


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-vinculos-cronograma'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool) -> None:
    """Liga/desliga a flag DIRETO na coluna (plano E3)."""
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()


def _cenario(flag: bool = True, com_vinculo: bool = False) -> dict:
    """Tenant novo com obra e duas folhas raiz:

        linha 1 — 'Fundação'  A: 01/07/2026 (qua), 5 dias úteis → fim 07/07
        linha 2 — 'Alvenaria' B: 01/07/2026, 3 dias úteis

    `com_vinculo=True` já grava A →TI/0→ B em tarefa_vinculo (sem recálculo).
    """
    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, flag)
        a = _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=5,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        b = _tarefa(obra, admin, 'Alvenaria', ordem=1, duracao_dias=3,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 3))
        ctx = {'admin_id': admin.id, 'obra_id': obra.id,
               'a_id': a.id, 'b_id': b.id}
        if com_vinculo:
            v = TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                              predecessora_id=a.id, sucessora_id=b.id,
                              tipo='TI', lag_dias=0)
            db.session.add(v)
            db.session.commit()
            ctx['vinculo_id'] = v.id
    return ctx


def _base(ctx) -> str:
    return f"/cronograma/obra/{ctx['obra_id']}"


def _por_id(lista: list, tarefa_id: int) -> dict | None:
    return next((t for t in lista if t['id'] == tarefa_id), None)


# ---------------------------------------------------------------------------
# CRUD de vínculo (C4)
# ---------------------------------------------------------------------------

def test_criar_vinculo_ok_devolve_cascata():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['b_id'],
        'tipo': 'TI', 'lag_dias': 0,
    })
    assert r.status_code == 201, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert corpo['vinculo']['tipo'] == 'TI'
    assert corpo['vinculo']['lag_dias'] == 0

    b = _por_id(corpo['tarefas_afetadas'], ctx['b_id'])
    assert b is not None, corpo['tarefas_afetadas']
    assert b['data_inicio'] == '2026-07-08'   # dia útil após o fim de A (07/07)
    assert b['data_fim'] == '2026-07-10'
    assert b['predecessoras_texto'] == '1'    # linha visual de A, TI/0 canônico

    with app.app_context():
        assert TarefaVinculo.query.filter_by(
            predecessora_id=ctx['a_id'], sucessora_id=ctx['b_id']).count() == 1


def test_criar_vinculo_cross_tenant_devolve_404_opaco():
    ctx = _cenario()
    with app.app_context():
        vizinho, _obra_b = _ambiente()
        _flag_editor_v2(vizinho.id, True)   # flag ligada: o 404 é do escopo
        vid = vizinho.id
    c = _client_como(vid)
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['b_id'],
    })
    assert r.status_code == 404
    with app.app_context():
        assert TarefaVinculo.query.filter_by(obra_id=ctx['obra_id']).count() == 0


def test_criar_vinculo_par_duplicado_400():
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['b_id'],
        'tipo': 'II', 'lag_dias': 3,
    })
    assert r.status_code == 400
    assert 'já existe' in r.get_json()['msg']


def test_criar_vinculo_ciclo_400_sem_persistir():
    ctx = _cenario(com_vinculo=True)   # A → B
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['b_id'], 'sucessora_id': ctx['a_id'],
    })
    assert r.status_code == 400
    assert 'ciclo' in r.get_json()['msg']
    with app.app_context():
        # rollback: o vínculo que fecharia o ciclo não foi gravado
        assert TarefaVinculo.query.filter_by(
            predecessora_id=ctx['b_id'], sucessora_id=ctx['a_id']).count() == 0


def test_criar_vinculo_auto_referencia_400():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['a_id'],
    })
    assert r.status_code == 400
    assert 'predecessora dela mesma' in r.get_json()['msg']


def test_criar_vinculo_com_tarefa_resumo_400():
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        # 'Fundação' (A) vira tarefa-resumo ao ganhar uma filha
        _tarefa(obra, admin, 'Escavação', ordem=2, tarefa_pai_id=ctx['a_id'])
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['b_id'],
    })
    assert r.status_code == 400
    assert 'tarefa-resumo' in r.get_json()['msg']


def test_atualizar_vinculo_tipo_e_lag_recalcula():
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/vinculo/{ctx['vinculo_id']}",
              json={'tipo': 'II', 'lag_dias': 2})
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['vinculo']['tipo'] == 'II'
    assert corpo['vinculo']['lag_dias'] == 2
    b = _por_id(corpo['tarefas_afetadas'], ctx['b_id'])
    assert b is not None
    # II+2: início de B = início de A (01/07 qua) + 2 dias úteis = 03/07
    assert b['data_inicio'] == '2026-07-03'


def test_excluir_vinculo_remove_e_recalcula():
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.delete(f"{_base(ctx)}/vinculo/{ctx['vinculo_id']}")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert 'tarefas_afetadas' in corpo
    with app.app_context():
        assert db.session.get(TarefaVinculo, ctx['vinculo_id']) is None


def test_rotas_de_vinculo_nao_existem_com_flag_off():
    ctx = _cenario(flag=False, com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r_post = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['b_id']})
    r_put = c.put(f"{_base(ctx)}/vinculo/{ctx['vinculo_id']}",
                  json={'lag_dias': 1})
    r_del = c.delete(f"{_base(ctx)}/vinculo/{ctx['vinculo_id']}")
    assert (r_post.status_code, r_put.status_code, r_del.status_code) == (404, 404, 404)


# ---------------------------------------------------------------------------
# Rotas de tarefa com flag on (C3)
# ---------------------------------------------------------------------------

def test_put_duracao_com_flag_on_devolve_cascata():
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}", json={'duracao_dias': 10})
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert corpo['tarefa']['duracao_dias'] == 10
    # compatibilidade: lista completa continua na resposta
    assert {t['id'] for t in corpo['tarefas']} >= {ctx['a_id'], ctx['b_id']}
    b = _por_id(corpo['tarefas_afetadas'], ctx['b_id'])
    assert b is not None, corpo['tarefas_afetadas']
    # A: 01/07 + 10 dias úteis → fim 14/07; B (TI/0) começa 15/07
    assert b['data_inicio'] == '2026-07-15'
    assert b['data_fim'] == '2026-07-17'


def test_put_data_inicio_de_tarefa_com_apontamento_400():
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        a = db.session.get(TarefaCronograma, ctx['a_id'])
        _rdo_com_apontamento(obra, admin, a)
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}",
              json={'data_inicio': '2026-07-20'})
    assert r.status_code == 400, r.get_data(as_text=True)
    assert r.get_json()['msg'] == MSG_INICIO_CONGELADO
    with app.app_context():
        assert db.session.get(TarefaCronograma, ctx['a_id']).data_inicio == date(2026, 7, 1)


def test_put_predecessoras_texto_cria_vinculo_e_congela_predecessora_id():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['b_id']}",
              json={'predecessoras_texto': '1TI+2'})
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['tarefa']['predecessoras_texto'] == '1TI+2'
    b = _por_id(corpo['tarefas_afetadas'], ctx['b_id'])
    assert b is not None
    # fim de A 07/07 + (1 + lag 2) dias úteis = 10/07
    assert b['data_inicio'] == '2026-07-10'
    with app.app_context():
        v = TarefaVinculo.query.filter_by(sucessora_id=ctx['b_id']).one()
        assert (v.predecessora_id, v.tipo, v.lag_dias) == (ctx['a_id'], 'TI', 2)
        # coluna legada congelada — o motor novo lê só tarefa_vinculo
        assert db.session.get(TarefaCronograma, ctx['b_id']).predecessora_id is None


def test_put_predecessoras_texto_linha_inexistente_400():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['b_id']}",
              json={'predecessoras_texto': '99'})
    assert r.status_code == 400
    assert r.get_json()['msg'] == 'Linha 99 não existe na grade'
    with app.app_context():
        assert TarefaVinculo.query.filter_by(sucessora_id=ctx['b_id']).count() == 0


def test_delete_tarefa_cascateia_vinculos_e_recalcula():
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.delete(f"{_base(ctx)}/tarefa/{ctx['a_id']}")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert 'tarefas_afetadas' in corpo          # recálculo do motor novo rodou
    assert _por_id(corpo['tarefas'], ctx['a_id']) is None
    with app.app_context():
        # ondelete=CASCADE: o vínculo morreu junto com a tarefa
        assert TarefaVinculo.query.filter_by(obra_id=ctx['obra_id']).count() == 0


# ---------------------------------------------------------------------------
# /recalcular despacha pelo flag
# ---------------------------------------------------------------------------

def test_recalcular_usa_motor_novo_com_flag_on():
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/recalcular")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert 'tarefas_afetadas' in corpo          # assinatura do motor novo
    b = _por_id(corpo['tarefas'], ctx['b_id'])
    assert b['data_inicio'] == '2026-07-08'     # cascata TI/0 aplicada


def test_recalcular_usa_engine_antigo_com_flag_off():
    ctx = _cenario(flag=False, com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/recalcular")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    # resposta byte-compatível com hoje: sem a chave nova do motor
    assert 'tarefas_afetadas' not in corpo
    # engine antigo ignora tarefa_vinculo (B sem predecessora_id fica em 01/07)
    b = _por_id(corpo['tarefas'], ctx['b_id'])
    assert b['data_inicio'] == '2026-07-01'


# ---------------------------------------------------------------------------
# Dual-write com flag off (C3 — tabela fresca para quando a flag ligar)
# ---------------------------------------------------------------------------

def test_dual_write_put_predecessora_id_cria_vinculo_ti0():
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['b_id']}",
              json={'predecessora_id': ctx['a_id']})
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert 'tarefas_afetadas' not in corpo      # resposta legada intocada
    with app.app_context():
        b = db.session.get(TarefaCronograma, ctx['b_id'])
        assert b.predecessora_id == ctx['a_id']  # coluna legada continua dona
        v = TarefaVinculo.query.filter_by(sucessora_id=ctx['b_id']).one()
        assert (v.predecessora_id, v.tipo, v.lag_dias) == (ctx['a_id'], 'TI', 0)


def test_dual_write_remocao_de_predecessora_limpa_vinculo():
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    c.put(f"{_base(ctx)}/tarefa/{ctx['b_id']}",
          json={'predecessora_id': ctx['a_id']})
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['b_id']}",
              json={'predecessora_id': None})
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(TarefaCronograma, ctx['b_id']).predecessora_id is None
        assert TarefaVinculo.query.filter_by(sucessora_id=ctx['b_id']).count() == 0
