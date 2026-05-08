<<<<<<< HEAD
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import logging
from app import db
from models import (
    AlmoxarifadoCategoria,
    AlmoxarifadoItem,
    AlmoxarifadoEstoque,
    AlmoxarifadoMovimento,
    Funcionario,
    Obra,
)
from . import almoxarifado_bp, get_admin_id
=======
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import logging

from views.almoxarifado import almoxarifado_bp, get_admin_id
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

logger = logging.getLogger(__name__)


@almoxarifado_bp.route('/itens')
@login_required
def itens():
    """Lista todos os itens do almoxarifado com busca e filtros"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    busca = request.args.get('busca', '').strip()
    categoria_id = request.args.get('categoria_id', type=int)
    tipo_controle = request.args.get('tipo_controle', '')
    
    query = AlmoxarifadoItem.query.filter_by(admin_id=admin_id)
    
=======

    busca = request.args.get('busca', '').strip()
    categoria_id = request.args.get('categoria_id', type=int)
    tipo_controle = request.args.get('tipo_controle', '')

    query = AlmoxarifadoItem.query.filter_by(admin_id=admin_id)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if busca:
        query = query.filter(
            or_(
                AlmoxarifadoItem.codigo.ilike(f'%{busca}%'),
                AlmoxarifadoItem.nome.ilike(f'%{busca}%')
            )
        )
<<<<<<< HEAD
    
    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)
    
    if tipo_controle:
        query = query.filter_by(tipo_controle=tipo_controle)
    
    itens = query.order_by(AlmoxarifadoItem.nome).all()
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    
=======

    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)

    if tipo_controle:
        query = query.filter_by(tipo_controle=tipo_controle)

    itens = query.order_by(AlmoxarifadoItem.nome).all()
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    itens_com_estoque = []
    for item in itens:
        if item.tipo_controle == 'SERIALIZADO':
            estoque_atual = AlmoxarifadoEstoque.query.filter_by(
                item_id=item.id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).count()
        else:
            estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                item_id=item.id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).scalar() or 0
<<<<<<< HEAD
        
        # Tratar estoque_minimo NULL (padronizar como 0)
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        estoque_minimo = item.estoque_minimo if item.estoque_minimo is not None else 0
        itens_com_estoque.append({
            'item': item,
            'estoque_atual': estoque_atual,
            'status_estoque': 'baixo' if estoque_atual <= estoque_minimo else 'normal'
        })
<<<<<<< HEAD
    
    return render_template('almoxarifado/itens.html',
                         itens_com_estoque=itens_com_estoque,
                         categorias=categorias,
                         busca=busca,
                         categoria_id=categoria_id,
                         tipo_controle=tipo_controle)
=======

    return render_template('almoxarifado/itens.html',
                           itens_com_estoque=itens_com_estoque,
                           categorias=categorias,
                           busca=busca,
                           categoria_id=categoria_id,
                           tipo_controle=tipo_controle)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/itens/criar', methods=['GET', 'POST'])
@login_required
def itens_criar():
    """Criar novo item"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo')
            nome = request.form.get('nome')
            categoria_id = request.form.get('categoria_id', type=int)
            tipo_controle = request.form.get('tipo_controle')
            permite_devolucao = request.form.get('permite_devolucao') == 'on'
            estoque_minimo = request.form.get('estoque_minimo', type=int) or 0
            unidade = request.form.get('unidade')
<<<<<<< HEAD
            
            if not all([codigo, nome, categoria_id, tipo_controle]):
                flash('Código, nome, categoria e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.itens_criar'))
            
            if tipo_controle == 'SERIALIZADO':
                permite_devolucao = True
            
=======

            if not all([codigo, nome, categoria_id, tipo_controle]):
                flash('Código, nome, categoria e tipo de controle são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.itens_criar'))

            if tipo_controle == 'SERIALIZADO':
                permite_devolucao = True

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            existe = AlmoxarifadoItem.query.filter_by(codigo=codigo, admin_id=admin_id).first()
            if existe:
                flash(f'Já existe um item com o código "{codigo}"', 'danger')
                return redirect(url_for('almoxarifado.itens_criar'))
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
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
<<<<<<< HEAD
            
            db.session.add(item)
            db.session.commit()
            
            flash(f'Item "{nome}" criado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens'))
            
