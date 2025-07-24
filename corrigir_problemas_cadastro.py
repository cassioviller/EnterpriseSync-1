#!/usr/bin/env python3
"""
Script para diagnosticar e corrigir problemas de cadastro no sistema
"""

from app import app, csrf
from models import Usuario, Departamento, Funcao, HorarioTrabalho, Servico
from werkzeug.security import check_password_hash
from flask import url_for

def testar_csrf_formularios():
    with app.test_client() as client:
        with app.app_context():
            print("🔍 Testando formulários com CSRF...")
            
            # 1. Login primeiro
            print("\n1. Fazendo login com valeverde...")
            
            # Obter página de login para conseguir o CSRF token
            login_page = client.get('/login')
            
            # Login sem CSRF (para testar se está funcionando)
            login_response = client.post('/login', data={
                'username': 'valeverde',
                'password': 'admin123'
            }, follow_redirects=False)
            
            print(f"Login response: {login_response.status_code}")
            
            if login_response.status_code == 302:  # Redirecionamento após login
                print("✅ Login bem-sucedido")
                
                # 2. Testar criação de departamento
                print("\n2. Testando criação de departamento...")
                
                dept_response = client.post('/departamentos/novo', data={
                    'nome': 'Departamento Teste CSRF',
                    'descricao': 'Teste criação via formulário'
                }, follow_redirects=True)
                
                print(f"Departamento POST: {dept_response.status_code}")
                
                if dept_response.status_code == 200:
                    print("✅ Departamento criado com sucesso")
                else:
                    print("❌ Falha na criação do departamento")
                
                # 3. Testar outras páginas
                print("\n3. Testando acesso às páginas:")
                
                test_pages = [
                    '/departamentos',
                    '/funcoes', 
                    '/horarios',
                    '/servicos'
                ]
                
                for page in test_pages:
                    response = client.get(page)
                    status = "✅" if response.status_code == 200 else "❌"
                    print(f"{status} {page}: {response.status_code}")
            
            else:
                print("❌ Falha no login")
                
                # Verificar dados do usuário
                user = Usuario.query.filter_by(username='valeverde').first()
                if user:
                    pwd_check = check_password_hash(user.password_hash, 'admin123')
                    print(f"Usuário encontrado: {user.email}, senha válida: {pwd_check}")
                    print(f"Tipo: {user.tipo_usuario.name}, Ativo: {user.ativo}")
                else:
                    print("❌ Usuário 'valeverde' não encontrado")

def configurar_csrf_sem_limite():
    """Configura CSRF sem limite de tempo"""
    with app.app_context():
        print("🔧 Configurando CSRF sem limite de tempo...")
        app.config['WTF_CSRF_TIME_LIMIT'] = None
        app.config['WTF_CSRF_SSL_STRICT'] = False  # Para desenvolvimento
        print("✅ CSRF configurado sem limite de tempo")

def listar_dados_sistema():
    """Lista dados existentes no sistema"""
    with app.app_context():
        print("\n📊 Dados existentes no sistema:")
        print(f"Usuários: {Usuario.query.count()}")
        print(f"Departamentos: {Departamento.query.count()}")
        print(f"Funções: {Funcao.query.count()}")
        print(f"Horários: {HorarioTrabalho.query.count()}")
        print(f"Serviços: {Servico.query.count()}")
        
        # Mostrar usuários ativos
        print("\nUsuários ativos:")
        for user in Usuario.query.filter_by(ativo=True).limit(5):
            print(f"  - {user.username} ({user.tipo_usuario.name}) - {user.email}")

if __name__ == "__main__":
    configurar_csrf_sem_limite()
    listar_dados_sistema()
    testar_csrf_formularios()