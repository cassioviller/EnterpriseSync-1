"""
Blueprint do Módulo de Cronograma de Obras — MS Project style (V2).
Rotas JSON para CRUD de tarefas + recálculo automático de datas.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_file, url_for, flash
from flask_login import current_user, login_required

from models import (
    db, Obra, TarefaCronograma, CalendarioEmpresa, RDOApontamentoCronograma,
    CronogramaTemplate, CronogramaTemplateItem, SubatividadeMestre, Servico,
    RDO, RDOMaoObra, RDOServicoSubatividade, Funcionario,
    ComposicaoServico, SubatividadeMaoObra,
)
from utils.cronograma_engine import (
    recalcular_cronograma,
    verificar_ciclo,
    get_calendario,
    calcular_data_fim,
    calcular_progresso_rdo,
    atualizar_percentual_tarefa,
    sincronizar_percentuais_obra,
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


def _tarefa_to_dict(t: TarefaCronograma, percentual_planejado: float = 0.0) -> dict:
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
        'subatividade_mestre_id': getattr(t, 'subatividade_mestre_id', None),
        'percentual_concluido': t.percentual_concluido or 0.0,
        'percentual_planejado': round(percentual_planejado, 1),
        'responsavel': getattr(t, 'responsavel', 'empresa') or 'empresa',
        # Task #102: marcador para o front exibir aviso ao editar/excluir tarefas
        # geradas automaticamente pela aprovação de proposta.
        'gerada_por_proposta_item_id': getattr(t, 'gerada_por_proposta_item_id', None),
    }


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _modo_cliente() -> bool:
    """
    Retorna True quando a operação está no modo "cronograma do cliente".
    Acionado por ?cliente=1 (querystring) OU pelo campo cliente=1 no body
    (form/JSON). Em modo cliente, todas as queries operam apenas sobre
    TarefaCronograma com is_cliente=True; o plano interno fica intocado.
    """
    val = request.values.get('cliente')
    if val is None:
        try:
            payload = request.get_json(silent=True) or {}
            val = payload.get('cliente')
        except Exception:
            val = None
    return str(val or '').strip() in ('1', 'true', 'True', 'on')


def _qs_cliente(cliente: bool) -> str:
    """Sufixo de querystring para preservar o modo entre redirects/links."""
    return '?cliente=1' if cliente else ''


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
    cliente_mode = _modo_cliente()

    # Sincroniza percentual_concluido com o último apontamento do RDO antes de exibir
    # (No modo cliente, sincroniza apenas o bottom-up dos pais; RDO não toca tarefas-cliente)
    sincronizar_percentuais_obra(obra_id, admin_id, cliente=cliente_mode)

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    cal = get_calendario(admin_id)

    # Calcula progresso planejado de hoje para cada tarefa
    hoje = date.today()
    tarefas_dict = []
    planejados_map: dict[int, float] = {}
    for t in tarefas:
        prog = calcular_progresso_rdo(t.id, hoje, admin_id)
        planejado = prog['percentual_planejado']
        planejados_map[t.id] = planejado
        tarefas_dict.append(_tarefa_to_dict(t, planejado))

    # Build lookup maps for rendering
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    tarefas_pred_map = {t.id: t.predecessora_id for t in tarefas}

    # Nome da empresa para o campo "Responsável"
    from models import ConfiguracaoEmpresa
    config_empresa = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config_empresa.nome_empresa if config_empresa else 'Empresa'

    return render_template(
        'obras/cronograma.html',
        obra=obra,
        tarefas=tarefas,
        tarefas_dict=tarefas_dict,
        calendario=cal,
        pai_ids=pai_ids,
        tarefas_pred_map=tarefas_pred_map,
        planejados_map=planejados_map,
        hoje=hoje,
        nome_empresa=nome_empresa,
        modo_cliente=cliente_mode,
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
    cliente_mode = _modo_cliente()

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
        # Validar que a tarefa pai existe e pertence à mesma obra/tenant/modo
        pai = TarefaCronograma.query.filter_by(
            id=tarefa_pai_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
        ).first()
        if not pai:
            return jsonify({
                'status': 'error',
                'msg': f'Tarefa pai id={tarefa_pai_id} não encontrada nesta obra.'
            }), 400

    predecessora_id = data.get('predecessora_id') or None
    if predecessora_id:
        predecessora_id = int(predecessora_id)
        # Validar que a predecessora existe e pertence à mesma obra/tenant/modo
        pred_check = TarefaCronograma.query.filter_by(
            id=predecessora_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
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
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
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

    responsavel = (data.get('responsavel') or 'empresa').strip().lower()
    if responsavel not in ('empresa', 'terceiros', 'subempreitada'):
        responsavel = 'empresa'

    sub_mestre_id = data.get('subatividade_mestre_id')
    try:
        sub_mestre_id = int(sub_mestre_id) if sub_mestre_id else None
    except (ValueError, TypeError):
        sub_mestre_id = None
    if sub_mestre_id is not None:
        sub_obj = SubatividadeMestre.query.filter_by(
            id=sub_mestre_id, admin_id=admin_id, ativo=True
        ).first()
        if sub_obj is None:
            sub_mestre_id = None

    # Task #62 — servico_id é obrigatório a partir de v9. Aceita id explícito;
    # senão tenta resolver pelo nome da tarefa (case-insensitive). Se nada
    # bater, devolve 400 para a UI exigir.
    raw_servico_id = data.get('servico_id')
    servico_id = None
    try:
        servico_id = int(raw_servico_id) if raw_servico_id else None
    except (ValueError, TypeError):
        servico_id = None
    if servico_id is not None:
        svc = Servico.query.filter_by(
            id=servico_id, admin_id=admin_id, ativo=True
        ).first()
        if not svc:
            servico_id = None
    if servico_id is None:
        # Fallback por nome (caso template/seed antigos)
        svc_nome = (data.get('servico_nome') or '').strip()
        if svc_nome:
            svc = (
                Servico.query
                .filter(
                    Servico.admin_id == admin_id,
                    Servico.ativo.is_(True),
                    db.func.lower(Servico.nome) == svc_nome.lower(),
                )
                .first()
            )
            if svc:
                servico_id = svc.id
    if servico_id is None:
        return jsonify({
            'status': 'error',
            'msg': 'Serviço é obrigatório. Selecione um serviço para a tarefa.',
        }), 400

    # Task #62 — auto-criação de SubatividadeMestre por nome quando não veio explícito
    if sub_mestre_id is None:
        try:
            from services.auto_subatividade_cronograma import garantir_subatividade
            sub_obj, _criada = garantir_subatividade(nome, admin_id, servico_id)
            if sub_obj is not None:
                sub_mestre_id = sub_obj.id
        except Exception as _e_sub:
            logger.warning(f"[Task#62] auto-subatividade falhou: {_e_sub}")
    else:
        # Task #62 — consistência: tarefa.servico_id deve bater com a sub.servico_id
        sub_existente = SubatividadeMestre.query.filter_by(
            id=sub_mestre_id, admin_id=admin_id
        ).first()
        if sub_existente and sub_existente.servico_id and sub_existente.servico_id != servico_id:
            return jsonify({
                'status': 'error',
                'msg': (
                    f'Inconsistência: a subatividade pertence ao serviço '
                    f'#{sub_existente.servico_id}, mas a tarefa foi enviada com serviço #{servico_id}.'
                ),
            }), 400

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
        subatividade_mestre_id=sub_mestre_id,
        servico_id=servico_id,
        percentual_concluido=0.0,
        responsavel=responsavel,
        admin_id=admin_id,
        is_cliente=cliente_mode,
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
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
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

    if 'subatividade_mestre_id' in data:
        try:
            val = data['subatividade_mestre_id']
            parsed_id = int(val) if val else None
        except (ValueError, TypeError):
            parsed_id = None
        if parsed_id is not None:
            sub_obj = SubatividadeMestre.query.filter_by(
                id=parsed_id, admin_id=admin_id, ativo=True
            ).first()
            tarefa.subatividade_mestre_id = sub_obj.id if sub_obj else None
        else:
            tarefa.subatividade_mestre_id = None

    if 'responsavel' in data:
        resp = str(data['responsavel']).strip().lower()
        if resp in ('empresa', 'terceiros', 'subempreitada'):
            tarefa.responsavel = resp

    if 'percentual_concluido' in data:
        try:
            tarefa.percentual_concluido = min(100.0, max(0.0, float(data['percentual_concluido'])))
        except (ValueError, TypeError):
            pass
        # Auto-sync data_entrega_real para tarefas de terceiros
        if (tarefa.responsavel or '').lower() == 'terceiros':
            from datetime import date as _date_today
            if tarefa.percentual_concluido >= 100.0 and not tarefa.data_entrega_real:
                tarefa.data_entrega_real = _date_today.today()
            elif tarefa.percentual_concluido < 100.0:
                tarefa.data_entrega_real = None

    if 'data_entrega_real' in data:
        d = _parse_date(data['data_entrega_real']) if data.get('data_entrega_real') else None
        tarefa.data_entrega_real = d

    if 'predecessora_id' in data:
        pred_val = data['predecessora_id']
        if pred_val in (None, '', '0', 0):
            tarefa.predecessora_id = None
        else:
            try:
                pred_id = int(pred_val)
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'msg': 'predecessora_id inválido'}), 400
            # Validar existência e pertencimento à obra/modo (igual a criar_tarefa)
            pred_tarefa = TarefaCronograma.query.filter_by(
                id=pred_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
            ).first()
            if not pred_tarefa:
                return jsonify({
                    'status': 'error',
                    'msg': f'Tarefa predecessora id={pred_id} não encontrada nesta obra.'
                }), 400
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

    # Recálculo em cadeia apenas quando campos de agendamento foram alterados.
    # Se percentual_concluido foi passado explicitamente, reaplicar APÓS o recálculo
    # (recalcular_cronograma chama atualizar_percentual_tarefa que pode sobrescrevê-lo).
    _SCHEDULING_FIELDS = {'duracao_dias', 'predecessora_id', 'data_inicio'}
    perc_manual = None
    if 'percentual_concluido' in data:
        try:
            perc_manual = min(100.0, max(0.0, float(data['percentual_concluido'])))
        except (ValueError, TypeError):
            pass

    if _SCHEDULING_FIELDS & set(data.keys()):
        recalcular_cronograma(obra_id, admin_id, cliente=cliente_mode)
        # Re-aplicar o percentual manual caso o recálculo tenha sobrescrito
        if perc_manual is not None:
            tarefa.percentual_concluido = perc_manual
            db.session.commit()

    # Devolver tarefa atualizada + lista completa após recalc para redesenho do Gantt
    db.session.refresh(tarefa)
    todas = TarefaCronograma.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).order_by(TarefaCronograma.ordem, TarefaCronograma.id).all()
    return jsonify({
        'status': 'ok',
        'tarefa': _tarefa_to_dict(tarefa),
        'tarefas': [_tarefa_to_dict(t) for t in todas],
    })


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
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).first_or_404()

    # Desvincular filhas e tarefas que dependem desta como predecessora
    TarefaCronograma.query.filter_by(tarefa_pai_id=tarefa_id).update({'tarefa_pai_id': None})
    TarefaCronograma.query.filter_by(predecessora_id=tarefa_id).update({'predecessora_id': None})

    db.session.delete(tarefa)
    db.session.commit()
    logger.info(f"[OK] TarefaCronograma excluída id={tarefa_id} cliente={cliente_mode}")
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
    cliente_mode = _modo_cliente()
    Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    ok = recalcular_cronograma(obra_id, admin_id, cliente=cliente_mode)
    if not ok:
        return jsonify({'status': 'error', 'msg': 'Erro ao recalcular cronograma'}), 500

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
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
    """
    Persiste a nova ordem dos itens do cronograma da obra. Espera JSON:
        {"ordem": [<id>, <id>, ...]}

    Task #19 — drag-and-drop com persistência: valida que a obra pertence
    ao tenant, que todos os IDs são inteiros únicos e que cada um pertence
    à mesma obra/admin (e ao mesmo modo cliente/interno). Escreve em uma
    única transação; em qualquer falha faz rollback e devolve erro para
    o front reverter visualmente.
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    cliente_mode = _modo_cliente()

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada.'}), 404

    data = request.get_json(silent=True) or {}
    ordem_raw = data.get('ordem')

    if not isinstance(ordem_raw, list) or not ordem_raw:
        return jsonify({
            'status': 'error',
            'msg': 'Campo "ordem" deve ser uma lista de IDs.',
        }), 400

    try:
        ordem_ids = [int(x) for x in ordem_raw]
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'IDs inválidos.'}), 400

    if len(set(ordem_ids)) != len(ordem_ids):
        return jsonify({'status': 'error', 'msg': 'IDs duplicados na ordem.'}), 400

    # Carrega TODAS as tarefas da nova ordem em UMA query e valida que
    # cada uma pertence à obra/admin e ao modo (cliente vs. interno) atual.
    # Tudo ou nada: se algum ID não bate, devolve 400 e nada é persistido.
    tarefas = TarefaCronograma.query.filter(
        TarefaCronograma.id.in_(ordem_ids),
        TarefaCronograma.obra_id == obra_id,
        TarefaCronograma.admin_id == admin_id,
        TarefaCronograma.is_cliente == cliente_mode,
    ).all()

    if len(tarefas) != len(ordem_ids):
        return jsonify({
            'status': 'error',
            'msg': 'Algumas tarefas não pertencem a esta obra.',
        }), 400

    by_id = {t.id: t for t in tarefas}
    try:
        for idx, tid in enumerate(ordem_ids):
            by_id[tid].ordem = idx
        db.session.commit()
    except Exception as exc:  # pragma: no cover - defensivo
        db.session.rollback()
        logger.exception(
            f"[ERROR] Falha ao reordenar cronograma obra={obra_id}: {exc}"
        )
        return jsonify({'status': 'error', 'msg': 'Falha ao salvar ordem.'}), 500

    logger.info(
        f"[OK] Cronograma reordenado obra={obra_id} cliente={cliente_mode} "
        f"qtd={len(ordem_ids)}"
    )
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

    # Task #147 — filtra explicitamente o cronograma INTERNO (is_cliente=False).
    # Sem esse filtro, obras que já tiveram o cronograma do cliente gerado
    # devolviam interno + clones do cliente juntos, dobrando cada item no card
    # "Apontamento de Produção — Cronograma" do Novo RDO.
    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    # Task #154 — usar o mesmo critério do cronograma para identificar pais
    # (qualquer tarefa cujo id apareça como tarefa_pai_id de outra) e
    # garantir que o agregado bate com a tela do cronograma.
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}

    # Montar dict com progresso
    resultado = []
    item_por_id: dict[int, dict] = {}
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

        item = {
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
            'responsavel': getattr(t, 'responsavel', 'empresa') or 'empresa',
            'is_pai': t.id in pai_ids,
            'data_entrega_real': (
                t.data_entrega_real.isoformat()
                if getattr(t, 'data_entrega_real', None) else None
            ),
        }
        resultado.append(item)
        item_por_id[t.id] = item

    # Bottom-up: % realizado dos pais = média ponderada por duração das filhas
    # (mesma fórmula de cronograma_engine.recalcular_cronograma). Garante que
    # o subgrupo no RDO mostra o mesmo valor agregado do cronograma, mesmo se
    # `percentual_concluido` persistido ainda estiver desatualizado.
    filhas_por_pai: dict[int, list[dict]] = {}
    for it in resultado:
        if it['tarefa_pai_id']:
            filhas_por_pai.setdefault(it['tarefa_pai_id'], []).append(it)

    pais_ord = [t for t in tarefas if t.id in pai_ids]
    for pai in sorted(pais_ord, key=lambda x: x.ordem, reverse=True):
        filhas = filhas_por_pai.get(pai.id, [])
        if not filhas:
            continue
        total_dur = sum(max(int((item_por_id[f['id']].get('duracao_dias') or 1)), 1) for f in filhas)
        if total_dur > 0:
            agregado = sum(
                (f.get('percentual_realizado') or 0) * max(int(f.get('duracao_dias') or 1), 1)
                for f in filhas
            ) / total_dur
            item_por_id[pai.id]['percentual_realizado'] = round(agregado, 2)
            item_por_id[pai.id]['percentual_concluido'] = round(agregado, 2)

    return jsonify({'status': 'ok', 'tarefas': resultado})


