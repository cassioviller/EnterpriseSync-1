"""
views/metricas_views.py — Task #3

Blueprint de Métricas de Produtividade e Lucratividade por RDO.
Telas:
  - /metricas/servico          → Empresa por Serviço
  - /metricas/funcionarios     → Cards de Funcionários
  - /metricas/funcionarios/<id>→ Detalhe do Funcionário
  - /metricas/ranking          → Ranking de Funcionários (+ CSV export)
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, timedelta

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, make_response,
)
from flask_login import login_required, current_user

from auth import admin_required
from app import db

logger = logging.getLogger(__name__)

metricas_bp = Blueprint('metricas', __name__, url_prefix='/metricas')


def _admin_id() -> int:
    return current_user.admin_id if getattr(current_user, 'admin_id', None) else current_user.id


def _parse_date(raw: str, default: date) -> date:
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return default


def _default_periodo():
    hoje = date.today()
    return hoje - timedelta(days=90), hoje


# ─────────────────────────────────────────────────────────────────────────────
# Empresa por Serviço
# ─────────────────────────────────────────────────────────────────────────────

@metricas_bp.route('/servico')
@login_required
@admin_required
def empresa_por_servico():
    admin_id = _admin_id()
    di_def, df_def = _default_periodo()

    data_inicio = _parse_date(request.args.get('data_inicio'), di_def)
    data_fim = _parse_date(request.args.get('data_fim'), df_def)
    obra_id_raw = request.args.get('obra_id', type=int)

    from models import Obra
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()

    try:
        from services.metricas_produtividade import produtividade_por_servico
        metricas = produtividade_por_servico(
            admin_id, data_inicio, data_fim, obra_id=obra_id_raw
        )
    except Exception:
        logger.exception("produtividade_por_servico falhou")
        metricas = []
        flash("Erro ao calcular métricas. Verifique os dados e tente novamente.", "danger")

    return render_template(
        'metricas/empresa_servico.html',
        metricas=metricas,
        obras=obras,
        data_inicio=data_inicio,
        data_fim=data_fim,
        obra_id_sel=obra_id_raw,
    )


@metricas_bp.route('/servico/aplicar-referencia', methods=['POST'])
@login_required
@admin_required
def aplicar_referencia():
    admin_id = _admin_id()
    servico_id = request.form.get('servico_id', type=int)
    data_inicio_raw = request.form.get('data_inicio')
    data_fim_raw = request.form.get('data_fim')
    di_def, df_def = _default_periodo()
    data_inicio = _parse_date(data_inicio_raw, di_def)
    data_fim = _parse_date(data_fim_raw, df_def)

    if not servico_id:
        flash("Serviço não identificado.", "danger")
        return redirect(url_for('metricas.empresa_por_servico'))

    try:
        from services.metricas_produtividade import aplicar_como_referencia
        resultado = aplicar_como_referencia(
            admin_id, servico_id, current_user.id, data_inicio, data_fim
        )
        if resultado['atualizados'] > 0:
            flash(
                f"Referência aplicada: {resultado['atualizados']} coeficiente(s) "
                f"atualizado(s) no catálogo.",
                "success"
            )
        else:
            flash("Nenhum coeficiente precisou ser atualizado.", "info")
    except Exception:
        logger.exception("aplicar_como_referencia falhou")
        flash("Erro ao aplicar referência. Tente novamente.", "danger")

    return redirect(url_for(
        'metricas.empresa_por_servico',
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Funcionários (cards)
# ─────────────────────────────────────────────────────────────────────────────

@metricas_bp.route('/funcionarios')
@login_required
@admin_required
def funcionarios():
    admin_id = _admin_id()
    di_def, df_def = _default_periodo()

    data_inicio = _parse_date(request.args.get('data_inicio'), di_def)
    data_fim = _parse_date(request.args.get('data_fim'), df_def)
    obra_ids_raw = request.args.getlist('obra_ids', type=int)
    funcao_ids_raw = request.args.getlist('funcao_ids', type=int)
    status_filtro = request.args.get('status', 'todos')

    from models import Obra, Funcao
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
    funcoes = Funcao.query.filter_by(admin_id=admin_id).order_by(Funcao.nome).all()

    try:
        from services.metricas_produtividade import producao_por_funcionario
        metricas = producao_por_funcionario(
            admin_id, data_inicio, data_fim,
            obra_ids=obra_ids_raw or None,
            funcao_ids=funcao_ids_raw or None,
        )
    except Exception:
        logger.exception("producao_por_funcionario falhou")
        metricas = []
        flash("Erro ao calcular métricas.", "danger")

    # Filtro de status
    if status_filtro == 'com_custo':
        metricas = [m for m in metricas if m['tem_custo']]
    elif status_filtro == 'sem_custo':
        metricas = [m for m in metricas if not m['tem_custo']]
    elif status_filtro == 'com_receita':
        metricas = [m for m in metricas if m['tem_receita']]

    return render_template(
        'metricas/funcionarios.html',
        metricas=metricas,
        obras=obras,
        funcoes=funcoes,
        data_inicio=data_inicio,
        data_fim=data_fim,
        obra_ids_sel=obra_ids_raw,
        funcao_ids_sel=funcao_ids_raw,
        status_filtro=status_filtro,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Detalhe do Funcionário
# ─────────────────────────────────────────────────────────────────────────────

@metricas_bp.route('/funcionarios/<int:funcionario_id>')
@login_required
@admin_required
def detalhe_funcionario(funcionario_id: int):
    admin_id = _admin_id()
    di_def, df_def = _default_periodo()
    data_inicio = _parse_date(request.args.get('data_inicio'), di_def)
    data_fim = _parse_date(request.args.get('data_fim'), df_def)

    from models import Funcionario
    func = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
    if not func:
        # Tenta também via tenant
        func = Funcionario.query.get(funcionario_id)
        if not func:
            abort(404)

    try:
        from services.metricas_produtividade import detalhe_funcionario as det_svc
        detalhe = det_svc(admin_id, funcionario_id, data_inicio, data_fim)
    except Exception:
        logger.exception("detalhe_funcionario falhou")
        detalhe = {'funcionario': func, 'por_servico': [], 'por_dia': [], 'diagnostico': {}}
        flash("Erro ao calcular detalhe.", "danger")

    return render_template(
        'metricas/detalhe_funcionario.html',
        func=func,
        detalhe=detalhe,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ranking
# ─────────────────────────────────────────────────────────────────────────────

@metricas_bp.route('/ranking')
@login_required
@admin_required
def ranking():
    admin_id = _admin_id()
    di_def, df_def = _default_periodo()

    data_inicio = _parse_date(request.args.get('data_inicio'), di_def)
    data_fim = _parse_date(request.args.get('data_fim'), df_def)
    obra_ids_raw = request.args.getlist('obra_ids', type=int)
    funcao_ids_raw = request.args.getlist('funcao_ids', type=int)
    servico_id_raw = request.args.get('servico_id', type=int)
    ordenar_por = request.args.get('ordenar_por', 'produtividade')
    exportar = request.args.get('exportar') == 'csv'

    from models import Obra, Funcao, Servico
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
    funcoes = Funcao.query.filter_by(admin_id=admin_id).order_by(Funcao.nome).all()
    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()

    try:
        from services.metricas_produtividade import ranking_funcionarios
        lista = ranking_funcionarios(
            admin_id, data_inicio, data_fim,
            obra_ids=obra_ids_raw or None,
            funcao_ids=funcao_ids_raw or None,
            servico_id=servico_id_raw,
            ordenar_por=ordenar_por,
        )
    except Exception:
        logger.exception("ranking_funcionarios falhou")
        lista = []
        flash("Erro ao calcular ranking.", "danger")

    if exportar:
        return _exportar_csv_ranking(lista, data_inicio, data_fim)

    return render_template(
        'metricas/ranking.html',
        lista=lista,
        obras=obras,
        funcoes=funcoes,
        servicos=servicos,
        data_inicio=data_inicio,
        data_fim=data_fim,
        obra_ids_sel=obra_ids_raw,
        funcao_ids_sel=funcao_ids_raw,
        servico_id_sel=servico_id_raw,
        ordenar_por=ordenar_por,
    )


def _exportar_csv_ranking(lista: list, data_inicio: date, data_fim: date):
    """Gera resposta CSV para o ranking."""
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow([
        'Nome', 'Função', 'Horas Normais', 'Horas Extras',
        'Dias com RDO', 'Dias Úteis', 'Assiduidade (%)',
        'Produtividade Real (un/HH)', 'Custo Total (R$)',
        'Receita Total (R$)', 'Lucro Total (R$)',
    ])
    for f in lista:
        writer.writerow([
            f['funcionario_nome'],
            f['funcao_nome'],
            f'{f["horas_normais"]:.1f}',
            f'{f["horas_extras"]:.1f}',
            f['dias_com_rdo'],
            f['dias_uteis_periodo'],
            f'{f["assiduidade_pct"]:.1f}',
            f'{f["prod_real_hh"]:.4f}' if f['prod_real_hh'] is not None else '—',
            f'{f["custo_total"]:.2f}' if f['custo_total'] is not None else '—',
            f'{f["receita_total"]:.2f}' if f['receita_total'] is not None else '—',
            f'{f["lucro_total"]:.2f}' if f['lucro_total'] is not None else '—',
        ])

    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = (
        f'attachment; filename=ranking_{data_inicio}_{data_fim}.csv'
    )
    output.headers['Content-type'] = 'text/csv; charset=utf-8'
    return output
