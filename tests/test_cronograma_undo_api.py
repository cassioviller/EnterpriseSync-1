"""Fase 3 (editor v2) — pilha de desfazer/refazer (plano Step F).

Cobre `services/cronograma_undo.py` + as rotas
`POST /cronograma/obra/<id>/desfazer` e `/refazer`:

  * desfazer/refazer de edição de célula, incluindo a cascata de datas;
  * a garantia central do diff POR CAMPO — desfazer não toca em campo que a
    ação não mexeu (um apontamento de RDO entre a ação e o Ctrl+Z sobrevive);
  * criar tarefa → desfazer arquiva; excluir → desfazer restaura tarefa,
    vínculos E apontamentos de RDO (é por isso que a Fase 3 troca o hard
    delete por arquivamento lógico);
  * recuar → desfazer restaura hierarquia e ordem;
  * vínculos (criar/editar) desfeitos pelo par natural;
  * invariantes da pilha: ação nova descarta o refazer, pilha vazia → 400,
    rota que falhou não empilha, escopo por usuário/obra/tenant, poda em 50;
  * flag off: rotas 404 e nada é empilhado;
  * Step D — tarefa arquivada some do físico-financeiro e do portal do cliente.

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
    CronogramaAcao,
    Obra,
    RDOApontamentoCronograma,
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

MSG_NADA_DESFAZER = 'Não há nada para desfazer'
MSG_NADA_REFAZER = 'Não há nada para refazer'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-undo-cronograma'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool) -> None:
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
        linha 2 — 'Alvenaria' B: 01/07/2026, 3 dias úteis      → fim 03/07
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


def _tarefa_db(tarefa_id: int) -> TarefaCronograma:
    with app.app_context():
        return db.session.get(TarefaCronograma, tarefa_id)


def _acoes(obra_id: int) -> list:
    with app.app_context():
        return (CronogramaAcao.query.filter_by(obra_id=obra_id)
                .order_by(CronogramaAcao.id).all())


# ---------------------------------------------------------------------------
# Edição de célula
# ---------------------------------------------------------------------------

def test_desfazer_e_refazer_edicao_de_nome():
    """(1) O caso mais simples: ida e volta de um campo de texto."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}",
              json={'nome_tarefa': 'Fundação profunda'})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['a_id']).nome_tarefa == 'Fundação profunda'

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['tipo_acao'] == 'editar_tarefa'
    assert corpo['pode_desfazer'] is False and corpo['pode_refazer'] is True
    assert _tarefa_db(ctx['a_id']).nome_tarefa == 'Fundação'

    r = c.post(f"{_base(ctx)}/refazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['pode_desfazer'] is True and corpo['pode_refazer'] is False
    assert _tarefa_db(ctx['a_id']).nome_tarefa == 'Fundação profunda'


def test_desfazer_edicao_de_duracao_restaura_a_cascata_inteira():
    """(2) O payload guarda as datas mexidas pelo motor, não só o campo
    editado — desfazer devolve a sucessora ao lugar."""
    ctx = _cenario(com_vinculo=True)     # A →TI/0→ B
    c = _client_como(ctx['admin_id'])
    # baseline: o vínculo ainda não foi aplicado; um recálculo alinha B
    c.post(f"{_base(ctx)}/recalcular")
    b_antes = _tarefa_db(ctx['b_id']).data_inicio

    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}", json={'duracao_dias': 10})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['b_id']).data_inicio == date(2026, 7, 15)

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['a_id']).duracao_dias == 5
    assert _tarefa_db(ctx['b_id']).data_inicio == b_antes
    assert _tarefa_db(ctx['b_id']).data_fim == date(2026, 7, 10)


def test_desfazer_nao_toca_campo_que_a_acao_nao_mexeu():
    """(3) A garantia central do diff POR CAMPO.

    Renomear → um RDO aponta progresso → Ctrl+Z. O desfazer restaura o nome
    e NÃO reverte `percentual_concluido`: aquele progresso é real e não
    fazia parte da ação desfeita.
    """
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}",
              json={'nome_tarefa': 'Fundação profunda'})
    assert r.status_code == 200, r.get_data(as_text=True)

    with app.app_context():
        a = db.session.get(TarefaCronograma, ctx['a_id'])
        a.percentual_concluido = 60.0
        db.session.commit()

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    a = _tarefa_db(ctx['a_id'])
    assert a.nome_tarefa == 'Fundação'          # a ação foi desfeita
    assert a.percentual_concluido == 60.0       # o progresso real sobreviveu


