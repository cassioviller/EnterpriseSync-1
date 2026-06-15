"""Tela 'Resultado por Atividade' da obra (espinha financeira — Fatia 1).

Mostra, por atividade do cronograma: Valor agregado, Custo incorrido (MO),
Resultado realizado, alarme de produtividade (R$) e índice em horas. Rollup por
serviço e obra. Tudo computado pelo read-model services/resultado_atividade_service.
"""
import calendar as _calendar
import logging
from datetime import date as _date

from flask import Blueprint, flash, redirect, render_template, request, url_for
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


def _parse_data_arg(arg):
    v = (request.args.get(arg) or '').strip()
    if not v:
        return None
    try:
        return _date.fromisoformat(v)
    except ValueError:
        return None


@resultado_bp.route('/obras/<int:obra_id>/caixa/')
@resultado_bp.route('/obras/<int:obra_id>/caixa')
@login_required
def caixa_obra(obra_id):
    """Lente de CAIXA da obra (Realizado/Previsto no tempo) — distinta da lente de
    competência (Resultado por Atividade). Ver DC4 / ADR 0003."""
    guard = _check_v2()
    if guard:
        return guard

    from models import Obra
    from services.caixa_obra_service import fluxo_caixa_obra

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    hoje = _date.today()
    data_inicio = _date(hoje.year, hoje.month, 1)
    data_fim = _date(hoje.year, hoje.month, _calendar.monthrange(hoje.year, hoje.month)[1])
    data_inicio = _parse_data_arg('data_inicio') or data_inicio
    data_fim = _parse_data_arg('data_fim') or data_fim

    dados = fluxo_caixa_obra(admin_id, obra_id, data_inicio, data_fim)
    return render_template(
        'resultado/caixa_obra.html',
        obra=obra, dados=dados, data_inicio=data_inicio, data_fim=data_fim,
    )
