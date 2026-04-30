"""
Task #42 — CRM de Leads.

Helpers de seed das listas mestras genéricas (sem nomes próprios).
Usado pela migração 146 (popula listas de admins existentes uma única
vez) e pelo fluxo de criação de novo admin (chamado em ``seed_listas_mestras_crm``
para que cada admin novo já comece com os valores padrão).

A lista de **Responsáveis** NÃO recebe seed — cada admin cadastra o time
dele.
"""
from __future__ import annotations

import logging
from typing import Iterable, Tuple

from app import db
from models import (
    CrmOrigem,
    CrmCadencia,
    CrmSituacao,
    CrmTipoMaterial,
    CrmTipoObra,
    CrmMotivoPerda,
)

logger = logging.getLogger(__name__)


CRM_SEED_GENERICO: dict[str, list[str]] = {
    'origem': [
        'Loja', 'Indicação', 'Anúncio Meta Ads', 'Google',
        'Site', 'Prospecção Ativa',
    ],
    'cadencia': [
        'Contato Dia 1', 'Contato Dia 3', 'Contato Dia 7', 'Contato Dia 15',
    ],
    'situacao': [
        'Levantar Necessidade', 'Em Negociação', 'Orçamento Enviado',
        'Fechamento', 'Sem Retorno',
    ],
    'tipo_material': [
        'Drywall', 'Steel Frame', 'Material', 'Serviço',
        'Obra Completa', 'Forros Removíveis', 'Projeto', 'Outros',
    ],
    'tipo_obra': [
        'Residencial', 'Empresarial', 'Empreendimento',
    ],
    'motivo_perda': [
        'Sem Retorno', 'Preço do Produto', 'Desistência de Compra',
        'Valor acima', 'Contato Agendado', 'Outros',
    ],
}


_MODELS_BY_LISTA = {
    'origem': CrmOrigem,
    'cadencia': CrmCadencia,
    'situacao': CrmSituacao,
    'tipo_material': CrmTipoMaterial,
    'tipo_obra': CrmTipoObra,
    'motivo_perda': CrmMotivoPerda,
}


def _semear_lista(model, admin_id: int, valores: Iterable[str]) -> int:
    """Insere os valores que ainda não existem para o admin.

    Idempotente — se o admin já tiver UMA linha qualquer (mesmo que
    diferente da lista padrão), assume-se que ele já personalizou e
    NÃO inserimos mais nada para evitar reaparecer item que ele
    apagou. Retorna o número de linhas efetivamente inseridas."""
    existe_algum = (
        db.session.query(model.id).filter_by(admin_id=admin_id).first()
        is not None
    )
    if existe_algum:
        return 0
    inseridos = 0
    for nome in valores:
        nome = (nome or '').strip()
        if not nome:
            continue
        db.session.add(model(admin_id=admin_id, nome=nome, ativo=True))
        inseridos += 1
    return inseridos


def seed_listas_mestras_crm(admin_id: int, commit: bool = True) -> dict[str, int]:
    """Popula as listas mestras genéricas para um admin.

    NÃO popula `crm_responsavel` — cada admin cadastra o próprio time.
    Retorna dict {lista: qtd_inserida}. Idempotente por lista (não
    duplica se o admin já tiver dados naquela lista).
    """
    inseridos: dict[str, int] = {}
    for lista, valores in CRM_SEED_GENERICO.items():
        model = _MODELS_BY_LISTA[lista]
        inseridos[lista] = _semear_lista(model, admin_id, valores)
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return inseridos


def seed_listas_mestras_para_todos_admins() -> Tuple[int, int]:
    """Para cada admin existente, garante o seed das listas genéricas.

    Retorna (n_admins_processados, n_total_linhas_inseridas).
    """
    from models import Usuario, TipoUsuario
    admins = (
        Usuario.query
        .filter(Usuario.tipo_usuario == TipoUsuario.ADMIN)
        .all()
    )
    total_linhas = 0
    for admin in admins:
        inseridos = seed_listas_mestras_crm(admin.id, commit=False)
        total_linhas += sum(inseridos.values())
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return (len(admins), total_linhas)
