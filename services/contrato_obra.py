"""Escritor único de `Obra.valor_contrato` — p9 do `PLANO-NUCLEO.md`.

## A decisão de 03/08

> Cássio, 03/08: o dono é a **Fase 6** — `ObraContratoVersao` +
> `services/contrato_obra.py` como cadeia única. A Fase 9b vira camada
> documental (PDF, assinatura, vencimento), sem listener concorrente.

Isto ratifica o que a própria 9b já assumia na premissa P1: o aditivo se
subordina à cadeia de versões, não cria uma segunda.

## Por que este módulo já existe, antes da Fase 6

Hoje **quatro** lugares escrevem o campo, cada um com sua regra:

| Onde | Quando |
|---|---|
| `event_manager.py:1195` | aprovação da proposta (e aditivo: congela medições já emitidas antes de trocar a base) |
| `views/obras.py:418` | criação manual da obra |
| `views/obras.py:955` | edição manual pelo formulário |
| `services/importacao_fisico_financeiro.py:754` | import de JSON físico-financeiro (`valor_venda`) |

O último estava **omitido do inventário da Fase 6** — quem executasse aquele
plano fecharia três portas e deixaria a quarta aberta.

Rotear os quatro por aqui **agora** torna "um único ponto de escrita"
verdadeiro antes da Fase 6 existir, e transforma a fase num acréscimo
(gravar `ObraContratoVersao` dentro desta função) em vez de uma caça a
chamadores espalhados.

## O que este módulo NÃO faz ainda

Não versiona. `ObraContratoVersao` é entrega da Fase 6; aqui o campo é
escrito e a mudança é **logada com origem e motivo** — que é o mínimo para
responder "quem mudou o contrato desta obra, e por quê" enquanto a tabela não
existe.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Origens reconhecidas. Não é enum de banco de propósito: enquanto a Fase 6
# não define a tabela de versões, isto é vocabulário de log — e log com
# vocabulário fechado é o que permite auditar depois.
ORIGEM_PROPOSTA = 'proposta_aprovada'
ORIGEM_ADITIVO = 'aditivo'
ORIGEM_CADASTRO = 'cadastro_manual'
ORIGEM_EDICAO = 'edicao_manual'
ORIGEM_IMPORTACAO = 'importacao_fisico_financeiro'

ORIGENS = (ORIGEM_PROPOSTA, ORIGEM_ADITIVO, ORIGEM_CADASTRO, ORIGEM_EDICAO,
           ORIGEM_IMPORTACAO)


def definir_valor_contrato(obra, valor, origem: str, motivo: str = '',
                           usuario_id=None) -> float:
    """Grava `obra.valor_contrato`. **Único** caminho de escrita do campo.

    Não commita: quem chama decide a transação — a aprovação de proposta, por
    exemplo, escreve o contrato no meio de uma transação que também cria
    itens de medição e cronograma, e um commit aqui a partiria no meio.

    `origem` deve ser uma das constantes deste módulo. Origem desconhecida
    não é bloqueada (não é papel deste módulo derrubar um cadastro), mas sai
    no log como anomalia — é assim que um quinto escritor aparece.

    Devolve o valor gravado.
    """
    anterior = float(getattr(obra, 'valor_contrato', 0) or 0)
    novo = float(valor or 0)

    if origem not in ORIGENS:
        logger.warning(
            '[p9] valor_contrato da obra %s escrito com origem desconhecida '
            '%r — se apareceu um escritor novo, ele precisa entrar em '
            'services/contrato_obra.py', getattr(obra, 'id', '?'), origem)

    obra.valor_contrato = novo

    if anterior != novo:
        logger.info(
            '[p9] obra %s: valor_contrato %.2f → %.2f (origem=%s, motivo=%s, '
            'usuario=%s)', getattr(obra, 'codigo', None) or getattr(obra, 'id', '?'),
            anterior, novo, origem, motivo or '—', usuario_id or '—')
    return novo
