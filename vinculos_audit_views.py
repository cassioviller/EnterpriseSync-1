"""Task #62 — página de auditoria "Vínculos a revisar".

4 abas:
  1. Subatividades a revisar (criada_via_cronograma OR precisa_revisao).
  2. Tarefas de cronograma sem servico_id (legado).
  3. RDOMaoObra com vinculo_status problemático
     (sem_funcao, funcao_fora_composicao, subatividade_sem_composicoes,
      ambiguo).
  4. Funções sem insumo equivalente (insumo_id IS NULL).

Multi-tenant: filtra TUDO por admin_id do usuário corrente.
"""
from __future__ import annotations

import logging

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from models import (
    db,
    Funcao,
    SubatividadeMestre,
    TarefaCronograma,
    RDOMaoObra,
    Funcionario,
    RDO,
    Obra,
    Servico,
)

logger = logging.getLogger(__name__)

vinculos_audit_bp = Blueprint(
    'vinculos_audit', __name__, url_prefix='/vinculos'
)


def _admin_id() -> int:
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


@vinculos_audit_bp.route('/auditoria')
@login_required
def auditoria():
    admin_id = _admin_id()

    subs_revisar = (
        SubatividadeMestre.query
        .filter(
            SubatividadeMestre.admin_id == admin_id,
            db.or_(
                SubatividadeMestre.criada_via_cronograma.is_(True),
                SubatividadeMestre.precisa_revisao.is_(True),
            ),
        )
        .order_by(SubatividadeMestre.created_at.desc())
        .all()
    )

    tarefas_sem_servico = (
        TarefaCronograma.query
        .filter(
            TarefaCronograma.admin_id == admin_id,
            TarefaCronograma.servico_id.is_(None),
        )
        .order_by(TarefaCronograma.created_at.desc())
        .all()
    )

    statuses_problema = (
        'sem_funcao',
        'funcao_fora_composicao',
        'subatividade_sem_composicoes',
        'ambiguo',
    )
    mao_obra_problema = (
        db.session.query(RDOMaoObra, Funcionario, RDO, Obra)
        .join(Funcionario, Funcionario.id == RDOMaoObra.funcionario_id)
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .join(Obra, Obra.id == RDO.obra_id)
        .filter(
            RDOMaoObra.admin_id == admin_id,
            RDOMaoObra.vinculo_status.in_(statuses_problema),
        )
        .order_by(RDO.data_relatorio.desc(), RDOMaoObra.id.desc())
        .limit(500)
        .all()
    )

    funcoes_sem_insumo = (
        Funcao.query
        .filter(
            Funcao.admin_id == admin_id,
            Funcao.insumo_id.is_(None),
        )
        .order_by(Funcao.nome)
        .all()
    )

    return render_template(
        'vinculos/auditoria.html',
        subs_revisar=subs_revisar,
        tarefas_sem_servico=tarefas_sem_servico,
        mao_obra_problema=mao_obra_problema,
        funcoes_sem_insumo=funcoes_sem_insumo,
    )


@vinculos_audit_bp.route(
    '/subatividade/<int:sub_id>/marcar-revisada', methods=['POST']
)
@login_required
def marcar_subatividade_revisada(sub_id: int):
    admin_id = _admin_id()
    sub = SubatividadeMestre.query.filter_by(
        id=sub_id, admin_id=admin_id
    ).first_or_404()
    sub.precisa_revisao = False
    sub.criada_via_cronograma = False
    db.session.commit()
    flash(f'Subatividade "{sub.nome}" marcada como revisada.', 'success')
    return redirect(url_for('vinculos_audit.auditoria'))
