"""
Blueprint do Módulo de Cronograma de Obras — MS Project style (V2).
Rotas JSON para CRUD de tarefas + recálculo automático de datas.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required

from models import db, Obra, TarefaCronograma, CalendarioEmpresa, RDOApontamentoCronograma
from utils.cronograma_engine import (
    recalcular_cronograma,
    verificar_ciclo,
    get_calendario,
    calcular_data_fim,
    calcular_progresso_rdo,
    atualizar_percentual_tarefa,
)

logger = logging.getLogger(__name__)

cronograma_bp = Blueprint('cronograma', __name__, url_prefix='/cronograma')


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_v2():
    """Retorna redirect/abort se o usuário não for V2."""
    from utils.tenant import is_v2_active
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


def _admin_id() -> int:
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


def _tarefa_to_dict(t: TarefaCronograma) -> dict:
    return {
        'id': t.id,
        'obra_id': t.obra_id,
        'tarefa_pai_id': t.tarefa_pai_id,
        'predecessora_id': t.predecessora_id,
        'ordem': t.ordem,
        'nome_tarefa': t.nome_tarefa,
        'duracao_dias': t.duracao_dias,
        'data_inicio': t.data_inicio.isoformat() if t.data_inicio else None,
        'data_fim': t.data_fim.isoformat() if t.data_fim else None,
        'quantidade_total': t.quantidade_total,
        'unidade_medida': t.unidade_medida,
        'percentual_concluido': t.percentual_concluido or 0.0,
    }


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICE — Lista de obras com cronograma
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/')
@login_required
def index():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    from sqlalchemy import func as sqlfunc
    # Monta sumário por obra
    resumos = []
    for obra in obras:
        total = TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=admin_id).count()
        perc_medio = (
            db.session.query(sqlfunc.avg(TarefaCronograma.percentual_concluido))
            .filter_by(obra_id=obra.id, admin_id=admin_id)
            .scalar()
        ) or 0.0
        resumos.append({
            'obra': obra,
            'total_tarefas': total,
            'perc_medio': round(float(perc_medio), 1),
            'tem_cronograma': total > 0,
        })

    cal = get_calendario(admin_id)
    return render_template(
        'cronograma/index.html',
        resumos=resumos,
        calendario=cal,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>')
@login_required
def cronograma_obra(obra_id: int):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    cal = get_calendario(admin_id)
    tarefas_dict = [_tarefa_to_dict(t) for t in tarefas]

    # Build lookup maps for rendering
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    tarefas_pred_map = {t.id: t.predecessora_id for t in tarefas}

    return render_template(
        'obras/cronograma.html',
        obra=obra,
        tarefas=tarefas,
        tarefas_dict=tarefas_dict,
        calendario=cal,
        pai_ids=pai_ids,
        tarefas_pred_map=tarefas_pred_map,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CRIAR TAREFA
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefa', methods=['POST'])
@login_required
def criar_tarefa(obra_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    data = request.get_json(silent=True) or request.form.to_dict()

    nome = (data.get('nome_tarefa') or '').strip()
    if not nome:
        return jsonify({'status': 'error', 'msg': 'Nome da tarefa é obrigatório'}), 400

    try:
        duracao = int(data.get('duracao_dias') or 1)
    except (ValueError, TypeError):
        duracao = 1

    data_inicio = _parse_date(data.get('data_inicio'))
    tarefa_pai_id = data.get('tarefa_pai_id') or None
    if tarefa_pai_id:
        tarefa_pai_id = int(tarefa_pai_id)
        # Validar que a tarefa pai existe e pertence à mesma obra/tenant
        pai = TarefaCronograma.query.filter_by(
            id=tarefa_pai_id, obra_id=obra_id, admin_id=admin_id
        ).first()
        if not pai:
            return jsonify({
                'status': 'error',
                'msg': f'Tarefa pai id={tarefa_pai_id} não encontrada nesta obra.'
            }), 400

    predecessora_id = data.get('predecessora_id') or None
    if predecessora_id:
        predecessora_id = int(predecessora_id)
        # Validar que a predecessora existe e pertence à mesma obra/tenant
        pred_check = TarefaCronograma.query.filter_by(
            id=predecessora_id, obra_id=obra_id, admin_id=admin_id
        ).first()
        if not pred_check:
            return jsonify({
                'status': 'error',
                'msg': f'Tarefa predecessora id={predecessora_id} não encontrada nesta obra.'
            }), 400
        if verificar_ciclo(0, predecessora_id, admin_id):
            return jsonify({'status': 'error', 'msg': 'Referência circular detectada'}), 400

    # Próxima ordem
    ultima = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(TarefaCronograma.ordem.desc())
        .first()
    )
    nova_ordem = (ultima.ordem + 1) if ultima else 0

    if data_inicio is None:
        if predecessora_id:
            pred = TarefaCronograma.query.get(predecessora_id)
            if pred and pred.data_fim:
                from utils.cronograma_engine import proximo_dia_util
                cal = get_calendario(admin_id)
                data_inicio = proximo_dia_util(
                    pred.data_fim, cal.considerar_sabado, cal.considerar_domingo
                )
        if data_inicio is None:
            data_inicio = date.today()

    cal = get_calendario(admin_id)
    data_fim = calcular_data_fim(
        data_inicio, duracao, cal.considerar_sabado, cal.considerar_domingo
    )

    tarefa = TarefaCronograma(
        obra_id=obra_id,
        tarefa_pai_id=tarefa_pai_id,
        predecessora_id=predecessora_id,
        ordem=nova_ordem,
        nome_tarefa=nome,
        duracao_dias=duracao,
        data_inicio=data_inicio,
        data_fim=data_fim,
        quantidade_total=float(data.get('quantidade_total') or 0) or None,
        unidade_medida=(data.get('unidade_medida') or '').strip() or None,
        percentual_concluido=0.0,
        admin_id=admin_id,
    )
    db.session.add(tarefa)
    db.session.commit()

    logger.info(f"[OK] TarefaCronograma criada id={tarefa.id} obra_id={obra_id}")
    return jsonify({'status': 'ok', 'tarefa': _tarefa_to_dict(tarefa)}), 201


# ─────────────────────────────────────────────────────────────────────────────
# ATUALIZAR TAREFA (inline edit via AJAX)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>', methods=['PUT', 'PATCH'])
@login_required
def atualizar_tarefa(obra_id: int, tarefa_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id
    ).first_or_404()

    data = request.get_json(silent=True) or {}

    if 'nome_tarefa' in data:
        nome = str(data['nome_tarefa']).strip()
        if nome:
            tarefa.nome_tarefa = nome

    if 'duracao_dias' in data:
        try:
            tarefa.duracao_dias = max(1, int(data['duracao_dias']))
        except (ValueError, TypeError):
            pass

    if 'data_inicio' in data:
        d = _parse_date(data['data_inicio'])
        if d:
            tarefa.data_inicio = d

    if 'quantidade_total' in data:
        try:
            tarefa.quantidade_total = float(data['quantidade_total']) or None
        except (ValueError, TypeError):
            tarefa.quantidade_total = None

    if 'unidade_medida' in data:
        tarefa.unidade_medida = str(data['unidade_medida']).strip() or None

    if 'percentual_concluido' in data:
        try:
            tarefa.percentual_concluido = min(100.0, max(0.0, float(data['percentual_concluido'])))
        except (ValueError, TypeError):
            pass

    if 'predecessora_id' in data:
        pred_val = data['predecessora_id']
        if pred_val in (None, '', '0', 0):
            tarefa.predecessora_id = None
        else:
            try:
                pred_id = int(pred_val)
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'msg': 'predecessora_id inválido'}), 400
            if verificar_ciclo(tarefa_id, pred_id, admin_id):
                return jsonify({
                    'status': 'error',
                    'msg': 'Referência circular: A depende de B e B depende de A'
                }), 400
            tarefa.predecessora_id = pred_id

    if 'tarefa_pai_id' in data:
        pai_val = data['tarefa_pai_id']
        tarefa.tarefa_pai_id = int(pai_val) if pai_val else None

    if 'ordem' in data:
        try:
            tarefa.ordem = int(data['ordem'])
        except (ValueError, TypeError):
            pass

    # Recalcular data_fim se data_inicio ou duração mudou
    cal = get_calendario(admin_id)
    if tarefa.data_inicio and tarefa.duracao_dias:
        tarefa.data_fim = calcular_data_fim(
            tarefa.data_inicio, tarefa.duracao_dias,
            cal.considerar_sabado, cal.considerar_domingo,
        )

    db.session.commit()
    logger.info(f"[OK] TarefaCronograma atualizada id={tarefa_id}")

    # Recálculo em cadeia: propagar mudanças para tarefas dependentes
    recalcular_cronograma(obra_id, admin_id)

    # Devolver tarefa atualizada (após recalc)
    db.session.refresh(tarefa)
    return jsonify({'status': 'ok', 'tarefa': _tarefa_to_dict(tarefa)})


# ─────────────────────────────────────────────────────────────────────────────
# EXCLUIR TAREFA
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>', methods=['DELETE'])
@login_required
def excluir_tarefa(obra_id: int, tarefa_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id
    ).first_or_404()

    # Desvincular filhas e tarefas que dependem desta como predecessora
    TarefaCronograma.query.filter_by(tarefa_pai_id=tarefa_id).update({'tarefa_pai_id': None})
    TarefaCronograma.query.filter_by(predecessora_id=tarefa_id).update({'predecessora_id': None})

    db.session.delete(tarefa)
    db.session.commit()
    logger.info(f"[OK] TarefaCronograma excluída id={tarefa_id}")
    return jsonify({'status': 'ok'})


# ─────────────────────────────────────────────────────────────────────────────
# RECALCULAR TODAS AS DATAS
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/recalcular', methods=['POST'])
@login_required
def recalcular(obra_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    ok = recalcular_cronograma(obra_id, admin_id)
    if not ok:
        return jsonify({'status': 'error', 'msg': 'Erro ao recalcular cronograma'}), 500

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(TarefaCronograma.ordem)
        .all()
    )
    return jsonify({'status': 'ok', 'tarefas': [_tarefa_to_dict(t) for t in tarefas]})


# ─────────────────────────────────────────────────────────────────────────────
# REORDENAR TAREFAS (drag & drop)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/reordenar', methods=['POST'])
@login_required
def reordenar(obra_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    admin_id = _admin_id()
    data = request.get_json(silent=True) or {}
    ordem_ids = data.get('ordem', [])  # lista de IDs na nova ordem

    for idx, tid in enumerate(ordem_ids):
        TarefaCronograma.query.filter_by(
            id=int(tid), obra_id=obra_id, admin_id=admin_id
        ).update({'ordem': idx})

    db.session.commit()
    return jsonify({'status': 'ok'})


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DO CALENDÁRIO
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/calendario', methods=['GET', 'POST'])
@login_required
def calendario():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    cal = get_calendario(admin_id)

    if request.method == 'POST':
        cal.considerar_sabado = bool(request.form.get('considerar_sabado'))
        cal.considerar_domingo = bool(request.form.get('considerar_domingo'))
        db.session.commit()

        recalcular_tudo = request.form.get('recalcular_tudo') == '1'
        if recalcular_tudo:
            obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
            for obra in obras:
                recalcular_cronograma(obra.id, admin_id)
            flash(
                f'Calendário salvo e {len(obras)} cronograma(s) recalculado(s).',
                'success',
            )
        else:
            flash('Configuração de calendário salva com sucesso.', 'success')

        return redirect(url_for('cronograma.calendario'))

    return render_template('configuracoes/calendario.html', calendario=cal)


# ─────────────────────────────────────────────────────────────────────────────
# API RDO ↔ CRONOGRAMA — Apontamento de Produção Diária
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefas-rdo')
@login_required
def tarefas_rdo(obra_id: int):
    """
    Retorna a árvore de tarefas do cronograma para apontamento em RDO.
    Query param: ?data=YYYY-MM-DD (data do RDO) e ?rdo_id=<id> (opcional)
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    data_str = request.args.get('data')
    rdo_id = request.args.get('rdo_id', type=int)

    try:
        data_rdo = date.fromisoformat(data_str) if data_str else date.today()
    except (ValueError, TypeError):
        data_rdo = date.today()

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    # Montar dict com progresso
    resultado = []
    for t in tarefas:
        progresso = calcular_progresso_rdo(t.id, data_rdo, admin_id)

        # Buscar apontamento específico deste RDO para esta tarefa (se existir)
        qty_hoje = 0.0
        apontamento_id = None
        if rdo_id:
            ap = RDOApontamentoCronograma.query.filter_by(
                rdo_id=rdo_id, tarefa_cronograma_id=t.id
            ).first()
            if ap:
                qty_hoje = ap.quantidade_executada_dia
                apontamento_id = ap.id

        resultado.append({
            'id': t.id,
            'tarefa_pai_id': t.tarefa_pai_id,
            'nome_tarefa': t.nome_tarefa,
            'duracao_dias': t.duracao_dias,
            'data_inicio': t.data_inicio.isoformat() if t.data_inicio else None,
            'data_fim': t.data_fim.isoformat() if t.data_fim else None,
            'quantidade_total': t.quantidade_total,
            'unidade_medida': t.unidade_medida or '',
            'percentual_concluido': t.percentual_concluido,
            'percentual_planejado': progresso['percentual_planejado'],
            'percentual_realizado': progresso['percentual_realizado'],
            'quantidade_acumulada': progresso['quantidade_acumulada'],
            'quantidade_executada_hoje': qty_hoje,
            'apontamento_id': apontamento_id,
        })

    return jsonify({'status': 'ok', 'tarefas': resultado})


