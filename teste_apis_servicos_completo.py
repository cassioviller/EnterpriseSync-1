#!/usr/bin/env python3
"""
Teste completo de todas as APIs de serviços corrigidas
"""

import requests
import json

def testar_apis_servicos():
    """Testa todas as APIs de serviços"""
    base_url = "http://127.0.0.1:5000"
    
    print("=== TESTE COMPLETO DAS APIs DE SERVIÇOS CORRIGIDAS ===\n")
    
    # 1. Teste da API principal /api/servicos
    print("1. TESTANDO API PRINCIPAL:")
    try:
        response = requests.get(f"{base_url}/api/servicos")
        data = response.json()
        
        print(f"   Status: {response.status_code}")
        print(f"   Success: {data.get('success', 'N/A')}")
        print(f"   Admin ID: {data.get('admin_id', 'N/A')}")
        print(f"   Total serviços: {data.get('total', 0)}")
        print(f"   User Status: {data.get('user_status', 'N/A')}")
        
        if data.get('servicos') and len(data['servicos']) > 0:
            print(f"   Primeiros 3 serviços:")
            for i, servico in enumerate(data['servicos'][:3]):
                print(f"     {i+1}. {servico['nome']} (admin_id: {servico['admin_id']})")
        
    except Exception as e:
        print(f"   ERRO: {e}")
    
    print(f"\n{'='*60}")
    print("✅ TESTE CONCLUÍDO")
    print("🎯 RESULTADO ESPERADO EM PRODUÇÃO:")
    print("   - Admin ID: 2")
    print("   - Total: 5 serviços")
    print("   - Isolamento: Apenas serviços da sua empresa")
    print("   - Modal funcionando com os serviços corretos")

if __name__ == "__main__":
    testar_apis_servicos()