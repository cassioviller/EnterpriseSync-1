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
            fornecedor_id=forn.id, data_compra=date.today(),
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
        fornecedor_id=forn.id, data_compra=date.today(),
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


def test_versao_de_contrato_e_unica_por_tenant_nao_por_obra():
    """🔴 `models.py:7616` — `UNIQUE(obra_id, versao)` sem `admin_id`.

    A migration 315 escopou a irmã (`uq_contrato_versao_vigente`) por tenant
    e deixou esta como estava. Com uma linha de admin_id divergente — o
    cenário que a própria docstring da 315 cita — o tenant correto numera a
    partir do SEU máximo e colide com a linha alheia.

    🔬 Andaime corrigido, em duas frentes (o brief nunca chegava a exercitar
    a constraint sob teste sem elas):

    1. A coluna é `valor` (`models.py:7624`, Numeric), não `valor_contrato`
       como o brief escrevia — e `vigente_de`/`origem_tipo` são NOT NULL
       (`models.py:7626,7628`), como o próprio `abrir_versao` grava
       (`services/contrato_obra.py:220-228`). Sem os três, o construtor
       levantaria `TypeError`/violaria NOT NULL antes de qualquer INSERT.
    2. `admin_id` tem FK real para `usuario.id`
       (`obra_contrato_versao_admin_id_fkey`, conferido pelo erro do RED).
       `t.admin_id + 999999` — o "tenant divergente" do brief — não é
       usuário nenhum, e o INSERT da linha órfã falhava com
       `ForeignKeyViolation` antes de chegar perto de
       `uq_contrato_versao_obra_versao`. Por isso o admin_id divergente
       aqui é o de um SEGUNDO tenant real (`dois_tenants`), exatamente o
       cenário que a migration 266/315 descrevem: uma linha de
       `obra_contrato_versao` cujo `admin_id` não é o dono da obra.
    """
    from models import ObraContratoVersao
    from helpers_tenant import dois_tenants

    with app.app_context():
        a, b = dois_tenants('contrato-uq', com_fatos=False)

        # A linha "órfã": obra do tenant A, admin_id do tenant B, versão
        # alta, já fechada (histórica) — não precisa estar vigente para
        # colidir com a numeração do tenant A, só precisa existir no par
        # (obra_id, versao) que a constraint velha enxerga.
        orfa = ObraContratoVersao(
            obra_id=a.obra_id, admin_id=b.admin_id,
            versao=3, valor=1000, origem_tipo='cadastro_manual',
            vigente_de=date(2025, 1, 1), vigente_ate=date(2026, 1, 1))
        db.session.add(orfa)
        db.session.commit()

        from models import Obra
        from services.contrato_obra import ORIGEM_CADASTRO, abrir_versao

        obra_ref = db.session.get(Obra, a.obra_id)
        # 🔬 Assinatura conferida (`services/contrato_obra.py:114`):
        # `abrir_versao(obra, valor, origem_tipo, *, origem_proposta_id=None,
        # aditivo_id=None, motivo=None, criado_por_id=None, vigente_de=None,
        # prazo_dias=None)`. `valor` e `origem_tipo` são POSICIONAIS e
        # obrigatórios.
        #
        # O tenant A numera a partir do SEU máximo (0) — 1, 2, 3 — e é na
        # terceira que ele encontra a órfã de versao=3.
        for _ in range(3):
            abrir_versao(obra_ref, 500, ORIGEM_CADASTRO)
            db.session.commit()

        vivas = ObraContratoVersao.query.filter_by(
            obra_id=a.obra_id, admin_id=a.admin_id).count()
        assert vivas == 3, (
            'a numeração do tenant colidiu com a versão de outro tenant na '
            'mesma obra — uq_contrato_versao_obra_versao não tem admin_id')


