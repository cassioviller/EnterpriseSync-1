#!/usr/bin/env python3
"""
Tenant Management Utilities - SIGE v8.0
Centralizes multitenant logic to prevent circular imports
"""

from flask_login import current_user
from models import TipoUsuario

def get_tenant_admin_id():
    """
    🔒 RESOLVER MULTITENANT UNIFICADO
    Determina o admin_id correto baseado no tipo de usuário para isolamento de dados
    - ADMIN: usa seu próprio ID (current_user.id) 
    - FUNCIONARIO: usa o admin_id da empresa que lhe deu acesso (current_user.admin_id)
    """
    if not current_user.is_authenticated:
        return None
    
    if current_user.tipo_usuario == TipoUsuario.ADMIN:
        return current_user.id
    else:
        return current_user.admin_id

def ensure_tenant_isolation(query_filter, admin_id_field='admin_id'):
    """
    Garante isolamento de dados por tenant
    """
    tenant_id = get_tenant_admin_id()
    if tenant_id:
        return query_filter.filter_by(**{admin_id_field: tenant_id})
    return query_filter

def get_safe_admin_id():
    """
    Retorna admin_id com fallback seguro para casos de desenvolvimento
    """
    tenant_id = get_tenant_admin_id()
    if tenant_id:
        return tenant_id
    
    # Fallback para desenvolvimento - usar primeiro admin disponível
    try:
        from models import Usuario
        primeiro_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
        if primeiro_admin:
            return primeiro_admin.id
    except:
        pass
    
    return 1  # Fallback absoluto