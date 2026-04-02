"""
Reembolsos V2 — CRUD completo de reembolsos para funcionários
Blueprint: /reembolso
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal
from app import db
from models import ReembolsoFuncionario, Funcionario, Obra, GestaoCustoPai
from multitenant_helper import get_admin_id
from utils.tenant import is_v2_active
import logging

logger = logging.getLogger(__name__)

reembolso_bp = Blueprint('reembolso', __name__, url_prefix='/reembolso')


def _guard():
    if not is_v2_active():
        flash('Este módulo está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main_bp.dashboard'))
    return None


# ──────────────────────────────────────────────────────────
# LISTAR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/')
@login_required
def index():
    g = _guard()
    if g:
        return g

    admin_id = get_admin_id()

    # Filtros
    status = request.args.get('status')          # pendente | pago
    func_id = request.args.get('funcionario_id', type=int)
    obra_id = request.args.get('obra_id', type=int)

    q = ReembolsoFuncionario.query.filter_by(admin_id=admin_id)
    if func_id:
        q = q.filter_by(funcionario_id=func_id)
    if obra_id:
        q = q.filter_by(obra_id=obra_id)

    reembolsos = q.order_by(ReembolsoFuncionario.data_despesa.desc()).all()

    # Totais
    total_valor = sum(float(r.valor) for r in reembolsos)

    funcionarios = (Funcionario.query
                    .filter_by(admin_id=admin_id, ativo=True)
                    .order_by(Funcionario.nome).all())
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    return render_template(
        'reembolsos/index.html',
        reembolsos=reembolsos,
        funcionarios=funcionarios,
        obras=obras,
        total_valor=total_valor,
        filtro_func=func_id,
        filtro_obra=obra_id,
    )


# ──────────────────────────────────────────────────────────
# CRIAR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    g = _guard()
    if g:
        return g

    admin_id = get_admin_id()
    funcionarios = (Funcionario.query
                    .filter_by(admin_id=admin_id, ativo=True)
                    .order_by(Funcionario.nome).all())
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    if request.method == 'POST':
        try:
            func_id = request.form.get('funcionario_id', type=int)
            if not func_id:
                flash('Selecione um funcionário.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       reembolso=None)

            # Validação multi-tenant: garante que funcionario_id pertence ao mesmo admin
            funcionario = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
            if not funcionario:
                flash('Funcionário inválido.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       reembolso=None)

            valor_str = request.form.get('valor', '0').replace(',', '.')
            valor = Decimal(valor_str)
            if valor <= 0:
                flash('Valor deve ser maior que zero.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       reembolso=None)

            data_str = request.form.get('data_despesa')
            data_despesa = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()

            descricao = request.form.get('descricao', '').strip()
            if not descricao:
                flash('Descrição é obrigatória.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       reembolso=None)

            obra_id_raw = request.form.get('obra_id', type=int)
            obra_id = None
            if obra_id_raw:
                obra = Obra.query.filter_by(id=obra_id_raw, admin_id=admin_id).first()
                if obra:
                    obra_id = obra_id_raw

            reembolso = ReembolsoFuncionario(
                funcionario_id=func_id,
                valor=valor,
                data_despesa=data_despesa,
                descricao=descricao,
                obra_id=obra_id,
                admin_id=admin_id,
            )
            db.session.add(reembolso)

            # Criar GestaoCustoPai automaticamente para integrar ao fluxo de aprovação
            gcp = GestaoCustoPai(
                tipo_categoria='REEMBOLSO',
                entidade_nome=funcionario.nome,
                entidade_id=func_id,
                valor_total=valor,
                valor_solicitado=valor,
                status='PENDENTE',
                admin_id=admin_id,
                observacoes=f'Reembolso: {descricao}',
            )
            db.session.add(gcp)
            db.session.flush()
            reembolso.origem_tabela = 'gestao_custo_pai'
            reembolso.origem_id = gcp.id

            db.session.commit()
            flash('Reembolso registrado com sucesso!', 'success')
            return redirect(url_for('reembolso.index'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Criar reembolso: {e}")
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('reembolsos/form.html',
                           funcionarios=funcionarios, obras=obras,
                           reembolso=None)


# ──────────────────────────────────────────────────────────
# EDITAR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/<int:reembolso_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(reembolso_id):
    g = _guard()
    if g:
        return g

    admin_id = get_admin_id()
    reembolso = ReembolsoFuncionario.query.filter_by(id=reembolso_id, admin_id=admin_id).first_or_404()

    funcionarios = (Funcionario.query
                    .filter_by(admin_id=admin_id, ativo=True)
                    .order_by(Funcionario.nome).all())
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    if request.method == 'POST':
        try:
            valor_str = request.form.get('valor', '0').replace(',', '.')
            valor = Decimal(valor_str)
            if valor <= 0:
                flash('Valor deve ser maior que zero.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       reembolso=reembolso)

            data_str = request.form.get('data_despesa')
            reembolso.data_despesa = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else reembolso.data_despesa
            reembolso.valor = valor
            reembolso.descricao = request.form.get('descricao', '').strip()

            obra_id_raw = request.form.get('obra_id', type=int)
            reembolso.obra_id = None
            if obra_id_raw:
                obra = Obra.query.filter_by(id=obra_id_raw, admin_id=admin_id).first()
                if obra:
                    reembolso.obra_id = obra_id_raw

            # Atualizar GestaoCustoPai associado se existir
            if reembolso.origem_tabela == 'gestao_custo_pai' and reembolso.origem_id:
                gcp = GestaoCustoPai.query.filter_by(id=reembolso.origem_id, admin_id=admin_id).first()
                if gcp and gcp.status == 'PENDENTE':
                    gcp.valor_total = valor
                    gcp.valor_solicitado = valor
                    gcp.observacoes = f'Reembolso: {reembolso.descricao}'

            db.session.commit()
            flash('Reembolso atualizado com sucesso!', 'success')
            return redirect(url_for('reembolso.index'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Editar reembolso {reembolso_id}: {e}")
            flash(f'Erro ao atualizar: {e}', 'danger')

    return render_template('reembolsos/form.html',
                           funcionarios=funcionarios, obras=obras,
                           reembolso=reembolso)


# ──────────────────────────────────────────────────────────
# EXCLUIR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/<int:reembolso_id>/excluir', methods=['POST'])
@login_required
def excluir(reembolso_id):
    g = _guard()
    if g:
        return redirect(url_for('reembolso.index'))

    admin_id = get_admin_id()
    reembolso = ReembolsoFuncionario.query.filter_by(id=reembolso_id, admin_id=admin_id).first_or_404()

    try:
        # Se existir GestaoCustoPai associado, excluir também
        if reembolso.origem_tabela == 'gestao_custo_pai' and reembolso.origem_id:
            gcp = GestaoCustoPai.query.filter_by(
                id=reembolso.origem_id, admin_id=admin_id
            ).first()
            if gcp and gcp.status == 'PENDENTE':
                db.session.delete(gcp)

        db.session.delete(reembolso)
        db.session.commit()
        flash('Reembolso excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Excluir reembolso {reembolso_id}: {e}")
        flash(f'Erro ao excluir: {e}', 'danger')

    return redirect(url_for('reembolso.index'))
