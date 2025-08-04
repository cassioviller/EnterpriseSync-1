#!/usr/bin/env python3
"""
🎯 TESTE ESPECÍFICO: Funcionário com 193.0h da imagem
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def buscar_funcionario_exato():
    """Buscar funcionário com exatamente ~193h (mais próximo)"""
    print("🎯 BUSCANDO FUNCIONÁRIO ESPECÍFICO DA IMAGEM")
    print("=" * 60)
    
    # Lista todos funcionários ordenados por proximidade de 193h
    funcionarios = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras,
            COUNT(CASE WHEN EXTRACT(DOW FROM r.data) = 6 AND r.horas_extras > 0 THEN 1 END) as sabados_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome
        ORDER BY ABS(SUM(r.horas_trabalhadas) - 193.0)
        LIMIT 10
    """)).fetchall()
    
    print("👥 FUNCIONÁRIOS MAIS PRÓXIMOS DE 193.0H:")
    for i, func in enumerate(funcionarios):
        diferenca = abs(func.total_trabalhadas - 193.0)
        print(f"   {i+1}. {func.nome[:25]:<25} | "
              f"{func.total_trabalhadas:.1f}h | "
              f"Extras: {func.total_extras:.1f}h | "
              f"Sáb: {func.sabados_extras} | "
              f"Dif: {diferenca:.1f}h")
    
    return funcionarios

def testar_kpis_detalhado(funcionario):
    """Testar KPIs em detalhes"""
    print(f"\n🔍 TESTE DETALHADO: {funcionario.nome}")
    print("=" * 60)
    
    # KPI Engine
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"📊 RESULTADOS KPI:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    
    # Verificar detalhes dos registros
    detalhes = db.session.execute(text("""
        SELECT 
            tipo_registro,
            COUNT(*) as registros,
            SUM(horas_trabalhadas) as total_trab,
            SUM(horas_extras) as total_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        GROUP BY tipo_registro
        ORDER BY total_extras DESC
    """), {'func_id': funcionario.id}).fetchall()
    
    print(f"\n📋 BREAKDOWN POR TIPO:")
    for detalhe in detalhes:
        print(f"   {detalhe.tipo_registro:<20} | "
              f"{detalhe.registros:2}x | "
              f"Trab: {detalhe.total_trab:.1f}h | "
              f"Extras: {detalhe.total_extras:.1f}h")
    
    # Sábados específicos
    sabados = db.session.execute(text("""
        SELECT 
            data,
            horas_trabalhadas,
            horas_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND EXTRACT(DOW FROM data) = 6
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        ORDER BY data
    """), {'func_id': funcionario.id}).fetchall()
    
    if sabados:
        print(f"\n🗓️  SÁBADOS DETALHADOS:")
        for sabado in sabados:
            print(f"   {sabado.data} | "
                  f"Trab: {sabado.horas_trabalhadas:.1f}h | "
                  f"Extras: {sabado.horas_extras:.1f}h")
    
    return kpis

def aplicar_ultima_correcao():
    """Aplicar correção específica se necessário"""
    print(f"\n🔧 APLICANDO ÚLTIMA CORREÇÃO")
    print("=" * 60)
    
    # Verificar se ainda há sábados com problemas
    sabados_problema = db.session.execute(text("""
        SELECT COUNT(*)
        FROM registro_ponto
        WHERE tipo_registro IN ('sabado_trabalhado', 'sabado_horas_extras')
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
    """)).fetchone()[0]
    
    if sabados_problema > 0:
        print(f"❌ {sabados_problema} sábados ainda têm horas trabalhadas")
        
        # Corrigir
        db.session.execute(text("""
            UPDATE registro_ponto 
            SET horas_extras = CASE 
                WHEN horas_trabalhadas > 0 THEN horas_trabalhadas 
                ELSE horas_extras 
            END,
            horas_trabalhadas = 0,
            percentual_extras = 50
            WHERE tipo_registro IN ('sabado_trabalhado', 'sabado_horas_extras')
                AND data >= '2025-07-01' 
                AND data <= '2025-07-31'
                AND horas_trabalhadas > 0
        """))
        
        db.session.commit()
        print(f"✅ {sabados_problema} sábados corrigidos")
        return True
    else:
        print(f"✅ Todos os sábados já estão corretos")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🎯 TESTE ESPECÍFICO - FUNCIONÁRIO 193.0H")
        print("=" * 80)
        
        # 1. Buscar funcionário específico
        funcionarios = buscar_funcionario_exato()
        
        if not funcionarios:
            print("❌ Nenhum funcionário encontrado")
            exit()
        
        # 2. Testar os 3 primeiros mais próximos
        for i in range(min(3, len(funcionarios))):
            func = funcionarios[i]
            print(f"\n{'='*60}")
            print(f"TESTE {i+1}: {func.nome}")
            print(f"{'='*60}")
            
            # Aplicar correção se necessário
            if i == 0:  # Só aplicar na primeira vez
                aplicar_ultima_correcao()
            
            # Testar KPIs
            kpis = testar_kpis_detalhado(func)
            
            print(f"\n🎯 RESUMO {func.nome}:")
            print(f"   ID: {func.id}")
            print(f"   URL: /funcionarios/{func.id}/perfil")
            print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
            print(f"   Valor: R$ {kpis['eficiencia']:.2f}")
            
            # Verificar se há sábados
            if func.sabados_extras > 0:
                print(f"   ✅ Tem {func.sabados_extras} sábados com extras")
            else:
                print(f"   ⚠️  Não tem sábados extras")
        
        print(f"\n🎊 TESTE COMPLETO!")
        print(f"🔗 Teste qualquer um dos funcionários acima na interface")
        print(f"📊 Os KPIs devem mostrar as horas extras corretas agora")