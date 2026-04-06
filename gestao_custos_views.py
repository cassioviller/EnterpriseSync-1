"""
gestao_custos_views.py
Blueprint V2: Gestão de Custos — hierarquia Pai/Filho + fluxo de aprovação.
Rota base: /gestao-custos
"""

import logging
from datetime import datetime, date
from decimal import Decimal

from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from models import (GestaoCustoPai, GestaoCustoFilho,
                    FluxoCaixa, Obra, TipoUsuario)
from utils.tenant import is_v2_active

logger = logging.getLogger(__name__)

gestao_custos_bp = Blueprint('gestao_custos', __name__,
                              url_prefix='/gestao-custos')

CATEGORIA_LABELS = {
    'SALARIO':        ('Pagamento Salário',    'fas fa-user-tie',     'primary'),
    'ALIMENTACAO':    ('Despesa Alimentação',  'fas fa-utensils',     'success'),
    'TRANSPORTE':     ('Despesa Transporte',   'fas fa-route',        'info'),
    'VEICULO':        ('Despesa de Frota',     'fas fa-truck',        'dark'),
    'COMPRA':         ('Compra de Material',   'fas fa-shopping-cart','warning'),
    'REEMBOLSO':      ('Reembolso a Pagar',    'fas fa-undo',         'danger'),
    'DESPESA_GERAL':  ('Despesa Geral / Avulsa','fas fa-file-invoice-dollar', 'purple'),
    'OUTROS':         ('Outros Custos',        'fas fa-receipt',      'secondary'),
}

STATUS_BADGES = {
    'PENDENTE':   'secondary',
    'SOLICITADO': 'warning',
    'AUTORIZADO': 'success',
    'PAGO':       'primary',
    'RECUSADO':   'danger',
}


def _check_v2():
    """Retorna (admin_id, None) ou (None, redirect_response) se não V2."""
    if not is_v2_active():
        flash('Módulo exclusivo da versão V2.', 'warning')
        return None, redirect(url_for('main.index'))
    admin_id = (current_user.id
                if current_user.tipo_usuario == TipoUsuario.ADMIN
                else current_user.admin_id)
    return admin_id, None


# ───────────────────────────────────────────────────────────────
# DASHBOARD / LISTAGEM
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/')
@login_required
def index():
    admin_id, err = _check_v2()
    if err:
        return err

    # Filtros
    filtro_status = request.args.get('status', '')
    filtro_categoria = request.args.get('categoria', '')
    filtro_busca = request.args.get('busca', '').strip()

    q = GestaoCustoPai.query.filter_by(admin_id=admin_id)
    if filtro_status:
        q = q.filter_by(status=filtro_status)
    if filtro_categoria:
        q = q.filter_by(tipo_categoria=filtro_categoria)
    if filtro_busca:
        q = q.filter(GestaoCustoPai.entidade_nome.ilike(f'%{filtro_busca}%'))

    registros = q.order_by(GestaoCustoPai.data_criacao.desc()).all()

    # Totais por status
    totais = (
        db.session.query(
            GestaoCustoPai.status,
            func.count(GestaoCustoPai.id),
            func.sum(GestaoCustoPai.valor_total),
        )
        .filter_by(admin_id=admin_id)
        .group_by(GestaoCustoPai.status)
        .all()
    )
    resumo = {row[0]: {'qtd': row[1], 'total': float(row[2] or 0)} for row in totais}

    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    return render_template(
        'custos/gestao.html',
        registros=registros,
        resumo=resumo,
        categoria_labels=CATEGORIA_LABELS,
        status_badges=STATUS_BADGES,
        filtro_status=filtro_status,
        filtro_categoria=filtro_categoria,
        filtro_busca=filtro_busca,
        obras=obras,
    )


