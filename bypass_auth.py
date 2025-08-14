"""
Sistema de bypass de autenticação para desenvolvimento
"""

from app import app
from flask import session, request, redirect, url_for
from types import SimpleNamespace

def criar_usuario_mock():
    """Criar usuário mock para desenvolvimento - usando admin real"""
    mock_user = SimpleNamespace()
    mock_user.id = 4  # admin@estruturasdovale.com.br
    mock_user.email = "admin@estruturasdovale.com.br"
    mock_user.nome = "Admin Estruturas do Vale"
    mock_user.is_authenticated = True
    mock_user.is_active = True
    mock_user.is_anonymous = False
    
    # Criar tipo_usuario mock
    from models import TipoUsuario
    mock_user.tipo_usuario = TipoUsuario.ADMIN
    
    mock_user.get_id = lambda: str(4)
    
    return mock_user

@app.before_request
def bypass_auth():
    """Bypass de autenticação para desenvolvimento"""
    
    # Se tentando acessar login estando "logado", redirecionar
    if request.endpoint == 'main.login' and session.get('user_logged_in'):
        return redirect(url_for('main.dashboard'))
    
    # Não aplicar bypass na página de login
    if request.endpoint == 'main.login':
        return None
    
    # Sempre configurar sessão para usuário admin
    session['user_logged_in'] = True
    session['user_id'] = 4
    session['user_email'] = 'admin@estruturasdovale.com.br'
    session['user_nome'] = 'Admin Estruturas do Vale'
    session['user_tipo'] = 'ADMIN'
    
    # Definir current_user global
    from flask import g
    g.current_user = criar_usuario_mock()

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
        return session.get('user_id', 4)
    
    @property
    def email(self):
        return session.get('user_email', 'admin@estruturasdovale.com.br')
    
    @property
    def nome(self):
        return session.get('user_nome', 'Admin Estruturas do Vale')
    
    @property
    def tipo_usuario(self):
        # Retornar enum correto baseado na string da sessão
        from models import TipoUsuario
        tipo_str = session.get('user_tipo', 'ADMIN')
        if tipo_str == 'SUPER_ADMIN':
            return TipoUsuario.SUPER_ADMIN
        elif tipo_str == 'ADMIN':
            return TipoUsuario.ADMIN
        else:
            return TipoUsuario.FUNCIONARIO
    
    def get_id(self):
        return str(self.id)

# Substituir current_user
flask_login.current_user = MockCurrentUser()

print("🔓 Sistema de bypass de autenticação ativado")
print("👤 Usuário mock: admin@estruturasdovale.com.br (ADMIN)")

if __name__ == '__main__':
    print("✅ Bypass configurado com sucesso!")