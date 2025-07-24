#!/usr/bin/env python3
"""
Script para testar login e acesso às rotas de configuração
"""

from app import app
from models import Usuario
from werkzeug.security import check_password_hash

def testar_login():
    with app.test_client() as client:
        print("🔍 Testando login e acesso às rotas...")
        
        # 1. Testar login com usuário admin
        print("\n1. Tentando login com valeverde/admin123:")
        response = client.post('/login', data={
            'username': 'valeverde',
            'password': 'admin123'
        }, follow_redirects=False)
        
        print(f"Status do login: {response.status_code}")
        print(f"Location header: {response.headers.get('Location', 'N/A')}")
        
        # 2. Testar acesso às páginas depois do login
        if response.status_code == 302:
            print("\n2. Fazendo login e testando acessos:")
            
            # Login com follow_redirects=True
            login_response = client.post('/login', data={
                'username': 'valeverde',
                'password': 'admin123'
            }, follow_redirects=True)
            
            print(f"Login response status: {login_response.status_code}")
            
            # Testar acesso às páginas
            pages = ['/departamentos', '/funcoes', '/horarios', '/servicos']
            for page in pages:
                response = client.get(page)
                print(f"GET {page}: {response.status_code}")
        
        # 3. Verificar usuários no banco
        print("\n3. Verificando usuários no banco:")
        with app.app_context():
            users = Usuario.query.filter_by(ativo=True).all()
            for user in users[:5]:
                print(f"- {user.username}: tipo={user.tipo_usuario.name}, ativo={user.ativo}")
                # Testar senha
                if user.username == 'valeverde':
                    is_valid = check_password_hash(user.password_hash, 'admin123')
                    print(f"  Senha válida: {is_valid}")

if __name__ == "__main__":
    testar_login()