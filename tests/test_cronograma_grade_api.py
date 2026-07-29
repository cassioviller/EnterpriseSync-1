"""Fase 2 (editor v2) — integração da API da grade tipo planilha (plano Step D).

Cobre o Step A+B do plano `2026-07-24-cronograma-fase2-plano.md`:

  * `POST /cronograma/obra/<id>/tarefa/<tid>/recuar` (indent, semântica
    Project: novo pai = irmã anterior; X entra como última filha) — sucesso
    com roll-up, sem irmã acima → 400, folha-com-vínculo que viraria resumo
    → 400, folha iniciada → 400, sob resumo já existente → última filha;
  * `POST .../desrecuar` (outdent): raiz → 400, filha vira irmã do ex-pai
    logo após a subárvore dele, ex-pai sem filhas volta a ser folha;
  * inserção posicionada em `POST /cronograma/obra/<id>/tarefa`
    (`ref_tarefa_id` + `posicao`), incluindo "abaixo" de resumo (cai depois
    da subárvore inteira), referência inválida → 400 e flag off ignorando
    os campos novos;
  * as rotas novas "não existem" (404 opaco) com a flag desligada e para
    tenant vizinho;
  * renumeração visual: indent PRESERVA a numeração (a irmã anterior está
    imediatamente acima), outdent DESLOCA — e `predecessoras_texto` sai
    fresco na resposta.

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

MSG_SEM_IRMA = ('Não é possível recuar: não há tarefa acima no mesmo '
                'nível para ser o novo grupo')
MSG_JA_RAIZ = 'A tarefa já está no nível raiz — não é possível desrecuar'
MSG_REF_INVALIDA = 'Tarefa de referência não encontrada nesta obra'
MSG_POSICAO_INVALIDA = "Posição inválida: use 'acima', 'abaixo' ou 'dentro'"


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-grade-cronograma'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool) -> None:
    """Liga/desliga a flag DIRETO na coluna (mesmo helper da Fase 1)."""
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()


def _cenario(flag: bool = True) -> dict:
    """Tenant novo com obra e três folhas raiz (ordem 0/5/10 — de propósito
    esparsa, para que a renumeração flat do plano fique visível):

        linha 1 — 'Fundação'  A: 01/07/2026 (qua), 5 dias úteis → fim 07/07
        linha 2 — 'Alvenaria' B: 01/07/2026, 3 dias úteis      → fim 03/07
        linha 3 — 'Cobertura' C: 01/07/2026, 2 dias úteis      → fim 02/07
    """
    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, flag)
        a = _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=5,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        b = _tarefa(obra, admin, 'Alvenaria', ordem=5, duracao_dias=3,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 3))
        c = _tarefa(obra, admin, 'Cobertura', ordem=10, duracao_dias=2,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 2))
        return {'admin_id': admin.id, 'obra_id': obra.id,
                'a_id': a.id, 'b_id': b.id, 'c_id': c.id}


def _base(ctx) -> str:
    return f"/cronograma/obra/{ctx['obra_id']}"


def _por_id(lista: list, tarefa_id: int) -> dict | None:
    return next((t for t in lista if t['id'] == tarefa_id), None)


def _ordem_visual(obra_id: int) -> list[tuple[int, int]]:
    """`[(tarefa_id, ordem)]` como está no banco, na ordem visual."""
    with app.app_context():
        return [
            (t.id, t.ordem)
            for t in TarefaCronograma.query
            .filter_by(obra_id=obra_id)
            .order_by(TarefaCronograma.ordem, TarefaCronograma.id).all()
        ]


def _pai_de(tarefa_id: int) -> int | None:
    with app.app_context():
        return db.session.get(TarefaCronograma, tarefa_id).tarefa_pai_id


def _grupo(ctx, filhas: int = 1) -> dict:
    """Transforma A em tarefa-resumo com `filhas` subtarefas ('Etapa 1..n').

    Devolve `ctx` acrescido de `f1_id`/`f2_id`.
    """
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        for i in range(filhas):
            f = _tarefa(obra, admin, f'Etapa {i + 1}', ordem=1 + i,
                        duracao_dias=2, tarefa_pai_id=ctx['a_id'],
                        data_inicio=date(2026, 7, 1),
                        data_fim=date(2026, 7, 2))
            ctx[f'f{i + 1}_id'] = f.id
    return ctx


# ---------------------------------------------------------------------------
# Recuar (indent)
# ---------------------------------------------------------------------------

def test_recuar_torna_irma_anterior_um_resumo_com_rollup():
    """(1) B recuada sob A: A vira resumo e herda as datas de B pelo roll-up."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert corpo['status'] == 'ok'
    assert corpo['tarefa']['id'] == ctx['b_id']
    assert corpo['tarefa']['nivel'] == 1

    # a lista completa volta em ordem visual, com `nivel` em cada item
    ids = [t['id'] for t in corpo['tarefas']]
    assert ids == [ctx['a_id'], ctx['b_id'], ctx['c_id']]
    assert [t['nivel'] for t in corpo['tarefas']] == [0, 1, 0]

    # A virou resumo: roll-up sobrescreve datas/duração com as da única filha
    a = _por_id(corpo['tarefas_afetadas'], ctx['a_id'])
    assert a is not None, corpo['tarefas_afetadas']
    assert a['data_inicio'] == '2026-07-01'
    assert a['data_fim'] == '2026-07-03'
    assert a['duracao_dias'] == 3

    assert _pai_de(ctx['b_id']) == ctx['a_id']


def test_recuar_primeira_linha_400():
    """(2) Sem irmã acima no mesmo nível não há grupo possível."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['a_id']}/recuar")
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_SEM_IRMA
    assert _pai_de(ctx['a_id']) is None


def test_recuar_primeira_filha_de_grupo_400():
    """(3) Mesma mensagem quando X é a primeira filha do próprio grupo."""
    ctx = _grupo(_cenario(), filhas=2)
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['f1_id']}/recuar")
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_SEM_IRMA
    assert _pai_de(ctx['f1_id']) == ctx['a_id']


def test_recuar_sob_folha_com_vinculo_400_sem_persistir():
    """(4) A folha que viraria resumo tem vínculos — rejeita, nunca muta."""
    ctx = _cenario()
    with app.app_context():
        db.session.add(TarefaVinculo(
            admin_id=ctx['admin_id'], obra_id=ctx['obra_id'],
            predecessora_id=ctx['a_id'], sucessora_id=ctx['c_id'],
            tipo='TI', lag_dias=0))
        db.session.commit()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 400
    assert r.get_json()['msg'] == (
        'A tarefa "Fundação" tem vínculos de predecessora/sucessora e '
        'viraria uma tarefa-resumo — remova os vínculos dela antes de recuar')
    assert _pai_de(ctx['b_id']) is None
    with app.app_context():
        assert TarefaVinculo.query.filter_by(obra_id=ctx['obra_id']).count() == 1


def test_recuar_sob_folha_iniciada_400():
    """(5) Tarefa com apontamento de RDO é âncora — não pode virar resumo."""
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        a = db.session.get(TarefaCronograma, ctx['a_id'])
        _rdo_com_apontamento(obra, admin, a)
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 400
    assert r.get_json()['msg'] == (
        'A tarefa "Fundação" já foi iniciada e não pode virar tarefa-resumo')
    assert _pai_de(ctx['b_id']) is None


def test_recuar_sob_resumo_entra_como_ultima_filha_e_renumera_flat():
    """(6) Sob um resumo existente X entra no fim; `ordem` vira 0..n-1."""
    ctx = _grupo(_cenario(), filhas=2)   # A(resumo) > Etapa 1, Etapa 2
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert [t['id'] for t in corpo['tarefas']] == [
        ctx['a_id'], ctx['f1_id'], ctx['f2_id'], ctx['b_id'], ctx['c_id']]
    assert [t['nivel'] for t in corpo['tarefas']] == [0, 1, 1, 1, 0]
    assert _pai_de(ctx['b_id']) == ctx['a_id']
    # renumeração flat (o cenário nasce com ordem 0/5/10)
    assert _ordem_visual(ctx['obra_id']) == [
        (ctx['a_id'], 0), (ctx['f1_id'], 1), (ctx['f2_id'], 2),
        (ctx['b_id'], 3), (ctx['c_id'], 4)]


# ---------------------------------------------------------------------------
# Desrecuar (outdent)
# ---------------------------------------------------------------------------

def test_desrecuar_tarefa_raiz_400():
    """(7) Já está no nível raiz."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/desrecuar")
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_JA_RAIZ


def test_desrecuar_filha_vira_irma_do_pai_apos_a_subarvore():
    """(8) X sai do grupo e cai DEPOIS da subárvore inteira do ex-pai; as
    irmãs seguintes permanecem no grupo (desvio deliberado do Project puro)."""
    ctx = _grupo(_cenario(), filhas=2)   # A(resumo) > Etapa 1, Etapa 2
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['f1_id']}/desrecuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert [t['id'] for t in corpo['tarefas']] == [
        ctx['a_id'], ctx['f2_id'], ctx['f1_id'], ctx['b_id'], ctx['c_id']]
    assert [t['nivel'] for t in corpo['tarefas']] == [0, 1, 0, 0, 0]
    assert _pai_de(ctx['f1_id']) is None
    assert _pai_de(ctx['f2_id']) == ctx['a_id']   # irmã seguinte fica no grupo


def test_desrecuar_ultima_filha_faz_ex_pai_voltar_a_ser_folha():
    """(8b) Pai → folha: sem filhas, mantém as datas do último roll-up e
    volta na lista para o front atualizar as classes."""
    ctx = _grupo(_cenario(), filhas=1)   # A(resumo) > Etapa 1
    c = _client_como(ctx['admin_id'])
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['f1_id']}/desrecuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    assert [t['id'] for t in corpo['tarefas']] == [
        ctx['a_id'], ctx['f1_id'], ctx['b_id'], ctx['c_id']]
    assert [t['nivel'] for t in corpo['tarefas']] == [0, 0, 0, 0]
    assert _por_id(corpo['tarefas'], ctx['a_id']) is not None
    with app.app_context():
        assert TarefaCronograma.query.filter_by(
            tarefa_pai_id=ctx['a_id']).count() == 0


# ---------------------------------------------------------------------------
# Escopo: flag off e cross-tenant
# ---------------------------------------------------------------------------

def test_rotas_de_hierarquia_nao_existem_com_flag_off():
    """(9) Flag desligada ⇒ 404 opaco, como qualquer URL desconhecida."""
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    r_rec = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    r_des = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/desrecuar")
    assert (r_rec.status_code, r_des.status_code) == (404, 404)
    assert _pai_de(ctx['b_id']) is None


def test_recuar_cross_tenant_404_opaco_sem_persistir():
    """(10) Tenant vizinho com a flag ligada mesmo assim não enxerga a obra."""
    ctx = _cenario()
    with app.app_context():
        vizinho, _obra_b = _ambiente()
        _flag_editor_v2(vizinho.id, True)   # flag ligada: o 404 é do escopo
        vid = vizinho.id
    c = _client_como(vid)
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 404
    assert _pai_de(ctx['b_id']) is None


# ---------------------------------------------------------------------------
# Inserir acima/abaixo (Step B)
# ---------------------------------------------------------------------------

def _criar(c, ctx, **body):
    return c.post(f"{_base(ctx)}/tarefa",
                  json={'nome_tarefa': 'Nova tarefa', 'duracao_dias': 1,
                        **body})


