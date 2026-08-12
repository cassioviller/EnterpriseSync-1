"""Recebimento e atesto de pedido de compra — Fase 4.

O caminho ÚNICO de escrita do recebimento, no molde do chokepoint que a Fase 3
usa em services/requisicao_compra.py. Quem grava recebimento passa por aqui;
quem gravar por fora vai divergir do `situacao_recebimento` persistido, e o
scripts/verificar_consistencia_recebimento.py denuncia.

Spec: docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md
"""
import logging
from decimal import Decimal

logger = logging.getLogger('recebimento_pedido')

# As quatro situações de `PedidoCompra.situacao_recebimento`.
# O que cabe em `recebimento_pedido_item.quantidade_recebida`, que é
# `Numeric(12,3)`. Passar disso é DataError no flush, não regra de negócio —
# e quem recebe caminhão merece a mensagem, não a página de erro.
QUANTIDADE_MAXIMA = Decimal('999999999.999')

NAO_RECEBIDO = 'nao_recebido'
PARCIAL = 'parcial'
RECEBIDO = 'recebido'
ENCERRADO_COM_SALDO = 'encerrado_com_saldo'


class RecebimentoInvalido(Exception):
    """Violação de regra de recebimento — dado errado, não bug.

    A mensagem é exibida ao usuário verbatim (a rota da R6 e o relatório de
    pendências da carga usam o texto como está). Escreva para humano: o que
    está errado e o que fazer.
    """


def regime_do_tenant(admin_id):
    """O pedido que nascer AGORA neste tenant exige atesto?

    Uma função só, chamada pelos dois pontos que criam `PedidoCompra` em
    compras_views.py — o POST avulso e a emissão a partir de requisição. Ter
    dois lugares lendo a flag por conta própria é como dois lugares divergirem
    na regra; ter um só é como isso não acontecer.

    O valor devolvido é CARIMBADO em `pedido_compra.exige_atesto` e nunca mais
    reconsultado para aquele pedido: desligar a flag depois não muda o regime
    do que já nasceu. Ver o spec, seção "Regime de virada".
    """
    from scripts.flag_recebimento_atesto import recebimento_atesto_ativo
    return bool(recebimento_atesto_ativo(admin_id))


def _d(valor):
    return Decimal(str(valor or 0))


def recebido_por_item(pedido):
    """{pedido_item_id: quantidade acumulada} somando TODOS os recebimentos.

    A soma é o que decide a situação do pedido — por isso ela vive numa função
    só, e não espalhada entre quem grava e quem confere.
    """
    from models import RecebimentoPedido, RecebimentoPedidoItem, db

    linhas = (db.session.query(RecebimentoPedidoItem)
              .join(RecebimentoPedido,
                    RecebimentoPedido.id == RecebimentoPedidoItem.recebimento_id)
              .filter(RecebimentoPedido.pedido_id == pedido.id)
              .all())
    acumulado = {}
    for linha in linhas:
        acumulado[linha.pedido_item_id] = (
            acumulado.get(linha.pedido_item_id, Decimal('0'))
            + _d(linha.quantidade_recebida))
    return acumulado


def _encerramento(pedido):
    """O recebimento que encerrou o saldo deste pedido, ou None."""
    from models import RecebimentoPedido
    return (RecebimentoPedido.query
            .filter_by(pedido_id=pedido.id, encerra_saldo=True)
            .order_by(RecebimentoPedido.sequencia)
            .first())


