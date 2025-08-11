#!/usr/bin/env python3
"""
TESTE DO CÁLCULO CORRIGIDO - CARLOS ALBERTO
Verificar se o cálculo está seguindo exatamente a metodologia solicitada:
- 8,8h/dia × 23 dias úteis julho = 202,4h mensais
- R$ 2.106 ÷ 202,4h = R$ 10,41/hora
- 7,8h extras × R$ 10,41 = R$ 81,20
"""

from datetime import date
from calendar import monthrange
import calendar

def calcular_dias_uteis(ano, mes):
    """Calcular dias úteis (seg-sex) em um mês específico"""
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = date(ano, mes, dia)
        # 0=segunda, 1=terça, ..., 6=domingo
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    return dias_uteis

def testar_calculo_carlos():
    """Testar o cálculo exato do Carlos Alberto"""
    
    print("🧮 TESTE DO CÁLCULO CORRIGIDO - CARLOS ALBERTO")
    print("=" * 60)
    
    # Dados do Carlos Alberto
    salario = 2106.00
    horas_diarias = 8.8
    horas_extras = 7.8
    mes_teste = 7  # Julho
    ano_teste = 2025
    
    # Calcular dias úteis de julho/2025
    dias_uteis_julho = calcular_dias_uteis(ano_teste, mes_teste)
    
    print(f"📅 Mês de referência: {mes_teste}/{ano_teste}")
    print(f"📊 Dias úteis no mês: {dias_uteis_julho}")
    print(f"⏰ Horas por dia: {horas_diarias}h")
    print(f"💰 Salário mensal: R$ {salario:,.2f}")
    print()
    
    # Cálculo das horas mensais
    horas_mensais = horas_diarias * dias_uteis_julho
    print(f"📈 Horas mensais: {horas_diarias}h × {dias_uteis_julho} dias = {horas_mensais}h")
    
    # Cálculo do valor hora
    valor_hora = salario / horas_mensais
    print(f"💵 Valor hora: R$ {salario:,.2f} ÷ {horas_mensais}h = R$ {valor_hora:.2f}")
    
    # Cálculo das horas extras (50% adicional)
    multiplicador = 1.5  # 50% adicional conforme CLT
    valor_extras = horas_extras * valor_hora * multiplicador
    print(f"⚡ Horas extras: {horas_extras}h × R$ {valor_hora:.2f} × {multiplicador} = R$ {valor_extras:.2f}")
    
    # Custo total
    custo_total = salario + valor_extras
    print(f"💼 Custo total mão de obra: R$ {salario:,.2f} + R$ {valor_extras:.2f} = R$ {custo_total:,.2f}")
    
    print()
    print("✅ VALIDAÇÃO:")
    print(f"   - Esperado valor hora: R$ 10,41")
    print(f"   - Calculado valor hora: R$ {valor_hora:.2f}")
    print(f"   - Esperado extras: R$ 121,74 (com 50% adicional)")
    print(f"   - Calculado extras: R$ {valor_extras:.2f}")
    print(f"   - Esperado total: R$ 2.227,74")
    print(f"   - Calculado total: R$ {custo_total:.2f}")
    
    # Verificar se está correto
    if abs(valor_hora - 10.41) < 0.01 and abs(valor_extras - 121.74) < 0.50:
        print("✅ CÁLCULO CORRETO!")
    else:
        print("❌ CÁLCULO INCORRETO - Revisar metodologia")

if __name__ == "__main__":
    testar_calculo_carlos()