def test_linha_intocada_nao_vira_alterado_por_arredondamento():
    """🔴 `services/proposta_diff.py:92` — `dv = _dec(it.subtotal_calculado) -
    _dec(anterior.subtotal_calculado)`, sem normalizar para centavos.

    `PropostaItem.subtotal_calculado` (`models.py:4029`) devolve o snapshot
    persistido (`subtotal`, `Numeric(15,2)`) quando existe, e o fallback
    `quantidade × preco_unitario` (`Numeric(10,3) × Numeric(10,2)`, até 5
    casas) quando não. Uma linha intocada cujo lado sem snapshot cai no
    fallback dá diferença de arredondamento — não zero — e sai como
    'alterado'.

    🔬 Andaime corrigido: o brief original criava o item "sem snapshot" só
    deixando `subtotal=None` no construtor. Isso não sobrevive — há um
    listener `before_insert`/`before_update` em `PropostaItem`
    (`models.py:8380-8383`, `_calc_proposta_item_snapshot`) que preenche
    `subtotal = quantidade * preco_unitario` sempre que está `None`, e a
    coluna é `Numeric(15,2)`: o Postgres arredonda o valor ao gravar, então
    depois do `commit()` (que expira os objetos) os DOIS lados voltam com
    `subtotal` já arredondado a 2 casas e IGUAIS — o teste passaria verde
    mesmo com o código velho, sem nunca alcançar o caminho do fallback.
    Confirmado batendo o cenário num REPL antes de escrever a asserção:
    sem o passo abaixo, `subtotal_calculado` dos dois lados vinha `14.06`
    nos dois, e não `14.06`/`14.05560`.

    Por isso o `subtotal` do item ATUAL é zerado por SQL cru DEPOIS do
    commit — simula o caso real que o comentário de `proposta_diff.py`
    descreve (item cujo snapshot nunca foi escrito por essa listener: dado
    migrado antes dela existir, ou uma correção por SQL direto) sem passar
    pelo ORM, que reagiria e preencheria de novo.

    Os dois itens compartilham `item_numero=1` e não têm
    `proposta_item_origem_id` — o fallback de linhagem para revisões antigas
    (`handlers/propostas_handlers.py:42-45`) é o que os pareia.
    """
    from decimal import Decimal

    from sqlalchemy import text

    from models import Proposta, PropostaItem
    # 🔬 Nome conferido (`services/proposta_diff.py:48`):
    # `diff_versoes(origem, destino) -> list[dict]`. Não existe
    # `diff_de_propostas`.
    from services.proposta_diff import diff_versoes

    with app.app_context():
        t = um_tenant('diff-arred', com_fatos=False)

        def _proposta():
            # 🔬 Campos NOT NULL conferidos (`models.py:3710-3719`):
            # `numero`, `cliente_nome`. `data_proposta` tem default.
            p = Proposta(admin_id=t.admin_id, numero=f'P-{uuid.uuid4().hex[:8]}',
                        cliente_nome='Cliente Teste')
            db.session.add(p)
            db.session.flush()
            # 🔬 Campos NOT NULL conferidos (`models.py:3960-3966`):
            # `admin_id`, `item_numero`, `descricao`, `quantidade`,
            # `unidade`, `preco_unitario`.
            item = PropostaItem(
                proposta_id=p.id, admin_id=t.admin_id, item_numero=1,
                descricao='Item', unidade='m2',
                quantidade=Decimal('4.505'), preco_unitario=Decimal('3.12'))
            db.session.add(item)
            db.session.flush()
            return p, item

        anterior, item_anterior = _proposta()
        atual, item_atual = _proposta()
        db.session.commit()

        # Zera o snapshot do item ATUAL por fora do ORM — ver docstring.
        db.session.execute(
            text('UPDATE proposta_itens SET subtotal = NULL WHERE id = :id'),
            {'id': item_atual.id})
        db.session.commit()
        db.session.expire_all()

        linhas = diff_versoes(anterior, atual)
        situacoes = {l['situacao'] for l in linhas}
        assert situacoes == {'mantido'}, (
            f'linha intocada saiu como {situacoes} — a diferença é só o '
            f'arredondamento do snapshot')


