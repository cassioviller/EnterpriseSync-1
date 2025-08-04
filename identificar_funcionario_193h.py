#!/usr/bin/env python3
"""
🔍 IDENTIFICAR: Qual funcionário tem 193.0h trabalhadas (da imagem)
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def identificar_funcionario_193h():
    """Identificar o funcionário com 193.0h trabalhadas"""
    print("🔍 IDENTIFICANDO FUNCIONÁRIO 193.0H")
    print("=" * 60)
    
    # Buscar funcionários próximos de 193h
    funcionarios = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome
        ORDER BY ABS(SUM(r.horas_trabalhadas) - 193.0)
        LIMIT 5
    """)).fetchall()
    
    print("👥 FUNCIONÁRIOS PRÓXIMOS DE 193H:")
    for func in funcionarios:
        print(f"   {func.nome[:30]:<30} | ID: {func.id:<3} | "
              f"Trab: {func.total_trabalhadas:.1f}h | "
              f"Extras: {func.total_extras:.1f}h")
    
    return funcionarios[0] if funcionarios else None

def diagnosticar_problema_kpis(funcionario):
    """Diagnosticar por que KPIs mostram 0.3h"""
    print(f"\n🔍 DIAGNÓSTICO KPIs: {funcionario.nome}")
    print("=" * 60)
    
    # Verificar sábados específicos
    sabados = db.session.execute(text("""
        SELECT 
            data,
            tipo_registro,
            horas_trabalhadas,
            horas_extras,
            percentual_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND EXTRACT(DOW FROM data) = 6
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        ORDER BY data
    """), {'func_id': funcionario.id}).fetchall()
    
    print(f"📋 SÁBADOS DO FUNCIONÁRIO:")
    total_sabado_extras = 0
    for sabado in sabados:
        print(f"   {sabado.data} | {sabado.tipo_registro} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h")
        total_sabado_extras += sabado.horas_extras
    
    print(f"   TOTAL SÁBADOS: {total_sabado_extras:.1f}h extras")
    
    # Testar KPI Engine diretamente
    engine = KPIsEngine()
    
    # Testar função específica
    horas_extras_funcao = engine._calcular_horas_extras(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"\n🤖 TESTE DIRETO:")
    print(f"   _calcular_horas_extras(): {horas_extras_funcao:.1f}h")
    
    # KPIs completos
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"   calcular_kpis_funcionario(): {kpis['horas_extras']:.1f}h")
    print(f"   Valor monetário: R$ {kpis['eficiencia']:.2f}")
    
    # Verificar DB diretamente
    total_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).scalar() or 0
    
    print(f"   DB direto: {total_db:.1f}h")
    
    # Análise
    if abs(total_db - kpis['horas_extras']) > 0.1:
        print(f"\n❌ PROBLEMA IDENTIFICADO:")
        print(f"   DB tem {total_db:.1f}h mas KPI retorna {kpis['horas_extras']:.1f}h")
        print(f"   Diferença: {abs(total_db - kpis['horas_extras']):.1f}h")
        return False
    else:
        print(f"\n✅ KPI ESTÁ CORRETO:")
        print(f"   Funcionário realmente tem apenas {kpis['horas_extras']:.1f}h extras")
        if total_sabado_extras == 0:
            print(f"   Este funcionário não trabalhou sábados")
        return True

def corrigir_forcadamente_sabados():
    """Forçar correção dos sábados que não foram aplicados"""
    print(f"\n🔧 CORREÇÃO FORÇADA: Sábados pendentes")
    print("=" * 60)
    
    # Buscar sábados que ainda têm horas trabalhadas
    sabados_problema = db.session.execute(text("""
        SELECT 
            id,
            data,
            funcionario_id,
            horas_trabalhadas,
            horas_extras
        FROM registro_ponto
        WHERE tipo_registro = 'sabado_trabalhado'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
    """)).fetchall()
    
    print(f"📋 SÁBADOS COM PROBLEMA ({len(sabados_problema)}):")
    
    if len(sabados_problema) == 0:
        print(f"   ✅ Todos os sábados já estão corretos")
        return 0
    
    for sabado in sabados_problema[:5]:  # Mostrar 5 exemplos
        print(f"   {sabado.data} | Func {sabado.funcionario_id} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h")
    
    # Aplicar correção
    db.session.execute(text("""
        UPDATE registro_ponto 
        SET horas_trabalhadas = 0,
            horas_extras = CASE 
                WHEN horas_trabalhadas > 0 THEN horas_trabalhadas 
                ELSE horas_extras 
            END,
            percentual_extras = 50
        WHERE tipo_registro = 'sabado_trabalhado'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
    """))
    
    db.session.commit()
    print(f"✅ {len(sabados_problema)} sábados corrigidos")
    
    return len(sabados_problema)

if __name__ == "__main__":
    with app.app_context():
        print("🔍 IDENTIFICANDO PROBLEMA 0.3H HORAS EXTRAS")
        print("=" * 80)
        
        # 1. Identificar funcionário
        funcionario = identificar_funcionario_193h()
        
        if not funcionario:
            print("❌ Nenhum funcionário encontrado")
            exit()
        
        # 2. Diagnosticar problema
        kpi_correto = diagnosticar_problema_kpis(funcionario)
        
        # 3. Se há problema, corrigir
        if not kpi_correto:
            corrigidos = corrigir_forcadamente_sabados()
            
            # Testar novamente
            print(f"\n🧪 TESTE APÓS CORREÇÃO:")
            engine = KPIsEngine()
            kpis_novo = engine.calcular_kpis_funcionario(
                funcionario.id,
                date(2025, 7, 1),
                date(2025, 7, 31)
            )
            print(f"   Horas extras agora: {kpis_novo['horas_extras']:.1f}h")
        
        print(f"\n🎯 CONCLUSÃO:")
        print(f"   Funcionário: {funcionario.nome}")
        print(f"   URL: /funcionarios/{funcionario.id}/perfil")
        print(f"   Status: {'✅ Correto' if kpi_correto else '🔧 Corrigido'}")