=======

            db.session.add(item)
            db.session.commit()

            flash(f'Item "{nome}" criado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar item: {str(e)}')
            flash('Erro ao criar item', 'danger')
            return redirect(url_for('almoxarifado.itens_criar'))
<<<<<<< HEAD
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/itens_form.html', item=None, categorias=categorias)

=======

    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/itens_form.html', item=None, categorias=categorias)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/itens/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def itens_editar(id):
    """Editar item existente"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
=======

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo')
            tipo_controle = request.form.get('tipo_controle')
            permite_devolucao = request.form.get('permite_devolucao') == 'on'
<<<<<<< HEAD
            
            if tipo_controle == 'SERIALIZADO':
                permite_devolucao = True
            
=======

            if tipo_controle == 'SERIALIZADO':
                permite_devolucao = True

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            existe = AlmoxarifadoItem.query.filter(
                AlmoxarifadoItem.codigo == codigo,
                AlmoxarifadoItem.admin_id == admin_id,
                AlmoxarifadoItem.id != id
            ).first()
            if existe:
                flash(f'Já existe outro item com o código "{codigo}"', 'danger')
                return redirect(url_for('almoxarifado.itens_editar', id=id))
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            item.codigo = codigo
            item.nome = request.form.get('nome')
            item.categoria_id = request.form.get('categoria_id', type=int)
            item.tipo_controle = tipo_controle
            item.permite_devolucao = permite_devolucao
            item.estoque_minimo = request.form.get('estoque_minimo', type=int) or 0
            item.unidade = request.form.get('unidade')
            item.updated_at = datetime.utcnow()
<<<<<<< HEAD
            
            db.session.commit()
            
            flash(f'Item "{item.nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens'))
            
=======

            db.session.commit()

            flash(f'Item "{item.nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar item: {str(e)}')
            flash('Erro ao atualizar item', 'danger')
<<<<<<< HEAD
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/itens_form.html', item=item, categorias=categorias)

=======

    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/itens_form.html', item=item, categorias=categorias)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/itens/<int:id>')
@login_required
def itens_detalhes(id):
    """Detalhes do item com histórico"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
=======

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if item.tipo_controle == 'SERIALIZADO':
        estoque_atual = AlmoxarifadoEstoque.query.filter_by(
            item_id=id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).count()
        itens_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).order_by(AlmoxarifadoEstoque.created_at.desc()).all()
    else:
        estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
            item_id=id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).scalar() or 0
        itens_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).filter(
            AlmoxarifadoEstoque.quantidade > 0
        ).order_by(AlmoxarifadoEstoque.created_at.desc()).all()
<<<<<<< HEAD
    
    movimentos = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id).order_by(
        AlmoxarifadoMovimento.data_movimento.desc()
    ).limit(20).all()
    
    return render_template('almoxarifado/itens_detalhes.html',
                         item=item,
                         estoque_atual=estoque_atual,
                         itens_estoque=itens_estoque,
                         movimentos=movimentos)
=======

    movimentos = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id).order_by(
        AlmoxarifadoMovimento.data_movimento.desc()
    ).limit(20).all()

    return render_template('almoxarifado/itens_detalhes.html',
                           item=item,
                           estoque_atual=estoque_atual,
                           itens_estoque=itens_estoque,
                           movimentos=movimentos)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/itens/<int:id>/movimentacoes')
