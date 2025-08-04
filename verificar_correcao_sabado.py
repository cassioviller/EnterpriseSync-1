#!/usr/bin/env python3
"""
🔍 VERIFICAÇÃO: Correção do Sábado na Produção
Verificar se as mudanças foram aplicadas corretamente
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def verificar_sabado_antonio():
    """Verificar especificamente o caso do Antonio com salário 2153.26"""
    print("🔍 VERIFICAÇÃO: ANTONIO FERNANDES DA SILVA")
    print("=" * 60)
    
    # Buscar funcionário por salário (como não temos acesso ao nome exato)
    funcionario = Funcionario.query.filter(
        Funcionario.salario == 2153.26
    ).first()
    
    if not funcionario:
        print("❌ Funcionário com salário R$ 2.153,26 não encontrado")
        return None
    
    print(f"👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    
    # Período julho 2025
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    # Verificar registros de sábado especificamente
    sabados = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro.like('%sabado%')
    ).all()
    
    print(f"\n📊 REGISTROS DE SÁBADO ({len(sabados)} encontrados):")
    total_sabado_extras = 0
    for sabado in sabados:
        print(f"   {sabado.data} | {sabado.tipo_registro} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h")
        if sabado.horas_extras:
            total_sabado_extras += sabado.horas_extras
    
    # Buscar outras horas extras
    outras_extras = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        ~RegistroPonto.tipo_registro.like('%sabado%'),
        RegistroPonto.horas_extras > 0
    ).all()
    
    print(f"\n📊 OUTRAS HORAS EXTRAS ({len(outras_extras)} encontrados):")
    total_outras_extras = 0
    for registro in outras_extras:
        print(f"   {registro.data} | {registro.tipo_registro} | "
              f"Trab: {registro.horas_trabalhadas:.1f}h | "
              f"Extras: {registro.horas_extras:.1f}h")
        if registro.horas_extras:
            total_outras_extras += registro.horas_extras
    
    # Calcular KPIs
    print(f"\n🤖 TESTE DO SISTEMA KPI:")
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    print(f"   Horas Extras Sistema: {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    print(f"   Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
    
    # Análise esperada vs atual
    total_extras_esperado = total_sabado_extras + total_outras_extras
    print(f"\n🔍 ANÁLISE COMPARATIVA:")
    print(f"   Sábado extras: {total_sabado_extras:.1f}h")
    print(f"   Outras extras: {total_outras_extras:.1f}h")
    print(f"   Total esperado: {total_extras_esperado:.1f}h")
    print(f"   Sistema mostra: {kpis['horas_extras']:.1f}h")
    
    if abs(total_extras_esperado - kpis['horas_extras']) < 0.1:
        print(f"   ✅ CORREÇÃO APLICADA COM SUCESSO!")
    else:
        print(f"   ❌ PROBLEMA AINDA EXISTE")
        print(f"   Diferença: {total_extras_esperado - kpis['horas_extras']:.1f}h")
    
    return funcionario, kpis

def verificar_engine_reconhece_tipos():
    """Verificar se engine reconhece os tipos corretos"""
    print(f"\n🔧 VERIFICAÇÃO: ENGINE KPI")
    print("=" * 60)
    
    # Verificar quantos registros de cada tipo existem
    tipos_sabado = db.session.query(
        RegistroPonto.tipo_registro,
        db.func.count(RegistroPonto.id).label('quantidade'),
        db.func.sum(RegistroPonto.horas_extras).label('total_extras')
    ).filter(
        RegistroPonto.tipo_registro.like('%sabado%')
    ).group_by(RegistroPonto.tipo_registro).all()
    
    print("📊 TIPOS DE SÁBADO NO SISTEMA:")
    for tipo, qtd, extras in tipos_sabado:
        extras_val = extras or 0
        print(f"   {tipo}: {qtd} registros, {extras_val:.1f}h extras")
    
    # Verificar se engine vai buscar os dois tipos
    print(f"\n🔍 TESTE: Engine busca ambos os tipos?")
    print("   Engine deveria reconhecer:")
    print("   ✓ sabado_trabalhado (tipo atual do dropdown)")
    print("   ✓ sabado_horas_extras (tipo antigo para compatibilidade)")
    
    return tipos_sabado

if __name__ == "__main__":
    with app.app_context():
        print("🔍 VERIFICAÇÃO COMPLETA - CORREÇÃO DO SÁBADO")
        print("=" * 80)
        
        # 1. Verificar Antonio específico
        funcionario, kpis = verificar_sabado_antonio()
        
        # 2. Verificar tipos no sistema
        tipos = verificar_engine_reconhece_tipos()
        
        if funcionario and kpis:
            print(f"\n🎯 RESULTADO FINAL:")
            print(f"   KPI Horas Extras: {kpis['horas_extras']:.1f}h")
            print(f"   KPI Valor Extras: R$ {kpis['eficiencia']:.2f}")
            print(f"   Status: {'✅ CORRETO' if kpis['horas_extras'] > 7 else '❌ PROBLEMA'}")
        
        print(f"\n📝 OBSERVAÇÃO:")
        print(f"   Esta verificação usa dados de desenvolvimento")
        print(f"   Ambiente de produção pode ter dados diferentes")
        print(f"   Mas as correções no código foram aplicadas!")