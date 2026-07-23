#!/usr/bin/env python3
"""Regras de derivação do destino do custo — SIGE Fase 4.

Todo lançamento de custo tem de ter um destino: uma **obra** ou o **centro
de custo administrativo** do tenant. Este módulo concentra as regras que
decidem qual, tanto para o backfill histórico quanto para a escrita nova.

A cascata, do mais forte para o mais fraco, parando no primeiro que resolve:

  R1  unanimidade dos filhos  → grava `gestao_custo_pai.obra_id`
  R2  irmão unânime           → filho órfão herda a obra do próprio pai
  R3  origem                  → filho órfão herda a obra da linha de origem
  R4  natureza da origem      → folha e almoxarifado vão para administrativo
  R5  resto                   → administrativo, carimbado e listado

Rejeitadas de propósito, e o motivo:

  * por DATA (obra ativa na data): com mais de uma obra ativa — o caso
    normal — é sorteio disfarçado de regra.
  * por CRIADOR: `admin_id` é tenant, não pessoa (models.py:5238);
    `responsavel_id` só vem preenchido por compras (compras_views.py:210).
  * por CENTRO DE CUSTO já gravado: 8 filhos de 1.823 tinham
    `centro_custo_id` em 2026-07-21. O campo está morto.
  * por RATEIO proporcional ao orçado (o que `resumo_custos_obra.py:191`
    faz em memória): gravar rateio é transformar estimativa em dado. É
    exatamente a dívida que esta fase existe para pagar.
"""
import logging

logger = logging.getLogger('destino_custo')

# origem_tabela → (tabela, coluna de obra). Todas conferidas no banco em
# 2026-07-21: as cinco têm a coluna `obra_id`.
ORIGENS_COM_OBRA = {
    'pedido_compra': ('pedido_compra', 'obra_id'),
    'conta_pagar': ('conta_pagar', 'obra_id'),
    'reembolso_funcionario': ('reembolso_funcionario', 'obra_id'),
    'alimentacao_lancamento': ('alimentacao_lancamento', 'obra_id'),
    'lancamento_transporte': ('lancamento_transporte', 'obra_id'),
}

# Origens que são administrativas POR CONSTRUÇÃO, não por falta de dado.
#   folha_pagamento        — a mão de obra que é custo de obra entra por
#                            outro caminho e já vem com obra: os filhos de
#                            origem rdo_mao_obra / rdo_mao_obra_va /
#                            rdo_mao_obra_vt / rdo_custo_diario têm obra em
#                            100% dos casos (conferido em 2026-07-21).
#                            Mandar a folha para obra seria contagem dupla.
#   almoxarifado_movimento — material que ENTRA em estoque ainda não é custo
#                            de obra; vira quando sai. Hoje
#                            `event_manager.py:223` grava sem destino nenhum.
ORIGENS_ADMINISTRATIVAS = {
    'folha_pagamento',
    'almoxarifado_movimento',
}

# Categorias em que "administrativo" é resposta errada por definição.
# FATURAMENTO_DIRETO é material que o cliente paga direto ao fornecedor DA
# OBRA (compras_views.py:314-345) — sem obra não significa nada.
CATEGORIAS_QUE_EXIGEM_OBRA = {'FATURAMENTO_DIRETO'}

# Carimbo das linhas que só a R5 alcançou — o que o humano tem de revisar.
MARCA_FALLBACK = '[FASE4:R5]'
REGRA_FALLBACK = 'administrativo'


def obra_unanime(obra_ids):
    """R1/R2 — devolve a única obra presente, ou None.

    `None` na lista é ignorado (linha sem obra não vota). Devolve None
    quando a lista é vazia, quando só há None, ou quando há divergência.
    Nunca "escolhe a maioria": maioria é chute.
    """
    distintas = {o for o in obra_ids if o is not None}
    if len(distintas) == 1:
        return next(iter(distintas))
    return None


def classificar_pai(obra_ids):
    """Classifica um pai a partir das obras dos filhos.

    Devolve `(situacao, obra_id)` com situacao em:
      'unanime'   — resolvido, obra_id preenchido
      'multiobra' — filhos em obras diferentes; obra_id do pai fica NULL
      'sem_obra'  — tem filhos, nenhum com obra
      'sem_filho' — pai sem filho nenhum
    """
    obra_ids = list(obra_ids)
    if not obra_ids:
        return ('sem_filho', None)
    unanime = obra_unanime(obra_ids)
    if unanime is not None:
        return ('unanime', unanime)
    if any(o is not None for o in obra_ids):
        return ('multiobra', None)
    return ('sem_obra', None)


def sincronizar_obra_do_pai(pai):
    """Recalcula `pai.obra_id` a partir dos filhos atuais.

    Chamada em toda escrita que mexe nos filhos. Não faz commit — quem
    chamou controla a transação, como `_recalcular_total_pai`
    (gestao_custos_views.py:415).

    Devolve o `obra_id` gravado (ou None).
    """
    from app import db
    from models import GestaoCustoFilho

    linhas = (db.session.query(GestaoCustoFilho.obra_id)
              .filter(GestaoCustoFilho.pai_id == pai.id)
              .all())
    _situacao, obra_id = classificar_pai([r[0] for r in linhas])
    pai.obra_id = obra_id
    return obra_id


def destino_de_filho_novo(admin_id, obra_id, centro_custo_id, origem_tabela,
                          tipo_categoria=None, criar_centro=True):
    """Resolve o destino de um lançamento NOVO. Devolve `(obra_id, centro_custo_id)`.

    Regra única e sem exceção: se não veio obra, o destino é o centro
    administrativo do tenant. Nunca devolve `(None, None)` — quando não dá
    para resolver, levanta `DestinoIndefinido`, e é isso que fecha a porta.

    `criar_centro=False` só consulta (usado por validação sem efeito).
    """
    from utils.centro_custo import id_do_centro_administrativo

    if obra_id:
        return (obra_id, centro_custo_id)

    if tipo_categoria in CATEGORIAS_QUE_EXIGEM_OBRA:
        raise DestinoIndefinido(
            f'A categoria {tipo_categoria} exige obra — "administrativo" não '
            'é resposta válida para ela.')

    if centro_custo_id:
        return (None, centro_custo_id)

    adm_id = id_do_centro_administrativo(admin_id, criar=criar_centro)
    if not adm_id:
        raise DestinoIndefinido(
            f'Tenant {admin_id} não tem centro de custo administrativo e não '
            'foi possível criá-lo. Rode a migration 251.')
    logger.debug('destino administrativo aplicado (origem=%s, tenant=%s)',
                 origem_tabela, admin_id)
    return (None, adm_id)


class DestinoIndefinido(ValueError):
    """Lançamento de custo sem obra e sem centro de custo resolvível."""
