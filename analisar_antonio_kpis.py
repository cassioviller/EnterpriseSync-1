#!/usr/bin/env python3
"""
🔍 ANÁLISE ESPECÍFICA: Antonio Fernandes da Silva
Investigar problemas nos cálculos de KPIs e custo
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def analisar_antonio():
    """Análise detalhada do Antonio"""
    print("🔍 ANÁLISE ANTONIO FERNANDES DA SILVA")
    print("=" * 60)
    
    # Buscar o funcionário
    funcionario = Funcionario.query.filter(
        Funcionario.nome.ilike('%antonio%fernandes%')
    ).first()
    
    if not funcionario:
        # Buscar por salário específico
        funcionario = Funcionario.query.filter(
            Funcionario.salario == 2153.26
        ).first()
    
    if not funcionario:
        print("❌ Funcionário não encontrado!")
        return
    
    print(f"👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    
    # Período de julho 2025
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    # Buscar registros de ponto
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data).all()
    
    print(f"\n📊 REGISTROS DE JULHO 2025 ({len(registros)} registros):")
    
    total_horas_trabalhadas = 0
    total_horas_extras = 0
    sab_horas_extras = 0
    dom_horas_extras = 0
    
    for registro in registros:
        print(f"   {registro.data} | {registro.tipo_registro} | "
              f"Trab: {registro.horas_trabalhadas:.1f}h | "
              f"Extras: {registro.horas_extras:.1f}h")
        
        if registro.horas_trabalhadas:
            total_horas_trabalhadas += registro.horas_trabalhadas
        
        if registro.horas_extras:
            total_horas_extras += registro.horas_extras
            
        # Identificar sábados
        if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
            sab_horas_extras += registro.horas_extras or 0
            
        # Identificar domingos  
        if registro.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras']:
            dom_horas_extras += registro.horas_extras or 0
    
    print(f"\n📈 TOTAIS CALCULADOS:")
    print(f"   Horas Trabalhadas: {total_horas_trabalhadas:.1f}h")
    print(f"   Horas Extras TOTAL: {total_horas_extras:.1f}h")
    print(f"   ↳ Sábado: {sab_horas_extras:.1f}h")
    print(f"   ↳ Domingo: {dom_horas_extras:.1f}h")
    
    # Calcular KPIs usando engine
    print(f"\n🤖 KPIs DO SISTEMA:")
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    print(f"   Horas Trabalhadas (Sistema): {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras (Sistema): {kpis['horas_extras']:.1f}h")
    print(f"   Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
    
    # Analisar diferença esperada vs sistema
    print(f"\n🔍 ANÁLISE DE DIFERENÇAS:")
    if abs(total_horas_extras - kpis['horas_extras']) > 0.1:
        print(f"   ❌ DIFERENÇA EM HORAS EXTRAS:")
        print(f"      Esperado: {total_horas_extras:.1f}h")
        print(f"      Sistema: {kpis['horas_extras']:.1f}h")
        print(f"      Diferença: {total_horas_extras - kpis['horas_extras']:.1f}h")
    else:
        print(f"   ✅ Horas extras estão corretas")
    
    # Analisar custo
    print(f"\n💰 ANÁLISE DO CUSTO:")
    print(f"   Salário base: R$ {funcionario.salario:.2f}")
    print(f"   Custo total: R$ {kpis['custo_mao_obra']:.2f}")
    print(f"   Diferença: R$ {kpis['custo_mao_obra'] - funcionario.salario:.2f}")
    
    diferenca_percentual = ((kpis['custo_mao_obra'] - funcionario.salario) / funcionario.salario) * 100
    print(f"   Acréscimo: {diferenca_percentual:.1f}%")
    
    return funcionario, kpis, registros

if __name__ == "__main__":
    with app.app_context():
        analisar_antonio()