#!/usr/bin/env python3
"""
🔍 DEBUG: Por que os KPIs não estão calculando as horas extras de sábado
"""

from app import app, db
from models import RegistroPonto, Funcionario
from sqlalchemy import func
from datetime import date

def debug_calculo_horas_extras():
    """Debug do método _calcular_horas_extras"""
    print("🔍 DEBUG: Cálculo de Horas Extras")
    print("=" * 60)
    
    # Simular exatamente o que o método _calcular_horas_extras faz
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    # Query exata do método _calcular_horas_extras
    total = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.horas_extras.isnot(None)
    ).scalar()
    
    print(f"📊 TOTAL HORAS EXTRAS (TODOS FUNCIONÁRIOS): {total or 0:.1f}h")
    
    # Verificar registros de sábado especificamente
    sabados = db.session.query(
        RegistroPonto.data,
        RegistroPonto.tipo_registro,
        RegistroPonto.horas_trabalhadas,
        RegistroPonto.horas_extras,
        Funcionario.nome
    ).join(Funcionario).filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.horas_extras > 0
    ).all()
    
    print(f"\n📊 SÁBADOS COM HORAS EXTRAS ({len(sabados)}):")
    total_sabados = 0
    for data, tipo, trabalhadas, extras, nome in sabados:
        print(f"   {data} | {nome} | Trab: {trabalhadas:.1f}h | Extras: {extras:.1f}h")
        total_sabados += extras or 0
    
    print(f"\n📈 TOTAL SÁBADOS: {total_sabados:.1f}h")
    
    # Verificar se há registros com horas_extras = NULL
    registros_null = db.session.query(func.count(RegistroPonto.id)).filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.horas_extras.is_(None)
    ).scalar()
    
    print(f"\n⚠️  REGISTROS SÁBADO COM HORAS_EXTRAS = NULL: {registros_null}")
    
    # Verificar se há registros com horas_extras = 0
    registros_zero = db.session.query(func.count(RegistroPonto.id)).filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.horas_extras == 0
    ).scalar()
    
    print(f"⚠️  REGISTROS SÁBADO COM HORAS_EXTRAS = 0: {registros_zero}")
    
    return total or 0, total_sabados

def debug_funcionario_especifico_salario():
    """Debug tentando diferentes salários próximos"""
    print(f"\n🔍 DEBUG: Funcionários com Salários Próximos a 2153.26")
    print("=" * 60)
    
    # Buscar funcionários com salários próximos
    funcionarios = db.session.query(
        Funcionario.id,
        Funcionario.nome,
        Funcionario.salario
    ).filter(
        Funcionario.salario >= 2000,
        Funcionario.salario <= 2500
    ).all()
    
    print(f"📊 FUNCIONÁRIOS COM SALÁRIO 2000-2500:")
    for id_func, nome, salario in funcionarios:
        print(f"   {nome} | R$ {salario:.2f} | ID: {id_func}")
        
        # Verificar registros de julho para cada um
        registros = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == id_func,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).scalar()
        
        if registros > 0:
            print(f"      → {registros} registros em julho 2025")
            
            # Verificar horas extras especificamente
            extras = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
                RegistroPonto.funcionario_id == id_func,
                RegistroPonto.data >= date(2025, 7, 1),
                RegistroPonto.data <= date(2025, 7, 31),
                RegistroPonto.horas_extras.isnot(None)
            ).scalar()
            
            print(f"      → {extras or 0:.1f}h de horas extras")

def verificar_query_kpi_engine():
    """Verificar se a query do KPI engine está correta"""
    print(f"\n🤖 DEBUG: Query do KPI Engine")
    print("=" * 60)
    
    # Simular para um funcionário específico (pegar o primeiro com registros)
    funcionario = db.session.query(Funcionario).join(RegistroPonto).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).first()
    
    if not funcionario:
        print("❌ Nenhum funcionário com registros em julho encontrado")
        return
    
    print(f"👤 Testando com: {funcionario.nome} (ID: {funcionario.id})")
    
    # Query do KPI engine
    total = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar()
    
    print(f"📊 KPI Query Result: {total or 0:.1f}h")
    
    # Query detalhada
    registros = db.session.query(
        RegistroPonto.data,
        RegistroPonto.tipo_registro,
        RegistroPonto.horas_extras
    ).filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).all()
    
    print(f"\n📋 REGISTROS DETALHADOS ({len(registros)}):")
    for data, tipo, extras in registros:
        print(f"   {data} | {tipo} | {extras or 0:.1f}h")

if __name__ == "__main__":
    with app.app_context():
        print("🔍 DEBUG COMPLETO - KPIs HORAS EXTRAS SÁBADO")
        print("=" * 80)
        
        # 1. Debug do cálculo geral
        total_geral, total_sabados = debug_calculo_horas_extras()
        
        # 2. Debug por funcionário específico
        debug_funcionario_especifico_salario()
        
        # 3. Debug da query do KPI engine
        verificar_query_kpi_engine()
        
        print(f"\n🎯 RESUMO:")
        print(f"   Total horas extras sistema: {total_geral:.1f}h")
        print(f"   Total só sábados: {total_sabados:.1f}h")
        print(f"   Diferença: {total_geral - total_sabados:.1f}h")