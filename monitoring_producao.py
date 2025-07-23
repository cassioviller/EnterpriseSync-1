from flask import Blueprint, jsonify
from datetime import datetime
import time
from app import app, db
from models import Usuario, Funcionario, Obra

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/health')
def health_check():
    """Health check para load balancer"""
    try:
        # Teste rápido de banco
        db.session.execute('SELECT 1').scalar()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '8.0',
            'database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@monitoring_bp.route('/metrics')
def metrics():
    """Métricas básicas do sistema"""
    try:
        usuarios_count = Usuario.query.count()
        funcionarios_count = Funcionario.query.count()
        obras_count = Obra.query.count()
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'counts': {
                'usuarios': usuarios_count,
                'funcionarios': funcionarios_count,
                'obras': obras_count
            },
            'system': 'operational'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Registrar no app principal
app.register_blueprint(monitoring_bp, url_prefix='/api/monitoring')
