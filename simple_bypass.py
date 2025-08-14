"""
Sistema simples de bypass de autenticação
"""

from app import app
from models import TipoUsuario
import flask_login

# Criar usuário mock simples
class MockUser:
    def __init__(self):
        self.id = 4
        self.email = 'admin@estruturasdovale.com.br'
        self.nome = 'Admin Estruturas do Vale'
        self.tipo_usuario = TipoUsuario.ADMIN
        self.admin_id = None
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        
    def get_id(self):
        return str(self.id)

# Substituir current_user globalmente
flask_login.current_user = MockUser()

print("🔓 Bypass simples ativado - admin@estruturasdovale.com.br (ID: 4)")