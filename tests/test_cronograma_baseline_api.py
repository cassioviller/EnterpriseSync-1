"""Fase 4 (editor v2) — linha de base do cronograma (plano Step D).

Cobre as rotas `/baseline`, `/baselines`, `/baseline/<id>/ativar` e
`DELETE /baseline/<id>`:

  * criar congela as datas das tarefas datáveis e nasce ativa;
  * a baseline é IMUTÁVEL — editar a tarefa depois muda a tarefa, não o
    congelado (é isso que torna o desvio uma medida honesta de atraso);
  * "uma ativa por obra", em código E no banco (índice único parcial);
  * tarefa sem datas é ignorada; obra sem nenhuma datável → 400 verbatim;
  * escopo por obra/tenant/modo, flag off → 404;
  * o `GET` da página injeta `baseline_map` só quando há baseline ativa.

NOTA de harness (mesma disciplina de `test_cronograma_vinculos_api.py`):
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
    CronogramaBaseline,
    CronogramaBaselineItem,
    Obra,
    TarefaCronograma,
    Usuario,
)
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _tarefa

pytestmark = pytest.mark.integration

MSG_SEM_TAREFAS = 'Não há tarefas com datas para congelar na linha de base'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-baseline-cronograma'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool) -> None:
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()


def _cenario(flag: bool = True, sem_datas: bool = False) -> dict:
    """Obra com duas folhas datadas (A 01→07/07, B 01→03/07).

    `sem_datas=True` deixa as duas sem início/fim — nada a congelar.
    """
    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, flag)
        kw_a = dict(duracao_dias=5, data_inicio=date(2026, 7, 1),
                    data_fim=date(2026, 7, 7))
        kw_b = dict(duracao_dias=3, data_inicio=date(2026, 7, 1),
                    data_fim=date(2026, 7, 3))
        if sem_datas:
            kw_a = dict(duracao_dias=5, data_inicio=None, data_fim=None)
            kw_b = dict(duracao_dias=3, data_inicio=None, data_fim=None)
        a = _tarefa(obra, admin, 'Fundação', ordem=0, **kw_a)
        b = _tarefa(obra, admin, 'Alvenaria', ordem=1, **kw_b)
        return {'admin_id': admin.id, 'obra_id': obra.id,
                'a_id': a.id, 'b_id': b.id}


def _base(ctx) -> str:
    return f"/cronograma/obra/{ctx['obra_id']}"


def _itens(baseline_id: int) -> dict:
    with app.app_context():
        return {i.tarefa_id: i for i in CronogramaBaselineItem.query
                .filter_by(baseline_id=baseline_id).all()}


# ---------------------------------------------------------------------------
# Criar
# ---------------------------------------------------------------------------

def test_criar_baseline_congela_datas_e_nasce_ativa():
    """(1) Todas as tarefas datáveis entram, com as datas do momento."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/baseline", json={'nome': 'Plano inicial'})
    assert r.status_code == 201, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['baseline']['nome'] == 'Plano inicial'
    assert corpo['baseline']['ativa'] is True
    assert corpo['baseline']['total_itens'] == 2
    assert corpo['baseline_map'][str(ctx['a_id'])]['data_fim'] == '2026-07-07'

    itens = _itens(corpo['baseline']['id'])
    assert itens[ctx['a_id']].data_inicio == date(2026, 7, 1)
    assert itens[ctx['a_id']].data_fim == date(2026, 7, 7)
    assert itens[ctx['a_id']].duracao_dias == 5
    assert itens[ctx['b_id']].data_fim == date(2026, 7, 3)


def test_nome_default_quando_omitido():
    """(1) Nome sugerido com a data de hoje."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/baseline", json={})
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()['baseline']['nome'] == \
        f"Linha de base {date.today().strftime('%d/%m/%Y')}"


def test_baseline_nao_muda_quando_a_tarefa_e_editada_depois():
    """(2) O congelado é imutável — é o que torna o desvio honesto."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/baseline", json={})
    bid = r.get_json()['baseline']['id']

    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}", json={'duracao_dias': 10})
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(TarefaCronograma, ctx['a_id']).data_fim == \
            date(2026, 7, 14)
    # a baseline continua com o fim antigo → desvio de 5 dias corridos
    assert _itens(bid)[ctx['a_id']].data_fim == date(2026, 7, 7)


def test_obra_sem_tarefa_datavel_400():
    """(7) Sem datas não há o que congelar."""
    ctx = _cenario(sem_datas=True)
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/baseline", json={})
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_SEM_TAREFAS
    with app.app_context():
        assert CronogramaBaseline.query.filter_by(obra_id=ctx['obra_id']).count() == 0


def test_tarefa_arquivada_fica_de_fora_do_congelamento():
    """(6) Tarefa excluída na grade (arquivada na Fase 3) não entra.

    O caso "sem datas" não é testado junto de propósito: qualquer rota que
    dispare o recálculo (a exclusão dispara) agenda a tarefa e ela deixa de
    ser sem-datas. Esse caminho é coberto por
    `test_obra_sem_tarefa_datavel_400`, que não recalcula.
    """
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.delete(f"{_base(ctx)}/tarefa/{ctx['b_id']}").status_code == 200

    r = c.post(f"{_base(ctx)}/baseline", json={})
    assert r.status_code == 201, r.get_data(as_text=True)
    itens = _itens(r.get_json()['baseline']['id'])
    assert set(itens) == {ctx['a_id']}


# ---------------------------------------------------------------------------
# Uma ativa por obra
# ---------------------------------------------------------------------------

