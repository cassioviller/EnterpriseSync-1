from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from models import Fornecedor
from sqlalchemy import or_
import logging

from views.almoxarifado import almoxarifado_bp, get_admin_id

logger = logging.getLogger(__name__)


@almoxarifado_bp.route('/fornecedores')
@login_required
def fornecedores():
    """Lista todos os fornecedores ativos"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    busca = request.args.get('busca', '').strip()

    query = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True)

    if busca:
        query = query.filter(
            or_(
                Fornecedor.razao_social.ilike(f'%{busca}%'),
                Fornecedor.nome_fantasia.ilike(f'%{busca}%'),
                Fornecedor.cnpj.ilike(f'%{busca}%')
            )
        )

    fornecedores = query.order_by(Fornecedor.razao_social).all()

    return render_template('almoxarifado/fornecedores.html',
                           fornecedores=fornecedores,
                           busca=busca)


@almoxarifado_bp.route('/fornecedores/criar', methods=['GET', 'POST'])
@login_required
def fornecedores_criar():
    """Criar novo fornecedor"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        try:
            razao_social = request.form.get('razao_social', '').strip()
            nome_fantasia = request.form.get('nome_fantasia', '').strip()
            cnpj = request.form.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '').strip()
            inscricao_estadual = request.form.get('inscricao_estadual', '').strip()

            endereco = request.form.get('endereco', '').strip()
            cidade = request.form.get('cidade', '').strip()
            estado = request.form.get('estado', '').strip()
            cep = request.form.get('cep', '').replace('-', '').strip()

            telefone = request.form.get('telefone', '').strip()
            email = request.form.get('email', '').strip()
            contato_responsavel = request.form.get('contato_responsavel', '').strip()

            if not razao_social:
                flash('Razão Social é obrigatória', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_criar'))

            if not cnpj:
                flash('CNPJ é obrigatório', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_criar'))

            existe = Fornecedor.query.filter_by(cnpj=cnpj, admin_id=admin_id).first()
            if existe:
                flash(f'Já existe um fornecedor cadastrado com o CNPJ {cnpj}', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_criar'))

            tipo_fornecedor = request.form.get('tipo_fornecedor', 'OUTRO').strip()
            if tipo_fornecedor not in ('MATERIAL', 'PRESTADOR_SERVICO', 'OUTRO'):
                tipo_fornecedor = 'OUTRO'

            chave_pix = request.form.get('chave_pix', '').strip()

            fornecedor = Fornecedor(
                nome=razao_social,
                razao_social=razao_social,
                nome_fantasia=nome_fantasia or None,
                cnpj=cnpj,
                inscricao_estadual=inscricao_estadual or None,
                endereco=endereco or None,
                cidade=cidade or None,
                estado=estado or None,
                cep=cep or None,
                telefone=telefone or None,
                email=email or None,
                contato_responsavel=contato_responsavel or None,
                tipo_fornecedor=tipo_fornecedor,
                chave_pix=chave_pix or None,
                admin_id=admin_id
            )

            db.session.add(fornecedor)
            db.session.commit()

            flash(f'Fornecedor "{razao_social}" cadastrado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.fornecedores'))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar fornecedor: {str(e)}')
            flash(f'Erro ao cadastrar fornecedor: {str(e)}', 'danger')
            return redirect(url_for('almoxarifado.fornecedores_criar'))

    return render_template('almoxarifado/fornecedores_form.html', fornecedor=None)


@almoxarifado_bp.route('/fornecedores/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def fornecedores_editar(id):
    """Editar fornecedor existente"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    fornecedor = Fornecedor.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        try:
            razao_social = request.form.get('razao_social', '').strip()
            nome_fantasia = request.form.get('nome_fantasia', '').strip()
            cnpj = request.form.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '').strip()
            inscricao_estadual = request.form.get('inscricao_estadual', '').strip()

            endereco = request.form.get('endereco', '').strip()
            cidade = request.form.get('cidade', '').strip()
            estado = request.form.get('estado', '').strip()
            cep = request.form.get('cep', '').replace('-', '').strip()

            telefone = request.form.get('telefone', '').strip()
            email = request.form.get('email', '').strip()
            contato_responsavel = request.form.get('contato_responsavel', '').strip()

            if not razao_social:
                flash('Razão Social é obrigatória', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_editar', id=id))

            if not cnpj:
                flash('CNPJ é obrigatório', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_editar', id=id))

            existe = Fornecedor.query.filter(
                Fornecedor.cnpj == cnpj,
                Fornecedor.admin_id == admin_id,
                Fornecedor.id != id
            ).first()
            if existe:
                flash(f'Já existe outro fornecedor cadastrado com o CNPJ {cnpj}', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_editar', id=id))

            tipo_fornecedor = request.form.get('tipo_fornecedor', 'OUTRO').strip()
            if tipo_fornecedor not in ('MATERIAL', 'PRESTADOR_SERVICO', 'OUTRO'):
                tipo_fornecedor = 'OUTRO'

            fornecedor.nome = razao_social
            fornecedor.razao_social = razao_social
            fornecedor.nome_fantasia = nome_fantasia or None
            fornecedor.cnpj = cnpj
            fornecedor.inscricao_estadual = inscricao_estadual or None
            fornecedor.endereco = endereco or None
            fornecedor.cidade = cidade or None
            fornecedor.estado = estado or None
            fornecedor.cep = cep or None
            fornecedor.telefone = telefone or None
            fornecedor.email = email or None
            fornecedor.contato_responsavel = contato_responsavel or None
            fornecedor.tipo_fornecedor = tipo_fornecedor
            fornecedor.chave_pix = request.form.get('chave_pix', '').strip() or None

            db.session.commit()

            flash(f'Fornecedor "{razao_social}" atualizado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.fornecedores'))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar fornecedor: {str(e)}')
            flash(f'Erro ao atualizar fornecedor: {str(e)}', 'danger')

    return render_template('almoxarifado/fornecedores_form.html', fornecedor=fornecedor)


@almoxarifado_bp.route('/fornecedores/deletar/<int:id>', methods=['POST'])
@login_required
def fornecedores_deletar(id):
    """Desativar fornecedor (soft delete)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    fornecedor = Fornecedor.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    try:
        from datetime import datetime as _dt
        fornecedor.ativo = False
        fornecedor.updated_at = _dt.utcnow()
        db.session.commit()
        flash(f'Fornecedor "{fornecedor.razao_social}" desativado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao desativar fornecedor: {str(e)}')
        flash('Erro ao desativar fornecedor', 'danger')

    return redirect(url_for('almoxarifado.fornecedores'))
