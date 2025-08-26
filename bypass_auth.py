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
print("👤 Usuário mock: funcionario@valeverde.com (FUNCIONÁRIO)")

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
        return 15  # ID do funcionário teste
    
    @property
    def admin_id(self):
        return 10  # Admin ID=10 (Vale Verde Estruturas Metálicas)
    
    @property
    def email(self):
        return 'funcionario@valeverde.com'
    
    @property
    def nome(self):
        return 'Funcionário Teste Vale Verde'
    
    @property
    def tipo_usuario(self):
        # Simular TipoUsuario.FUNCIONARIO para testar
        tipo = SimpleNamespace()
        tipo.value = 'funcionario'
        tipo.name = 'FUNCIONARIO'
        # Para compatibilidade com enum
        from models import TipoUsuario
        return TipoUsuario.FUNCIONARIO
    
    def get_id(self):
        return str(self.id)

# Substituir current_user globalmente para desenvolvimento
if BYPASS_ATIVO:
    flask_login.current_user = MockCurrentUser()
    
    # Sobrescrever decorador login_required
    def bypass_login_required(f):
        """Decorador que bypassa o login em desenvolvimento"""
        return f
    
    # Sobrescrever decorador funcionario_required também
    def bypass_funcionario_required(f):
        """Decorador que bypassa o funcionario_required em desenvolvimento"""
        return f
    
    # Substituir login_required globalmente
    flask_login.login_required = bypass_login_required
    
    # Registrar bypass para funcionario_required quando auth.py for importado
    try:
        import auth
        auth.funcionario_required = bypass_funcionario_required
    except ImportError:
        pass
    
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