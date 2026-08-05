"""A cadeia CRM → Proposta → Obra → Lead, pelas ROTAS.

Bloco B3 (§6.1) do `docs/superpowers/plans/2026-08-04-plano-consolidado.md`.

Este arquivo cobre as Tasks **B3.1** (perna da obra do A07), **B3.2** (perna da
proposta do A07) e **B3.3** (A22, só o select). Os casos T3 (segunda metade,
``Lead.proposta_id``), T4, T5 e T6 (segunda metade, ``Lead.obra_id``) pertencem
a B3.4/B3.5 e **não** estão aqui.

**Por que por rota.** O defeito que o bloco ataca é exatamente de acoplamento
entre peças vivas: o CRM monta a query string, o alias a descarta no 302 e o
formulário nunca a lê. Nenhuma das três pontas está quebrada isoladamente —
é a costura que não existe. Um teste que chame ``nova()`` direto acharia tudo
em ordem.

**Regra de tenant.** Um request AUTENTICADO por ``app.app_context()``: ``g``
pertence ao app context e o Flask-Login cacheia o usuário em ``g._login_user``,
então um segundo `test_client` dentro do mesmo contexto rodaria COMO O
PRIMEIRO. Aqui cada teste usa **um único** tenant como autor dos requests; o
outro tenant existe só como precondição semeada direto no banco, e é pela
``marca`` dele que se procura o vazamento.
"""
import os
import re
import sys
from datetime import date
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import Cliente, Lead, LeadStatus, Proposta, Servico

from helpers_tenant import cliente_de, dois_tenants, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cadeia-crm'
    yield


# ---------------------------------------------------------------------------
# Semente comum: um Servico ativo e um Lead ENVIADO já amarrado ao Cliente.
# ---------------------------------------------------------------------------

def _servico(tenant):
    s = Servico(nome=f'Servico {tenant.marca}', admin_id=tenant.admin_id,
                ativo=True, unidade_medida='m2', categoria='estrutural')
    db.session.add(s)
    db.session.flush()
    return s


def _lead(tenant, status=LeadStatus.ENVIADO):
    """Lead com ``cliente_id`` já resolvido.

    Sem ``cliente_id`` as duas rotas do CRM chamam
    ``vincular_ou_criar_cliente`` e commitam — o teste passaria a medir aquele
    helper em vez da passagem dos args.
    """
    lead = Lead(nome=f'Lead {tenant.marca}', admin_id=tenant.admin_id,
                data_chegada=date(2026, 6, 1), status=status.value,
                cliente_id=tenant.cliente_id)
    db.session.add(lead)
    db.session.commit()
    return lead


def _corpo(resposta):
    return resposta.get_data(as_text=True)


def _trecho_select_cliente(html):
    """O bloco ``<select name="cliente_id" …>…</select>``, ou '' se não houver.

    Procurar ``selected`` no documento inteiro daria falso positivo em
    qualquer outro select da página.
    """
    m = re.search(r'<select[^>]*name="cliente_id".*?</select>', html,
                  re.DOTALL | re.IGNORECASE)
    return m.group(0) if m else ''


def _valor_do_input(html, nome):
    """``value`` do primeiro ``<input …name="<nome>"…>``, ou None."""
    m = re.search(r'<input[^>]*name="%s"[^>]*>' % re.escape(nome), html,
                  re.IGNORECASE)
    if not m:
        return None
    v = re.search(r'value="([^"]*)"', m.group(0))
    return v.group(1) if v else ''


# ---------------------------------------------------------------------------
# T1 — CRM → alias → /propostas/nova, atravessando os dois 302
# ---------------------------------------------------------------------------

