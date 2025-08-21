"""
Helper para sistema multitenant que funciona em desenvolvimento e produção
"""
from flask_login import current_user
import os

def get_admin_id():
    """
    Retorna o admin_id correto baseado no ambiente e usuário
    Funciona tanto em desenvolvimento (com bypass) quanto em produção
    """
    try:
        # Verificar se estamos em desenvolvimento com bypass
        if os.getenv('FLASK_ENV') == 'development':
            # Tentar importar bypass se disponível
            try:
                from bypass_auth import MockCurrentUser
                mock_user = MockCurrentUser()
                return getattr(mock_user, 'admin_id', None) or mock_user.id
            except ImportError:
                pass
        
        # Lógica para produção ou desenvolvimento sem bypass
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            # Para funcionário, usar admin_id. Para admin, usar o próprio ID
            if hasattr(current_user, 'tipo_usuario'):
                if hasattr(current_user.tipo_usuario, 'value'):
                    # SQLAlchemy Enum
                    if current_user.tipo_usuario.value == 'funcionario':
                        return getattr(current_user, 'admin_id', current_user.id)
                elif hasattr(current_user.tipo_usuario, 'name'):
                    # Flask-Login Enum
                    if current_user.tipo_usuario.name == 'FUNCIONARIO':
                        return getattr(current_user, 'admin_id', current_user.id)
            
            # Para admin ou casos não identificados, usar próprio ID
            return current_user.id
        
        # Fallback para casos não autenticados ou problemas
        return None
        
    except Exception as e:
        print(f"ERRO get_admin_id: {e}")
        # Em caso de erro, tentar usar o ID do usuário atual
        try:
            return current_user.id if hasattr(current_user, 'id') else None
        except:
            return None

def get_current_user_safe():
    """
    Retorna o current_user de forma segura, funcionando em dev e produção
    """
    try:
        # Em desenvolvimento com bypass
        if os.getenv('FLASK_ENV') == 'development':
            try:
                from bypass_auth import MockCurrentUser
                return MockCurrentUser()
            except ImportError:
                pass
        
        # Retornar current_user normal
        return current_user
        
    except Exception:
        return current_user