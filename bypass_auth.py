"""
Sistema de bypass de autenticação para desenvolvimento
Este módulo cria um usuário mock para facilitar o desenvolvimento e testes
"""
from flask import session, g
from werkzeug.security import generate_password_hash
import logging

# Flag para ativar/desativar o bypass
BYPASS_ATIVO = True

print("🔓 Sistema de bypass de autenticação ativado")
print("👤 Usuário mock: admin@valeverde.com (ADMIN)")

# Sobrescrever flask_login.current_user para desenvolvimento
import flask_login
from types import SimpleNamespace

class MockCurrentUser:
    """Usuário mock para bypass de autenticação"""
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    @property
    def id(self):
        return 10  # ID do usuário Vale Verde
    
    @property
    def admin_id(self):
        return 10  # Para usuários ADMIN, admin_id é o próprio ID
    
    @property
    def email(self):
        return 'admin@valeverde.com'
    
    @property
    def nome(self):
        return 'Administrador Vale Verde'
    
    @property
    def tipo_usuario(self):
        # Simular TipoUsuario.ADMIN
        tipo = SimpleNamespace()
        tipo.value = 'admin'
        tipo.name = 'ADMIN'
        # Para compatibilidade com enum
        from models import TipoUsuario
        return TipoUsuario.ADMIN
    
    def get_id(self):
        return str(self.id)

# Substituir current_user globalmente para desenvolvimento
if BYPASS_ATIVO:
    flask_login.current_user = MockCurrentUser()
    
    # Sobrescrever decorador login_required
    def bypass_login_required(f):
        """Decorador que bypassa o login em desenvolvimento"""
        return f
    
    # Substituir login_required globalmente
    flask_login.login_required = bypass_login_required
    
    # Criar before_request handler para manter sessão
    def criar_before_request(app):
        @app.before_request  
        def bypass_login():
            session['bypass_active'] = True
    
    # Registrar com app quando disponível
    try:
        from app import app
        criar_before_request(app)
    except:
        pass