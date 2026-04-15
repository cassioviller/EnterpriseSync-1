"""
Blueprint: Portal do Cliente por Obra
Acesso público via token — sem login necessário.
Permite que o cliente acompanhe progresso, aprove/recuse compras
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
    MedicaoObra, Fornecedor, ConfiguracaoEmpresa, RDO,
    RDOFoto, RDOServicoSubatividade, RDOMaoObra, RDOEquipamento, RDOOcorrencia,
    MapaConcorrencia, OpcaoConcorrencia,
)

logger = logging.getLogger(__name__)

portal_obras_bp = Blueprint(
    'portal_obras', __name__, url_prefix='/portal'
)

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'comprovantes')
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf'}


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

    compras_pendentes = (
        PedidoCompra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .filter(
            db.or_(
                PedidoCompra.status_aprovacao_cliente == 'PENDENTE',
                PedidoCompra.status_aprovacao_cliente.is_(None),
            )
        )
        .order_by(PedidoCompra.created_at.desc())
        .all()
    )

    compras_resolvidas = (
        PedidoCompra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .filter(PedidoCompra.status_aprovacao_cliente.in_(['APROVADO', 'RECUSADO']))
        .order_by(PedidoCompra.created_at.desc())
        .all()
    )

    rdos = (
        RDO.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, status='Finalizado')
        .order_by(RDO.data_relatorio.desc())
        .limit(20)
        .all()
    )

    medicoes = (
        MedicaoObra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .order_by(MedicaoObra.numero.desc())
        .all()
    )

    from models import ContaReceber
    medicao_contas = {}
    for m in medicoes:
        if m.conta_receber_id:
            cr = ContaReceber.query.get(m.conta_receber_id)
            if cr:
                medicao_contas[m.id] = cr

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config.nome_empresa if config else 'Construtora'

    mapas_pendentes = (
        MapaConcorrencia.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, status='pendente')
        .order_by(MapaConcorrencia.created_at.desc())
        .all()
    )
    mapas_concluidos = (
        MapaConcorrencia.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, status='concluido')
        .order_by(MapaConcorrencia.created_at.desc())
        .all()
    )
    for m in mapas_pendentes + mapas_concluidos:
        m._opcoes_list = m.opcoes.all()

    return render_template(
        'portal/portal_obra.html',
        obra=obra,
        tarefas=tarefas,
        perc_geral=round(perc_geral, 1),
        compras_pendentes=compras_pendentes,
        compras_resolvidas=compras_resolvidas,
        rdos=rdos,
        medicoes=medicoes,
        medicao_contas=medicao_contas,
        nome_empresa=nome_empresa,
        hoje=date.today(),
        mapas_pendentes=mapas_pendentes,
        mapas_concluidos=mapas_concluidos,
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


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/recusar', methods=['POST'])
def recusar_compra(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()
    compra.status_aprovacao_cliente = 'RECUSADO'
    db.session.commit()
    logger.info(f"[PORTAL] Compra {compra_id} RECUSADA pelo cliente — obra {obra.id}")
    flash('Compra recusada.', 'warning')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/comprovante', methods=['POST'])
def upload_comprovante(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()

    if compra.status_aprovacao_cliente != 'APROVADO':
        flash('Comprovante só pode ser enviado para compras aprovadas.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    arquivo = request.files.get('comprovante')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    ext = os.path.splitext(arquivo.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash('Tipo de arquivo não permitido. Envie imagem ou PDF.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    _ensure_upload_folder()
    nome_seguro = f"comprovante_{compra_id}_{secrets.token_hex(6)}{ext}"
    caminho = os.path.join(UPLOAD_FOLDER, nome_seguro)
    arquivo.save(caminho)

    compra.comprovante_pagamento_url = '/' + caminho.replace('\\', '/')
    db.session.commit()
    logger.info(f"[PORTAL] Comprovante enviado para compra {compra_id} — obra {obra.id}")
    flash('Comprovante enviado com sucesso!', 'success')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/mapa/<int:mapa_id>/aprovar', methods=['POST'])
def aprovar_mapa_concorrencia(token: str, mapa_id: int):
    """O cliente seleciona a opção preferida no Mapa de Concorrência."""
    obra = _get_obra_by_token(token)
    mapa = MapaConcorrencia.query.filter_by(
        id=mapa_id, obra_id=obra.id, admin_id=obra.admin_id
    ).first_or_404()

    if mapa.status != 'pendente':
        flash('Este mapa de concorrência já foi concluído e não pode ser alterado.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    opcao_id = request.form.get('opcao_id', type=int)
    if not opcao_id:
        flash('Selecione uma opção de fornecedor.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    opcao = OpcaoConcorrencia.query.filter_by(id=opcao_id, mapa_id=mapa.id).first()
    if not opcao:
        flash('Opção não encontrada.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    for op in mapa.opcoes.all():
        op.selecionada = False

    opcao.selecionada = True
    mapa.status = 'concluido'
    try:
        db.session.commit()
        logger.info(f"[PORTAL] Mapa {mapa_id} aprovado pelo cliente — opção {opcao_id}, obra {obra.id}")
        flash(f'Fornecedor "{opcao.fornecedor_nome}" selecionado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PORTAL] Erro ao aprovar mapa {mapa_id}: {e}")
        flash('Erro ao registrar aprovação. Tente novamente.', 'danger')

    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<int:obra_id>/portal-toggle', methods=['POST'])
@login_required
def toggle_portal(obra_id: int):
    from utils.tenant import get_tenant_admin_id
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    obra.portal_ativo = not obra.portal_ativo

    if obra.portal_ativo and not obra.token_cliente:
        obra.token_cliente = secrets.token_urlsafe(32)

    db.session.commit()
    status = 'ativado' if obra.portal_ativo else 'desativado'
    logger.info(f"[PORTAL] Portal {status} para obra {obra_id}")
    flash(f'Portal do cliente {status}.', 'success')
    return redirect(url_for('main.detalhes_obra', id=obra_id))


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

    if date.today().day <= 15:
        data_inicio_med = date.today().replace(day=1)
        data_fim_med = date.today().replace(day=15)
    else:
        import calendar
        data_inicio_med = date.today().replace(day=16)
        ultimo_dia = calendar.monthrange(date.today().year, date.today().month)[1]
        data_fim_med = date.today().replace(day=ultimo_dia)

    tarefas_empresa = TarefaCronograma.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, responsavel='empresa'
    ).all()

    total = len(tarefas_empresa)
    perc = (sum(t.percentual_concluido or 0 for t in tarefas_empresa) / total) if total else 0.0

    valor_medido = 0
    if obra.valor_contrato and obra.valor_contrato > 0:
        valor_medido = round(float(obra.valor_contrato) * perc / 100, 2)

    med = MedicaoObra(
        obra_id=obra_id,
        numero=proximo_numero,
        data_medicao=date.today(),
        data_inicio=data_inicio_med,
        data_fim=data_fim_med,
        periodo_inicio=data_inicio_med,
        periodo_fim=data_fim_med,
        percentual_executado=round(perc, 2),
        valor_medido=valor_medido,
        status='PENDENTE',
        admin_id=admin_id,
    )
    db.session.add(med)
    db.session.commit()
    logger.info(f"[MEDICAO] #{proximo_numero} gerada para obra {obra_id}")
    flash(f'Medição #{proximo_numero} gerada com sucesso!', 'success')
    return redirect(url_for('main.detalhes_obra', id=obra_id))


@portal_obras_bp.route('/obra/<token>/rdo/<int:rdo_id>')
def portal_rdo_detalhe(token: str, rdo_id: int):
    obra = _get_obra_by_token(token)
    admin_id = obra.admin_id

    rdo = RDO.query.filter_by(id=rdo_id, obra_id=obra.id, admin_id=admin_id).first()
    if not rdo:
        abort(404)

    fotos = RDOFoto.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).order_by(RDOFoto.ordem).all()
    subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).order_by(RDOServicoSubatividade.ordem_execucao).all()
    mao_obra = RDOMaoObra.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()
    equipamentos = RDOEquipamento.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()
    ocorrencias = RDOOcorrencia.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config.nome_empresa if config else 'Construtora'

    return render_template(
        'portal/portal_rdo_detalhe.html',
        obra=obra,
        rdo=rdo,
        fotos=fotos,
        subatividades=subatividades,
        mao_obra=mao_obra,
        equipamentos=equipamentos,
        ocorrencias=ocorrencias,
        nome_empresa=nome_empresa,
        token=token,
    )
