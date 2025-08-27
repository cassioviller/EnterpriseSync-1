"""
Blueprint para Gestão de Serviços
Sistema SIGE - Estruturas do Vale
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date
from sqlalchemy import and_, desc, asc
from app import db
from models_servicos import CategoriaServico, ServicoGestao, SubatividadeServico, ServicoObraGestao, TabelaPreco, ItemTabelaPreco
from models import Obra
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)

# Criar blueprint
servicos_bp = Blueprint('servicos', __name__, url_prefix='/servicos')

def get_admin_id():
    """Retorna o admin_id para multi-tenancy"""
    return 10  # Desenvolvimento - substituir pela lógica de autenticação real

@servicos_bp.route('/')
def dashboard():
    """Dashboard principal do módulo de serviços"""
    try:
        admin_id = get_admin_id()
        
        # Estatísticas gerais
        total_categorias = CategoriaServico.query.filter_by(admin_id=admin_id, ativo=True).count()
        total_servicos = ServicoGestao.query.filter_by(admin_id=admin_id, ativo=True).count()
        total_subatividades = SubatividadeServico.query.filter_by(admin_id=admin_id, ativo=True).count()
        total_tabelas = TabelaPreco.query.filter_by(admin_id=admin_id, ativo=True).count()
        
        # Serviços mais utilizados nas obras
        servicos_populares = db.session.query(
            ServicoGestao.nome,
            db.func.count(ServicoObraGestao.id).label('total_obras')
        ).join(ServicoObraGestao).filter(
            ServicoGestao.admin_id == admin_id,
            ServicoObraGestao.admin_id == admin_id
        ).group_by(ServicoGestao.id, ServicoGestao.nome).order_by(desc('total_obras')).limit(5).all()
        
        # Categorias com mais serviços
        categorias_stats = db.session.query(
            CategoriaServico.nome,
            CategoriaServico.cor_hexadecimal,
            db.func.count(ServicoGestao.id).label('total_servicos')
        ).outerjoin(ServicoGestao).filter(
            CategoriaServico.admin_id == admin_id,
            CategoriaServico.ativo == True
        ).group_by(CategoriaServico.id).order_by(desc('total_servicos')).all()
        
        print(f"DEBUG SERVICOS DASHBOARD: {total_categorias} categorias, {total_servicos} serviços")
        
        return render_template('servicos/dashboard.html',
                               total_categorias=total_categorias,
                               total_servicos=total_servicos,
                               total_subatividades=total_subatividades,
                               total_tabelas=total_tabelas,
                               servicos_populares=servicos_populares,
                               categorias_stats=categorias_stats)
    except Exception as e:
        print(f"ERRO SERVICOS DASHBOARD: {str(e)}")
        flash(f'Erro ao carregar dashboard: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

# ============= CATEGORIAS =============

@servicos_bp.route('/categorias')
def listar_categorias():
    """Lista todas as categorias de serviços"""
    try:
        admin_id = get_admin_id()
        categorias = CategoriaServico.query.filter_by(admin_id=admin_id).order_by(CategoriaServico.nome).all()
        
        # Contar serviços por categoria
        for categoria in categorias:
            categoria.total_servicos = ServicoGestao.query.filter_by(categoria_id=categoria.id, ativo=True).count()
        
        return render_template('servicos/listar_categorias.html', categorias=categorias)
    except Exception as e:
        print(f"ERRO LISTAR CATEGORIAS: {str(e)}")
        flash(f'Erro ao listar categorias: {str(e)}', 'error')
        return redirect(url_for('servicos.dashboard'))

@servicos_bp.route('/categorias/nova', methods=['GET', 'POST'])
def nova_categoria():
    """Criar nova categoria de serviço"""
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            
            categoria = CategoriaServico()
            categoria.nome = request.form['nome']
            categoria.descricao = request.form.get('descricao', '')
            categoria.cor_hexadecimal = request.form.get('cor_hexadecimal', '#007bff')
            categoria.admin_id = admin_id
            
            db.session.add(categoria)
            db.session.commit()
            
            flash('Categoria criada com sucesso!', 'success')
            return redirect(url_for('servicos.listar_categorias'))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO NOVA CATEGORIA: {str(e)}")
            flash(f'Erro ao criar categoria: {str(e)}', 'error')
    
    return render_template('servicos/nova_categoria.html')

@servicos_bp.route('/categorias/<int:id>/editar', methods=['GET', 'POST'])
def editar_categoria(id):
    """Editar categoria existente"""
    admin_id = get_admin_id()
    categoria = CategoriaServico.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            categoria.nome = request.form['nome']
            categoria.descricao = request.form.get('descricao', '')
            categoria.cor_hexadecimal = request.form.get('cor_hexadecimal', '#007bff')
            categoria.ativo = 'ativo' in request.form
            
            db.session.commit()
            flash('Categoria atualizada com sucesso!', 'success')
            return redirect(url_for('servicos.listar_categorias'))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO EDITAR CATEGORIA: {str(e)}")
            flash(f'Erro ao atualizar categoria: {str(e)}', 'error')
    
    return render_template('servicos/editar_categoria.html', categoria=categoria)

# ============= SERVIÇOS =============

@servicos_bp.route('/listar')
def listar_servicos():
    """Lista todos os serviços"""
    try:
        admin_id = get_admin_id()
        
        # Filtros
        categoria_id = request.args.get('categoria_id', type=int)
        busca = request.args.get('busca', '').strip()
        
        # Query base
        query = ServicoGestao.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if categoria_id:
            query = query.filter_by(categoria_id=categoria_id)
        
        if busca:
            query = query.filter(ServicoGestao.nome.ilike(f'%{busca}%'))
        
        servicos = query.order_by(ServicoGestao.nome).all()
        categorias = CategoriaServico.query.filter_by(admin_id=admin_id, ativo=True).order_by(CategoriaServico.nome).all()
        
        return render_template('servicos/listar_servicos.html', 
                               servicos=servicos, 
                               categorias=categorias,
                               categoria_id=categoria_id,
                               busca=busca)
    except Exception as e:
        print(f"ERRO LISTAR SERVICOS: {str(e)}")
        flash(f'Erro ao listar serviços: {str(e)}', 'error')
        return redirect(url_for('servicos.dashboard'))

@servicos_bp.route('/novo', methods=['GET', 'POST'])
def novo_servico():
    """Criar novo serviço"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            servico = ServicoGestao()
            servico.nome = request.form['nome']
            servico.descricao = request.form.get('descricao', '')
            servico.categoria_id = request.form['categoria_id']
            servico.unidade = request.form['unidade']
            servico.unidade_simbolo = request.form['unidade_simbolo']
            servico.preco_base = float(request.form.get('preco_base', 0))
            servico.tempo_estimado = int(request.form.get('tempo_estimado', 1))
            servico.admin_id = admin_id
            
            db.session.add(servico)
            db.session.flush()  # Para obter o ID
            
            # Adicionar subatividades se fornecidas
            subatividades_nomes = request.form.getlist('subatividade_nome[]')
            subatividades_percentuais = request.form.getlist('subatividade_percentual[]')
            
            for i, nome in enumerate(subatividades_nomes):
                if nome.strip():
                    percentual = float(subatividades_percentuais[i]) if i < len(subatividades_percentuais) else 0
                    subatividade = SubatividadeServico()
                    subatividade.servico_id = servico.id
                    subatividade.nome = nome.strip()
                    subatividade.percentual_padrao = percentual
                    subatividade.ordem = i + 1
                    subatividade.admin_id = admin_id
                    db.session.add(subatividade)
            
            db.session.commit()
            flash('Serviço criado com sucesso!', 'success')
            return redirect(url_for('servicos.listar_servicos'))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO NOVO SERVICO: {str(e)}")
            flash(f'Erro ao criar serviço: {str(e)}', 'error')
    
    categorias = CategoriaServico.query.filter_by(admin_id=admin_id, ativo=True).order_by(CategoriaServico.nome).all()
    return render_template('servicos/novo_servico.html', categorias=categorias)

