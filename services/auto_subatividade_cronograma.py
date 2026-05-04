"""Task #62 — auto-criação de SubatividadeMestre quando uma tarefa de
cronograma é criada com um nome que não corresponde a nenhuma subatividade
existente do tenant.

Estratégia (case-insensitive trim):
  1. Busca SubatividadeMestre ativa por (admin_id, lower(nome)).
     Se achar → reutiliza, retorna o id e marca como existente.
  2. Senão cria nova com:
        tipo='subatividade', servico_id=<servico_id da tarefa>,
        criada_via_cronograma=True, precisa_revisao=True,
        ativo=True, obrigatoria=False, ordem_padrao=0.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from models import db, SubatividadeMestre

logger = logging.getLogger(__name__)


def garantir_subatividade(
    nome: str,
    admin_id: int,
    servico_id: Optional[int] = None,
) -> Tuple[Optional[SubatividadeMestre], bool]:
    """Retorna (sub, criada). criada=True quando uma nova foi instanciada."""
    if not nome:
        return None, False
    nome_norm = nome.strip()
    if not nome_norm:
        return None, False

    # Busca por (admin, tipo, lower(nome)) escopada pelo MESMO serviço para
    # evitar reuso cruzado entre serviços distintos com nomes coincidentes.
    base_q = SubatividadeMestre.query.filter(
        SubatividadeMestre.admin_id == admin_id,
        SubatividadeMestre.tipo == 'subatividade',
        db.func.lower(SubatividadeMestre.nome) == nome_norm.lower(),
    )
    if servico_id is not None:
        existente = base_q.filter(
            SubatividadeMestre.servico_id == servico_id
        ).first()
    else:
        # Sem serviço informado, só reusa se a existente também for sem serviço.
        existente = base_q.filter(
            SubatividadeMestre.servico_id.is_(None)
        ).first()
    if existente:
        return existente, False

    nova = SubatividadeMestre(
        servico_id=servico_id,
        tipo='subatividade',
        nome=nome_norm,
        ordem_padrao=0,
        obrigatoria=False,
        admin_id=admin_id,
        ativo=True,
        criada_via_cronograma=True,
        precisa_revisao=True,
    )
    db.session.add(nova)
    db.session.flush()
    logger.info(
        f"[Task#62] SubatividadeMestre auto-criada via cronograma id={nova.id} "
        f"nome='{nome_norm}' servico_id={servico_id} admin_id={admin_id}"
    )
    return nova, True