def situacao_para(pedido):
    """A situação de recebimento DERIVADA — função pura de leitura.

    Separada de quem grava de propósito: é esta que o
    scripts/verificar_consistencia_recebimento.py (R7) compara com o valor
    persistido para achar drift. Se a regra vivesse dentro de
    `registrar_recebimento`, o sensor teria de reimplementá-la — e um sensor
    que reimplementa o que vigia não vigia nada.

    A ordem das perguntas é a regra:
      1. nada recebido            → nao_recebido
      2. todo item completo       → recebido   (mesmo com encerra_saldo:
                                                não há saldo a encerrar)
      3. alguém encerrou o saldo  → encerrado_com_saldo
      4. resto                    → parcial
    """
    from models import PedidoCompraItem

    acumulado = recebido_por_item(pedido)
    if not acumulado or all(q <= 0 for q in acumulado.values()):
        return NAO_RECEBIDO

    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()
    completo = all(
        acumulado.get(item.id, Decimal('0')) >= _d(item.quantidade)
        for item in itens)
    if completo:
        return RECEBIDO
    if _encerramento(pedido) is not None:
        return ENCERRADO_COM_SALDO
    return PARCIAL


def valor_atestado(pedido):
    """Σ (quantidade recebida × preço unitário) — o que CHEGOU vale quanto?

    O gancho da fase financeira: é este número que o Fluxo A vai usar para
    pagar o que chegou em vez do que foi pedido. Fica exposto já nesta fase
    porque é barato agora e caro descobrir depois que não dá para calcular.

    Inclui item de texto livre — frete não movimenta estoque, mas foi
    entregue e é para pagar — e ignora o saldo não entregue, que é
    exatamente o que a fase financeira vai evitar pagar.
    """
    from models import PedidoCompraItem

    acumulado = recebido_por_item(pedido)
    if not acumulado:
        return Decimal('0')

    itens = {i.id: i for i in
             PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()}
    total = Decimal('0')
    for item_id, quantidade in acumulado.items():
        item = itens.get(item_id)
        if item is None:
            continue
        total += _d(quantidade) * _d(item.preco_unitario)
    return total


def _validar_linhas(pedido, linhas, acumulado, permitir_sobre_entrega):
    """Quantidades: positivas, de itens DESTE pedido, e sem estourar o pedido."""
    from models import PedidoCompraItem

    if not linhas:
        raise RecebimentoInvalido(
            'informe ao menos um item recebido — recebimento vazio não é '
            'atesto de nada.')

    itens = {i.id: i for i in
             PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()}
    vistos = set()
    for item_id, quantidade in linhas:
        if item_id in vistos:
            raise RecebimentoInvalido(
                f'o item {item_id} aparece duas vezes neste recebimento — '
                f'some as quantidades numa linha só.')
        vistos.add(item_id)

        item = itens.get(item_id)
        if item is None:
            raise RecebimentoInvalido(
                f'o item {item_id} não é deste pedido.')

        qtd = _d(quantidade)
        if not qtd.is_finite():
            # `Decimal('nan')` não levanta no construtor e sobrevive ao filtro
            # do zero da rota; comparar NaN com zero, três linhas abaixo,
            # levanta `InvalidOperation` — que vira 500 com a sessão sem
            # rollback em vez de mensagem de regra. O serviço é o chokepoint:
            # não pode depender de a rota ter limpado o dado.
            raise RecebimentoInvalido(
                f'"{item.descricao}": {quantidade} não é uma quantidade.')

        if qtd <= 0:
            raise RecebimentoInvalido(
                f'"{item.descricao}": a quantidade recebida tem de ser maior '
                f'que zero. Devolução não é recebimento negativo.')

        if qtd > QUANTIDADE_MAXIMA:
            # O teto da coluna `Numeric(12,3)` é uma regra como as outras, e
            # quem a conhece é este serviço. Sem isto, `1e999` com a
            # sobre-entrega marcada passa por todas as validações e vira
            # DataError no flush — 500 em vez de mensagem.
            raise RecebimentoInvalido(
                f'"{item.descricao}": {qtd} não cabe como quantidade '
                f'recebida — o máximo é {QUANTIDADE_MAXIMA}.')

        if not permitir_sobre_entrega:
            total = acumulado.get(item_id, Decimal('0')) + qtd
            pedido_qtd = _d(item.quantidade)
            if total > pedido_qtd:
                ja = acumulado.get(item_id, Decimal('0'))
                raise RecebimentoInvalido(
                    f'"{item.descricao}": recebendo {qtd} chega a {total}, '
                    f'acima dos {pedido_qtd} do pedido'
                    + (f' ({ja} já recebidos)' if ja else '')
                    + '. Se veio mais mesmo, marque a sobre-entrega e '
                      'justifique.')


