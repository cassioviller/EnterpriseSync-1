from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento
from models import Funcionario, Obra, Usuario, Fornecedor
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from event_manager import EventManager
import logging

logger = logging.getLogger(__name__)

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')

def get_admin_id():
    """Retorna admin_id do usuário atual (padrão consolidado do sistema)"""
    if current_user.is_authenticated:
        if hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
        return current_user.id
    return None

@almoxarifado_bp.route('/')
@login_required
def dashboard():
    """Dashboard principal do almoxarifado v3.0 - KPIs, alertas e movimentações"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # ========================================
    # KPI 1: Total de Itens Cadastrados
    # ========================================
    total_itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).count()
    
    # ========================================
    # KPI 2: Estoque Baixo
    # ========================================
    itens_estoque_baixo = []
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).all()
    
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
        
        # Tratar estoque_minimo NULL (padronizar como 0)
        estoque_minimo = item.estoque_minimo if item.estoque_minimo is not None else 0
        if estoque_atual < estoque_minimo:
            itens_estoque_baixo.append({
                'item': item,
                'estoque_atual': estoque_atual,
                'estoque_minimo': estoque_minimo
            })
    
    estoque_baixo = len(itens_estoque_baixo)
    
    # ========================================
    # KPI 3: Movimentações Hoje
    # ========================================
    hoje = datetime.now().date()
    movimentos_hoje = AlmoxarifadoMovimento.query.filter(
        AlmoxarifadoMovimento.admin_id == admin_id,
        func.date(AlmoxarifadoMovimento.data_movimento) == hoje
    ).count()
    
    # ========================================
    # KPI 4: Valor Total em Estoque
    # ========================================
    valor_total = db.session.query(
        func.sum(AlmoxarifadoEstoque.valor_unitario * AlmoxarifadoEstoque.quantidade)
    ).filter_by(
        status='DISPONIVEL',
        admin_id=admin_id
    ).scalar() or 0
    
    # ========================================
    # ALERTAS
    # ========================================
    
    # Alerta 1: Itens Vencendo (30 dias)
    data_limite_vencimento = datetime.now().date() + timedelta(days=30)
    itens_vencendo = AlmoxarifadoEstoque.query.filter(
        AlmoxarifadoEstoque.admin_id == admin_id,
        AlmoxarifadoEstoque.status == 'DISPONIVEL',
        AlmoxarifadoEstoque.data_validade.isnot(None),
        AlmoxarifadoEstoque.data_validade <= data_limite_vencimento
    ).join(AlmoxarifadoItem).all()
    
    # Alerta 2: Itens em Manutenção
    itens_manutencao = AlmoxarifadoEstoque.query.filter_by(
        admin_id=admin_id,
        status='EM_MANUTENCAO'
    ).join(AlmoxarifadoItem).all()
    
    # ========================================
    # ÚLTIMAS 10 MOVIMENTAÇÕES
    # ========================================
    ultimas_movimentacoes = AlmoxarifadoMovimento.query.filter_by(
        admin_id=admin_id
    ).join(
        AlmoxarifadoItem
    ).outerjoin(
        Funcionario, AlmoxarifadoMovimento.funcionario_id == Funcionario.id
    ).order_by(
        AlmoxarifadoMovimento.data_movimento.desc()
    ).limit(10).all()
    
    return render_template('almoxarifado/dashboard.html',
                         total_itens=total_itens,
                         estoque_baixo=estoque_baixo,
                         movimentos_hoje=movimentos_hoje,
                         valor_total=valor_total,
                         itens_estoque_baixo=itens_estoque_baixo,
                         itens_vencendo=itens_vencendo,
                         itens_manutencao=itens_manutencao,
                         ultimas_movimentacoes=ultimas_movimentacoes)

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
        return redirect(url_for('main.index'))
    
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    return render_template('almoxarifado/categorias.html', categorias=categorias)

@almoxarifado_bp.route('/categorias/criar', methods=['GET', 'POST'])
@login_required
def categorias_criar():
    """Criar nova categoria"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
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
        return redirect(url_for('main.index'))
    
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
        return redirect(url_for('main.index'))
    
    categoria = AlmoxarifadoCategoria.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Verificar se existem itens vinculados
    itens_count = AlmoxarifadoItem.query.filter_by(categoria_id=id, admin_id=admin_id).count()
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
        
        # Tratar estoque_minimo NULL (padronizar como 0)
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
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Filtros da query string
    tipo_filtro = request.args.get('tipo', '')
    funcionario_filtro = request.args.get('funcionario', '')
    obra_filtro = request.args.get('obra', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id)
    
    # Aplicar filtros
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
            # Adicionar 1 dia para incluir movimentos do dia inteiro
            dt_fim = dt_fim + timedelta(days=1)
            query = query.filter(AlmoxarifadoMovimento.data_movimento < dt_fim)
        except ValueError:
            pass
    
    # Ordenar e buscar
    movimentos = query.order_by(AlmoxarifadoMovimento.data_movimento.desc()).all()
    
    # Buscar listas para filtros
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

@almoxarifado_bp.route('/itens/deletar/<int:id>', methods=['POST'])
@login_required
def itens_deletar(id):
    """Deletar item - com suporte a exclusão forçada"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    force = request.form.get('force', '0') == '1'
    
    qtd_estoque = AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).count()
    qtd_movimentos = AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id).count()
    
    if (qtd_estoque > 0 or qtd_movimentos > 0) and not force:
        flash(f'Item "{item.nome}" possui {qtd_estoque} registros de estoque e {qtd_movimentos} movimentações. Use exclusão forçada.', 'warning')
        return redirect(url_for('almoxarifado.itens'))
    
    try:
        nome = item.nome
        
        if force:
            AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).delete()
            AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id).delete()
            logger.info(f'Exclusão forçada: {qtd_estoque} estoques e {qtd_movimentos} movimentos removidos para item {nome}')
        
        db.session.delete(item)
        db.session.commit()
        
        if force:
            flash(f'Item "{nome}" e todos os registros relacionados foram excluídos!', 'success')
        else:
            flash(f'Item "{nome}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar item: {str(e)}')
        flash('Erro ao excluir item', 'danger')
    
    return redirect(url_for('almoxarifado.itens'))

# ========================================
# ENTRADA DE MATERIAIS
# ========================================

@almoxarifado_bp.route('/entrada', methods=['GET', 'POST'])
@login_required
def entrada():
    """Formulário de entrada de materiais"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by(Fornecedor.razao_social).all()
    
    return render_template('almoxarifado/entrada.html', itens=itens, fornecedores=fornecedores)