def test_criar_com_ativar_false_mantem_a_anterior_ativa():
    """(3) Guardar sem trocar a comparação corrente."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    primeira = c.post(f"{_base(ctx)}/baseline", json={'nome': 'Um'}) \
        .get_json()['baseline']['id']
    r = c.post(f"{_base(ctx)}/baseline", json={'nome': 'Dois', 'ativar': False})
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()['baseline']['ativa'] is False
    assert r.get_json()['baseline_map'] == {}
    with app.app_context():
        ativas = CronogramaBaseline.query.filter_by(
            obra_id=ctx['obra_id'], ativa=True).all()
        assert [b.id for b in ativas] == [primeira]


def test_ativar_desativa_as_outras():
    """(4) Trocar a baseline usada na comparação."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    um = c.post(f"{_base(ctx)}/baseline", json={'nome': 'Um'}) \
        .get_json()['baseline']['id']
    dois = c.post(f"{_base(ctx)}/baseline", json={'nome': 'Dois', 'ativar': False}) \
        .get_json()['baseline']['id']

    r = c.post(f"{_base(ctx)}/baseline/{dois}/ativar")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['baseline']['ativa'] is True
    assert len(r.get_json()['baseline_map']) == 2
    with app.app_context():
        assert db.session.get(CronogramaBaseline, um).ativa is False
        assert db.session.get(CronogramaBaseline, dois).ativa is True


def test_indice_parcial_impede_duas_ativas_por_escrita_direta():
    """(5) A invariante é do banco, não só da aplicação."""
    from sqlalchemy.exc import IntegrityError
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.post(f"{_base(ctx)}/baseline", json={}).status_code == 201
    with app.app_context():
        db.session.add(CronogramaBaseline(
            obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
            nome='Clandestina', ativa=True, is_cliente=False))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Listar / excluir / escopo
# ---------------------------------------------------------------------------

def test_listar_baselines_mais_recente_primeiro():
    """(8) Histórico da obra."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    c.post(f"{_base(ctx)}/baseline", json={'nome': 'Um'})
    c.post(f"{_base(ctx)}/baseline", json={'nome': 'Dois'})
    r = c.get(f"{_base(ctx)}/baselines")
    assert r.status_code == 200, r.get_data(as_text=True)
    nomes = [b['nome'] for b in r.get_json()['baselines']]
    assert nomes == ['Dois', 'Um']
    assert [b['ativa'] for b in r.get_json()['baselines']] == [True, False]


def test_excluir_baseline_remove_os_itens():
    """(10) CASCADE nos itens."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    bid = c.post(f"{_base(ctx)}/baseline", json={}).get_json()['baseline']['id']
    r = c.delete(f"{_base(ctx)}/baseline/{bid}")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['baseline_map'] == {}   # não sobrou ativa
    with app.app_context():
        assert db.session.get(CronogramaBaseline, bid) is None
        assert CronogramaBaselineItem.query.filter_by(baseline_id=bid).count() == 0


def test_escopo_cross_tenant_404_opaco():
    """(8) Tenant vizinho com a flag ligada não enxerga a obra."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    bid = c.post(f"{_base(ctx)}/baseline", json={}).get_json()['baseline']['id']

    with app.app_context():
        vizinho, _obra_b = _ambiente()
        _flag_editor_v2(vizinho.id, True)
        vid = vizinho.id
    c2 = _client_como(vid)
    assert c2.post(f"{_base(ctx)}/baseline", json={}).status_code == 404
    assert c2.get(f"{_base(ctx)}/baselines").status_code == 404
    assert c2.post(f"{_base(ctx)}/baseline/{bid}/ativar").status_code == 404
    assert c2.delete(f"{_base(ctx)}/baseline/{bid}").status_code == 404


def test_rotas_de_baseline_nao_existem_com_flag_off():
    """(9) Fora do rollout a Fase 4 não existe."""
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    assert c.post(f"{_base(ctx)}/baseline", json={}).status_code == 404
    assert c.get(f"{_base(ctx)}/baselines").status_code == 404
    assert c.post(f"{_base(ctx)}/baseline/1/ativar").status_code == 404
    assert c.delete(f"{_base(ctx)}/baseline/1").status_code == 404


def test_baseline_do_interno_nao_vaza_para_o_plano_do_cliente():
    """(12) Pilhas separadas por modo."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    assert c.post(f"{_base(ctx)}/baseline", json={}).status_code == 201
    r = c.get(f"{_base(ctx)}/baselines?cliente=1")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['baselines'] == []


# ---------------------------------------------------------------------------
# Render da página
# ---------------------------------------------------------------------------

def test_pagina_injeta_baseline_map_so_quando_ha_ativa():
    """(11) Sem baseline a grade e o Gantt ficam exatamente como antes."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.get(_base(ctx))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'let BASELINE_MAP = {};' in html
    # "Desvio"/"desvio-val" também aparecem no JS (comentário e seletor) — a
    # asserção é sobre a MARCAÇÃO da coluna, não sobre o texto solto.
    assert 'td-perc desvio-val' not in html
    assert '>Desvio</th>' not in html

    assert c.post(f"{_base(ctx)}/baseline", json={}).status_code == 201
    r = c.get(_base(ctx))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f'"{ctx["a_id"]}"' in html.split('let BASELINE_MAP = ')[1][:400]
    assert '>Desvio</th>' in html
    assert html.count('td-perc desvio-val') == 2   # uma célula por tarefa
