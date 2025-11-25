#!/usr/bin/env python3
"""
SIMULAÇÃO: IMPACTO DE FERIADOS NO CÁLCULO
Mostra como feriados afetam o valor/hora e custos
"""

import os
import sys
sys.path.append('.')

from datetime import date, timedelta
import calendar

def simular_mes_com_feriado():
    """Simula um mês com feriado para mostrar o impacto"""
    
    print("SIMULAÇÃO: IMPACTO DE FERIADO")
    print("=" * 50)
    
    salario = 2800.00
    
    # Exemplo: Setembro 2025 (tem feriado no dia 7)
    ano, mes = 2025, 9
    
    # Calcular dias úteis SEM considerar feriado
    dias_sem_feriado = calcular_dias_uteis_simples(ano, mes)
    horas_sem_feriado = dias_sem_feriado * 8
    
    # Calcular dias úteis COM feriado (7 de setembro)
    feriados = [date(2025, 9, 7)]  # Independência do Brasil
    dias_com_feriado = calcular_dias_uteis_com_feriados(ano, mes, feriados)
    horas_com_feriado = dias_com_feriado * 8
    
    print(f"MÊS: SETEMBRO/2025")
    print(f"Feriado: 7 de setembro (domingo - não afeta)")
    print(f"")
    
    # Na verdade, 7 de setembro de 2025 é domingo, não afeta
    # Vamos simular com um feriado que cai em dia útil
    print("SIMULAÇÃO: Feriado em dia útil (ex: 21 de abril)")
    
    # Simular abril 2025 (21 de abril = Tiradentes)
    ano, mes = 2025, 4
    
    dias_sem_feriado = calcular_dias_uteis_simples(ano, mes)
    horas_sem_feriado = dias_sem_feriado * 8
    valor_hora_sem = salario / horas_sem_feriado
    
    feriados_abril = [date(2025, 4, 21)]  # Tiradentes (segunda-feira)
    dias_com_feriado = calcular_dias_uteis_com_feriados(ano, mes, feriados_abril)
    horas_com_feriado = dias_com_feriado * 8
    valor_hora_com = salario / horas_com_feriado
    
    print(f"ABRIL/2025:")
    print(f"Sem feriado: {dias_sem_feriado} dias = {horas_sem_feriado}h = R$ {valor_hora_sem:.2f}/h")
    print(f"Com feriado: {dias_com_feriado} dias = {horas_com_feriado}h = R$ {valor_hora_com:.2f}/h")
    
    diferenca = valor_hora_com - valor_hora_sem
    print(f"Diferença: +R$ {diferenca:.2f}/h ({(diferenca/valor_hora_sem)*100:.1f}% mais caro)")
    
    # Impacto no custo
    print(f"\nIMPACTO NO CUSTO:")
    print(f"Se funcionário trabalhar {horas_com_feriado}h:")
    custo_com_feriado = horas_com_feriado * valor_hora_com
    print(f"Custo: {horas_com_feriado}h × R$ {valor_hora_com:.2f} = R$ {custo_com_feriado:.2f}")
    print(f"Resultado: Custo igual ao salário (R$ {salario:.2f})")

def calcular_dias_uteis_simples(ano, mes):
    """Calcula dias úteis sem considerar feriados"""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    
    dias_uteis = 0
    data_atual = primeiro_dia
    
    while data_atual <= ultimo_dia:
        if data_atual.weekday() < 5:  # Seg-Sex
            dias_uteis += 1
        data_atual += timedelta(days=1)
    
    return dias_uteis

def calcular_dias_uteis_com_feriados(ano, mes, feriados):
    """Calcula dias úteis considerando feriados"""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    
    dias_uteis = 0
    data_atual = primeiro_dia
    
    while data_atual <= ultimo_dia:
        if data_atual.weekday() < 5 and data_atual not in feriados:
            dias_uteis += 1
        data_atual += timedelta(days=1)
    
    return dias_uteis

def explicar_logica_sistema():
    """Explica como o sistema funciona com feriados"""
    
    print(f"\n" + "=" * 50)
    print("COMO O SISTEMA FUNCIONA:")
    print("=" * 50)
    
    print("1. CÁLCULO DE DIAS ÚTEIS:")
    print("   • Conta seg-sex do mês")
    print("   • Remove feriados nacionais")
    print("   • Remove fins de semana")
    
    print("\n2. CÁLCULO DE HORAS MENSAIS:")
    print("   • horas_mensais = dias_úteis × 8h")
    print("   • Menos dias úteis = menos horas esperadas")
    
    print("\n3. VALOR/HORA DINÂMICO:")
    print("   • Se trabalhou normalmente:")
    print("     valor_hora = salário ÷ horas_trabalhadas")
    print("   • Se teve faltas/extras:")
    print("     valor_hora = salário ÷ horas_esperadas_mes")
    
    print("\n4. RESULTADO:")
    print("   • Mês com feriado = menos horas esperadas")
    print("   • Valor/hora aumenta automaticamente")
    print("   • Custo final mantém-se próximo ao salário")

if __name__ == "__main__":
    simular_mes_com_feriado()
    explicar_logica_sistema()
    
    print(f"\n" + "=" * 50)
    print("RESPOSTA À PERGUNTA:")
    print("✅ SIM, feriados reduzem dias úteis")
    print("✅ SIM, isso aumenta o valor/hora")  
    print("✅ SIM, o sistema recalcula automaticamente")
    print("✅ Custo final permanece justo (próximo ao salário)")