@almoxarifado_bp.route('/api/item/<int:id>')
@login_required
def api_item_info(id):
    """API que retorna info do item (tipo_controle, unidade, estoque_atual)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401
    
    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404
    
    # Calcular estoque atual
    if item.tipo_controle == 'SERIALIZADO':
        estoque_atual = AlmoxarifadoEstoque.query.filter_by(
            item_id=id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).count()
    else:
        estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
            item_id=id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).scalar() or 0
    
    return jsonify({
        'id': item.id,
        'nome': item.nome,
        'codigo': item.codigo,
        'tipo_controle': item.tipo_controle,
        'unidade': item.unidade,
        'estoque_atual': estoque_atual
    })

@almoxarifado_bp.route('/processar-entrada', methods=['POST'])
@login_required
def processar_entrada():
    """Processa entrada de materiais (SERIALIZADO ou CONSUMIVEL)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        item_id = request.form.get('item_id', type=int)
        tipo_controle = request.form.get('tipo_controle')
        nota_fiscal = request.form.get('nota_fiscal', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        valor_unitario = request.form.get('valor_unitario', type=float)
        fornecedor_id = request.form.get('fornecedor_id', type=int)
        
        # Validações básicas
        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
        
        if not valor_unitario or valor_unitario <= 0:
            flash('Valor unitário deve ser maior que zero', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
        
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item:
            flash('Item não encontrado', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
        
        # ✅ VALIDAÇÃO CRÍTICA DE SEGURANÇA: Se fornecedor_id fornecido, validar que pertence ao tenant
        if fornecedor_id:
            fornecedor = Fornecedor.query.filter_by(
                id=fornecedor_id,
                admin_id=admin_id
            ).first()
            
            if not fornecedor:
                logger.warning(f"⚠️ Tentativa de usar fornecedor {fornecedor_id} que não pertence ao tenant {admin_id}")
                flash('Fornecedor não encontrado ou sem permissão.', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
        
        # LÓGICA SERIALIZADO vs CONSUMIVEL
        if tipo_controle == 'SERIALIZADO':
            # Para SERIALIZADO: processar múltiplos números de série
            numeros_serie = request.form.get('numeros_serie', '').strip()
            if not numeros_serie:
                flash('Números de série são obrigatórios para itens serializados', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
            
            # Split por vírgula ou quebra de linha
            series = [s.strip() for s in numeros_serie.replace('\n', ',').split(',') if s.strip()]
            
            if not series:
                flash('Nenhum número de série válido fornecido', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
            
            # Verificar duplicatas
            for serie in series:
                existe = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item_id,
                    numero_serie=serie,
                    admin_id=admin_id
                ).first()
                if existe:
                    flash(f'Número de série "{serie}" já cadastrado para este item', 'danger')
                    return redirect(url_for('almoxarifado.entrada'))
            
            # Criar 1 registro de estoque por série + 1 movimento por série
            movimentos_criados = 0
            movimentos_ids = []
            for serie in series:
                # Primeiro criar o movimento
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='ENTRADA',
                    quantidade=1,
                    numero_serie=serie,
                    valor_unitario=valor_unitario,
                    nota_fiscal=nota_fiscal,
                    observacao=observacoes,
                    estoque_id=None,
                    fornecedor_id=fornecedor_id,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=None
                )
                db.session.add(movimento)
                db.session.flush()  # Flush para obter movimento.id
                
                # Agora criar o estoque com rastreamento de lote
                estoque = AlmoxarifadoEstoque(
                    item_id=item_id,
                    numero_serie=serie,
                    quantidade=1,
                    quantidade_inicial=1,
                    quantidade_disponivel=1,
                    entrada_movimento_id=movimento.id,
                    valor_unitario=valor_unitario,
                    status='DISPONIVEL',
                    admin_id=admin_id
                )
                db.session.add(estoque)
                
                movimentos_ids.append(movimento.id)
                movimentos_criados += 1
            
            db.session.commit()
            
            # EMITIR EVENTO para criar conta a pagar (se fornecedor existe)
            if fornecedor_id:
                for mov_id in movimentos_ids:
                    EventManager.emit('material_entrada', {
                        'movimento_id': mov_id,
                        'item_id': item_id,
                        'fornecedor_id': fornecedor_id,
                    }, admin_id=admin_id)
            
            flash(f'Entrada processada com sucesso! {movimentos_criados} itens serializados cadastrados.', 'success')
        
        else:  # CONSUMIVEL
            quantidade = request.form.get('quantidade', type=float)
            if not quantidade or quantidade <= 0:
                flash('Quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
            
            logger.debug(f'Processando entrada CONSUMIVEL - valor_unitario recebido: {valor_unitario}')
            
            # Primeiro criar o movimento
            movimento = AlmoxarifadoMovimento(
                item_id=item_id,
                tipo_movimento='ENTRADA',
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                nota_fiscal=nota_fiscal,
                observacao=observacoes,
                estoque_id=None,  # Será atualizado após criar estoque
                fornecedor_id=fornecedor_id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=None
            )
            db.session.add(movimento)
            db.session.flush()  # Flush para obter movimento.id
            
            # Agora criar registro de estoque com rastreamento de lote FIFO
            estoque = AlmoxarifadoEstoque(
                item_id=item_id,
                quantidade=quantidade,
                quantidade_inicial=quantidade,
                quantidade_disponivel=quantidade,
                entrada_movimento_id=movimento.id,
                valor_unitario=valor_unitario,
                status='DISPONIVEL',
                lote=nota_fiscal,  # Usar nota fiscal como identificador de lote
                admin_id=admin_id
            )
            db.session.add(estoque)
            db.session.flush()
            
            # Atualizar movimento com estoque_id
            movimento.estoque_id = estoque.id
            
            db.session.commit()
            
            # EMITIR EVENTO para criar conta a pagar (se fornecedor existe)
            if fornecedor_id:
                EventManager.emit('material_entrada', {
                    'movimento_id': movimento.id,
                    'item_id': item_id,
                    'fornecedor_id': fornecedor_id,
                }, admin_id=admin_id)
            
            flash(f'Entrada processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" cadastrados.', 'success')
        
        return redirect(url_for('almoxarifado.entrada'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar entrada: {str(e)}')
        flash('Erro ao processar entrada de material', 'danger')
        return redirect(url_for('almoxarifado.entrada'))

@almoxarifado_bp.route('/processar-entrada-multipla', methods=['POST'])
@login_required
def processar_entrada_multipla():
    """Processa entrada de múltiplos materiais (carrinho) - TRANSAÇÃO ATÔMICA"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
    
    try:
        data = request.get_json()
        itens = data.get('itens', [])
        nota_fiscal = data.get('nota_fiscal', '').strip()
        observacoes = data.get('observacoes', '').strip()
        fornecedor_id = data.get('fornecedor_id')
        
        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400
        
        # ✅ VALIDAÇÃO CRÍTICA DE SEGURANÇA: Se fornecedor_id fornecido, validar que pertence ao tenant
        if fornecedor_id:
            fornecedor = Fornecedor.query.filter_by(
                id=fornecedor_id,
                admin_id=admin_id
            ).first()
            
            if not fornecedor:
                logger.warning(f"⚠️ Tentativa de usar fornecedor {fornecedor_id} que não pertence ao tenant {admin_id}")
                return jsonify({'success': False, 'message': 'Fornecedor não encontrado ou sem permissão'}), 403
        
        # ========================================
        # FASE 1: VALIDAÇÃO PRÉVIA COMPLETA
        # ========================================
        erros = []
        itens_validados = []
        
        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')
            valor_unitario = float(item_data.get('valor_unitario', 0))
            
            # Validar: item_id, tipo_controle e valor_unitario obrigatórios
            if not item_id or not tipo_controle:
                erros.append(f"Item {idx+1}: Dados incompletos")
                continue
            
            # Validar: valor unitário > 0
            if valor_unitario <= 0:
                erros.append(f"Item {idx+1}: Valor unitário deve ser maior que zero")
                continue
            
            # Verificar se item existe
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                erros.append(f"Item {idx+1}: Item não encontrado")
                continue
            
            if tipo_controle == 'SERIALIZADO':
                # Processar números de série
                numeros_serie = item_data.get('numeros_serie', '')
                series = [s.strip() for s in numeros_serie.split(',') if s.strip()]
                
                if not series:
                    erros.append(f"Item {idx+1} ({item.nome}): Números de série obrigatórios para itens serializados")
                    continue
                
                # Validar: verificar duplicatas nos números de série
                for serie in series:
                    existe = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item_id,
                        numero_serie=serie,
                        admin_id=admin_id
                    ).first()
                    
                    if existe:
                        erros.append(f"Item {idx+1} ({item.nome}): Número de série '{serie}' já cadastrado")
                
                # Se passou nas validações, adicionar à lista de processamento
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'valor_unitario': valor_unitario,
                    'series': series
                })
                
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade_raw = item_data.get('quantidade', 0)
                quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
                
                # Validar: quantidade > 0
                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'valor_unitario': valor_unitario,
                    'quantidade': quantidade
                })
        
        # Se houver QUALQUER erro, abortar TUDO
        if erros:
            return jsonify({
                'success': False,
                'message': f'{len(erros)} erro(s) encontrado(s)',
                'erros': erros
            }), 400
        
        # ========================================
        # FASE 2: PROCESSAMENTO TRANSACIONAL
        # ========================================
        total_processados = 0
        total_itens_esperados = len(itens_validados)
        
        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']
            valor_unitario = item_validado['valor_unitario']
            
            if tipo_controle == 'SERIALIZADO':
                series = item_validado['series']
                
                for serie in series:
                    # Primeiro criar o movimento
                    movimento = AlmoxarifadoMovimento(
                        item_id=item.id,
                        tipo_movimento='ENTRADA',
                        quantidade=1,
                        numero_serie=serie,
                        valor_unitario=valor_unitario,
                        nota_fiscal=nota_fiscal,
                        observacao=observacoes,
                        estoque_id=None,
                        fornecedor_id=fornecedor_id,
                        admin_id=admin_id,
                        usuario_id=current_user.id,
                        obra_id=None
                    )
                    db.session.add(movimento)
                    db.session.flush()
                    
                    # Agora criar estoque com rastreamento de lote
                    estoque = AlmoxarifadoEstoque(
                        item_id=item.id,
                        numero_serie=serie,
                        quantidade=1,
                        quantidade_inicial=1,
                        quantidade_disponivel=1,
                        entrada_movimento_id=movimento.id,
                        valor_unitario=valor_unitario,
                        status='DISPONIVEL',
                        admin_id=admin_id
                    )
                    db.session.add(estoque)
                    
                    # Emitir evento se tem fornecedor
                    if fornecedor_id:
                        EventManager.emit('material_entrada', {
                            'movimento_id': movimento.id,
                            'item_id': item.id,
                            'fornecedor_id': fornecedor_id,
                        }, admin_id=admin_id)
                
                total_processados += 1
                
            else:  # CONSUMIVEL
                quantidade = item_validado['quantidade']
                
                # Primeiro criar o movimento
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='ENTRADA',
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    nota_fiscal=nota_fiscal,
                    observacao=observacoes,
                    estoque_id=None,
                    fornecedor_id=fornecedor_id,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=None
                )
                db.session.add(movimento)
                db.session.flush()
                
                # Agora criar estoque com rastreamento de lote FIFO
                estoque = AlmoxarifadoEstoque(
                    item_id=item.id,
                    quantidade=quantidade,
                    quantidade_inicial=quantidade,
                    quantidade_disponivel=quantidade,
                    entrada_movimento_id=movimento.id,
                    valor_unitario=valor_unitario,
                    status='DISPONIVEL',
                    lote=nota_fiscal,
                    admin_id=admin_id
                )
                db.session.add(estoque)
                db.session.flush()
                
                # Atualizar movimento com estoque_id
                movimento.estoque_id = estoque.id
                
                # Emitir evento se tem fornecedor
                if fornecedor_id:
                    EventManager.emit('material_entrada', {
                        'movimento_id': movimento.id,
                        'item_id': item.id,
                        'fornecedor_id': fornecedor_id,
                    }, admin_id=admin_id)
                
                total_processados += 1
        
        # Commit APENAS se TODOS itens foram processados
        if total_processados != total_itens_esperados:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Erro: Esperado {total_itens_esperados} itens, processado {total_processados}'
            }), 500
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{total_processados} itens processados com sucesso!',
            'total_esperado': total_itens_esperados,
            'total_processado': total_processados
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar entrada múltipla: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao processar operação'}), 500

# ========================================
# SAÍDA DE MATERIAIS
# ========================================

@almoxarifado_bp.route('/saida', methods=['GET'])
@login_required
def saida():
    """Formulário de saída de materiais"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    return render_template('almoxarifado/saida.html', 
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras)

@almoxarifado_bp.route('/api/estoque-disponivel/<int:item_id>')
@login_required
def api_estoque_disponivel(item_id):
    """API que retorna estoque disponível (SERIALIZADO: lista de itens, CONSUMIVEL: quantidade total)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401
    
    item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404
    
    if item.tipo_controle == 'SERIALIZADO':
        # Retorna lista de itens serializados disponíveis
        itens_disponiveis = AlmoxarifadoEstoque.query.filter_by(
            item_id=item_id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).all()
        
        return jsonify({
            'tipo_controle': 'SERIALIZADO',
            'itens': [{
                'id': est.id,
                'numero_serie': est.numero_serie,
                'data_entrada': est.created_at.strftime('%d/%m/%Y')
            } for est in itens_disponiveis]
        })
    else:
        # Retorna quantidade total disponível
        quantidade_total = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
            item_id=item_id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).scalar() or 0
        
        return jsonify({
            'tipo_controle': 'CONSUMIVEL',
            'quantidade_disponivel': quantidade_total,
            'unidade': item.unidade
        })

@almoxarifado_bp.route('/api/lotes-disponiveis/<int:item_id>')
@login_required
def api_lotes_disponiveis(item_id):
    """Retorna lotes disponíveis de um item ordenados por FIFO (created_at ASC)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401
    
    item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404
    
    # Buscar todos estoques disponíveis deste item ordenados por data (FIFO)
    lotes = AlmoxarifadoEstoque.query.filter_by(
        item_id=item_id,
        status='DISPONIVEL',
        admin_id=admin_id
    ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()
    
    lotes_data = []
    for lote in lotes:
        # Buscar informação da nota fiscal do movimento de entrada
        nota_fiscal = None
        if lote.entrada_movimento_id:
            movimento_entrada = AlmoxarifadoMovimento.query.filter_by(
                id=lote.entrada_movimento_id,
                admin_id=admin_id
            ).first()
            if movimento_entrada:
                nota_fiscal = movimento_entrada.nota_fiscal
        
        # Para CONSUMIVEL, usar quantidade_disponivel; para SERIALIZADO, sempre 1
        qtd_disponivel = float(lote.quantidade_disponivel) if lote.quantidade_disponivel else float(lote.quantidade)
        
        lotes_data.append({
            'estoque_id': lote.id,
            'lote': lote.lote,
            'numero_serie': lote.numero_serie,  # Para itens SERIALIZADO
            'quantidade_disponivel': qtd_disponivel,
            'quantidade_inicial': float(lote.quantidade_inicial) if lote.quantidade_inicial else float(lote.quantidade),
            'valor_unitario': float(lote.valor_unitario) if lote.valor_unitario else 0.0,
            'data_entrada': lote.created_at.strftime('%d/%m/%Y %H:%M'),
            'nota_fiscal': nota_fiscal,
            'data_validade': lote.data_validade.strftime('%d/%m/%Y') if lote.data_validade else None
        })
    
    return jsonify({
        'success': True,
        'item_id': item_id,
        'item_nome': item.nome,
        'tipo_controle': item.tipo_controle,
        'unidade': item.unidade,
        'lotes': lotes_data,
        'total_disponivel': sum(l['quantidade_disponivel'] for l in lotes_data)
    })

@almoxarifado_bp.route('/processar-saida', methods=['POST'])
@login_required
def processar_saida():
    """Processa saída de materiais (SERIALIZADO ou CONSUMIVEL)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        item_id = request.form.get('item_id', type=int)
        tipo_controle = request.form.get('tipo_controle')
        funcionario_id = request.form.get('funcionario_id', type=int)
        obra_id = request.form.get('obra_id', type=int)
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validações básicas
        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.saida'))
        
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item:
            flash('Item não encontrado', 'danger')
            return redirect(url_for('almoxarifado.saida'))
        
        # Funcionário é obrigatório
        if not funcionario_id:
            flash('Funcionário é obrigatório para saída', 'danger')
            return redirect(url_for('almoxarifado.saida'))
        
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            flash('Funcionário não encontrado', 'danger')
            return redirect(url_for('almoxarifado.saida'))
        
        # Obra é opcional
        obra = None
        if obra_id:
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        
        # LÓGICA SERIALIZADO vs CONSUMIVEL
        if tipo_controle == 'SERIALIZADO':
            # Para SERIALIZADO: selecionar itens específicos
            estoque_ids = request.form.getlist('estoque_ids[]')
            if not estoque_ids:
                flash('Selecione ao menos um item para saída', 'danger')
                return redirect(url_for('almoxarifado.saida'))
            
            # Validar estoque e atualizar status
            itens_processados = 0
            for estoque_id in estoque_ids:
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=int(estoque_id),
                    item_id=item_id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).first()
                
                if not estoque:
                    db.session.rollback()
                    flash(f'Item de estoque ID {estoque_id} não está disponível', 'danger')
                    return redirect(url_for('almoxarifado.saida'))
                
                # Atualizar estoque
                estoque.status = 'EM_USO'
                estoque.funcionario_atual_id = funcionario_id
                estoque.obra_id = obra_id
                estoque.updated_at = datetime.utcnow()
                
                # Criar movimento
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='SAIDA',
                    quantidade=1,
                    numero_serie=estoque.numero_serie,
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                itens_processados += 1
            
            db.session.commit()
            flash(f'Saída processada com sucesso! {itens_processados} itens entregues para {funcionario.nome}.', 'success')
        
        else:  # CONSUMIVEL
            from decimal import Decimal
            quantidade_raw = request.form.get('quantidade', type=float)
            quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
            if not quantidade or quantidade <= 0:
                flash('Quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('almoxarifado.saida'))
            
            # Verificar quantidade disponível usando quantidade_disponivel (FIFO)
            quantidade_disponivel_total = db.session.query(
                func.sum(AlmoxarifadoEstoque.quantidade_disponivel)
            ).filter_by(
                item_id=item_id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).scalar() or Decimal('0')
            
            logger.debug(f'Saída CONSUMIVEL - Quantidade solicitada: {quantidade}, Disponível: {quantidade_disponivel_total}')
            
            if quantidade > quantidade_disponivel_total:
                flash(f'Quantidade insuficiente! Disponível: {quantidade_disponivel_total} {item.unidade}', 'danger')
                return redirect(url_for('almoxarifado.saida'))
            
            # Implementar consumo FIFO pelos lotes mais antigos
            lotes = AlmoxarifadoEstoque.query.filter_by(
                item_id=item_id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()  # FIFO: mais antigos primeiro
            
            quantidade_restante = quantidade
            
            for lote in lotes:
                if quantidade_restante <= 0:
                    break
                
                # Usar quantidade_disponivel para rastreamento FIFO
                qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade
                
                if qtd_disponivel_lote <= 0:
                    continue  # Pular lotes já consumidos
                
                # Quantidade a consumir deste lote
                if qtd_disponivel_lote >= quantidade_restante:
                    qtd_consumida = quantidade_restante
                    quantidade_restante = Decimal('0')
                else:
                    qtd_consumida = qtd_disponivel_lote
                    quantidade_restante -= qtd_disponivel_lote
                
                # Atualizar lote (FIFO tracking)
                lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                lote.quantidade = lote.quantidade_disponivel  # Manter sincronizado
                
                if lote.quantidade_disponivel == 0:
                    lote.status = 'CONSUMIDO'
                
                lote.updated_at = datetime.utcnow()
                
                # Criar movimento individual para este lote consumido
                # Isso permite rastrear o valor_unitario correto de cada lote
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='SAIDA',
                    quantidade=qtd_consumida,
                    valor_unitario=lote.valor_unitario,  # Valor do lote específico
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    observacao=observacoes,
                    estoque_id=lote.id,
                    lote=lote.lote,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                
                logger.debug(f'Lote {lote.id} - Consumido: {qtd_consumida}, Restante no lote: {lote.quantidade_disponivel}, Valor unitário: {lote.valor_unitario}')
            
            db.session.commit()
            
            # 🔗 INTEGRAÇÃO AUTOMÁTICA - Emitir evento de material saída
            try:
                from event_manager import EventManager
                from decimal import Decimal
                # AlmoxarifadoItem não tem valor_unitario - enviar quantidade e item para cálculo posterior
                EventManager.emit('material_saida', {
                    'movimento_id': movimento.id,
                    'item_id': item_id,
                    'item_nome': item.nome,
                    'quantidade': float(quantidade),
                    'obra_id': obra_id,
                    'funcionario_id': funcionario_id,
                    'valor_total': 0  # Será calculado quando houver módulo de custos com preços
                }, admin_id)
            except Exception as e:
                logger.warning(f'Integração automática falhou (não crítico): {e}')
            
            flash(f'Saída processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" entregues para {funcionario.nome}.', 'success')
        
        return redirect(url_for('almoxarifado.saida'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar saída: {str(e)}')
        flash('Erro ao processar saída de material', 'danger')
        return redirect(url_for('almoxarifado.saida'))

@almoxarifado_bp.route('/processar-saida-multipla', methods=['POST'])
@login_required
def processar_saida_multipla():
    """Processa saída de múltiplos itens (carrinho) - TRANSAÇÃO ATÔMICA"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
    
    try:
        data = request.get_json()
        itens = data.get('itens', [])
        observacoes = data.get('observacoes', '').strip()
        
        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400
        
        # ========================================
        # FASE 1: VALIDAÇÃO PRÉVIA COMPLETA
        # ========================================
        erros = []
        itens_validados = []
        
        # Validar que todos itens têm mesmo funcionário e obra
        funcionario_id = itens[0].get('funcionario_id')
        obra_id = itens[0].get('obra_id') or None
        
        for item_data in itens:
            if item_data.get('funcionario_id') != funcionario_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesmo funcionário'}), 400
            item_obra_id = item_data.get('obra_id') or None
            if item_obra_id != obra_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesma obra'}), 400
        
        # Validar que funcionário existe
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 400
        
        # Validar cada item
        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')
            
            # Verificar se item existe
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                erros.append(f"Item {idx+1}: Item não encontrado")
                continue
            
            if tipo_controle == 'SERIALIZADO':
                estoque_id = item_data.get('estoque_id')
                numero_serie = item_data.get('numero_serie')
                
                # VALIDAR: Série existe e está disponível?
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=estoque_id,
                    item_id=item_id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).first()
                
                if not estoque:
                    erros.append(f"Item {idx+1} ({item.nome}): Número de série {numero_serie} não disponível")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'estoque_id': estoque_id,
                    'numero_serie': numero_serie,
                    'estoque': estoque
                })
            
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade_raw = item_data.get('quantidade', 0)
                quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
                lote_allocations = item_data.get('lote_allocations', [])
                
                # Validar: quantidade > 0
                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue
                
                # VALIDAR alocações de lotes (se fornecidas)
                if lote_allocations:
                    # Validar que a soma das alocações = quantidade total
                    total_alocado = sum(Decimal(str(alloc.get('quantidade', 0))) for alloc in lote_allocations)
                    if abs(total_alocado - quantidade) >= Decimal('0.001'):
                        erros.append(f"Item {idx+1} ({item.nome}): Soma das alocações ({total_alocado}) diferente da quantidade total ({quantidade})")
                        continue
                    
                    # Validar cada alocação
                    for alloc_idx, alloc in enumerate(lote_allocations):
                        estoque_id = alloc.get('estoque_id')
                        qtd_alloc = Decimal(str(alloc.get('quantidade', 0)))
                        
                        if qtd_alloc <= 0:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Quantidade deve ser maior que zero")
                            continue
                        
                        # Verificar se o lote existe e pertence ao admin
                        lote_estoque = AlmoxarifadoEstoque.query.filter_by(
                            id=estoque_id,
                            item_id=item_id,
                            status='DISPONIVEL',
                            admin_id=admin_id
                        ).first()
                        
                        if not lote_estoque:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Lote não encontrado ou não disponível")
                            continue
                        
                        # Verificar quantidade disponível
                        qtd_disponivel = lote_estoque.quantidade_disponivel if lote_estoque.quantidade_disponivel else lote_estoque.quantidade
                        if qtd_alloc > qtd_disponivel:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Quantidade solicitada ({qtd_alloc}) maior que disponível ({qtd_disponivel})")
                            continue
                else:
                    # Sem alocações manuais - validar estoque total apenas
                    estoque_total = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade_disponivel)).filter_by(
                        item_id=item_id,
                        status='DISPONIVEL',
                        admin_id=admin_id
                    ).scalar() or 0
                    
                    if estoque_total < quantidade:
                        erros.append(f"Item {idx+1} ({item.nome}): Estoque insuficiente (disponível: {estoque_total}, solicitado: {quantidade})")
                        continue
                
                # Se passou nas validações, adicionar à lista de processamento
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'quantidade': quantidade,
                    'lote_allocations': lote_allocations
                })
        
        # Se houver QUALQUER erro, abortar TUDO
        if erros:
            return jsonify({
                'success': False,
                'message': f'{len(erros)} erro(s) encontrado(s)',
                'erros': erros
            }), 400
        
        # ========================================
        # FASE 2: PROCESSAMENTO TRANSACIONAL
        # ========================================
        total_processados = 0
        total_itens_esperados = len(itens_validados)
        
        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']
            
            if tipo_controle == 'SERIALIZADO':
                estoque = item_validado['estoque']
                numero_serie = item_validado['numero_serie']
                
                # Atualizar estoque
                estoque.status = 'EM_USO'
                estoque.funcionario_atual_id = funcionario_id
                estoque.obra_id = obra_id
                estoque.updated_at = datetime.utcnow()
                
                # Criar movimento
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='SAIDA',
                    quantidade=1,
                    numero_serie=numero_serie,
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                total_processados += 1
            
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade = item_validado['quantidade']
                lote_allocations = item_validado.get('lote_allocations', [])
                
                # PROCESSAMENTO: Escolha Manual vs FIFO Automático
                if lote_allocations:
                    # ========================================
                    # MODO: SELEÇÃO MANUAL DE LOTES
                    # ========================================
                    for alloc in lote_allocations:
                        estoque_id = alloc.get('estoque_id')
                        qtd_consumida = Decimal(str(alloc.get('quantidade', 0)))
                        
                        # Buscar o lote específico
                        lote = AlmoxarifadoEstoque.query.filter_by(
                            id=estoque_id,
                            item_id=item.id,
                            status='DISPONIVEL',
                            admin_id=admin_id
                        ).first()
                        
                        if not lote:
                            continue  # Já validado anteriormente, não deve acontecer
                        
                        qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade
                        
                        # Atualizar lote
                        lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                        lote.quantidade = lote.quantidade_disponivel
                        
                        if lote.quantidade_disponivel == 0:
                            lote.status = 'CONSUMIDO'
                        
                        lote.updated_at = datetime.utcnow()
                        
                        # Criar movimento para este lote consumido
                        movimento = AlmoxarifadoMovimento(
                            item_id=item.id,
                            tipo_movimento='SAIDA',
                            quantidade=qtd_consumida,
                            valor_unitario=lote.valor_unitario,
                            funcionario_id=funcionario_id,
                            obra_id=obra_id,
                            observacao=observacoes,
                            estoque_id=lote.id,
                            lote=lote.lote,
                            admin_id=admin_id,
                            usuario_id=current_user.id
                        )
                        db.session.add(movimento)
                else:
                    # ========================================
                    # MODO: FIFO AUTOMÁTICO (LEGADO)
                    # ========================================
                    lotes = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=admin_id
                    ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()
                    
                    qtd_restante = quantidade
                    
                    for lote in lotes:
                        if qtd_restante <= 0:
                            break
                        
                        qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade
                        
                        if qtd_disponivel_lote <= 0:
                            continue
                        
                        if qtd_disponivel_lote >= qtd_restante:
                            qtd_consumida = qtd_restante
                            qtd_restante = Decimal('0')
                        else:
                            qtd_consumida = qtd_disponivel_lote
                            qtd_restante -= qtd_disponivel_lote
                        
                        lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                        lote.quantidade = lote.quantidade_disponivel
                        
                        if lote.quantidade_disponivel == 0:
                            lote.status = 'CONSUMIDO'
                        
                        lote.updated_at = datetime.utcnow()
                        
                        movimento = AlmoxarifadoMovimento(
                            item_id=item.id,
                            tipo_movimento='SAIDA',
                            quantidade=qtd_consumida,
                            valor_unitario=lote.valor_unitario,
                            funcionario_id=funcionario_id,
                            obra_id=obra_id,
                            observacao=observacoes,
                            estoque_id=lote.id,
                            lote=lote.lote,
                            admin_id=admin_id,
                            usuario_id=current_user.id
                        )
                        db.session.add(movimento)
                
                total_processados += 1
        
        # Commit APENAS se TODOS itens foram processados
        if total_processados != total_itens_esperados:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Erro: Esperado {total_itens_esperados} itens, processado {total_processados}'
            }), 500
        
        db.session.commit()
        
        # 🔗 INTEGRAÇÃO AUTOMÁTICA - Emitir eventos para cada item processado
        try:
            from event_manager import EventManager
            for item_validado in itens_validados:
                item = item_validado['item']
                quantidade = item_validado.get('quantidade', 1)
                EventManager.emit('material_saida', {
                    'movimento_id': 0,  # ID não disponível aqui (múltiplos movimentos)
                    'item_id': item.id,
                    'item_nome': item.nome,
                    'quantidade': quantidade,
                    'obra_id': obra_id,
                    'funcionario_id': funcionario_id,
                    'valor_total': 0  # Será calculado quando houver módulo de custos com preços
                }, admin_id)
        except Exception as e:
            logger.warning(f'Integração automática falhou (não crítico): {e}')
        
        return jsonify({
            'success': True,
            'message': f'{total_processados} itens processados com sucesso! Entregues para {funcionario.nome}.',
            'total_esperado': total_itens_esperados,
            'total_processado': total_processados
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar saída múltipla: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao processar operação'}), 500

# ========================================
# DEVOLUÇÃO DE MATERIAIS
# ========================================

@almoxarifado_bp.route('/devolucao', methods=['GET'])
@login_required
def devolucao():
    """Formulário de devolução de materiais"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('almoxarifado/devolucao.html', funcionarios=funcionarios)

@almoxarifado_bp.route('/api/itens-funcionario/<int:funcionario_id>')
@login_required
def api_itens_funcionario(funcionario_id):
    """API que retorna itens em posse do funcionário (SERIALIZADOS + CONSUMÍVEIS retornáveis)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401
    
    funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
    if not funcionario:
        return jsonify({'error': 'Funcionário não encontrado'}), 404
    
    itens_retornaveis = []
    
    # 1. SERIALIZADOS em posse (status='EM_USO' e funcionario_atual_id)
    estoques_serializados = AlmoxarifadoEstoque.query.filter_by(
        funcionario_atual_id=funcionario_id,
        status='EM_USO',
        admin_id=admin_id
    ).join(AlmoxarifadoItem).filter(
        AlmoxarifadoItem.tipo_controle == 'SERIALIZADO'
    ).all()
    
    for est in estoques_serializados:
        itens_retornaveis.append({
            'estoque_id': est.id,
            'item_id': est.item_id,
            'item_nome': est.item.nome,
            'tipo_controle': 'SERIALIZADO',
            'numero_serie': est.numero_serie,
            'obra': est.obra.nome if est.obra else 'N/A',
            'data_saida': est.updated_at.strftime('%d/%m/%Y') if est.updated_at else 'N/A'
        })
    
    # 2. CONSUMÍVEIS em posse do funcionário
    # ✅ CORREÇÃO: Buscar TODOS os movimentos de SAÍDA (não apenas permite_devolucao=True)
    movimentos_saida = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='SAIDA',
        admin_id=admin_id
    ).join(AlmoxarifadoItem).filter(
        AlmoxarifadoItem.tipo_controle == 'CONSUMIVEL'
    ).all()
    
    # Agrupar por item e calcular quantidade disponível para devolução
    consumiveis_dict = {}
    for mov in movimentos_saida:
        if mov.item_id not in consumiveis_dict:
            consumiveis_dict[mov.item_id] = {
                'item': mov.item,
                'quantidade_saida': 0,
                'quantidade_devolvida': 0
            }
        consumiveis_dict[mov.item_id]['quantidade_saida'] += mov.quantidade or 0
    
    # Subtrair devoluções já feitas
    movimentos_devolucao = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='DEVOLUCAO',
        admin_id=admin_id
    ).all()
    
    for mov in movimentos_devolucao:
        if mov.item_id in consumiveis_dict:
            consumiveis_dict[mov.item_id]['quantidade_devolvida'] += mov.quantidade or 0
    
    # Subtrair consumidos
    movimentos_consumido = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='CONSUMIDO',
        admin_id=admin_id
    ).all()
    
    for mov in movimentos_consumido:
        if mov.item_id not in consumiveis_dict:
            consumiveis_dict[mov.item_id] = {
                'item': mov.item,
                'quantidade_saida': 0,
                'quantidade_devolvida': 0
            }
        if 'quantidade_consumida' not in consumiveis_dict[mov.item_id]:
            consumiveis_dict[mov.item_id]['quantidade_consumida'] = 0
        consumiveis_dict[mov.item_id]['quantidade_consumida'] += mov.quantidade or 0
    
    # Adicionar consumíveis com quantidade disponível > 0 (SAIDA - DEVOLUCAO - CONSUMIDO)
    for item_id, dados in consumiveis_dict.items():
        quantidade_consumida = dados.get('quantidade_consumida', 0)
        qtd_disponivel = dados['quantidade_saida'] - dados['quantidade_devolvida'] - quantidade_consumida
        if qtd_disponivel > 0:
            itens_retornaveis.append({
                'item_id': item_id,
                'item_nome': dados['item'].nome,
                'tipo_controle': 'CONSUMIVEL',
                'quantidade_disponivel': qtd_disponivel,
                'unidade': dados['item'].unidade,
                'permite_devolucao': dados['item'].permite_devolucao  # ✅ Flag para frontend
            })
    
    return jsonify({'itens': itens_retornaveis})

