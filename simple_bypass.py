"""
Sistema simples de bypass de autenticação com Flask-Login
"""

from app import app, login_manager
from models import TipoUsuario, Usuario
from flask_login import UserMixin
import flask_login

# Criar usuário mock compatível com Flask-Login
class MockUser(UserMixin):
    def __init__(self):
        self.id = 4
        self.email = 'admin@estruturasdovale.com.br'
        self.nome = 'Admin Estruturas do Vale'
        self.tipo_usuario = TipoUsuario.ADMIN
        self.admin_id = None
        
    def get_id(self):
        return str(self.id)

# Mock user_loader para o Flask-Login
@login_manager.user_loader
def load_user(user_id):
    if int(user_id) == 4:
        return MockUser()
    return None

# Patch para current_user retornar nosso mock
original_current_user = flask_login.current_user.__class__

class MockCurrentUserProxy:
    def __init__(self):
        self._user = MockUser()
    
    def __getattr__(self, name):
        return getattr(self._user, name)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

# Substituir o current_user
flask_login.current_user = MockCurrentUserProxy()

print("🔓 Bypass Flask-Login ativado - admin@estruturasdovale.com.br (ID: 4)")