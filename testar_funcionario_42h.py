#!/usr/bin/env python3
"""
🎯 TESTE: Funcionário com 42h extras para confirmar se o sistema funciona
"""

from app import app, db
from models import Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def testar_funcionario_com_extras():
    """Testar funcionário 'Teste Completo KPIs' que tem 42h extras"""
    print("🎯 TESTE: Funcionário 'Teste Completo KPIs'")
    print("=" * 50)
    
    funcionario = Funcionario.query.filter(Funcionario.nome.like('%Teste Completo%')).first()
    
    if not funcionario:
        print("❌ Funcionário não encontrado")
        return
    
    print(f"👤 {funcionario.nome} (ID: {funcionario.id})")
    
    # KPIs completos
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"\n📊 DASHBOARD SIMULADO:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")  # Deve ser 42.0h
    print(f"   Faltas: {kpis['faltas']}")
    print(f"   Atrasos: {kpis['atrasos_horas']:.2f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    print(f"   Custo Total: R$ {kpis['custo_total']:.2f}")
    
    if kpis['horas_extras'] >= 40:
        print(f"\n✅ SISTEMA FUNCIONANDO!")
        print(f"   Este funcionário mostra {kpis['horas_extras']:.1f}h extras")
        print(f"   URL: /funcionarios/{funcionario.id}/perfil")
    else:
        print(f"\n❌ PROBLEMA PERSISTE!")
        print(f"   Deveria mostrar ~42h mas mostra {kpis['horas_extras']:.1f}h")
    
    return funcionario, kpis

if __name__ == "__main__":
    with app.app_context():
        funcionario, kpis = testar_funcionario_com_extras()
        
        print(f"\n🔗 TESTE NO NAVEGADOR:")
        print(f"   Acesse: /funcionarios/{funcionario.id}/perfil")
        print(f"   Deve mostrar: {kpis['horas_extras']:.1f}h extras")