@cronograma_bp.route('/rdo/<int:rdo_id>/apontar', methods=['POST'])
@login_required
def apontar_producao(rdo_id: int):
    """
    Salva ou atualiza a produção diária de uma tarefa do cronograma.
    Body JSON: { tarefa_cronograma_id, quantidade_executada_dia }
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    data = request.get_json(silent=True) or {}
    tarefa_id = data.get('tarefa_cronograma_id')
    qty_dia = float(data.get('quantidade_executada_dia', 0) or 0)

    if not tarefa_id:
        return jsonify({'status': 'error', 'msg': 'tarefa_cronograma_id obrigatório'}), 400

    # Verificar que o RDO pertence ao admin (isolamento multi-tenant)
    from models import RDO
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404

    tarefa = TarefaCronograma.query.filter_by(id=tarefa_id, admin_id=admin_id).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404

    # Buscar apontamento existente ou criar
    ap = RDOApontamentoCronograma.query.filter_by(
        rdo_id=rdo_id, tarefa_cronograma_id=tarefa_id
    ).first()

    if ap is None:
        ap = RDOApontamentoCronograma(
            rdo_id=rdo_id,
            tarefa_cronograma_id=tarefa_id,
            admin_id=admin_id,
        )
        db.session.add(ap)

    # Calcular acumulado ANTES deste RDO
    from sqlalchemy import func as sqlfunc
    acum_anterior = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio < rdo.data_relatorio,
        )
        .scalar()
    ) or 0.0

    nova_acumulada = acum_anterior + qty_dia

    # Calcular percentuais
    progresso = calcular_progresso_rdo(tarefa_id, rdo.data_relatorio, admin_id)

    perc_realizado = 0.0
    if tarefa.quantidade_total and tarefa.quantidade_total > 0:
        perc_realizado = min(100.0, round(nova_acumulada / tarefa.quantidade_total * 100, 2))

    ap.quantidade_executada_dia = qty_dia
    ap.quantidade_acumulada = nova_acumulada
    ap.percentual_realizado = perc_realizado
    ap.percentual_planejado = progresso['percentual_planejado']

    db.session.commit()

    # Atualizar percentual_concluido da tarefa
    atualizar_percentual_tarefa(tarefa_id, admin_id)

    return jsonify({
        'status': 'ok',
        'apontamento': {
            'id': ap.id,
            'quantidade_executada_dia': ap.quantidade_executada_dia,
            'quantidade_acumulada': ap.quantidade_acumulada,
            'percentual_realizado': ap.percentual_realizado,
            'percentual_planejado': ap.percentual_planejado,
        },
    })


@cronograma_bp.route('/rdo/<int:rdo_id>/apontamentos')
@login_required
def listar_apontamentos(rdo_id: int):
    """Retorna todos os apontamentos de um RDO com dados da tarefa."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    admin_id = _admin_id()
    aps = (
        RDOApontamentoCronograma.query
        .filter_by(rdo_id=rdo_id, admin_id=admin_id)
        .all()
    )

    resultado = []
    for ap in aps:
        t = ap.tarefa
        resultado.append({
            'id': ap.id,
            'tarefa_id': ap.tarefa_cronograma_id,
            'nome_tarefa': t.nome_tarefa if t else '—',
            'unidade_medida': t.unidade_medida if t else '',
            'quantidade_total': t.quantidade_total if t else None,
            'quantidade_executada_dia': ap.quantidade_executada_dia,
            'quantidade_acumulada': ap.quantidade_acumulada,
            'percentual_realizado': ap.percentual_realizado,
            'percentual_planejado': ap.percentual_planejado,
        })

    return jsonify({'status': 'ok', 'apontamentos': resultado})