# ─────────────────────────────────────────────────────────────────────────────
# SUBEMPREITADA — Apontamentos diários (pessoas × horas × quantidade)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/rdo/<int:rdo_id>/apontar-subempreitada', methods=['POST'])
@login_required
def apontar_subempreitada(rdo_id: int):
    """
    Cria/atualiza um apontamento de equipe de subempreitada para uma tarefa em um RDO.
    Body JSON: {
        id (opcional, para update), tarefa_cronograma_id, subempreiteiro_id,
        qtd_pessoas, horas_trabalhadas, quantidade_produzida, observacoes
    }
    Atualiza o percentual da tarefa do cronograma como soma dos apontamentos
    (homem-empresa + subempreitada).
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    from models import RDO, RDOSubempreitadaApontamento, Subempreiteiro

    admin_id = _admin_id()
    data = request.get_json(silent=True) or {}

    apt_id = data.get('id')
    tarefa_id = data.get('tarefa_cronograma_id')
    sub_id = data.get('subempreiteiro_id')
    qtd_pessoas = int(data.get('qtd_pessoas', 0) or 0)
    horas = float(data.get('horas_trabalhadas', 0) or 0)
    qtd_prod = float(data.get('quantidade_produzida', 0) or 0)
    obs = (data.get('observacoes') or '').strip() or None

    if not tarefa_id or not sub_id:
        return jsonify({'status': 'error', 'msg': 'tarefa_cronograma_id e subempreiteiro_id obrigatórios'}), 400

    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404

    tarefa = TarefaCronograma.query.filter_by(id=tarefa_id, admin_id=admin_id).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404

    # Task #147 — apontamentos só podem ser criados na árvore INTERNA da obra.
    # Bloqueia tentativa (acidental ou maliciosa) de apontar em um clone do
    # cronograma do cliente, que geraria registros "fantasma" no portal.
    if tarefa.is_cliente:
        return jsonify({
            'status': 'error',
            'msg': 'Apontamentos não podem ser feitos em tarefas do cronograma do cliente'
        }), 400

    sub = Subempreiteiro.query.filter_by(id=sub_id, admin_id=admin_id).first()
    if not sub:
        return jsonify({'status': 'error', 'msg': 'Subempreiteiro não encontrado'}), 404

    if apt_id:
        apt = RDOSubempreitadaApontamento.query.filter_by(id=apt_id, admin_id=admin_id).first()
        if not apt:
            return jsonify({'status': 'error', 'msg': 'Apontamento não encontrado'}), 404
    else:
        apt = RDOSubempreitadaApontamento(
            rdo_id=rdo_id, admin_id=admin_id,
            tarefa_cronograma_id=tarefa_id, subempreiteiro_id=sub_id,
        )
        db.session.add(apt)

    apt.tarefa_cronograma_id = tarefa_id
    apt.subempreiteiro_id = sub_id
    apt.qtd_pessoas = qtd_pessoas
    apt.horas_trabalhadas = horas
    apt.quantidade_produzida = qtd_prod
    apt.observacoes = obs
    apt.calcular_homem_hora()

    db.session.commit()

    # Recalcular percentual da tarefa somando empresa + subempreitada (acumulado por data)
    _atualizar_percentual_com_subempreitada(tarefa_id, admin_id)

    return jsonify({
        'status': 'ok',
        'apontamento': {
            'id': apt.id,
            'tarefa_cronograma_id': apt.tarefa_cronograma_id,
            'subempreiteiro_id': apt.subempreiteiro_id,
            'subempreiteiro_nome': sub.nome,
            'qtd_pessoas': apt.qtd_pessoas,
            'horas_trabalhadas': apt.horas_trabalhadas,
            'quantidade_produzida': apt.quantidade_produzida,
            'homem_hora': apt.homem_hora,
            'observacoes': apt.observacoes,
        },
    })


@cronograma_bp.route('/rdo/<int:rdo_id>/apontamentos-subempreitada')
@login_required
def listar_apontamentos_subempreitada(rdo_id: int):
    """Lista todos os apontamentos de subempreitada deste RDO."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    from models import RDO, RDOSubempreitadaApontamento, Subempreiteiro

    admin_id = _admin_id()
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404

    rows = (
        db.session.query(RDOSubempreitadaApontamento, Subempreiteiro)
        .join(Subempreiteiro, Subempreiteiro.id == RDOSubempreitadaApontamento.subempreiteiro_id)
        .filter(RDOSubempreitadaApontamento.rdo_id == rdo_id,
                RDOSubempreitadaApontamento.admin_id == admin_id)
        .all()
    )

    return jsonify({
        'status': 'ok',
        'apontamentos': [
            {
                'id': apt.id,
                'tarefa_cronograma_id': apt.tarefa_cronograma_id,
                'subempreiteiro_id': apt.subempreiteiro_id,
                'subempreiteiro_nome': sub.nome,
                'qtd_pessoas': apt.qtd_pessoas,
                'horas_trabalhadas': apt.horas_trabalhadas,
                'quantidade_produzida': apt.quantidade_produzida,
                'homem_hora': apt.homem_hora,
                'observacoes': apt.observacoes,
            }
            for apt, sub in rows
        ],
    })