@login_required
def itens_movimentacoes(id):
    """Histórico completo de movimentações com filtros avançados"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Filtros da query string
=======

    from models import Funcionario, Obra

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    tipo_filtro = request.args.get('tipo', '')
    funcionario_filtro = request.args.get('funcionario', '')
    obra_filtro = request.args.get('obra', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
<<<<<<< HEAD
    
    # Query base
    query = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id)
    
    # Aplicar filtros
    if tipo_filtro:
        query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_filtro)
    
    if funcionario_filtro:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == int(funcionario_filtro))
    
    if obra_filtro:
        query = query.filter(AlmoxarifadoMovimento.obra_id == int(obra_filtro))
    
=======

    query = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id)

    if tipo_filtro:
        query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_filtro)

    if funcionario_filtro:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == int(funcionario_filtro))

    if obra_filtro:
        query = query.filter(AlmoxarifadoMovimento.obra_id == int(obra_filtro))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if data_inicio:
        try:
            dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(AlmoxarifadoMovimento.data_movimento >= dt_inicio)
        except ValueError:
            pass
<<<<<<< HEAD
    
    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
            # Adicionar 1 dia para incluir movimentos do dia inteiro
=======

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            dt_fim = dt_fim + timedelta(days=1)
            query = query.filter(AlmoxarifadoMovimento.data_movimento < dt_fim)
        except ValueError:
            pass
<<<<<<< HEAD
    
    # Ordenar e buscar
    movimentos = query.order_by(AlmoxarifadoMovimento.data_movimento.desc()).all()
    
    # Buscar listas para filtros
=======

    movimentos = query.order_by(AlmoxarifadoMovimento.data_movimento.desc()).all()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    funcionarios = db.session.query(Funcionario).join(
        AlmoxarifadoMovimento,
        Funcionario.id == AlmoxarifadoMovimento.funcionario_id
    ).filter(
        AlmoxarifadoMovimento.item_id == id,
        AlmoxarifadoMovimento.admin_id == admin_id
    ).distinct().order_by(Funcionario.nome).all()
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    obras = db.session.query(Obra).join(
        AlmoxarifadoMovimento,
        Obra.id == AlmoxarifadoMovimento.obra_id
    ).filter(
        AlmoxarifadoMovimento.item_id == id,
        AlmoxarifadoMovimento.admin_id == admin_id
    ).distinct().order_by(Obra.nome).all()
<<<<<<< HEAD
    
    # Estatísticas
    total_entradas = sum(m.quantidade or 0 for m in movimentos if m.tipo_movimento == 'ENTRADA')
    total_saidas = sum(m.quantidade or 0 for m in movimentos if m.tipo_movimento == 'SAIDA')
    total_devolucoes = sum(m.quantidade or 0 for m in movimentos if m.tipo_movimento == 'DEVOLUCAO')
    
    return render_template('almoxarifado/itens_movimentacoes.html',
                         item=item,
                         movimentos=movimentos,
                         funcionarios=funcionarios,
                         obras=obras,
                         tipo_filtro=tipo_filtro,
                         funcionario_filtro=funcionario_filtro,
                         obra_filtro=obra_filtro,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         total_entradas=total_entradas,
                         total_saidas=total_saidas,
                         total_devolucoes=total_devolucoes)
=======

    total_entradas = sum(m.quantidade or 0 for m in movimentos if m.tipo_movimento == 'ENTRADA')
    total_saidas = sum(m.quantidade or 0 for m in movimentos if m.tipo_movimento == 'SAIDA')
    total_devolucoes = sum(m.quantidade or 0 for m in movimentos if m.tipo_movimento == 'DEVOLUCAO')

    return render_template('almoxarifado/itens_movimentacoes.html',
                           item=item,
                           movimentos=movimentos,
                           funcionarios=funcionarios,
                           obras=obras,
                           tipo_filtro=tipo_filtro,
                           funcionario_filtro=funcionario_filtro,
                           obra_filtro=obra_filtro,
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           total_entradas=total_entradas,
                           total_saidas=total_saidas,
                           total_devolucoes=total_devolucoes)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/itens/deletar/<int:id>', methods=['POST'])
@login_required
def itens_deletar(id):
    """Deletar item"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
=======

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    tem_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).count() > 0
    if tem_estoque:
        flash(f'Não é possível excluir o item "{item.nome}" pois possui registros de estoque', 'danger')
        return redirect(url_for('almoxarifado.itens'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        nome = item.nome
        db.session.delete(item)
        db.session.commit()
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        flash(f'Item "{nome}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar item: {str(e)}')
        flash('Erro ao excluir item', 'danger')
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    return redirect(url_for('almoxarifado.itens'))
