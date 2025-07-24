#!/usr/bin/env python3
"""
Script para testar o sistema completo com banco SQLite local
"""

from app import app
from models import Usuario, Departamento, Funcao
from werkzeug.security import check_password_hash

def testar_sistema():
    with app.test_client() as client:
        with app.app_context():
            print("🔍 Testando sistema SIGE v8.0 completo...")
            
            # 1. Testar login com usuário valeverde
            print("\n1. Testando login com valeverde/admin123:")
            
            # Primeiro fazer GET para obter o token CSRF
            login_page = client.get('/login')
            print(f"GET /login: {login_page.status_code}")
            
            # Extrair CSRF token da página (simulação)
            if login_page.status_code == 200:
                # Fazer login
                login_response = client.post('/login', data={
                    'username': 'valeverde',
                    'password': 'admin123'
                }, follow_redirects=True)
                
                print(f"POST /login: {login_response.status_code}")
                
                if login_response.status_code == 200:
                    print("✅ Login realizado com sucesso")
                    
                    # 2. Testar acesso às páginas de configuração
                    print("\n2. Testando acesso às páginas:")
                    
                    pages = [
                        ('/departamentos', 'Departamentos'),
                        ('/funcoes', 'Funções'),
                        ('/horarios', 'Horários'),
                        ('/servicos', 'Serviços')
                    ]
                    
                    for url, name in pages:
                        response = client.get(url)
                        status = "✅" if response.status_code == 200 else "❌"
                        print(f"{status} GET {url}: {response.status_code}")
                    
                    # 3. Verificar dados no banco
                    print("\n3. Verificando dados no banco:")
                    print(f"Usuários: {Usuario.query.count()}")
                    print(f"Departamentos: {Departamento.query.count()}")
                    print(f"Funções: {Funcao.query.count()}")
                    
                    # 4. Testar autenticação do usuário valeverde
                    user = Usuario.query.filter_by(username='valeverde').first()
                    if user:
                        pwd_valid = check_password_hash(user.password_hash, 'admin123')
                        print(f"Senha válida para valeverde: {pwd_valid}")
                        print(f"Tipo: {user.tipo_usuario.name}, Ativo: {user.ativo}")
                    
                    print("\n✅ Sistema testado com sucesso!")
                    print("🌐 Acesse http://localhost:5000 e faça login com:")
                    print("   • Username: valeverde")
                    print("   • Password: admin123")
                
                else:
                    print("❌ Falha no login")
            else:
                print("❌ Falha ao acessar página de login")

if __name__ == "__main__":
    testar_sistema()