@servicos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
def editar_servico(id):
    """Editar serviço existente"""
    admin_id = get_admin_id()
    servico = ServicoGestao.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            servico.nome = request.form['nome']
            servico.descricao = request.form.get('descricao', '')
            servico.categoria_id = request.form['categoria_id']
            servico.unidade = request.form['unidade']
            servico.unidade_simbolo = request.form['unidade_simbolo']
            servico.preco_base = float(request.form.get('preco_base', 0))
            servico.tempo_estimado = int(request.form.get('tempo_estimado', 1))
            servico.ativo = 'ativo' in request.form
            servico.atualizado_em = datetime.utcnow()
            
            # Atualizar subatividades existentes
            subatividades_ids = request.form.getlist('subatividade_id[]')
            subatividades_nomes = request.form.getlist('subatividade_nome[]')
            subatividades_percentuais = request.form.getlist('subatividade_percentual[]')
            
            # Marcar todas as subatividades como inativas primeiro
            SubatividadeServico.query.filter_by(servico_id=servico.id).update({'ativo': False})
            
            # Processar subatividades
            for i, nome in enumerate(subatividades_nomes):
                if nome.strip():
                    percentual = float(subatividades_percentuais[i]) if i < len(subatividades_percentuais) else 0
                    
                    if i < len(subatividades_ids) and subatividades_ids[i]:
                        # Atualizar existente
                        subatividade = SubatividadeServico.query.get(subatividades_ids[i])
                        if subatividade:
                            subatividade.nome = nome.strip()
                            subatividade.percentual_padrao = percentual
                            subatividade.ordem = i + 1
                            subatividade.ativo = True
                    else:
                        # Criar nova
                        subatividade = SubatividadeServico()
                        subatividade.servico_id = servico.id
                        subatividade.nome = nome.strip()
                        subatividade.percentual_padrao = percentual
                        subatividade.ordem = i + 1
                        subatividade.admin_id = admin_id
                        db.session.add(subatividade)
            
            db.session.commit()
            flash('Serviço atualizado com sucesso!', 'success')
            return redirect(url_for('servicos.listar_servicos'))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO EDITAR SERVICO: {str(e)}")
            flash(f'Erro ao atualizar serviço: {str(e)}', 'error')
    
    categorias = CategoriaServico.query.filter_by(admin_id=admin_id, ativo=True).order_by(CategoriaServico.nome).all()
    return render_template('servicos/editar_servico.html', servico=servico, categorias=categorias)

