"""
ENDPOINT DE DEBUG ESPECÍFICO PARA RDO EM PRODUÇÃO
Sistema para diagnosticar problemas de salvamento em produção
"""

from flask import Blueprint, jsonify, request, render_template
from models import db, RDO, RDOServicoSubatividade, Obra, Servico
from bypass_auth import obter_admin_id
import traceback
import json
from datetime import datetime

debug_rdo_bp = Blueprint('debug_rdo', __name__)

@debug_rdo_bp.route('/debug/rdo-status')
def debug_rdo_status():
    """Status detalhado do sistema RDO em produção"""
    try:
        admin_id = obter_admin_id()
        
        status_data = {
            'timestamp': datetime.now().isoformat(),
            'admin_id': admin_id,
            'database_status': 'connected',
            'tables_status': {},
            'recent_rdos': [],
            'error_summary': []
        }
        
        # Verificar tabelas críticas
        try:
            rdo_count = RDO.query.filter(RDO.obra_id.in_(
                db.session.query(Obra.id).filter_by(admin_id=admin_id)
            )).count()
            status_data['tables_status']['rdo'] = f"{rdo_count} RDOs encontrados"
        except Exception as e:
            status_data['tables_status']['rdo'] = f"ERRO: {e}"
            
        try:
            subatividades_count = RDOServicoSubatividade.query.join(RDO).join(Obra).filter(
                Obra.admin_id == admin_id
            ).count()
            status_data['tables_status']['rdo_subatividades'] = f"{subatividades_count} subatividades"
        except Exception as e:
            status_data['tables_status']['rdo_subatividades'] = f"ERRO: {e}"
            
        try:
            servicos_count = Servico.query.filter_by(admin_id=admin_id, ativo=True).count()
            status_data['tables_status']['servicos'] = f"{servicos_count} serviços ativos"
        except Exception as e:
            status_data['tables_status']['servicos'] = f"ERRO: {e}"
            
        # Buscar RDOs recentes
        try:
            rdos_recentes = db.session.query(RDO, Obra).join(Obra).filter(
                Obra.admin_id == admin_id
            ).order_by(RDO.id.desc()).limit(5).all()
            
            for rdo, obra in rdos_recentes:
                subatividades_rdo = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).count()
                
                status_data['recent_rdos'].append({
                    'id': rdo.id,
                    'numero_rdo': rdo.numero_rdo,
                    'obra_nome': obra.nome,
                    'data_relatorio': rdo.data_relatorio.isoformat() if rdo.data_relatorio else None,
                    'subatividades_count': subatividades_rdo,
                    'created_at': rdo.created_at.isoformat() if hasattr(rdo, 'created_at') and rdo.created_at else None
                })
        except Exception as e:
            status_data['error_summary'].append(f"Erro ao buscar RDOs recentes: {e}")
        
        return jsonify(status_data)
        
    except Exception as e:
        error_data = {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"🚨 ERRO DEBUG RDO STATUS: {e}")
        return jsonify(error_data), 500

@debug_rdo_bp.route('/debug/rdo-last-errors')
def debug_rdo_last_errors():
    """Últimos erros específicos de RDO"""
    try:
        # Ler logs de erro específicos do RDO
        error_logs = []
        
        try:
            with open('/app/logs/production_errors.log', 'r') as f:
                lines = f.readlines()
                # Filtrar apenas linhas relacionadas ao RDO
                rdo_lines = [line for line in lines if 'RDO' in line or 'rdo' in line]
                error_logs = rdo_lines[-20:]  # Últimas 20 linhas relacionadas ao RDO
        except FileNotFoundError:
            error_logs = ['Log de erros RDO não encontrado']
            
        return jsonify({
            'success': True,
            'rdo_errors': error_logs,
            'count': len(error_logs),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@debug_rdo_bp.route('/debug/rdo-simulate-error')
def debug_rdo_simulate_error():
    """Simular erro para testar sistema de logging (apenas desenvolvimento)"""
    if request.environ.get('FLASK_ENV') != 'production':
        return jsonify({
            'success': False,
            'message': 'Simulação de erro apenas disponível em desenvolvimento'
        }), 403
        
    try:
        # Simular diferentes tipos de erro
        error_type = request.args.get('type', 'generic')
        
        if error_type == 'database':
            # Forçar erro de banco de dados
            db.session.execute("SELECT * FROM tabela_inexistente")
        elif error_type == 'rdo':
            # Simular erro específico do RDO
            raise Exception("Erro simulado no sistema RDO para teste de logging")
        else:
            # Erro genérico
            raise Exception("Erro simulado para teste do sistema de logging")
            
    except Exception as e:
        # O sistema de logging deve capturar este erro
        return jsonify({
            'success': False,
            'message': 'Erro simulado capturado',
            'error': str(e),
            'logged': True
        }), 500

print("✅ Debug RDO Blueprint registrado")