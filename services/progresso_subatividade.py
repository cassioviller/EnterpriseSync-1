"""Progresso da subatividade DERIVADO do cronograma — p8 do `PLANO-NUCLEO.md`.

## O elo que existia e ninguém lia

`RDOServicoSubatividade.subatividade_mestre_id` (models.py:1952) e
`TarefaCronograma.subatividade_mestre_id` (models.py:5897) apontam para o
mesmo catálogo. Quando os dois lados estão preenchidos, a linha do RDO e a
tarefa do cronograma **são o mesmo trabalho** — e ninguém usava esse elo para
progresso: cada lado guardava o próprio número, digitado ou derivado por
caminhos diferentes, e eles divergiam em silêncio.

O sintoma visível estava na medição: `_recalcular_imc_avanco`
(`services/medicao_service.py:267`) cai para
`MAX(RDOServicoSubatividade.percentual_conclusao)` quando o item comercial não
tem vínculo de cronograma. Esse MAX é de uma fonte; o percentual da tarefa é
de outra. A mesma obra podia medir por um número e mostrar outro no Gantt.

## O que este módulo faz — e o que deixa para depois

Faz a **leitura convergir**: dada uma linha de RDO, devolve o percentual da
tarefa de cronograma correspondente pelo elo do catálogo. Uma fonte, dois
lugares.

Não reescreve as gravações. A dualidade de ESCRITA — a coluna
`TarefaCronograma.percentual_concluido` (import de .mpp/JSON, grade do editor,
sincronização) versus os apontamentos `RDOApontamentoCronograma` — é o resto
do p8, e o p4 já registrou por que ela não pode ser resolvida por decreto:
`utils/cronograma_engine.progresso_ponderado_armazenado` existe porque trocar
a fonte embaixo da medição do portal zeraria obra que avança sem apontar RDO.

Por isso a derivação aqui lê `percentual_concluido` da tarefa — a fonte que
todos os caminhos de entrada alimentam —, não o motor de apontamentos.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def tarefa_da_subatividade(subatividade_mestre_id, obra_id, admin_id):
    """A tarefa de cronograma que representa esta subatividade nesta obra.

    Só o cronograma INTERNO e vivo (`is_cliente=False`, `ativa=True`): a
    cópia-cliente é outro conjunto, e arquivada não conta.

    Devolve None quando o elo não existe — que é o caso da maioria dos dados
    antigos, e por isso todo chamador precisa de fallback.
    """
    if not subatividade_mestre_id or not obra_id:
        return None
    try:
        from models import TarefaCronograma
        return (TarefaCronograma.query
                .filter_by(obra_id=obra_id, admin_id=admin_id,
                           subatividade_mestre_id=subatividade_mestre_id,
                           is_cliente=False)
                .filter(TarefaCronograma.ativa.is_(True))
                .first())
    except Exception:
        logger.exception('tarefa_da_subatividade falhou (sub=%s obra=%s)',
                         subatividade_mestre_id, obra_id)
        return None


def percentual_derivado(rss, obra_id, admin_id):
    """Percentual da linha de RDO, derivado do cronograma quando há elo.

    Ordem:

    1. tarefa de cronograma ligada pelo `subatividade_mestre_id` → o
       `percentual_concluido` dela;
    2. sem elo, o valor gravado na própria linha (`percentual_conclusao`).

    Devolve `(percentual, origem)`, com origem em `{'cronograma', 'linha'}`.
    A origem importa: é o que permite a um chamador dizer no log de onde veio
    o número em vez de apresentar dois valores diferentes sem explicação.
    """
    tarefa = tarefa_da_subatividade(
        getattr(rss, 'subatividade_mestre_id', None), obra_id, admin_id)
    if tarefa is not None:
        return float(tarefa.percentual_concluido or 0), 'cronograma'
    return float(getattr(rss, 'percentual_conclusao', 0) or 0), 'linha'


def percentual_do_servico_na_obra(servico_id, obra_id, admin_id):
    """Maior percentual do serviço na obra, preferindo o cronograma.

    Substitui o `MAX(RDOServicoSubatividade.percentual_conclusao)` que a
    medição usava como fallback: onde há elo com o cronograma, o número passa
    a ser o mesmo que o Gantt mostra; onde não há, cai para o gravado, que é
    o comportamento de antes.

    Devolve None quando não há nenhuma linha — para o chamador distinguir
    "sem dado" de "zero por cento".
    """
    try:
        from models import RDO, RDOServicoSubatividade

        linhas = (
            RDOServicoSubatividade.query
            .join(RDO, RDO.id == RDOServicoSubatividade.rdo_id)
            .filter(RDOServicoSubatividade.servico_id == servico_id,
                    RDOServicoSubatividade.admin_id == admin_id,
                    RDO.obra_id == obra_id,
                    RDO.status.in_(['Finalizado', 'FINALIZADO', 'finalizado']))
            .all()
        )
        if not linhas:
            return None

        melhor = None
        origens = set()
        for linha in linhas:
            perc, origem = percentual_derivado(linha, obra_id, admin_id)
            origens.add(origem)
            if melhor is None or perc > melhor:
                melhor = perc

        if origens == {'cronograma'}:
            logger.debug('[p8] serviço %s da obra %s: %.2f%% derivado do '
                         'cronograma', servico_id, obra_id, melhor or 0)
        elif 'cronograma' in origens:
            logger.info('[p8] serviço %s da obra %s: linhas com e sem elo de '
                        'catálogo convivendo — número veio do maior entre as '
                        'duas fontes', servico_id, obra_id)
        return melhor
    except Exception:
        logger.exception('percentual_do_servico_na_obra falhou '
                         '(servico=%s obra=%s)', servico_id, obra_id)
        return None
