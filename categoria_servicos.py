"""
SISTEMA DE GESTÃO DE CATEGORIAS DE SERVIÇOS - SIGE v8.0
Módulo para gerenciamento completo de categorias de serviços
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user
from models import db, CategoriaServico
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

categorias_bp = Blueprint('categorias_servicos', __name__, url_prefix='/categorias-servicos')

# Função para obter admin_id dinâmico
def get_admin_id():
    """Obtém admin_id dinamicamente baseado no usuário logado"""
    try:
        if hasattr(current_user, 'tipo_usuario'):
            if current_user.tipo_usuario.name in ['ADMIN', 'SUPER_ADMIN']:
                return current_user.id
            else:
                return current_user.admin_id or 10
        return 10
    except:
        return 10

@categorias_bp.route('/', methods=['GET'])
def index():
    """Página principal de gestão de categorias"""
    try:
        admin_id = get_admin_id()
        categorias = CategoriaServico.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(CategoriaServico.nome).all()
        
        return render_template('servicos/categorias.html',
                             categorias=categorias)
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar página de categorias: {str(e)}")
        flash(f'Erro ao carregar categorias: {str(e)}', 'error')
        return redirect('/servicos')

# ================================
# ROTAS API PARA CATEGORIAS
# ================================

@categorias_bp.route('/api/listar')
def api_listar_categorias():
    """API para listar categorias do usuário"""
    try:
        admin_id = get_admin_id()
        
        categorias = CategoriaServico.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(CategoriaServico.ordem, CategoriaServico.nome).all()
        
        return jsonify({
            'success': True,
            'categorias': [{
                'id': cat.id,
                'nome': cat.nome,
                'descricao': cat.descricao,
                'cor': cat.cor,
                'icone': cat.icone,
                'ordem': cat.ordem,
                'ativo': cat.ativo
            } for cat in categorias]
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar categorias: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@categorias_bp.route('/api/criar', methods=['POST'])
def api_criar_categoria():
    """API para criar nova categoria"""
    try:
        admin_id = get_admin_id()
        dados = request.get_json()
        
        nome = dados.get('nome', '').strip()
        if not nome:
            return jsonify({
                'success': False,
                'error': 'Nome da categoria é obrigatório'
            }), 400
        
        # Verificar se categoria já existe
        existente = CategoriaServico.query.filter_by(
            nome=nome,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if existente:
            return jsonify({
                'success': False,
                'error': f'Categoria "{nome}" já existe'
            }), 400
        
        # Obter próxima ordem
        max_ordem = db.session.query(db.func.max(CategoriaServico.ordem)).filter_by(
            admin_id=admin_id,
            ativo=True
        ).scalar() or 0
        
        # Criar nova categoria
        nova_categoria = CategoriaServico(
            nome=nome,
            descricao=dados.get('descricao', ''),
            admin_id=admin_id,
            ordem=max_ordem + 1,
            cor='#198754',
            icone='fas fa-tag',
            ativo=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.session.add(nova_categoria)
        db.session.commit()
        
        logger.info(f"✅ Nova categoria criada: {nome} (ID: {nova_categoria.id})")
        
        return jsonify({
            'success': True,
            'message': 'Categoria criada com sucesso',
            'categoria': {
                'id': nova_categoria.id,
                'nome': nova_categoria.nome,
                'descricao': nova_categoria.descricao
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar categoria: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@categorias_bp.route('/api/<int:categoria_id>/excluir', methods=['DELETE'])
def api_excluir_categoria(categoria_id):
    """API para excluir categoria (soft delete)"""
    try:
        admin_id = get_admin_id()
        
        categoria = CategoriaServico.query.filter_by(
            id=categoria_id,
            admin_id=admin_id
        ).first()
        
        if not categoria:
            return jsonify({
                'success': False,
                'error': 'Categoria não encontrada'
            }), 404
        
        # Soft delete
        categoria.ativo = False
        categoria.updated_at = datetime.now()
        
        db.session.commit()
        
        logger.info(f"✅ Categoria excluída: {categoria.nome} (ID: {categoria_id})")
        
        return jsonify({
            'success': True,
            'message': 'Categoria excluída com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao excluir categoria: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@categorias_bp.route('/api/<int:categoria_id>/editar', methods=['POST'])
def api_editar_categoria(categoria_id):
    """API para editar categoria existente"""
    try:
        admin_id = get_admin_id()
        dados = request.get_json()
        
        categoria = CategoriaServico.query.filter_by(
            id=categoria_id,
            admin_id=admin_id
        ).first()
        
        if not categoria:
            return jsonify({
                'success': False,
                'error': 'Categoria não encontrada'
            }), 404
        
        nome = dados.get('nome', '').strip()
        if not nome:
            return jsonify({
                'success': False,
                'error': 'Nome da categoria é obrigatório'
            }), 400
        
        # Verificar se nome já existe (exceto para a categoria atual)
        existente = CategoriaServico.query.filter(
            CategoriaServico.nome == nome,
            CategoriaServico.admin_id == admin_id,
            CategoriaServico.id != categoria_id,
            CategoriaServico.ativo == True
        ).first()
        
        if existente:
            return jsonify({
                'success': False,
                'error': f'Já existe uma categoria com o nome "{nome}"'
            }), 400
        
        # Atualizar categoria
        categoria.nome = nome
        categoria.descricao = dados.get('descricao', '').strip()
        categoria.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Categoria atualizada com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao editar categoria: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500