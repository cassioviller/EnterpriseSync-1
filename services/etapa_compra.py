"""A régua de status unificado do pedido de compra — Fase 4 do ciclo.

Spec: docs/superpowers/specs/2026-08-19-status-unificado-design.md

Por que DERIVADA e não gravada (D1a): gravar a etapa criaria um SÉTIMO portador
de estado ao lado dos seis que já existem — e divergir dos outros seis é
exatamente a doença que esta fase existe para curar. Esta função LÊ; não escreve
nada, não commita nada, e por isso pode ser chamada de dentro de um template.

Por que LISTA DE CONFERÊNCIA e não barra de progresso (D3.1): no Fluxo B
(adiantamento) paga-se ANTES de receber — 📖 models.py:5845. Numa barra linear
isso acende a casa 8 antes da 4 e lê como defeito. Aqui cada casa acende pela
própria condição e o "onde está" é derivado: a primeira casa aplicável ainda não
satisfeita. É o desenho que SAP (indicadores independentes ELIKZ/EREKZ) e Odoo
(state + receipt_status/invoice_status derivados) usam; a NetSuite, que força um
enum linear, acabou com o status "Pending Billing/Partially Received" — o produto
cartesiano vazando para dentro do enum.
"""
from collections import namedtuple

Casa = namedtuple('Casa', 'chave rotulo grupo acesa aplicavel selos')

CHAVES = ('requisitada', 'aprovada', 'pedido_emitido', 'material_recebido',
          'nota_lancada', 'liberada', 'em_lote', 'paga', 'encerrada')

ROTULOS = {
    'requisitada': 'Requisitada',
    'aprovada': 'Aprovada',
    'pedido_emitido': 'Pedido emitido',
    'material_recebido': 'Material recebido',
    'nota_lancada': 'Nota lançada',
    'liberada': 'Liberada para pagamento',
    'em_lote': 'Em lote de pagamento',
    'paga': 'Paga',
    'encerrada': 'Encerrada',
}

# As casas 3, 4 e 5 são o three-way match (pedido ↔ recebimento ↔ nota) — o
# mesmo trio que SAP, Odoo e NetSuite conferem. Marcá-las como grupo é o que dá
# sentido a elas para além da ordem.
GRUPO_TRIADE = ('pedido_emitido', 'material_recebido', 'nota_lancada')


