#!/usr/bin/env python3
"""
🧪 TESTE: KPIs usando funcionário existente para simular problema do Antonio
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import date, datetime

def testar_com_funcionario_existente():
    """Usar funcionário existente e adicionar registros de sábado"""
    print("🧪 TESTE COM FUNCIONÁRIO EXISTENTE")
    print("=" * 60)
    
    # Pegar primeiro funcionário ativo
    funcionario = Funcionario.query.filter_by(ativo=True).first()
    if not funcionario:
        print("❌ Nenhum funcionário ativo encontrado")
        return
    
    print(f"👤 Usando: {funcionario.nome} (ID: {funcionario.id})")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    
    # Limpar registros de julho 2025
    RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).delete()
    
    print(f"\n📊 CRIANDO REGISTROS DE TESTE:")
    
    # Criar registros similares ao caso do Antonio
    registros_teste = [
        # Registro normal com 0.3h extras
        {
            'data': date(2025, 7, 15),
            'tipo': 'trabalho_normal',
            'trabalhadas': 8.3,
            'extras': 0.3
        },
        # Primeiro sábado - 8.0h
        {
            'data': date(2025, 7, 5),  # Sábado
            'tipo': 'sabado_trabalhado',
            'trabalhadas': 8.0,
            'extras': 8.0
        },
        # Segundo sábado - 7.9h  
        {
            'data': date(2025, 7, 12),  # Sábado
            'tipo': 'sabado_trabalhado',
            'trabalhadas': 7.9,
            'extras': 7.9
        }
    ]
    
    total_esperado = 0
    for reg in registros_teste:
        registro = RegistroPonto(
            funcionario_id=funcionario.id,
            data=reg['data'],
            tipo_registro=reg['tipo'],
            horas_trabalhadas=reg['trabalhadas'],
            horas_extras=reg['extras'],
            percentual_extras=50.0 if 'sabado' in reg['tipo'] else 60.0,
            entrada=datetime.combine(reg['data'], datetime.min.time().replace(hour=7)),
            saida=datetime.combine(reg['data'], datetime.min.time().replace(hour=15, minute=30))
        )
        db.session.add(registro)
        total_esperado += reg['extras']
        
        print(f"   {reg['data']} | {reg['tipo']} | {reg['extras']:.1f}h extras")
    
    db.session.commit()
    print(f"\n📈 TOTAL ESPERADO: {total_esperado:.1f}h")
    
    return funcionario, total_esperado

def verificar_kpis(funcionario, total_esperado):
    """Calcular e verificar KPIs"""
    print(f"\n🤖 CALCULANDO KPIs")
    print("=" * 60)
    
    engine = KPIsEngine()
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    kpis = engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    print(f"📊 RESULTADO:")
    print(f"   Horas Extras (KPI): {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    print(f"   Total Esperado: {total_esperado:.1f}h")
    
    diferenca = abs(kpis['horas_extras'] - total_esperado)
    if diferenca < 0.1:
        print(f"\n✅ TESTE PASSOU: Sistema calcula corretamente!")
    else:
        print(f"\n❌ TESTE FALHOU: Diferença de {diferenca:.1f}h")
        print(f"   Sistema mostra: {kpis['horas_extras']:.1f}h")
        print(f"   Deveria mostrar: {total_esperado:.1f}h")
    
    return kpis

def verificar_query_kpis(funcionario_id):
    """Verificar query SQL que o KPI usa"""
    print(f"\n🔍 VERIFICANDO QUERY SQL")
    print("=" * 60)
    
    # Mesma query que _calcular_horas_extras usa
    from sqlalchemy import func
    total = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar()
    
    print(f"📊 QUERY SQL DIRETA: {total or 0:.1f}h")
    
    # Verificar todos os registros
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).all()
    
    print(f"\n📋 REGISTROS INDIVIDUAIS ({len(registros)}):")
    for reg in registros:
        print(f"   {reg.data} | {reg.tipo_registro} | "
              f"Extras: {reg.horas_extras:.1f}h | "
              f"NULL: {'Sim' if reg.horas_extras is None else 'Não'}")
    
    return total or 0

if __name__ == "__main__":
    with app.app_context():
        print("🧪 TESTE COMPLETO - PROBLEMA KPIs SÁBADO")
        print("=" * 80)
        
        # 1. Criar teste com funcionário existente
        funcionario, total_esperado = testar_com_funcionario_existente()
        
        # 2. Verificar query SQL direta
        total_sql = verificar_query_kpis(funcionario.id)
        
        # 3. Testar KPIs
        kpis = verificar_kpis(funcionario, total_esperado)
        
        print(f"\n🎯 DIAGNÓSTICO FINAL:")
        print(f"   Esperado: {total_esperado:.1f}h")
        print(f"   SQL direto: {total_sql:.1f}h")
        print(f"   KPI resultado: {kpis['horas_extras']:.1f}h")
        
        if total_sql == total_esperado == kpis['horas_extras']:
            print(f"\n✅ SISTEMA FUNCIONANDO PERFEITAMENTE!")
            print(f"   Problema no ambiente de produção é diferente")
        else:
            print(f"\n❌ PROBLEMA IDENTIFICADO NO SISTEMA")