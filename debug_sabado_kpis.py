#!/usr/bin/env python3
"""
🔍 DEBUG: Por que sábados não são contados nos KPIs?
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def investigar_problema_sabado():
    """Investigar se sábados estão sendo contados nos KPIs"""
    print("🔍 INVESTIGAÇÃO: Sábados nos KPIs")
    print("=" * 60)
    
    # Buscar funcionário Teste Completo KPIs
    func_teste = Funcionario.query.filter(Funcionario.nome.like('%Teste Completo%')).first()
    
    if not func_teste:
        print("❌ Funcionário não encontrado")
        return
    
    print(f"👤 {func_teste.nome} (ID: {func_teste.id})")
    
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
    """), {'func_id': func_teste.id}).fetchall()
    
    print(f"\n📋 SÁBADOS DO FUNCIONÁRIO ({len(sabados)}):")
    total_sabado_trabalhadas = 0
    total_sabado_extras = 0
    
    for sabado in sabados:
        print(f"   {sabado.data} | {sabado.tipo_registro} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h | "
              f"Perc: {sabado.percentual_extras or 0}%")
        total_sabado_trabalhadas += sabado.horas_trabalhadas
        total_sabado_extras += sabado.horas_extras
    
    print(f"\n📊 TOTAIS SÁBADOS:")
    print(f"   Horas Trabalhadas: {total_sabado_trabalhadas:.1f}h")
    print(f"   Horas Extras: {total_sabado_extras:.1f}h")
    
    # Testar KPI Engine
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        func_teste.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"\n🤖 KPIs CALCULADOS:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
    
    # Verificar se sábados estão sendo contados
    total_geral_extras = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == func_teste.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).scalar() or 0
    
    print(f"\n🔍 VERIFICAÇÃO:")
    print(f"   DB Total Extras: {total_geral_extras:.1f}h")
    print(f"   KPI Extras: {kpis['horas_extras']:.1f}h")
    print(f"   Sábados Extras: {total_sabado_extras:.1f}h")
    
    if abs(total_geral_extras - kpis['horas_extras']) < 0.1:
        print(f"   ✅ KPI está correto")
        if total_sabado_extras > 0:
            print(f"   ✅ Sábados estão sendo contados")
        else:
            print(f"   ⚠️  Funcionário não tem horas extras de sábado")
    else:
        print(f"   ❌ KPI não confere com DB")
    
    return func_teste, sabados, kpis

def corrigir_sabados_para_apenas_extras():
    """Zerar horas trabalhadas de sábado e deixar apenas extras"""
    print(f"\n🔧 CORREÇÃO: Sábados = 0h trabalhadas, apenas extras")
    print("=" * 60)
    
    # Buscar sábados com horas trabalhadas > 0
    sabados_trabalho = db.session.execute(text("""
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
    
    print(f"📋 CORRIGINDO {len(sabados_trabalho)} SÁBADOS:")
    
    for sabado in sabados_trabalho:
        # Mover horas trabalhadas para extras
        novas_extras = sabado.horas_trabalhadas  # No sábado, toda hora é extra
        
        db.session.execute(text("""
            UPDATE registro_ponto 
            SET horas_trabalhadas = 0,
                horas_extras = :novas_extras,
                percentual_extras = 50
            WHERE id = :reg_id
        """), {
            'novas_extras': novas_extras,
            'reg_id': sabado.id
        })
        
        print(f"   {sabado.data} | Func {sabado.funcionario_id} | "
              f"Era: {sabado.horas_trabalhadas:.1f}h trab + {sabado.horas_extras:.1f}h extras | "
              f"Agora: 0h trab + {novas_extras:.1f}h extras")
    
    db.session.commit()
    print(f"✅ {len(sabados_trabalho)} sábados corrigidos")
    
    return len(sabados_trabalho)

def testar_apos_correcao():
    """Testar KPIs após correção"""
    print(f"\n🧪 TESTE APÓS CORREÇÃO:")
    print("=" * 60)
    
    func_teste = Funcionario.query.filter(Funcionario.nome.like('%Teste Completo%')).first()
    
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        func_teste.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    # Verificar totais
    total_extras_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == func_teste.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).scalar() or 0
    
    sabados_extras = db.session.execute(text("""
        SELECT SUM(horas_extras)
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND EXTRACT(DOW FROM data) = 6
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras > 0
    """), {'func_id': func_teste.id}).scalar() or 0
    
    print(f"👤 {func_teste.nome}")
    print(f"📊 DB Total Extras: {total_extras_db:.1f}h")
    print(f"📊 Sábados Extras: {sabados_extras:.1f}h")
    print(f"🤖 KPI Extras: {kpis['horas_extras']:.1f}h")
    print(f"💰 Valor Extras: R$ {kpis['eficiencia']:.2f}")
    
    if abs(total_extras_db - kpis['horas_extras']) < 0.1:
        print(f"✅ CORREÇÃO FUNCIONOU!")
        if sabados_extras > 20:  # Esperamos ~26h de sábado
            print(f"✅ Sábados estão sendo contados ({sabados_extras:.1f}h)")
        return True
    else:
        print(f"❌ Ainda há divergência: {abs(total_extras_db - kpis['horas_extras']):.1f}h")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🔍 DEBUG - POR QUE SÁBADOS NÃO SÃO CONTADOS NOS KPIs?")
        print("=" * 80)
        
        # 1. Investigar problema
        func_teste, sabados, kpis_antes = investigar_problema_sabado()
        
        # 2. Aplicar correção se necessário
        if len(sabados) > 0 and any(s.horas_trabalhadas > 0 for s in sabados):
            sabados_corrigidos = corrigir_sabados_para_apenas_extras()
            
            # 3. Testar após correção
            sucesso = testar_apos_correcao()
            
            print(f"\n🎯 RESULTADO:")
            print(f"   Sábados corrigidos: {sabados_corrigidos}")
            print(f"   Teste pós-correção: {'✅ SUCESSO' if sucesso else '❌ FALHOU'}")
        else:
            print(f"\n⚠️  Sábados já estão no formato correto")
            print(f"   Se ainda há problema, é na lógica do KPI Engine")