def etapa_do_pedido(pedido, dados=None):
    """Onde este pedido está. Não escreve nada.

    Devolve {'casas': [Casa...], 'ponteiro': chave|None, 'encerrada_por': None}.
    `ponteiro` é None quando não falta nada aplicável, e também quando a casa 9
    (`encerrada`) já acendeu — casa terminal, e casa que ficou apagada no
    caminho que o pedido de fato seguiu (nota lançada depois de pago, ou nunca
    passou por lote) não é pendência, é caminho não tomado.

    `dados` é o pré-carregamento opcional que a LISTAGEM usa (Task 6): um dict
    {'contas': [...], 'notas': [...], 'adiantamentos': [...]} já filtrado para
    este pedido. Sem ele a função consulta sozinha, que é o certo para a tela de
    um pedido só. 🔬 a listagem traz até 200 pedidos (`compras_views.py:592`,
    `query.limit(200)`) e NÃO é paginada — chamar esta função 200 vezes sem
    pré-carregamento são ~800 consultas, o mesmo vício que custou /obras e
    /ponto/lista-obras em 21/08.
    """
    from models import EstadoRequisicao

    requisicao = pedido.requisicao
    tem_requisicao = requisicao is not None

    estado = getattr(requisicao, 'estado', None)
    aprovada = estado in (EstadoRequisicao.APROVADA, EstadoRequisicao.CONVERTIDA)

    acesa = {
        'requisitada': tem_requisicao,
        'aprovada': aprovada,
        'pedido_emitido': pedido.id is not None,
        'material_recebido': False,
        'nota_lancada': False,
        'liberada': False,
        'em_lote': False,
        'paga': False,
        'encerrada': False,
    }
    aplicavel = {chave: True for chave in CHAVES}
    aplicavel['requisitada'] = tem_requisicao
    aplicavel['aprovada'] = tem_requisicao
    selos = {chave: [] for chave in CHAVES}

    from services.financeiro_compra import valor_das_notas

    # A tríade só existe no regime novo. 📖 templates/compras/index.html:126:
    # em pedido legado o estoque entrou na emissão, e inventar "não recebido"
    # ali seria mentir.
    tem_triade = bool(pedido.exige_atesto)
    aplicavel['material_recebido'] = tem_triade
    aplicavel['nota_lancada'] = tem_triade

    recebido = pedido.situacao_recebimento in ('parcial', 'recebido',
                                               'encerrado_com_saldo')
    acesa['material_recebido'] = tem_triade and recebido
    acesa['nota_lancada'] = tem_triade and valor_das_notas(pedido) > 0

    if pedido.situacao_recebimento == 'encerrado_com_saldo':
        selos['material_recebido'].append('com saldo')
        selos['encerrada'].append('com saldo')

    recebimento_fechado = pedido.situacao_recebimento in ('recebido',
                                                          'encerrado_com_saldo')

    from models import AdiantamentoFornecedor, ContaPagar

    contas = ContaPagar.query.filter_by(
        pedido_compra_id=pedido.id, admin_id=pedido.admin_id).all()

    acesa['liberada'] = any(c.situacao_liberacao == 'liberada' for c in contas)
    if any(c.situacao_liberacao == 'liberada' and c.liberacao_justificativa
           for c in contas):
        selos['liberada'].append('com ressalva')

    acesa['em_lote'] = any(c.fechamento_id for c in contas)
    if any(c.fechamento is not None and c.fechamento.segregacao_justificativa
           for c in contas):
        selos['em_lote'].append('fechado por quem montou')

    pagas = [c for c in contas if c.status in ('PAGO', 'PARCIAL')]
    # A casa 8 é UNIÃO, não campo único: no Fluxo B o dinheiro sai como
    # adiantamento, antes de existir conta paga. Sem esta perna a régua diria
    # "não pago" sobre um pedido cujo dinheiro já saiu.
    adiantamento_baixado = False
    if pedido.fluxo_pagamento == 'adiantamento':
        adiantamento_baixado = AdiantamentoFornecedor.query.filter(
            AdiantamentoFornecedor.pedido_id == pedido.id,
            AdiantamentoFornecedor.baixado_em.isnot(None)).first() is not None
    acesa['paga'] = bool(pagas) or adiantamento_baixado
    if adiantamento_baixado:
        selos['paga'].append('adiantamento')

    tudo_pago = bool(contas) and all(c.status == 'PAGO' for c in contas)
    # Pedido LEGADO (sem tríade) não tem recebimento a fechar: exigir
    # `recebimento_fechado` dele o prenderia para sempre na casa 9, com o
    # ponteiro apontando uma casa que nunca vai acender. Para ele, encerrar é
    # pagar.
    if tem_triade:
        acesa['encerrada'] = (tudo_pago or adiantamento_baixado) and recebimento_fechado
    else:
        acesa['encerrada'] = tudo_pago

    casas = [Casa(chave=c, rotulo=ROTULOS[c],
                  grupo='triade' if c in GRUPO_TRIADE else None,
                  acesa=bool(acesa[c]), aplicavel=bool(aplicavel[c]),
                  selos=list(selos[c]))
             for c in CHAVES]

    # A casa 9 é terminal: quando ela acende, o pedido terminou. Sem este
    # curto-circuito, uma casa opcional que ficou apagada no caminho realizado
    # (nota lançada depois do pagamento, pagamento sem lote — nenhuma delas
    # bloqueia o encerramento, 🔬 confirmado pelos testes
    # `test_pedido_legado_encerra_so_com_o_pagamento` e
    # `test_encerrada_exige_pago_e_recebimento_fechado`) prenderia o ponteiro
    # numa casa que a régua já provou não fazer falta.
    if acesa['encerrada']:
        ponteiro = None
    else:
        ponteiro = next((c.chave for c in casas if c.aplicavel and not c.acesa),
                        None)
    return {'casas': casas, 'ponteiro': ponteiro, 'encerrada_por': None}
