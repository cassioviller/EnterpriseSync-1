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
    `ponteiro` é None quando não falta nada aplicável.

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

    # A casa 9 depende do pagamento, entregue na Task 3 — provisória por ora.
    acesa['encerrada'] = (not tem_triade) and recebimento_fechado

    casas = [Casa(chave=c, rotulo=ROTULOS[c],
                  grupo='triade' if c in GRUPO_TRIADE else None,
                  acesa=bool(acesa[c]), aplicavel=bool(aplicavel[c]),
                  selos=list(selos[c]))
             for c in CHAVES]

    ponteiro = next((c.chave for c in casas if c.aplicavel and not c.acesa), None)
    return {'casas': casas, 'ponteiro': ponteiro, 'encerrada_por': None}
