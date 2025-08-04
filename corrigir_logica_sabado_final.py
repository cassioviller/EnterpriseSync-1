#!/usr/bin/env python3
"""
🔧 CORREÇÃO DEFINITIVA: Lógica de Sábado nas Horas Extras
O problema é que sábados estão indo para horas_trabalhadas mas não para horas_extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, datetime
from sqlalchemy import text

def analisar_problema_sabado():
    """Analisar especificamente o problema do sábado"""
    print("🔍 ANÁLISE: Problema do Sábado")
    print("=" * 60)
    
    # Buscar todos os registros de julho que são sábados
    registros_sabado = db.session.execute(text("""
        SELECT 
            r.data,
            r.tipo_registro,
            r.horas_trabalhadas,
            r.horas_extras,
            f.nome,
            EXTRACT(DOW FROM r.data) as dia_semana
        FROM registro_ponto r
        JOIN funcionario f ON r.funcionario_id = f.id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND EXTRACT(DOW FROM r.data) = 6  -- Sábado
            AND r.horas_trabalhadas > 0
        ORDER BY r.data, f.nome
    """)).fetchall()
    
    print(f"📊 SÁBADOS COM HORAS TRABALHADAS: {len(registros_sabado)}")
    
    total_trabalhadas_sabado = 0
    total_extras_sabado = 0
    
    for reg in registros_sabado[:15]:  # Mostrar primeiros 15
        print(f"   {reg.data} | {reg.nome[:20]}... | "
              f"Tipo: {reg.tipo_registro} | "
              f"Trab: {reg.horas_trabalhadas:.1f}h | "
              f"Extras: {reg.horas_extras or 0:.1f}h")
        
        total_trabalhadas_sabado += reg.horas_trabalhadas or 0
        total_extras_sabado += reg.horas_extras or 0
    
    if len(registros_sabado) > 15:
        print(f"   ... e mais {len(registros_sabado) - 15} registros")
    
    print(f"\n📈 TOTAIS DOS SÁBADOS:")
    print(f"   Horas Trabalhadas: {total_trabalhadas_sabado:.1f}h")
    print(f"   Horas Extras: {total_extras_sabado:.1f}h")
    print(f"   PROBLEMA: {total_trabalhadas_sabado - total_extras_sabado:.1f}h não contabilizadas como extras")
    
    return registros_sabado

def corrigir_sabados_definitivo():
    """Aplicar correção definitiva nos sábados"""
    print(f"\n🔧 CORREÇÃO DEFINITIVA: Sábados")
    print("=" * 60)
    
    # Estratégia 1: Corrigir por tipo de registro
    resultado1 = db.session.execute(text("""
        UPDATE registro_ponto 
        SET horas_extras = horas_trabalhadas,
            percentual_extras = 50.0
        WHERE tipo_registro IN ('sabado_trabalhado', 'sabado_horas_extras')
            AND horas_trabalhadas > 0
            AND (horas_extras IS NULL OR horas_extras < horas_trabalhadas)
    """))
    
    print(f"✅ Correção por tipo: {resultado1.rowcount} registros atualizados")
    
    # Estratégia 2: Corrigir por dia da semana (sábados)
    resultado2 = db.session.execute(text("""
        UPDATE registro_ponto 
        SET horas_extras = horas_trabalhadas,
            percentual_extras = 50.0,
            tipo_registro = 'sabado_trabalhado'
        WHERE EXTRACT(DOW FROM data) = 6  -- Sábado
            AND horas_trabalhadas > 0
            AND (horas_extras IS NULL OR horas_extras < horas_trabalhadas)
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """))
    
    print(f"✅ Correção por dia da semana: {resultado2.rowcount} registros atualizados")
    
    # Commit das mudanças
    db.session.commit()
    
    return resultado1.rowcount + resultado2.rowcount

def verificar_correcao():
    """Verificar se a correção funcionou"""
    print(f"\n✅ VERIFICAÇÃO: Pós-Correção")
    print("=" * 60)
    
    # Verificar totais após correção
    resultado = db.session.execute(text("""
        SELECT 
            COUNT(*) as total_registros,
            SUM(horas_trabalhadas) as total_trabalhadas,
            SUM(horas_extras) as total_extras
        FROM registro_ponto
        WHERE data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
    """)).fetchone()
    
    print(f"📊 TOTAIS PÓS-CORREÇÃO:")
    print(f"   Registros: {resultado.total_registros}")
    print(f"   Horas Trabalhadas: {resultado.total_trabalhadas:.1f}h")
    print(f"   Horas Extras: {resultado.total_extras:.1f}h")
    
    # Verificar sábados especificamente
    sabados = db.session.execute(text("""
        SELECT 
            COUNT(*) as total_sabados,
            SUM(horas_trabalhadas) as trab_sabados,
            SUM(horas_extras) as extras_sabados
        FROM registro_ponto
        WHERE EXTRACT(DOW FROM data) = 6
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
    """)).fetchone()
    
    print(f"\n📊 SÁBADOS PÓS-CORREÇÃO:")
    print(f"   Registros: {sabados.total_sabados}")
    print(f"   Horas Trabalhadas: {sabados.trab_sabados:.1f}h")
    print(f"   Horas Extras: {sabados.extras_sabados:.1f}h")
    
    if abs((sabados.trab_sabados or 0) - (sabados.extras_sabados or 0)) < 0.1:
        print(f"✅ CORREÇÃO APLICADA COM SUCESSO!")
    else:
        print(f"❌ AINDA HÁ DIVERGÊNCIA")
    
    return resultado

def testar_kpi_especifico():
    """Testar KPI com funcionário específico"""
    print(f"\n🧪 TESTE: KPI Específico")
    print("=" * 60)
    
    # Pegar funcionário com mais registros
    funcionario = db.session.execute(text("""
        SELECT f.id, f.nome, f.salario, COUNT(r.id) as num_registros
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        ORDER BY num_registros DESC
        LIMIT 1
    """)).fetchone()
    
    if not funcionario:
        print("❌ Nenhum funcionário encontrado")
        return
    
    print(f"👤 Testando: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    print(f"📊 Registros: {funcionario.num_registros}")
    
    # Calcular KPIs
    from kpis_engine import KPIsEngine
    engine = KPIsEngine()
    
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id, 
        date(2025, 7, 1), 
        date(2025, 7, 31)
    )
    
    print(f"\n📊 RESULTADO KPI:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    
    # Verificar registros manuais
    registros = db.session.execute(text("""
        SELECT SUM(horas_trabalhadas) as trab, SUM(horas_extras) as extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """), {'func_id': funcionario.id}).fetchone()
    
    print(f"\n📊 VERIFICAÇÃO MANUAL:")
    print(f"   Horas Trabalhadas: {registros.trab:.1f}h")
    print(f"   Horas Extras: {registros.extras:.1f}h")
    
    if abs(kpis['horas_extras'] - (registros.extras or 0)) < 0.1:
        print(f"✅ KPI ESTÁ CORRETO!")
    else:
        print(f"❌ KPI TEM DIVERGÊNCIA")

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO DEFINITIVA - LÓGICA SÁBADO")
        print("=" * 80)
        
        # 1. Analisar o problema
        registros_problema = analisar_problema_sabado()
        
        # 2. Aplicar correção
        corrigidos = corrigir_sabados_definitivo()
        
        # 3. Verificar resultado
        resultado = verificar_correcao()
        
        # 4. Testar KPI
        testar_kpi_especifico()
        
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Registros corrigidos: {corrigidos}")
        print(f"   Total horas extras: {resultado.total_extras:.1f}h")
        print(f"   Reinicie o servidor para ver as mudanças")