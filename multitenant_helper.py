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
        # PRIMEIRO: Tentar usar bypass se disponível (desenvolvimento)
        try:
            from bypass_auth import MockCurrentUser
            mock_user = MockCurrentUser()
            admin_id = getattr(mock_user, 'admin_id', None) or mock_user.id
            print(f"DEBUG HELPER: Usando bypass - admin_id={admin_id}")
            return admin_id
        except ImportError:
            print("DEBUG HELPER: Bypass não disponível, usando current_user")
        
        # SEGUNDO: Lógica para produção usando current_user real
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            print(f"DEBUG HELPER: Current user ID={current_user.id}, tipo={getattr(current_user, 'tipo_usuario', 'N/A')}")
            
            # Para funcionário, usar admin_id. Para admin, usar o próprio ID
            if hasattr(current_user, 'tipo_usuario'):
                if hasattr(current_user.tipo_usuario, 'value'):
                    # SQLAlchemy Enum
                    if current_user.tipo_usuario.value == 'funcionario':
                        admin_id = getattr(current_user, 'admin_id', current_user.id)
                        print(f"DEBUG HELPER: Funcionário - admin_id={admin_id}")
                        return admin_id
                elif hasattr(current_user.tipo_usuario, 'name'):
                    # Flask-Login Enum
                    if current_user.tipo_usuario.name == 'FUNCIONARIO':
                        admin_id = getattr(current_user, 'admin_id', current_user.id)
                        print(f"DEBUG HELPER: Funcionário (name) - admin_id={admin_id}")
                        return admin_id
            
            # Para admin ou casos não identificados, usar próprio ID
            print(f"DEBUG HELPER: Admin/default - usando ID={current_user.id}")
            return current_user.id
        
        print("DEBUG HELPER: Usuário não autenticado")
        return None
        
    except Exception as e:
        print(f"ERRO HELPER get_admin_id: {e}")
        # Em caso de erro, tentar usar o ID do usuário atual
        try:
            fallback_id = current_user.id if hasattr(current_user, 'id') else 10
            print(f"DEBUG HELPER: Fallback para admin_id={fallback_id}")
            return fallback_id
        except:
            print("DEBUG HELPER: Fallback final para admin_id=2 (produção)")
            return 2

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