def descricao_da_saida(pedido, lote_ref):
    """O texto da SAÍDA pareada, ou None quando não há saída a gerar.

    Espelha, palavra por palavra, as duas chamadas de
    `compras_views._gerar_saida_almoxarifado`:

    | Pedido               | Emissão (regime antigo)   | Atesto (regime novo) |
    |----------------------|---------------------------|----------------------|
    | normal COM obra      | "Consumo direto na obra"  | idem                 |
    | normal SEM obra      | só entrada (fica em estoque) | idem              |
    | `aprovacao_cliente`  | "Consumo faturamento direto" | idem              |

    Está aqui, e não embutido no lançamento, porque é a REGRA — e a regra
    tinha de ser lida junto da tabela para se conferir que espelha mesmo.
    """
    if pedido.tipo_compra == 'aprovacao_cliente':
        return f'Consumo faturamento direto — compra {lote_ref}'
    if pedido.obra_id:
        return f'Consumo direto na obra — compra {lote_ref}'
    return None


def _lancar_no_estoque(pedido, recebimento, linha, item, usuario_id):
    """ENTRADA + lote FIFO da quantidade que ESTA linha atestou, e a SAÍDA pareada.

    O espelho de `compras_views._gerar_entrada_almoxarifado` + `_gerar_saida_
    almoxarifado`, com a diferença que é a razão desta fase existir: a
    quantidade é a RECEBIDA, não a pedida, e o momento é o da chegada, não o
    da emissão. ⚠️ Os dois lados são a MESMA regra em dois lugares: mexer em
    um pede conferir o outro, e o teste de paridade
    (`test_paridade_de_movimentos_entre_os_dois_regimes`) é quem cobra isso.

    A saída existe porque material comprado para obra é reconhecido como
    consumido no ato — era assim na emissão e continua sendo. Sem ela o lote
    fica DISPONIVEL para sempre e o mesmo material pode sair uma segunda vez
    pela tela do almoxarifado (achado 1 da revisão de 12/08).

    `data_movimento` recebe a data do RECEBIMENTO, não a do registro: o
    caminhão que chega no sábado e é lançado na segunda pertence ao sábado, e
    é para isso que `RecebimentoPedido.data_recebimento` existe.

    Item de texto livre não chega aqui — sem `almoxarifado_item_id` não há o
    que movimentar, e a linha do recebimento fica com os dois ids NULL de
    propósito.

    `pedido_compra_id` é preenchido porque o handler `material_entrada` do
    EventManager dedup por ele: sem isso o custo do material entra duas vezes.
    """
    from datetime import datetime, time

    from models import AlmoxarifadoEstoque, AlmoxarifadoMovimento, db

    lote_ref = f'{pedido.numero or f"PC-{pedido.id}"}/{recebimento.sequencia}'
    quantidade = _d(linha.quantidade_recebida)
    quando = recebimento.data_recebimento
    if not isinstance(quando, datetime):
        quando = datetime.combine(quando, time.min)

    mov = AlmoxarifadoMovimento(
        item_id=item.almoxarifado_item_id,
        tipo_movimento='ENTRADA',
        quantidade=quantidade,
        valor_unitario=item.preco_unitario,
        data_movimento=quando,
        nota_fiscal=pedido.numero,
        observacao=f'Recebimento {recebimento.rotulo}: {item.descricao[:100]}',
        estoque_id=None,
        fornecedor_id=pedido.fornecedor_id,
        admin_id=pedido.admin_id,
        usuario_id=usuario_id,
        obra_id=pedido.obra_id,
        pedido_compra_id=pedido.id,
    )
    db.session.add(mov)
    db.session.flush()

    estoque = AlmoxarifadoEstoque(
        item_id=item.almoxarifado_item_id,
        quantidade=quantidade,
        quantidade_inicial=quantidade,
        quantidade_disponivel=quantidade,
        entrada_movimento_id=mov.id,
        valor_unitario=item.preco_unitario,
        status='DISPONIVEL',
        # O lote carrega a sequência do recebimento: duas entregas do mesmo
        # pedido são dois lotes distinguíveis na prateleira e no estorno.
        lote=lote_ref[:50],
        obra_id=pedido.obra_id,
        admin_id=pedido.admin_id,
    )
    db.session.add(estoque)
    db.session.flush()
    mov.estoque_id = estoque.id

    linha.almoxarifado_movimento_id = mov.id

    descricao = descricao_da_saida(pedido, lote_ref)
    if descricao is None:
        return mov

    estoque.quantidade_disponivel = 0
    estoque.status = 'CONSUMIDO'
    saida = AlmoxarifadoMovimento(
        item_id=item.almoxarifado_item_id,
        tipo_movimento='SAIDA',
        quantidade=quantidade,
        valor_unitario=item.preco_unitario,
        data_movimento=quando,
        funcionario_id=None,
        obra_id=pedido.obra_id,
        observacao=descricao,
        estoque_id=estoque.id,
        lote=estoque.lote,
        admin_id=pedido.admin_id,
        usuario_id=usuario_id,
        pedido_compra_id=pedido.id,
    )
    db.session.add(saida)
    db.session.flush()
    linha.almoxarifado_saida_movimento_id = saida.id
    return mov


