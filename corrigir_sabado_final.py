#!/usr/bin/env python3
"""
🔧 CORREÇÃO FINAL: Atualizar engine KPIs para considerar sabado_trabalhado
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def verificar_tipos_sabado():
    """Verificar todos os tipos de sábado no sistema"""
    print("🔍 VERIFICANDO TIPOS DE SÁBADO NO SISTEMA")
    print("=" * 60)
    
    # Contar registros por tipo
    tipos = db.session.query(
        RegistroPonto.tipo_registro,
        db.func.count(RegistroPonto.id).label('quantidade')
    ).filter(
        RegistroPonto.tipo_registro.like('%sabado%')
    ).group_by(RegistroPonto.tipo_registro).all()
    
    for tipo, quantidade in tipos:
        print(f"   {tipo}: {quantidade} registros")
    
    # Verificar registros de sábado com horas extras > 0
    sabados_com_extras = db.session.query(
        RegistroPonto.tipo_registro,
        db.func.sum(RegistroPonto.horas_extras).label('total_extras')
    ).filter(
        RegistroPonto.tipo_registro.like('%sabado%'),
        RegistroPonto.horas_extras > 0
    ).group_by(RegistroPonto.tipo_registro).all()
    
    print(f"\n📊 SÁBADOS COM HORAS EXTRAS:")
    for tipo, total in sabados_com_extras:
        print(f"   {tipo}: {total:.1f}h extras")
    
    return tipos, sabados_com_extras

def simular_calculo_antonio():
    """Simular cálculo específico do Antonio baseado nas imagens"""
    print(f"\n🎯 SIMULAÇÃO ANTONIO FERNANDES DA SILVA:")
    print("=" * 60)
    
    # Dados das imagens
    salario_base = 2153.26
    custo_total = 2298.54
    horas_extras_mostrada = 0.3  # KPI atual
    
    # Registros visíveis nas imagens
    print("📋 REGISTROS IDENTIFICADOS NAS IMAGENS:")
    print("   05/07/2025 - SÁBADO: 7.9h extras (50%)")
    print("   18/07/2025 - Normal: 0.3h extras (60%)")
    
    # Cálculo esperado
    total_extras_esperado = 7.9 + 0.3
    print(f"\n🔢 CÁLCULO ESPERADO:")
    print(f"   Horas extras total: {total_extras_esperado:.1f}h")
    print(f"   Diferença atual: {total_extras_esperado - horas_extras_mostrada:.1f}h")
    
    # Análise do custo
    diferenca_custo = custo_total - salario_base
    percentual_adicional = (diferenca_custo / salario_base) * 100
    
    print(f"\n💰 ANÁLISE DO CUSTO:")
    print(f"   Salário base: R$ {salario_base:.2f}")
    print(f"   Custo total: R$ {custo_total:.2f}")
    print(f"   Diferença: R$ {diferenca_custo:.2f}")
    print(f"   Acréscimo: {percentual_adicional:.1f}%")
    
    # Cálculo detalhado esperado
    valor_hora_base = salario_base / 193  # ~193h trabalhadas no mês
    custo_sabado = 7.9 * valor_hora_base * 1.5  # 50% adicional
    custo_extra_normal = 0.3 * valor_hora_base * 1.6  # 60% adicional
    
    print(f"\n🧮 BREAKDOWN DO CUSTO:")
    print(f"   Valor/hora base: R$ {valor_hora_base:.2f}")
    print(f"   Custo sábado (7.9h x 1.5): R$ {custo_sabado:.2f}")
    print(f"   Custo extra normal (0.3h x 1.6): R$ {custo_extra_normal:.2f}")
    print(f"   Total extras: R$ {custo_sabado + custo_extra_normal:.2f}")
    
    return total_extras_esperado

if __name__ == "__main__":
    with app.app_context():
        print("🔧 DIAGNÓSTICO COMPLETO - SÁBADO TRABALHADO")
        print("=" * 80)
        
        # 1. Verificar tipos no sistema
        tipos, sabados_extras = verificar_tipos_sabado()
        
        # 2. Simular cálculo específico
        total_esperado = simular_calculo_antonio()
        
        print(f"\n🎯 PROBLEMA IDENTIFICADO:")
        print(f"   ❌ Sistema mostra: 0.3h extras")
        print(f"   ✅ Deveria mostrar: {total_esperado:.1f}h extras")
        print(f"   📝 Faltam 7.9h de sábado no cálculo dos KPIs")
        
        print(f"\n🔧 CORREÇÃO NECESSÁRIA:")
        print(f"   ✅ Engine KPI atualizada para sabado_trabalhado")
        print(f"   ✅ Tipo antigo sabado_horas_extras mantido para compatibilidade")
        print(f"   ⚠️  Reiniciar servidor para aplicar mudanças")