def test_t1_gerar_proposta_do_crm_chega_com_cliente_e_lead_preenchidos():
    """A costura inteira: `crm_views.py:936-939` → alias `:1186-1188` → `nova()`.

    O alias hoje é ``redirect(url_for('propostas.nova'))`` — **sem** query
    string — e ``nova()`` não lê ``request.args``. Qualquer uma das duas
    metades sozinha é no-op; por isso o teste atravessa os dois redirects em
    vez de bater direto em `/propostas/nova`.
    """
    with app.app_context():
        a = um_tenant('cadeia1', com_fatos=False)
        _servico(a)
        lead = _lead(a)
        cliente_nome = Cliente.query.get(a.cliente_id).nome

        resp = cliente_de(a.admin_id).get(
            f'/crm/{lead.id}/gerar_proposta', follow_redirects=True)
        assert resp.status_code == 200, (
            f'a cadeia CRM→proposta respondeu {resp.status_code}')
        html = _corpo(resp)

        select = _trecho_select_cliente(html)
        assert select, (
            'o formulário de nova proposta não tem <select name="cliente_id"> '
            '— A22 continua aberto')
        assert cliente_nome in select, (
            f'o cliente do tenant ({cliente_nome}) nem aparece nas options')
        marcada = re.search(
            r'<option[^>]*value="%d"[^>]*selected' % a.cliente_id, select)
        assert marcada, (
            f'a option do cliente {a.cliente_id} não veio selected — o '
            f'cliente_id do CRM se perdeu no caminho')

        assert _valor_do_input(html, 'lead_id') == str(lead.id), (
            f'hidden lead_id deveria valer {lead.id}, veio '
            f'{_valor_do_input(html, "lead_id")!r}')


# ---------------------------------------------------------------------------
# T2 — cliente de outro tenant não pré-seleciona nada, e não vaza
# ---------------------------------------------------------------------------

def test_t2_cliente_de_outro_tenant_nao_pre_seleciona_nem_vaza():
    """200 com o corpo limpo, **não** 404.

    O ``except Exception`` de `propostas_consolidated.py:542-545` engoliria um
    ``abort(404)`` e devolveria 302 para `propostas.index` — o vazamento
    ficaria escondido atrás de um status inocente. Quem prova o tenant aqui é
    o CONTEÚDO renderizado.
    """
    with app.app_context():
        a, b = dois_tenants('cadeia2', com_fatos=False)

        resp = cliente_de(a.admin_id).get(
            f'/propostas/nova?cliente_id={b.cliente_id}&lead_id=999999')
        assert resp.status_code == 200, (
            f'esperava 200 (o tenant se prova pelo conteúdo), veio '
            f'{resp.status_code}')
        html = _corpo(resp)

        select = _trecho_select_cliente(html)
        assert select, ('sem <select name="cliente_id"> não há o que provar '
                        '— A22 continua aberto')
        # A ordem importa: esta asserção vem ANTES da marca porque é a única
        # que pega a implementação ingênua de pré-seleção — a que resolve o
        # `cliente_pre` sem escopo e o injeta como option extra "para garantir
        # que apareça". Depois da asserção de marca ela nunca dispararia, e um
        # assert que nunca dispara não é teste, é decoração.
        assert 'selected' not in select, (
            'um cliente de outro tenant foi pré-selecionado')
        assert b.marca not in html, (
            f'a marca do tenant B ({b.marca}) vazou no formulário de A')


# ---------------------------------------------------------------------------
# T3 (primeira metade) — o POST manual grava `proposta.cliente_id`
# ---------------------------------------------------------------------------

def test_t3_criar_proposta_pelo_select_grava_cliente_id():
    """Sem ``cliente_nome`` no POST — quem nomeia o cliente é o ``cliente_id``.

    É a metade da cadeia que quebra produção se sair pela metade: `:567-569`
    valida ``cliente_nome`` como obrigatório e `:651` o grava numa coluna NOT
    NULL. Este POST omite o campo de texto de propósito.
    """
    with app.app_context():
        a = um_tenant('cadeia3', com_fatos=False)
        servico = _servico(a)
        lead = _lead(a)
        cliente = Cliente.query.get(a.cliente_id)
        cliente_nome = cliente.nome
        titulo = f'Proposta cadeia {uuid4().hex[:8]}'

        resp = cliente_de(a.admin_id).post('/propostas/criar', data={
            'cliente_id': str(a.cliente_id),
            'lead_id': str(lead.id),
            'assunto': titulo,
            'objeto': 'Objeto da proposta da cadeia',
            'item_descricao': 'Item 1',
            'item_quantidade': '10',
            'item_unidade': 'm2',
            'item_preco': '100,00',
            'item_servico_id': str(servico.id),
        })
        assert resp.status_code in (200, 302), (
            f'/propostas/criar respondeu {resp.status_code}')

        db.session.expire_all()
        p = Proposta.query.filter_by(
            admin_id=a.admin_id, titulo=titulo).first()
        assert p is not None, (
            'a proposta não foi criada — o formulário manual ainda exige o '
            'input de texto cliente_nome')
        assert p.cliente_id == a.cliente_id, (
            f'proposta.cliente_id deveria ser {a.cliente_id}, veio '
            f'{p.cliente_id!r} — o resolver de cliente vai duplicar o Cliente '
            f'na aprovação')
        assert p.cliente_nome == cliente_nome, (
            f'cliente_nome deveria vir do cadastro ({cliente_nome}), veio '
            f'{p.cliente_nome!r}')


