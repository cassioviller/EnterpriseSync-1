#!/usr/bin/env python3
"""
VERIFICAR CÁLCULO EM PRODUÇÃO
Testar se o cálculo corrigido está funcionando com dados reais
"""

import os
import sys
from datetime import datetime, date
from calendar import monthrange

# Configurar ambiente Flask
sys.path.insert(0, '/home/runner/workspace')
os.environ['FLASK_APP'] = 'main.py'

from app import app, db
from models import *

def calcular_dias_uteis(ano, mes):
    """Calcular dias úteis (seg-sex) em um mês específico"""
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = date(ano, mes, dia)
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    return dias_uteis

def verificar_calculo():
    """Verificar cálculo com dados de produção"""
    
    with app.app_context():
        print("🔍 VERIFICANDO CÁLCULO EM PRODUÇÃO")
        print("=" * 50)
        
        # Buscar funcionários com horário 8.8h
        funcionarios = Funcionario.query.join(HorarioTrabalho).filter(
            HorarioTrabalho.horas_diarias == 8.8
        ).all()
        
        if not funcionarios:
            print("❌ Nenhum funcionário com 8.8h encontrado")
            return
        
        print(f"👥 Funcionários encontrados: {len(funcionarios)}")
        
        for func in funcionarios:
            print(f"\n👤 {func.nome}")
            print(f"💰 Salário: R$ {func.salario:,.2f}")
            print(f"⏰ Horas/dia: {func.horario_trabalho.horas_diarias}h")
            
            # Testar para julho/2025
            dias_uteis_julho = calcular_dias_uteis(2025, 7)
            horas_mensais = func.horario_trabalho.horas_diarias * dias_uteis_julho
            valor_hora = func.salario / horas_mensais
            
            print(f"📊 Julho/2025: {dias_uteis_julho} dias úteis")
            print(f"📈 Horas mensais: {horas_mensais}h")
            print(f"💵 Valor hora: R$ {valor_hora:.2f}")
            
            # Simular 7.8h extras
            valor_7_8h = 7.8 * valor_hora
            print(f"⚡ 7.8h extras: R$ {valor_7_8h:.2f}")
            print(f"💼 Total: R$ {func.salario + valor_7_8h:.2f}")
            
            # Verificar se está próximo dos valores esperados
            if abs(valor_hora - 10.41) < 0.05:
                print("✅ Valor hora correto!")
            if abs(valor_7_8h - 81.20) < 2.0:
                print("✅ Valor extras correto!")

if __name__ == "__main__":
    verificar_calculo()