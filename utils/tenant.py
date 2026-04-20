#!/usr/bin/env python3
"""
Tenant Management Utilities - SIGE v8.0
Centralizes multitenant logic to prevent circular imports
"""

from flask_login import current_user
from models import TipoUsuario
import logging

# Configure logging for tenant operations
logger = logging.getLogger('tenant')
logger.setLevel(logging.INFO)

def get_tenant_admin_id():
    """
    🔒 RESOLVER MULTITENANT UNIFICADO SEGURO
    Determina o admin_id correto baseado APENAS no usuário autenticado
    SEM auto-detecção para evitar vazamento de dados entre empresas
    - ADMIN: usa seu próprio ID (current_user.id) 
    - FUNCIONARIO: usa o admin_id da empresa que lhe deu acesso (current_user.admin_id)
    - FALHA SEGURA: Retorna None se dados inconsistentes
    """
    if not current_user.is_authenticated:
        return None
    
    # Lógica baseada APENAS no usuário autenticado
    if current_user.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return current_user.id
    else:
        return current_user.admin_id

def ensure_tenant_isolation(query_filter, admin_id_field='admin_id'):
    """
    Garante isolamento de dados por tenant - FALHA SEGURA
    """
    tenant_id = get_tenant_admin_id()
    if tenant_id:
        return query_filter.filter_by(**{admin_id_field: tenant_id})
    
    # SEGURANÇA: NUNCA retornar dados sem tenant válido
    from flask import abort
    logger.error("❌ ERRO CRÍTICO DE SEGURANÇA: Tentativa de acesso sem tenant válido!")
    abort(403)

def require_tenant():
    """
    Valida que usuário tem tenant válido - OBRIGATÓRIO para rotas sensíveis
    """
    if not current_user.is_authenticated:
        from flask import abort
        logger.error("❌ Acesso negado: Usuário não autenticado")
        abort(401)
    
    tenant_id = get_tenant_admin_id()
    if not tenant_id:
        from flask import abort
        logger.error(f"❌ Acesso negado: Usuário {current_user.email} sem tenant válido")
        abort(403)
    
    return tenant_id

def is_v2_active():
    """
    Verifica se o tenant atual está usando a V2 do sistema (Feature Flag).
    Retorna True apenas se o admin do tenant tem versao_sistema == 'v2'.
    Exportada para o contexto Jinja via context_processor em app.py.
    """
    from flask_login import current_user
    from models import Usuario, TipoUsuario

    # Em contexto background (seed, threads, jobs) current_user pode ser None
    # ou um proxy sem request context — não quebrar.
    try:
        if current_user is None or not current_user.is_authenticated:
            return False
    except Exception:
        return False

    if current_user.tipo_usuario == TipoUsuario.ADMIN:
        return getattr(current_user, 'versao_sistema', 'v1') == 'v2'

    if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        return False

    if current_user.admin_id:
        admin = Usuario.query.get(current_user.admin_id)
        return admin is not None and getattr(admin, 'versao_sistema', 'v1') == 'v2'

    return False


def get_safe_admin_id():
    """
    Retorna admin_id com fallback SEGURO apenas para desenvolvimento
    """
    tenant_id = get_tenant_admin_id()
    if tenant_id:
        return tenant_id
    
    # DESENVOLVIMENTO: Fallback apenas se explicitamente permitido
    import os
    if os.environ.get('ALLOW_TENANT_AUTODETECT') == 'true':
        logger.warning("⚠️ DESENVOLVIMENTO: Usando fallback de tenant - NUNCA usar em produção!")
        try:
            from models import Usuario
            primeiro_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
            if primeiro_admin:
                return primeiro_admin.id
        except Exception as e:
            logger.error(f"Erro no fallback de desenvolvimento: {e}")
    
    # Falha segura - sem admin_id válido
    logger.error("❌ ERRO CRÍTICO: Nenhum admin_id válido encontrado!")
    return None