def registrar_recebimento(pedido, usuario, linhas, data, observacao=None,
                          encerra_saldo=False, motivo=None,
                          permitir_sobre_entrega=False):
    """Grava UM recebimento do pedido. Uma transação, um commit.

    `linhas`: iterável de `(pedido_item_id, quantidade)`. Só os itens que
    chegaram — item ausente é item que não veio nesta entrega, não item com
    quantidade zero.

    Devolve o `RecebimentoPedido` criado. Levanta `RecebimentoInvalido` com
    mensagem para humano quando alguma regra não bate; nada é gravado nesse
    caso.

    É AQUI que o estoque entra, para pedido do regime novo: cada linha de
    item de catálogo gera ENTRADA + lote FIFO com a quantidade recebida. A
    emissão do pedido, que fazia isso antes, não faz mais
    (compras_views._gerar_entrada_almoxarifado).
    """
    from models import (PedidoCompraItem, RecebimentoPedido,
                        RecebimentoPedidoItem, db)
    from utils.autorizacao import usuario_pode_receber_na_obra

    linhas = list(linhas or [])

    if not usuario_pode_receber_na_obra(usuario, pedido.obra_id):
        raise RecebimentoInvalido(
            'você não tem permissão para atestar recebimento nesta obra.')

    if encerra_saldo and not (motivo or '').strip():
        raise RecebimentoInvalido(
            'para encerrar o saldo é preciso dizer por quê — é o motivo que '
            'explica, seis meses depois, por que o pedido fechou incompleto.')

    # Trava a linha do pedido ANTES de somar: sem isso duas telas abertas
    # somam contra o mesmo acumulado e furam juntas o limite de quantidade.
    db.session.query(type(pedido)).filter_by(id=pedido.id).with_for_update().first()

    ja_encerrado = _encerramento(pedido)
    if ja_encerrado is not None:
        quem = getattr(ja_encerrado.recebido_por, 'nome', None) or 'alguém'
        quando = ja_encerrado.data_recebimento.strftime('%d/%m/%Y')
        raise RecebimentoInvalido(
            f'o saldo deste pedido foi encerrado por {quem} em {quando} '
            f'("{(ja_encerrado.motivo_encerramento or "").strip()}"). Para '
            f'receber mais, reabra o pedido ou emita um pedido novo.')

    acumulado = recebido_por_item(pedido)
    _validar_linhas(pedido, linhas, acumulado, permitir_sobre_entrega)

    ultima = (RecebimentoPedido.query
              .filter_by(pedido_id=pedido.id)
              .order_by(RecebimentoPedido.sequencia.desc())
              .first())
    sequencia = (ultima.sequencia + 1) if ultima else 1

    recebimento = RecebimentoPedido(
        pedido_id=pedido.id,
        admin_id=pedido.admin_id,
        sequencia=sequencia,
        recebido_por_id=usuario.id,
        data_recebimento=data,
        observacao=observacao,
        encerra_saldo=bool(encerra_saldo),
        motivo_encerramento=(motivo or None) if encerra_saldo else None,
    )
    db.session.add(recebimento)
    db.session.flush()

    itens = {i.id: i for i in
             PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()}
    gravadas = []
    for item_id, quantidade in linhas:
        registro = RecebimentoPedidoItem(
            recebimento_id=recebimento.id,
            admin_id=pedido.admin_id,
            pedido_item_id=item_id,
            quantidade_recebida=_d(quantidade),
        )
        db.session.add(registro)
        gravadas.append((registro, itens[item_id]))
    db.session.flush()

    # O estoque nasce daqui — e SÓ no regime novo. Para pedido legado
    # (`exige_atesto=False`) a entrada já aconteceu na emissão; lançar de novo
    # aqui seria a dupla escrita que esta fase existe para consertar, com o
    # sinal trocado. A recusa explícita desses pedidos na tela é da R6.
    movimentos = 0
    if pedido.exige_atesto:
        for registro, item in gravadas:
            if item.almoxarifado_item_id:
                _lancar_no_estoque(pedido, recebimento, registro, item,
                                   usuario.id)
                movimentos += 1
        db.session.flush()

    pedido.situacao_recebimento = situacao_para(pedido)
    db.session.commit()

    logger.info('recebimento %s: %s itens (%s no estoque) por usuario=%s — '
                'pedido agora %s', recebimento.rotulo, len(linhas), movimentos,
                usuario.id, pedido.situacao_recebimento)
    return recebimento


