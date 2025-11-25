#!/usr/bin/env python3
"""
Verificação de Deploy SIGE v8.0
Testa se todas as funcionalidades críticas estão funcionando
"""

import requests
import sys
import time

def test_endpoint(url, expected_status=200):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == expected_status:
            print(f"✅ {url} - Status {response.status_code}")
            return True
        else:
            print(f"❌ {url} - Status {response.status_code} (esperado {expected_status})")
            return False
    except Exception as e:
        print(f"❌ {url} - Erro: {e}")
        return False

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    print(f"🔍 Testando deploy em: {base_url}")
    
    # Endpoints críticos para testar
    endpoints = [
        f"{base_url}/",
        f"{base_url}/login",
        f"{base_url}/dashboard", 
        f"{base_url}/funcionarios",
        f"{base_url}/rdos",
        f"{base_url}/propostas",
        f"{base_url}/health"
    ]
    
    success_count = 0
    for endpoint in endpoints:
        if test_endpoint(endpoint):
            success_count += 1
        time.sleep(1)
    
    print(f"\n📊 Resultado: {success_count}/{len(endpoints)} endpoints funcionando")
    
    if success_count == len(endpoints):
        print("🎉 Deploy verificado com sucesso!")
        sys.exit(0)
    else:
        print("❌ Deploy com problemas!")
        sys.exit(1)

if __name__ == "__main__":
    main()
