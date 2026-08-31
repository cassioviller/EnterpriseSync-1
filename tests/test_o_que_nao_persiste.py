"""O que não persiste, e o que persiste pela metade.

A regra destes testes: a afirmação é olhada NO BANCO, depois do teardown da
requisição. `assert` dentro do mesmo contexto vê a SESSÃO, não o banco — e a
diferença entre as duas é exatamente onde estes defeitos moram.

Nenhum teste aqui prova por `inspect.getsource()`.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-nao-persiste'
    yield


def test_erro_ao_aprovar_compra_nao_conta_a_excecao_ao_anonimo(monkeypatch):
    """🔴 `portal_obras_views.py:648` — `flash(f'Erro ao aprovar compra: {e}')`.

    O portal é acessado por TOKEN, sem autenticação. `str(e)` de erro
    SQLAlchemy carrega o SQL e os parâmetros vinculados, e vai para a tela de
    quem tem o link.

    Nota de gatilho: `compra_id` inexistente NÃO chega ao `except` —
    `_get_compra_do_portal` (`portal_obras_views.py:530`) usa
    `.first_or_404()` e aborta ANTES do `try` (`:557`, antes do `:593`). Um
    teste que dependesse disso passaria verde sem nunca ter exercitado o
    `except` — o mesmo andaime-que-não-podia-falhar que a Task R8 da onda
    anterior tirou de `test_porta_irma.py`. Em vez disso, o erro é INJETADO:
    `processar_compra_aprovada_cliente` (chamada dentro do `try`,
    `portal_obras_views.py:627`) é trocada por uma que estoura
    `SQLAlchemyError` com SQL e parâmetros no texto, de forma
    determinística.

    A prova de que o gatilho funcionou vem do BANCO — `PortalAcessoEvento`
    com `detalhes={'resultado': 'erro'}`, gravado só dentro do `except`
    (`:645-647`) — antes de olhar o corpo da resposta. Sem essa prova
    primeiro, um teste que nunca chegasse ao `except` passaria verde do
    mesmo jeito, só que sem ter provado nada.
    """
    from models import Fornecedor, Obra, PedidoCompra, PortalAcessoEvento
    import compras_views

    def _estoura(*args, **kwargs):
        raise SQLAlchemyError(
            "(psycopg2.errors.UniqueViolation) duplicate key value "
            "violates unique constraint \"gestao_custo_pai_pkey\"\n"
            "[SQL: INSERT INTO gestao_custo_pai (obra_id, valor) "
            "VALUES (%(obra_id)s, %(valor)s)]\n"
            "[parameters: {'obra_id': 5, 'valor': Decimal('1000.00')}]")

    monkeypatch.setattr(compras_views, 'processar_compra_aprovada_cliente',
                        _estoura)

    with app.app_context():
        t = um_tenant('portal-erro', com_fatos=False)
        obra = db.session.get(Obra, t.obra_id)
        # 🔬 Campo conferido: `Obra.token_cliente` (`models.py:397`).
        obra.token_cliente = token = uuid.uuid4().hex
        # `token_cliente_expira_em` fica NULO — `_get_obra_by_token` (:89)
        # trata token expirado como ausência (404) e só NULL segue valendo.

        forn = Fornecedor(nome='Fornecedor Teste', cnpj=uuid.uuid4().hex[:18],
                          admin_id=t.admin_id, ativo=True)
        db.session.add(forn)
        db.session.flush()

        compra = PedidoCompra(
            fornecedor_id=forn.id, data_compra=date(2026, 8, 1),
            obra_id=obra.id, condicao_pagamento='a_vista', parcelas=1,
            valor_total=Decimal('1000.00'), tipo_compra='aprovacao_cliente',
            processada_apos_aprovacao=False, admin_id=t.admin_id,
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE')
        db.session.add(compra)
        db.session.commit()
        compra_id = compra.id
        obra_id = obra.id

    cliente = app.test_client()
    resposta = cliente.post(f'/portal/obra/{token}/compra/{compra_id}/aprovar',
                            data={}, follow_redirects=True)
    corpo = resposta.get_data(as_text=True)

    with app.app_context():
        eventos_de_erro = [
            ev for ev in PortalAcessoEvento.query.filter_by(
                obra_id=obra_id, acao='compra_aprovar',
                alvo_tipo='pedido_compra', alvo_id=compra_id).all()
            if (ev.detalhes or {}).get('resultado') == 'erro'
        ]
        # PRIMEIRO: o gatilho tem que ter funcionado de verdade — senão o
        # que segue passa verde sem ter exercitado o `except`.
        assert len(eventos_de_erro) == 1, (
            'o `except` de aprovar_compra não rodou — o gatilho (erro '
            'injetado em processar_compra_aprovada_cliente) parou de '
            'funcionar, e este teste não prova mais nada')

    for vazamento in ('[SQL:', '[parameters:', 'psycopg2.', 'sqlalchemy.exc',
                      'Traceback (most recent call last)'):
        assert vazamento not in corpo, (
            f'{vazamento!r} vazou para visitante anônimo do portal')


def _obra_com_token(marca):
    from models import Obra
    from helpers_tenant import um_tenant

    t = um_tenant(marca, com_fatos=False)
    obra = db.session.get(Obra, t.obra_id)
    # 🔬 Campo conferido: `Obra.token_cliente` (`models.py:397`).
    obra.token_cliente = token = uuid.uuid4().hex
    db.session.commit()
    return t, token


def _compra_do_portal(t, obra, status='AGUARDANDO_APROVACAO_CLIENTE'):
    """Uma `PedidoCompra` real, do tipo que o portal de fato oferece.

    🔬 O andaime que o brief propunha usava `compra_id=999999999` — mas
    `_get_compra_do_portal` (`portal_obras_views.py:530`) usa
    `.first_or_404()` e aborta ANTES de `_registrar_acesso` ser chamado, tanto
    em `ver_comprovante` (`:785`) quanto em `upload_comprovante` (`:707`). Um
    id inexistente nunca alcançaria o trecho sob teste — o mesmo
    andaime-que-não-podia-falhar que a Task 1 deste plano já tinha achado em
    `aprovar_compra`. Por isso a compra aqui é real: pertence ao tenant, à
    obra, e tem `tipo_compra='aprovacao_cliente'`.
    """
    from models import Fornecedor, PedidoCompra

    forn = Fornecedor(nome='Fornecedor Teste', cnpj=uuid.uuid4().hex[:18],
                      admin_id=t.admin_id, ativo=True)
    db.session.add(forn)
    db.session.flush()

    compra = PedidoCompra(
        fornecedor_id=forn.id, data_compra=date(2026, 8, 1),
        obra_id=obra.id, condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1000.00'), tipo_compra='aprovacao_cliente',
        processada_apos_aprovacao=False, admin_id=t.admin_id,
        status_aprovacao_cliente=status)
    db.session.add(compra)
    db.session.commit()
    return compra


def test_visualizacao_de_comprovante_deixa_rastro():
    """🔴 `portal_obras_views.py:785` — registra e devolve `send_file` sem
    commit algum.

    `_registrar_acesso` não commita (docstring `:138`), e o `session.remove()`
    do teardown desfaz o evento. Toda visualização de comprovante de
    pagamento pelo cliente sumia — e é o acesso que mais interessa auditar.

    A conferência é feita em contexto NOVO, depois do teardown: dentro da
    mesma sessão o evento apareceria e o teste passaria por engano.

    A compra não precisa ter arquivo físico: `_registrar_acesso` roda ANTES
    de `_arquivo_comprovante` resolver o caminho em disco (`:786`), então o
    404 de arquivo ausente não impede o evento de ter sido gravado — é
    justamente essa gravação que este teste prova.
    """
    from models import Obra, PortalAcessoEvento

    with app.app_context():
        t, token = _obra_com_token('portal-trilha')
        obra = db.session.get(Obra, t.obra_id)
        compra = _compra_do_portal(t, obra, status='APROVADO')
        obra_id = t.obra_id
        compra_id = compra.id
        antes = PortalAcessoEvento.query.filter_by(
            obra_id=obra_id, acao='compra_comprovante_ver').count()

    app.test_client().get(
        f'/portal/obra/{token}/compra/{compra_id}/comprovante')

    with app.app_context():
        depois = PortalAcessoEvento.query.filter_by(
            obra_id=obra_id, acao='compra_comprovante_ver').count()
        assert depois > antes, (
            'a visualização de comprovante não deixou rastro — o teardown '
            'desfez o evento que ninguém commitou')


def test_tentativa_recusada_no_portal_tambem_deixa_rastro():
    """🔴 `:707` `upload_comprovante` — registra na entrada e tem saídas
    antecipadas que nunca alcançam commit.

    Upload sem arquivo selecionado (mesma família de saída antecipada que
    tipo errado, >5 MB, ou compra fora de APROVADO) some da trilha. É
    exatamente o conjunto de tentativas para o qual uma auditoria existe.
    """
    from models import Obra, PortalAcessoEvento

    with app.app_context():
        t, token = _obra_com_token('portal-recusa')
        obra = db.session.get(Obra, t.obra_id)
        compra = _compra_do_portal(t, obra, status='APROVADO')
        obra_id = t.obra_id
        compra_id = compra.id
        antes = PortalAcessoEvento.query.filter_by(obra_id=obra_id).count()

    app.test_client().post(
        f'/portal/obra/{token}/compra/{compra_id}/comprovante',
        data={}, follow_redirects=True)

    with app.app_context():
        depois = PortalAcessoEvento.query.filter_by(obra_id=obra_id).count()
        assert depois > antes, (
            'a tentativa recusada de upload não deixou rastro')


def test_reativar_tarefa_arquivada_limpa_arquivada_em_e_cascateia():
    """🔴 `cronograma_proposta.py:609` — `if not t.ativa: t.ativa = True`.

    Reimplementa incompleto o `reativar_tarefas_de_itens_reincluidos`
    (`:892`), que cumpre DUAS obrigações: limpa `arquivada_em` e cascateia
    para as filhas. O inline faz nem uma nem outra.

    `ativa=True` com `arquivada_em` preenchido é estado que nenhum outro
    escritor produz — e que o próprio restaurador nunca poderá limpar,
    porque filtra `ativa.is_(False)`.

    🔬 Andaime: o brief original passava `[pai.gerada_por_proposta_item_id]`
    sem nunca ter setado esse campo no construtor — `None`, filtrado pelo
    `if i` de `reativar_tarefas_de_itens_reincluidos` (`:927`), vira lista
    vazia, e a função devolve 0 ANTES de tocar em qualquer tarefa
    (`if not ids: return 0`, `:928-929`). Isso teria dado RED por um motivo
    que nada tem a ver com o defeito — o gatilho nem chegava na cascata. Por
    isso aqui há um `PropostaItem` real, ligado ao pai por
    `gerada_por_proposta_item_id`, exatamente como o próprio brief avisou
    que seria preciso.
    """
    from datetime import datetime

    from models import Proposta, PropostaItem, TarefaCronograma

    with app.app_context():
        t = um_tenant('reativa', com_fatos=False)
        arquivada = datetime(2026, 8, 1)

        proposta = Proposta(
            numero=f'P-{uuid.uuid4().hex[:8]}', admin_id=t.admin_id,
            cliente_nome='Cliente Teste')
        db.session.add(proposta)
        db.session.flush()

        item = PropostaItem(
            admin_id=t.admin_id, proposta_id=proposta.id, item_numero=1,
            descricao='Servico do item', quantidade=Decimal('1'),
            unidade='un', preco_unitario=Decimal('100.00'), ordem=1)
        db.session.add(item)
        db.session.flush()

        pai = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'Servico {uuid.uuid4().hex[:6]}', ordem=0,
            responsavel='propria', duracao_dias=5,
            percentual_concluido=0.0, ativa=False, arquivada_em=arquivada,
            gerada_por_proposta_item_id=item.id)
        db.session.add(pai)
        db.session.flush()

        filha = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'Sub {uuid.uuid4().hex[:6]}', ordem=1,
            responsavel='propria', duracao_dias=2,
            percentual_concluido=0.0, ativa=False, arquivada_em=arquivada,
            tarefa_pai_id=pai.id)
        db.session.add(filha)
        db.session.commit()

        from services.cronograma_proposta import (
            reativar_tarefas_de_itens_reincluidos)
        # A prova é do INVARIANTE, não do caminho: depois de restaurar, não
        # pode existir tarefa viva com lápide, nem filha esquecida.
        n = reativar_tarefas_de_itens_reincluidos(
            t.obra_id, t.admin_id, [pai.gerada_por_proposta_item_id])
        assert n == 2, (
            f'o restaurador reativou {n} tarefa(s), esperava 2 (pai+filha) '
            '— o gatilho não atravessou a cascata')
        db.session.commit()

        for alvo, rotulo in ((pai, 'o serviço'), (filha, 'a subtarefa')):
            db.session.refresh(alvo)
            assert alvo.ativa is True, f'{rotulo} não voltou'
            assert alvo.arquivada_em is None, (
                f'{rotulo} voltou viva com lápide: ativa=True e '
                f'arquivada_em={alvo.arquivada_em}')


def test_materializar_cronograma_reativa_por_id_proprio_nao_pelo_da_revisao_atual():
    """🔴 `cronograma_proposta.py:609` e `:685`, no PONTO DE CHAMADA real —
    dentro de `materializar_cronograma`, não chamando o restaurador direto.

    A pré-condição que o brief não conferiu: `reativar_tarefas_de_itens_
    reincluidos` casa tarefa por `gerada_por_proposta_item_id.in_(ids)`
    (`:934-940`). Mas o nó de árvore que bate no natural-key match
    (`existente_serv = nat_idx.get(chave_serv)`, `:601`) é casado por NOME,
    não por id — e `pi_id` ali (`nivel0.get('proposta_item_id')`) é o id do
    `PropostaItem` da revisão ATUAL, que `propostas_handlers.py:97-98`
    documenta ser um CLONE com id novo a cada revisão ("valor novo é sempre
    o id de um PropostaItem recém-clonado"). A tarefa arquivada guarda o id
    do clone ANCESTRAL que a materializou originalmente — quase sempre
    diferente do `pi_id` da revisão corrente.

    Delegar com `reativar_tarefas_de_itens_reincluidos(obra_id, admin_id,
    [pi_id])` (a correção ingênua do brief) faria a seed query da função
    não achar a própria tarefa casada — `alvo` ficaria vazio e ela
    continuaria `ativa=False` para sempre, uma REGRESSÃO pior que o defeito
    atual (que ao menos reativava a flag, mesmo sem limpar a lápide). A
    correção usada aqui passa `tarefa_serv.gerada_por_proposta_item_id`
    (o id que a própria tarefa carrega) junto com `pi_id`, garantindo
    auto-casamento na seed independente de qual dos dois a query pede.
    """
    from datetime import datetime

    from models import Proposta, PropostaItem, TarefaCronograma
    from services.cronograma_proposta import materializar_cronograma

    with app.app_context():
        t = um_tenant('reativa3', com_fatos=False)
        arquivada = datetime(2026, 8, 1)

        proposta = Proposta(
            numero=f'P-{uuid.uuid4().hex[:8]}', admin_id=t.admin_id,
            cliente_nome='Cliente Teste')
        db.session.add(proposta)
        db.session.flush()

        # Item ANCESTRAL — o clone que materializou a tarefa originalmente,
        # antes de o item ser suprimido numa revisão e a tarefa arquivada.
        item_ancestral = PropostaItem(
            admin_id=t.admin_id, proposta_id=proposta.id, item_numero=1,
            descricao='Item ancestral', quantidade=Decimal('1'),
            unidade='un', preco_unitario=Decimal('100.00'), ordem=1)
        db.session.add(item_ancestral)
        db.session.flush()

        # Item da revisão ATUAL — clone com id novo, é o que
        # `nivel0.get('proposta_item_id')` traz para materializar_cronograma.
        item_atual = PropostaItem(
            admin_id=t.admin_id, proposta_id=proposta.id, item_numero=1,
            descricao='Item atual', quantidade=Decimal('1'),
            unidade='un', preco_unitario=Decimal('100.00'), ordem=1)
        db.session.add(item_atual)
        db.session.flush()

        nome_raiz = f'Servico {uuid.uuid4().hex[:6]}'
        nome_filha = f'Sub {uuid.uuid4().hex[:6]}'

        raiz = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id, nome_tarefa=nome_raiz,
            ordem=0, responsavel='empresa', duracao_dias=5,
            percentual_concluido=0.0, ativa=False, arquivada_em=arquivada,
            gerada_por_proposta_item_id=item_ancestral.id)
        db.session.add(raiz)
        db.session.flush()

        filha = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id, nome_tarefa=nome_filha,
            ordem=1, responsavel='empresa', duracao_dias=2,
            percentual_concluido=0.0, ativa=False, arquivada_em=arquivada,
            tarefa_pai_id=raiz.id,
            gerada_por_proposta_item_id=item_ancestral.id)
        db.session.add(filha)
        db.session.commit()
        raiz_id, filha_id = raiz.id, filha.id

        arvore = [{
            'marcado': True,
            'servico_nome': nome_raiz,
            'proposta_item_id': item_atual.id,  # id da revisão ATUAL — != item_ancestral.id
            'servico_id': None,
            'sem_template': False,
            'filhos': [
                {'marcado': True, 'nome': nome_filha},
            ],
        }]

        criadas = materializar_cronograma(
            proposta, t.admin_id, t.obra_id, arvore)
        db.session.commit()

        # PRIMEIRO: prova de que o gatilho passou pelo caminho de REUSO
        # (natural-key match), não criou tarefas novas por engano — senão a
        # afirmação abaixo não estaria testando a reativação de nada.
        assert criadas == 0, (
            f'materializar_cronograma criou {criadas} tarefa(s) nova(s) — '
            'o cenário não exercitou o caminho de reuso/reativação')

        for id_, rotulo in ((raiz_id, 'a raiz'), (filha_id, 'a filha')):
            tarefa_db = db.session.get(TarefaCronograma, id_)
            db.session.refresh(tarefa_db)
            assert tarefa_db.ativa is True, (
                f'{rotulo} não voltou — delegar ao restaurador só com o '
                '`pi_id` da revisão atual não bate na seed query, que casa '
                'pelo `gerada_por_proposta_item_id` que a tarefa carrega')
            assert tarefa_db.arquivada_em is None, (
                f'{rotulo} voltou viva com lápide: ativa=True e '
                f'arquivada_em={tarefa_db.arquivada_em}')