# ---------------------------------------------------------------------------
# Criar / excluir
# ---------------------------------------------------------------------------

def test_desfazer_criacao_arquiva_e_refazer_restaura():
    """(4) Criar é mutação de `ativa` na volta — o id nunca ressuscita."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa",
               json={'nome_tarefa': 'Cobertura', 'duracao_dias': 2})
    assert r.status_code == 201, r.get_data(as_text=True)
    nova = r.get_json()['tarefa']['id']

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(nova).ativa is False
    assert _por_id(r.get_json()['tarefas'], nova) is None   # sumiu da grade

    r = c.post(f"{_base(ctx)}/refazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(nova).ativa is True
    assert _por_id(r.get_json()['tarefas'], nova) is not None


def test_desfazer_exclusao_restaura_tarefa_vinculos_e_apontamentos():
    """(5) A razão de existir do soft delete: o desfazer devolve a tarefa
    com os vínculos e SEM perder apontamento de RDO."""
    ctx = _cenario(com_vinculo=True)     # A →TI/0→ B
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        b = db.session.get(TarefaCronograma, ctx['b_id'])
        _rdo_com_apontamento(obra, admin, b)

    c = _client_como(ctx['admin_id'])
    r = c.delete(f"{_base(ctx)}/tarefa/{ctx['b_id']}")
    assert r.status_code == 200, r.get_data(as_text=True)
    b = _tarefa_db(ctx['b_id'])
    assert b is not None and b.ativa is False and b.arquivada_em is not None
    with app.app_context():
        assert TarefaVinculo.query.filter_by(sucessora_id=ctx['b_id']).count() == 0
        # o apontamento sobreviveu ao arquivamento (com hard delete, cairia)
        assert RDOApontamentoCronograma.query.filter_by(
            tarefa_cronograma_id=ctx['b_id']).count() == 1

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['b_id']).ativa is True
    with app.app_context():
        v = TarefaVinculo.query.filter_by(
            predecessora_id=ctx['a_id'], sucessora_id=ctx['b_id']).one()
        assert (v.tipo, v.lag_dias) == ('TI', 0)
        assert RDOApontamentoCronograma.query.filter_by(
            tarefa_cronograma_id=ctx['b_id']).count() == 1


def test_exclusao_com_flag_off_continua_hard_delete():
    """(5b) Fora do rollout nada muda: a linha some da tabela."""
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    r = c.delete(f"{_base(ctx)}/tarefa/{ctx['b_id']}")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['b_id']) is None
    assert _acoes(ctx['obra_id']) == []


# ---------------------------------------------------------------------------
# Hierarquia e vínculos
# ---------------------------------------------------------------------------

def test_desfazer_recuar_restaura_hierarquia_e_ordem():
    """(6) `tarefa_pai_id` e `ordem` voltam juntos."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['b_id']).tarefa_pai_id == ctx['a_id']

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['tipo_acao'] == 'recuar_tarefa'
    b = _tarefa_db(ctx['b_id'])
    assert b.tarefa_pai_id is None and b.ordem == 1


def test_desfazer_mover_restaura_hierarquia():
    """(6b, Fase 6) O arrastar-e-soltar entra na pilha como qualquer ação."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/mover",
               json={'novo_pai_id': ctx['a_id']})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['b_id']).tarefa_pai_id == ctx['a_id']

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['tipo_acao'] == 'mover_tarefa'
    assert _tarefa_db(ctx['b_id']).tarefa_pai_id is None

    r = c.post(f"{_base(ctx)}/refazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(ctx['b_id']).tarefa_pai_id == ctx['a_id']


def test_mover_no_op_nao_empilha_acao():
    """Soltar onde a tarefa já está não pode gastar um passo do desfazer."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/mover",
           json={'novo_pai_id': ctx['a_id']})
    antes = len(_acoes(ctx['obra_id']))

    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/mover",
               json={'novo_pai_id': ctx['a_id']})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert len(_acoes(ctx['obra_id'])) == antes


