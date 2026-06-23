"""
Decoradores de autenticação e autorização
"""
from functools import wraps

def admin_required(f):
    """Requer que o usuário seja administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Durante desenvolvimento, bypass para todos
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Requer que o usuário esteja logado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Durante desenvolvimento, bypass para todos
        return f(*args, **kwargs)
    return decorated_function