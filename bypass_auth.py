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
print("👤 Usuário mock: username=funcionario (FUNCIONÁRIO)")
print("💡 Para produção: Login = joao / Senha = 123456")

# Forçar reload do current_user para usar email correto
import flask_login
flask_login._get_user = lambda: MockCurrentUser()

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
        return 43  # ID do usuário funcionário real
    
    @property
    def admin_id(self):
        return 10  # Admin ID=10 (Vale Verde Estruturas Metálicas)
    
    @property
    def email(self):
        return 'funcionario@sistema.local'
    
    @property
    def username(self):
        return 'funcionario'
    
    @property
    def nome(self):
        return 'João Silva Santos'
    
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

def obter_admin_id():
    """Função utilitária para obter admin_id no contexto atual"""
    try:
        # Importar módulos necessários
        from flask_login import current_user
        from flask import session
        
        # Verificar usuário autenticado
        if current_user and current_user.is_authenticated:
            # Para usuários ADMIN, usar o próprio ID como admin_id
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario.value == 'admin':
                admin_id = current_user.id
                print(f"✅ BYPASS RDO: Usuário ADMIN detectado (ID={current_user.id}) - USANDO admin_id={admin_id}")
                return admin_id
            # Para funcionários, usar o admin_id associado
            elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                admin_id = current_user.admin_id
                print(f"✅ BYPASS RDO: Funcionário detectado - USANDO admin_id={admin_id}")
                return admin_id
        
        # Verificar sessão para qualquer usuário
        if session and '_user_id' in session:
            user_id = int(session['_user_id'])
            # Buscar no banco para determinar admin_id correto
            try:
                from models import Usuario, TipoUsuario
                usuario = Usuario.query.get(user_id)
                if usuario:
                    if usuario.tipo_usuario == TipoUsuario.ADMIN:
                        admin_id = usuario.id
                    else:
                        admin_id = usuario.admin_id or usuario.id
                    print(f"✅ BYPASS RDO: Usuário sessão ID={user_id} - USANDO admin_id={admin_id}")
                    return admin_id
            except Exception as e:
                print(f"⚠️ Erro ao buscar usuário no banco: {e}")
                # Fallback: usar o próprio user_id como admin_id
                print(f"✅ BYPASS RDO: Fallback - USANDO admin_id={user_id}")
                return user_id
        
        # Fallback padrão
        print(f"✅ BYPASS RDO: Usando admin_id padrão=10")
        return 10
        
    except Exception as e:
        print(f"❌ Erro no bypass RDO: {e}")
        return 10

def obter_usuario_atual():
    """Função utilitária para obter usuário atual - baseado apenas no acesso"""
    try:
        # Usar ID do usuário logado (não funcionário)
        user_id = 46  # ID do usuário cassio1 que tem acesso
        print(f"✅ BYPASS: Usando usuário logado: ID={user_id} (admin_id=10)")
        return user_id
                
    except Exception as e:
        print(f"❌ Erro ao obter usuário: {e}")
        return 46  # Fallback para usuário cassio1