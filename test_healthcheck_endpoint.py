#!/usr/bin/env python3
"""
Teste do endpoint de health check para validar deploy
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

import requests
import json
from datetime import datetime

def test_healthcheck():
    """Testa endpoint de health check"""
    try:
        print("🔍 Testando endpoint de health check...")
        
        # URL do endpoint local
        url = "http://localhost:5000/api/monitoring/health"
        
        # Fazer requisição GET
        response = requests.get(url, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ Health check funcionando!")
                print(f"   Status: {data.get('status')}")
                print(f"   Version: {data.get('version')}")
                print(f"   Database: {data.get('database')}")
                print(f"   Timestamp: {data.get('timestamp')}")
                return True
            except json.JSONDecodeError:
                print("⚠️ Resposta não é JSON válido")
                print(f"   Conteúdo: {response.text[:200]}")
                return False
        else:
            print(f"❌ Erro no health check: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Erro de conexão - aplicação pode não estar rodando")
        return False
    except requests.exceptions.Timeout:
        print("❌ Timeout na requisição")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def test_app_running():
    """Testa se a aplicação está respondendo"""
    try:
        print("🌐 Testando se aplicação está rodando...")
        
        # URL raiz da aplicação
        url = "http://localhost:5000/"
        
        # Fazer requisição GET
        response = requests.get(url, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code in [200, 302, 401]:  # 200=OK, 302=Redirect, 401=Auth needed
            print("✅ Aplicação está respondendo!")
            return True
        else:
            print(f"⚠️ Status inesperado: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar aplicação: {e}")
        return False

if __name__ == "__main__":
    print("🧪 TESTE DE SAÚDE DA APLICAÇÃO - SIGE v8.0")
    print("=" * 50)
    
    app_ok = test_app_running()
    health_ok = test_healthcheck()
    
    print("\n📊 RESULTADOS:")
    print(f"   Aplicação rodando: {'✅' if app_ok else '❌'}")
    print(f"   Health check: {'✅' if health_ok else '❌'}")
    
    if app_ok and health_ok:
        print("\n🎯 Sistema pronto para deploy!")
    else:
        print("\n⚠️ Sistema precisa de ajustes antes do deploy")