def test_inserir_acima_e_abaixo_posiciona_como_irma():
    """(11) `posicao` relativa à referência, herdando o pai dela."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])

    r = _criar(c, ctx, ref_tarefa_id=ctx['b_id'], posicao='acima')
    assert r.status_code == 201, r.get_data(as_text=True)
    nova_acima = r.get_json()['tarefa']['id']
    assert [t['id'] for t in r.get_json()['tarefas']] == [
        ctx['a_id'], nova_acima, ctx['b_id'], ctx['c_id']]

    r = _criar(c, ctx, ref_tarefa_id=ctx['b_id'], posicao='abaixo')
    assert r.status_code == 201, r.get_data(as_text=True)
    nova_abaixo = r.get_json()['tarefa']['id']
    assert [t['id'] for t in r.get_json()['tarefas']] == [
        ctx['a_id'], nova_acima, ctx['b_id'], nova_abaixo, ctx['c_id']]
    assert _pai_de(nova_abaixo) is None


def test_inserir_abaixo_de_resumo_cai_apos_a_subarvore():
    """(11) 'abaixo' de um grupo = próxima IRMÃ dele, não última filha."""
    ctx = _grupo(_cenario(), filhas=2)
    c = _client_como(ctx['admin_id'])
    r = _criar(c, ctx, ref_tarefa_id=ctx['a_id'], posicao='abaixo')
    assert r.status_code == 201, r.get_data(as_text=True)
    corpo = r.get_json()
    nova = corpo['tarefa']['id']
    assert [t['id'] for t in corpo['tarefas']] == [
        ctx['a_id'], ctx['f1_id'], ctx['f2_id'], nova,
        ctx['b_id'], ctx['c_id']]
    assert [t['nivel'] for t in corpo['tarefas']] == [0, 1, 1, 0, 0, 0]
    assert _pai_de(nova) is None


def test_inserir_dentro_de_grupo_herda_o_pai_da_referencia():
    """(11) Referência é filha ⇒ a nova nasce irmã dela, dentro do grupo."""
    ctx = _grupo(_cenario(), filhas=2)
    c = _client_como(ctx['admin_id'])
    r = _criar(c, ctx, ref_tarefa_id=ctx['f1_id'], posicao='abaixo')
    assert r.status_code == 201, r.get_data(as_text=True)
    corpo = r.get_json()
    nova = corpo['tarefa']['id']
    assert [t['id'] for t in corpo['tarefas']] == [
        ctx['a_id'], ctx['f1_id'], nova, ctx['f2_id'],
        ctx['b_id'], ctx['c_id']]
    assert _pai_de(nova) == ctx['a_id']


def test_inserir_com_referencia_ou_posicao_invalida_400_sem_criar():
    """(11) Referência inexistente/de outra obra e posição fora do enum."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = _criar(c, ctx, ref_tarefa_id=999_999, posicao='abaixo')
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_REF_INVALIDA

    r = _criar(c, ctx, ref_tarefa_id=ctx['b_id'], posicao='ao_lado')
    assert r.status_code == 400
    assert r.get_json()['msg'] == MSG_POSICAO_INVALIDA

    with app.app_context():
        assert TarefaCronograma.query.filter_by(
            obra_id=ctx['obra_id']).count() == 3


def test_inserir_com_flag_off_ignora_ref_e_anexa_no_fim():
    """(11) Flag off = comportamento legado byte-idêntico (anexa no fim)."""
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    r = _criar(c, ctx, ref_tarefa_id=ctx['a_id'], posicao='acima')
    assert r.status_code == 201, r.get_data(as_text=True)
    corpo = r.get_json()
    assert 'tarefas' not in corpo          # resposta legada não muda de shape
    nova = corpo['tarefa']['id']
    assert _pai_de(nova) is None
    ordens = dict(_ordem_visual(ctx['obra_id']))
    assert ordens[nova] > ordens[ctx['c_id']]


# ---------------------------------------------------------------------------
# Numeração visual e predecessoras
# ---------------------------------------------------------------------------

