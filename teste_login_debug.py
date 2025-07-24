#!/usr/bin/env python3
"""
Debug do sistema de login
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

import requests
import sys

def test_login_redirect():
    """Testa o login e redirecionamento do super admin"""
    
    session = requests.Session()
    
    print("1. Acessando página de login...")
    login_page = session.get('http://localhost:5000/login')
    print(f"   Status: {login_page.status_code}")
    
    print("2. Fazendo login como axiom...")
    login_data = {
        'username': 'axiom',
        'password': 'cassio123'
    }
    
    login_response = session.post('http://localhost:5000/login', data=login_data, allow_redirects=False)
    print(f"   Status: {login_response.status_code}")
    print(f"   Headers: {dict(login_response.headers)}")
    
    if 'Location' in login_response.headers:
        redirect_url = login_response.headers['Location']
        print(f"   Redirecionando para: {redirect_url}")
        
        # Seguir redirecionamento
        print("3. Seguindo redirecionamento...")
        final_page = session.get(f'http://localhost:5000{redirect_url}')
        print(f"   Status final: {final_page.status_code}")
        print(f"   URL final: {final_page.url}")
        
        # Verificar conteúdo
        if 'Gerenciar Administradores' in final_page.text:
            print("✅ Login funcionando! Super Admin Dashboard carregado.")
        elif 'login' in final_page.text.lower():
            print("❌ Ainda na página de login - senha incorreta?")
        else:
            print("❓ Redirecionado para página desconhecida")
            print(f"   Conteúdo (primeiros 200 chars): {final_page.text[:200]}")
    else:
        print("❌ Sem redirecionamento - login falhou")
        print(f"   Conteúdo: {login_response.text[:200]}")

if __name__ == "__main__":
    test_login_redirect()