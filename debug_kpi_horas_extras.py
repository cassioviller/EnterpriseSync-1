#!/usr/bin/env python3
"""
🔍 DEBUG: Investigar por que não está somando as 7.9h de sábado
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def debug_funcionario_especifico():
    """Debug do funcionário que aparece na imagem (193.0h trabalhadas, 0.3h extras)"""
    print("🔍 DEBUG: Funcionário da Imagem")
    print("=" * 60)
    
    # Buscar funcionário com ~193h trabalhadas
    funcionario = db.session.execute(text("""
        SELECT 
            f.id, 
            f.nome, 
            f.salario,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras,
            COUNT(r.id) as registros
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        HAVING SUM(r.horas_trabalhadas) BETWEEN 190 AND 200
        ORDER BY total_trabalhadas DESC
        LIMIT 1
    """)).fetchone()
    
    if not funcionario:
        print("❌ Funcionário não encontrado")
        return None
    
    print(f"👤 Funcionário: {funcionario.nome}")
    print(f"🆔 ID: {funcionario.id}")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    print(f"📊 Horas Trabalhadas: {funcionario.total_trabalhadas:.1f}h")
    print(f"⚡ Horas Extras (DB): {funcionario.total_extras:.1f}h")
    
    return funcionario

def debug_query_kpi_engine(funcionario_id):
    """Debug da query do KPI engine"""
    print(f"\n🔍 DEBUG: Query KPI Engine")
    print("=" * 60)
    
    # Reproduzir a query exata do KPI engine
    total_kpi = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None),
        RegistroPonto.horas_extras > 0  # Esta linha pode ser o problema!
    ).scalar()
    
    print(f"📊 Query KPI (com horas_extras > 0): {total_kpi or 0:.1f}h")
    
    # Testar sem o filtro > 0
    total_sem_filtro = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar()
    
    print(f"📊 Query SEM filtro > 0: {total_sem_filtro or 0:.1f}h")
    
    # Listar todos os registros com horas_extras
    registros = db.session.execute(text("""
        SELECT 
            data,
            tipo_registro,
            horas_trabalhadas,
            horas_extras,
            percentual_extras,
            EXTRACT(DOW FROM data) as dia_semana
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras IS NOT NULL
        ORDER BY data
    """), {'func_id': funcionario_id}).fetchall()
    
    print(f"\n📋 REGISTROS COM HORAS_EXTRAS ({len(registros)}):")
    for reg in registros:
        dia_nome = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'][int(reg.dia_semana)]
        print(f"   {reg.data} ({dia_nome}) | {reg.tipo_registro} | "
              f"Trab: {reg.horas_trabalhadas:.1f}h | "
              f"Extras: {reg.horas_extras:.1f}h | "
              f"Perc: {reg.percentual_extras or 0:.0f}%")
    
    # Verificar se há registros com horas_extras = 0
    registros_zero = db.session.execute(text("""
        SELECT COUNT(*) as count
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras = 0
    """), {'func_id': funcionario_id}).fetchone()
    
    print(f"\n⚠️  REGISTROS COM HORAS_EXTRAS = 0: {registros_zero.count}")
    
    return total_kpi, total_sem_filtro

def debug_calcular_kpi_real(funcionario_id):
    """Debug do cálculo real do KPI"""
    print(f"\n🧪 DEBUG: Cálculo Real do KPI")
    print("=" * 60)
    
    try:
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(
            funcionario_id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"📊 RESULTADO KPI ENGINE:")
        print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
        
        return kpis
        
    except Exception as e:
        print(f"❌ ERRO no KPI Engine: {e}")
        import traceback
        traceback.print_exc()
        return None

def debug_sabados_especificos(funcionario_id):
    """Debug específico dos sábados"""
    print(f"\n🔍 DEBUG: Sábados Específicos")
    print("=" * 60)
    
    sabados = db.session.execute(text("""
        SELECT 
            data,
            tipo_registro,
            horas_trabalhadas,
            horas_extras,
            percentual_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND EXTRACT(DOW FROM data) = 6  -- Sábado
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        ORDER BY data
    """), {'func_id': funcionario_id}).fetchall()
    
    print(f"📋 SÁBADOS ENCONTRADOS ({len(sabados)}):")
    total_sabados = 0
    for sabado in sabados:
        print(f"   {sabado.data} | {sabado.tipo_registro} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h")
        total_sabados += sabado.horas_extras or 0
    
    print(f"📊 TOTAL SÁBADOS: {total_sabados:.1f}h")
    
    if total_sabados == 0:
        print("❌ PROBLEMA: Nenhuma hora extra de sábado!")
    else:
        print("✅ Sábados têm horas extras registradas")
    
    return total_sabados

def corrigir_filtro_kpi():
    """Corrigir o filtro problemático no KPI engine"""
    print(f"\n🔧 CORREÇÃO: Remover filtro > 0 problemático")
    print("=" * 60)
    
    # Ler o arquivo atual
    with open('kpis_engine.py', 'r') as f:
        content = f.read()
    
    # Verificar se tem o filtro problemático
    if 'RegistroPonto.horas_extras > 0' in content:
        print("⚠️  FILTRO PROBLEMÁTICO ENCONTRADO!")
        print("   Linha: RegistroPonto.horas_extras > 0")
        print("   Problema: Pode estar excluindo registros válidos")
        return True
    else:
        print("✅ Filtro não encontrado no código atual")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🔍 DEBUG COMPLETO - HORAS EXTRAS NÃO SOMANDO")
        print("=" * 80)
        
        # 1. Encontrar funcionário da imagem
        funcionario = debug_funcionario_especifico()
        
        if funcionario:
            # 2. Debug da query
            total_kpi, total_sem_filtro = debug_query_kpi_engine(funcionario.id)
            
            # 3. Debug do KPI real
            kpis = debug_calcular_kpi_real(funcionario.id)
            
            # 4. Debug dos sábados
            total_sabados = debug_sabados_especificos(funcionario.id)
            
            # 5. Verificar filtro problemático
            tem_filtro_problema = corrigir_filtro_kpi()
            
            print(f"\n🎯 DIAGNÓSTICO:")
            print(f"   Horas extras no DB: {funcionario.total_extras:.1f}h")
            print(f"   Horas extras KPI: {kpis['horas_extras']:.1f}h" if kpis else "N/A")
            print(f"   Sábados: {total_sabados:.1f}h")
            print(f"   Filtro problemático: {'❌ SIM' if tem_filtro_problema else '✅ NÃO'}")
            
            if funcionario.total_extras > kpis['horas_extras'] if kpis else 0:
                print(f"\n❌ PROBLEMA CONFIRMADO:")
                print(f"   O KPI está perdendo {funcionario.total_extras - (kpis['horas_extras'] if kpis else 0):.1f}h")
                print(f"   Possível causa: Filtro RegistroPonto.horas_extras > 0")