def test_t3b_cliente_de_outro_tenant_no_post_nao_e_gravado():
    """O ``cliente_id`` do POST é um dado do usuário — vale o mesmo escopo."""
    with app.app_context():
        a, b = dois_tenants('cadeia3b', com_fatos=False)
        titulo = f'Proposta invasora {uuid4().hex[:8]}'

        cliente_de(a.admin_id).post('/propostas/criar', data={
            'cliente_id': str(b.cliente_id),
            'cliente_nome': 'Digitado à mão',
            'assunto': titulo,
            'item_descricao': 'Item 1',
            'item_quantidade': '1',
            'item_unidade': 'un',
            'item_preco': '10,00',
        })

        db.session.expire_all()
        p = Proposta.query.filter_by(
            admin_id=a.admin_id, titulo=titulo).first()
        if p is not None:
            assert p.cliente_id != b.cliente_id, (
                f'a proposta de A ficou amarrada ao Cliente {b.cliente_id} '
                f'do tenant B')


# ---------------------------------------------------------------------------
# T6 (primeira metade) — a perna da obra, que não passa por alias nenhum
# ---------------------------------------------------------------------------

def test_t6_criar_obra_do_crm_chega_com_cliente_pre_preenchido():
    """`crm_views.py:974-977` → `main.nova_obra` GET, rota direta.

    A query string chega íntegra e hoje é descartada no ramo GET
    (`views/obras.py:498-523`).
    """
    with app.app_context():
        a = um_tenant('cadeia6', com_fatos=False)
        lead = _lead(a)
        cliente_nome = Cliente.query.get(a.cliente_id).nome

        resp = cliente_de(a.admin_id).get(
            f'/crm/{lead.id}/criar_obra', follow_redirects=True)
        assert resp.status_code == 200, (
            f'a cadeia CRM→obra respondeu {resp.status_code}')
        html = _corpo(resp)

        assert _valor_do_input(html, 'cliente_id') == str(a.cliente_id), (
            f'hidden cliente_id deveria valer {a.cliente_id}, veio '
            f'{_valor_do_input(html, "cliente_id")!r}')
        assert _valor_do_input(html, 'cliente_busca') == cliente_nome, (
            f'a caixa de busca deveria mostrar {cliente_nome!r}, veio '
            f'{_valor_do_input(html, "cliente_busca")!r}')
        assert _valor_do_input(html, 'lead_id') == str(lead.id), (
            f'hidden lead_id deveria valer {lead.id}, veio '
            f'{_valor_do_input(html, "lead_id")!r}')


def test_t6b_cliente_de_outro_tenant_nao_pre_preenche_a_obra():
    """Mesma regra do T2 na perna da obra: não pré-seleciona e **não** aborta.

    O ``except Exception`` de `views/obras.py:511-514` e o try de `:499`
    transformariam um abort em formulário sem funcionários nem serviços.
    """
    with app.app_context():
        a, b = dois_tenants('cadeia6b', com_fatos=False)

        resp = cliente_de(a.admin_id).get(
            f'/obras/nova?cliente_id={b.cliente_id}&lead_id=999999')
        assert resp.status_code == 200, (
            f'esperava 200, veio {resp.status_code}')
        html = _corpo(resp)

        assert b.marca not in html, (
            f'a marca do tenant B ({b.marca}) vazou no formulário de obra de A')
        assert _valor_do_input(html, 'cliente_id') == '', (
            'um cliente de outro tenant foi pré-preenchido na nova obra')
