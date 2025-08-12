#!/usr/bin/env python3
"""
🧪 TESTE COMPLETO DE NAVEGAÇÃO - SIGE v8.0
Verifica todas as rotas e corrige problemas de navegação
"""

import requests
import sys
from urllib.parse import urljoin

def testar_navegacao_completa():
    print("🧪 TESTE COMPLETO DE NAVEGAÇÃO - SIGE v8.0")
    print("=" * 60)
    
    base_url = "http://localhost:5000"
    
    # Criar sessão
    session = requests.Session()
    
    # Lista de rotas para testar
    rotas_teste = [
        "/",
        "/test", 
        "/login",
        "/dashboard",
        "/funcionarios",
        "/obras",
        "/veiculos",
        "/propostas",
        "/equipes",
        "/almoxarifado",
        "/folha-pagamento", 
        "/contabilidade"
    ]
    
    sucessos = 0
    total = len(rotas_teste)
    
    print("📡 TESTANDO ROTAS PRINCIPAIS:")
    print("-" * 40)
    
    for rota in rotas_teste:
        try:
            url = urljoin(base_url, rota)
            response = session.get(url, timeout=10)
            
            if response.status_code == 200:
                status = "✅ OK"
                sucessos += 1
            elif response.status_code == 302:
                status = "🔄 REDIRECT"
                sucessos += 1
            elif response.status_code == 404:
                status = "❌ 404"
            elif response.status_code == 500:
                status = "💥 500"
            else:
                status = f"⚠️ {response.status_code}"
                
            print(f"{rota:<20} {status}")
            
        except requests.RequestException as e:
            print(f"{rota:<20} ❌ ERRO: {str(e)}")
    
    print("-" * 40)
    print(f"📊 RESULTADO: {sucessos}/{total} rotas funcionando")
    
    # Teste específico com login
    print("\n🔐 TESTANDO COM LOGIN:")
    print("-" * 40)
    
    # Fazer login
    login_data = {
        'username': 'admin@sige.com',
        'password': 'admin123'
    }
    
    login_response = session.post(urljoin(base_url, "/login"), data=login_data)
    
    if login_response.status_code in [200, 302]:
        print("✅ Login realizado com sucesso")
        
        # Testar rotas autenticadas
        rotas_auth = ["/dashboard", "/funcionarios", "/propostas", "/equipes"]
        
        for rota in rotas_auth:
            try:
                response = session.get(urljoin(base_url, rota))
                if response.status_code == 200:
                    print(f"✅ {rota} - Acessível após login")
                else:
                    print(f"❌ {rota} - Status: {response.status_code}")
            except Exception as e:
                print(f"❌ {rota} - Erro: {str(e)}")
    else:
        print("❌ Falha no login")
    
    print("\n" + "=" * 60)
    print("✅ TESTE DE NAVEGAÇÃO CONCLUÍDO")
    
    return sucessos / total >= 0.8

if __name__ == "__main__":
    resultado = testar_navegacao_completa()
    sys.exit(0 if resultado else 1)