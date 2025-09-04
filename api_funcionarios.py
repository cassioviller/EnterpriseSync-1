"""
API para funcionários - Sistema RDO
"""

from flask import Blueprint, jsonify, request
from models import db, Funcionario
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Blueprint
api_funcionarios_bp = Blueprint('api_funcionarios', __name__, url_prefix='/api')

def get_admin_id():
    """Obter admin_id do usuário atual"""
    try:
        from utils.auth_utils import get_admin_id_from_user
        return get_admin_id_from_user()
    except ImportError:
        # bypass_auth removido - usar admin_id do current_user
        from flask_login import current_user
        return getattr(current_user, 'admin_id', current_user.id)

@api_funcionarios_bp.route('/funcionarios-ativos', methods=['GET'])
def funcionarios_ativos():
    """Retorna lista de funcionários ativos para autocomplete"""
    try:
        admin_id = get_admin_id()
        logger.info(f"🔍 Buscando funcionários ativos para admin_id={admin_id}")
        
        # Buscar funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Converter para JSON
        funcionarios_data = []
        for func in funcionarios:
            funcionarios_data.append({
                'id': func.id,
                'nome': func.nome,
                'cargo': 'Funcionário',  # Campo padrão
                'valor_hora': float(func.salario / 160) if func.salario else 15.0,  # Salário/160h
                'telefone': func.telefone,
                'email': func.email
            })
        
        logger.info(f"✅ Encontrados {len(funcionarios_data)} funcionários ativos")
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_data,
            'total': len(funcionarios_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar funcionários: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'funcionarios': []
        }), 500

@api_funcionarios_bp.route('/funcionarios/buscar', methods=['GET'])
def buscar_funcionarios():
    """Busca funcionários com filtro de texto"""
    try:
        admin_id = get_admin_id()
        termo = request.args.get('q', '').strip()
        
        logger.info(f"🔍 Buscando funcionários com termo: '{termo}' para admin_id={admin_id}")
        
        # Query base
        query = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        )
        
        # Filtrar por termo se fornecido
        if termo:
            query = query.filter(
                Funcionario.nome.ilike(f'%{termo}%')
            )
        
        funcionarios = query.order_by(Funcionario.nome).limit(50).all()
        
        # Converter para JSON
        funcionarios_data = []
        for func in funcionarios:
            funcionarios_data.append({
                'id': func.id,
                'nome': func.nome,
                'cargo': 'Funcionário',  # Campo padrão
                'valor_hora': float(func.salario / 160) if func.salario else 15.0,  # Salário/160h
                'telefone': func.telefone,
                'email': func.email,
                'text': f"{func.nome} - Funcionário" # Para autocomplete
            })
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_data,
            'total': len(funcionarios_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na busca: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'funcionarios': []
        }), 500

@api_funcionarios_bp.route('/funcionarios/<int:funcionario_id>', methods=['GET'])
def obter_funcionario(funcionario_id):
    """Obtém dados de um funcionário específico"""
    try:
        admin_id = get_admin_id()
        
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not funcionario:
            return jsonify({
                'success': False,
                'error': 'Funcionário não encontrado'
            }), 404
        
        return jsonify({
            'success': True,
            'funcionario': {
                'id': funcionario.id,
                'nome': funcionario.nome,
                'cargo': 'Funcionário',  # Campo padrão
                'valor_hora': float(funcionario.salario / 160) if funcionario.salario else 15.0,  # Salário/160h
                'telefone': funcionario.telefone,
                'email': funcionario.email
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter funcionário: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500