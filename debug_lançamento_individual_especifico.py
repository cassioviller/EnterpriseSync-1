#!/usr/bin/env python3
"""
DEBUG ESPECÍFICO: Lançamento Individual vs Período
Identificar diferença entre os dois fluxos
"""

from datetime import datetime, date

def simular_fluxo_periodo():
    """Simula o fluxo que funciona (período)"""
    
    print("✅ FLUXO QUE FUNCIONA - PERÍODO:")
    print("=" * 50)
    
    # Dados que vêm do formulário no período
    data_inicio = "2025-07-18"
    data_fim = "2025-07-18"
    
    print(f"Frontend envia:")
    print(f"  data_inicio: '{data_inicio}'")
    print(f"  data_fim: '{data_fim}'")
    print(f"  data: None (vazio)")
    
    # Processamento no backend (views.py linhas 4069-4078)
    if data_inicio and data_fim:
        inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        print(f"\nBackend processa:")
        print(f"  inicio: {inicio} (mês {inicio.month})")
        print(f"  fim: {fim} (mês {fim.month})")
        
        # Gerar lista de datas do período
        from datetime import timedelta
        datas_processamento = []
        data_atual = inicio
        while data_atual <= fim:
            datas_processamento.append(data_atual)
            data_atual += timedelta(days=1)
        
        print(f"  datas_processamento: {datas_processamento}")
        
        for data in datas_processamento:
            print(f"  ✅ Data salva: {data} (mês {data.month})")

def simular_fluxo_individual():
    """Simula o fluxo com problema (individual)"""
    
    print("\n❌ FLUXO COM PROBLEMA - INDIVIDUAL:")
    print("=" * 50)
    
    # Dados que vêm do formulário individual  
    data_unica = "2025-07-18"
    data_inicio = None
    data_fim = None
    
    print(f"Frontend envia:")
    print(f"  data: '{data_unica}'")
    print(f"  data_inicio: {data_inicio}")
    print(f"  data_fim: {data_fim}")
    
    # Processamento no backend (views.py linhas 4082-4094)
    if data_unica:
        print(f"\nBackend processa:")
        print(f"  📅 LANÇAMENTO INDIVIDUAL - data_unica: '{data_unica}'")
        
        data_convertida = datetime.strptime(data_unica, '%Y-%m-%d').date()
        print(f"  📅 Data convertida: {data_convertida} (mês {data_convertida.month})")
        
        # VERIFICAR SE ESTÁ SENDO ALTERADA PARA O MÊS ATUAL
        if data_convertida.month == 8:  # Agosto (mês atual)
            print(f"  🚨 PROBLEMA DETECTADO: Data convertida está em agosto!")
            print(f"  Original string: '{data_unica}'")
            print(f"  Resultado conversão: {data_convertida}")
        else:
            print(f"  ✅ Data convertida corretamente para julho")
        
        datas_processamento = [data_convertida]
        print(f"  datas_processamento: {datas_processamento}")
        
        for data in datas_processamento:
            print(f"  Data que será salva: {data} (mês {data.month})")

def identificar_diferenca():
    """Identifica a diferença entre os fluxos"""
    
    print("\n🔍 ANÁLISE DAS DIFERENÇAS:")
    print("-" * 40)
    
    print("PERÍODO (funciona):")
    print("  1. data_inicio e data_fim são processados")
    print("  2. Usa datetime.strptime() diretamente")
    print("  3. Gera lista com timedelta")
    print("  4. Salva datas corretas")
    
    print("\nINDIVIDUAL (problema):")
    print("  1. data_unica é processado")
    print("  2. Usa datetime.strptime() diretamente (igual)")
    print("  3. Cria lista com uma data apenas")
    print("  4. ???") # O problema deve estar depois
    
    print("\n🤔 POSSÍVEL CAUSA:")
    print("  - O problema pode estar DEPOIS da conversão")
    print("  - Talvez na criação do registro no banco")
    print("  - Ou no JavaScript que envia dados diferentes")

if __name__ == "__main__":
    simular_fluxo_periodo()
    simular_fluxo_individual() 
    identificar_diferenca()