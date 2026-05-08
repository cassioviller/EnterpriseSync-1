<<<<<<< HEAD
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from datetime import datetime
import logging
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem
from . import almoxarifado_bp, get_admin_id
=======
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem
from datetime import datetime
import logging

from views.almoxarifado import almoxarifado_bp, get_admin_id
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

logger = logging.getLogger(__name__)


@almoxarifado_bp.route('/categorias')
@login_required
def categorias():
    """Lista todas as categorias do almoxarifado"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/categorias.html', categorias=categorias)

=======

    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/categorias.html', categorias=categorias)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/categorias/criar', methods=['GET', 'POST'])
@login_required
def categorias_criar():
    """Criar nova categoria"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo_controle_padrao = request.form.get('tipo_controle_padrao')
            permite_devolucao_padrao = request.form.get('permite_devolucao_padrao') == 'on'
<<<<<<< HEAD
            
            # Validações
            if not nome or not tipo_controle_padrao:
                flash('Nome e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.categorias_criar'))
            
=======

            if not nome or not tipo_controle_padrao:
                flash('Nome e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.categorias_criar'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            categoria = AlmoxarifadoCategoria(
                nome=nome,
                tipo_controle_padrao=tipo_controle_padrao,
                permite_devolucao_padrao=permite_devolucao_padrao,
                admin_id=admin_id
            )
<<<<<<< HEAD
            
            db.session.add(categoria)
            db.session.commit()
            
            flash(f'Categoria "{nome}" criada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.categorias'))
            
=======

            db.session.add(categoria)
            db.session.commit()

            flash(f'Categoria "{nome}" criada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.categorias'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar categoria: {str(e)}')
            flash('Erro ao criar categoria', 'danger')
            return redirect(url_for('almoxarifado.categorias_criar'))
<<<<<<< HEAD
    
    return render_template('almoxarifado/categorias_form.html', categoria=None)

=======

    return render_template('almoxarifado/categorias_form.html', categoria=None)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/categorias/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def categorias_editar(id):
    """Editar categoria existente"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
=======

    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo_controle_padrao = request.form.get('tipo_controle_padrao')
            permite_devolucao_padrao = request.form.get('permite_devolucao_padrao') == 'on'
<<<<<<< HEAD
            
            # Validações obrigatórias
            if not nome or not tipo_controle_padrao:
                flash('Nome e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.categorias_editar', id=id))
            
=======

            if not nome or not tipo_controle_padrao:
                flash('Nome e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.categorias_editar', id=id))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            categoria.nome = nome
            categoria.tipo_controle_padrao = tipo_controle_padrao
            categoria.permite_devolucao_padrao = permite_devolucao_padrao
            categoria.updated_at = datetime.utcnow()
<<<<<<< HEAD
            
            db.session.commit()
            
            flash(f'Categoria "{categoria.nome}" atualizada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.categorias'))
            
=======

            db.session.commit()

            flash(f'Categoria "{categoria.nome}" atualizada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.categorias'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar categoria: {str(e)}')
            flash('Erro ao atualizar categoria', 'danger')
<<<<<<< HEAD
    
    return render_template('almoxarifado/categorias_form.html', categoria=categoria)

=======

    return render_template('almoxarifado/categorias_form.html', categoria=categoria)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/categorias/deletar/<int:id>', methods=['POST'])
@login_required
def categorias_deletar(id):
    """Deletar categoria"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Verificar se existem itens vinculados
=======

    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    itens_count = AlmoxarifadoItem.query.filter_by(categoria_id=id, admin_id=admin_id).count()
    if itens_count > 0:
        flash(f'Não é possível excluir a categoria "{categoria.nome}" pois existem {itens_count} itens vinculados', 'danger')
        return redirect(url_for('almoxarifado.categorias'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        nome = categoria.nome
        db.session.delete(categoria)
        db.session.commit()
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        flash(f'Categoria "{nome}" excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar categoria: {str(e)}')
        flash('Erro ao excluir categoria', 'danger')
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    return redirect(url_for('almoxarifado.categorias'))