# ───────────────────────────────────────────────────────────────
# LANÇAMENTO MANUAL
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    admin_id, err = _check_v2()
    if err:
        return err

    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    today = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        try:
            tipo_categoria = request.form.get('tipo_categoria', 'OUTROS')
            entidade_nome = request.form.get('entidade_nome', '').strip()
            descricao = request.form.get('descricao', '').strip()
            valor = Decimal(request.form.get('valor', '0').replace(',', '.'))
            data_ref_str = request.form.get('data_referencia')
            data_ref = datetime.strptime(data_ref_str, '%Y-%m-%d').date() if data_ref_str else date.today()
            obra_id = request.form.get('obra_id', type=int)

            # Campos extras para DESPESA_GERAL
            data_venc_str = request.form.get('data_vencimento', '').strip()
            data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None
            numero_doc = request.form.get('numero_documento', '').strip() or None

            if not entidade_nome or valor <= 0:
                flash('Entidade e valor são obrigatórios.', 'warning')
                return render_template('custos/gestao.html',
                                       modo='novo', obras=obras,
                                       categoria_labels=CATEGORIA_LABELS,
                                       status_badges=STATUS_BADGES,
                                       registros=[], resumo={})

            pai = GestaoCustoPai(
                admin_id=admin_id,
                tipo_categoria=tipo_categoria,
                entidade_nome=entidade_nome,
                entidade_id=None,
                valor_total=valor,
                status='PENDENTE',
                data_vencimento=data_venc,
                numero_documento=numero_doc,
            )
            db.session.add(pai)
            db.session.flush()

            filho = GestaoCustoFilho(
                pai_id=pai.id,
                admin_id=admin_id,
                data_referencia=data_ref,
                descricao=descricao or entidade_nome,
                valor=valor,
                obra_id=obra_id,
                origem_tabela='manual',
            )
            db.session.add(filho)
            db.session.commit()
            flash(f'Custo "{entidade_nome}" lançado com sucesso.', 'success')
            return redirect(url_for('gestao_custos.index'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao criar custo manual: {e}")
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template(
        'custos/gestao.html',
        modo='novo',
        obras=obras,
        today=today,
        categoria_labels=CATEGORIA_LABELS,
        status_badges=STATUS_BADGES,
        registros=[],
        resumo={},
    )


# ───────────────────────────────────────────────────────────────
# DETALHES / FILHOS (AJAX)
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/filhos')
@login_required
def filhos(pai_id):
    admin_id, err = _check_v2()
    if err:
        return jsonify({'status': 'error', 'message': 'V2 only'}), 403

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()
    itens = GestaoCustoFilho.query.filter_by(pai_id=pai.id).order_by(
        GestaoCustoFilho.data_referencia.asc()).all()

    return jsonify({
        'status': 'ok',
        'itens': [
            {
                'id': f.id,
                'data': f.data_referencia.strftime('%d/%m/%Y'),
                'descricao': f.descricao,
                'valor': float(f.valor),
                'obra': f.obra.nome if f.obra else '—',
                'origem': f.origem_tabela or '—',
            }
            for f in itens
        ],
    })


# ───────────────────────────────────────────────────────────────
# SOLICITAR PAGAMENTO   PENDENTE → SOLICITADO
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/solicitar', methods=['POST'])
@login_required
def solicitar(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()

    if pai.status != 'PENDENTE':
        flash('Apenas registros PENDENTES podem ser solicitados.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    try:
        valor_sol_str = request.form.get('valor_solicitado', '').replace(',', '.')
        valor_sol = Decimal(valor_sol_str) if valor_sol_str else pai.valor_total
        pai.valor_solicitado = valor_sol
        pai.status = 'SOLICITADO'
        db.session.commit()
        flash(f'Pagamento de R$ {valor_sol:,.2f} solicitado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] solicitar pagamento: {e}")
        flash(f'Erro: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


# ───────────────────────────────────────────────────────────────
# AUTORIZAR / RECUSAR    SOLICITADO → AUTORIZADO / PENDENTE
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/autorizar', methods=['POST'])
@login_required
def autorizar(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()

    if pai.status != 'SOLICITADO':
        flash('Apenas registros SOLICITADOS podem ser autorizados.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    acao = request.form.get('acao', 'autorizar')

    if acao == 'recusar':
        pai.status = 'PENDENTE'
        pai.valor_solicitado = None
        db.session.commit()
        flash('Solicitação recusada. Status voltou para PENDENTE.', 'info')
        return redirect(url_for('gestao_custos.index'))

    try:
        pai.status = 'AUTORIZADO'
        db.session.commit()
        flash(f'Pagamento de R$ {float(pai.valor_solicitado or pai.valor_total):,.2f} autorizado. Aguardando efetivação pelo financeiro.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] autorizar pagamento: {e}", exc_info=True)
        flash(f'Erro ao autorizar: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


# ───────────────────────────────────────────────────────────────
# EFETIVAR PAGAMENTO    AUTORIZADO → PAGO
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/pagar', methods=['POST'])
@login_required
def pagar(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()

    if pai.status != 'AUTORIZADO':
        flash('Apenas registros AUTORIZADOS podem ser efetivados como pagos.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    try:
        data_pgto_str = request.form.get('data_pagamento', '')
        data_pgto = (datetime.strptime(data_pgto_str, '%Y-%m-%d').date()
                     if data_pgto_str else date.today())
        conta = request.form.get('conta_bancaria', '').strip()
        valor_pago = Decimal(str(request.form.get('valor_pago', '') or pai.valor_solicitado or pai.valor_total)
                             .replace(',', '.'))

        # Mapear categoria → categoria FluxoCaixa
        cat_mapa = {
            'SALARIO':     'salario',
            'ALIMENTACAO': 'alimentacao',
            'TRANSPORTE':  'custo_obra',
            'VEICULO':     'custo_obra',
            'COMPRA':      'custo_obra',
            'REEMBOLSO':   'custo_obra',
            'OUTROS':      'custo_obra',
        }
        cat_fc = cat_mapa.get(pai.tipo_categoria, 'custo_obra')
        label = CATEGORIA_LABELS.get(pai.tipo_categoria, ('Custo',))[0]

        # Criar FluxoCaixa
        fc = FluxoCaixa(
            admin_id=admin_id,
            data_movimento=data_pgto,
            tipo_movimento='SAIDA',
            categoria=cat_fc,
            valor=float(valor_pago),
            descricao=f'{label} — {pai.entidade_nome}',
            referencia_id=pai.id,
            referencia_tabela='gestao_custo_pai',
            observacoes=conta or None,
        )
        db.session.add(fc)
        db.session.flush()

        pai.status = 'PAGO'
        pai.data_pagamento = data_pgto
        pai.conta_bancaria = conta
        pai.fluxo_caixa_id = fc.id
        db.session.commit()

        # Lançamento contábil (opcional, V2)
        try:
            from contabilidade_utils import gerar_lancamento_contabil_automatico
            gerar_lancamento_contabil_automatico(
                admin_id=admin_id,
                tipo_operacao='DESPESA_GERAL',
                valor=float(valor_pago),
                data=data_pgto,
                descricao=f'{label} — {pai.entidade_nome}',
            )
        except Exception as e_cont:
            logger.warning(f"[WARN] Lançamento contábil falhou (não crítico): {e_cont}")

        flash(f'Pagamento de R$ {valor_pago:,.2f} efetivado e registrado no Fluxo de Caixa.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] efetivar pagamento: {e}", exc_info=True)
        flash(f'Erro ao pagar: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


# ───────────────────────────────────────────────────────────────
# EXCLUIR PAI (apenas PENDENTE)
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/excluir', methods=['POST'])
@login_required
def excluir(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()
    if pai.status not in ('PENDENTE', 'RECUSADO'):
        flash('Apenas registros PENDENTES ou RECUSADOS podem ser excluídos.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    try:
        db.session.delete(pai)
        db.session.commit()
        flash('Registro excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))