def _lote_do_movimento(movimento_id):
    from models import AlmoxarifadoEstoque
    return AlmoxarifadoEstoque.query.filter_by(
        entrada_movimento_id=movimento_id).first()


def _ja_teve_saida(lote, tem_saida_propria=False):
    """O material deste lote já saiu da prateleira — por MÃO DE TERCEIRO?

    A regra normal é o disponível ter caído abaixo do que entrou. É o que TODO
    caminho de saída faz (views/almoxarifado/movimentos.py e o consumo direto
    de compras_views._gerar_saida_almoxarifado, que zera o disponível e marca
    CONSUMIDO): baixar `quantidade_disponivel` é o efeito comum a todos, e
    status é consequência dele — no zero vira CONSUMIDO.

    `tem_saida_propria` muda a pergunta, e é a razão de este parâmetro
    existir (C2): desde que o atesto passou a gerar a SAÍDA pareada, o lote de
    pedido com obra nasce CONSUMIDO no mesmo instante em que nasce. Comparar
    disponível com inicial acusaria a nós mesmos, e nenhuma exclusão de
    recebimento passaria mais.

    O que denuncia terceiro, nesse caso, é o TAMANHO do lote ter mudado:
    `views/almoxarifado/movimentos.py:637` faz `lote.quantidade =
    lote.quantidade_disponivel` ao consumir, enquanto a saída pareada mexe só
    no disponível. E a rigor terceiro nenhum consegue consumir um lote com
    disponível zero — a checagem da tela de saída barra antes. Isto aqui é o
    cinto além do suspensório.
    """
    inicial = _d(lote.quantidade_inicial if lote.quantidade_inicial is not None
                 else lote.quantidade)
    if tem_saida_propria:
        return _d(lote.quantidade) < inicial
    return _d(lote.quantidade_disponivel) < inicial


