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
print("👤 Usuário mock: admin@sige.com (SUPER_ADMIN)")

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
        return 1
    
    @property
    def email(self):
        return 'admin@sige.com'
    
    @property
    def nome(self):
        return 'Super Admin SIGE'
    
    @property
    def tipo_usuario(self):
        # Simular TipoUsuario.SUPER_ADMIN
        tipo = SimpleNamespace()
        tipo.value = 'super_admin'
        tipo.name = 'SUPER_ADMIN'
        # Para compatibilidade com enum
        from models import TipoUsuario
        return TipoUsuario.SUPER_ADMIN
    
    def get_id(self):
        return str(self.id)

# Substituir current_user globalmente para desenvolvimento
if BYPASS_ATIVO:
    flask_login.current_user = MockCurrentUser()
    
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