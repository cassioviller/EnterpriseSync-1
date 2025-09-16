#!/usr/bin/env python3
"""
TESTE DEBUG ESPECÍFICO - Investigar problemas encontrados nos testes principais
"""

import requests
import json
from bs4 import BeautifulSoup

def teste_manual_completo():
    """Teste manual para debugging específico"""
    
    session = requests.Session()
    base_url = 'http://0.0.0.0:5000'
    
    print("🔍 DEBUGANDO PROBLEMAS DOS TESTES")
    print("=" * 60)
    
    # 1. Testar login sem cookies primeiro
    print("\n1. TESTANDO LOGIN BÁSICO")
    login_response = session.get(f'{base_url}/login')
    print(f"   GET /login: {login_response.status_code}")
    
    # Fazer login
    login_data = {
        'email': 'admin@teste.com',
        'password': 'admin123'
    }
    
    login_post = session.post(f'{base_url}/login', data=login_data)
    print(f"   POST /login: {login_post.status_code}")
    print(f"   Cookies após login: {len(session.cookies)}")
    
    # 2. Testar acesso ao dashboard
    print("\n2. TESTANDO ACESSO AO DASHBOARD")
    dashboard_response = session.get(f'{base_url}/dashboard')
    print(f"   GET /dashboard: {dashboard_response.status_code}")
    
    if dashboard_response.status_code == 200:
        soup = BeautifulSoup(dashboard_response.text, 'html.parser')
        title = soup.find('title')
        print(f"   Título da página: {title.text if title else 'Não encontrado'}")
        
        # Procurar indicações de login bem-sucedido
        user_indicator = soup.find(string=lambda text: 'admin' in text.lower() if text else False)
        print(f"   Indicação de usuário logado: {'Sim' if user_indicator else 'Não'}")
    
    # 3. Testar acesso à lista de veículos
    print("\n3. TESTANDO ACESSO À LISTA DE VEÍCULOS")
    veiculos_response = session.get(f'{base_url}/veiculos')
    print(f"   GET /veiculos: {veiculos_response.status_code}")
    
    if veiculos_response.status_code == 200:
        # Analisar conteúdo da página de veículos
        soup = BeautifulSoup(veiculos_response.text, 'html.parser')
        title = soup.find('title')
        print(f"   Título: {title.text if title else 'Não encontrado'}")
        
        # Procurar palavras-chave relacionadas a veículos
        keywords = ['veículo', 'veiculo', 'frota', 'automóvel', 'placa', 'marca', 'modelo']
        found_keywords = []
        
        page_text = veiculos_response.text.lower()
        for keyword in keywords:
            if keyword in page_text:
                found_keywords.append(keyword)
        
        print(f"   Palavras-chave encontradas: {found_keywords}")
        
        # Procurar tabelas ou listas
        tables = soup.find_all('table')
        cards = soup.find_all('div', class_=['card', 'vehicle-card'])
        lists = soup.find_all(['ul', 'ol'])
        
        print(f"   Elementos estruturais: {len(tables)} tabelas, {len(cards)} cards, {len(lists)} listas")
        
    elif veiculos_response.status_code == 302:
        print(f"   Redirecionamento para: {veiculos_response.headers.get('Location', 'N/A')}")
    
    # 4. Testar criação de usuário admin se não existir
    print("\n4. TESTANDO CRIAÇÃO DE DADOS DE TESTE")
    
    # Verificar se precisa criar usuário admin
    try:
        # Tentar acessar endpoint que requer admin
        admin_test = session.get(f'{base_url}/usuarios')
        print(f"   GET /usuarios (admin required): {admin_test.status_code}")
    except Exception as e:
        print(f"   Erro ao testar acesso admin: {e}")
    
    # 5. Testar criação de veículo
    print("\n5. TESTANDO CRIAÇÃO DE VEÍCULO")
    novo_veiculo_get = session.get(f'{base_url}/veiculos/novo')
    print(f"   GET /veiculos/novo: {novo_veiculo_get.status_code}")
    
    if novo_veiculo_get.status_code == 200:
        # Analisar formulário
        soup = BeautifulSoup(novo_veiculo_get.text, 'html.parser')
        forms = soup.find_all('form')
        inputs = soup.find_all('input')
        
        print(f"   Formulários encontrados: {len(forms)}")
        print(f"   Inputs encontrados: {len(inputs)}")
        
        # Tentar submeter dados de veículo
        veiculo_data = {
            'placa': 'TST1234',
            'marca': 'Volkswagen', 
            'modelo': 'Amarok',
            'ano': '2023',
            'tipo': 'Caminhonete'
        }
        
        novo_veiculo_post = session.post(f'{base_url}/veiculos/novo', data=veiculo_data)
        print(f"   POST /veiculos/novo: {novo_veiculo_post.status_code}")
        
        if novo_veiculo_post.status_code == 302:
            print(f"   Redirecionado para: {novo_veiculo_post.headers.get('Location', 'N/A')}")
    
    # 6. Verificar se existe algum veículo criado
    print("\n6. VERIFICANDO VEÍCULOS EXISTENTES")
    veiculos_final = session.get(f'{base_url}/veiculos')
    
    if veiculos_final.status_code == 200:
        soup = BeautifulSoup(veiculos_final.text, 'html.parser')
        
        # Procurar pela placa TST1234 criada no teste
        if 'TST1234' in veiculos_final.text:
            print("   ✅ Veículo de teste encontrado na listagem")
        else:
            print("   ❌ Veículo de teste NÃO encontrado na listagem")
            
        # Verificar se página tem estrutura de listagem
        if 'tabela' in veiculos_final.text.lower() or 'table' in veiculos_final.text.lower():
            print("   ✅ Página tem estrutura de tabela")
        else:
            print("   ❌ Página NÃO tem estrutura de tabela visível")
    
    print("\n" + "=" * 60)
    print("🔍 DEBUG CONCLUÍDO")

def verificar_dados_existentes():
    """Verificar se existem dados no banco"""
    
    session = requests.Session()
    base_url = 'http://0.0.0.0:5000'
    
    print("\n🗄️ VERIFICANDO DADOS EXISTENTES NO SISTEMA")
    print("=" * 60)
    
    # Fazer login primeiro
    login_data = {
        'email': 'admin@teste.com', 
        'password': 'admin123'
    }
    session.post(f'{base_url}/login', data=login_data)
    
    # Endpoints para verificar
    endpoints = [
        '/veiculos',
        '/funcionarios', 
        '/obras',
        '/dashboard'
    ]
    
    for endpoint in endpoints:
        try:
            response = session.get(f'{base_url}{endpoint}')
            print(f"   {endpoint}: Status {response.status_code}")
            
            if response.status_code == 200:
                # Contar elementos na página
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.find_all('tr')  # Linhas de tabela
                cards = soup.find_all('div', class_=['card'])  # Cards
                
                if len(rows) > 1:  # Mais que header
                    print(f"     📊 {len(rows)-1} itens em tabela")
                elif len(cards) > 0:
                    print(f"     📋 {len(cards)} cards encontrados")
                else:
                    print(f"     📭 Nenhum dado visível")
                    
        except Exception as e:
            print(f"   {endpoint}: ERRO - {e}")

if __name__ == "__main__":
    teste_manual_completo()
    verificar_dados_existentes()