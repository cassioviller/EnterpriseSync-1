#!/usr/bin/env python3
"""
TESTE URGENTE: Fazer um lançamento real para capturar logs
"""

import requests
from datetime import date

def simular_requisicao_individual():
    """Simula requisição individual como seria enviada pelo navegador"""
    
    print("🧪 SIMULANDO REQUISIÇÃO INDIVIDUAL")
    print("=" * 50)
    
    # Dados que deveriam ser enviados para 18/07/2025
    dados_form = {
        'data': '2025-07-18',  # Campo individual
        'data_inicio': '',     # Vazio no individual
        'data_fim': '',        # Vazio no individual
        'tipo': 'almoco',
        'valor': '22.00',
        'obra_id': '1',
        'restaurante_id': '1',
        'funcionarios_ids[]': ['7', '10'],  # IDs de exemplo
        'observacoes': 'Teste debug individual'
    }
    
    print("📤 Dados que seriam enviados:")
    for key, value in dados_form.items():
        if 'data' in key:
            print(f"   {key}: '{value}'")
    
    # URL do endpoint
    url = "http://localhost:5000/alimentacao/novo"
    
    print(f"\n📍 URL: {url}")
    print("⚠️ Simulação - não enviando requisição real")
    print("   (para evitar criar registros de teste)")

def simular_requisicao_periodo():
    """Simula requisição período que funciona"""
    
    print("\n✅ SIMULANDO REQUISIÇÃO PERÍODO (QUE FUNCIONA)")
    print("=" * 50)
    
    # Dados que deveriam ser enviados para período 18/07/2025
    dados_form = {
        'data': '',                # Vazio no período
        'data_inicio': '2025-07-18',  # Período
        'data_fim': '2025-07-18',     # Período
        'tipo': 'almoco',
        'valor': '22.00',
        'obra_id': '1',
        'restaurante_id': '1',
        'funcionarios_ids[]': ['7', '10'],
        'observacoes': 'Teste debug período'
    }
    
    print("📤 Dados que seriam enviados:")
    for key, value in dados_form.items():
        if 'data' in key:
            print(f"   {key}: '{value}'")

def analisar_diferenca_dados():
    """Analisa diferença nos dados enviados"""
    
    print("\n🔍 ANÁLISE DOS DADOS:")
    print("-" * 40)
    
    print("INDIVIDUAL (problema):")
    print("   data: '2025-07-18'")
    print("   data_inicio: ''")
    print("   data_fim: ''")
    
    print("\nPERÍODO (funciona):")
    print("   data: ''")
    print("   data_inicio: '2025-07-18'")
    print("   data_fim: '2025-07-18'")
    
    print("\n💡 HIPÓTESE:")
    print("   O problema pode estar no frontend JavaScript")
    print("   que altera o campo 'data' antes do envio")
    print("   mas não altera 'data_inicio'/'data_fim'")

if __name__ == "__main__":
    simular_requisicao_individual()
    simular_requisicao_periodo()
    analisar_diferenca_dados()