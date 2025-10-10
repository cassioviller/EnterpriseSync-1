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
        
        if estoque_atual < item.estoque_minimo:
            itens_estoque_baixo.append({
                'item': item,
                'estoque_atual': estoque_atual,
                'estoque_minimo': item.estoque_minimo
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
    
    return render_template('almoxarifado/entrada.html', itens=itens)

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
        
        # Validações básicas
        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
        
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item:
            flash('Item não encontrado', 'danger')
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
            for serie in series:
                estoque = AlmoxarifadoEstoque(
                    item_id=item_id,
                    numero_serie=serie,
                    quantidade=1,
                    status='DISPONIVEL',
                    admin_id=admin_id
                )
                db.session.add(estoque)
                
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='ENTRADA',
                    quantidade=1,
                    numero_serie=serie,
                    nota_fiscal=nota_fiscal,
                    observacao=observacoes,
                    estoque_id=None,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=None
                )
                db.session.add(movimento)
                movimentos_criados += 1
            
            db.session.commit()
            flash(f'Entrada processada com sucesso! {movimentos_criados} itens serializados cadastrados.', 'success')
        
        else:  # CONSUMIVEL
            quantidade = request.form.get('quantidade', type=float)
            if not quantidade or quantidade <= 0:
                flash('Quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
            
            # Criar 1 registro de estoque com quantidade
            estoque = AlmoxarifadoEstoque(
                item_id=item_id,
                quantidade=quantidade,
                status='DISPONIVEL',
                admin_id=admin_id
            )
            db.session.add(estoque)
            db.session.flush()
            
            # Criar 1 movimento
            movimento = AlmoxarifadoMovimento(
                item_id=item_id,
                tipo_movimento='ENTRADA',
                quantidade=quantidade,
                nota_fiscal=nota_fiscal,
                observacao=observacoes,
                estoque_id=estoque.id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=None
            )
            db.session.add(movimento)
            
            db.session.commit()
            flash(f'Entrada processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" cadastrados.', 'success')
        
        return redirect(url_for('almoxarifado.entrada'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar entrada: {str(e)}')
        flash('Erro ao processar entrada de material', 'danger')
        return redirect(url_for('almoxarifado.entrada'))

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
                estoque.funcionario_id = funcionario_id
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
            quantidade = request.form.get('quantidade', type=float)
            if not quantidade or quantidade <= 0:
                flash('Quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('almoxarifado.saida'))
            
            # Verificar quantidade disponível
            quantidade_disponivel = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                item_id=item_id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).scalar() or 0
            
            if quantidade > quantidade_disponivel:
                flash(f'Quantidade insuficiente! Disponível: {quantidade_disponivel} {item.unidade}', 'danger')
                return redirect(url_for('almoxarifado.saida'))
            
            # Consumir quantidade de estoque disponível (FIFO)
            estoques = AlmoxarifadoEstoque.query.filter_by(
                item_id=item_id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).order_by(AlmoxarifadoEstoque.created_at).all()
            
            quantidade_restante = quantidade
            for est in estoques:
                if quantidade_restante <= 0:
                    break
                
                if est.quantidade >= quantidade_restante:
                    est.quantidade -= quantidade_restante
                    quantidade_restante = 0
                    if est.quantidade == 0:
                        est.status = 'CONSUMIDO'
                else:
                    quantidade_restante -= est.quantidade
                    est.quantidade = 0
                    est.status = 'CONSUMIDO'
                
                est.updated_at = datetime.utcnow()
            
            # Criar movimento
            movimento = AlmoxarifadoMovimento(
                item_id=item_id,
                tipo_movimento='SAIDA',
                quantidade=quantidade,
                funcionario_id=funcionario_id,
                obra_id=obra_id,
                observacao=observacoes,
                admin_id=admin_id,
                usuario_id=current_user.id
            )
            db.session.add(movimento)
            
            db.session.commit()
            flash(f'Saída processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" entregues para {funcionario.nome}.', 'success')
        
        return redirect(url_for('almoxarifado.saida'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar saída: {str(e)}')
        flash('Erro ao processar saída de material', 'danger')
        return redirect(url_for('almoxarifado.saida'))

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
    
    # 1. SERIALIZADOS em posse (status='EM_USO' e funcionario_id)
    estoques_serializados = AlmoxarifadoEstoque.query.filter_by(
        funcionario_id=funcionario_id,
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
    
    # 2. CONSUMÍVEIS retornáveis (permite_devolucao=True)
    # Buscar movimentos de SAÍDA deste funcionário para itens retornáveis
    movimentos_saida = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='SAIDA',
        admin_id=admin_id
    ).join(AlmoxarifadoItem).filter(
        AlmoxarifadoItem.tipo_controle == 'CONSUMIVEL',
        AlmoxarifadoItem.permite_devolucao == True
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
    
    # Adicionar consumíveis com quantidade disponível > 0
    for item_id, dados in consumiveis_dict.items():
        qtd_disponivel = dados['quantidade_saida'] - dados['quantidade_devolvida']
        if qtd_disponivel > 0:
            itens_retornaveis.append({
                'item_id': item_id,
                'item_nome': dados['item'].nome,
                'tipo_controle': 'CONSUMIVEL',
                'quantidade_disponivel': qtd_disponivel,
                'unidade': dados['item'].unidade
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
                    funcionario_id=funcionario_id,
                    status='EM_USO',
                    admin_id=admin_id
                ).first()
                
                if not estoque:
                    db.session.rollback()
                    flash(f'Item de estoque ID {estoque_id} não está em uso por este funcionário', 'danger')
                    return redirect(url_for('almoxarifado.devolucao'))
                
                # Atualizar estoque
                estoque.status = 'DISPONIVEL'
                estoque.funcionario_id = None
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