def test_desfazer_criacao_de_vinculo_remove_o_par():
    """(7) Vínculo é chaveado pelo par natural, não por id."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['b_id'],
        'tipo': 'TI', 'lag_dias': 0})
    assert r.status_code == 201, r.get_data(as_text=True)

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        assert TarefaVinculo.query.filter_by(
            predecessora_id=ctx['a_id'], sucessora_id=ctx['b_id']).count() == 0

    r = c.post(f"{_base(ctx)}/refazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        assert TarefaVinculo.query.filter_by(
            predecessora_id=ctx['a_id'], sucessora_id=ctx['b_id']).count() == 1


def test_desfazer_edicao_de_vinculo_restaura_tipo_e_lag():
    """(7) Edição de tipo/lag volta ao valor anterior."""
    ctx = _cenario(com_vinculo=True)
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/vinculo/{ctx['vinculo_id']}",
              json={'tipo': 'II', 'lag_dias': 2})
    assert r.status_code == 200, r.get_data(as_text=True)

    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        v = TarefaVinculo.query.filter_by(
            predecessora_id=ctx['a_id'], sucessora_id=ctx['b_id']).one()
        assert (v.tipo, v.lag_dias) == ('TI', 0)


# ---------------------------------------------------------------------------
# Invariantes da pilha
# ---------------------------------------------------------------------------

def test_acao_nova_descarta_o_refazer_pendente():
    """(8) Spec §6: depois de desfazer, uma edição nova mata o refazer."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}", json={'nome_tarefa': 'X'})
    r = c.post(f"{_base(ctx)}/desfazer")
    assert r.get_json()['pode_refazer'] is True

    c.put(f"{_base(ctx)}/tarefa/{ctx['b_id']}", json={'nome_tarefa': 'Y'})
    r = c.post(f"{_base(ctx)}/refazer")
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_NADA_REFAZER
    with app.app_context():
        assert CronogramaAcao.query.filter_by(
            obra_id=ctx['obra_id'], desfeita=True).count() == 0


def test_pilha_vazia_devolve_400_nas_duas_rotas():
    """(9) Mensagens verbatim."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r_des = c.post(f"{_base(ctx)}/desfazer")
    r_ref = c.post(f"{_base(ctx)}/refazer")
    assert (r_des.status_code, r_ref.status_code) == (400, 400)
    assert r_des.get_json()['msg'] == MSG_NADA_DESFAZER
    assert r_ref.get_json()['msg'] == MSG_NADA_REFAZER


def test_flag_off_nao_empilha_e_rotas_404():
    """(10) Fora do rollout a Fase 3 não existe."""
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}", json={'nome_tarefa': 'Z'})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _acoes(ctx['obra_id']) == []
    assert c.post(f"{_base(ctx)}/desfazer").status_code == 404
    assert c.post(f"{_base(ctx)}/refazer").status_code == 404


def test_rota_que_falha_nao_empilha_acao():
    """(11) Sem diff, sem ação — o rollback do 400 não suja a pilha."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    # recuar a primeira linha é 400 (não há irmã acima) — Fase 2
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['a_id']}/recuar")
    assert r.status_code == 400
    # auto-vínculo é 400 — Fase 1
    r = c.post(f"{_base(ctx)}/vinculo", json={
        'predecessora_id': ctx['a_id'], 'sucessora_id': ctx['a_id']})
    assert r.status_code == 400
    assert _acoes(ctx['obra_id']) == []
    assert c.post(f"{_base(ctx)}/desfazer").status_code == 400


def test_pilha_e_por_usuario_e_obra_e_cross_tenant_404():
    """(12) A ação de um usuário não é desfeita por outro; obra alheia 404."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}", json={'nome_tarefa': 'Alfa'})

    with app.app_context():
        vizinho, _obra_b = _ambiente()
        _flag_editor_v2(vizinho.id, True)   # flag ligada: o 404 é do escopo
        vid = vizinho.id
    c2 = _client_como(vid)
    r = c2.post(f"{_base(ctx)}/desfazer")
    assert r.status_code == 404
    assert _tarefa_db(ctx['a_id']).nome_tarefa == 'Alfa'   # nada foi desfeito


def test_pilha_podada_em_50_acoes():
    """(13) A 51ª ação descarta a mais antiga."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    for i in range(51):
        r = c.put(f"{_base(ctx)}/tarefa/{ctx['a_id']}",
                  json={'nome_tarefa': f'Nome {i}'})
        assert r.status_code == 200, r.get_data(as_text=True)
    acoes = _acoes(ctx['obra_id'])
    assert len(acoes) == 50
    # a mais antiga preservada é a da 2ª edição ('Nome 0' → 'Nome 1')
    assert acoes[0].payload_antes['tarefas'][str(ctx['a_id'])]['nome_tarefa'] \
        == 'Nome 0'


