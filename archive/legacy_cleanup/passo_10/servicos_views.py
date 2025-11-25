"""
Views para Sistema de Gestão de Serviços - SIGE v8.0
Módulo completo para gestão de serviços e composições
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import (
    db, ServicoMestre, SubServico, TabelaComposicao, 
    ItemTabelaComposicao, StatusServico, TipoUnidade
)
from datetime import datetime
from decimal import Decimal
import json

servicos_bp = Blueprint('servicos', __name__)

def admin_required(f):
    """Decorator para verificar permissões de admin"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario and current_user.tipo_usuario.name in ['ADMIN', 'SUPER_ADMIN']:
            return f(*args, **kwargs)
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('main.dashboard'))
    return decorated_function

# ================================
# DASHBOARD DE SERVIÇOS
# ================================

@servicos_bp.route('/dashboard')
@admin_required
def dashboard():
    """Dashboard principal de serviços"""
    
    # Estatísticas gerais
    total_servicos = ServicoMestre.query.filter_by(admin_id=current_user.id).count()
    servicos_ativos = ServicoMestre.query.filter_by(
        admin_id=current_user.id, 
        status='ativo'
    ).count()
    
    total_subservicos = SubServico.query.filter_by(admin_id=current_user.id).count()
    total_tabelas = TabelaComposicao.query.filter_by(admin_id=current_user.id).count()
    
    # Serviços mais utilizados (top 5)
    # TODO FASE 3: Reimplementar query de serviços populares com PropostaItem
    # servicos_populares = db.session.query(
    #     ServicoMestre,
    #     db.func.count(ItemServicoPropostaDinamica.id).label('uso_count')
    # ).join(
    #     ItemServicoPropostaDinamica, 
    #     ServicoMestre.id == ItemServicoPropostaDinamica.servico_mestre_id
    # ).filter(
    #     ServicoMestre.admin_id == current_user.id
    # ).group_by(
    #     ServicoMestre.id
    # ).order_by(
    #     db.text('uso_count DESC')
    # ).limit(5).all()
    
    # Temporariamente retornando lista vazia até FASE 3
    servicos_populares = []
    
    # Serviços recentes
    servicos_recentes = ServicoMestre.query.filter_by(
        admin_id=current_user.id
    ).order_by(ServicoMestre.criado_em.desc()).limit(5).all()
    
    return render_template('servicos/dashboard.html',
                         total_servicos=total_servicos,
                         servicos_ativos=servicos_ativos,
                         total_subservicos=total_subservicos,
                         total_tabelas=total_tabelas,
                         servicos_populares=servicos_populares,
                         servicos_recentes=servicos_recentes)

# ================================
# GESTÃO DE SERVIÇOS MESTRES
# ================================

@servicos_bp.route('/servicos')
@admin_required
def listar_servicos():
    """Lista todos os serviços mestres"""
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'todos')
    search = request.args.get('search', '')
    
    query = ServicoMestre.query.filter_by(admin_id=current_user.id)
    
    if status_filter != 'todos':
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.filter(
            db.or_(
                ServicoMestre.codigo.ilike(f'%{search}%'),
                ServicoMestre.nome.ilike(f'%{search}%')
            )
        )
    
    servicos = query.order_by(ServicoMestre.codigo).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('servicos/listar_servicos.html', 
                         servicos=servicos,
                         status_filter=status_filter,
                         search=search)

