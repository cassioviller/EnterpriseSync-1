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


class Avaliacao:
    """O que o motor decidiu, e com que números. Não persiste nada."""

    def __init__(self, valor_estimado, valor_efetivo, somadas, faixa_base,
                 condicoes, faixa_final):
        self.valor_estimado = valor_estimado
        self.valor_efetivo = valor_efetivo
        self.somadas = somadas
        self.faixa_base = faixa_base
        self.condicoes = condicoes
        self.degraus = len(condicoes)
        self.faixa_final = faixa_final

    def motivos_para_carimbo(self):
        """O JSON que vai para `requisicao_compra.alcada_motivos`."""
        return {
            'valor_estimado': float(self.valor_estimado),
            'valor_efetivo': float(self.valor_efetivo),
            'somadas': self.somadas,
            'faixa_base_ordem': getattr(self.faixa_base, 'ordem', None),
            'condicoes': self.condicoes,
        }


def _sem_concorrencia(requisicao):
    """A SC teve concorrência? Piso FIXO de 2 fornecedores.

    Não usa o `fornecedores_minimos` da faixa de propósito: amarrar a condição
    à faixa final seria circular (a faixa depende dos degraus, que dependeriam
    da condição) e inútil — só dispararia onde a pendência de
    `exige_mapa_concorrencia` já barra. São duas perguntas diferentes: aqui,
    "houve concorrência?"; lá, "esta faixa aceita fechar sem mapa de N?".
    """
    from services.alcada_compras import mapa_serve_de_concorrencia
    if mapa_serve_de_concorrencia(requisicao, minimo=2):
        return None
    return {'codigo': 'sem_concorrencia',
            'texto': 'compra sem mapa de concorrência com ao menos 2 fornecedores',
            'numeros': {}}


def _estoura_orcamento(requisicao, comprometido):
    """Realizado + comprometido + esta SC passa do orçado da etapa?

    Sem etapa, a base é a obra inteira. Orçado indisponível (zero, ausente ou
    consulta que falhou) NÃO dispara — a condição se cala em vez de inventar
    um número, e `custo_orcado` já devolve `{}` quando quebra.
    """
    from services.custo_orcado import (custo_orcado_da_obra,
                                       projecao_de_custo_por_servico)
    osc_id = requisicao.obra_servico_custo_id
    if osc_id:
        projecao = projecao_de_custo_por_servico(
            requisicao.obra_id, requisicao.admin_id).get(osc_id) or {}
        orcado = _d(projecao.get('orcado'))
        realizado = _d(projecao.get('realizado'))
        base = f'etapa {osc_id}'
    else:
        orcado = _d(custo_orcado_da_obra(requisicao.obra_id, requisicao.admin_id))
        realizado = Decimal('0')
        base = 'obra'

    if orcado <= 0:
        return None

    total = realizado + comprometido + _d(requisicao.valor_estimado)
    if total <= orcado:
        return None
    return {'codigo': 'estoura_orcamento',
            'texto': f'o pedido leva o custo de {base} acima do orçado',
            'numeros': {'orcado': float(orcado), 'realizado': float(realizado),
                        'comprometido': float(comprometido),
                        'esta_sc': float(_d(requisicao.valor_estimado))}}


def _nao_menor_preco(requisicao):
    """Existe cotação mais barata que a selecionada, em algum item do mapa?

    Valor zero é "não cotou", não "de graça" — fica de fora da comparação.
    """
    from models import MapaCotacao
    if not requisicao.mapa_v2_id:
        return None
    cotacoes = (MapaCotacao.query
                .filter_by(mapa_id=requisicao.mapa_v2_id,
                           admin_id=requisicao.admin_id)
                .filter(MapaCotacao.valor_unitario > 0)
                .all())
    por_item = {}
    for c in cotacoes:
        por_item.setdefault(c.item_id, []).append(c)

    for item_id, lista in por_item.items():
        escolhida = next((c for c in lista if c.selecionado), None)
        if escolhida is None:
            continue
        menor = min(_d(c.valor_unitario) for c in lista)
        if _d(escolhida.valor_unitario) > menor:
            return {'codigo': 'nao_menor_preco',
                    'texto': 'o fornecedor escolhido não é o de menor preço',
                    'numeros': {'item_id': item_id,
                                'escolhido': float(_d(escolhida.valor_unitario)),
                                'menor': float(menor)}}
    return None


def _urgente(requisicao):
    if (requisicao.urgencia or 'normal') != 'urgente':
        return None
    return {'codigo': 'urgente',
            'texto': 'requisição marcada como urgente',
            'numeros': {}}


def _faixa_por_degraus(admin_id, faixa_base, degraus):
    """A faixa `degraus` acima da base, com teto na mais alta ativa."""
    from services.alcada_compras import faixas_ordenadas
    if getattr(faixa_base, 'id', None) is None:
        return faixa_base          # _FaixaSeguranca: já é o máximo
    faixas = faixas_ordenadas(admin_id)
    ids = [f.id for f in faixas]
    if faixa_base.id not in ids:
        return faixa_base
    i = ids.index(faixa_base.id)
    return faixas[min(i + degraus, len(faixas) - 1)]


def avaliar_alcada(requisicao, agora=None):
    """A avaliação completa. Uma passada, sem laço."""
    from services.alcada_compras import faixa_para_valor

    comprometido, somadas = soma_da_janela(requisicao, agora=agora)
    valor_efetivo = _d(requisicao.valor_estimado) + comprometido
    faixa_base = faixa_para_valor(requisicao.admin_id, valor_efetivo)

    condicoes = [c for c in (
        _sem_concorrencia(requisicao),
        _estoura_orcamento(requisicao, comprometido),
        _nao_menor_preco(requisicao),
        _urgente(requisicao),
    ) if c]

    faixa_final = _faixa_por_degraus(requisicao.admin_id, faixa_base,
                                     len(condicoes))
    return Avaliacao(_d(requisicao.valor_estimado), valor_efetivo, somadas,
                     faixa_base, condicoes, faixa_final)
