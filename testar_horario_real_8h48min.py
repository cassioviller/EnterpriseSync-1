#!/usr/bin/env python3
"""
TESTE HORÁRIO REAL: 7h12 às 17h (8h48min por dia)
Calcula valor/hora baseado na jornada real de trabalho
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario
from kpis_engine import KPIsEngine
from datetime import date
import calendar

def calcular_horas_reais_julho_2025():
    """Calcula horas reais de julho 2025 com jornada 8h48min"""
    
    print("CÁLCULO HORAS REAIS - JULHO 2025")
    print("=" * 50)
    
    # Horário: 7h12 às 17h = 9h48min no local
    # Menos 1h de almoço = 8h48min = 8.8h por dia
    horas_diarias = 8.8
    
    # Julho 2025: calcular dias úteis
    ano, mes = 2025, 7
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    
    dias_uteis = 0
    feriados = []  # Julho 2025 sem feriados nacionais
    
    data_atual = primeiro_dia
    dias_detalhados = []
    
    while data_atual <= ultimo_dia:
        dia_semana = data_atual.weekday()  # 0=seg, 6=dom
        nome_dia = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'][dia_semana]
        
        if dia_semana < 5 and data_atual not in feriados:  # Seg-Sex
            dias_uteis += 1
            dias_detalhados.append(f"{data_atual.strftime('%d/%m')} ({nome_dia}) - ÚTIL")
        else:
            dias_detalhados.append(f"{data_atual.strftime('%d/%m')} ({nome_dia}) - Folga")
        
        data_atual += pd.Timedelta(days=1) if 'pd' in globals() else date(data_atual.year, data_atual.month, data_atual.day + 1) if data_atual.day < calendar.monthrange(ano, mes)[1] else date(data_atual.year, data_atual.month + 1, 1) if data_atual.month < 12 else date(data_atual.year + 1, 1, 1)
        
        # Correção para próximo dia
        try:
            data_atual = data_atual.replace(day=data_atual.day + 1)
        except ValueError:
            if data_atual.month == 12:
                data_atual = data_atual.replace(year=data_atual.year + 1, month=1, day=1)
            else:
                data_atual = data_atual.replace(month=data_atual.month + 1, day=1)
        
        if data_atual > ultimo_dia:
            break
    
    horas_mensais = dias_uteis * horas_diarias
    
    print(f"Horário: 7h12 às 17h")
    print(f"Tempo no local: 9h48min")
    print(f"Almoço: 1h")
    print(f"Horas efetivas/dia: 8h48min = {horas_diarias}h")
    print(f"Dias úteis julho: {dias_uteis}")
    print(f"Horas mensais: {dias_uteis} × {horas_diarias}h = {horas_mensais}h")
    
    return dias_uteis, horas_mensais, horas_diarias

def calcular_valor_hora_correto_8h48():
    """Calcula o valor/hora correto com jornada 8h48min"""
    
    print("\nCÁLCULO VALOR/HORA CORRETO")
    print("=" * 40)
    
    salario = 2800.00
    dias_uteis = 23  # Julho 2025
    horas_diarias = 8.8  # 8h48min
    horas_mensais = dias_uteis * horas_diarias  # 23 × 8.8 = 202.4h
    
    valor_hora = salario / horas_mensais
    
    print(f"Salário: R$ {salario:.2f}")
    print(f"Horas mensais: {horas_mensais}h")
    print(f"Valor/hora: R$ {valor_hora:.2f}")
    
    # Para 184h trabalhadas
    horas_trabalhadas = 184.0
    custo_184h = horas_trabalhadas * valor_hora
    
    print(f"\nPara {horas_trabalhadas}h trabalhadas:")
    print(f"Custo: {horas_trabalhadas}h × R$ {valor_hora:.2f} = R$ {custo_184h:.2f}")
    
    return valor_hora, custo_184h

def testar_com_danilo():
    """Testa o cálculo com Danilo usando nova engine"""
    
    with app.app_context():
        print("\nTESTE COM DANILO - NOVA ENGINE")
        print("=" * 45)
        
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return
        
        # Recalcular com nova engine
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(
            danilo.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        horas_trabalhadas = kpis.get('horas_trabalhadas', 0)
        custo_engine = kpis.get('custo_mao_obra', 0)
        
        print(f"Funcionário: {danilo.nome}")
        print(f"Horas trabalhadas: {horas_trabalhadas}h")
        print(f"Custo engine: R$ {custo_engine:.2f}")
        
        # Cálculo manual
        valor_hora_manual = 2800.00 / (23 * 8.8)  # 202.4h
        custo_manual = horas_trabalhadas * valor_hora_manual
        
        print(f"Valor/hora manual: R$ {valor_hora_manual:.2f}")
        print(f"Custo manual: R$ {custo_manual:.2f}")
        
        diferenca = abs(custo_engine - custo_manual)
        print(f"Diferença: R$ {diferenca:.2f}")
        
        if diferenca < 1.0:
            print("✅ CÁLCULO CORRETO!")
        else:
            print("❌ Ainda há diferença")

if __name__ == "__main__":
    print("TESTE HORÁRIO REAL 8H48MIN")
    print("=" * 60)
    
    try:
        # Calcular horas reais
        dias_uteis, horas_mensais, horas_diarias = calcular_horas_reais_julho_2025()
        
        # Calcular valor/hora
        valor_hora, custo_184h = calcular_valor_hora_correto_8h48()
        
        # Testar com Danilo
        testar_com_danilo()
        
        print(f"\n" + "=" * 60)
        print("RESUMO:")
        print(f"✅ Jornada real: 8h48min por dia")
        print(f"✅ Julho 2025: {dias_uteis} dias úteis = {horas_mensais}h")
        print(f"✅ Valor/hora: R$ {valor_hora:.2f}")
        print(f"✅ Custo para 184h: R$ {custo_184h:.2f}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        # Cálculo simples direto
        print("\nCÁLCULO DIRETO:")
        print("Julho 2025: 23 dias úteis × 8.8h = 202.4h")
        print("Valor/hora: R$ 2.800 ÷ 202.4h = R$ 13.83")
        print("Custo 184h: 184h × R$ 13.83 = R$ 2.544,72")