"""
Helper para sistema multitenant que funciona em desenvolvimento e produção.
Usa current_user do Flask-Login diretamente (sem bypass).
"""
from flask_login import current_user
import logging
import os

logger = logging.getLogger(__name__)

def get_admin_id():
    """
    Retorna o admin_id correto baseado no usuário autenticado.
    - Admin: retorna o próprio ID
    - Funcionário: retorna o admin_id do funcionário
    """
    try:
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            if hasattr(current_user, 'tipo_usuario'):
                tipo = None
                if hasattr(current_user.tipo_usuario, 'value'):
                    tipo = current_user.tipo_usuario.value
                elif hasattr(current_user.tipo_usuario, 'name'):
                    tipo = current_user.tipo_usuario.name.lower()
                
                if tipo == 'funcionario':
                    admin_id = getattr(current_user, 'admin_id', current_user.id)
                    logger.debug(f"Funcionário autenticado - admin_id={admin_id}")
                    return admin_id
            
            logger.debug(f"Admin/default autenticado - ID={current_user.id}")
            return current_user.id
        
        logger.warning("Usuário não autenticado ao buscar admin_id")
        return None
        
    except Exception as e:
        logger.error(f"Erro em get_admin_id: {e}")
        try:
            if hasattr(current_user, 'id'):
                return current_user.id
        except Exception:
            pass
        return None

def get_current_user_safe():
    """
    Retorna o current_user de forma segura
    """
    return current_user