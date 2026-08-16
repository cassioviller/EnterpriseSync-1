"""As regras que sobem a alçada além do valor — spec 2026-08-16.

Separado de `alcada_compras.py` de propósito: as quatro condições consultam
quatro subsistemas diferentes (mapa de concorrência, custo orçado, outras
requisições, a própria SC). Empurrar isso para dentro do motor de faixas o
tornaria o arquivo que ninguém mais entende.

Este módulo não decide permissão e não muda estado. Ele responde uma pergunta
só: **que faixa esta requisição exige, e por quê**.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from models import EstadoRequisicao, RequisicaoCompra, db

logger = logging.getLogger('alcada_regras')

# Janela do anti-fracionamento, em dias CORRIDOS. Não é mês-calendário: mês
# fechado convida a esperar o dia 1º.
JANELA_DIAS = 30

# Estados que representam COMPROMISSO de gasto. Rascunho não é compromisso
# (e um rascunho abandonado elevaria a exigência de quem está trabalhando);
# rejeitada e cancelada são a prova de que o dinheiro não vai sair.
ESTADOS_QUE_SOMAM = (
    EstadoRequisicao.AGUARDANDO_APROVACAO,
    EstadoRequisicao.APROVADA,
    EstadoRequisicao.CONVERTIDA,
)


def _d(v):
    return Decimal(str(v or 0))


def soma_da_janela(requisicao, agora=None):
    """(soma, somadas) das outras SCs da mesma obra+etapa nos 30 dias.

    `somadas` é uma lista de dicts prontos para o carimbo — é o que a tela
    mostra quando alguém pergunta por que a exigência subiu.

    A própria requisição fica de fora (`id !=`): no momento do carimbo ela já
    está em AGUARDANDO_APROVACAO, e sem isso se somaria a si mesma.

    Etapa NULL casa com etapa NULL — é o balde único da obra, e é o que impede
    que deixar o centro de custo em branco desligue a regra.
    """
    agora = agora or datetime.utcnow()
    corte = agora - timedelta(days=JANELA_DIAS)

    q = (RequisicaoCompra.query
         .filter(RequisicaoCompra.admin_id == requisicao.admin_id,
                 RequisicaoCompra.obra_id == requisicao.obra_id,
                 RequisicaoCompra.id != requisicao.id,
                 RequisicaoCompra.estado.in_(ESTADOS_QUE_SOMAM),
                 RequisicaoCompra.created_at >= corte))
    if requisicao.obra_servico_custo_id is None:
        q = q.filter(RequisicaoCompra.obra_servico_custo_id.is_(None))
    else:
        q = q.filter(RequisicaoCompra.obra_servico_custo_id ==
                     requisicao.obra_servico_custo_id)

    somadas, total = [], Decimal('0')
    for outra in q.order_by(RequisicaoCompra.created_at).all():
        total += _d(outra.valor_estimado)
        somadas.append({
            'numero': outra.numero,
            'valor': float(_d(outra.valor_estimado)),
            'data': outra.created_at.date().isoformat() if outra.created_at else None,
        })
    return total, somadas
