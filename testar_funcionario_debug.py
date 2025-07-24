#!/usr/bin/env python3
"""
Script para testar criação de funcionário via interface web simulada
"""

from app import app, csrf
from models import Usuario, Funcionario
from werkzeug.security import check_password_hash
from flask import url_for

def testar_funcionario():
    with app.test_client() as client:
        with app.app_context():
            print("🔍 Testando criação de funcionário...")
            
            # 1. Fazer login primeiro
            print("\n1. Fazendo login...")
            
            # Simular request context para gerar token CSRF válido
            with client.session_transaction() as sess:
                # Gerar token CSRF
                csrf_token = csrf.generate_csrf()
                print(f"CSRF Token gerado: {csrf_token[:20]}...")
            
            # Fazer login com token CSRF
            login_response = client.post('/login', data={
                'username': 'valeverde',
                'password': 'admin123',
                'csrf_token': csrf_token
            })
            
            print(f"Login status: {login_response.status_code}")
            
            # 2. Testar acesso ao departamentos após login
            if login_response.status_code in [200, 302]:
                print("\n2. Testando acesso às páginas após login:")
                
                response = client.get('/departamentos')
                print(f"GET /departamentos: {response.status_code}")
                
                response = client.get('/funcoes')
                print(f"GET /funcoes: {response.status_code}")
                
                # 3. Testar POST para criar departamento
                print("\n3. Testando criação de departamento:")
                
                with client.session_transaction() as sess:
                    csrf_token_new = csrf.generate_csrf()
                
                dept_response = client.post('/departamentos/novo', data={
                    'nome': f'Departamento Web {csrf_token_new[-4:]}',
                    'descricao': 'Teste via web',
                    'csrf_token': csrf_token_new
                })
                
                print(f"POST departamento: {dept_response.status_code}")
                if dept_response.status_code == 302:
                    print("✅ Departamento criado com sucesso (redirecionamento)")
                elif dept_response.status_code == 200:
                    print("⚠️  Departamento - resposta 200 (possível erro)")
                
                # 4. Testar POST para criar função
                print("\n4. Testando criação de função:")
                
                with client.session_transaction() as sess:
                    csrf_token_func = csrf.generate_csrf()
                
                func_response = client.post('/funcoes/novo', data={
                    'nome': f'Função Web {csrf_token_func[-4:]}',
                    'descricao': 'Teste via web',
                    'salario_base': '3500.00',
                    'csrf_token': csrf_token_func
                })
                
                print(f"POST função: {func_response.status_code}")
                if func_response.status_code == 302:
                    print("✅ Função criada com sucesso (redirecionamento)")
                elif func_response.status_code == 200:
                    print("⚠️  Função - resposta 200 (possível erro)")

if __name__ == "__main__":
    testar_funcionario()