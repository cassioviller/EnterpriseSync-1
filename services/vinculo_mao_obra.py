"""Task #62 — Auto-vínculo Funcao→ComposicaoServico para RDOMaoObra.

Resolve, para cada linha de RDOMaoObra recém-criada, qual ComposicaoServico
(linha de mão-de-obra do serviço) deve ser anexada via
``RDOMaoObra.composicao_servico_id``. Grava também o status do vínculo em
``vinculo_status`` para auditoria posterior.

Status possíveis (em ordem de precedência decrescente):
    'manual'                          — já existe composicao_servico_id
                                          definido (alguém editou na mão).
    'auto'                            — vínculo único e determinístico.
    'ambiguo'                         — várias composições possíveis para a
                                          mesma função; primeira foi gravada,
                                          mas precisa revisão manual.
    'sem_funcao'                      — Funcionario sem ``funcao_ref`` ou
                                          Funcao sem ``insumo_id``.
    'funcao_fora_composicao'          — Função existe, mas o serviço não tem
                                          composição com aquele insumo.
    'subatividade_sem_composicoes'    — Subatividade sem nenhuma composição
                                          marcada (junção SubatividadeMaoObra
                                          vazia para o sub_mestre).

Os helpers ficam idempotentes: rodar de novo no mesmo conjunto não mexe nas
linhas já com ``vinculo_status='manual'`` e refresca o status das demais.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from sqlalchemy.orm import joinedload

from models import (
    db,
    Funcionario,
    RDOMaoObra,
    RDOServicoSubatividade,
    SubatividadeMestre,
    SubatividadeMaoObra,
    ComposicaoServico,
    TarefaCronograma,
)

logger = logging.getLogger(__name__)


def _candidatos_para_servico(
    servico_id: int,
    insumo_id: int,
    sub_mestre_id: Optional[int] = None,
) -> list[ComposicaoServico]:
    """Retorna a lista de ComposicaoServico candidatas para a (servico, insumo)
    do funcionário. Quando ``sub_mestre_id`` é fornecido E há ao menos uma
    composição vinculada à subatividade, restringe a interseção aos vínculos
    explícitos da subatividade.
    """
    q = ComposicaoServico.query.filter_by(
        servico_id=servico_id, insumo_id=insumo_id
    )
    composicoes_servico = q.all()
    if not composicoes_servico:
        return []

    if sub_mestre_id is not None:
        ids_validos = {
            link.composicao_servico_id
            for link in SubatividadeMaoObra.query.filter_by(
                subatividade_mestre_id=sub_mestre_id
            ).all()
        }
        # Subatividade DEVE ter vínculos explícitos. Sem links → o chamador
        # marca 'subatividade_sem_composicoes' (não há fallback automático).
        if not ids_validos:
            return []
        return [c for c in composicoes_servico if c.id in ids_validos]

    return composicoes_servico


def resolver_vinculo(linha: RDOMaoObra) -> tuple[Optional[int], str]:
    """Resolve a composicao_servico_id e o status para 1 linha de RDOMaoObra.

    Retorna ``(composicao_servico_id|None, status)``. Não persiste nada — o
    chamador grava no model e faz commit.
    """
    # Manual: já tem composição setada explicitamente — não mexe.
    if linha.composicao_servico_id and linha.vinculo_status == 'manual':
        return linha.composicao_servico_id, 'manual'

    funcionario = linha.funcionario or Funcionario.query.get(linha.funcionario_id)
    funcao = getattr(funcionario, 'funcao_ref', None) if funcionario else None
    if not funcao or not getattr(funcao, 'insumo_id', None):
        return None, 'sem_funcao'

    # Descobrir servico_id (e sub_mestre_id se houver) a partir do contexto
    servico_id: Optional[int] = None
    sub_mestre_id: Optional[int] = None

    if linha.subatividade_id:
        sub_rdo: Optional[RDOServicoSubatividade] = (
            RDOServicoSubatividade.query.get(linha.subatividade_id)
        )
        if sub_rdo:
            servico_id = sub_rdo.servico_id
            sub_mestre_id = sub_rdo.subatividade_mestre_id
    elif linha.tarefa_cronograma_id:
        tarefa: Optional[TarefaCronograma] = (
            TarefaCronograma.query.get(linha.tarefa_cronograma_id)
        )
        if tarefa:
            servico_id = tarefa.servico_id
            sub_mestre_id = tarefa.subatividade_mestre_id

    if not servico_id:
        return None, 'sem_funcao'

    # Filtrar candidatas pela subatividade quando aplicável
    candidatas = _candidatos_para_servico(servico_id, funcao.insumo_id, sub_mestre_id)
    if not candidatas:
        # Distinguir cenários: subatividade sem links vs função fora da composição.
        if sub_mestre_id is not None:
            tem_links = SubatividadeMaoObra.query.filter_by(
                subatividade_mestre_id=sub_mestre_id
            ).first()
            if not tem_links:
                # Sub sem nenhum link N:N → pendência específica para audit.
                return None, 'subatividade_sem_composicoes'
        return None, 'funcao_fora_composicao'

    if len(candidatas) == 1:
        return candidatas[0].id, 'auto'

    # Múltiplas candidatas → ambíguo, NÃO grava id (gestor decide).
    return None, 'ambiguo'


def aplicar_vinculo_em_linhas(linhas: Iterable[RDOMaoObra]) -> dict[str, int]:
    """Aplica resolver_vinculo nas linhas e grava in-place. Retorna contadores.

    Não faz commit — assume que a transação externa fará. Linhas com
    ``vinculo_status='manual'`` permanecem intocadas.
    """
    counts = {
        'auto': 0, 'manual': 0, 'ambiguo': 0,
        'sem_funcao': 0, 'funcao_fora_composicao': 0,
        'subatividade_sem_composicoes': 0,
    }
    for linha in linhas:
        if linha.vinculo_status == 'manual' and linha.composicao_servico_id:
            counts['manual'] += 1
            continue
        comp_id, status = resolver_vinculo(linha)
        linha.composicao_servico_id = comp_id
        linha.vinculo_status = status
        counts[status] = counts.get(status, 0) + 1
    return counts


def aplicar_vinculo_no_rdo(rdo_id: int) -> dict[str, int]:
    """Resolve composição para todas as linhas RDOMaoObra de um RDO."""
    linhas = (
        RDOMaoObra.query
        .options(joinedload(RDOMaoObra.funcionario))
        .filter_by(rdo_id=rdo_id)
        .all()
    )
    counts = aplicar_vinculo_em_linhas(linhas)
    logger.info(
        f"[Task#62] vinculo MO RDO {rdo_id}: {counts}"
    )
    return counts


def install_auto_link_listener() -> None:
    """Task #62 — instala um listener SQLAlchemy ``before_flush`` que aplica
    o auto-vínculo a TODA RDOMaoObra recém-criada (qualquer rota de
    salvamento de RDO: V1/V2/edição/duplicação) sem que cada caller precise
    chamar manualmente.

    Idempotente: só aplica se ``vinculo_status is None`` (linha nova ou
    legado retroativo). Não toca em linhas com status='manual'.
    """
    from sqlalchemy import event

    @event.listens_for(db.session, 'before_flush')
    def _before_flush(session, _flush_ctx, _instances):
        for obj in list(session.new) + list(session.dirty):
            if not isinstance(obj, RDOMaoObra):
                continue
            if obj.vinculo_status:
                continue
            try:
                comp_id, status = resolver_vinculo(obj)
                obj.composicao_servico_id = comp_id
                obj.vinculo_status = status
            except Exception as e:
                logger.warning(
                    f"[Task#62] auto-link listener falhou (linha {obj!r}): {e}"
                )