# ---------------------------------------------------------------------------
# Step D — tarefa arquivada não vaza
# ---------------------------------------------------------------------------

def _custo_ligado_a_tarefa(ctx, tarefa_id: int) -> None:
    """Um `ObraServicoCusto` cujo item de medição aponta SÓ para `tarefa_id`.

    É a cadeia que o físico-financeiro percorre para decidir se a etapa é
    'entregavel' (tem tarefa de cronograma para fasear o previsto físico) ou
    'periodo' (não tem). Se a tarefa arquivada continuasse visível, a etapa
    seguiria entregável — é exatamente isso que o Step D corrige.
    """
    from models import ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, ObraServicoCusto
    with app.app_context():
        item = ItemMedicaoComercial(
            admin_id=ctx['admin_id'], obra_id=ctx['obra_id'],
            nome='Item medição', valor_comercial=1000)
        db.session.add(item)
        db.session.flush()
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=item.id, cronograma_tarefa_id=tarefa_id,
            peso=100, admin_id=ctx['admin_id']))
        db.session.commit()
        # `obra_servico_custo.item_medicao_comercial_id` é UNIQUE e o sistema
        # já cria o OSC espelho ao criar o item — reaproveitar, não duplicar.
        osc = ObraServicoCusto.query.filter_by(
            item_medicao_comercial_id=item.id).first()
        if osc is None:
            osc = ObraServicoCusto(
                admin_id=ctx['admin_id'], obra_id=ctx['obra_id'],
                item_medicao_comercial_id=item.id, nome='Etapa Alvenaria')
            db.session.add(osc)
        osc.valor_orcado = 1000
        db.session.commit()


def test_tarefa_arquivada_sai_do_faseamento_do_fisico_financeiro():
    """(14) O conserto do vazamento no físico-financeiro.

    Com a tarefa ativa, a etapa é 'entregavel' e o previsto é faseado pelas
    datas dela. Depois de arquivada, ela some de `por_id` e a etapa cai para
    'periodo' — antes do Step D ela continuaria faseando por uma tarefa que
    não existe mais.
    """
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    ctx = _cenario()
    _custo_ligado_a_tarefa(ctx, ctx['b_id'])

    with app.app_context():
        dados = montar_fisico_financeiro(ctx['obra_id'], ctx['admin_id'])
    assert [e['tipo'] for e in dados['etapas']] == ['entregavel']

    c = _client_como(ctx['admin_id'])
    assert c.delete(f"{_base(ctx)}/tarefa/{ctx['b_id']}").status_code == 200

    with app.app_context():
        dados = montar_fisico_financeiro(ctx['obra_id'], ctx['admin_id'])
    assert [e['tipo'] for e in dados['etapas']] == ['periodo']


def test_tarefa_arquivada_nao_aparece_no_portal_do_cliente():
    """(14) Idem no portal.

    O portal renderiza o cronograma DO CLIENTE (`is_cliente=True`), então o
    cenário usa esse plano e exclui em modo cliente (`?cliente=1`).
    """
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        # `_tarefa` fixa is_cliente=False — o plano do cliente é criado à mão.
        visivel = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, nome_tarefa='Etapa Visivel',
            ordem=0, duracao_dias=5, data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 7), is_cliente=True)
        oculta = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, nome_tarefa='Etapa Removida',
            ordem=1, duracao_dias=3, data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 3), is_cliente=True)
        db.session.add_all([visivel, oculta])
        db.session.commit()
        obra.portal_ativo = True
        obra.token_cliente = f'tok-undo-{obra.id}'
        obra.token_cliente_expira_em = None
        db.session.commit()
        token, oculta_id = obra.token_cliente, oculta.id

    c = _client_como(ctx['admin_id'])
    r = c.delete(f"{_base(ctx)}/tarefa/{oculta_id}?cliente=1")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tarefa_db(oculta_id).ativa is False

    r = app.test_client().get(f'/portal/obra/{token}')
    assert r.status_code == 200, r.get_data(as_text=True)[:500]
    html = r.get_data(as_text=True)
    assert 'Etapa Visivel' in html
    assert 'Etapa Removida' not in html
