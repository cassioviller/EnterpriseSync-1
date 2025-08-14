"""
Sistema de bypass de autenticação para desenvolvimento
"""

from app import app
from flask import session, request, redirect, url_for
from types import SimpleNamespace

def criar_usuario_mock():
    """Criar usuário mock para desenvolvimento"""
    mock_user = SimpleNamespace()
    mock_user.id = 1
    mock_user.email = "admin@sige.com"
    mock_user.nome = "Administrador SIGE"
    mock_user.is_authenticated = True
    mock_user.is_active = True
    mock_user.is_anonymous = False
    
    # Criar tipo_usuario mock
    mock_tipo = SimpleNamespace()
    mock_tipo.name = "SUPER_ADMIN"
    mock_user.tipo_usuario = mock_tipo
    
    mock_user.get_id = lambda: str(1)
    
    return mock_user

@app.before_request
def bypass_auth():
    """Bypass de autenticação para desenvolvimento"""
    
    # Não aplicar bypass na página de login
    if request.endpoint == 'main.login':
        return None
    
    # Se não estiver logado, simular login automático
    if 'user_logged_in' not in session:
        session['user_logged_in'] = True
        session['user_id'] = 1
        session['user_email'] = 'admin@sige.com'
        session['user_nome'] = 'Administrador SIGE'
        session['user_tipo'] = 'SUPER_ADMIN'
        
        # Definir current_user global
        from flask import g
        g.current_user = criar_usuario_mock()
    
    # Se tentando acessar login estando "logado", redirecionar
    if request.endpoint == 'main.login' and session.get('user_logged_in'):
        return redirect(url_for('main.dashboard'))

# Patch para flask-login
from flask_login import current_user

# Monkey patch para current_user funcionar
import flask_login
original_current_user = flask_login.current_user

class MockCurrentUser:
    @property
    def is_authenticated(self):
        return session.get('user_logged_in', False)
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return not self.is_authenticated
    
    @property
    def id(self):
        return session.get('user_id', 1)
    
    @property
    def email(self):
        return session.get('user_email', 'admin@sige.com')
    
    @property
    def nome(self):
        return session.get('user_nome', 'Administrador SIGE')
    
    @property
    def tipo_usuario(self):
        tipo = SimpleNamespace()
        tipo.name = session.get('user_tipo', 'SUPER_ADMIN')
        return tipo
    
    def get_id(self):
        return str(self.id)

# Substituir current_user
flask_login.current_user = MockCurrentUser()

print("🔓 Sistema de bypass de autenticação ativado")
print("👤 Usuário mock: admin@sige.com (SUPER_ADMIN)")

if __name__ == '__main__':
    print("✅ Bypass configurado com sucesso!")