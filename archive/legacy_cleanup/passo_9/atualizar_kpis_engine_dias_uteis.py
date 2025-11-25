#!/usr/bin/env python3
"""
ATUALIZAR KPIs ENGINE - CÁLCULO COM DIAS ÚTEIS REAIS
Implementar metodologia correta: horas/dia × dias úteis do mês específico
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
        # 0=segunda, 1=terça, ..., 6=domingo  
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    return dias_uteis

def atualizar_kpis_engine():
    """Atualizar o arquivo kpis_engine.py com o cálculo correto"""
    
    print("🔧 ATUALIZANDO KPIs ENGINE COM DIAS ÚTEIS REAIS")
    print("=" * 60)
    
    # Ler o arquivo atual
    with open('kpis_engine.py', 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Localizar e substituir a função de cálculo de valor hora
    novo_codigo = '''
def calcular_valor_hora_funcionario(funcionario, data_referencia):
    """
    Calcular valor hora do funcionário baseado em dias úteis reais do mês
    
    Args:
        funcionario: Instância do modelo Funcionario
        data_referencia: datetime.date do mês de referência
    
    Returns:
        float: Valor da hora normal do funcionário
    """
    from calendar import monthrange
    
    if not funcionario.salario:
        return 0.0
    
    # Calcular dias úteis reais do mês
    ano = data_referencia.year
    mes = data_referencia.month
    
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = data_referencia.replace(day=dia)
        # 0=segunda, 1=terça, ..., 6=domingo
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    # Usar horário específico do funcionário
    if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
        horas_diarias = funcionario.horario_trabalho.horas_diarias
    else:
        horas_diarias = 8.8  # Padrão baseado no horário Carlos Alberto
    
    # Horas mensais = horas/dia × dias úteis do mês
    horas_mensais = horas_diarias * dias_uteis
    
    return funcionario.salario / horas_mensais if horas_mensais > 0 else 0.0

def calcular_valor_horas_extras_funcionario(funcionario, horas_extras, tipo_registro, data_referencia):
    """
    Calcular valor das horas extras conforme legislação brasileira
    
    Args:
        funcionario: Instância do modelo Funcionario
        horas_extras: Quantidade de horas extras (float)
        tipo_registro: Tipo do registro ('domingo_trabalhado', etc.)
        data_referencia: datetime.date do mês de referência
    
    Returns:
        float: Valor monetário das horas extras
    """
    if not horas_extras or horas_extras <= 0:
        return 0.0
    
    valor_hora_normal = calcular_valor_hora_funcionario(funcionario, data_referencia)
    
    if valor_hora_normal <= 0:
        return 0.0
    
    # Multiplicador conforme legislação brasileira (CLT)
    if tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
        multiplicador = 2.0  # 100% adicional
    else:
        multiplicador = 1.5  # 50% adicional padrão
    
    return horas_extras * valor_hora_normal * multiplicador
'''
    
    # Adicionar as novas funções ao início do arquivo
    if 'def calcular_valor_hora_funcionario' not in conteudo:
        # Inserir após os imports
        import_end = conteudo.find('def ')
        if import_end != -1:
            conteudo_atualizado = conteudo[:import_end] + novo_codigo + '\n\n' + conteudo[import_end:]
        else:
            conteudo_atualizado = novo_codigo + '\n\n' + conteudo
        
        # Salvar arquivo atualizado
        with open('kpis_engine.py', 'w', encoding='utf-8') as f:
            f.write(conteudo_atualizado)
        
        print("✅ KPIs Engine atualizado com cálculo de dias úteis reais")
    else:
        print("ℹ️ KPIs Engine já possui as funções de cálculo")

def testar_calculo_com_dados_reais():
    """Testar com dados reais do Carlos Alberto"""
    
    with app.app_context():
        # Buscar Carlos Alberto
        carlos = Funcionario.query.filter_by(nome='Carlos Alberto Rigolin Junior').first()
        
        if not carlos:
            print("❌ Carlos Alberto não encontrado no banco")
            return
        
        print(f"\n📊 TESTE COM DADOS REAIS:")
        print(f"👤 Funcionário: {carlos.nome}")
        print(f"💰 Salário: R$ {carlos.salario:,.2f}")
        
        # Testar para julho/2025
        data_julho = date(2025, 7, 15)
        dias_uteis_julho = calcular_dias_uteis(2025, 7)
        
        print(f"📅 Mês: Julho/2025")
        print(f"📊 Dias úteis: {dias_uteis_julho}")
        
        if carlos.horario_trabalho:
            horas_diarias = carlos.horario_trabalho.horas_diarias
            print(f"⏰ Horas/dia: {horas_diarias}h")
            
            horas_mensais = horas_diarias * dias_uteis_julho
            valor_hora = carlos.salario / horas_mensais
            
            print(f"📈 Horas mensais: {horas_mensais}h")
            print(f"💵 Valor hora: R$ {valor_hora:.2f}")
            
            # Testar 7.8h extras
            valor_extras = 7.8 * valor_hora * 1.5
            print(f"⚡ 7.8h extras: R$ {valor_extras:.2f}")
            print(f"💼 Custo total: R$ {carlos.salario + valor_extras:,.2f}")
        else:
            print("⚠️ Horário de trabalho não definido")

if __name__ == "__main__":
    atualizar_kpis_engine()
    testar_calculo_com_dados_reais()