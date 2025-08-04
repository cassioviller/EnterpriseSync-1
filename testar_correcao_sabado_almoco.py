#!/usr/bin/env python3
"""
Script para testar e corrigir o problema do horário de almoço do sábado não sendo salvo
"""

import requests
from requests.sessions import Session
import json

def testar_edicao_ponto():
    """Testar edição de registro de ponto com horário de almoço no sábado"""
    
    # Configurar sessão
    s = Session()
    
    # 1. Fazer login
    print("🔐 Fazendo login...")
    login_data = {
        'username': 'admin@test.com',
        'password': '123456'
    }
    
    login_response = s.post('http://0.0.0.0:5000/login', data=login_data)
    
    if login_response.status_code not in [200, 302]:
        print(f"❌ Erro no login: {login_response.status_code}")
        return
    
    print("✅ Login realizado com sucesso!")
    
    # 2. Acessar o perfil do funcionário para ver registros
    print("📊 Acessando perfil do funcionário...")
    funcionario_response = s.get('http://0.0.0.0:5000/funcionarios/2/perfil')
    
    if funcionario_response.status_code != 200:
        print(f"❌ Erro ao acessar perfil: {funcionario_response.status_code}")
        return
    
    print("✅ Perfil acessado com sucesso!")
    
    # 3. Testar busca de registro específico (sabado com ID que pode existir)
    print("🔍 Testando busca de registro...")
    test_id = 50  # Usar um ID que provavelmente existe
    
    registro_response = s.get(f'http://0.0.0.0:5000/ponto/registro/{test_id}')
    
    if registro_response.status_code == 200:
        print(f"✅ Registro {test_id} encontrado!")
        data = registro_response.json()
        print(f"   📅 Data: {data.get('data')}")
        print(f"   🏗️ Tipo: {data.get('tipo_registro')}")
        print(f"   🕐 Entrada: {data.get('entrada')}")
        print(f"   🍽️ Saída Almoço: {data.get('saida_almoco')}")
        print(f"   🍽️ Retorno Almoço: {data.get('retorno_almoco')}")
        print(f"   🕕 Saída: {data.get('saida')}")
        
        # 4. Testar edição do registro (adicionar horários de almoço)
        print(f"\n✏️ Testando edição do registro {test_id}...")
        
        dados_edicao = {
            'data': data.get('data'),
            'tipo_lancamento': data.get('tipo_registro'),
            'obra_id': data.get('obra_id', ''),
            'hora_entrada': data.get('entrada') or '07:32',
            'hora_almoco_saida': '12:00',  # Adicionar horário de almoço
            'hora_almoco_retorno': '13:00',  # Adicionar retorno do almoço
            'hora_saida': data.get('saida') or '17:00',
            'percentual_extras': data.get('percentual_extras', 0),
            'observacoes': 'Teste de edição - horário de almoço no sábado'
        }
        
        edicao_response = s.post(f'http://0.0.0.0:5000/ponto/registro/{test_id}', 
                                data=dados_edicao)
        
        if edicao_response.status_code == 200:
            result = edicao_response.json()
            if result.get('success'):
                print("✅ Edição realizada com sucesso!")
                
                # Verificar se os dados foram salvos
                verificacao_response = s.get(f'http://0.0.0.0:5000/ponto/registro/{test_id}')
                if verificacao_response.status_code == 200:
                    new_data = verificacao_response.json()
                    print(f"   🍽️ Novo Saída Almoço: {new_data.get('saida_almoco')}")
                    print(f"   🍽️ Novo Retorno Almoço: {new_data.get('retorno_almoco')}")
                    
                    if new_data.get('saida_almoco') and new_data.get('retorno_almoco'):
                        print("✅ SUCESSO: Horários de almoço foram salvos corretamente!")
                    else:
                        print("❌ PROBLEMA: Horários de almoço não foram salvos!")
                
            else:
                print(f"❌ Erro na edição: {result.get('error', 'Erro desconhecido')}")
        else:
            print(f"❌ Erro HTTP na edição: {edicao_response.status_code}")
            try:
                error_data = edicao_response.json()
                print(f"   Erro: {error_data}")
            except:
                print(f"   Resposta: {edicao_response.text[:200]}")
                
    else:
        print(f"❌ Registro {test_id} não encontrado: {registro_response.status_code}")
        
        # Se não encontrou, tentar com outros IDs
        for test_id in [45, 55, 60, 65]:
            print(f"🔍 Tentando registro {test_id}...")
            registro_response = s.get(f'http://0.0.0.0:5000/ponto/registro/{test_id}')
            if registro_response.status_code == 200:
                print(f"✅ Encontrado registro {test_id}!")
                break
        else:
            print("❌ Nenhum registro encontrado para teste")

if __name__ == "__main__":
    print("🧪 TESTE: Correção do horário de almoço do sábado")
    print("=" * 50)
    testar_edicao_ponto()