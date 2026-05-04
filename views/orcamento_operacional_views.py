"""
views/orcamento_operacional_views.py — Task #63

Blueprint do Orçamento Operacional da Obra: cópia editável separada do
orçamento de contrato, com versionamento por item.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db
from auth import admin_required
from models import (
    Obra, ObraOrcamentoOperacional, ObraOrcamentoOperacionalItem,
    ObraOrcamentoOperacionalItemVersao, OrcamentoItem,
)
from services.orcamento_operacional import (
    garantir_operacional, listar_versoes, editar_item, diff_com_original,
    atualizar_do_original,
)

logger = logging.getLogger(__name__)

orcamento_operacional_bp = Blueprint(
    'orcamento_operacional', __name__,
    url_prefix='/obra/<int:obra_id>/orcamento-operacional',
)


def _admin_id() -> int:
    return current_user.admin_id if getattr(current_user, 'admin_id', None) else current_user.id


def _parse_br_decimal(raw, default=None):
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except Exception:
        return default


def _parse_br_float(raw, default=0.0):
    if raw is None:
        return float(default)
    s = str(raw).strip()
    if not s:
        return float(default)
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except (TypeError, ValueError):
        return float(default)


def _obra_do_admin_or_404(obra_id: int) -> Obra:
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        abort(404)
    return obra


def _versoes_vigentes_por_item(op: ObraOrcamentoOperacional) -> dict:
    """Mapa item_id → versão atualmente vigente (vigente_ate IS NULL)."""
    versoes = (
        ObraOrcamentoOperacionalItemVersao.query
        .join(ObraOrcamentoOperacionalItem,
              ObraOrcamentoOperacionalItem.id == ObraOrcamentoOperacionalItemVersao.item_id)
        .filter(
            ObraOrcamentoOperacionalItem.operacional_id == op.id,
            ObraOrcamentoOperacionalItemVersao.vigente_ate.is_(None),
        )
        .all()
    )
    return {v.item_id: v for v in versoes}


@orcamento_operacional_bp.route('/', methods=['GET'])
@login_required
@admin_required
def index(obra_id: int):
    """Tela principal: lista itens operacionais editáveis + aba histórico."""
    obra = _obra_do_admin_or_404(obra_id)
    # Lazy-create: se a obra ainda não tem operacional, cria agora.
    op = garantir_operacional(obra.id, criado_por_id=current_user.id)
    # Recarrega após o flush
    op = ObraOrcamentoOperacional.query.filter_by(obra_id=obra.id).first()
    versoes_atuais = _versoes_vigentes_por_item(op) if op else {}

    # Histórico completo (todas as versões de todos os itens, ordenadas
    # por data desc) — pra a aba "Histórico".
    historico = []
    if op:
        historico = (
            db.session.query(ObraOrcamentoOperacionalItemVersao,
                              ObraOrcamentoOperacionalItem)
            .join(ObraOrcamentoOperacionalItem,
                  ObraOrcamentoOperacionalItem.id == ObraOrcamentoOperacionalItemVersao.item_id)
            .filter(ObraOrcamentoOperacionalItem.operacional_id == op.id)
            .order_by(ObraOrcamentoOperacionalItemVersao.id.desc())
            .all()
        )

    diffs = diff_com_original(obra.id) if op else []

    return render_template(
        'orcamento_operacional/index.html',
        obra=obra,
        operacional=op,
        versoes_atuais=versoes_atuais,
        historico=historico,
        diffs=diffs,
    )


@orcamento_operacional_bp.route('/item/<int:item_id>/salvar', methods=['POST'])
@login_required
@admin_required
def salvar_item(obra_id: int, item_id: int):
    """Salva a edição do item operacional com modo de aplicação escolhido."""
    obra = _obra_do_admin_or_404(obra_id)
    item = ObraOrcamentoOperacionalItem.query.get_or_404(item_id)
    op = ObraOrcamentoOperacional.query.get_or_404(item.operacional_id)
    if op.obra_id != obra.id:
        abort(404)

    modo = request.form.get('modo_aplicacao', 'a_partir_de_hoje')
    if modo not in ('a_partir_de_hoje', 'retroativo'):
        modo = 'a_partir_de_hoje'
    motivo = (request.form.get('motivo') or '').strip() or None

    # Composição (campos paralelos como no orçamento original)
    tipos = request.form.getlist('comp_tipo')
    nomes = request.form.getlist('comp_nome')
    unids = request.form.getlist('comp_unidade')
    coefs = request.form.getlist('comp_coeficiente')
    precos = request.form.getlist('comp_preco_unitario')
    ins_ids = request.form.getlist('comp_insumo_id')
    nova_comp = []
    for i in range(len(nomes)):
        nm = (nomes[i] or '').strip()
        if not nm:
            continue
        coef = _parse_br_float(coefs[i] if i < len(coefs) else 0)
        preco = _parse_br_float(precos[i] if i < len(precos) else 0)
        try:
            insumo_id = int(ins_ids[i]) if i < len(ins_ids) and ins_ids[i] else None
        except (ValueError, TypeError):
            insumo_id = None
        nova_comp.append({
            'tipo': (tipos[i] if i < len(tipos) else 'MATERIAL') or 'MATERIAL',
            'insumo_id': insumo_id,
            'nome': nm,
            'unidade': (unids[i] if i < len(unids) else 'un') or 'un',
            'coeficiente': coef,
            'preco_unitario': preco,
            'subtotal_unitario': round(coef * preco, 4),
        })

    margem = _parse_br_decimal(request.form.get('margem_pct'))
    imposto = _parse_br_decimal(request.form.get('imposto_pct'))

    try:
        editar_item(
            item_id=item.id,
            nova_composicao=nova_comp,
            nova_margem_pct=margem,
            novo_imposto_pct=imposto,
            modo=modo,
            criado_por_id=current_user.id,
            motivo=motivo,
        )
        flash(
            f'Item atualizado ({"nova versão a partir de hoje" if modo == "a_partir_de_hoje" else "aplicado retroativo"}).',
            'success',
        )
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao salvar item operacional')
        flash(f'Erro: {e}', 'error')
    return redirect(url_for('orcamento_operacional.index', obra_id=obra.id))


@orcamento_operacional_bp.route('/atualizar-do-original', methods=['POST'])
@login_required
@admin_required
def atualizar_do_original_route(obra_id: int):
    """Propaga mudanças do orçamento original pro operacional (a partir de hoje)."""
    obra = _obra_do_admin_or_404(obra_id)
    item_ids_raw = request.form.getlist('item_ids')
    # Distinguir "campo ausente" (None → propaga todos divergentes) de
    # "campo presente sem seleção" (lista vazia → 0 atualizações).
    if 'item_ids' in request.form:
        item_ids = []
        for r in item_ids_raw:
            try:
                item_ids.append(int(r))
            except (TypeError, ValueError):
                continue
    else:
        item_ids = None
    try:
        n = atualizar_do_original(
            obra_id=obra.id,
            item_ids=item_ids,
            criado_por_id=current_user.id,
        )
        if n:
            flash(f'{n} item(ns) atualizado(s) a partir do orçamento original.', 'success')
        else:
            flash('Nenhuma diferença encontrada (operacional já está alinhado com o original).', 'info')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao atualizar do original')
        flash(f'Erro: {e}', 'error')
    return redirect(url_for('orcamento_operacional.index', obra_id=obra.id))
