#!/usr/bin/env python3
"""
Script de teste para verificar saúde do container Docker
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

import requests
import sys
import time
from datetime import datetime

def test_health_endpoint():
    """Testa o endpoint de saúde da aplicação"""
    try:
        print("🔍 Testando endpoint de saúde...")
        response = requests.get("http://localhost:5000/api/monitoring/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check OK: {data}")
            return True
        else:
            print(f"❌ Health check falhou: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
        return False

def test_login_page():
    """Testa se a página de login está acessível"""
    try:
        print("🔍 Testando página de login...")
        response = requests.get("http://localhost:5000/login", timeout=10)
        
        if response.status_code == 200:
            print("✅ Página de login acessível")
            return True
        else:
            print(f"❌ Página de login inacessível: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar login: {e}")
        return False

def test_database_connection():
    """Testa se o banco de dados está conectado através do endpoint de métricas"""
    try:
        print("🔍 Testando conexão com banco de dados...")
        response = requests.get("http://localhost:5000/api/monitoring/metrics", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('database_status') == 'connected':
                print("✅ Banco de dados conectado")
                return True
            else:
                print(f"❌ Banco desconectado: {data.get('database_status')}")
                return False
        else:
            print(f"❌ Não foi possível verificar banco: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao verificar banco: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("🚀 Iniciando testes de saúde do SIGE v8.0")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print("-" * 50)
    
    # Aguardar aplicação inicializar
    print("⏳ Aguardando aplicação inicializar (30s)...")
    time.sleep(30)
    
    tests = [
        ("Health Endpoint", test_health_endpoint),
        ("Página de Login", test_login_page),
        ("Conexão BD", test_database_connection)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Executando: {test_name}")
        result = test_func()
        results.append((test_name, result))
        time.sleep(2)  # Pausa entre testes
    
    # Resumo dos resultados
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nResultado: {passed}/{len(tests)} testes passaram")
    
    if passed == len(tests):
        print("🎉 Todos os testes passaram! Container está saudável.")
        sys.exit(0)
    else:
        print("⚠️ Alguns testes falharam. Verifique logs do container.")
        sys.exit(1)

if __name__ == "__main__":
    main()