@almoxarifado_bp.route('/processar-devolucao', methods=['POST'])
@login_required
def processar_devolucao():
    """Processa devolução de materiais (SERIALIZADO ou CONSUMIVEL)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        funcionario_id = request.form.get('funcionario_id', type=int)
        tipo_controle = request.form.get('tipo_controle')
        condicao_devolucao = request.form.get('condicao_devolucao', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validações
        if not funcionario_id:
            flash('Funcionário é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            flash('Funcionário não encontrado', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        if not condicao_devolucao:
            flash('Condição do item é obrigatória', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        # LÓGICA SERIALIZADO vs CONSUMIVEL
        if tipo_controle == 'SERIALIZADO':
            # Devolução de itens serializados (múltipla seleção)
            estoque_ids = request.form.getlist('estoque_ids[]')
            if not estoque_ids:
                flash('Selecione ao menos um item para devolução', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))
            
            itens_processados = 0
            for estoque_id in estoque_ids:
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=int(estoque_id),
                    funcionario_atual_id=funcionario_id,
                    status='EM_USO',
                    admin_id=admin_id
                ).first()
                
                if not estoque:
                    db.session.rollback()
                    flash(f'Item de estoque ID {estoque_id} não está em uso por este funcionário', 'danger')
                    return redirect(url_for('almoxarifado.devolucao'))
                
                # Atualizar estoque
                estoque.status = 'DISPONIVEL'
                estoque.funcionario_atual_id = None
                estoque.obra_id = None
                estoque.updated_at = datetime.utcnow()
                
                # Criar movimento de devolução
                movimento = AlmoxarifadoMovimento(
                    item_id=estoque.item_id,
                    tipo_movimento='DEVOLUCAO',
                    quantidade=1,
                    numero_serie=estoque.numero_serie,
                    funcionario_id=funcionario_id,
                    condicao_item=condicao_devolucao,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=estoque.obra_id or 1
                )
                db.session.add(movimento)
                itens_processados += 1
            
            db.session.commit()
            flash(f'Devolução processada com sucesso! {itens_processados} itens devolvidos por {funcionario.nome}.', 'success')
        
        else:  # CONSUMIVEL
            item_id = request.form.get('item_id', type=int)
            quantidade = request.form.get('quantidade', type=float)
            
            if not item_id or not quantidade or quantidade <= 0:
                flash('Item e quantidade válida são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))
            
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item or not item.permite_devolucao:
                flash('Item não permite devolução', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))
            
            # Criar novo registro de estoque com quantidade devolvida
            estoque = AlmoxarifadoEstoque(
                item_id=item_id,
                quantidade=quantidade,
                status='DISPONIVEL',
                admin_id=admin_id
            )
            db.session.add(estoque)
            db.session.flush()
            
            # Criar movimento de devolução
            movimento = AlmoxarifadoMovimento(
                item_id=item_id,
                tipo_movimento='DEVOLUCAO',
                quantidade=quantidade,
                funcionario_id=funcionario_id,
                condicao_item=condicao_devolucao,
                observacao=observacoes,
                estoque_id=estoque.id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=None
            )
            db.session.add(movimento)
            
            db.session.commit()
            flash(f'Devolução processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" devolvidos por {funcionario.nome}.', 'success')
        
        return redirect(url_for('almoxarifado.devolucao'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar devolução: {str(e)}')
        flash('Erro ao processar devolução de material', 'danger')
        return redirect(url_for('almoxarifado.devolucao'))

@almoxarifado_bp.route('/processar-consumo', methods=['POST'])
@login_required
def processar_consumo():
    """Processa consumo de materiais consumíveis"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        funcionario_id = request.form.get('funcionario_id', type=int)
        item_id = request.form.get('item_id', type=int)
        quantidade = request.form.get('quantidade', type=float)
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validações
        if not funcionario_id:
            flash('Funcionário é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        if not item_id or not quantidade or quantidade <= 0:
            flash('Item e quantidade válida são obrigatórios', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            flash('Funcionário não encontrado', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item or item.tipo_controle != 'CONSUMIVEL':
            flash('Item não encontrado ou não é consumível', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        # Calcular quantidade em posse
        from decimal import Decimal
        quantidade_saida = db.session.query(func.sum(AlmoxarifadoMovimento.quantidade)).filter_by(
            item_id=item_id,
            funcionario_id=funcionario_id,
            tipo_movimento='SAIDA',
            admin_id=admin_id
        ).scalar() or Decimal('0')
        
        quantidade_devolvida = db.session.query(func.sum(AlmoxarifadoMovimento.quantidade)).filter_by(
            item_id=item_id,
            funcionario_id=funcionario_id,
            tipo_movimento='DEVOLUCAO',
            admin_id=admin_id
        ).scalar() or Decimal('0')
        
        quantidade_consumida = db.session.query(func.sum(AlmoxarifadoMovimento.quantidade)).filter_by(
            item_id=item_id,
            funcionario_id=funcionario_id,
            tipo_movimento='CONSUMIDO',
            admin_id=admin_id
        ).scalar() or Decimal('0')
        
        quantidade_em_posse = quantidade_saida - quantidade_devolvida - quantidade_consumida
        
        # Verificar se tem quantidade suficiente
        if Decimal(str(quantidade)) > quantidade_em_posse:
            flash(f'Quantidade insuficiente! Funcionário possui apenas {quantidade_em_posse} {item.unidade} em posse.', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        # Criar movimento de consumo
        movimento = AlmoxarifadoMovimento(
            item_id=item_id,
            tipo_movimento='CONSUMIDO',
            quantidade=quantidade,
            funcionario_id=funcionario_id,
            observacao=observacoes,
            admin_id=admin_id,
            usuario_id=current_user.id,
            obra_id=None
        )
        db.session.add(movimento)
        db.session.commit()
        
        flash(f'Consumo registrado com sucesso! {quantidade} {item.unidade} de "{item.nome}" consumidos por {funcionario.nome}.', 'success')
        return redirect(url_for('almoxarifado.devolucao'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar consumo: {str(e)}')
        flash('Erro ao processar consumo de material', 'danger')
        return redirect(url_for('almoxarifado.devolucao'))

@almoxarifado_bp.route('/processar-devolucao-multipla', methods=['POST'])
@login_required
def processar_devolucao_multipla():
    """Processa devolução de múltiplos itens (carrinho) - TRANSAÇÃO ATÔMICA"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
    
    try:
        data = request.get_json()
        itens = data.get('itens', [])
        observacoes = data.get('observacoes', '').strip()
        
        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400
        
        # ========================================
        # FASE 1: VALIDAÇÃO PRÉVIA COMPLETA
        # ========================================
        erros = []
        itens_validados = []
        
        # Validar que todos itens têm mesmo funcionário
        funcionario_id = itens[0].get('funcionario_id')
        
        for item_data in itens:
            if item_data.get('funcionario_id') != funcionario_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesmo funcionário'}), 400
        
        # Validar que funcionário existe
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 400
        
        # Condições válidas
        condicoes_validas = ['Perfeito', 'Bom', 'Regular', 'Danificado', 'Inutilizado']
        
        # Validar cada item
        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')
            condicao_item = item_data.get('condicao_item', '').strip()
            
            # Validar: condição obrigatória
            if not condicao_item:
                erros.append(f"Item {idx+1}: Condição do item é obrigatória")
                continue
            
            # Validar: condição válida
            if condicao_item not in condicoes_validas:
                erros.append(f"Item {idx+1}: Condição '{condicao_item}' inválida")
                continue
            
            # Verificar se item existe
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                erros.append(f"Item {idx+1}: Item não encontrado")
                continue
            
            if tipo_controle == 'SERIALIZADO':
                estoque_id = item_data.get('estoque_id')
                numero_serie = item_data.get('numero_serie')
                
                # VALIDAR: Item pertence ao funcionário (status='EM_USO')?
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=estoque_id,
                    funcionario_id=funcionario_id,
                    status='EM_USO',
                    admin_id=admin_id
                ).first()
                
                if not estoque:
                    erros.append(f"Item {idx+1} ({item.nome}): Número de série {numero_serie} não está em uso pelo funcionário")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'estoque_id': estoque_id,
                    'numero_serie': numero_serie,
                    'condicao_item': condicao_item,
                    'estoque': estoque
                })
            
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade_raw = item_data.get('quantidade', 0)
                quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
                
                # Validar: quantidade > 0
                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue
                
                # VALIDAR: Item permite devolução?
                if not item.permite_devolucao:
                    erros.append(f"Item {idx+1} ({item.nome}): Item não permite devolução")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'quantidade': quantidade,
                    'condicao_item': condicao_item
                })
        
        # Se houver QUALQUER erro, abortar TUDO
        if erros:
            return jsonify({
                'success': False,
                'message': f'{len(erros)} erro(s) encontrado(s)',
                'erros': erros
            }), 400
        
        # ========================================
        # FASE 2: PROCESSAMENTO TRANSACIONAL
        # ========================================
        total_processados = 0
        total_itens_esperados = len(itens_validados)
        
        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']
            condicao_item = item_validado['condicao_item']
            
            if tipo_controle == 'SERIALIZADO':
                estoque = item_validado['estoque']
                numero_serie = item_validado['numero_serie']
                
                # Determinar novo status baseado na condição
                if condicao_item in ['Perfeito', 'Bom']:
                    estoque.status = 'DISPONIVEL'
                elif condicao_item == 'Regular':
                    estoque.status = 'DISPONIVEL'
                elif condicao_item == 'Danificado':
                    estoque.status = 'EM_MANUTENCAO'
                elif condicao_item == 'Inutilizado':
                    estoque.status = 'INUTILIZADO'
                
                # Limpar vinculo com funcionário e obra
                obra_id_movimento = estoque.obra_id
                estoque.funcionario_atual_id = None
                estoque.obra_id = None
                estoque.updated_at = datetime.utcnow()
                
                # Criar movimento de devolução
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='DEVOLUCAO',
                    quantidade=1,
                    numero_serie=numero_serie,
                    funcionario_id=funcionario_id,
                    obra_id=obra_id_movimento,
                    condicao_item=condicao_item,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                total_processados += 1
            
            else:  # CONSUMIVEL
                quantidade = item_validado['quantidade']
                
                # Criar novo registro de estoque com quantidade devolvida
                estoque = AlmoxarifadoEstoque(
                    item_id=item.id,
                    quantidade=quantidade,
                    status='DISPONIVEL',
                    admin_id=admin_id
                )
                db.session.add(estoque)
                db.session.flush()
                
                # Criar movimento de devolução
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='DEVOLUCAO',
                    quantidade=quantidade,
                    funcionario_id=funcionario_id,
                    obra_id=None,
                    condicao_item=condicao_item,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                total_processados += 1
        
        # Commit APENAS se TODOS itens foram processados
        if total_processados != total_itens_esperados:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Erro: Esperado {total_itens_esperados} itens, processado {total_processados}'
            }), 500
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{total_processados} itens devolvidos com sucesso por {funcionario.nome}!',
            'total_esperado': total_itens_esperados,
            'total_processado': total_processados
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar devolução múltipla: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao processar operação'}), 500

@almoxarifado_bp.route('/movimentacoes')
@login_required
def movimentacoes():
    """Lista todas as movimentações com filtros avançados e paginação - FASE 5"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Obter parâmetros de filtro
    page = request.args.get('page', 1, type=int)
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    tipo_movimento = request.args.get('tipo_movimento', '')
    funcionario_id = request.args.get('funcionario_id', type=int)
    obra_id = request.args.get('obra_id', type=int)
    item_id = request.args.get('item_id', type=int)
    
    # Query base com multi-tenant
    query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id)
    
    # JOIN com Item (sempre necessário)
    query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
    
    # OUTER JOIN com Funcionario e Obra
    query = query.outerjoin(Funcionario, AlmoxarifadoMovimento.funcionario_id == Funcionario.id)
    query = query.outerjoin(Obra, AlmoxarifadoMovimento.obra_id == Obra.id)
    
    # Aplicar filtros
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(AlmoxarifadoMovimento.data_movimento >= data_inicio_obj)
        except ValueError:
            flash('Data de início inválida', 'warning')
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
            # Adicionar 1 dia para incluir todo o dia final
            data_fim_obj = data_fim_obj + timedelta(days=1)
            query = query.filter(AlmoxarifadoMovimento.data_movimento < data_fim_obj)
        except ValueError:
            flash('Data de fim inválida', 'warning')
    
    if tipo_movimento:
        query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_movimento)
    
    if funcionario_id:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == funcionario_id)
    
    if obra_id:
        query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)
    
    if item_id:
        query = query.filter(AlmoxarifadoMovimento.item_id == item_id)
    
    # Ordenar por data mais recente primeiro
    query = query.order_by(AlmoxarifadoMovimento.data_movimento.desc())
    
    # Paginação (50 registros por página)
    movimentacoes_paginadas = query.paginate(page=page, per_page=50, error_out=False)
    
    # Buscar dados para os filtros (com multi-tenant)
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    # Calcular estatísticas de exibição
    total_registros = movimentacoes_paginadas.total
    inicio = (page - 1) * 50 + 1 if total_registros > 0 else 0
    fim = min(page * 50, total_registros)
    
    return render_template('almoxarifado/movimentacoes.html',
                         movimentacoes=movimentacoes_paginadas,
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         tipo_movimento=tipo_movimento,
                         funcionario_id=funcionario_id,
                         obra_id=obra_id,
                         item_id=item_id,
                         total_registros=total_registros,
                         inicio=inicio,
                         fim=fim)

@almoxarifado_bp.route('/relatorios')
@login_required
def relatorios():
    """Sistema de Relatórios do Almoxarifado - 5 Relatórios Completos"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Identificar qual relatório gerar
    relatorio_tipo = request.args.get('tipo', '')
    
    # Dados para os filtros (multi-tenant)
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    dados_relatorio = None
    
    # ========================================
    # RELATÓRIO 1: POSIÇÃO DE ESTOQUE
    # ========================================
    if relatorio_tipo == 'posicao_estoque':
        categoria_id = request.args.get('categoria_id', type=int)
        tipo_controle = request.args.get('tipo_controle', '')
        condicao = request.args.get('condicao', '')
        
        # Query base com multi-tenant
        query = AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, ativo=True)
        query = query.join(AlmoxarifadoItem, AlmoxarifadoEstoque.item_id == AlmoxarifadoItem.id)
        query = query.join(AlmoxarifadoCategoria, AlmoxarifadoItem.categoria_id == AlmoxarifadoCategoria.id)
        
        # Filtros
        if categoria_id:
            query = query.filter(AlmoxarifadoItem.categoria_id == categoria_id)
        
        if tipo_controle:
            query = query.filter(AlmoxarifadoItem.tipo_controle == tipo_controle)
        
        if condicao:
            query = query.filter(AlmoxarifadoEstoque.status == condicao)
        
        # Ordenar por categoria e item
        query = query.order_by(AlmoxarifadoCategoria.nome, AlmoxarifadoItem.nome)
        
        itens_estoque = query.all()
        
        # Agrupar por categoria
        estoque_por_categoria = {}
        for estoque in itens_estoque:
            cat_nome = estoque.item.categoria.nome
            if cat_nome not in estoque_por_categoria:
                estoque_por_categoria[cat_nome] = []
            estoque_por_categoria[cat_nome].append(estoque)
        
        # Calcular subtotais
        subtotais = {}
        for cat, itens in estoque_por_categoria.items():
            subtotal = sum([(e.valor_unitario or 0) * (e.quantidade or 0) for e in itens])
            subtotais[cat] = subtotal
        
        total_geral = sum(subtotais.values())
        
        dados_relatorio = {
            'tipo': 'posicao_estoque',
            'estoque_por_categoria': estoque_por_categoria,
            'subtotais': subtotais,
            'total_geral': total_geral,
            'filtros': {
                'categoria_id': categoria_id,
                'tipo_controle': tipo_controle,
                'condicao': condicao
            }
        }
    
    # ========================================
    # RELATÓRIO 2: MOVIMENTAÇÕES POR PERÍODO
    # ========================================
    elif relatorio_tipo == 'movimentacoes':
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        tipo_movimento = request.args.get('tipo_movimento', '')
        funcionario_id = request.args.get('funcionario_id', type=int)
        obra_id = request.args.get('obra_id', type=int)
        
        # Query base com multi-tenant
        query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id)
        query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
        query = query.outerjoin(Funcionario, and_(
            AlmoxarifadoMovimento.funcionario_id == Funcionario.id,
            Funcionario.admin_id == admin_id
        ))
        query = query.outerjoin(Obra, and_(
            AlmoxarifadoMovimento.obra_id == Obra.id,
            Obra.admin_id == admin_id
        ))
        
        # Filtros de data (obrigatório)
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(AlmoxarifadoMovimento.data_movimento >= data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_obj = data_fim_obj + timedelta(days=1)
                query = query.filter(AlmoxarifadoMovimento.data_movimento < data_fim_obj)
            except ValueError:
                pass
        
        if tipo_movimento:
            query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_movimento)
        
        if funcionario_id:
            query = query.filter(AlmoxarifadoMovimento.funcionario_id == funcionario_id)
        
        if obra_id:
            query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)
        
        query = query.order_by(AlmoxarifadoMovimento.data_movimento.desc())
        
        movimentos = query.all()
        
        # Agrupar por tipo
        movimentos_por_tipo = {
            'ENTRADA': [],
            'SAIDA': [],
            'DEVOLUCAO': []
        }
        
        for mov in movimentos:
            if mov.tipo_movimento in movimentos_por_tipo:
                movimentos_por_tipo[mov.tipo_movimento].append(mov)
        
        # Calcular subtotais por tipo
        subtotais_tipo = {}
        for tipo, movs in movimentos_por_tipo.items():
            subtotal = sum([(m.quantidade or 0) for m in movs])
            subtotais_tipo[tipo] = subtotal
        
        dados_relatorio = {
            'tipo': 'movimentacoes',
            'movimentos_por_tipo': movimentos_por_tipo,
            'subtotais_tipo': subtotais_tipo,
            'filtros': {
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'tipo_movimento': tipo_movimento,
                'funcionario_id': funcionario_id,
                'obra_id': obra_id
            }
        }
    
    # ========================================
    # RELATÓRIO 3: ITENS POR FUNCIONÁRIO
    # ========================================
    elif relatorio_tipo == 'itens_funcionario':
        funcionario_id = request.args.get('funcionario_id', type=int)
        obra_id = request.args.get('obra_id', type=int)
        
        # Query base: Itens EM_USO com multi-tenant
        query = AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, status='EM_USO')
        query = query.join(AlmoxarifadoItem, AlmoxarifadoEstoque.item_id == AlmoxarifadoItem.id)
        query = query.join(Funcionario, and_(
            AlmoxarifadoEstoque.funcionario_atual_id == Funcionario.id,
            Funcionario.admin_id == admin_id
        ))
        query = query.outerjoin(Obra, and_(
            AlmoxarifadoEstoque.obra_id == Obra.id,
            Obra.admin_id == admin_id
        ))
        
        # Filtros
        if funcionario_id:
            query = query.filter(AlmoxarifadoEstoque.funcionario_atual_id == funcionario_id)
        
        if obra_id:
            query = query.filter(AlmoxarifadoEstoque.obra_id == obra_id)
        
        query = query.order_by(Funcionario.nome, AlmoxarifadoEstoque.updated_at.desc())
        
        itens_funcionario = query.all()
        
        # Agrupar por funcionário
        itens_por_funcionario = {}
        for estoque in itens_funcionario:
            func_nome = estoque.funcionario_atual.nome if estoque.funcionario_atual else 'Sem Funcionário'
            if func_nome not in itens_por_funcionario:
                itens_por_funcionario[func_nome] = []
            itens_por_funcionario[func_nome].append(estoque)
        
        # Calcular subtotais
        subtotais_func = {}
        for func, itens in itens_por_funcionario.items():
            subtotal = sum([(e.valor_unitario or 0) * (e.quantidade or 0) for e in itens])
            subtotais_func[func] = subtotal
        
        total_geral = sum(subtotais_func.values())
        
        dados_relatorio = {
            'tipo': 'itens_funcionario',
            'itens_por_funcionario': itens_por_funcionario,
            'subtotais_func': subtotais_func,
            'total_geral': total_geral,
            'filtros': {
                'funcionario_id': funcionario_id,
                'obra_id': obra_id
            }
        }
    
    # ========================================
    # RELATÓRIO 4: CONSUMO POR OBRA
    # ========================================
    elif relatorio_tipo == 'consumo_obra':
        obra_id = request.args.get('obra_id', type=int)
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        
        # Query: SAIDA não devolvida (CONSUMIVEL ou SERIALIZADO sem DEVOLUCAO)
        query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id, tipo_movimento='SAIDA')
        query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
        query = query.join(Obra, and_(
            AlmoxarifadoMovimento.obra_id == Obra.id,
            Obra.admin_id == admin_id
        ))
        
        # Filtros
        if obra_id:
            query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(AlmoxarifadoMovimento.data_movimento >= data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_obj = data_fim_obj + timedelta(days=1)
                query = query.filter(AlmoxarifadoMovimento.data_movimento < data_fim_obj)
            except ValueError:
                pass
        
        query = query.order_by(Obra.nome, AlmoxarifadoMovimento.data_movimento.desc())
        
        saidas = query.all()
        
        # Agrupar por obra
        consumo_por_obra = {}
        for saida in saidas:
            obra_nome = saida.obra.nome if saida.obra else 'Sem Obra'
            if obra_nome not in consumo_por_obra:
                consumo_por_obra[obra_nome] = []
            consumo_por_obra[obra_nome].append(saida)
        
        # Calcular subtotais
        subtotais_obra = {}
        for obra, saidas_obra in consumo_por_obra.items():
            subtotal = sum([(s.valor_unitario or 0) * (s.quantidade or 0) for s in saidas_obra])
            subtotais_obra[obra] = subtotal
        
        total_geral = sum(subtotais_obra.values())
        
        dados_relatorio = {
            'tipo': 'consumo_obra',
            'consumo_por_obra': consumo_por_obra,
            'subtotais_obra': subtotais_obra,
            'total_geral': total_geral,
            'filtros': {
                'obra_id': obra_id,
                'data_inicio': data_inicio,
                'data_fim': data_fim
            }
        }
    
    # ========================================
    # RELATÓRIO 5: ALERTAS E PENDÊNCIAS
    # ========================================
    elif relatorio_tipo == 'alertas':
        # 1. Estoque Baixo
        itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).all()
        estoque_baixo = []
        
        for item in itens:
            if item.tipo_controle == 'SERIALIZADO':
                qtd_atual = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).count()
            else:
                qtd_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                    item_id=item.id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).scalar() or 0
            
            if qtd_atual < item.estoque_minimo:
                estoque_baixo.append({
                    'item': item,
                    'qtd_atual': qtd_atual,
                    'qtd_minima': item.estoque_minimo,
                    'diferenca': item.estoque_minimo - qtd_atual
                })
        
        # 2. Manutenção Pendente
        manutencao = AlmoxarifadoEstoque.query.filter_by(
            admin_id=admin_id,
            status='EM_MANUTENCAO'
        ).join(AlmoxarifadoItem).all()
        
        # 3. Itens não devolvidos há >30 dias
        data_limite = datetime.now() - timedelta(days=30)
        
        nao_devolvidos = AlmoxarifadoEstoque.query.filter(
            AlmoxarifadoEstoque.admin_id == admin_id,
            AlmoxarifadoEstoque.status == 'EM_USO',
            AlmoxarifadoEstoque.updated_at <= data_limite
        ).join(AlmoxarifadoItem).outerjoin(Funcionario, and_(
            AlmoxarifadoEstoque.funcionario_atual_id == Funcionario.id,
            Funcionario.admin_id == admin_id
        )).outerjoin(Obra, and_(
            AlmoxarifadoEstoque.obra_id == Obra.id,
            Obra.admin_id == admin_id
        )).all()
        
        # Calcular dias pendentes
        nao_devolvidos_com_dias = []
        for item in nao_devolvidos:
            dias_pendente = (datetime.now() - item.updated_at).days
            nao_devolvidos_com_dias.append({
                'item': item,
                'dias_pendente': dias_pendente
            })
        
        dados_relatorio = {
            'tipo': 'alertas',
            'estoque_baixo': estoque_baixo,
            'manutencao': manutencao,
            'nao_devolvidos': nao_devolvidos_com_dias,
            'filtros': {}
        }
    
    return render_template('almoxarifado/relatorios.html',
                         categorias=categorias,
                         funcionarios=funcionarios,
                         obras=obras,
                         dados_relatorio=dados_relatorio,
                         relatorio_tipo=relatorio_tipo)

# ========================================
# FORNECEDORES - CRUD COMPLETO
# ========================================

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
            
            # Validações
            if not razao_social:
                flash('Razão Social é obrigatória', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_criar'))
            
            if not cnpj:
                flash('CNPJ é obrigatório', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_criar'))
            
            # Verificar se CNPJ já existe
            existe = Fornecedor.query.filter_by(cnpj=cnpj, admin_id=admin_id).first()
            if existe:
                flash(f'Já existe um fornecedor cadastrado com o CNPJ {cnpj}', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_criar'))
            
            # Criar fornecedor
            fornecedor = Fornecedor(
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
            
            # Validações
            if not razao_social:
                flash('Razão Social é obrigatória', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_editar', id=id))
            
            if not cnpj:
                flash('CNPJ é obrigatório', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_editar', id=id))
            
            # Verificar se CNPJ já existe em outro fornecedor
            existe = Fornecedor.query.filter(
                Fornecedor.cnpj == cnpj,
                Fornecedor.admin_id == admin_id,
                Fornecedor.id != id
            ).first()
            if existe:
                flash(f'Já existe outro fornecedor cadastrado com o CNPJ {cnpj}', 'danger')
                return redirect(url_for('almoxarifado.fornecedores_editar', id=id))
            
            # Atualizar fornecedor
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
            fornecedor.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Fornecedor "{fornecedor.razao_social}" atualizado com sucesso!', 'success')
            return redirect(url_for('almoxarifado.fornecedores'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar fornecedor: {str(e)}')
            flash(f'Erro ao atualizar fornecedor: {str(e)}', 'danger')
    
    return render_template('almoxarifado/fornecedores_form.html', fornecedor=fornecedor)

@almoxarifado_bp.route('/fornecedores/deletar/<int:id>', methods=['POST'])
@login_required
def fornecedores_deletar(id):
    """Deletar fornecedor (soft delete)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    fornecedor = Fornecedor.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    try:
        # Soft delete - apenas marca como inativo
        fornecedor.ativo = False
        fornecedor.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Fornecedor "{fornecedor.razao_social}" desativado com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao desativar fornecedor: {str(e)}')
        flash(f'Erro ao desativar fornecedor: {str(e)}', 'danger')
    
    return redirect(url_for('almoxarifado.fornecedores'))

# ========================================
# CRUD MOVIMENTAÇÕES MANUAIS
# ========================================

@almoxarifado_bp.route('/movimentacoes/criar', methods=['GET', 'POST'])
@login_required
def movimentacoes_criar():
    """Criar nova movimentação manual"""
    from almoxarifado_utils import apply_movimento_manual
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            tipo_movimento = request.form.get('tipo_movimento')
            item_id = request.form.get('item_id')
            quantidade = request.form.get('quantidade')
            data_movimento = request.form.get('data_movimento')
            funcionario_id = request.form.get('funcionario_id')
            obra_id = request.form.get('obra_id')
            observacao = request.form.get('observacao', '').strip()
            impacta_estoque = request.form.get('impacta_estoque') == 'on'
            valor_unitario = request.form.get('valor_unitario')
            lote = request.form.get('lote', '').strip()
            numero_serie = request.form.get('numero_serie', '').strip()
            
            # Validações
            if not tipo_movimento or not item_id or not quantidade:
                flash('Tipo de movimento, item e quantidade são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))
            
            try:
                quantidade = float(quantidade)
                if quantidade <= 0:
                    flash('Quantidade deve ser maior que zero', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            except ValueError:
                flash('Quantidade inválida', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))
            
            # Validar data
            if data_movimento:
                data_mov = datetime.strptime(data_movimento, '%Y-%m-%d')
                if data_mov.date() > datetime.now().date():
                    flash('Data do movimento não pode ser futura', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            else:
                data_mov = datetime.now()
            
            # Validar item
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                flash('Item não encontrado', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))
            
            # Validar funcionário e obra (se fornecidos)
            if funcionario_id:
                funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
                if not funcionario:
                    flash('Funcionário não encontrado', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            else:
                funcionario_id = None
            
            if obra_id:
                obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
                if not obra:
                    flash('Obra não encontrada', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            else:
                obra_id = None
            
            # Processar valor unitário
            if valor_unitario:
                try:
                    valor_unitario = float(valor_unitario)
                except ValueError:
                    valor_unitario = None
            else:
                valor_unitario = None
            
            # Criar movimentação
            movimento = AlmoxarifadoMovimento(
                tipo_movimento=tipo_movimento,
                item_id=item_id,
                quantidade=quantidade,
                data_movimento=data_mov,
                funcionario_id=funcionario_id,
                obra_id=obra_id,
                observacao=observacao or None,
                impacta_estoque=impacta_estoque,
                origem_manual=True,
                usuario_id=current_user.id,
                admin_id=admin_id,
                valor_unitario=valor_unitario,
                lote=lote or None,
                numero_serie=numero_serie or None
            )
            
            db.session.add(movimento)
            db.session.flush()
            
            # Aplicar ao estoque se necessário
            if impacta_estoque:
                resultado = apply_movimento_manual(movimento)
                if not resultado['sucesso']:
                    db.session.rollback()
                    flash(f'Erro ao aplicar movimento ao estoque: {resultado["mensagem"]}', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            
            db.session.commit()
            
            flash(f'Movimentação manual criada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar movimentação manual: {str(e)}')
            flash(f'Erro ao criar movimentação: {str(e)}', 'danger')
            return redirect(url_for('almoxarifado.movimentacoes_criar'))
    
    # GET - Carregar dados para o formulário
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    # Item pré-selecionado da query string
    item_id_pre = request.args.get('item_id')
    
    # Data de hoje
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('almoxarifado/movimentacoes_form.html',
                         movimento=None,
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras,
                         item_id_pre=item_id_pre,
                         hoje=hoje)

@almoxarifado_bp.route('/movimentacoes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def movimentacoes_editar(id):
    """Editar movimentação manual existente com proteção contra concorrência"""
    from almoxarifado_utils import apply_movimento_manual, rollback_movimento_manual
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    movimento = AlmoxarifadoMovimento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # ===== PROTEÇÃO DE CONCORRÊNCIA: Optimistic Locking =====
            # Validar timestamp para detectar edições concorrentes
            updated_at_original = request.form.get('updated_at_original')
            if updated_at_original:
                try:
                    updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S')
                
                # Recarregar movimento do banco para verificar se foi modificado
                db.session.refresh(movimento)
                
                if movimento.updated_at and movimento.updated_at > updated_at_check:
                    flash(
                        'ERRO: Este registro foi modificado por outro usuário. '
                        'Por favor, recarregue a página e tente novamente.',
                        'danger'
                    )
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            
            # ===== TRANSAÇÃO ATÔMICA =====
            # Iniciar transação explícita para garantir atomicidade
            
            # Salvar estado anterior para rollback
            impactava_estoque_antes = movimento.impacta_estoque
            
            # Rollback do estoque anterior se estava impactando
            if impactava_estoque_antes:
                resultado = rollback_movimento_manual(movimento)
                if not resultado['sucesso']:
                    db.session.rollback()
                    flash(f'Erro ao reverter movimento anterior: {resultado["mensagem"]}', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            
            # Atualizar campos
            tipo_movimento = request.form.get('tipo_movimento')
            quantidade = request.form.get('quantidade')
            data_movimento = request.form.get('data_movimento')
            funcionario_id = request.form.get('funcionario_id')
            obra_id = request.form.get('obra_id')
            observacao = request.form.get('observacao', '').strip()
            impacta_estoque = request.form.get('impacta_estoque') == 'on'
            valor_unitario = request.form.get('valor_unitario')
            lote = request.form.get('lote', '').strip()
            numero_serie = request.form.get('numero_serie', '').strip()
            
            # Validações
            if not tipo_movimento or not quantidade:
                flash('Tipo de movimento e quantidade são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            
            try:
                quantidade = float(quantidade)
                if quantidade <= 0:
                    flash('Quantidade deve ser maior que zero', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            except ValueError:
                flash('Quantidade inválida', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            
            # Validar data
            if data_movimento:
                data_mov = datetime.strptime(data_movimento, '%Y-%m-%d')
                if data_mov.date() > datetime.now().date():
                    flash('Data do movimento não pode ser futura', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            else:
                data_mov = movimento.data_movimento
            
            # Validar funcionário e obra (se fornecidos)
            if funcionario_id:
                funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
                if not funcionario:
                    flash('Funcionário não encontrado', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            else:
                funcionario_id = None
            
            if obra_id:
                obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
                if not obra:
                    flash('Obra não encontrada', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            else:
                obra_id = None
            
            # Processar valor unitário
            if valor_unitario:
                try:
                    valor_unitario = float(valor_unitario)
                except ValueError:
                    valor_unitario = None
            else:
                valor_unitario = None
            
            # Atualizar movimento
            movimento.tipo_movimento = tipo_movimento
            movimento.quantidade = quantidade
            movimento.data_movimento = data_mov
            movimento.funcionario_id = funcionario_id
            movimento.obra_id = obra_id
            movimento.observacao = observacao or None
            movimento.impacta_estoque = impacta_estoque
            movimento.valor_unitario = valor_unitario
            movimento.lote = lote or None
            movimento.numero_serie = numero_serie or None
            
            db.session.flush()
            
            # Aplicar novo movimento ao estoque se necessário
            if impacta_estoque:
                resultado = apply_movimento_manual(movimento)
                if not resultado['sucesso']:
                    db.session.rollback()
                    flash(f'Erro ao aplicar movimento ao estoque: {resultado["mensagem"]}', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            
            db.session.commit()
            
            flash('Movimentação atualizada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens_movimentacoes', id=movimento.item_id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao editar movimentação: {str(e)}')
            flash(f'Erro ao editar movimentação: {str(e)}', 'danger')
    
    # GET - Carregar dados para o formulário
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    # Data de hoje
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('almoxarifado/movimentacoes_form.html',
                         movimento=movimento,
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras,
                         hoje=hoje)

@almoxarifado_bp.route('/movimentacoes/deletar/<int:id>', methods=['POST'])
@login_required
def movimentacoes_deletar(id):
    """Deletar movimentação manual com proteção contra concorrência"""
    from almoxarifado_utils import rollback_movimento_manual
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    movimento = AlmoxarifadoMovimento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    item_id = movimento.item_id
    
    try:
        # ===== PROTEÇÃO DE CONCORRÊNCIA: Optimistic Locking =====
        # Validar timestamp para detectar modificações concorrentes
        updated_at_original = request.form.get('updated_at_original')
        if updated_at_original:
            try:
                updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S')
            
            # Recarregar movimento do banco para verificar se foi modificado
            db.session.refresh(movimento)
            
            if movimento.updated_at and movimento.updated_at > updated_at_check:
                flash(
                    'ERRO: Este registro foi modificado por outro usuário. '
                    'A exclusão foi cancelada. Por favor, recarregue a página.',
                    'danger'
                )
                return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
        
        # ===== TRANSAÇÃO ATÔMICA =====
        
        # Rollback do estoque se estava impactando
        if movimento.impacta_estoque:
            resultado = rollback_movimento_manual(movimento)
            if not resultado['sucesso']:
                db.session.rollback()
                flash(f'Erro ao reverter estoque: {resultado["mensagem"]}', 'danger')
                return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
        
        # Hard delete (pode mudar para soft delete se necessário)
        db.session.delete(movimento)
        db.session.commit()
        
        flash('Movimentação excluída com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar movimentação: {str(e)}')
        flash(f'Erro ao excluir movimentação: {str(e)}', 'danger')
    
    # Redirecionar de volta para a página de origem
    # Se veio da lista principal de movimentações, volta para lá
    # Se veio da página do item, volta para a página do item
    referrer = request.referrer
    if referrer and '/almoxarifado/movimentacoes' in referrer and f'/itens/{item_id}' not in referrer:
        return redirect(url_for('almoxarifado.movimentacoes'))
    else:
        return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
