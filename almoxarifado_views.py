from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento
from models import Funcionario, Obra, Usuario
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import logging

logger = logging.getLogger(__name__)

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')

def get_admin_id():
    """Retorna admin_id do usuário atual"""
    if hasattr(current_user, 'perfil'):
        if current_user.perfil == 'admin':
            return current_user.id
        elif current_user.perfil == 'funcionario' and current_user.admin_id:
            return current_user.admin_id
    return None

@almoxarifado_bp.route('/')
@login_required
def dashboard():
    """Dashboard principal do almoxarifado - KPIs e ações rápidas"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    # KPIs básicos (será expandido na FASE 5)
    total_itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).count()
    estoque_baixo = 0
    movimentos_hoje = 0
    valor_total = 0
    
    return render_template('almoxarifado/dashboard.html',
                         total_itens=total_itens,
                         estoque_baixo=estoque_baixo,
                         movimentos_hoje=movimentos_hoje,
                         valor_total=valor_total)

# ========================================
# CRUD CATEGORIAS
# ========================================

@almoxarifado_bp.route('/categorias')
@login_required
def categorias():
    """Lista todas as categorias do almoxarifado"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/categorias.html', categorias=categorias)

@almoxarifado_bp.route('/categorias/criar', methods=['GET', 'POST'])
@login_required
def categorias_criar():
    """Criar nova categoria"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo_controle_padrao = request.form.get('tipo_controle_padrao')
            permite_devolucao_padrao = request.form.get('permite_devolucao_padrao') == 'on'
            
            # Validações
            if not nome or not tipo_controle_padrao:
                flash('Nome e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.categorias_criar'))
            
            categoria = AlmoxarifadoCategoria(
                nome=nome,
                tipo_controle_padrao=tipo_controle_padrao,
                permite_devolucao_padrao=permite_devolucao_padrao,
                admin_id=admin_id
            )
            
            db.session.add(categoria)
            db.session.commit()
            
            flash(f'Categoria "{nome}" criada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.categorias'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar categoria: {str(e)}')
            flash('Erro ao criar categoria', 'danger')
            return redirect(url_for('almoxarifado.categorias_criar'))
    
    return render_template('almoxarifado/categorias_form.html', categoria=None)

@almoxarifado_bp.route('/categorias/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def categorias_editar(id):
    """Editar categoria existente"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo_controle_padrao = request.form.get('tipo_controle_padrao')
            permite_devolucao_padrao = request.form.get('permite_devolucao_padrao') == 'on'
            
            # Validações obrigatórias
            if not nome or not tipo_controle_padrao:
                flash('Nome e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.categorias_editar', id=id))
            
            categoria.nome = nome
            categoria.tipo_controle_padrao = tipo_controle_padrao
            categoria.permite_devolucao_padrao = permite_devolucao_padrao
            categoria.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Categoria "{categoria.nome}" atualizada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.categorias'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar categoria: {str(e)}')
            flash('Erro ao atualizar categoria', 'danger')
    
    return render_template('almoxarifado/categorias_form.html', categoria=categoria)

@almoxarifado_bp.route('/categorias/deletar/<int:id>', methods=['POST'])
@login_required
def categorias_deletar(id):
    """Deletar categoria"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Verificar se existem itens vinculados
    itens_count = AlmoxarifadoItem.query.filter_by(categoria_id=id).count()
    if itens_count > 0:
        flash(f'Não é possível excluir a categoria "{categoria.nome}" pois existem {itens_count} itens vinculados', 'danger')
        return redirect(url_for('almoxarifado.categorias'))
    
    try:
        nome = categoria.nome
        db.session.delete(categoria)
        db.session.commit()
        
        flash(f'Categoria "{nome}" excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar categoria: {str(e)}')
        flash('Erro ao excluir categoria', 'danger')
    
    return redirect(url_for('almoxarifado.categorias'))

# ========================================
# CRUD ITENS
# ========================================

@almoxarifado_bp.route('/itens')
@login_required
def itens():
    """Lista todos os itens do almoxarifado com busca e filtros"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    busca = request.args.get('busca', '').strip()
    categoria_id = request.args.get('categoria_id', type=int)
    tipo_controle = request.args.get('tipo_controle', '')
    
    query = AlmoxarifadoItem.query.filter_by(admin_id=admin_id)
    
    if busca:
        query = query.filter(
            or_(
                AlmoxarifadoItem.codigo.ilike(f'%{busca}%'),
                AlmoxarifadoItem.nome.ilike(f'%{busca}%')
            )
        )
    
    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)
    
    if tipo_controle:
        query = query.filter_by(tipo_controle=tipo_controle)
    
    itens = query.order_by(AlmoxarifadoItem.nome).all()
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    
    itens_com_estoque = []
    for item in itens:
        if item.tipo_controle == 'SERIALIZADO':
            estoque_atual = AlmoxarifadoEstoque.query.filter_by(
                item_id=item.id,
                status='DISPONIVEL'
            ).count()
        else:
            estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                item_id=item.id,
                status='DISPONIVEL'
            ).scalar() or 0
        
        itens_com_estoque.append({
            'item': item,
            'estoque_atual': estoque_atual,
            'status_estoque': 'baixo' if estoque_atual <= item.estoque_minimo else 'normal'
        })
    
    return render_template('almoxarifado/itens.html',
                         itens_com_estoque=itens_com_estoque,
                         categorias=categorias,
                         busca=busca,
                         categoria_id=categoria_id,
                         tipo_controle=tipo_controle)

