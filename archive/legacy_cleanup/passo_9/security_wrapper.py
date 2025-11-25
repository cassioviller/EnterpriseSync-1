"""
Security Wrapper para isolamento rigoroso de dados por ambiente
Arquiteto: Padrão de segregação com audit trail e validação em runtime
"""
from functools import wraps
from flask import current_app
from models import Servico, db
from datetime import datetime
import logging

# Configurar logger específico para auditoria de segurança
audit_logger = logging.getLogger('security_audit')
audit_logger.setLevel(logging.INFO)

# Handler para arquivo de auditoria
import os
log_handler = logging.FileHandler('/home/runner/workspace/security_audit.log')
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - SECURITY - %(message)s'
))
audit_logger.addHandler(log_handler)

def validate_admin_isolation(func):
    """
    Decorator que garante isolamento rigoroso de dados por admin_id
    Logs de auditoria para detectar vazamentos
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Capturar contexto da requisição
        try:
            from flask_login import current_user
            if hasattr(current_user, 'admin_id'):
                expected_admin_id = current_user.admin_id
            else:
                expected_admin_id = None
        except:
            expected_admin_id = None
            
        # Log inicial
        audit_logger.info(f"QUERY_START - Function: {func.__name__} - Expected_admin_id: {expected_admin_id}")
        
        # Executar função original
        result = func(*args, **kwargs)
        
        # Validar resultado se contém serviços
        if hasattr(result, '__iter__') and result:
            try:
                # Verificar se são objetos Servico
                servicos_encontrados = []
                for item in result:
                    if hasattr(item, 'admin_id') and hasattr(item, 'nome'):
                        servicos_encontrados.append({
                            'id': getattr(item, 'id', None),
                            'nome': getattr(item, 'nome', None),
                            'admin_id': getattr(item, 'admin_id', None)
                        })
                
                if servicos_encontrados:
                    admin_ids_encontrados = set(s['admin_id'] for s in servicos_encontrados)
                    
                    # ALERTA CRÍTICO: Múltiplos admin_ids
                    if len(admin_ids_encontrados) > 1:
                        audit_logger.error(f"🚨 VAZAMENTO_DETECTADO - Function: {func.__name__} - Expected: {expected_admin_id} - Found: {admin_ids_encontrados} - Servicos: {[s['nome'] for s in servicos_encontrados]}")
                        
                    # ALERTA: admin_id inesperado
                    if expected_admin_id and expected_admin_id not in admin_ids_encontrados:
                        audit_logger.warning(f"⚠️ ADMIN_ID_INESPERADO - Function: {func.__name__} - Expected: {expected_admin_id} - Found: {admin_ids_encontrados}")
                    
                    # Log normal
                    audit_logger.info(f"QUERY_SUCCESS - Function: {func.__name__} - Servicos: {len(servicos_encontrados)} - Admin_IDs: {admin_ids_encontrados}")
                        
            except Exception as e:
                audit_logger.error(f"VALIDATION_ERROR - Function: {func.__name__} - Error: {str(e)}")
        
        return result
    return wrapper

@validate_admin_isolation
def get_servicos_seguros(admin_id, ativo=True):
    """
    Consulta SEGURA de serviços com validação rigorosa de isolamento
    """
    if not admin_id:
        audit_logger.error("🚨 ADMIN_ID_NULL - Tentativa de consulta sem admin_id")
        return []
    
    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=ativo).all()
    
    # Validação dupla - garantir que TODOS os serviços têm o admin_id correto
    servicos_validados = []
    for servico in servicos:
        if servico.admin_id != admin_id:
            audit_logger.error(f"🚨 VAZAMENTO_CRITICO - Servico {servico.nome} (ID: {servico.id}) tem admin_id {servico.admin_id} mas foi consultado para admin_id {admin_id}")
            continue
        servicos_validados.append(servico)
    
    return servicos_validados

def log_api_call(api_name, obra_id, admin_id, servicos_count=None, servicos_nomes=None):
    """
    Log estruturado para auditoria de APIs
    """
    audit_logger.info(f"API_CALL - {api_name} - obra_id: {obra_id} - admin_id: {admin_id} - servicos_count: {servicos_count} - servicos: {servicos_nomes}")

# Health Check para detectar contaminação
def health_check_environment_isolation():
    """
    Verifica se há contaminação de dados entre ambientes
    Retorna dict com status e alertas
    """
    try:
        # Verificar se há serviços órfãos (sem admin_id ou com admin_id inválido)
        orphan_services = Servico.query.filter(Servico.admin_id.is_(None)).all()
        
        # Verificar se há admin_ids inesperados
        admin_ids = [r[0] for r in db.session.query(Servico.admin_id).distinct().all() if r[0] is not None]
        expected_admin_ids = [2, 10, 50]  # Produção, Dev, Teste
        unexpected_admin_ids = [aid for aid in admin_ids if aid not in expected_admin_ids]
        
        status = "OK"
        alerts = []
        
        if orphan_services:
            status = "CRITICAL"
            alerts.append(f"Encontrados {len(orphan_services)} serviços órfãos sem admin_id")
            
        if unexpected_admin_ids:
            status = "WARNING" if status == "OK" else status
            alerts.append(f"Admin_IDs inesperados: {unexpected_admin_ids}")
        
        return {
            "status": status,
            "alerts": alerts,
            "admin_ids_found": admin_ids,
            "orphan_services": len(orphan_services),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }