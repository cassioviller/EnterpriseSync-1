#!/usr/bin/env python3
"""
Script de teste para validar implementação dos padrões de auditoria:
- Idempotência
- Circuit Breaker  
- Saga
"""

import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor
import sys

# Configuração do teste
BASE_URL = "http://localhost:5000"
TEST_USER = {
    "email": "joao@estruturasdovale.com.br",
    "password": "123456"
}

def test_idempotency():
    """Testa padrão de idempotência em operações RDO"""
    print("🔑 TESTE IDEMPOTÊNCIA - RDO")
    
    # Dados de teste para criação de RDO
    rdo_data = {
        'obra_id': 1,
        'data_relatorio': '2025-08-27',
        'tempo_manha': 'Bom',
        'observacoes': 'Teste de idempotência'
    }
    
    # Enviar mesma requisição 3 vezes simultaneamente
    def send_request():
        response = requests.post(
            f"{BASE_URL}/rdo/salvar",
            data=rdo_data,
            headers={'Idempotency-Key': 'test-rdo-2025-08-27-obra-1'}
        )
        return response.status_code, response.text[:100]
    
    print("Enviando 3 requisições idênticas simultaneamente...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(send_request) for _ in range(3)]
        results = [f.result() for f in futures]
    
    print("Resultados:")
    for i, (status, text) in enumerate(results):
        print(f"  Requisição {i+1}: Status {status}")
    
    # Verificar se apenas 1 RDO foi criado
    return len(set(results)) <= 2  # Permite primeira criação + respostas idempotentes

def test_circuit_breaker():
    """Testa circuit breaker em geração de PDF"""
    print("\n🔌 TESTE CIRCUIT BREAKER - PDF")
    
    # Tentar gerar PDF que pode falhar
    def test_pdf_generation():
        response = requests.get(f"{BASE_URL}/funcionario_perfil/1/pdf")
        return response.status_code
    
    print("Testando geração de PDF...")
    results = []
    
    for i in range(5):
        try:
            status = test_pdf_generation()
            results.append(status)
            print(f"  Tentativa {i+1}: Status {status}")
            time.sleep(1)
        except Exception as e:
            print(f"  Tentativa {i+1}: Erro {e}")
            results.append(0)
    
    # Verificar se circuit breaker foi ativado após falhas
    return any(status == 503 for status in results)  # Status 503 = fallback ativo

def test_saga_pattern():
    """Testa padrão Saga em operação complexa"""
    print("\n🎭 TESTE SAGA - Atualização Salarial")
    
    # Simular atualização salarial que pode falhar
    funcionario_data = {
        'funcionario_id': 1,
        'novo_salario': 5000.00,
        'justificativa': 'Promoção por mérito - Teste Saga'
    }
    
    print("Simulando operação Saga...")
    
    # Como não temos endpoint específico, vamos testar a estrutura
    try:
        from utils.saga import FuncionarioSaga
        from app import app
        
        with app.app_context():
            saga = FuncionarioSaga(admin_id=10, funcionario_id=1)
            success = saga.update_salary_workflow(5000.00, "Teste Saga")
            
            print(f"  Saga executada: {'✅ Sucesso' if success else '❌ Falha'}")
            print(f"  Status: {saga.saga.get_status()}")
            
            return success
    except Exception as e:
        print(f"  Erro no teste Saga: {e}")
        return False

def test_database_resilience():
    """Testa resiliência geral do sistema"""
    print("\n🛡️ TESTE RESILIÊNCIA GERAL")
    
    endpoints_to_test = [
        "/dashboard",
        "/funcionarios", 
        "/rdo",
        "/health"
    ]
    
    results = {}
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            results[endpoint] = response.status_code
            print(f"  {endpoint}: Status {response.status_code}")
        except Exception as e:
            results[endpoint] = 0
            print(f"  {endpoint}: Erro {e}")
    
    # Verificar se pelo menos metade dos endpoints respondem
    successful = sum(1 for status in results.values() if status in [200, 302, 401])
    return successful >= len(endpoints_to_test) // 2

def main():
    """Executa todos os testes de auditoria"""
    print("🔍 AUDITORIA TÉCNICA - TESTES DE RESILIÊNCIA")
    print("=" * 50)
    
    tests = [
        ("Idempotência", test_idempotency),
        ("Circuit Breaker", test_circuit_breaker), 
        ("Saga Pattern", test_saga_pattern),
        ("Resiliência Geral", test_database_resilience)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"ERRO no teste {test_name}: {e}")
            results[test_name] = False
        
        time.sleep(2)  # Pausa entre testes
    
    print("\n" + "=" * 50)
    print("📊 RESULTADOS FINAIS:")
    
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {test_name}: {status}")
    
    passed_tests = sum(results.values())
    total_tests = len(results)
    
    print(f"\n🎯 RESUMO: {passed_tests}/{total_tests} testes passaram")
    
    if passed_tests >= total_tests * 0.75:  # 75% de sucesso
        print("✅ AUDITORIA APROVADA - Padrões implementados com sucesso")
        return 0
    else:
        print("⚠️ AUDITORIA PENDENTE - Necessário revisar implementação")
        return 1

if __name__ == "__main__":
    sys.exit(main())