@cronograma_bp.route('/rdo/apontamento-subempreitada/<int:apt_id>', methods=['DELETE'])
@login_required
def excluir_apontamento_subempreitada(apt_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    from models import RDOSubempreitadaApontamento

    admin_id = _admin_id()
    apt = RDOSubempreitadaApontamento.query.filter_by(id=apt_id, admin_id=admin_id).first()
    if not apt:
        return jsonify({'status': 'error', 'msg': 'Não encontrado'}), 404

    tarefa_id = apt.tarefa_cronograma_id
    db.session.delete(apt)
    db.session.commit()
    _atualizar_percentual_com_subempreitada(tarefa_id, admin_id)
    return jsonify({'status': 'ok'})


def _atualizar_percentual_com_subempreitada(tarefa_id: int, admin_id: int):
    """
    Recalcula percentual_concluido da tarefa considerando produção total
    (apontamentos da empresa + apontamentos de subempreitada).
    """
    from sqlalchemy import func as sqlfunc
    from models import RDOSubempreitadaApontamento

    tarefa = TarefaCronograma.query.filter_by(id=tarefa_id, admin_id=admin_id).first()
    if not tarefa:
        return

    qtd_empresa = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
        .filter(RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
                RDOApontamentoCronograma.admin_id == admin_id)
        .scalar()
    ) or 0.0

    qtd_sub = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(RDOSubempreitadaApontamento.quantidade_produzida), 0.0))
        .filter(RDOSubempreitadaApontamento.tarefa_cronograma_id == tarefa_id,
                RDOSubempreitadaApontamento.admin_id == admin_id)
        .scalar()
    ) or 0.0

    qtd_total = float(qtd_empresa) + float(qtd_sub)

    if tarefa.quantidade_total and tarefa.quantidade_total > 0:
        tarefa.percentual_concluido = min(100.0, round(qtd_total / tarefa.quantidade_total * 100, 2))
    db.session.commit()


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

    # Task #147 — apontamentos só podem ser criados na árvore INTERNA da obra.
    # Bloqueia tentativa (acidental ou maliciosa) de apontar em um clone do
    # cronograma do cliente, que geraria registros "fantasma" no portal.
    if tarefa.is_cliente:
        return jsonify({
            'status': 'error',
            'msg': 'Apontamentos não podem ser feitos em tarefas do cronograma do cliente'
        }), 400

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
    # Task #142 — coluna agora é nullable. Persistimos `None` quando a tarefa
    # não tem plano calculável (sem data_inicio/duração). A UI usa esse `None`
    # para mostrar "—" / badge "Sem plano" em vez de 0%.
    plan_calculado = progresso['percentual_planejado']
    ap.percentual_planejado = plan_calculado

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
            'percentual_planejado': plan_calculado,
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


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO DE SUBATIVIDADES — CRUD SubatividadeMestre com unidade/meta
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/catalogo')
@login_required
def catalogo_subatividades():
    """Página de gestão do catálogo de subatividades com metas de produtividade."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
    todos = (
        SubatividadeMestre.query
        .filter_by(admin_id=admin_id)
        .order_by(SubatividadeMestre.nome)
        .all()
    )
    grupos = [s for s in todos if getattr(s, 'tipo', 'subatividade') == 'grupo']
    subatividades = [s for s in todos if getattr(s, 'tipo', 'subatividade') != 'grupo']
    return render_template(
        'cronograma/catalogo.html',
        servicos=servicos,
        subatividades=subatividades,
        grupos=grupos,
    )


@cronograma_bp.route('/catalogo/nova', methods=['POST'])
@login_required
def catalogo_nova_subatividade():
    """Criar nova subatividade no catálogo."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tipo = (request.form.get('tipo') or 'subatividade').strip()
    if tipo not in ('grupo', 'subatividade'):
        tipo = 'subatividade'
    nome = (request.form.get('nome') or '').strip()

    if not nome:
        flash('Nome é obrigatório.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    if tipo == 'grupo':
        sub = SubatividadeMestre(
            servico_id=None,
            tipo='grupo',
            nome=nome,
            descricao=(request.form.get('descricao') or '').strip() or None,
            obrigatoria=False,
            admin_id=admin_id,
        )
        db.session.add(sub)
        db.session.commit()
        flash(f'Grupo "{nome}" criado com sucesso.', 'success')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    # tipo == 'subatividade'
    descricao = (request.form.get('descricao') or '').strip()
    unidade_medida = (request.form.get('unidade_medida') or '').strip() or None
    meta_produtividade_str = (request.form.get('meta_produtividade') or '').strip()
    ordem_padrao = request.form.get('ordem_padrao', type=int, default=0)
    obrigatoria = request.form.get('obrigatoria') == '1'
    servico_id = request.form.get('servico_id', type=int)

    if not unidade_medida:
        flash('Unidade de Medida é obrigatória para subatividades.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    if not meta_produtividade_str:
        flash('Meta de Produtividade é obrigatória para subatividades.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    try:
        meta = float(meta_produtividade_str)
        if meta <= 0:
            raise ValueError("meta deve ser positiva")
    except ValueError:
        flash('Meta de Produtividade deve ser um número positivo.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    sub = SubatividadeMestre(
        servico_id=servico_id or None,
        tipo='subatividade',
        nome=nome,
        descricao=descricao or None,
        unidade_medida=unidade_medida,
        meta_produtividade=meta,
        ordem_padrao=ordem_padrao,
        obrigatoria=obrigatoria,
        admin_id=admin_id,
    )
    db.session.add(sub)
    db.session.flush()

    # Task #62 — vincular composições selecionadas (N:N SubatividadeMaoObra)
    _sync_composicoes_subatividade(sub, request.form.getlist('composicoes_ids'), admin_id)

    db.session.commit()
    flash(f'Subatividade "{nome}" criada com sucesso.', 'success')
    return redirect(url_for('cronograma.catalogo_subatividades'))


def _sync_composicoes_subatividade(sub: SubatividadeMestre, ids_raw: list, admin_id: int) -> None:
    """Task #62 — sincroniza SubatividadeMaoObra para a subatividade.

    ids_raw: lista de strings do form (composicoes_ids[]). Apenas IDs que
    pertencem ao admin e (quando sub.servico_id está setado) ao mesmo serviço
    são aceitos. Apaga os removidos e cria os novos. Idempotente.
    """
    novos_ids = set()
    for raw in (ids_raw or []):
        try:
            novos_ids.add(int(raw))
        except (ValueError, TypeError):
            continue

    if novos_ids:
        # Multi-tenant: SEMPRE filtra por admin_id; restringe ao serviço da sub
        # quando houver; aceita apenas composições de insumo MAO_OBRA.
        from models import Insumo as _Insumo
        q = (
            ComposicaoServico.query
            .join(_Insumo, ComposicaoServico.insumo_id == _Insumo.id)
            .filter(
                ComposicaoServico.id.in_(novos_ids),
                ComposicaoServico.admin_id == admin_id,
                _Insumo.tipo == 'MAO_OBRA',
            )
        )
        if sub.servico_id:
            q = q.filter(ComposicaoServico.servico_id == sub.servico_id)
        composicoes_validas = {c.id for c in q.all()}
        novos_ids = novos_ids & composicoes_validas

    atuais = SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id
    ).all()
    atuais_ids = {l.composicao_servico_id for l in atuais}

    for link in atuais:
        if link.composicao_servico_id not in novos_ids:
            db.session.delete(link)

    for new_id in (novos_ids - atuais_ids):
        db.session.add(SubatividadeMaoObra(
            admin_id=admin_id,
            subatividade_mestre_id=sub.id,
            composicao_servico_id=new_id,
        ))


@cronograma_bp.route('/catalogo/novo-grupo', methods=['POST'])
@login_required
def catalogo_novo_grupo():
    """Criar novo grupo no catálogo (sem vínculo com Serviço)."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    nome = (request.form.get('nome') or '').strip()
    if not nome:
        flash('Nome é obrigatório.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    grupo = SubatividadeMestre(
        servico_id=None,
        tipo='grupo',
        nome=nome,
        descricao=(request.form.get('descricao') or '').strip() or None,
        obrigatoria=False,
        admin_id=admin_id,
    )
    db.session.add(grupo)
    db.session.commit()
    flash(f'Grupo "{nome}" criado com sucesso.', 'success')
    return redirect(url_for('cronograma.catalogo_subatividades'))


@cronograma_bp.route('/catalogo/<int:sub_id>/editar', methods=['GET', 'POST'])
@login_required
def catalogo_editar_subatividade(sub_id: int):
    """Editar subatividade do catálogo."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    sub = SubatividadeMestre.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'warning')
        else:
            tipo_atual = getattr(sub, 'tipo', 'subatividade')
            if tipo_atual == 'grupo':
                sub.nome = nome
                sub.descricao = (request.form.get('descricao') or '').strip() or None
                sub.ativo = request.form.get('ativo') == '1'
                db.session.commit()
                flash(f'Grupo "{sub.nome}" atualizado.', 'success')
                return redirect(url_for('cronograma.catalogo_subatividades'))
            else:
                meta_str = request.form.get('meta_produtividade') or ''
                try:
                    meta = float(meta_str) if meta_str else None
                except ValueError:
                    meta = None
                sub.nome = nome
                # Only update servico_id when the field is explicitly present in the submitted form
                if 'servico_id' in request.form:
                    sub.servico_id = request.form.get('servico_id', type=int) or None
                sub.descricao = (request.form.get('descricao') or '').strip() or None
                sub.unidade_medida = (request.form.get('unidade_medida') or '').strip() or None
                sub.meta_produtividade = meta
                sub.ordem_padrao = request.form.get('ordem_padrao', type=int, default=0)
                sub.obrigatoria = request.form.get('obrigatoria') == '1'
                sub.ativo = request.form.get('ativo') == '1'
                # Task #62 — flag de revisão (auto-marcada via cronograma)
                if 'precisa_revisao' in request.form:
                    sub.precisa_revisao = request.form.get('precisa_revisao') == '1'
                # Task #62 — sincroniza N:N composições
                if 'composicoes_ids' in request.form or any(
                    k.startswith('composicoes_ids') for k in request.form.keys()
                ):
                    _sync_composicoes_subatividade(
                        sub, request.form.getlist('composicoes_ids'), admin_id
                    )
                db.session.commit()
                flash(f'Subatividade "{sub.nome}" atualizada.', 'success')
                return redirect(url_for('cronograma.catalogo_subatividades'))

    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
    # Task #62 — composições disponíveis (apenas MO, do serviço da sub, do admin)
    composicoes = []
    if sub.servico_id:
        from models import Insumo as _Insumo
        composicoes = (
            ComposicaoServico.query
            .join(_Insumo, ComposicaoServico.insumo_id == _Insumo.id)
            .filter(
                ComposicaoServico.servico_id == sub.servico_id,
                ComposicaoServico.admin_id == admin_id,
                _Insumo.tipo == 'MAO_OBRA',
            )
            .order_by(ComposicaoServico.id)
            .all()
        )
    composicoes_selecionadas_ids = {
        l.composicao_servico_id
        for l in SubatividadeMaoObra.query.filter_by(
            subatividade_mestre_id=sub.id
        ).all()
    }
    return render_template(
        'cronograma/catalogo_editar.html',
        sub=sub, servicos=servicos,
        composicoes=composicoes,
        composicoes_selecionadas_ids=composicoes_selecionadas_ids,
    )


@cronograma_bp.route('/catalogo/<int:sub_id>/excluir', methods=['POST'])
@login_required
def catalogo_excluir_subatividade(sub_id: int):
    """Excluir subatividade do catálogo."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    sub = SubatividadeMestre.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()
    nome = sub.nome
    try:
        db.session.delete(sub)
        db.session.commit()
        flash(f'Subatividade "{nome}" excluída.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO EXCLUIR SubatividadeMestre {sub_id}: {e}")
        flash('Erro ao excluir. Verifique se há itens vinculados.', 'error')
    return redirect(url_for('cronograma.catalogo_subatividades'))


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO — API JSON (painel esquerdo do template builder)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/api/catalogo')
@login_required
def api_catalogo():
    """Retorna grupos, subatividades e serviços do catálogo (para autocomplete e template builder)."""
    guard = _check_v2()
    if guard:
        return jsonify({'error': 'V2 required'}), 403

    admin_id = _admin_id()
    todos = (
        SubatividadeMestre.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(SubatividadeMestre.nome)
        .all()
    )

    def _sub_to_dict(s):
        return {
            'id': s.id,
            'nome': s.nome,
            'tipo': getattr(s, 'tipo', 'subatividade'),
            'unidade_medida': s.unidade_medida or '',
            'meta_produtividade': s.meta_produtividade,
        }

    grupos = [_sub_to_dict(s) for s in todos if getattr(s, 'tipo', 'subatividade') == 'grupo']
    subatividades = [_sub_to_dict(s) for s in todos if getattr(s, 'tipo', 'subatividade') != 'grupo']

    servicos = (
        Servico.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(Servico.nome)
        .all()
    )
    servicos_list = [
        {'id': sv.id, 'nome': sv.nome, 'unidade_medida': sv.unidade_medida or ''}
        for sv in servicos
    ]

    return jsonify({'grupos': grupos, 'subatividades': subatividades, 'servicos': servicos_list})


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATES DE CRONOGRAMA — CRUD
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/templates')
@login_required
def listar_templates():
    """Lista todos os templates de cronograma do tenant."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    templates = (
        CronogramaTemplate.query
        .filter_by(admin_id=admin_id)
        .order_by(CronogramaTemplate.nome)
        .all()
    )
    return render_template('cronograma/templates.html', templates=templates)


@cronograma_bp.route('/templates/novo', methods=['GET', 'POST'])
@login_required
def novo_template():
    """Criar novo template de cronograma."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('O nome do template é obrigatório.', 'warning')
            return redirect(url_for('cronograma.novo_template'))

        tmpl = CronogramaTemplate(
            nome=nome,
            descricao=(request.form.get('descricao') or '').strip() or None,
            categoria=(request.form.get('categoria') or '').strip() or None,
            ativo=request.form.get('ativo', '1') == '1',
            admin_id=admin_id,
        )
        db.session.add(tmpl)
        db.session.flush()

        itens_json = request.form.get('itens_json')
        if itens_json:
            import json as _json
            try:
                arvore = _json.loads(itens_json)
                _salvar_arvore_template(tmpl, admin_id, arvore)
            except Exception as e:
                logger.warning(f"Erro ao parsear itens_json: {e}")
                _salvar_itens_template(tmpl, admin_id)
        else:
            _salvar_itens_template(tmpl, admin_id)

        db.session.commit()
        flash(f'Template "{tmpl.nome}" criado com sucesso.', 'success')
        return redirect(url_for('cronograma.detalhe_template', template_id=tmpl.id))

    return render_template(
        'cronograma/template_form.html',
        template=None,
        itens=[],
        itens_arvore=[],
    )


@cronograma_bp.route('/templates/<int:template_id>')
@login_required
def detalhe_template(template_id: int):
    """Exibe detalhes e itens de um template."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first_or_404()
    itens_arvore = _construir_arvore_itens(list(tmpl.itens))
    return render_template('cronograma/template_detalhe.html', template=tmpl, itens_arvore=itens_arvore)


@cronograma_bp.route('/templates/<int:template_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_template(template_id: int):
    """Editar template de cronograma."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('O nome do template é obrigatório.', 'warning')
            return redirect(url_for('cronograma.editar_template', template_id=template_id))

        tmpl.nome = nome
        tmpl.descricao = (request.form.get('descricao') or '').strip() or None
        tmpl.categoria = (request.form.get('categoria') or '').strip() or None
        tmpl.ativo = request.form.get('ativo') == '1'

        # Remover itens antigos e recriar
        for item in list(tmpl.itens):
            db.session.delete(item)
        db.session.flush()

        itens_json = request.form.get('itens_json')
        if itens_json:
            import json as _json
            try:
                arvore = _json.loads(itens_json)
                _salvar_arvore_template(tmpl, admin_id, arvore)
            except Exception as e:
                logger.warning(f"Erro ao parsear itens_json: {e}")
                _salvar_itens_template(tmpl, admin_id)
        else:
            _salvar_itens_template(tmpl, admin_id)

        db.session.commit()
        flash(f'Template "{tmpl.nome}" atualizado.', 'success')
        return redirect(url_for('cronograma.detalhe_template', template_id=tmpl.id))

    # Montar árvore dos itens existentes para o template builder
    itens_arvore = _construir_arvore_itens(list(tmpl.itens))
    return render_template(
        'cronograma/template_form.html',
        template=tmpl,
        itens=list(tmpl.itens),
        itens_arvore=itens_arvore,
    )


# Task #23 — Modelo Excel para Templates de Cronograma (download/import)
@cronograma_bp.route('/templates/modelo-excel')
@login_required
def templates_modelo_excel():
    """Baixa o modelo `.xlsx` para cadastro de template + itens."""
    guard = _check_v2()
    if guard:
        return guard
    from services.catalogo_excel import gerar_modelo_cronograma_xlsx
    import io as _io
    bio = gerar_modelo_cronograma_xlsx()
    return send_file(
        _io.BytesIO(bio),
        as_attachment=True,
        download_name='modelo_cronograma.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@cronograma_bp.route('/templates/importar-excel', methods=['POST'])
@login_required
def templates_importar_excel():
    """Recebe um `.xlsx` preenchido e cria/atualiza um template."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        flash('Selecione um arquivo Excel para importar.', 'error')
        return redirect(url_for('cronograma.listar_templates'))
    if not arquivo.filename.lower().endswith(('.xlsx', '.xlsm')):
        flash('Envie um arquivo .xlsx (Excel).', 'error')
        return redirect(url_for('cronograma.listar_templates'))

    from services.catalogo_excel import importar_cronograma_xlsx
    try:
        resultado = importar_cronograma_xlsx(arquivo.stream, admin_id)
    except ValueError as e:
        flash(f'Erro ao importar: {e}', 'error')
        return redirect(url_for('cronograma.listar_templates'))
    except Exception as e:
        logger.exception('Erro inesperado importando template via Excel')
        flash(f'Erro inesperado: {e}', 'error')
        return redirect(url_for('cronograma.listar_templates'))

    acao = 'criado' if resultado['criado_ou_atualizado'] == 'created' else 'atualizado'
    flash(
        f'Template "{resultado["template_nome"]}" {acao} com '
        f'{resultado["itens_count"]} item(ns).',
        'success',
    )

    if resultado['rejected']:
        detalhes = '; '.join(
            f'linha {r["linha"]}: {r["motivo"]}'
            for r in resultado['rejected'][:15]
        )
        suffix = '' if len(resultado['rejected']) <= 15 else f' (+{len(resultado["rejected"]) - 15} outras)'
        flash(
            f'{len(resultado["rejected"])} linha(s) rejeitada(s): {detalhes}{suffix}',
            'warning',
        )

    return redirect(url_for('cronograma.listar_templates'))


@cronograma_bp.route('/templates/<int:template_id>/excluir', methods=['POST'])
@login_required
def excluir_template(template_id: int):
    """Excluir template de cronograma."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first_or_404()
    nome = tmpl.nome
    try:
        db.session.delete(tmpl)
        db.session.commit()
        flash(f'Template "{nome}" excluído.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO EXCLUIR TEMPLATE {template_id}: {e}")
        flash('Erro ao excluir o template.', 'error')
    return redirect(url_for('cronograma.listar_templates'))


def _salvar_itens_template(tmpl: CronogramaTemplate, admin_id: int) -> None:
    """
    Lê as listas de campos do formulário e salva os itens do template.
    Espera campos: item_nome[], item_ordem[], item_duracao_dias[],
                   item_quantidade_prevista[], item_responsavel[],
                   item_subatividade_mestre_id[]

    SEGURANÇA: cada subatividade_mestre_id é validado contra admin_id para
    garantir isolamento multi-tenant. IDs inválidos ou de outros tenants são
    silenciosamente descartados (item criado sem vínculo de catálogo).
    """
    nomes = request.form.getlist('item_nome')
    ordens = request.form.getlist('item_ordem')
    duracoes = request.form.getlist('item_duracao_dias')
    quantidades = request.form.getlist('item_quantidade_prevista')
    responsaveis = request.form.getlist('item_responsavel')
    sub_ids = request.form.getlist('item_subatividade_mestre_id')

    # Cache de SubatividadeMestre válidas para o tenant (evita N queries)
    sub_ids_validos: dict[int, bool] = {}

    for i, nome in enumerate(nomes):
        nome = (nome or '').strip()
        if not nome:
            continue
        try:
            ordem = int(ordens[i]) if i < len(ordens) else i
        except (ValueError, IndexError):
            ordem = i
        try:
            duracao = max(1, int(duracoes[i])) if i < len(duracoes) else 1
        except (ValueError, IndexError):
            duracao = 1
        try:
            qty_str = quantidades[i] if i < len(quantidades) else ''
            qty = float(qty_str) if qty_str and qty_str.strip() else None
        except (ValueError, IndexError):
            qty = None
        responsavel = (responsaveis[i] if i < len(responsaveis) else 'empresa') or 'empresa'

        # Validar subatividade_mestre_id pertence ao tenant
        sub_id: int | None = None
        try:
            sub_id_raw = sub_ids[i] if i < len(sub_ids) else ''
            raw_int = int(sub_id_raw) if sub_id_raw and sub_id_raw.strip() else None
            if raw_int is not None:
                if raw_int not in sub_ids_validos:
                    existe = SubatividadeMestre.query.filter_by(
                        id=raw_int, admin_id=admin_id
                    ).first() is not None
                    sub_ids_validos[raw_int] = existe
                sub_id = raw_int if sub_ids_validos[raw_int] else None
                if not sub_ids_validos.get(raw_int):
                    logger.warning(
                        f"SEGURANÇA: subatividade_mestre_id={raw_int} recusada "
                        f"(não pertence a admin_id={admin_id})"
                    )
        except (ValueError, IndexError):
            sub_id = None

        item = CronogramaTemplateItem(
            template_id=tmpl.id,
            subatividade_mestre_id=sub_id,
            nome_tarefa=nome,
            ordem=ordem,
            duracao_dias=duracao,
            quantidade_prevista=qty,
            responsavel=responsavel,
            admin_id=admin_id,
        )
        db.session.add(item)


def _salvar_arvore_template(tmpl: CronogramaTemplate, admin_id: int, arvore: list, parent_db_id: int | None = None, ordem_base: int = 0) -> int:
    """
    Salva recursivamente a árvore hierárquica de itens do template.
    Cada nó da arvore é um dict com:
      catalogo_id: int | None  (SubatividadeMestre.id)
      nome: str
      tipo: 'grupo' | 'subatividade'
      quantidade_prevista: float | None
      filhos: list  (apenas grupos podem ter filhos)

    Retorna a próxima ordem disponível.
    """
    ordem = ordem_base
    # Cache: catalogo_id → SubatividadeMestre (or None) for admin_id validation
    catalogo_cache: dict[int, object] = {}

    def _buscar_catalogo(cid: int):
        if cid not in catalogo_cache:
            catalogo_cache[cid] = SubatividadeMestre.query.filter_by(
                id=cid, admin_id=admin_id, ativo=True
            ).first()
        return catalogo_cache[cid]

    for no in arvore:
        catalogo_id = no.get('catalogo_id')
        nome = (no.get('nome') or '').strip()
        tipo_no = (no.get('tipo') or 'subatividade').strip()
        if tipo_no not in ('grupo', 'subatividade'):
            tipo_no = 'subatividade'
        if not nome:
            continue

        sub_id: int | None = None
        if catalogo_id:
            try:
                raw_int = int(catalogo_id)
                sm = _buscar_catalogo(raw_int)
                if sm is not None:
                    # Validate catalog item tipo matches tree node tipo
                    sm_tipo = getattr(sm, 'tipo', None) or 'subatividade'
                    if sm_tipo == tipo_no:
                        sub_id = raw_int
                    else:
                        logger.warning(
                            f"Template save: catalogo_id={raw_int} tipo={sm_tipo!r} "
                            f"não corresponde ao nó tipo={tipo_no!r} — referência ignorada"
                        )
            except (ValueError, TypeError):
                sub_id = None

        filhos = no.get('filhos') or []

        # Server-side rule: only grupos can have children
        if tipo_no == 'subatividade' and filhos:
            logger.warning(
                f"Template save: nó '{nome}' (tipo=subatividade) tem filhos — filhos ignorados"
            )
            filhos = []

        try:
            qty = float(no.get('quantidade_prevista') or 0) or None
        except (ValueError, TypeError):
            qty = None

        item = CronogramaTemplateItem(
            template_id=tmpl.id,
            subatividade_mestre_id=sub_id,
            parent_item_id=parent_db_id,
            nome_tarefa=nome,
            ordem=ordem,
            duracao_dias=1,
            quantidade_prevista=qty,
            responsavel='empresa',
            admin_id=admin_id,
        )
        db.session.add(item)
        db.session.flush()  # obtém item.id para usar como parent_item_id nos filhos

        ordem += 1
        if filhos:
            _salvar_arvore_template(tmpl, admin_id, filhos, parent_db_id=item.id, ordem_base=0)

    return ordem


def _construir_arvore_itens(itens: list) -> list:
    """
    Converte lista plana de CronogramaTemplateItem em árvore aninhada (JSON-serializable).
    Itens com filhos são automaticamente tratados como 'grupo'.
    """
    by_id = {item.id: {
        'id': item.id,
        'nome': item.nome_tarefa,
        'catalogo_id': item.subatividade_mestre_id,
        'tipo': (getattr(item.subatividade, 'tipo', None) or 'subatividade') if item.subatividade else 'subatividade',
        'quantidade_prevista': item.quantidade_prevista,
        'parent_item_id': getattr(item, 'parent_item_id', None),
        'ordem': item.ordem,
        'filhos': [],
    } for item in itens}

    raizes = []
    for node in by_id.values():
        parent_id = node['parent_item_id']
        if parent_id and parent_id in by_id:
            by_id[parent_id]['filhos'].append(node)
        else:
            raizes.append(node)

    def _fixar_e_ordenar(nodes):
        nodes.sort(key=lambda n: n['ordem'])
        for n in nodes:
            _fixar_e_ordenar(n['filhos'])
            if n['filhos']:
                n['tipo'] = 'grupo'

    _fixar_e_ordenar(raizes)
    return raizes


# ─────────────────────────────────────────────────────────────────────────────
# APLICAR TEMPLATE AO CRONOGRAMA DE UMA OBRA
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/aplicar-template', methods=['POST'])
@login_required
def aplicar_template(obra_id: int):
    """
    Aplica um template ao cronograma da obra, criando TarefaCronograma para
    cada item do template. As tarefas são inseridas sequencialmente após as
    já existentes, e o cronograma é recalculado ao final.
    """
    guard = _check_v2()
    if guard:
        flash('Funcionalidade disponível apenas no plano V2.', 'warning')
        return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id))

    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    qs = _qs_cliente(cliente_mode)
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    template_id = request.form.get('template_id', type=int)
    if not template_id:
        flash('Selecione um template.', 'warning')
        return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id) + qs)

    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first()
    if not tmpl:
        flash('Template não encontrado.', 'error')
        return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id) + qs)

    # Data de início: form ou hoje
    data_inicio_str = request.form.get('data_inicio_template') or ''
    data_inicio = _parse_date(data_inicio_str) or date.today()

    # Offset de ordem para não sobrescrever tarefas existentes (no mesmo modo)
    max_ordem_row = (
        db.session.query(db.func.max(TarefaCronograma.ordem))
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .scalar()
    )
    ordem_base = (max_ordem_row or 0) + 10

    try:
        from datetime import timedelta

        # Construir árvore hierárquica dos itens do template
        arvore_template = _construir_arvore_itens(list(tmpl.itens))

        # Mapa: CronogramaTemplateItem.id → TarefaCronograma.id (para setar tarefa_pai_id)
        item_id_para_tarefa_id: dict[int, int] = {}
        criadas = 0

        # Cache por id para acesso rápido a admin_id e subatividade
        item_by_id = {item.id: item for item in tmpl.itens}

        # Contador monotônico compartilhado: garante ordem única para cada tarefa
        # independente do nível de profundidade na hierarquia do template.
        ordem_seq = [0]

        def _criar_tarefas(nos: list, pai_tarefa_id, data_ref) -> object:
            """
            Cria TarefaCronograma recursivamente.
            Retorna data_após_último_filho.
            """
            nonlocal criadas
            data_corrente = data_ref
            for no in nos:
                item = item_by_id.get(no['id'])
                if item is None or item.admin_id != admin_id:
                    continue

                # Segurança: validar subatividade vinculada
                unidade = None
                quantidade = item.quantidade_prevista
                sub = item.subatividade
                if sub and sub.admin_id == admin_id:
                    unidade = sub.unidade_medida
                elif sub:
                    sub = None

                is_grupo = no['tipo'] == 'grupo'

                # Task #4 — propaga servico_id da SubatividadeMestre para
                # que tarefas criadas via "Aplicar template" também tenham
                # vínculo com o serviço (UI/custos por serviço, auto-vínculo
                # Função→Composição, etc).
                servico_id_no = sub.servico_id if sub else None
                tarefa = TarefaCronograma(
                    obra_id=obra_id,
                    nome_tarefa=item.nome_tarefa,
                    duracao_dias=item.duracao_dias,
                    data_inicio=data_corrente,
                    quantidade_total=None if is_grupo else quantidade,
                    unidade_medida=None if is_grupo else unidade,
                    responsavel=item.responsavel or 'empresa',
                    tarefa_pai_id=pai_tarefa_id,
                    ordem=ordem_base + ordem_seq[0] * 10,
                    admin_id=admin_id,
                    is_cliente=cliente_mode,
                    subatividade_mestre_id=(sub.id if sub else None),
                    servico_id=servico_id_no,
                )
                ordem_seq[0] += 1
                db.session.add(tarefa)
                db.session.flush()  # obtém tarefa.id para os filhos

                item_id_para_tarefa_id[item.id] = tarefa.id
                criadas += 1

                if no['filhos']:
                    # Filhos herdam data_corrente e têm pai = tarefa.id
                    _criar_tarefas(no['filhos'], tarefa.id, data_corrente)
                    # Data avança pela duração total dos filhos (soma)
                    duracao_filhos = sum(
                        item_by_id[f['id']].duracao_dias
                        for f in no['filhos']
                        if item_by_id.get(f['id'])
                    )
                    data_corrente = data_corrente + timedelta(days=max(duracao_filhos, item.duracao_dias))
                else:
                    data_corrente = data_corrente + timedelta(days=item.duracao_dias)

            return data_corrente

        _criar_tarefas(arvore_template, None, data_inicio)
        db.session.commit()

        # Recalcular datas do cronograma (no mesmo modo)
        recalcular_cronograma(obra_id, admin_id, cliente=cliente_mode)

        flash(
            f'Template "{tmpl.nome}" aplicado com sucesso! {criadas} tarefa(s) criada(s).',
            'success',
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO APLICAR TEMPLATE obra={obra_id} tmpl={template_id} cliente={cliente_mode}: {e}")
        flash(f'Erro ao aplicar template: {str(e)}', 'error')

    return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id) + qs)


@cronograma_bp.route('/api/templates/<int:template_id>')
@login_required
def api_template_arvore(template_id: int):
    """API JSON — retorna a árvore hierárquica de itens de um template."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    template = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id, ativo=True).first()
    if not template:
        return jsonify({'status': 'error', 'msg': 'Template não encontrado'}), 404

    arvore = _construir_arvore_itens(template.itens)

    def _serializar(itens):
        resultado = []
        for item in itens:
            node = {
                'id': item['id'],
                'tipo': item['tipo'],
                'nome': item['nome'],
                'ordem': item.get('ordem', 0),
                'quantidade_prevista': item.get('quantidade_prevista'),
                'catalogo_id': item.get('catalogo_id'),
                'filhos': _serializar(item.get('filhos', [])),
            }
            resultado.append(node)
        return resultado

    return jsonify({
        'status': 'ok',
        'template': {
            'id': template.id,
            'nome': template.nome,
            'categoria': template.categoria,
        },
        'arvore': _serializar(arvore),
    })


@cronograma_bp.route('/api/templates')
@login_required
def api_listar_templates():
    """API JSON — lista templates para o modal de aplicação."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    templates = (
        CronogramaTemplate.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(CronogramaTemplate.nome)
        .all()
    )
    return jsonify({
        'status': 'ok',
        'templates': [
            {
                'id': t.id,
                'nome': t.nome,
                'categoria': t.categoria,
                'total_itens': len(t.itens),
            }
            for t in templates
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard de Produtividade (V2)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/produtividade')
@login_required
def produtividade_dashboard():
    """Página do dashboard de produtividade de funcionários (V2)."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    subatividades = (
        SubatividadeMestre.query
        .join(Servico, SubatividadeMestre.servico_id == Servico.id)
        .filter(Servico.admin_id == admin_id)
        .order_by(SubatividadeMestre.nome)
        .all()
    )
    funcionarios = (
        Funcionario.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(Funcionario.nome)
        .all()
    )
    from datetime import date as _date, timedelta as _td
    data_fim_default = _date.today()
    data_inicio_default = data_fim_default - _td(days=30)
    return render_template(
        'cronograma/produtividade.html',
        obras=obras,
        subatividades=subatividades,
        funcionarios=funcionarios,
        data_inicio_default=data_inicio_default.isoformat(),
        data_fim_default=data_fim_default.isoformat(),
    )


@cronograma_bp.route('/api/produtividade')
@login_required
def api_produtividade():
    """Endpoint JSON: agrega dados de produtividade por funcionário × subatividade."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()

    obra_id = request.args.get('obra_id', type=int)
    sub_mestre_id = request.args.get('subatividade_id', type=int)
    func_id_filtro = request.args.get('funcionario_id', type=int)
    data_inicio_str = request.args.get('data_inicio', '')
    data_fim_str = request.args.get('data_fim', '')

    from datetime import date as _date, datetime as _dt

    try:
        data_inicio = _dt.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else None
    except ValueError:
        data_inicio = None
    try:
        data_fim = _dt.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else None
    except ValueError:
        data_fim = None

    # Base query: RDOMaoObra → subatividade com mestre_id → RDO finalizado
    q = (
        db.session.query(
            RDOMaoObra,
            RDOServicoSubatividade,
            RDO,
            Funcionario,
        )
        .join(RDOServicoSubatividade, RDOMaoObra.subatividade_id == RDOServicoSubatividade.id)
        .join(RDO, RDOMaoObra.rdo_id == RDO.id)
        .join(Funcionario, RDOMaoObra.funcionario_id == Funcionario.id)
        .filter(
            RDO.admin_id == admin_id,
            RDO.status == 'Finalizado',
            RDOServicoSubatividade.subatividade_mestre_id.isnot(None),
            RDOMaoObra.produtividade_real.isnot(None),
        )
    )

    if obra_id:
        q = q.filter(RDO.obra_id == obra_id)
    if sub_mestre_id:
        q = q.filter(RDOServicoSubatividade.subatividade_mestre_id == sub_mestre_id)
    if func_id_filtro:
        q = q.filter(RDOMaoObra.funcionario_id == func_id_filtro)
    if data_inicio:
        q = q.filter(RDO.data_relatorio >= data_inicio)
    if data_fim:
        q = q.filter(RDO.data_relatorio <= data_fim)

    rows = q.order_by(RDO.data_relatorio).all()

    # ── Query separada para média_empresa (sem filtro de funcionário) ──────
    # media_empresa deve refletir o desempenho de TODOS os funcionários da empresa,
    # independente do filtro de funcionario_id.
    from collections import defaultdict

    q_emp = (
        db.session.query(RDOMaoObra, RDOServicoSubatividade, RDO)
        .join(RDOServicoSubatividade, RDOMaoObra.subatividade_id == RDOServicoSubatividade.id)
        .join(RDO, RDOMaoObra.rdo_id == RDO.id)
        .filter(
            RDO.admin_id == admin_id,
            RDO.status == 'Finalizado',
            RDOServicoSubatividade.subatividade_mestre_id.isnot(None),
            RDOMaoObra.produtividade_real.isnot(None),
        )
    )
    if obra_id:
        q_emp = q_emp.filter(RDO.obra_id == obra_id)
    if sub_mestre_id:
        q_emp = q_emp.filter(RDOServicoSubatividade.subatividade_mestre_id == sub_mestre_id)
    if data_inicio:
        q_emp = q_emp.filter(RDO.data_relatorio >= data_inicio)
    if data_fim:
        q_emp = q_emp.filter(RDO.data_relatorio <= data_fim)

    rows_empresa = q_emp.all()

    # Calcular rdo_sub_totais a partir dos dados de TODA a empresa
    rdo_sub_totais: dict = {}
    for mo_e, sub_e, rdo_e in rows_empresa:
        day_key = (rdo_e.id, sub_e.id)
        if day_key not in rdo_sub_totais:
            rdo_sub_totais[day_key] = {
                'sub_mestre_id': sub_e.subatividade_mestre_id,
                'quantidade': sub_e.quantidade_produzida or 0.0,
                'horas_totais': 0.0,
            }
        rdo_sub_totais[day_key]['horas_totais'] += mo_e.horas_trabalhadas or 0.0

    # ── Agregação por (funcionario, subatividade_mestre) ──────────────────
    # Por funcionário × subatividade: média ponderada por horas individuais
    # prod_ponderada = Σ(produtividade_real × horas_pessoa) / Σ(horas_pessoa)
    agg = defaultdict(lambda: {
        'func_nome': '',
        'sub_nome': '',
        'sub_mestre_id': None,
        'meta': None,
        'unidade': '',
        'soma_prod_pond': 0.0,   # Σ(prod_real × horas_pessoa)
        'soma_indice_pond': 0.0, # Σ(indice × horas_pessoa)
        'total_horas': 0.0,      # Σ(horas_pessoa)
        'count': 0,
    })

    for mo, sub, rdo, func in rows:
        key = (func.id, sub.subatividade_mestre_id)
        h = mo.horas_trabalhadas or 0.0
        p = mo.produtividade_real or 0.0
        idx = mo.indice_produtividade or 0.0

        entry = agg[key]
        entry['func_nome'] = func.nome
        entry['sub_nome'] = sub.nome_subatividade
        entry['sub_mestre_id'] = sub.subatividade_mestre_id
        entry['meta'] = sub.meta_produtividade_snapshot
        entry['unidade'] = sub.unidade_medida_snapshot or ''
        entry['soma_prod_pond'] += p * h
        entry['soma_indice_pond'] += idx * h
        entry['total_horas'] += h
        entry['count'] += 1

    # ── Média da empresa por subatividade_mestre ───────────────────────────
    # media_empresa[sub_mestre_id] = Σ(quantidade) / Σ(horas_totais_equipe_por_dia)
    empresa_by_sub = defaultdict(lambda: {'total_qtd': 0.0, 'total_horas': 0.0})
    for d in rdo_sub_totais.values():
        k = d['sub_mestre_id']
        if k is None:
            continue
        empresa_by_sub[k]['total_qtd'] += d['quantidade']
        empresa_by_sub[k]['total_horas'] += d['horas_totais']

    media_empresa: dict = {
        str(sid): round(e['total_qtd'] / e['total_horas'], 3)
        for sid, e in empresa_by_sub.items()
        if e['total_horas'] > 0
    }

    # ── Montar ranking ─────────────────────────────────────────────────────
    ranking = []
    for (fid, sid), e in agg.items():
        h = e['total_horas']
        prod_pond = round(e['soma_prod_pond'] / h, 3) if h > 0 else 0.0
        indice_pond = round(e['soma_indice_pond'] / h, 3) if h > 0 else 0.0
        if indice_pond >= 1.0:
            badge = 'success'
        elif indice_pond >= 0.8:
            badge = 'warning'
        else:
            badge = 'danger'
        sub_mestre_str = str(sid) if sid else None
        media_emp = media_empresa.get(sub_mestre_str)
        # badge_vs_empresa: compara prod ponderada do funcionário vs média empresa
        if media_emp and media_emp > 0:
            ratio = prod_pond / media_emp
            if ratio >= 1.0:
                badge_empresa = 'success'
            elif ratio >= 0.85:
                badge_empresa = 'warning'
            else:
                badge_empresa = 'danger'
        else:
            ratio = None
            badge_empresa = 'secondary'
        ranking.append({
            'funcionario_id': fid,
            'funcionario': e['func_nome'],
            'subatividade': e['sub_nome'],
            'sub_mestre_id': sid,
            'meta': e['meta'],
            'unidade': e['unidade'],
            'total_horas': round(h, 1),
            'prod_media': prod_pond,
            'indice_medio': indice_pond,
            'media_empresa': media_emp,
            'ratio_empresa': round(ratio, 3) if ratio is not None else None,
            'badge': badge,
            'badge_empresa': badge_empresa,
            'registros': e['count'],
        })
    ranking.sort(key=lambda x: x['indice_medio'], reverse=True)

    # ── Gráfico de barras ─────────────────────────────────────────────────
    barra_labels = [r['funcionario'] for r in ranking]
    barra_prod = [r['prod_media'] for r in ranking]
    metas_distintas = {r['meta'] for r in ranking if r['meta'] is not None}
    meta_ref = metas_distintas.pop() if len(metas_distintas) == 1 else None
    # Média empresa no gráfico de barras: só faz sentido quando há uma única subatividade
    medias_empresa_distintas = {r['media_empresa'] for r in ranking if r['media_empresa'] is not None}
    media_empresa_ref = medias_empresa_distintas.pop() if len(medias_empresa_distintas) == 1 else None

    # ── Gráfico de linha: evolução diária da prod média (ponderada) ────────
    # Por dia: Σ(prod_real × horas) / Σ(horas) — para a seleção de filtros
    dia_agg = defaultdict(lambda: {'soma_pond': 0.0, 'soma_horas': 0.0})
    for mo, sub, rdo, func in rows:
        d = str(rdo.data_relatorio)
        h = mo.horas_trabalhadas or 0.0
        if mo.produtividade_real is not None and h > 0:
            dia_agg[d]['soma_pond'] += mo.produtividade_real * h
            dia_agg[d]['soma_horas'] += h

    linha_labels = sorted(dia_agg.keys())
    linha_valores = [
        round(dia_agg[d]['soma_pond'] / dia_agg[d]['soma_horas'], 3)
        if dia_agg[d]['soma_horas'] > 0 else 0
        for d in linha_labels
    ]

    # ── Agregação mensal para gráfico de evolução no perfil do funcionário ─
    mensal_agg = defaultdict(lambda: {'soma_pond': 0.0, 'soma_horas': 0.0})
    for mo, sub, rdo, func in rows:
        mes = rdo.data_relatorio.strftime('%Y-%m')
        h = mo.horas_trabalhadas or 0.0
        if mo.produtividade_real is not None and h > 0:
            mensal_agg[mes]['soma_pond'] += mo.produtividade_real * h
            mensal_agg[mes]['soma_horas'] += h

    mensal_labels = sorted(mensal_agg.keys())
    mensal_valores = [
        round(mensal_agg[m]['soma_pond'] / mensal_agg[m]['soma_horas'], 3)
        if mensal_agg[m]['soma_horas'] > 0 else 0
        for m in mensal_labels
    ]

    # ── Cards de resumo ───────────────────────────────────────────────────
    melhor = ranking[0] if ranking else None
    pior = ranking[-1] if ranking else None
    indices = [r['indice_medio'] for r in ranking if r['indice_medio'] > 0]
    media_equipe = round(sum(indices) / len(indices), 3) if indices else None

    return jsonify({
        'status': 'ok',
        'ranking': ranking,
        'media_empresa': media_empresa,
        'barra': {
            'labels': barra_labels,
            'prod': barra_prod,
            'meta': meta_ref,
            'media_empresa': media_empresa_ref,
        },
        'mensal': {
            'labels': mensal_labels,
            'valores': mensal_valores,
        },
        'linha': {
            'labels': linha_labels,
            'valores': linha_valores,
            'meta': meta_ref,
        },
        'resumo': {
            'melhor': melhor,
            'pior': pior,
            'media_equipe': media_equipe,
            'total_registros': len(rows),
        },
    })
