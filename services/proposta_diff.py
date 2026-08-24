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
from decimal import Decimal

logger = logging.getLogger(__name__)


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


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
        dv = _dec(it.subtotal) - _dec(anterior.subtotal)
        mudou = (dq != 0 or dv != 0
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
    """
    total = Decimal('0')
    for l in linhas:
        if l['delta_valor'] is not None:
            total += l['delta_valor']
        elif l['situacao'] == 'incluido':
            total += _dec(l['destino'].subtotal)
        elif l['situacao'] == 'suprimido':
            total -= _dec(l['origem'].subtotal)
    return total