def excluir_recebimento(recebimento, usuario):
    """Apaga o ÚLTIMO recebimento do pedido, estornando o estoque que gerou.

    Errar a quantidade digitada é o erro mais comum de quem recebe caminhão no
    portão, e o conserto não pode ser um segundo recebimento com número
    negativo — quantidade negativa é justamente o que `registrar_recebimento`
    recusa.

    Duas condições, e as duas existem por uma razão física:

    * **só o último.** A `sequencia` é 1, 2, 3 e não tem buraco: furar o meio
      quebraria o rótulo que a tela mostra (`PC-1234/2` passaria a apontar
      para outro fato).
    * **só enquanto o material estiver na prateleira.** Estornar a entrada de
      um lote já consumido deixaria estoque negativo e uma saída apontando
      para um lote que deixou de existir.

    O estorno usa `RecebimentoPedidoItem.almoxarifado_movimento_id` — é para
    isso que a coluna existe. Levanta `RecebimentoInvalido` com mensagem para
    humano; nada é apagado nesse caso.
    """
    from models import AlmoxarifadoMovimento, RecebimentoPedido, db
    from utils.autorizacao import usuario_pode_receber_na_obra

    pedido = recebimento.pedido

    if not usuario_pode_receber_na_obra(usuario, pedido.obra_id):
        raise RecebimentoInvalido(
            'você não tem permissão para excluir recebimento nesta obra.')

    db.session.query(type(pedido)).filter_by(id=pedido.id).with_for_update().first()

    ultimo = (RecebimentoPedido.query
              .filter_by(pedido_id=pedido.id)
              .order_by(RecebimentoPedido.sequencia.desc())
              .first())
    if ultimo is None or ultimo.id != recebimento.id:
        raise RecebimentoInvalido(
            f'só o último recebimento do pedido pode ser excluído, e o último '
            f'é o {ultimo.rotulo}. Exclua ele primeiro.')

    # Valida TUDO antes de apagar QUALQUER coisa: recusa que já estornou
    # metade dos movimentos deixa o estoque pior do que encontrou.
    linhas = list(recebimento.itens)
    a_estornar = []
    for linha in linhas:
        if not linha.almoxarifado_movimento_id:
            continue
        mov = db.session.get(AlmoxarifadoMovimento,
                             linha.almoxarifado_movimento_id)
        if mov is None:
            continue
        lote = _lote_do_movimento(mov.id)
        # A saída pareada que ESTE recebimento gerou (C2) é desfeita junto: é
        # nossa, e desfazer a entrada sem ela deixaria uma saída apontando
        # para um lote que deixou de existir.
        saida = (db.session.get(AlmoxarifadoMovimento,
                                linha.almoxarifado_saida_movimento_id)
                 if linha.almoxarifado_saida_movimento_id else None)
        if lote is not None and _ja_teve_saida(lote,
                                               tem_saida_propria=saida is not None):
            nome = getattr(mov.item, 'nome', None) or linha.pedido_item.descricao
            raise RecebimentoInvalido(
                f'"{nome}" deste recebimento já teve saída do almoxarifado — '
                f'o material foi consumido e a entrada não pode ser desfeita. '
                f'Registre a devolução ao fornecedor em vez de excluir.')
        a_estornar.append((linha, mov, lote, saida))

    rotulo = recebimento.rotulo
    for linha, mov, lote, saida in a_estornar:
        # A ordem importa: `estoque_id` nos movimentos e `entrada_movimento_id`
        # no lote apontam um para o outro. Soltar os vínculos antes de apagar
        # evita que o banco recuse por FK.
        linha.almoxarifado_movimento_id = None
        linha.almoxarifado_saida_movimento_id = None
        mov.estoque_id = None
        if saida is not None:
            saida.estoque_id = None
        db.session.flush()
        if saida is not None:
            db.session.delete(saida)
        if lote is not None:
            db.session.delete(lote)
        db.session.delete(mov)
    db.session.flush()

    db.session.delete(recebimento)  # as linhas vão junto (delete-orphan)
    db.session.flush()

    pedido.situacao_recebimento = situacao_para(pedido)
    db.session.commit()

    logger.info('recebimento %s excluido por usuario=%s (%s movimentos '
                'estornados) — pedido agora %s', rotulo, usuario.id,
                len(a_estornar), pedido.situacao_recebimento)
    return pedido.situacao_recebimento