def test_recuar_preserva_numeracao_e_desrecuar_desloca():
    """(12) A irmã anterior está imediatamente acima, então o indent NÃO
    muda a ordem visual; o outdent muda — e `predecessoras_texto` volta
    recalculado sobre as linhas novas."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    # C (linha 3) depende de B (linha 2)
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['c_id']}",
              json={'predecessoras_texto': '2'})
    assert r.status_code == 200, r.get_data(as_text=True)

    # indent de B sob A: visual continua A, B, C → C ainda aponta para a 2
    r = c.post(f"{_base(ctx)}/tarefa/{ctx['b_id']}/recuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    c_dict = _por_id(r.get_json()['tarefas'], ctx['c_id'])
    assert c_dict['predecessoras_texto'] == '2'

    # outdent de B: nada muda aqui (A ficou sem filhas, B volta para a raiz
    # logo após A) — mas com uma irmã seguinte no grupo a numeração desloca
    ctx2 = _grupo(_cenario(), filhas=2)     # A > Etapa 1(2), Etapa 2(3)
    c2 = _client_como(ctx2['admin_id'])
    r = c2.put(f"{_base(ctx2)}/tarefa/{ctx2['b_id']}",
               json={'predecessoras_texto': '3'})   # B depende de Etapa 2
    assert r.status_code == 200, r.get_data(as_text=True)
    r = c2.post(f"{_base(ctx2)}/tarefa/{ctx2['f1_id']}/desrecuar")
    assert r.status_code == 200, r.get_data(as_text=True)
    tarefas = r.get_json()['tarefas']
    # nova ordem: A(1), Etapa 2(2), Etapa 1(3), B(4), C(5)
    assert [t['id'] for t in tarefas] == [
        ctx2['a_id'], ctx2['f2_id'], ctx2['f1_id'], ctx2['b_id'], ctx2['c_id']]
    b_dict = _por_id(tarefas, ctx2['b_id'])
    assert b_dict['predecessoras_texto'] == '2'   # Etapa 2 agora é a linha 2


# ---------------------------------------------------------------------------
# Cadastro de quantitativo em tarefa com histórico em percentual
# ---------------------------------------------------------------------------

def _tarefa_com_apontamento_percentual():
    """Tenant + tarefa SEM quantitativo, já apontada em percentual."""
    from models import RDO, RDOApontamentoCronograma
    with app.app_context():
        admin, obra = _ambiente()
        t = _tarefa(obra, admin, 'Pintura', ordem=0, duracao_dias=5,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        rdo = RDO(numero_rdo=f'RDO-PCT-{t.id}', data_relatorio=date(2026, 7, 3),
                  obra_id=obra.id, admin_id=admin.id)
        db.session.add(rdo)
        db.session.flush()
        db.session.add(RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=t.id, admin_id=admin.id,
            tipo_apontamento='percentual', quantidade_executada_dia=0.0,
            quantidade_acumulada=0.0, percentual_realizado=80.0,
            percentual_acumulado=80.0))
        db.session.commit()
        return {'admin_id': admin.id, 'obra_id': obra.id, 'tarefa_id': t.id}


def test_rota_recusa_quantitativo_em_tarefa_apontada_em_percentual():
    """A rota devolve 400 e NÃO grava.

    O bloqueio existiu em `7b8cd6fc`, saiu no revert `39958447` e volta
    aqui com outra justificativa: não é mais o histórico que se
    reescreveria (isso virou defeito corrigido), é o avanço acumulado em %
    que os apontamentos seguintes descartariam.
    """
    ctx = _tarefa_com_apontamento_percentual()
    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['tarefa_id']}",
              json={'quantidade_total': 200})
    assert r.status_code == 400, r.get_data(as_text=True)
    assert 'PERCENTUAL' in r.get_json()['msg']

    with app.app_context():
        t = db.session.get(TarefaCronograma, ctx['tarefa_id'])
        assert t.quantidade_total in (None, 0), 'a rota gravou mesmo recusando'


def test_rota_aceita_quantitativo_em_tarefa_sem_apontamento():
    """O contrapeso: sem histórico em %, o cadastro segue livre pela tela."""
    with app.app_context():
        admin, obra = _ambiente()
        t = _tarefa(obra, admin, 'Forma', ordem=0, duracao_dias=3,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 3))
        ctx = {'admin_id': admin.id, 'obra_id': obra.id, 'tarefa_id': t.id}

    c = _client_como(ctx['admin_id'])
    r = c.put(f"{_base(ctx)}/tarefa/{ctx['tarefa_id']}",
              json={'quantidade_total': 48})
    assert r.status_code == 200, r.get_data(as_text=True)

    with app.app_context():
        t = db.session.get(TarefaCronograma, ctx['tarefa_id'])
        assert t.quantidade_total == 48


# ---------------------------------------------------------------------------
# Fase 6 — mover (re-parent explícito do arrastar-e-soltar)
# ---------------------------------------------------------------------------

def _mover(c, ctx, tarefa_id, novo_pai_id):
    return c.post(f"{_base(ctx)}/tarefa/{tarefa_id}/mover",
                  json={'novo_pai_id': novo_pai_id})


def test_mover_entra_como_ultima_filha_do_destino_e_renumera_flat():
    """Soltar B sobre o resumo A: entra DEPOIS das filhas que A já tinha."""
    ctx = _grupo(_cenario(), filhas=2)
    c = _client_como(ctx['admin_id'])

    r = _mover(c, ctx, ctx['b_id'], ctx['a_id'])
    assert r.status_code == 200, r.get_data(as_text=True)
    assert [t['id'] for t in r.get_json()['tarefas']] == [
        ctx['a_id'], ctx['f1_id'], ctx['f2_id'], ctx['b_id'], ctx['c_id']]
    assert _pai_de(ctx['b_id']) == ctx['a_id']
    # Renumeração flat sobre TODAS as tarefas do modo, como as rotas irmãs.
    assert [o for _, o in _ordem_visual(ctx['obra_id'])] == [0, 1, 2, 3, 4]


def test_mover_sobre_folha_a_transforma_em_resumo():
    """O caso central do arrasto: a linha-alvo era folha e vira grupo."""
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])

    r = _mover(c, ctx, ctx['c_id'], ctx['b_id'])
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _pai_de(ctx['c_id']) == ctx['b_id']
    assert [t['id'] for t in r.get_json()['tarefas']] == [
        ctx['a_id'], ctx['b_id'], ctx['c_id']]
    # B agora é resumo: o nível de C desceu (é o que dá a indentação no front).
    assert _por_id(r.get_json()['tarefas'], ctx['c_id'])['nivel'] == 1


def test_mover_com_pai_nulo_promove_para_a_raiz():
    """`novo_pai_id: null` — o outro sentido do gesto (arrastar para fora)."""
    ctx = _grupo(_cenario(), filhas=1)
    c = _client_como(ctx['admin_id'])
    assert _pai_de(ctx['f1_id']) == ctx['a_id']

    r = _mover(c, ctx, ctx['f1_id'], None)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _pai_de(ctx['f1_id']) is None
    # Última irmã da raiz — o append de `filhas_map[None]`.
    assert [t['id'] for t in r.get_json()['tarefas']][-1] == ctx['f1_id']


def test_mover_para_folha_com_vinculo_400_sem_persistir():
    """Mesmo guard do indent: o arrasto não é porta dos fundos do recuar."""
    ctx = _cenario()
    with app.app_context():
        db.session.add(TarefaVinculo(
            admin_id=ctx['admin_id'], obra_id=ctx['obra_id'],
            predecessora_id=ctx['a_id'], sucessora_id=ctx['c_id'],
            tipo='TI', lag_dias=0))
        db.session.commit()
    c = _client_como(ctx['admin_id'])

    r = _mover(c, ctx, ctx['b_id'], ctx['a_id'])
    assert r.status_code == 400
    assert r.get_json()['msg'] == (
        'A tarefa "Fundação" tem vínculos de predecessora/sucessora e '
        'viraria uma tarefa-resumo — remova os vínculos dela antes de mover '
        'para dentro dela')
    assert _pai_de(ctx['b_id']) is None
    with app.app_context():
        assert TarefaVinculo.query.filter_by(obra_id=ctx['obra_id']).count() == 1


def test_mover_para_folha_iniciada_400():
    """Âncora de apontamento não pode virar resumo — nem pelo mouse."""
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        a = db.session.get(TarefaCronograma, ctx['a_id'])
        _rdo_com_apontamento(obra, admin, a)
    c = _client_como(ctx['admin_id'])

    r = _mover(c, ctx, ctx['b_id'], ctx['a_id'])
    assert r.status_code == 400
    assert r.get_json()['msg'] == (
        'A tarefa "Fundação" já foi iniciada e não pode virar tarefa-resumo')
    assert _pai_de(ctx['b_id']) is None


def test_mover_pai_para_dentro_do_proprio_filho_400():
    """Ciclo: aqui é o caso REAL (o mouse alcança o próprio descendente)."""
    ctx = _grupo(_cenario(), filhas=1)
    c = _client_como(ctx['admin_id'])

    r = _mover(c, ctx, ctx['a_id'], ctx['f1_id'])
    assert r.status_code == 400
    assert 'circular' in r.get_json()['msg']
    assert _pai_de(ctx['a_id']) is None
    assert _pai_de(ctx['f1_id']) == ctx['a_id']


def test_mover_para_si_mesma_400():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])
    r = _mover(c, ctx, ctx['b_id'], ctx['b_id'])
    assert r.status_code == 400
    assert r.get_json()['msg'] == 'Uma tarefa não pode ser filha de si mesma'
    assert _pai_de(ctx['b_id']) is None


def test_mover_para_o_pai_atual_e_no_op_sem_erro():
    """Soltar onde já está devolve a grade sem empilhar ação de desfazer."""
    ctx = _grupo(_cenario(), filhas=1)
    c = _client_como(ctx['admin_id'])

    r = _mover(c, ctx, ctx['f1_id'], ctx['a_id'])
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['tarefas_afetadas'] == []
    assert _pai_de(ctx['f1_id']) == ctx['a_id']


def test_mover_nao_existe_com_flag_off_e_e_404_cross_tenant():
    """Mesmo escopo das irmãs: 404 opaco fora do rollout e fora do tenant."""
    ctx_off = _cenario(flag=False)
    c_off = _client_como(ctx_off['admin_id'])
    assert _mover(c_off, ctx_off, ctx_off['b_id'],
                  ctx_off['a_id']).status_code == 404
    assert _pai_de(ctx_off['b_id']) is None

    ctx = _cenario()
    with app.app_context():
        vizinho, _obra_b = _ambiente()
        _flag_editor_v2(vizinho.id, True)
        vid = vizinho.id
    c = _client_como(vid)
    assert _mover(c, ctx, ctx['b_id'], ctx['a_id']).status_code == 404
    assert _pai_de(ctx['b_id']) is None


def test_mover_para_pai_de_outra_obra_404_opaco():
    """Destino existe, mas em outra obra — não pode nem vazar que existe."""
    ctx = _cenario()
    outra = _cenario()
    c = _client_como(ctx['admin_id'])
    r = _mover(c, ctx, ctx['b_id'], outra['a_id'])
    assert r.status_code == 404
    assert _pai_de(ctx['b_id']) is None


# ---------------------------------------------------------------------------
# Fase 6 — criar com posicao='dentro' (Nova subtarefa)
# ---------------------------------------------------------------------------

def test_criar_dentro_nasce_como_ultima_filha_da_referencia():
    """Poupa o inserir-e-recuar: a nova já nasce dentro do grupo."""
    ctx = _grupo(_cenario(), filhas=1)
    c = _client_como(ctx['admin_id'])

    r = _criar(c, ctx, ref_tarefa_id=ctx['a_id'], posicao='dentro')
    assert r.status_code == 201, r.get_data(as_text=True)
    nova = r.get_json()['tarefa']['id']
    assert _pai_de(nova) == ctx['a_id']
    assert [t['id'] for t in r.get_json()['tarefas']] == [
        ctx['a_id'], ctx['f1_id'], nova, ctx['b_id'], ctx['c_id']]


def test_criar_dentro_de_folha_transforma_a_referencia_em_grupo():
    ctx = _cenario()
    c = _client_como(ctx['admin_id'])

    r = _criar(c, ctx, ref_tarefa_id=ctx['b_id'], posicao='dentro')
    assert r.status_code == 201, r.get_data(as_text=True)
    nova = r.get_json()['tarefa']['id']
    assert _pai_de(nova) == ctx['b_id']
    assert _por_id(r.get_json()['tarefas'], nova)['nivel'] == 1


def test_criar_dentro_de_folha_iniciada_400_sem_criar():
    """O guard de resumo vale na criação também — e nada é persistido."""
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        a = db.session.get(TarefaCronograma, ctx['a_id'])
        _rdo_com_apontamento(obra, admin, a)
    c = _client_como(ctx['admin_id'])

    r = _criar(c, ctx, ref_tarefa_id=ctx['a_id'], posicao='dentro')
    assert r.status_code == 400
    assert r.get_json()['msg'] == (
        'A tarefa "Fundação" já foi iniciada e não pode virar tarefa-resumo')
    with app.app_context():
        assert TarefaCronograma.query.filter_by(
            obra_id=ctx['obra_id']).count() == 3


# ---------------------------------------------------------------------------
# Fase 6 — geometria do soltar-para-aninhar (achado da revisão de 29/07)
# ---------------------------------------------------------------------------

def test_soltar_fora_da_grade_nao_aninha():
    """`onMove` só dispara sobre itens da lista: se o ponteiro cruza a faixa
    central de uma linha e depois sai da tabela, `_alvoNest` fica armado com
    alvo obsoleto e o `onEnd` aninhava numa linha onde o cursor já não estava.

    O Playwright não sobe neste ambiente (libnspr4.so ausente), então o teste
    extrai `_soltouSobreOAlvo` do template e exercita a geometria no Node —
    que é exatamente onde o defeito morava.
    """
    import json
    import os
    import re
    import shutil
    import subprocess
    import tempfile

    node = shutil.which('node')
    if not node:
        pytest.skip('node indisponível')

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, 'templates/obras/cronograma.html')) as f:
        html = f.read()

    consts = re.search(r'const NEST_MIN = [^;]+;', html)
    func = re.search(
        r'function _soltouSobreOAlvo\(oe, alvoId\) \{.*?\n\}', html, re.S)
    assert consts and func, 'a função de conferência do drop sumiu do template'

    # Linha alvo em y=100..140 (altura 40): faixa central = 112..128.
    harness = f"""
{consts.group(0)}
function _rowDe(id) {{
  if (id !== 7) return null;
  return {{ getBoundingClientRect: () => (
    {{ left: 0, right: 500, top: 100, height: 40 }}) }};
}}
{func.group(0)}
const casos = {{
  centro_da_linha:        _soltouSobreOAlvo({{clientX: 250, clientY: 120}}, 7),
  borda_de_cima:          _soltouSobreOAlvo({{clientX: 250, clientY: 104}}, 7),
  borda_de_baixo:         _soltouSobreOAlvo({{clientX: 250, clientY: 136}}, 7),
  abaixo_da_tabela:       _soltouSobreOAlvo({{clientX: 250, clientY: 400}}, 7),
  a_esquerda_fora:        _soltouSobreOAlvo({{clientX: -10, clientY: 120}}, 7),
  sem_coordenadas:        _soltouSobreOAlvo({{}}, 7),
  evento_nulo:            _soltouSobreOAlvo(null, 7),
  toque_via_changedTouches: _soltouSobreOAlvo(
      {{changedTouches: [{{clientX: 250, clientY: 120}}]}}, 7),
  alvo_inexistente:       _soltouSobreOAlvo({{clientX: 250, clientY: 120}}, 99),
}};
console.log(JSON.stringify(casos));
"""
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(harness)
        caminho = f.name
    try:
        p = subprocess.run([node, caminho], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        r = json.loads(p.stdout)
    finally:
        os.unlink(caminho)

    # Só a faixa central aninha.
    assert r['centro_da_linha'] is True
    assert r['toque_via_changedTouches'] is True

    # Tudo o mais cai para reordenação — o comportamento pré-Fase 6.
    assert r['borda_de_cima'] is False
    assert r['borda_de_baixo'] is False
    assert r['abaixo_da_tabela'] is False, 'ESTE é o bug: soltar fora aninhava'
    assert r['a_esquerda_fora'] is False
    assert r['sem_coordenadas'] is False
    assert r['evento_nulo'] is False
    assert r['alvo_inexistente'] is False
