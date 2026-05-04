"""
services/orcamento_operacional.py — Task #63

Orçamento Operacional da Obra: cópia editável separada do orçamento de
contrato. Métricas/RDO leem SEMPRE daqui (versão vigente na data do RDO).
Edições no orçamento original (OrcamentoItem) NÃO afetam o operacional.

Modelo de versionamento:
- Cada `ObraOrcamentoOperacionalItem` tem 1..N versões (composicao_snapshot
  + margem + imposto), com janela [vigente_de, vigente_ate). A versão "atual"
  tem `vigente_ate = NULL`.
- Edição "a_partir_de_hoje" fecha a vigente (vigente_ate=now) e abre uma
  nova (vigente_de=now, vigente_ate=NULL). RDOs antigos continuam lendo a
  versão fechada.
- Edição "retroativo" atualiza in-place a vigente; o evento fica registrado
  no histórico com modo='retroativo' (audit-only — não cria nova linha).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app import db
from models import (
    Obra, Orcamento, OrcamentoItem, Proposta, RDO,
    ObraOrcamentoOperacional, ObraOrcamentoOperacionalItem,
    ObraOrcamentoOperacionalItemVersao,
)

logger = logging.getLogger(__name__)


def _orcamento_da_obra(obra: Obra) -> Optional[Orcamento]:
    """Resolve o Orçamento original da obra via Proposta de origem."""
    if not obra.proposta_origem_id:
        return None
    proposta = Proposta.query.get(obra.proposta_origem_id)
    if not proposta or not proposta.orcamento_id:
        return None
    return Orcamento.query.get(proposta.orcamento_id)


def _data_inicial_vigencia(obra: Obra) -> datetime:
    """Data base da 1ª versão: data do 1º RDO (preferida) ou data_inicio da obra."""
    primeiro = (
        RDO.query.filter_by(obra_id=obra.id)
        .order_by(RDO.data_relatorio.asc())
        .first()
    )
    if primeiro and primeiro.data_relatorio:
        return datetime.combine(primeiro.data_relatorio, datetime.min.time())
    if obra.data_inicio:
        return datetime.combine(obra.data_inicio, datetime.min.time())
    return datetime.utcnow()


def garantir_operacional(obra_id: int, criado_por_id: Optional[int] = None) -> ObraOrcamentoOperacional:
    """Garante que a obra tem um Orçamento Operacional clonado.

    Idempotente: se já existe, devolve o existente sem alterar nada.
    Se a obra não tem orçamento original aprovado, cria operacional VAZIO
    (preenchido manualmente depois) — não bloqueia o fluxo de RDO.
    """
    op = ObraOrcamentoOperacional.query.filter_by(obra_id=obra_id).first()
    if op:
        return op

    obra = Obra.query.get(obra_id)
    if not obra:
        raise ValueError(f"Obra {obra_id} não encontrada")

    orc = _orcamento_da_obra(obra)
    op = ObraOrcamentoOperacional(
        obra_id=obra.id,
        admin_id=obra.admin_id,
        orcamento_origem_id=orc.id if orc else None,
        criado_por_id=criado_por_id,
    )
    db.session.add(op)
    db.session.flush()  # garante op.id

    if orc and orc.itens:
        vigente_de = _data_inicial_vigencia(obra)
        for it in orc.itens:
            novo = ObraOrcamentoOperacionalItem(
                operacional_id=op.id,
                admin_id=obra.admin_id,
                orcamento_item_origem_id=it.id,
                servico_id=it.servico_id,
                quantidade=it.quantidade,
                unidade=it.unidade,
                descricao=it.descricao,
            )
            db.session.add(novo)
            db.session.flush()
            ver = ObraOrcamentoOperacionalItemVersao(
                item_id=novo.id,
                admin_id=obra.admin_id,
                composicao_snapshot=it.composicao_snapshot or [],
                margem_pct=it.margem_pct,
                imposto_pct=it.imposto_pct,
                vigente_de=vigente_de,
                vigente_ate=None,
                criado_por_id=criado_por_id,
                motivo='Clonagem inicial do orçamento original',
                modo_aplicacao='clonagem_inicial',
            )
            db.session.add(ver)

    db.session.commit()
    logger.info(
        "[orcamento_operacional] criado obra=%s itens=%s origem_orc=%s",
        obra_id, len(orc.itens) if orc else 0, orc.id if orc else None,
    )
    return op


def obter_operacional_vigente(obra_id: int, item_id: int, data_referencia: datetime) -> Optional[dict]:
    """Devolve a versão do item operacional vigente em `data_referencia`.

    Critério: vigente_de <= data_referencia AND (vigente_ate IS NULL OR data_referencia < vigente_ate).
    Se não houver versão dentro da janela, devolve a 1ª versão criada (defesa).
    """
    item = ObraOrcamentoOperacionalItem.query.get(item_id)
    if not item:
        return None
    op = ObraOrcamentoOperacional.query.get(item.operacional_id)
    if not op or op.obra_id != obra_id:
        return None

    versao = (
        ObraOrcamentoOperacionalItemVersao.query
        .filter(
            ObraOrcamentoOperacionalItemVersao.item_id == item_id,
            ObraOrcamentoOperacionalItemVersao.vigente_de <= data_referencia,
            db.or_(
                ObraOrcamentoOperacionalItemVersao.vigente_ate.is_(None),
                ObraOrcamentoOperacionalItemVersao.vigente_ate > data_referencia,
            ),
        )
        # Tie-break determinístico: vigente_de DESC, depois id DESC (versão
        # mais nova ganha em caso de empate — evita ambiguidade pós-retroativo).
        .order_by(ObraOrcamentoOperacionalItemVersao.vigente_de.desc(),
                  ObraOrcamentoOperacionalItemVersao.id.desc())
        .first()
    )
    if not versao:
        # Fallback: data anterior à 1ª versão → devolve a 1ª (pra evitar None
        # quando o RDO é, por algum motivo, anterior à data_inicio da obra).
        versao = (
            ObraOrcamentoOperacionalItemVersao.query
            .filter_by(item_id=item_id)
            .order_by(ObraOrcamentoOperacionalItemVersao.vigente_de.asc(),
                      ObraOrcamentoOperacionalItemVersao.id.asc())
            .first()
        )
    if not versao:
        return None
    return {
        'versao_id': versao.id,
        'composicao': versao.composicao_snapshot or [],
        'margem_pct': float(versao.margem_pct) if versao.margem_pct is not None else None,
        'imposto_pct': float(versao.imposto_pct) if versao.imposto_pct is not None else None,
        'vigente_de': versao.vigente_de,
        'vigente_ate': versao.vigente_ate,
    }


def listar_versoes(item_id: int) -> list:
    """Lista todas as versões do item operacional, mais recente primeiro."""
    versoes = (
        ObraOrcamentoOperacionalItemVersao.query
        .filter_by(item_id=item_id)
        .order_by(ObraOrcamentoOperacionalItemVersao.vigente_de.desc(),
                  ObraOrcamentoOperacionalItemVersao.id.desc())
        .all()
    )
    return versoes


def editar_item(
    item_id: int,
    nova_composicao: list,
    nova_margem_pct: Optional[float],
    novo_imposto_pct: Optional[float],
    modo: str,
    criado_por_id: Optional[int] = None,
    motivo: Optional[str] = None,
) -> ObraOrcamentoOperacionalItemVersao:
    """Aplica edição em um item operacional segundo `modo`.

    - modo='a_partir_de_hoje': fecha vigente atual com vigente_ate=now() e
      cria nova com vigente_de=now(), vigente_ate=NULL. RDOs anteriores
      mantêm os valores que tinham (apontam pra versão fechada via janela).
    - modo='retroativo': atualiza in-place a versão vigente atual; cria
      ADICIONALMENTE uma linha de auditoria (vigente_de=NULL, vigente_ate=
      now(), modo='retroativo') só pra rastreabilidade.

    Devolve a versão "ativa" resultante (a vigente atual após a edição).
    """
    if modo not in ('a_partir_de_hoje', 'retroativo'):
        raise ValueError(f"modo inválido: {modo!r}")

    item = ObraOrcamentoOperacionalItem.query.get(item_id)
    if not item:
        raise ValueError(f"Item operacional {item_id} não encontrado")

    vigente = (
        ObraOrcamentoOperacionalItemVersao.query
        .filter_by(item_id=item_id, vigente_ate=None)
        .order_by(ObraOrcamentoOperacionalItemVersao.vigente_de.desc())
        .first()
    )
    agora = datetime.utcnow()

    if modo == 'a_partir_de_hoje':
        if vigente:
            vigente.vigente_ate = agora
        nova = ObraOrcamentoOperacionalItemVersao(
            item_id=item_id,
            admin_id=item.admin_id,
            composicao_snapshot=nova_composicao or [],
            margem_pct=nova_margem_pct,
            imposto_pct=novo_imposto_pct,
            vigente_de=agora,
            vigente_ate=None,
            criado_por_id=criado_por_id,
            motivo=motivo,
            modo_aplicacao='a_partir_de_hoje',
        )
        db.session.add(nova)
        db.session.commit()
        logger.info(
            "[orcamento_operacional] item=%s editado A_PARTIR_DE_HOJE versao_nova=%s",
            item_id, nova.id,
        )
        return nova

    # modo == 'retroativo'
    if not vigente:
        # Sem vigente: comporta-se como criação inicial
        vigente = ObraOrcamentoOperacionalItemVersao(
            item_id=item_id,
            admin_id=item.admin_id,
            composicao_snapshot=nova_composicao or [],
            margem_pct=nova_margem_pct,
            imposto_pct=novo_imposto_pct,
            vigente_de=agora,
            vigente_ate=None,
            criado_por_id=criado_por_id,
            motivo=motivo,
            modo_aplicacao='retroativo',
        )
        db.session.add(vigente)
        db.session.commit()
        return vigente

    # Update in-place + linha de auditoria
    vigente.composicao_snapshot = nova_composicao or []
    vigente.margem_pct = nova_margem_pct
    vigente.imposto_pct = novo_imposto_pct
    auditoria = ObraOrcamentoOperacionalItemVersao(
        item_id=item_id,
        admin_id=item.admin_id,
        composicao_snapshot=nova_composicao or [],
        margem_pct=nova_margem_pct,
        imposto_pct=novo_imposto_pct,
        vigente_de=vigente.vigente_de,
        vigente_ate=agora,  # marcador: registro de auditoria, não janela ativa
        criado_por_id=criado_por_id,
        motivo=motivo,
        modo_aplicacao='retroativo',
    )
    db.session.add(auditoria)
    db.session.commit()
    logger.info(
        "[orcamento_operacional] item=%s editado RETROATIVO (in-place) auditoria=%s",
        item_id, auditoria.id,
    )
    return vigente


def diff_com_original(obra_id: int) -> list:
    """Compara cada item operacional com seu OrcamentoItem de origem.

    Devolve lista de dicts com itens onde diverge:
        {'item_id', 'descricao', 'mudancas': [...]}.
    Útil pro botão "Atualizar do orçamento original" (mostra diff antes de
    aplicar).
    """
    op = ObraOrcamentoOperacional.query.filter_by(obra_id=obra_id).first()
    if not op:
        return []
    diffs = []
    for item in op.itens:
        if not item.orcamento_item_origem_id:
            continue
        origem = OrcamentoItem.query.get(item.orcamento_item_origem_id)
        if not origem:
            continue
        vig = (
            ObraOrcamentoOperacionalItemVersao.query
            .filter_by(item_id=item.id, vigente_ate=None)
            .order_by(ObraOrcamentoOperacionalItemVersao.vigente_de.desc())
            .first()
        )
        if not vig:
            continue
        mudancas = []
        # margem
        m_op = float(vig.margem_pct) if vig.margem_pct is not None else None
        m_or = float(origem.margem_pct) if origem.margem_pct is not None else None
        if m_op != m_or:
            mudancas.append(('margem_pct', m_op, m_or))
        # imposto
        i_op = float(vig.imposto_pct) if vig.imposto_pct is not None else None
        i_or = float(origem.imposto_pct) if origem.imposto_pct is not None else None
        if i_op != i_or:
            mudancas.append(('imposto_pct', i_op, i_or))
        # composicao (compara coeficiente + preco_unitario por insumo_id|nome)
        comp_op = vig.composicao_snapshot or []
        comp_or = origem.composicao_snapshot or []
        def _key(linha):
            return (linha.get('insumo_id'), linha.get('nome') or '')
        map_op = {_key(l): l for l in comp_op}
        map_or = {_key(l): l for l in comp_or}
        for k, lin_or in map_or.items():
            lin_op = map_op.get(k)
            if not lin_op:
                mudancas.append(('insumo_novo', None, lin_or.get('nome')))
                continue
            if float(lin_op.get('coeficiente') or 0) != float(lin_or.get('coeficiente') or 0):
                mudancas.append((
                    f"coef:{lin_or.get('nome')}",
                    float(lin_op.get('coeficiente') or 0),
                    float(lin_or.get('coeficiente') or 0),
                ))
            if float(lin_op.get('preco_unitario') or 0) != float(lin_or.get('preco_unitario') or 0):
                mudancas.append((
                    f"preco:{lin_or.get('nome')}",
                    float(lin_op.get('preco_unitario') or 0),
                    float(lin_or.get('preco_unitario') or 0),
                ))
        for k, lin_op in map_op.items():
            if k not in map_or:
                mudancas.append(('insumo_removido_do_original', lin_op.get('nome'), None))
        if mudancas:
            diffs.append({
                'item_id': item.id,
                'descricao': item.descricao,
                'mudancas': mudancas,
            })
    return diffs


def atualizar_do_original(
    obra_id: int,
    item_ids: Optional[list] = None,
    criado_por_id: Optional[int] = None,
) -> int:
    """Propaga mudanças do orçamento original para o operacional.

    Aplica como "a_partir_de_hoje" (preserva histórico). Sempre filtra
    pelos itens que efetivamente divergem do original (via diff_com_original).
    Se `item_ids` é fornecido, restringe ainda mais à interseção desse set
    com os divergentes (lista vazia → 0 atualizações). Se `item_ids=None`,
    propaga todos os divergentes. Retorna nº de itens propagados.
    """
    op = ObraOrcamentoOperacional.query.filter_by(obra_id=obra_id).first()
    if not op:
        return 0
    # Por padrão, só propaga itens que de fato divergem do original.
    # `item_ids` explícito (UI) restringe ainda mais. Lista vazia → nada.
    diff_ids = {d['item_id'] for d in diff_com_original(obra_id)}
    if item_ids is not None:
        alvo_ids = set(item_ids) & diff_ids  # interseção: subset com mudança
    else:
        alvo_ids = diff_ids
    if not alvo_ids:
        return 0
    n = 0
    for item in op.itens:
        if item.id not in alvo_ids:
            continue
        if not item.orcamento_item_origem_id:
            continue
        origem = OrcamentoItem.query.get(item.orcamento_item_origem_id)
        if not origem:
            continue
        editar_item(
            item_id=item.id,
            nova_composicao=origem.composicao_snapshot or [],
            nova_margem_pct=float(origem.margem_pct) if origem.margem_pct is not None else None,
            novo_imposto_pct=float(origem.imposto_pct) if origem.imposto_pct is not None else None,
            modo='a_partir_de_hoje',
            criado_por_id=criado_por_id,
            motivo='Atualização puxada do orçamento original',
        )
        n += 1
    return n
