#!/usr/bin/env python3
"""
Health Check Endpoint para SIGE v8.0
Verifica se o sistema está funcionando corretamente em produção
"""

from flask import Blueprint, jsonify
import os
from datetime import datetime

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health_check():
    """Endpoint de verificação de saúde do sistema"""
    try:
        # Verificar conexão com banco de dados
        from app import db
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db_status = "OK"
    except Exception as e:
        db_status = f"ERRO: {str(e)}"
    
    # Verificar arquivos críticos
    critical_files = [
        'main.py',
        'views.py',
        'models.py',
        'propostas_consolidated.py'
    ]
    
    files_status = {}
    for file in critical_files:
        files_status[file] = os.path.exists(file)
    
    # Status geral
    overall_status = "OK" if db_status == "OK" and all(files_status.values()) else "ERROR"
    
    response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "8.0",
        "system": "SIGE - Sistema Integrado de Gestão Empresarial",
        "checks": {
            "database": db_status,
            "files": files_status
        },
        "environment": os.environ.get('FLASK_ENV', 'development')
    }
    
    status_code = 200 if overall_status == "OK" else 500
    return jsonify(response), status_code

@health_bp.route('/health/simple')
def simple_health():
    """Endpoint simples para verificação rápida"""
    return "OK", 200