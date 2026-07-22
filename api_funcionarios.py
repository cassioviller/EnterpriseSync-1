"""
API para funcionários - Sistema RDO
"""

from flask import Blueprint, jsonify, request
from models import db, Funcionario, TipoUsuario
from services.funcionario_metrics import calcular_valor_hora, get_modo_remuneracao
import logging
from flask_login import login_required


def _valor_hora_api(func):
    """Resolve valor/hora considerando v1 (salário) e v2 (diária)."""
    modo = get_modo_remuneracao(func)
    if modo == 'diaria':
        return float(func.valor_diaria or 0) / 8.0 if func.valor_diaria else 0.0
    vh = calcular_valor_hora(func)
    if vh:
        return vh
    return float(func.salario / 220.0) if func.salario else 0.0

# Configurar logging
logger = logging.getLogger(__name__)

# Blueprint
api_funcionarios_bp = Blueprint('api_funcionarios', __name__, url_prefix='/api')

def get_admin_id():
    """Tenant do usuário autenticado — falha segura.

    Fase 0 / R3 — o `try` importava `utils.auth_utils`, módulo que NÃO
    EXISTE no repositório: o `except ImportError` era portanto o único
    caminho executado, e o seu ramo anônimo escolhia o admin com mais
    funcionários, caindo em `return 10`. Com as rotas deste blueprint sem
    decorator de autenticação, era listagem de funcionários de uma empresa
    arbitrária para visitante não autenticado.
    """
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()

@api_funcionarios_bp.route('/funcionarios-ativos', methods=['GET'])
@login_required
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
                'valor_hora': _valor_hora_api(func),  # Salário/160h
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
@login_required
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
                'valor_hora': _valor_hora_api(func),  # Salário/160h
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
@login_required
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
                'valor_hora': _valor_hora_api(funcionario),  # Salário/160h
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