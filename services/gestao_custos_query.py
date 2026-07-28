"""Filtro compartilhado para agregados de GestaoCustoFilho.

Excluir um RDO não apaga o lançamento financeiro que ele gerou: o
`cancelar_custos_rdo` (services/rdo_custos.py) marca o `GestaoCustoPai` como
CANCELADO de propósito, para preservar o histórico para auditoria. Só que
nenhum dos agregados de "custo realizado" olhava `status` — o custo de um RDO
excluído continuava somando no Realizado da obra, medido e reproduzido.

Cancelar é uma decisão de quem escreve; ignorar o cancelado é obrigação de
quem lê. Este módulo é o lugar dessa obrigação, para o próximo agregado
nascer certo em vez de repetir o descuido.
"""
from sqlalchemy import or_

CANCELADO = 'CANCELADO'


def sem_cancelados(query):
    """Tira do agregado os filhos cujo pai foi cancelado.

    A query já precisa ter `GestaoCustoPai` no join — este filtro não o
    adiciona, para não mudar a cardinalidade de quem chama sem perceber.

    `status` é nullable: um `!= 'CANCELADO'` cru descartaria as linhas com
    NULL junto, porque em SQL `NULL != 'X'` é NULL, não TRUE. Hoje não há
    nenhuma no banco, mas sumir com lançamento legítimo é o tipo de erro que
    ninguém percebe até o número não fechar.
    """
    from models import GestaoCustoPai
    return query.filter(
        or_(GestaoCustoPai.status.is_(None),
            GestaoCustoPai.status != CANCELADO)
    )
