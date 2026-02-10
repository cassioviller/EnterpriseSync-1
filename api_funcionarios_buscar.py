#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API para busca de funcionários com autocomplete
Sistema SIGE v8.0 - Módulo de RDO
"""

from flask import Blueprint, request, jsonify, session
from models import Funcionario, Usuario
import logging

# Configurar logging específico para este módulo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar blueprint para busca de funcionários
api_buscar_funcionarios_bp = Blueprint('api_buscar_funcionarios', __name__)

@api_buscar_funcionarios_bp.route('/api/funcionarios/buscar', methods=['GET'])
def buscar_funcionarios():
    """
    Busca funcionários por nome (autocomplete)
    """
    try:
        # Obter termo de busca
        termo = request.args.get('q', '').strip()
        
        if len(termo) < 2:
            return jsonify({
                'success': False,
                'error': 'Termo de busca deve ter pelo menos 2 caracteres'
            }), 400
        
        # Sistema de bypass para desenvolvimento
        admin_id = 10  # Fixo para desenvolvimento
        
        # Em produção seria:
        # if 'user_id' not in session:
        #     return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        # 
        # usuario = Usuario.query.get(session['user_id'])
        # if not usuario:
        #     return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        # 
        # admin_id = usuario.admin_id
        
        logger.info(f"[DEBUG] Buscando funcionários com termo '{termo}' para admin_id={admin_id}")
        
        # Buscar funcionários que correspondem ao termo
        funcionarios = Funcionario.query.filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            Funcionario.nome.ilike(f'%{termo}%')
        ).order_by(Funcionario.nome).limit(10).all()
        
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
        
            logger.info(f"[OK] Encontrados {len(funcionarios_data)} funcionários")
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_data,
            'total': len(funcionarios_data)
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Erro na busca de funcionários: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

if __name__ == '__main__':
    logger.info("API de busca de funcionários carregada")