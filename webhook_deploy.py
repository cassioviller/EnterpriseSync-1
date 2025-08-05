#!/usr/bin/env python3
"""
WEBHOOK DE DEPLOY AUTOMÁTICO
Endpoint para deploy automático via webhook
"""

from flask import Flask, request, jsonify
import subprocess
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webhook_deploy.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# App Flask para webhook
webhook_app = Flask(__name__)

# Token de segurança (deve ser configurado em produção)
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'sua_chave_secreta_aqui')

@webhook_app.route('/deploy', methods=['POST'])
def webhook_deploy():
    """Endpoint para receber webhooks de deploy"""
    try:
        # Verificar autenticação
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != WEBHOOK_SECRET:
            logger.warning("🔒 Tentativa de acesso não autorizada")
            return jsonify({'error': 'Não autorizado'}), 401
        
        # Log da requisição
        logger.info("🔔 Webhook de deploy recebido")
        logger.info(f"   IP: {request.remote_addr}")  
        logger.info(f"   User-Agent: {request.headers.get('User-Agent', 'N/A')}")
        
        # Executar deploy automático
        logger.info("🚀 Iniciando deploy automático...")
        
        result = subprocess.run([
            'python', 'auto_deploy_producao.py', '--auto'
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            logger.info("✅ Deploy executado com sucesso")
            return jsonify({
                'status': 'success',
                'message': 'Deploy executado com sucesso',
                'timestamp': datetime.now().isoformat(),
                'output': result.stdout
            })
        else:
            logger.error(f"❌ Erro no deploy: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': 'Erro no deploy',
                'error': result.stderr,
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro interno: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Erro interno do servidor',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@webhook_app.route('/status', methods=['GET'])
def webhook_status():
    """Status do webhook"""
    return jsonify({
        'status': 'active',
        'service': 'SIGE Auto Deploy Webhook',
        'version': '1.0',
        'timestamp': datetime.now().isoformat()
    })

@webhook_app.route('/health', methods=['GET'])
def health_check():
    """Health check para monitoramento"""
    try:
        # Verificar se consegue conectar no banco
        from app import app, db
        from sqlalchemy import text
        
        with app.app_context():
            db.session.execute(text('SELECT 1'))
            
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    logger.info("🌐 Iniciando webhook de deploy automático...")
    logger.info(f"🔑 Token configurado: {'✅ SIM' if WEBHOOK_SECRET != 'sua_chave_secreta_aqui' else '❌ USAR PADRÃO'}")
    
    # Executar webhook na porta 8080
    webhook_app.run(
        host='0.0.0.0',
        port=int(os.environ.get('WEBHOOK_PORT', 8080)),
        debug=False
    )