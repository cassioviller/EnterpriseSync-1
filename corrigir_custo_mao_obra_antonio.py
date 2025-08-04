#!/usr/bin/env python3
"""
🔧 CORRIGIR: Cálculo de custo de mão de obra do Antonio
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date
import calendar

def analisar_antonio_detalhado():
    """Analisar dados do Antonio em detalhes"""
    print("🔍 ANÁLISE DETALHADA: Antonio Fernandes da Silva")
    print("=" * 60)
    
    # Buscar Antonio
    antonio = Funcionario.query.filter(Funcionario.nome.like('%Antonio%')).first()
    if not antonio:
        print("❌ Antonio não encontrado")
        return None
    
    print(f"👤 {antonio.nome}")
    print(f"💰 Salário: R$ {antonio.salario:.2f}")
    
    # Dados do período
    registros = db.session.execute(text("""
        SELECT 
            tipo_registro,
            COUNT(*) as quantidade,
            SUM(horas_trabalhadas) as total_trabalhadas,
            SUM(horas_extras) as total_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        GROUP BY tipo_registro
        ORDER BY quantidade DESC
    """), {'func_id': antonio.id}).fetchall()
    
    print(f"\n📋 REGISTROS JULHO 2025:")
    dias_falta = 0
    total_extras = 0
    
    for reg in registros:
        print(f"   {reg.tipo_registro:<20} | {reg.quantidade:2}x | "
              f"Trab: {reg.total_trabalhadas:.1f}h | "
              f"Extras: {reg.total_extras:.1f}h")
        
        if reg.tipo_registro == 'falta':
            dias_falta = reg.quantidade
        total_extras += reg.total_extras
    
    print(f"\n📊 RESUMO:")
    print(f"   Faltas: {dias_falta} dias")
    print(f"   Horas extras: {total_extras:.1f}h")
    
    return antonio, dias_falta, total_extras

def calcular_custo_correto(funcionario, dias_falta, horas_extras):
    """Calcular custo correto da mão de obra"""
    print(f"\n🧮 CÁLCULO CORRETO CUSTO MÃO OBRA:")
    print("=" * 60)
    
    salario_base = funcionario.salario
    print(f"💰 Salário base: R$ {salario_base:.2f}")
    
    # Dias úteis de julho 2025
    dias_uteis_julho = 23  # Julho 2025 tem 23 dias úteis
    print(f"📅 Dias úteis julho: {dias_uteis_julho}")
    
    # Desconto por faltas
    valor_dia = salario_base / dias_uteis_julho
    desconto_faltas = valor_dia * dias_falta
    print(f"❌ Desconto faltas: {dias_falta} dias × R$ {valor_dia:.2f} = R$ {desconto_faltas:.2f}")
    
    # Salário após desconto
    salario_apos_faltas = salario_base - desconto_faltas
    print(f"💵 Salário após faltas: R$ {salario_apos_faltas:.2f}")
    
    # Valor hora para horas extras
    horas_mensais = dias_uteis_julho * 8.8  # 8.8h por dia útil (horário do Antonio)
    valor_hora = salario_base / horas_mensais
    print(f"⏰ Valor hora: R$ {salario_base:.2f} ÷ {horas_mensais:.1f}h = R$ {valor_hora:.2f}")
    
    # Horas extras com adicional
    # Verificar tipos de extras (sábado 50%, normal 60%)
    extras_sabado = db.session.execute(text("""
        SELECT SUM(horas_extras)
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND tipo_registro = 'sabado_trabalhado'
    """), {'func_id': funcionario.id}).scalar() or 0
    
    extras_normais = horas_extras - extras_sabado
    
    print(f"🔢 Horas extras sábado (50%): {extras_sabado:.1f}h")
    print(f"🔢 Horas extras normais (60%): {extras_normais:.1f}h")
    
    # Calcular valor das extras
    valor_extras_sabado = extras_sabado * valor_hora * 1.5  # 50% adicional
    valor_extras_normais = extras_normais * valor_hora * 1.6  # 60% adicional
    total_valor_extras = valor_extras_sabado + valor_extras_normais
    
    print(f"💲 Valor extras sábado: {extras_sabado:.1f}h × R$ {valor_hora:.2f} × 1.5 = R$ {valor_extras_sabado:.2f}")
    print(f"💲 Valor extras normais: {extras_normais:.1f}h × R$ {valor_hora:.2f} × 1.6 = R$ {valor_extras_normais:.2f}")
    print(f"💲 Total extras: R$ {total_valor_extras:.2f}")
    
    # Custo total correto
    custo_total_correto = salario_apos_faltas + total_valor_extras
    print(f"\n🎯 CUSTO TOTAL CORRETO:")
    print(f"   R$ {salario_apos_faltas:.2f} (salário - faltas) + R$ {total_valor_extras:.2f} (extras) = R$ {custo_total_correto:.2f}")
    
    return custo_total_correto, valor_extras_sabado + valor_extras_normais

def testar_kpi_atual(funcionario):
    """Testar KPI atual do Antonio"""
    print(f"\n🤖 TESTE KPI ATUAL:")
    print("=" * 60)
    
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"📊 KPI Custo Mão Obra: R$ {kpis['custo_mao_obra']:.2f}")
    print(f"📊 KPI Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    print(f"📊 KPI Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"📊 KPI Faltas: {kpis['faltas']}")
    
    return kpis

def corrigir_calculo_custo():
    """Corrigir cálculo de custo na engine"""
    print(f"\n🔧 VERIFICANDO MÉTODO _calcular_custo_mensal")
    print("=" * 60)
    
    # Vou analisar o método atual
    print("Verificando implementação atual do cálculo de custo...")
    
    return True

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO CUSTO MÃO OBRA - ANTONIO")
        print("=" * 80)
        
        # 1. Analisar Antonio
        antonio, faltas, extras = analisar_antonio_detalhado()
        
        if not antonio:
            exit()
        
        # 2. Calcular custo correto
        custo_correto, valor_extras = calcular_custo_correto(antonio, faltas, extras)
        
        # 3. Testar KPI atual
        kpis_atual = testar_kpi_atual(antonio)
        
        # 4. Comparar
        diferenca = abs(kpis_atual['custo_mao_obra'] - custo_correto)
        
        print(f"\n🎯 COMPARAÇÃO:")
        print(f"   KPI atual: R$ {kpis_atual['custo_mao_obra']:.2f}")
        print(f"   Cálculo correto: R$ {custo_correto:.2f}")
        print(f"   Diferença: R$ {diferenca:.2f}")
        
        if diferenca > 50:  # Mais de R$ 50 de diferença
            print(f"\n❌ CÁLCULO INCORRETO!")
            print(f"📝 PROBLEMA IDENTIFICADO:")
            print(f"   • Custo deveria ser R$ {custo_correto:.2f}")
            print(f"   • Sistema mostra R$ {kpis_atual['custo_mao_obra']:.2f}")
            print(f"   • Diferença de R$ {diferenca:.2f}")
            
            print(f"\n🔧 CORREÇÃO NECESSÁRIA:")
            print(f"   1. Descontar faltas do salário base")
            print(f"   2. Calcular horas extras com percentuais corretos")
            print(f"   3. Somar salário líquido + valor extras")
        else:
            print(f"\n✅ CÁLCULO ESTÁ CORRETO!")
            print(f"   Diferença menor que R$ 50")