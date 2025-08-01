#!/usr/bin/env python3
"""
CÁLCULO CORRETO DE DIAS ÚTEIS POR MÊS
Calcula dias úteis reais considerando feriados e fins de semana
"""

import os
import sys
sys.path.append('.')

from datetime import date, timedelta
import calendar

def calcular_dias_uteis_mes(ano, mes):
    """
    Calcula dias úteis reais do mês (seg-sex, excluindo feriados)
    """
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    
    dias_uteis = 0
    feriados_nacionais = get_feriados_brasil(ano)
    
    data_atual = primeiro_dia
    while data_atual <= ultimo_dia:
        # Segunda a sexta (weekday 0-4)
        if data_atual.weekday() < 5:  # 0=seg, 1=ter, 2=qua, 3=qui, 4=sex
            # Verificar se não é feriado
            if data_atual not in feriados_nacionais:
                dias_uteis += 1
        
        data_atual += timedelta(days=1)
    
    return dias_uteis

def get_feriados_brasil(ano):
    """Feriados nacionais fixos do Brasil"""
    feriados = [
        date(ano, 1, 1),   # Confraternização Universal
        date(ano, 4, 21),  # Tiradentes
        date(ano, 5, 1),   # Dia do Trabalhador
        date(ano, 9, 7),   # Independência do Brasil
        date(ano, 10, 12), # Nossa Senhora Aparecida
        date(ano, 11, 2),  # Finados
        date(ano, 11, 15), # Proclamação da República
        date(ano, 12, 25), # Natal
    ]
    return feriados

def analisar_julho_2025():
    """Analisa especificamente julho de 2025"""
    
    print("ANÁLISE JULHO 2025")
    print("=" * 40)
    
    ano, mes = 2025, 7
    dias_mes = calendar.monthrange(ano, mes)[1]
    dias_uteis = calcular_dias_uteis_mes(ano, mes)
    
    print(f"Mês: Julho/{ano}")
    print(f"Total de dias: {dias_mes}")
    print(f"Dias úteis (seg-sex): {dias_uteis}")
    
    # Calcular fins de semana
    primeiro_dia = date(ano, mes, 1)
    sabados = 0
    domingos = 0
    
    for dia in range(1, dias_mes + 1):
        data_dia = date(ano, mes, dia)
        if data_dia.weekday() == 5:  # Sábado
            sabados += 1
        elif data_dia.weekday() == 6:  # Domingo
            domingos += 1
    
    print(f"Sábados: {sabados}")
    print(f"Domingos: {domingos}")
    print(f"Feriados: 0 (julho/2025 não tem feriados nacionais)")
    
    # Horas trabalhadas (considerando 8h por dia útil)
    horas_esperadas_mes = dias_uteis * 8
    
    print(f"\nHORAS DE TRABALHO:")
    print(f"Dias úteis × 8h = {dias_uteis} × 8 = {horas_esperadas_mes}h")
    
    return dias_uteis, horas_esperadas_mes

def calcular_valor_hora_correto(salario, ano, mes):
    """Calcula valor/hora baseado nos dias úteis reais do mês"""
    
    dias_uteis = calcular_dias_uteis_mes(ano, mes)
    horas_mensais = dias_uteis * 8  # 8h por dia útil
    valor_hora = salario / horas_mensais
    
    return valor_hora, horas_mensais, dias_uteis

def testar_calculo_danilo():
    """Testa o cálculo correto para Danilo em julho/2025"""
    
    print("\nTESTE CÁLCULO CORRETO - DANILO")
    print("=" * 50)
    
    salario_danilo = 2800.00
    horas_trabalhadas = 184.0  # Conforme registros
    
    # Cálculo correto
    valor_hora, horas_mensais, dias_uteis = calcular_valor_hora_correto(salario_danilo, 2025, 7)
    custo_correto = horas_trabalhadas * valor_hora
    
    print(f"Salário: R$ {salario_danilo:,.2f}")
    print(f"Dias úteis julho/2025: {dias_uteis}")
    print(f"Horas mensais (real): {horas_mensais}h")
    print(f"Valor/hora (correto): R$ {valor_hora:.2f}")
    print(f"Horas trabalhadas: {horas_trabalhadas}h")
    print(f"Custo correto: R$ {custo_correto:.2f}")
    
    # Comparar com cálculo antigo (220h)
    valor_hora_antigo = salario_danilo / 220
    custo_antigo = horas_trabalhadas * valor_hora_antigo
    
    print(f"\nCOMPARAÇÃO:")
    print(f"Cálculo antigo (220h): R$ {custo_antigo:.2f}")
    print(f"Cálculo correto ({horas_mensais}h): R$ {custo_correto:.2f}")  
    print(f"Diferença: R$ {abs(custo_correto - custo_antigo):.2f}")
    
    return valor_hora, horas_mensais

if __name__ == "__main__":
    print("CÁLCULO CORRETO DE VALOR/HORA")
    print("=" * 60)
    
    # Analisar julho 2025
    dias_uteis, horas_esperadas = analisar_julho_2025()
    
    # Testar com Danilo
    valor_hora, horas_mensais = testar_calculo_danilo()
    
    print(f"\n" + "=" * 60)
    print("FÓRMULA CORRETA:")
    print(f"valor_hora = salario_mensal / (dias_uteis_mes × 8)")
    print(f"Para julho/2025: valor_hora = salario / {horas_mensais}")
    print(f"custo_mao_obra = horas_trabalhadas × valor_hora")