# ============= TABELAS DE PREÇO =============

@servicos_bp.route('/tabelas')
def listar_tabelas():
    """Lista todas as tabelas de preços"""
    try:
        admin_id = get_admin_id()
        tabelas = TabelaPreco.query.filter_by(admin_id=admin_id).order_by(desc(TabelaPreco.criado_em)).all()
        
        return render_template('servicos/listar_tabelas.html', tabelas=tabelas)
    except Exception as e:
        print(f"ERRO LISTAR TABELAS: {str(e)}")
        flash(f'Erro ao listar tabelas: {str(e)}', 'error')
        return redirect(url_for('servicos.dashboard'))

@servicos_bp.route('/tabelas/nova', methods=['GET', 'POST'])
def nova_tabela():
    """Criar nova tabela de preços"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            # Se marcada como padrão, desmarcar outras
            if 'padrao' in request.form:
                TabelaPreco.query.filter_by(admin_id=admin_id).update({'padrao': False})
            
            vigencia_fim = None
            if request.form.get('vigencia_fim'):
                vigencia_fim = datetime.strptime(request.form['vigencia_fim'], '%Y-%m-%d').date()
            
            tabela = TabelaPreco()
            tabela.nome = request.form['nome']
            tabela.descricao = request.form.get('descricao', '')
            tabela.vigencia_inicio = datetime.strptime(request.form['vigencia_inicio'], '%Y-%m-%d').date()
            tabela.vigencia_fim = vigencia_fim
            tabela.padrao = 'padrao' in request.form
            tabela.admin_id = admin_id
            
            db.session.add(tabela)
            db.session.commit()
            
            flash('Tabela de preços criada com sucesso!', 'success')
            return redirect(url_for('servicos.ver_tabela', id=tabela.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO NOVA TABELA: {str(e)}")
            flash(f'Erro ao criar tabela: {str(e)}', 'error')
    
    return render_template('servicos/nova_tabela.html')

@servicos_bp.route('/tabelas/<int:id>')
def ver_tabela(id):
    """Visualizar tabela de preços com seus itens"""
    admin_id = get_admin_id()
    tabela = TabelaPreco.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Buscar itens da tabela com informações do serviço
    itens = db.session.query(ItemTabelaPreco, Servico, CategoriaServico).join(
        Servico, ItemTabelaPreco.servico_id == Servico.id
    ).join(
        CategoriaServico, Servico.categoria_id == CategoriaServico.id
    ).filter(
        ItemTabelaPreco.tabela_id == id,
        ItemTabelaPreco.admin_id == admin_id
    ).order_by(CategoriaServico.nome, Servico.nome).all()
    
    # Serviços disponíveis para adicionar (que não estão na tabela)
    servicos_na_tabela = [item[0].servico_id for item in itens]
    servicos_disponiveis = Servico.query.filter(
        Servico.admin_id == admin_id,
        Servico.ativo == True,
        ~Servico.id.in_(servicos_na_tabela)
    ).order_by(Servico.nome).all()
    
    return render_template('servicos/ver_tabela.html', 
                           tabela=tabela, 
                           itens=itens,
                           servicos_disponiveis=servicos_disponiveis)

# ============= API ENDPOINTS =============

@servicos_bp.route('/api/categorias')
def api_categorias():
    """API para listar categorias"""
    admin_id = get_admin_id()
    categorias = CategoriaServico.query.filter_by(admin_id=admin_id, ativo=True).order_by(CategoriaServico.nome).all()
    
    return jsonify([{
        'id': c.id,
        'nome': c.nome,
        'cor_hexadecimal': c.cor_hexadecimal
    } for c in categorias])

@servicos_bp.route('/api/servicos/<int:categoria_id>')
def api_servicos_categoria(categoria_id):
    """API para listar serviços de uma categoria"""
    admin_id = get_admin_id()
    servicos = Servico.query.filter_by(
        admin_id=admin_id, 
        categoria_id=categoria_id, 
        ativo=True
    ).order_by(Servico.nome).all()
    
    return jsonify([{
        'id': s.id,
        'nome': s.nome,
        'unidade': s.unidade,
        'unidade_simbolo': s.unidade_simbolo,
        'preco_base': float(s.preco_base),
        'subatividades': [{
            'id': sub.id,
            'nome': sub.nome,
            'percentual_padrao': float(sub.percentual_padrao)
        } for sub in s.subatividades if sub.ativo]
    } for s in servicos])

@servicos_bp.route('/api/tabela/<int:tabela_id>/adicionar-item', methods=['POST'])
def api_adicionar_item_tabela(tabela_id):
    """API para adicionar item à tabela de preços"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        # Verificar se o item já existe
        item_existente = ItemTabelaPreco.query.filter_by(
            tabela_id=tabela_id,
            servico_id=data['servico_id'],
            admin_id=admin_id
        ).first()
        
        if item_existente:
            return jsonify({'error': 'Serviço já está na tabela'}), 400
        
        item = ItemTabelaPreco()
        item.tabela_id = tabela_id
        item.servico_id = data['servico_id']
        item.preco_unitario = float(data['preco_unitario'])
        item.observacoes = data.get('observacoes', '')
        item.admin_id = admin_id
        
        db.session.add(item)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Item adicionado à tabela'})
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO API ADICIONAR ITEM: {str(e)}")
        return jsonify({'error': str(e)}), 500