@servicos_bp.route('/servicos/novo', methods=['GET', 'POST'])
@admin_required
def novo_servico():
    """Criar novo serviço mestre"""
    
    if request.method == 'POST':
        # Gerar código automático
        ultimo_servico = ServicoMestre.query.filter_by(
            admin_id=current_user.id
        ).order_by(ServicoMestre.id.desc()).first()
        
        if ultimo_servico:
            ultimo_num = int(ultimo_servico.codigo.replace('SRV', ''))
            novo_codigo = f'SRV{str(ultimo_num + 1).zfill(3)}'
        else:
            novo_codigo = 'SRV001'
        
        servico = ServicoMestre(
            admin_id=current_user.id,
            codigo=novo_codigo,
            nome=request.form['nome'],
            descricao=request.form.get('descricao', ''),
            unidade=request.form['unidade'],
            preco_base=Decimal(request.form.get('preco_base', '0')),
            margem_lucro=Decimal(request.form.get('margem_lucro', '30')),
            status=request.form.get('status', 'ativo')
        )
        
        try:
            db.session.add(servico)
            db.session.commit()
            flash(f'Serviço {servico.codigo} criado com sucesso!', 'success')
            return redirect(url_for('servicos.ver_servico', id=servico.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar serviço: {str(e)}', 'error')
    
    return render_template('servicos/novo_servico.html')

@servicos_bp.route('/servicos/<int:id>')
@admin_required
def ver_servico(id):
    """Visualizar detalhes do serviço"""
    
    servico = ServicoMestre.query.filter_by(
        id=id, admin_id=current_user.id
    ).first_or_404()
    
    return render_template('servicos/ver_servico.html', servico=servico)

@servicos_bp.route('/servicos/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_servico(id):
    """Editar serviço mestre"""
    
    servico = ServicoMestre.query.filter_by(
        id=id, admin_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        servico.nome = request.form['nome']
        servico.descricao = request.form.get('descricao', '')
        servico.unidade = request.form['unidade']
        servico.preco_base = Decimal(request.form.get('preco_base', '0'))
        servico.margem_lucro = Decimal(request.form.get('margem_lucro', '30'))
        servico.status = request.form.get('status', 'ativo')
        servico.atualizado_em = datetime.utcnow()
        
        try:
            db.session.commit()
            flash('Serviço atualizado com sucesso!', 'success')
            return redirect(url_for('servicos.ver_servico', id=servico.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar serviço: {str(e)}', 'error')
    
    return render_template('servicos/editar_servico.html', servico=servico)

# ================================
# GESTÃO DE SUBSERVIÇOS
# ================================

@servicos_bp.route('/servicos/<int:servico_id>/subservicos/novo', methods=['GET', 'POST'])
@admin_required
def novo_subservico(servico_id):
    """Adicionar subserviço a um serviço mestre"""
    
    servico = ServicoMestre.query.filter_by(
        id=servico_id, admin_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        # Gerar código automático para subserviço
        total_subs = len(servico.subservicos)
        novo_codigo = f'{servico.codigo}.{str(total_subs + 1).zfill(3)}'
        
        subservico = SubServico(
            servico_mestre_id=servico.id,
            admin_id=current_user.id,
            codigo=novo_codigo,
            nome=request.form['nome'],
            descricao=request.form.get('descricao', ''),
            unidade=request.form['unidade'],
            quantidade_base=Decimal(request.form.get('quantidade_base', '1')),
            preco_unitario=Decimal(request.form.get('preco_unitario', '0')),
            tempo_execucao=Decimal(request.form.get('tempo_execucao', '0')),
            nivel_dificuldade=request.form.get('nivel_dificuldade', 'medio'),
            status=request.form.get('status', 'ativo')
        )
        
        try:
            db.session.add(subservico)
            db.session.commit()
            flash(f'Subserviço {subservico.codigo} adicionado com sucesso!', 'success')
            return redirect(url_for('servicos.ver_servico', id=servico.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar subserviço: {str(e)}', 'error')
    
    return render_template('servicos/novo_subservico.html', servico=servico)

# ================================
# TABELAS DE COMPOSIÇÃO
# ================================

@servicos_bp.route('/tabelas')
@admin_required
def listar_tabelas():
    """Lista todas as tabelas de composição"""
    
    tabelas = TabelaComposicao.query.filter_by(
        admin_id=current_user.id
    ).order_by(TabelaComposicao.nome).all()
    
    return render_template('servicos/listar_tabelas.html', tabelas=tabelas)

@servicos_bp.route('/tabelas/nova', methods=['GET', 'POST'])
@admin_required
def nova_tabela():
    """Criar nova tabela de composição"""
    
    if request.method == 'POST':
        tabela = TabelaComposicao(
            admin_id=current_user.id,
            nome=request.form['nome'],
            descricao=request.form.get('descricao', ''),
            tipo_estrutura=request.form['tipo_estrutura'],
            area_minima=Decimal(request.form.get('area_minima', '0')),
            area_maxima=Decimal(request.form.get('area_maxima', '999999')),
            altura_minima=Decimal(request.form.get('altura_minima', '0')),
            altura_maxima=Decimal(request.form.get('altura_maxima', '999')),
            status=request.form.get('status', 'ativa')
        )
        
        try:
            db.session.add(tabela)
            db.session.commit()
            flash('Tabela de composição criada com sucesso!', 'success')
            return redirect(url_for('servicos.ver_tabela', id=tabela.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar tabela: {str(e)}', 'error')
    
    return render_template('servicos/nova_tabela.html')

@servicos_bp.route('/tabelas/<int:id>')
@admin_required
def ver_tabela(id):
    """Visualizar tabela de composição"""
    
    tabela = TabelaComposicao.query.filter_by(
        id=id, admin_id=current_user.id
    ).first_or_404()
    
    # Serviços disponíveis para adicionar
    servicos_disponiveis = ServicoMestre.query.filter_by(
        admin_id=current_user.id,
        status='ativo'
    ).order_by(ServicoMestre.nome).all()
    
    return render_template('servicos/ver_tabela.html', 
                         tabela=tabela,
                         servicos_disponiveis=servicos_disponiveis)

# ================================
# API PARA INTEGRAÇÃO COM PROPOSTAS
# ================================

@servicos_bp.route('/api/servicos')
@admin_required
def api_servicos():
    """API para listar serviços ativos"""
    
    servicos = ServicoMestre.query.filter_by(
        admin_id=current_user.id,
        status='ativo'
    ).order_by(ServicoMestre.nome).all()
    
    return jsonify([{
        'id': s.id,
        'codigo': s.codigo,
        'nome': s.nome,
        'descricao': s.descricao,
        'unidade': s.unidade,
        'preco_base': float(s.preco_base),
        'preco_final': s.preco_final,
        'total_subservicos': s.total_subservicos
    } for s in servicos])

@servicos_bp.route('/api/servicos/<int:id>/subservicos')
@admin_required
def api_subservicos(id):
    """API para listar subserviços de um serviço"""
    
    servico = ServicoMestre.query.filter_by(
        id=id, admin_id=current_user.id
    ).first_or_404()
    
    return jsonify([{
        'id': sub.id,
        'codigo': sub.codigo,
        'nome': sub.nome,
        'descricao': sub.descricao,
        'unidade': sub.unidade,
        'quantidade_base': float(sub.quantidade_base),
        'preco_unitario': float(sub.preco_unitario),
        'valor_total_base': sub.valor_total_base,
        'tempo_execucao': float(sub.tempo_execucao),
        'nivel_dificuldade': sub.nivel_dificuldade
    } for sub in servico.subservicos if sub.status == 'ativo'])

@servicos_bp.route('/api/aplicar-servico-proposta', methods=['POST'])
@admin_required
def api_aplicar_servico_proposta():
    """API para aplicar serviço completo em uma proposta"""
    
    data = request.get_json()
    servico_id = data.get('servico_id')
    proposta_id = data.get('proposta_id', 0)  # 0 = nova proposta
    incluir_subservicos = data.get('incluir_subservicos', False)
    quantidade_servico = Decimal(str(data.get('quantidade', 1)))
    
    servico = ServicoMestre.query.filter_by(
        id=servico_id, admin_id=current_user.id
    ).first_or_404()
    
    try:
        itens_criados = []
        
        # TODO FASE 3: Reimplementar com PropostaItem na FASE 3
        # Criar item principal do serviço
        # item_principal = ItemServicoPropostaDinamica(
        #     proposta_id=proposta_id if proposta_id > 0 else None,
        #     servico_mestre_id=servico.id,
        #     admin_id=current_user.id,
        #     codigo_item=servico.codigo,
        #     nome_item=servico.nome,
        #     descricao_item=servico.descricao,
        #     quantidade=quantidade_servico,
        #     unidade=servico.unidade,
        #     preco_unitario=Decimal(str(servico.preco_final)),
        #     e_servico_mestre=True,
        #     inclui_subservicos=incluir_subservicos,
        #     ordem=1
        # )
        # 
        # db.session.add(item_principal)
        # itens_criados.append({
        #     'tipo': 'servico_principal',
        #     'codigo': item_principal.codigo_item,
        #     'nome': item_principal.nome_item,
        #     'quantidade': float(item_principal.quantidade),
        #     'preco_unitario': float(item_principal.preco_unitario),
        #     'valor_total': item_principal.valor_total
        # })
        
        # TODO FASE 3: Reimplementar com PropostaItem na FASE 3
        # Adicionar subserviços se solicitado
        # if incluir_subservicos:
        #     ordem = 2
        #     for subservico in servico.subservicos:
        #         if subservico.status == 'ativo':
        #             quantidade_sub = quantidade_servico * subservico.quantidade_base
        #             
        #             item_sub = ItemServicoPropostaDinamica(
        #                 proposta_id=proposta_id if proposta_id > 0 else None,
        #                 servico_mestre_id=servico.id,
        #                 admin_id=current_user.id,
        #                 codigo_item=subservico.codigo,
        #                 nome_item=f"  └─ {subservico.nome}",
        #                 descricao_item=subservico.descricao,
        #                 quantidade=quantidade_sub,
        #                 unidade=subservico.unidade,
        #                 preco_unitario=subservico.preco_unitario,
        #                 e_servico_mestre=False,
        #                 inclui_subservicos=False,
        #                 ordem=ordem
        #             )
        #             
        #             db.session.add(item_sub)
        #             itens_criados.append({
        #                 'tipo': 'subservico',
        #                 'codigo': item_sub.codigo_item,
        #                 'nome': item_sub.nome_item,
        #                 'quantidade': float(item_sub.quantidade),
        #                 'preco_unitario': float(item_sub.preco_unitario),
        #                 'valor_total': item_sub.valor_total
        #             })
        #             ordem += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Serviço {servico.codigo} aplicado com sucesso!',
            'itens_criados': itens_criados,
            'total_itens': len(itens_criados),
            'valor_total': sum(item['valor_total'] for item in itens_criados)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao aplicar serviço: {str(e)}'
        }), 500