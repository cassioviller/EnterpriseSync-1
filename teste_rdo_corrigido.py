#!/usr/bin/env python3
"""
Teste das correções implementadas no sistema RDO
"""

import requests
import json
from datetime import datetime

def testar_nova_interface_rdo():
    """Testar se nova interface RDO está funcionando"""
    
    print("🧪 TESTE RDO CORRIGIDO")
    print("=" * 40)
    
    base_url = "http://localhost:5000"
    
    # 1. Testar se página RDO carrega
    print("1. Testando carregamento da página RDO...")
    try:
        response = requests.get(f"{base_url}/funcionario/rdo/novo", timeout=10)
        if response.status_code == 200:
            print("✅ Página RDO carregada com sucesso")
            
            # Verificar se tem campos com name attributes
            content = response.text
            if 'nome_subatividade_1_percentual' in content:
                print("✅ Campos de captura de dados encontrados")
            else:
                print("❌ Campos de captura não encontrados")
                
        else:
            print(f"❌ Erro ao carregar página: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro de conexão: {str(e)}")
    
    # 2. Testar salvamento de RDO
    print("\n2. Testando salvamento de RDO com dados manuais...")
    try:
        # Simular dados do formulário
        form_data = {
            'obra_id': 40,  # Galpão Industrial Premium
            'data_relatorio': datetime.now().strftime('%Y-%m-%d'),
            'condicoes_climaticas': 'Ensolarado',
            'temperatura': '25°C',
            
            # Dados manuais das subatividades
            'nome_subatividade_1': 'Montagem de Pilares',
            'nome_subatividade_1_percentual': 100.0,
            'nome_subatividade_2': 'Instalação de Vigas',
            'nome_subatividade_2_percentual': 100.0,
            'nome_subatividade_3': 'Soldagem de Bases',
            'nome_subatividade_3_percentual': 85.0,
            
            'observacoes_tecnicas': 'Teste automatizado - RDO com subatividades manuais'
        }
        
        response = requests.post(f"{base_url}/salvar-rdo-flexivel", data=form_data, timeout=15)
        
        if response.status_code == 302:  # Redirect após sucesso
            print("✅ RDO salvo com redirecionamento")
        elif response.status_code == 200:
            print("✅ RDO processado com sucesso")
        else:
            print(f"❌ Erro ao salvar RDO: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Erro ao testar salvamento: {str(e)}")
    
    # 3. Testar listagem de RDOs
    print("\n3. Testando listagem de RDOs...")
    try:
        response = requests.get(f"{base_url}/funcionario/rdo/consolidado", timeout=10)
        if response.status_code == 200:
            print("✅ Lista de RDOs carregada")
            
            # Verificar se tem progresso da obra
            content = response.text
            if 'PROGRESSO' in content and '%' in content:
                print("✅ Progresso da obra sendo exibido")
            else:
                print("⚠️ Progresso da obra pode não estar sendo exibido")
                
        else:
            print(f"❌ Erro ao listar RDOs: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro ao testar listagem: {str(e)}")
    
    print("\n📋 TESTE CONCLUÍDO")
    print("=" * 40)

def testar_api_servicos():
    """Testar API de serviços para obra"""
    
    print("\n🔧 TESTE API SERVIÇOS")
    print("=" * 30)
    
    base_url = "http://localhost:5000"
    obra_id = 40  # Galpão Industrial Premium
    
    try:
        response = requests.get(f"{base_url}/api/test/rdo/servicos-obra/{obra_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API funcionando - {data.get('total', 0)} serviços encontrados")
            print(f"   Total subatividades: {data.get('total_subatividades', 0)}")
        else:
            print(f"❌ Erro na API: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro ao testar API: {str(e)}")

if __name__ == "__main__":
    testar_nova_interface_rdo()
    testar_api_servicos()