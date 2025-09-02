"""
SISTEMA DE GESTÃO DE CATEGORIAS DE SERVIÇOS - SIGE v8.0
Módulo para gerenciamento completo de categorias de serviços
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user
from models import db
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

# Usar modelo existente do models.py para evitar conflito
from models import CategoriaServico


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
        categoria_existente = CategoriaServico.query.filter_by(
            nome=nome,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if categoria_existente:
            return jsonify({
                'success': False,
                'error': f'Categoria "{nome}" já existe'
            }), 400
        
        # Criar nova categoria
        nova_categoria = CategoriaServico(
            nome=nome,
            descricao=dados.get('descricao', ''),
            cor=dados.get('cor', '#198754'),
            icone=dados.get('icone', 'tools'),
            admin_id=admin_id
        )
        
        db.session.add(nova_categoria)
        db.session.commit()
        
        logger.info(f"✅ Categoria criada: {nome} (admin_id={admin_id})")
        
        return jsonify({
            'success': True,
            'categoria': {
                'id': nova_categoria.id,
                'nome': nova_categoria.nome,
                'descricao': nova_categoria.descricao,
                'cor': nova_categoria.cor,
                'icone': nova_categoria.icone,
                'ordem': nova_categoria.ordem,
                'ativo': nova_categoria.ativo
            },
            'message': f'Categoria "{nome}" criada com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar categoria: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@categorias_bp.route('/api/<int:categoria_id>/atualizar', methods=['PUT'])
def api_atualizar_categoria(categoria_id):
    """API para atualizar categoria existente"""
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
        
        # Verificar se outro categoria já usa este nome
        categoria_existente = CategoriaServico.query.filter(
            CategoriaServico.nome == nome,
            CategoriaServico.admin_id == admin_id,
            CategoriaServico.id != categoria_id,
            CategoriaServico.ativo == True
        ).first()
        
        if categoria_existente:
            return jsonify({
                'success': False,
                'error': f'Categoria "{nome}" já existe'
            }), 400
        
        # Atualizar categoria
        categoria.nome = nome
        categoria.descricao = dados.get('descricao', categoria.descricao)
        categoria.cor = dados.get('cor', categoria.cor)
        categoria.icone = dados.get('icone', categoria.icone)
        categoria.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Categoria atualizada: {nome} (ID: {categoria_id})")
        
        return jsonify({
            'success': True,
            'categoria': {
                'id': categoria.id,
                'nome': categoria.nome,
                'descricao': categoria.descricao,
                'cor': categoria.cor,
                'icone': categoria.icone,
                'ordem': categoria.ordem,
                'ativo': categoria.ativo
            },
            'message': f'Categoria "{nome}" atualizada com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao atualizar categoria: {str(e)}")
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
        categoria.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Categoria excluída: {categoria.nome} (ID: {categoria_id})")
        
        return jsonify({
            'success': True,
            'message': f'Categoria "{categoria.nome}" excluída com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao excluir categoria: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ================================
# INICIALIZAR CATEGORIAS PADRÃO
# ================================

def inicializar_categorias_padrao(admin_id):
    """Inicializa categorias padrão para um novo admin"""
    categorias_padrao = [
        {'nome': 'Estrutural', 'cor': '#dc3545', 'icone': 'building'},
        {'nome': 'Soldagem', 'cor': '#fd7e14', 'icone': 'fire'},
        {'nome': 'Pintura', 'cor': '#6f42c1', 'icone': 'palette'},
        {'nome': 'Instalação', 'cor': '#20c997', 'icone': 'tools'},
        {'nome': 'Acabamento', 'cor': '#0dcaf0', 'icone': 'brush'},
        {'nome': 'Manutenção', 'cor': '#198754', 'icone': 'gear'},
        {'nome': 'Outros', 'cor': '#6c757d', 'icone': 'question-circle'}
    ]
    
    try:
        for i, cat_data in enumerate(categorias_padrao):
            # Verificar se categoria já existe
            categoria_existente = CategoriaServico.query.filter_by(
                nome=cat_data['nome'],
                admin_id=admin_id
            ).first()
            
            if not categoria_existente:
                categoria = CategoriaServico(
                    nome=cat_data['nome'],
                    cor=cat_data['cor'],
                    icone=cat_data['icone'],
                    ordem=i + 1,
                    admin_id=admin_id
                )
                db.session.add(categoria)
        
        db.session.commit()
        logger.info(f"✅ Categorias padrão inicializadas para admin_id={admin_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao inicializar categorias padrão: {str(e)}")

def obter_categorias_disponiveis(admin_id):
    """Obtém lista de categorias disponíveis para um admin"""
    try:
        # Verificar se admin tem categorias
        count_categorias = CategoriaServico.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).count()
        
        # Se não tem categorias, inicializar padrão
        if count_categorias == 0:
            inicializar_categorias_padrao(admin_id)
        
        # Retornar categorias
        categorias = CategoriaServico.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(CategoriaServico.ordem, CategoriaServico.nome).all()
        
        return [cat.nome for cat in categorias]
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter categorias: {str(e)}")
        # Fallback para categorias básicas
        return ['Estrutural', 'Soldagem', 'Pintura', 'Instalação', 'Acabamento', 'Manutenção', 'Outros']