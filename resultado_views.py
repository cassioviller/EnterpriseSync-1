"""Tela 'Resultado por Atividade' da obra (espinha financeira — Fatia 1).

Mostra, por atividade do cronograma: Valor agregado, Custo incorrido (MO),
Resultado realizado, alarme de produtividade (R$) e índice em horas. Rollup por
serviço e obra. Tudo computado pelo read-model services/resultado_atividade_service.
"""
import logging

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

logger = logging.getLogger(__name__)

resultado_bp = Blueprint('resultado', __name__)


def _admin_id():
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


def _check_v2():
    from utils.tenant import is_v2_active
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


@resultado_bp.route('/obras/<int:obra_id>/resultado/')
@resultado_bp.route('/obras/<int:obra_id>/resultado')
@login_required
def resultado_por_atividade(obra_id):
    guard = _check_v2()
    if guard:
        return guard

    from models import Obra
    from services.resultado_atividade_service import resultado_obra, evm_obra

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    dados = resultado_obra(obra_id)
    evm = evm_obra(obra_id, admin_id)
    evm_por_tarefa = {it['tarefa_id']: it for it in evm['itens']}
    return render_template(
        'resultado/por_atividade.html',
        obra=obra, dados=dados, evm=evm, evm_por_tarefa=evm_por_tarefa,
    )
