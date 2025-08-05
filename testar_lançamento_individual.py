#!/usr/bin/env python3
"""
TESTE: Lançamento Individual de Alimentação
Simular o processo de lançamento individual para identificar onde a data é alterada
"""

from datetime import datetime, date

def testar_conversao_data_individual():
    """Testa a conversão de data individual como no sistema"""
    
    print("🧪 TESTE: Conversão Data Individual")
    print("=" * 50)
    
    # Casos que podem estar causando problema
    casos_teste = [
        "2025-07-15",  # Julho normal
        "2025-7-15",   # Julho sem zero
        "15/07/2025",  # Formato brasileiro (pode vir do frontend)
        "07/15/2025",  # Formato americano
    ]
    
    for caso in casos_teste:
        print(f"\n📅 Testando: '{caso}'")
        
        try:
            # Tentar conversão ISO (como no código atual)
            if '-' in caso and len(caso.split('-')[0]) == 4:
                data_convertida = datetime.strptime(caso, '%Y-%m-%d').date()
                print(f"   ✅ Formato ISO: {data_convertida} (mês {data_convertida.month})")
                
                # Verificar se está correto
                if data_convertida.month == 7:
                    print(f"   ✅ Julho correto")
                else:
                    print(f"   ❌ Mês incorreto: {data_convertida.month}")
            
            # Tentar formato brasileiro
            elif '/' in caso:
                # DD/MM/YYYY
                if len(caso.split('/')[2]) == 4:
                    data_convertida = datetime.strptime(caso, '%d/%m/%Y').date()
                    print(f"   ✅ Formato BR: {data_convertida} (mês {data_convertida.month})")
                # MM/DD/YYYY 
                else:
                    data_convertida = datetime.strptime(caso, '%m/%d/%Y').date()
                    print(f"   ⚠️ Formato US: {data_convertida} (mês {data_convertida.month})")
            
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")

def simular_problema_timezone():
    """Simula problema de timezone que pode estar afetando as datas"""
    
    print("\n🌍 TESTE: Problemas de Timezone")
    print("-" * 40)
    
    # Data de julho
    data_julho = "2025-07-15"
    
    print(f"String original: '{data_julho}'")
    
    # Conversão simples (como no código)
    data_simples = datetime.strptime(data_julho, '%Y-%m-%d').date()
    print(f"Conversão simples: {data_simples} (mês {data_simples.month})")
    
    # Conversão com datetime completo
    data_datetime = datetime.strptime(data_julho, '%Y-%m-%d')
    print(f"DateTime completo: {data_datetime}")
    print(f"Date do DateTime: {data_datetime.date()} (mês {data_datetime.date().month})")
    
    # Data de hoje para comparação
    hoje = date.today()
    print(f"Data de hoje: {hoje} (mês {hoje.month})")
    
    # Verificar se o problema é alguma substituição automática
    if data_simples != date(2025, 7, 15):
        print("🚨 PROBLEMA: Data não é 15/07/2025!")

def verificar_html_date_input():
    """Verifica como o HTML date input envia as datas"""
    
    print("\n📝 TESTE: HTML Date Input")
    print("-" * 40)
    
    # HTML date input sempre envia no formato YYYY-MM-DD
    print("HTML date input formato: YYYY-MM-DD")
    print("Exemplo para 15 de julho: '2025-07-15'")
    
    # Testar se há algum problema na conversão
    data_html = "2025-07-15"
    data_convertida = datetime.strptime(data_html, '%Y-%m-%d').date()
    
    print(f"'{data_html}' → {data_convertida}")
    print(f"Ano: {data_convertida.year}")
    print(f"Mês: {data_convertida.month}")
    print(f"Dia: {data_convertida.day}")
    
    # Verificar se está correto
    esperado = date(2025, 7, 15)
    if data_convertida == esperado:
        print("✅ Conversão está correta!")
    else:
        print(f"❌ ERRO: Esperado {esperado}, obtido {data_convertida}")

if __name__ == "__main__":
    testar_conversao_data_individual()
    simular_problema_timezone()
    verificar_html_date_input()