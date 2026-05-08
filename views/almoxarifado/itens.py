from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import logging

from views.almoxarifado import almoxarifado_bp, get_admin_id

logger = logging.getLogger(__name__)


@almoxarifado_bp.route('/itens')
@login_required
def itens():
    """Lista todos os itens do almoxarifado com busca e filtros"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

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
                status='DISPONIVEL',
                admin_id=admin_id
            ).count()
        else:
            estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                item_id=item.id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).scalar() or 0

        estoque_minimo = item.estoque_minimo if item.estoque_minimo is not None else 0
        itens_com_estoque.append({
            'item': item,
            'estoque_atual': estoque_atual,
            'status_estoque': 'baixo' if estoque_atual <= estoque_minimo else 'normal'
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
        return redirect(url_for('main.index'))

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
        return redirect(url_for('main.index'))

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
        return redirect(url_for('main.index'))

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

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

    movimentos = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id).order_by(
        AlmoxarifadoMovimento.data_movimento.desc()
    ).limit(20).all()

    return render_template('almoxarifado/itens_detalhes.html',
                           item=item,
                           estoque_atual=estoque_atual,
                           itens_estoque=itens_estoque,
                           movimentos=movimentos)


@almoxarifado_bp.route('/itens/<int:id>/movimentacoes')
@login_required
def itens_movimentacoes(id):
    """Histórico completo de movimentações com filtros avançados"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    from models import Funcionario, Obra

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    tipo_filtro = request.args.get('tipo', '')
    funcionario_filtro = request.args.get('funcionario', '')
    obra_filtro = request.args.get('obra', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')

    query = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id)

    if tipo_filtro:
        query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_filtro)

    if funcionario_filtro:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == int(funcionario_filtro))

    if obra_filtro:
        query = query.filter(AlmoxarifadoMovimento.obra_id == int(obra_filtro))

    if data_inicio:
        try:
            dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(AlmoxarifadoMovimento.data_movimento >= dt_inicio)
        except ValueError:
            pass

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
            dt_fim = dt_fim + timedelta(days=1)
            query = query.filter(AlmoxarifadoMovimento.data_movimento < dt_fim)
        except ValueError:
            pass

    movimentos = query.order_by(AlmoxarifadoMovimento.data_movimento.desc()).all()

    funcionarios = db.session.query(Funcionario).join(
        AlmoxarifadoMovimento,
        Funcionario.id == AlmoxarifadoMovimento.funcionario_id
    ).filter(
        AlmoxarifadoMovimento.item_id == id,
        AlmoxarifadoMovimento.admin_id == admin_id
    ).distinct().order_by(Funcionario.nome).all()

    obras = db.session.query(Obra).join(
        AlmoxarifadoMovimento,
        Obra.id == AlmoxarifadoMovimento.obra_id
    ).filter(
        AlmoxarifadoMovimento.item_id == id,
        AlmoxarifadoMovimento.admin_id == admin_id
    ).distinct().order_by(Obra.nome).all()

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


@almoxarifado_bp.route('/itens/deletar/<int:id>', methods=['POST'])
@login_required
def itens_deletar(id):
    """Deletar item"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    tem_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).count() > 0
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
