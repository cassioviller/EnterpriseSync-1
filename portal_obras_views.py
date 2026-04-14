"""
Blueprint: Portal do Cliente por Obra
Acesso público via token — sem login necessário.
Permite que o cliente acompanhe progresso, aprove/rejeite compras
e envie comprovantes de pagamento.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import date, datetime

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from models import (
    db, Obra, TarefaCronograma, PedidoCompra, PedidoCompraItem,
    MedicaoObra, Fornecedor, ConfiguracaoEmpresa,
)

logger = logging.getLogger(__name__)

portal_obras_bp = Blueprint(
    'portal_obras', __name__, url_prefix='/portal'
)

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'comprovantes')


def _ensure_upload_folder():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _get_obra_by_token(token: str) -> Obra:
    obra = Obra.query.filter_by(token_cliente=token, portal_ativo=True).first()
    if not obra:
        abort(404)
    return obra


@portal_obras_bp.route('/obra/<token>')
def portal_obra(token: str):
    obra = _get_obra_by_token(token)

    obra.ultima_visualizacao_cliente = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    admin_id = obra.admin_id

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    total_tarefas = len(tarefas)
    if total_tarefas > 0:
        perc_geral = sum(t.percentual_concluido or 0 for t in tarefas) / total_tarefas
    else:
        perc_geral = 0.0

    compras = (
        PedidoCompra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .order_by(PedidoCompra.created_at.desc())
        .all()
    )

    medicoes = (
        MedicaoObra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .order_by(MedicaoObra.numero.desc())
        .all()
    )

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config.nome_empresa if config else 'Construtora'

    return render_template(
        'portal/portal_obra.html',
        obra=obra,
        tarefas=tarefas,
        perc_geral=round(perc_geral, 1),
        compras=compras,
        medicoes=medicoes,
        nome_empresa=nome_empresa,
        hoje=date.today(),
    )


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/aprovar', methods=['POST'])
def aprovar_compra(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()
    compra.status_aprovacao_cliente = 'APROVADO'
    db.session.commit()
    logger.info(f"[PORTAL] Compra {compra_id} APROVADA pelo cliente — obra {obra.id}")
    flash('Compra aprovada com sucesso!', 'success')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/rejeitar', methods=['POST'])
def rejeitar_compra(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()
    compra.status_aprovacao_cliente = 'REJEITADO'
    db.session.commit()
    logger.info(f"[PORTAL] Compra {compra_id} REJEITADA pelo cliente — obra {obra.id}")
    flash('Compra rejeitada.', 'warning')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/comprovante', methods=['POST'])
def upload_comprovante(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()

    arquivo = request.files.get('comprovante')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    _ensure_upload_folder()
    ext = os.path.splitext(arquivo.filename)[1].lower()
    nome_seguro = f"comprovante_{compra_id}_{secrets.token_hex(6)}{ext}"
    caminho = os.path.join(UPLOAD_FOLDER, nome_seguro)
    arquivo.save(caminho)

    compra.comprovante_pagamento_url = '/' + caminho.replace('\\', '/')
    db.session.commit()
    logger.info(f"[PORTAL] Comprovante enviado para compra {compra_id} — obra {obra.id}")
    flash('Comprovante enviado com sucesso!', 'success')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<int:obra_id>/medicao/gerar', methods=['POST'])
@login_required
def gerar_medicao(obra_id: int):
    from utils.tenant import get_tenant_admin_id
    admin_id = get_tenant_admin_id()

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    ultima = (
        MedicaoObra.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(MedicaoObra.numero.desc())
        .first()
    )
    proximo_numero = (ultima.numero + 1) if ultima else 1

    data_inicio_med = date.today().replace(day=1)
    if date.today().day <= 15:
        data_fim_med = date.today().replace(day=15)
    else:
        import calendar
        ultimo_dia = calendar.monthrange(date.today().year, date.today().month)[1]
        data_fim_med = date.today().replace(day=ultimo_dia)

    tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()
    total = len(tarefas)
    perc = (sum(t.percentual_concluido or 0 for t in tarefas) / total) if total else 0.0

    valor_medido = 0
    if obra.valor_contrato and obra.valor_contrato > 0:
        perc_anterior = ultima.percentual_acumulado if ultima else 0
        delta = max(0, perc - perc_anterior)
        valor_medido = round(float(obra.valor_contrato) * delta / 100, 2)

    med = MedicaoObra(
        obra_id=obra_id,
        numero=proximo_numero,
        data_inicio=data_inicio_med,
        data_fim=data_fim_med,
        percentual_acumulado=round(perc, 2),
        valor_medido=valor_medido,
        status='RASCUNHO',
        admin_id=admin_id,
    )
    db.session.add(med)
    db.session.commit()
    logger.info(f"[MEDICAO] #{proximo_numero} gerada para obra {obra_id}")
    flash(f'Medição #{proximo_numero} gerada com sucesso!', 'success')
    return redirect(url_for('main.detalhes_obra', id=obra_id))
