"""Serviço da RequisicaoCompra — Fase 3.

Único caminho de escrita do estado e do valor da requisição. O modelo
(models.RequisicaoCompra) é deliberadamente burro: nenhuma regra mora
lá, para que não existam dois lugares onde uma transição possa
acontecer.
"""
import logging
from datetime import datetime
from decimal import Decimal

from models import EstadoRequisicao, RequisicaoCompra, db

logger = logging.getLogger('requisicao_compra')


def recalcular_valor(requisicao):
    """Soma os itens em `valor_estimado`. NÃO commita.

    Chamada em todo ponto que mexe em item. O valor é a base da alçada
    (services/alcada_compras.py), então deixá-lo desatualizado é deixar a
    requisição cair na faixa errada.
    """
    total = Decimal('0.00')
    for item in requisicao.itens:
        total += item.subtotal
    requisicao.valor_estimado = total
    requisicao.updated_at = datetime.utcnow()
    return total


def proximo_numero(admin_id, ano=None):
    """Próximo `RC-<ano>-<NNNN>` do tenant.

    Sequencial por tenant e por ano. Há corrida possível entre dois
    requests simultâneos; ela é fechada pelo UNIQUE (admin_id, numero) e
    pelo retry em `compras_views.requisicao_nova_post`. Mesmo padrão já
    usado no versionamento do relatório de mapa (views/obras.py:3279).
    """
    ano = ano or datetime.utcnow().year
    prefixo = f'RC-{ano}-'
    ultimo = (
        db.session.query(RequisicaoCompra.numero)
        .filter(RequisicaoCompra.admin_id == admin_id)
        .filter(RequisicaoCompra.numero.like(f'{prefixo}%'))
        .order_by(RequisicaoCompra.numero.desc())
        .first()
    )
    if not ultimo:
        return f'{prefixo}0001'
    try:
        seq = int(ultimo[0].rsplit('-', 1)[1]) + 1
    except (IndexError, ValueError):
        logger.warning('numero fora do padrão no tenant %s: %r', admin_id, ultimo[0])
        seq = 1
    return f'{prefixo}{seq:04d}'
