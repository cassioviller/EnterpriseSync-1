"""Fase 6 / Task 12 — diff entre duas versões de proposta.

O aditivo pergunta "o que mudou da versão que o cliente aprovou para esta?".
Sem diff, a resposta é ler duas listas lado a lado e confiar na memória — que é
exatamente como um item suprimido passa despercebido até a medição.

Contrato **idêntico** ao de `services.orcamento_versao.diff_revisoes`, de
propósito: os dois templates de comparação são simétricos, e quem lê um
entende o outro.

**Nunca casa por descrição.** Descrição é texto editável: casar por ela produz
falso "mantido" quando alguém corrige uma vírgula, e falso "suprimido +
incluído" quando renomeia de verdade. Renomear é ALTERAR.

A convenção de linhagem da proposta é diferente da do orçamento:
`PropostaItem.proposta_item_origem_id` aponta para a **raiz** (o clone propaga
a raiz, não o pai imediato), então não há corrente a subir — mas há o fallback
por `item_numero`, para as revisões criadas antes da Fase 0.6, em que os dois
lados têm `origem_id` NULL e cada item seria raiz de si mesmo.
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

logger = logging.getLogger(__name__)

CENTAVO = Decimal('0.01')


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


def _em_centavos(v) -> Decimal:
    """Dinheiro se compara em centavos.

    `subtotal_calculado` devolve `Numeric(15,2)` quando há snapshot
    persistido e o produto `quantidade × preco_unitario` (até 5 casas,
    `Numeric(10,3) × Numeric(10,2)`) quando não há. Sem normalizar, o caso
    misto — item sem snapshot ao lado de item com snapshot — fazia linha
    INTOCADA dar diferença de arredondamento (ex.: 0.00315) e sair como
    'alterado'. `subtotal_calculado` nunca tem mais de 2 casas com
    significado monetário real neste sistema: o snapshot persistido já é
    `Numeric(15,2)`, e o próprio total é sempre exibido e conferido em
    centavos — então uma diferença abaixo de um centavo não é "real" em
    nenhum contexto que este diff alimenta.
    """
    return _dec(v).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _chaves(item) -> list:
    """As identidades do item através das versões, em ordem de confiança.

    Reusa `handlers.propostas_handlers._chaves_de_linhagem` — a MESMA regra que
    a propagação proposta→obra aplica para decidir se dois itens são o mesmo.
    Duplicá-la aqui criaria duas verdades sobre identidade de item, e elas
    divergiriam no primeiro ajuste.

    Import tardio de propósito: `handlers` importa `services` nos seus próprios
    caminhos, e um import de módulo aqui fecharia o ciclo.
    """
    from handlers.propostas_handlers import _chaves_de_linhagem
    return _chaves_de_linhagem(item)


def diff_versoes(origem, destino) -> list[dict]:
    """Compara duas versões de proposta, item a item, pela linhagem.

    Devolve::

        [{'situacao': 'mantido'|'alterado'|'incluido'|'suprimido',
          'origem': PropostaItem | None,
          'destino': PropostaItem | None,
          'delta_quantidade': Decimal | None,
          'delta_valor': Decimal | None}]

    `delta_*` é `None` — e não zero — quando falta um dos lados: zero diria
    "não mudou", e um item incluído não "não mudou".

    Um item da origem casa com no máximo UM item do destino. Sem essa trava, o
    fallback por `item_numero` poderia parear duas linhas do destino no mesmo
    item de origem e o total do diff deixaria de fechar.
    """
    indice, ordem_origem = {}, []
    for it in origem.itens:
        ordem_origem.append(it)
        for chave in _chaves(it):
            indice.setdefault(chave, it)

    linhas, usados = [], set()
    for it in sorted(destino.itens,
                     key=lambda i: (i.item_numero or 0, i.id)):
        anterior = None
        for chave in _chaves(it):
            candidato = indice.get(chave)
            if candidato is not None and candidato.id not in usados:
                anterior = candidato
                break
        if anterior is None:
            linhas.append({'situacao': 'incluido', 'origem': None,
                           'destino': it, 'delta_quantidade': None,
                           'delta_valor': None})
            continue
        usados.add(anterior.id)
        dq = _dec(it.quantidade) - _dec(anterior.quantidade)
        # `subtotal_calculado`, nunca `subtotal` cru: o snapshot é NULL para
        # todo item fora do caminho de explosão da Task #89, e NULL − NULL = 0
        # fazia revisão que muda só o preço sair como "mantido" com impacto
        # R$ 0,00.
        #
        # Duas responsabilidades, dois números — de propósito:
        #
        # `dv_centavos` decide SÓ a classificação (mantido vs alterado), em
        # centavos: `subtotal_calculado` mistura snapshot de 2 casas com
        # produto cru de até 5, e uma linha intocada cujo lado sem snapshot
        # cai no fallback dava diferença de arredondamento — não zero — e
        # saía como "alterado".
        #
        # `dv` (bruto, sem arredondar) é o que entra em `delta_valor` e,
        # dali, no somatório de `total_do_diff`. Arredondar CADA linha antes
        # de somar esconderia um efeito sistêmico: um reajuste de preço
        # espalhado por muitos itens, cada delta abaixo do centavo, somaria
        # zero linha a linha mesmo que o impacto real, agregado, seja
        # material — `total_do_diff` arredonda uma vez só, no fim.
        # `delta_quantidade` (`dq`, acima) já era bruto e continua: uma
        # edição real de quantidade, por menor que seja, tem que continuar
        # acusando "alterado" mesmo que o impacto em reais fique abaixo do
        # centavo.
        dv = _dec(it.subtotal_calculado) - _dec(anterior.subtotal_calculado)
        dv_centavos = _em_centavos(it.subtotal_calculado) - _em_centavos(
            anterior.subtotal_calculado)
        mudou = (dq != 0 or dv_centavos != 0
                 or (it.descricao or '') != (anterior.descricao or '')
                 or (it.unidade or '') != (anterior.unidade or ''))
        linhas.append({'situacao': 'alterado' if mudou else 'mantido',
                       'origem': anterior, 'destino': it,
                       'delta_quantidade': dq, 'delta_valor': dv})

    for it in ordem_origem:
        if it.id not in usados:
            linhas.append({'situacao': 'suprimido', 'origem': it,
                           'destino': None, 'delta_quantidade': None,
                           'delta_valor': None})
    return linhas


def total_do_diff(linhas) -> Decimal:
    """Delta financeiro da revisão inteira.

    Soma os deltas de quem tem os dois lados, mais o valor cheio dos incluídos,
    menos o dos suprimidos. É o número que o extrato de contrato mostra como
    "impacto do aditivo" — e ele tem de bater com a diferença dos totais das
    duas versões, senão o diff perdeu ou duplicou linha.

    A soma acumula em precisão BRUTA (o mesmo `subtotal_calculado`, sem
    arredondar por linha) e só arredonda para centavos no final. Rodar
    `_em_centavos` por parcela — inclusive nos ramos `incluido`/`suprimido`,
    que somam `subtotal_calculado` direto — misturaria termos de 2 casas com
    termos de até 5 na mesma soma, e arredondar cada termo individualmente
    apagaria um efeito sistêmico real (muitos deltas abaixo do centavo que,
    somados, são materiais).
    """
    total = Decimal('0')
    for l in linhas:
        if l['delta_valor'] is not None:
            total += l['delta_valor']
        elif l['situacao'] == 'incluido':
            total += _dec(l['destino'].subtotal_calculado)
        elif l['situacao'] == 'suprimido':
            total -= _dec(l['origem'].subtotal_calculado)
    return _em_centavos(total)
