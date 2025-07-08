"""
Script para testar os KPIs do Cássio após as correções
"""

from app import app
from kpis_engine_v3 import calcular_kpis_funcionario_v3
from datetime import date

def testar_kpis_cassio():
    """Testa os KPIs do Cássio para junho de 2025"""
    
    with app.app_context():
        # ID do Cássio
        cassio_id = 101
        
        # Período de teste (junho 2025)
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        # Calcular KPIs
        kpis = calcular_kpis_funcionario_v3(cassio_id, data_inicio, data_fim)
        
        if kpis:
            print("KPIs do Cássio - Junho 2025:")
            print(f"1. Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
            print(f"2. Horas Extras: {kpis['horas_extras']:.1f}h")
            print(f"3. Faltas: {kpis['faltas']}")
            print(f"4. Atrasos: {kpis['atrasos']:.2f}h")
            print(f"5. Produtividade: {kpis['produtividade']:.1f}%")
            print(f"6. Absenteísmo: {kpis['absenteismo']:.1f}%")
            print(f"7. Média Diária: {kpis['media_diaria']:.1f}h")
            print(f"8. Horas Perdidas: {kpis['horas_perdidas']:.1f}h")
            print(f"9. Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
            print(f"10. Custo Alimentação: R$ {kpis['custo_alimentacao']:.2f}")
            
            print("\nDetalhes dos atrasos:")
            print(f"- Total de atrasos em minutos: {kpis.get('total_atrasos_minutos', 0)}")
            print(f"- Total de atrasos em horas: {kpis['atrasos']:.2f}h")
            
            # Verificar se feriado trabalhado está sendo contabilizado corretamente
            print(f"\nHoras extras esperadas: 8h (feriado) + 4h (sábado) + 4h (domingo) = 16h")
            print(f"Horas extras calculadas: {kpis['horas_extras']:.1f}h")
            
            # Verificar atrasos esperados
            print(f"\nAtrasos esperados: 30min + 30min = 60min = 1.0h")
            print(f"Atrasos calculados: {kpis['atrasos']:.2f}h")
            
        else:
            print("Erro ao calcular KPIs do Cássio")

if __name__ == "__main__":
    testar_kpis_cassio()