@almoxarifado_bp.route('/itens/criar', methods=['GET', 'POST'])
@login_required
def itens_criar():
    """Criar novo item"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo')
            nome = request.form.get('nome')
            categoria_id = request.form.get('categoria_id', type=int)
            tipo_controle = request.form.get('tipo_controle')
            permite_devolucao = request.form.get('permite_devolucao') == 'on'
            estoque_minimo = request.form.get('estoque_minimo', type=int) or 0
            unidade = request.form.get('unidade')
            
            if not all([codigo, nome, categoria_id, tipo_controle]):
                flash('Código, nome, categoria e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.itens_criar'))
            
            if tipo_controle == 'SERIALIZADO':
                permite_devolucao = True
            
            existe = AlmoxarifadoItem.query.filter_by(codigo=codigo, admin_id=admin_id).first()
            if existe:
                flash(f'Já existe um item com o código "{codigo}"', 'danger')
                return redirect(url_for('almoxarifado.itens_criar'))
            
            item = AlmoxarifadoItem(
                codigo=codigo,
                nome=nome,
                categoria_id=categoria_id,
                tipo_controle=tipo_controle,
                permite_devolucao=permite_devolucao,
                estoque_minimo=estoque_minimo,
                unidade=unidade,
                admin_id=admin_id
            )
            
            db.session.add(item)
            db.session.commit()
            
            flash(f'Item "{nome}" criado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar item: {str(e)}')
            flash('Erro ao criar item', 'danger')
            return redirect(url_for('almoxarifado.itens_criar'))
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/itens_form.html', item=None, categorias=categorias)

@almoxarifado_bp.route('/itens/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def itens_editar(id):
    """Editar item existente"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo')
            tipo_controle = request.form.get('tipo_controle')
            permite_devolucao = request.form.get('permite_devolucao') == 'on'
            
            if tipo_controle == 'SERIALIZADO':
                permite_devolucao = True
            
            existe = AlmoxarifadoItem.query.filter(
                AlmoxarifadoItem.codigo == codigo,
                AlmoxarifadoItem.admin_id == admin_id,
                AlmoxarifadoItem.id != id
            ).first()
            if existe:
                flash(f'Já existe outro item com o código "{codigo}"', 'danger')
                return redirect(url_for('almoxarifado.itens_editar', id=id))
            
            item.codigo = codigo
            item.nome = request.form.get('nome')
            item.categoria_id = request.form.get('categoria_id', type=int)
            item.tipo_controle = tipo_controle
            item.permite_devolucao = permite_devolucao
            item.estoque_minimo = request.form.get('estoque_minimo', type=int) or 0
            item.unidade = request.form.get('unidade')
            item.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Item "{item.nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar item: {str(e)}')
            flash('Erro ao atualizar item', 'danger')
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/itens_form.html', item=item, categorias=categorias)

@almoxarifado_bp.route('/itens/<int:id>')
@login_required
def itens_detalhes(id):
    """Detalhes do item com histórico"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if item.tipo_controle == 'SERIALIZADO':
        estoque_atual = AlmoxarifadoEstoque.query.filter_by(
            item_id=id,
            status='DISPONIVEL'
        ).count()
        itens_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id).order_by(AlmoxarifadoEstoque.created_at.desc()).all()
    else:
        estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
            item_id=id,
            status='DISPONIVEL'
        ).scalar() or 0
        itens_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id).filter(
            AlmoxarifadoEstoque.quantidade > 0
        ).order_by(AlmoxarifadoEstoque.created_at.desc()).all()
    
    movimentos = AlmoxarifadoMovimento.query.filter_by(item_id=id).order_by(
        AlmoxarifadoMovimento.data_movimento.desc()
    ).limit(20).all()
    
    return render_template('almoxarifado/itens_detalhes.html',
                         item=item,
                         estoque_atual=estoque_atual,
                         itens_estoque=itens_estoque,
                         movimentos=movimentos)

@almoxarifado_bp.route('/itens/deletar/<int:id>', methods=['POST'])
@login_required
def itens_deletar(id):
    """Deletar item"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    tem_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id).count() > 0
    if tem_estoque:
        flash(f'Não é possível excluir o item "{item.nome}" pois possui registros de estoque', 'danger')
        return redirect(url_for('almoxarifado.itens'))
    
    try:
        nome = item.nome
        db.session.delete(item)
        db.session.commit()
        
        flash(f'Item "{nome}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar item: {str(e)}')
        flash('Erro ao excluir item', 'danger')
    
    return redirect(url_for('almoxarifado.itens'))

@almoxarifado_bp.route('/entrada')
@login_required
def entrada():
    """STUB - Será implementado na FASE 4"""
    flash('Módulo em desenvolvimento - FASE 4', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/saida')
@login_required
def saida():
    """STUB - Será implementado na FASE 4"""
    flash('Módulo em desenvolvimento - FASE 4', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/devolucao')
@login_required
def devolucao():
    """STUB - Será implementado na FASE 4"""
    flash('Módulo em desenvolvimento - FASE 4', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/movimentacoes')
@login_required
def movimentacoes():
    """STUB - Será implementado na FASE 5"""
    flash('Módulo em desenvolvimento - FASE 5', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/relatorios')
@login_required
def relatorios():
    """STUB - Será implementado na FASE 5"""
    flash('Módulo em desenvolvimento - FASE 5', 'info')
    return redirect(url_for('almoxarifado.dashboard'))