def test_total_do_diff_nao_mistura_2_e_5_casas_em_incluido():
    """🟠 Fix round 1 — Important 1: `total_do_diff` somava
    `_dec(item.subtotal_calculado)` SEM arredondar nos ramos
    incluido/suprimido, enquanto os deltas de mantido/alterado já vinham em
    centavos — misturando termos de 2 e de até 5 casas na mesma soma.

    Um item incluído sem snapshot (`subtotal` NULL, mesmo cenário legado do
    teste de arredondamento acima) cai no fallback `quantidade ×
    preco_unitario`, até 5 casas. O total tem que sair em centavos mesmo
    assim — arredondado uma vez só, no fim, não por parcela.
    """
    from decimal import Decimal

    from sqlalchemy import text

    from models import Proposta, PropostaItem
    from services.proposta_diff import diff_versoes, total_do_diff

    with app.app_context():
        t = um_tenant('diff-total-incl', com_fatos=False)

        def _proposta():
            p = Proposta(admin_id=t.admin_id, numero=f'P-{uuid.uuid4().hex[:8]}',
                        cliente_nome='Cliente Teste')
            db.session.add(p)
            db.session.flush()
            return p

        anterior = _proposta()  # sem itens
        atual = _proposta()
        item = PropostaItem(
            proposta_id=atual.id, admin_id=t.admin_id, item_numero=1,
            descricao='Item novo', unidade='m2',
            quantidade=Decimal('4.505'), preco_unitario=Decimal('3.12'))
        db.session.add(item)
        db.session.flush()
        item_id = item.id
        db.session.commit()

        # Zera o snapshot por fora do ORM, simulando o item legado sem
        # `subtotal` — ver docstring do teste de arredondamento acima.
        db.session.execute(
            text('UPDATE proposta_itens SET subtotal = NULL WHERE id = :id'),
            {'id': item_id})
        db.session.commit()
        db.session.expire_all()

        linhas = diff_versoes(anterior, atual)
        assert {l['situacao'] for l in linhas} == {'incluido'}, (
            'andaime: o item devia sair como incluído, sem parear com nada '
            'na origem (que não tem itens)')

        total = total_do_diff(linhas)
        # 4.505 * 3.12 = 14.05560 (bruto, do fallback) — o total tem de sair
        # 14.06, não 14.05560 nem qualquer coisa com mais de 2 casas.
        assert total == Decimal('14.06'), (
            f'total saiu {total} — misturou o fallback de 5 casas '
            '(quantidade × preço) com a precisão de centavos')


def test_total_do_diff_soma_deltas_antes_de_arredondar():
    """🟠 Fix round 1 — Important 2: arredondar CADA linha antes de somar
    esconde efeito sistêmico. Cenário do revisor: um reajuste distribuído
    por muitos itens, cada delta individual abaixo de meio centavo — cada
    linha classifica 'mantido' (correto: a task 5 existe para isso), mas a
    SOMA dos deltas brutos é material e o total tem que mostrá-la.

    Reusa o mesmo par (snapshot 2 casas vs. fallback 5 casas, `4.505 ×
    3.12`) do teste de arredondamento, repetido em N itens: cada linha tem
    delta bruto de `14.05560 - 14.06 = -0.00440` — abaixo de meio centavo,
    então cada uma isolada arredonda para 0,00 e classifica 'mantido'. Com
    N=20, a soma bruta é `-0.08800`, que arredonda para -0,09: material, e
    seria invisível se cada linha tivesse arredondado antes de somar.
    """
    from decimal import Decimal

    from sqlalchemy import text

    from models import Proposta, PropostaItem
    from services.proposta_diff import diff_versoes, total_do_diff

    with app.app_context():
        t = um_tenant('diff-total-sist', com_fatos=False)

        def _proposta():
            p = Proposta(admin_id=t.admin_id, numero=f'P-{uuid.uuid4().hex[:8]}',
                        cliente_nome='Cliente Teste')
            db.session.add(p)
            db.session.flush()
            return p

        anterior = _proposta()
        atual = _proposta()

        N = 20
        itens_atual_ids = []
        for n in range(1, N + 1):
            db.session.add(PropostaItem(
                proposta_id=anterior.id, admin_id=t.admin_id, item_numero=n,
                descricao=f'Item {n}', unidade='m2',
                quantidade=Decimal('4.505'), preco_unitario=Decimal('3.12')))
            item_atual = PropostaItem(
                proposta_id=atual.id, admin_id=t.admin_id, item_numero=n,
                descricao=f'Item {n}', unidade='m2',
                quantidade=Decimal('4.505'), preco_unitario=Decimal('3.12'))
            db.session.add(item_atual)
            db.session.flush()
            itens_atual_ids.append(item_atual.id)
        db.session.commit()

        # Zera o snapshot de cada item ATUAL por fora do ORM — os N itens
        # ficam sem `subtotal`, e cada um cai no fallback de 5 casas.
        for iid in itens_atual_ids:
            db.session.execute(
                text('UPDATE proposta_itens SET subtotal = NULL WHERE id = :id'),
                {'id': iid})
        db.session.commit()
        db.session.expire_all()

        linhas = diff_versoes(anterior, atual)
        situacoes = {l['situacao'] for l in linhas}
        assert situacoes == {'mantido'}, (
            f'cada linha tem diferença sub-centavo — continuam "mantido", '
            f'não {situacoes}')

        total = total_do_diff(linhas)
        assert total == Decimal('-0.09'), (
            f'total saiu {total} — o efeito sistêmico de {N} deltas '
            'sub-centavo sumiu porque cada linha foi arredondada antes de '
            'somar')
