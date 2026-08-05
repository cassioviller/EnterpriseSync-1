"""Arreio da trilha T3 — dedup de NF e isolamento de tenant.

**Passo 0 do bloco: este arquivo nasce VERMELHO**, e é isso que se quer. Sem os
dois tenants semeados lado a lado e postando nas rotas, "não vaza" é opinião —
foi o critério do p1 Step 0 (`c9138a39`) e vale igual aqui.

O que ele cobre, e por que cada caso existe:

* **A09 (dedup de NF).** `views/almoxarifado/movimentos.py` lê `nota_fiscal` em
  `:47` (form) e `:217` (JSON) e grava em seis pontos sem verificação nenhuma. A
  única guarda viva é por número de série (`:88-96`), que só alcança item
  SERIALIZADO — o consumível não tem defesa: reenviar o formulário duplica
  estoque em silêncio. F5 numa tela de entrada é operação de rotina.
* **O vazamento de tenant DE VERDADE**, que não está em nenhum dos dois
  documentos do backlog e fica 40 linhas abaixo do que eles apontam:
  `views/obras.py:791-798` junta `ServicoObraReal` com `Servico` filtrando
  `ServicoObraReal.admin_id` e `Servico.ativo` — e **nunca `Servico.admin_id`**.
  O fallback logo abaixo (`:856`) faz certo, com `s.admin_id = :admin_id`: é a
  mesma pergunta feita duas vezes no mesmo arquivo, com respostas diferentes.
* **B1.15 — o 403 que conta o que não devia** (T5, escrito em 05/08). A rota JSON
  `processar-entrada-multipla` filtra `admin_id` e não vaza dado nenhum; vaza o
  **status**, porque 403 responde "existe, não é seu" e 404 responde "não existe".
  ⚠️ **Este caso estava no recorte da T3 desde o começo e não foi escrito** — o
  plano marcou o Step 1 da B1.12 incluindo o T5, e `grep` pelo nome da rota em
  `tests/` devolvia vazio. Ficou de aviso: checkbox de arreio se confere com grep.

O que ele deliberadamente NÃO cobre: `almoxarifado_utils.py:257`. Confirmado que
`processar_xml_nfe` (`:250`) **não tem chamador vivo** — `grep` fora de `archive/`
devolve só a definição. Corrigi-la sozinha pioraria: com `admin_id` na consulta o
fluxo passaria a alcançar o `flush()` e estouraria `IntegrityError` contra o
UNIQUE **global** de `NotaFiscal.chave_acesso` (`models.py:2626`), trocando uma
mensagem amigável errada por um 500. Foi essa a razão do **corte da Task B1.14 em
05/08** (§8.1 do plano consolidado).
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (AlmoxarifadoCategoria, AlmoxarifadoEstoque,
                    AlmoxarifadoItem, AlmoxarifadoMovimento, Fornecedor,
                    RDO, RDOServicoSubatividade, Servico, ServicoObraReal)

from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

DIA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-arreio-almox'
    yield


def _almoxarifado_de(tenant):
    """Categoria + item CONSUMIVEL + fornecedor do tenant.

    `helpers_tenant` não semeia almoxarifado, e `categoria_id` é NOT NULL
    (`models.py:5253`) — daí a categoria vir antes do item.

    O item é CONSUMIVEL de propósito: é o perfil **sem defesa nenhuma**. O
    serializado ao menos esbarra na guarda de número de série (`:88-96`), que
    recusa a segunda entrada por acidente de unicidade — não por dedup de NF.
    """
    cat = AlmoxarifadoCategoria(nome=f'Cat {tenant.marca}',
                                tipo_controle_padrao='CONSUMIVEL',
                                admin_id=tenant.admin_id)
    db.session.add(cat)
    db.session.flush()

    item = AlmoxarifadoItem(
        codigo=f'IT{uuid.uuid4().hex[:8].upper()}', nome=f'Item {tenant.marca}',
        categoria_id=cat.id, tipo_controle='CONSUMIVEL',
        admin_id=tenant.admin_id)
    db.session.add(item)

    forn = Fornecedor(nome=f'Fornecedor {tenant.marca}',
                      razao_social=f'Fornecedor {tenant.marca}',
                      cnpj=f'{uuid.uuid4().int % 10**14:014d}',
                      admin_id=tenant.admin_id)
    db.session.add(forn)
    db.session.commit()
    return item, forn


def _entrada(tenant, item, fornecedor, nf, quantidade=10.0):
    """``POST /almoxarifado/processar-entrada`` — form, redireciona com flash."""
    cli = cliente_de(tenant.admin_id)
    return cli.post('/almoxarifado/processar-entrada', data={
        'item_id': str(item.id),
        'tipo_controle': 'CONSUMIVEL',
        'nota_fiscal': nf,
        'valor_unitario': '25.00',
        'quantidade': str(quantidade),
        'fornecedor_id': str(fornecedor.id),
    })


def _movimentos(tenant, nf=None):
    db.session.expire_all()
    q = AlmoxarifadoMovimento.query.filter_by(admin_id=tenant.admin_id,
                                              tipo_movimento='ENTRADA')
    if nf is not None:
        q = q.filter(AlmoxarifadoMovimento.nota_fiscal == nf)
    return q.all()


def _estoque_total(tenant, item):
    db.session.expire_all()
    linhas = AlmoxarifadoEstoque.query.filter_by(
        admin_id=tenant.admin_id, item_id=item.id).all()
    return sum(float(e.quantidade or 0) for e in linhas)


# ---------------------------------------------------------------------------
# T1, T2, T3 — dedup de nota fiscal (A09)
# ---------------------------------------------------------------------------

def test_reenviar_a_mesma_nota_fiscal_nao_duplica_estoque():
    """F5 na tela de entrada não pode virar estoque em dobro.

    A guarda de número de série (`:88-96`) só alcança item SERIALIZADO. Para
    consumível não existe defesa: os dois POSTs gravam dois
    `AlmoxarifadoMovimento` e duas linhas de `AlmoxarifadoEstoque`, e o estoque
    do item passa a valer o dobro do que a nota diz.
    """
    with app.app_context():
        t = um_tenant('nfdup', data_ref=DIA, com_fatos=False)
        item, forn = _almoxarifado_de(t)

        _entrada(t, item, forn, 'NF-4321', quantidade=10.0)
        depois_da_primeira = _estoque_total(t, item)

        _entrada(t, item, forn, 'NF-4321', quantidade=10.0)

        movimentos = _movimentos(t, 'NF-4321')
        assert len(movimentos) == 1, (
            f'a mesma NF entrou {len(movimentos)} vezes — reenviar o formulário '
            f'duplica estoque')
        assert _estoque_total(t, item) == pytest.approx(depois_da_primeira), (
            f'o estoque foi de {depois_da_primeira} para '
            f'{_estoque_total(t, item)} com a mesma nota fiscal')


def test_a_nota_de_um_tenant_nao_recusa_a_entrada_do_outro():
    """A dedup tem de ser POR TENANT, e este caso é o que impede o conserto
    errado.

    🔬 A tentação, ao consertar A09, é uma chave global de `nota_fiscal` — e
    seria repetir o defeito que já existe um andar acima: o UNIQUE **global** de
    `NotaFiscal.chave_acesso` (`models.py:2550`), que faz a nota de uma empresa
    bloquear a de outra. Dois fornecedores diferentes emitem notas com o mesmo
    número o tempo todo; a numeração é sequencial por emitente, não universal.

    🔬 **UM POST só, e a nota de A é semeada direto no banco.** A primeira versão
    postava pelas duas rotas e media errado: o segundo cliente não completa
    dentro do mesmo ``app_context`` — é o mesmo defeito de construção que já
    apareceu duas vezes nesta rodada (`tests/test_arreio_custo_rdo_rotas.py`
    registra os dois casos). O que interessa aqui é a **precondição** (existe
    NF-1000 em A) e **uma** ação (B posta), então o cenário não precisa da
    segunda rota — e sem ela o teste mede o que diz medir.
    """
    with app.app_context():
        a = um_tenant('nfA', data_ref=DIA, com_fatos=False)
        b = um_tenant('nfB', data_ref=DIA, com_fatos=False)
        item_a, _ = _almoxarifado_de(a)
        item_b, forn_b = _almoxarifado_de(b)

        # Precondição: A já tem NF-1000 lançada. Semeada, não postada.
        db.session.add(AlmoxarifadoMovimento(
            item_id=item_a.id, tipo_movimento='ENTRADA', quantidade=10,
            valor_unitario=25.0, nota_fiscal='NF-1000',
            admin_id=a.admin_id, usuario_id=a.admin_id))
        db.session.commit()

        _entrada(b, item_b, forn_b, 'NF-1000')

        assert len(_movimentos(a, 'NF-1000')) == 1, (
            'a entrada semeada de A sumiu — cenário quebrado')
        assert len(_movimentos(b, 'NF-1000')) == 1, (
            'a nota de A recusou a entrada de B — a dedup ficou global em vez '
            'de por tenant, repetindo o defeito de NotaFiscal.chave_acesso')


def test_nota_fiscal_vazia_nao_e_chave_de_dedup():
    """Sem NF, cada entrada é uma entrada.

    Campo vazio é o default do formulário (`:47` faz `.strip()` sobre
    `''`). Tratá-lo como chave faria a segunda compra sem nota sumir — e
    entrada sem NF é rotina em obra: compra de balcão, doação, sobra de outra
    obra. Este teste passa hoje e existe para não deixar a correção de A09
    quebrá-lo.
    """
    with app.app_context():
        t = um_tenant('nfvazia', data_ref=DIA, com_fatos=False)
        item, forn = _almoxarifado_de(t)

        _entrada(t, item, forn, '', quantidade=5.0)
        _entrada(t, item, forn, '', quantidade=5.0)

        movimentos = [m for m in _movimentos(t) if not (m.nota_fiscal or '')]
        assert len(movimentos) == 2, (
            f'entradas sem nota fiscal foram deduplicadas entre si: '
            f'{len(movimentos)} movimento(s) para dois lançamentos legítimos')


# ---------------------------------------------------------------------------
# T4 — o vazamento de catálogo na tela da obra
# ---------------------------------------------------------------------------

def test_obter_servicos_da_obra_nao_devolve_servico_de_outro_tenant():
    """`Servico` alheio não pode sair desta consulta.

    O join de `views/obras.py:791-798` filtra `ServicoObraReal.admin_id` e
    `Servico.ativo`, mas **não** `Servico.admin_id`. Basta um `ServicoObraReal`
    apontando para serviço de outro tenant — que nada impede, porque a FK não
    conhece fronteira de tenant — para nome, categoria, unidade e
    `custo_unitario` alheios saírem em `servicos_lista` (`:803-808`).

    O fallback de `:856` já faz certo, com `s.admin_id = :admin_id`. É a mesma
    pergunta, duas vezes no mesmo arquivo, com respostas diferentes.

    🔬 **Este teste afirma sobre a FUNÇÃO, e não sobre o corpo da resposta, e a
    razão é uma medição que corrige o recorte.** O plano diz que os dados alheios
    "sobem para a tela de detalhes/edição da obra". Medido nas duas rotas vivas:
    **não sobem.** `/obras/<id>` passa `servicos_obra` para
    `obras/detalhes_obra_profissional.html`, que **não referencia a variável**; e
    `/obras/editar/<id>` reduz a lista a IDs (`:1105`) usados só para marcar
    checkbox (`templates/obra_form.html:666`), e id alheio nunca casa com um
    serviço listado. As duas respondem 200 sem o nome no corpo.

    Ou seja: o defeito da consulta é real e sai por ela, mas **não é vazamento
    observável pelo usuário hoje** — é a mesma classificação que o plano deu ao
    `views/obras.py:743-757`, e vale a mesma consequência: **não entra no
    changelog como `fix(tenant)`**. Um teste por corpo de resposta aqui seria
    vacuoso, e é o sexto instrumento medindo o vazio nesta rodada.
    """
    with app.app_context():
        from views.obras import obter_servicos_da_obra

        a = um_tenant('vazA', data_ref=DIA, com_fatos=False)
        b = um_tenant('vazB', data_ref=DIA, com_fatos=False)

        servico_de_b = Servico(
            nome=f'SEGREDO {b.marca}', categoria='geral', unidade_medida='un',
            custo_unitario=999.0, ativo=True, admin_id=b.admin_id)
        db.session.add(servico_de_b)
        db.session.flush()

        # Vínculo do tenant A apontando para o serviço de B. A FK permite: ela
        # não conhece fronteira de tenant, e é isso que o filtro da consulta
        # deveria estar cobrindo.
        db.session.add(ServicoObraReal(
            obra_id=a.obra_id, servico_id=servico_de_b.id,
            admin_id=a.admin_id, ativo=True))
        db.session.commit()

        devolvidos = obter_servicos_da_obra(a.obra_id, a.admin_id)
        nomes = [s['nome'] for s in devolvidos]

        assert f'SEGREDO {b.marca}' not in nomes, (
            f'o catálogo do tenant B saiu na consulta da obra de A: {nomes}')


def test_a_obra_de_outro_tenant_responde_404():
    """404, nunca 403 nem 200: 403 confirma que a obra existe.

    Passa hoje — `utils/autorizacao.py:73-99` filtra `Obra.admin_id` sempre. É
    guarda de não-regressão para as Tasks que vão mexer nesta consulta.
    """
    with app.app_context():
        a = um_tenant('obrA', data_ref=DIA, com_fatos=False)
        b = um_tenant('obrB', data_ref=DIA, com_fatos=False)

        cli = cliente_de(a.admin_id)
        r = cli.get(f'/obras/{b.obra_id}')

        assert r.status_code == 404, (
            f'obra de outro tenant respondeu {r.status_code} — 403 já confirma '
            f'que ela existe, e 200 é vazamento')


# ---------------------------------------------------------------------------
# T5 — fornecedor de outro tenant na entrada múltipla (B1.15)
# ---------------------------------------------------------------------------

def test_fornecedor_de_outro_tenant_na_entrada_multipla_responde_404():
    """Mesma doutrina do T4, na rota JSON: **404, nunca 403**.

    `views/almoxarifado/movimentos.py:271-278` já filtra `admin_id` — o dado não
    vaza. O que vaza é o **código**: 403 responde "existe, mas não é seu" e 404
    responde "não existe", e para quem está do lado de fora a diferença entre os
    dois é um oráculo de enumeração. Chuta `fornecedor_id` de 1 a 5000 e o 403
    desenha a base de fornecedores das outras empresas.

    É o critério que `955aeb9f` fixou e que o T4 já cobra na rota de obra. Este
    arquivo respondia a mesma pergunta de dois jeitos — e a rota irmã
    `processar_entrada` (`:71-74`) responde de um terceiro, por flash+redirect,
    que não é oráculo e por isso fica como está.

    A segunda asserção é a que importa tanto quanto o status: recusar **e gravar**
    seria pior que não recusar.

    🔬 **A terceira asserção é o Step 2 da B1.15 virado em teste.** O recorte
    mandava "conferir o `fetch` de `templates/almoxarifado/entrada.html:428`, que
    pode ramificar por `response.status === 403`". Conferido: **não ramifica** —
    faz `await response.json()` e decide por `result.success` (`:441-450`), então
    o código nunca chega a ele. Mas o que o JS **exige** é que o corpo continue
    sendo JSON: um 404 que caísse no handler de erro do Flask devolveria HTML, o
    `response.json()` estouraria e o usuário veria "tente novamente" em vez da
    mensagem. Conferência de olho não impede regressão; a asserção impede.
    """
    with app.app_context():
        a = um_tenant('fornA', data_ref=DIA, com_fatos=False)
        b = um_tenant('fornB', data_ref=DIA, com_fatos=False)
        item_a, _ = _almoxarifado_de(a)
        _item_b, forn_b = _almoxarifado_de(b)

        antes = len(_movimentos(a))

        cli = cliente_de(a.admin_id)
        r = cli.post('/almoxarifado/processar-entrada-multipla', json={
            'itens': [{
                'item_id': item_a.id,
                'tipo_controle': 'CONSUMIVEL',
                'quantidade': 7,
                'valor_unitario': 25.00,
            }],
            'nota_fiscal': 'NF-T5',
            'fornecedor_id': forn_b.id,
            'observacoes': '',
        })

        assert r.status_code == 404, (
            f'fornecedor de outro tenant respondeu {r.status_code} — 403 '
            f'confirma que ele existe e transforma a rota em oráculo de '
            f'enumeração')
        assert len(_movimentos(a)) == antes, (
            'a rota recusou o fornecedor alheio E gravou movimento — recusar '
            'gravando é pior que não recusar')
        assert r.is_json and r.get_json().get('success') is False, (
            f'o 404 saiu como {r.content_type} em vez de JSON — o fetch de '
            f'entrada.html:441 faz response.json() e decide por result.success; '
            f'com HTML no corpo o usuário perde a mensagem')
