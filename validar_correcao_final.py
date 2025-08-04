#!/usr/bin/env python3
"""
✅ VALIDAÇÃO FINAL: Verificar se a correção dos sábados foi aplicada
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def validar_correcao_sabados():
    """Validar se todos os sábados foram corrigidos"""
    print("✅ VALIDAÇÃO: Correção dos Sábados")
    print("=" * 60)
    
    # 1. Verificar se ainda há sábados com problema
    problemas = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.horas_trabalhadas > 0,
        (RegistroPonto.horas_extras == 0) | (RegistroPonto.horas_extras.is_(None))
    ).count()
    
    print(f"📊 SÁBADOS COM PROBLEMA: {problemas}")
    
    if problemas > 0:
        print("❌ AINDA HÁ REGISTROS COM PROBLEMA")
        return False
    else:
        print("✅ TODOS OS SÁBADOS ESTÃO CORRETOS")
    
    # 2. Verificar total de horas extras de sábado
    from sqlalchemy import func
    total_sabados = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"📈 TOTAL HORAS EXTRAS SÁBADO: {total_sabados:.1f}h")
    
    return problemas == 0

def testar_funcionario_salario_alto():
    """Testar com funcionário de salário mais alto que temos"""
    print(f"\n🧪 TESTE: Funcionário Salário Alto")
    print("=" * 60)
    
    # Buscar funcionário com salário entre 2000-2500 (mais próximo do Antonio)
    funcionario = Funcionario.query.filter(
        Funcionario.salario >= 2000,
        Funcionario.salario <= 2500
    ).first()
    
    if not funcionario:
        # Se não houver, pegar o de maior salário
        funcionario = Funcionario.query.order_by(Funcionario.salario.desc()).first()
    
    if not funcionario:
        print("❌ Nenhum funcionário encontrado")
        return
    
    print(f"👤 Testando: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    
    # Calcular KPIs
    engine = KPIsEngine()
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    kpis = engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    print(f"\n📊 KPIS CALCULADOS:")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    
    # Verificar registros de sábado deste funcionário
    sabados = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    print(f"\n📋 SÁBADOS DO FUNCIONÁRIO ({len(sabados)}):")
    total_sabados_func = 0
    for sabado in sabados:
        print(f"   {sabado.data} | Trab: {sabado.horas_trabalhadas:.1f}h | Extras: {sabado.horas_extras:.1f}h")
        total_sabados_func += sabado.horas_extras or 0
    
    print(f"\n📈 TOTAL SÁBADOS FUNCIONÁRIO: {total_sabados_func:.1f}h")
    
    # Verificar se há outras horas extras
    outras_extras = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro != 'sabado_trabalhado',
        RegistroPonto.horas_extras > 0
    ).all()
    
    total_outras = sum(reg.horas_extras or 0 for reg in outras_extras)
    print(f"📈 OUTRAS HORAS EXTRAS: {total_outras:.1f}h")
    
    total_esperado = total_sabados_func + total_outras
    print(f"📈 TOTAL ESPERADO: {total_esperado:.1f}h")
    print(f"📈 KPI MOSTRA: {kpis['horas_extras']:.1f}h")
    
    if abs(total_esperado - kpis['horas_extras']) < 0.1:
        print(f"\n✅ TESTE PASSOU!")
        return True
    else:
        print(f"\n❌ TESTE FALHOU!")
        print(f"   Diferença: {abs(total_esperado - kpis['horas_extras']):.1f}h")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("✅ VALIDAÇÃO FINAL - CORREÇÃO SÁBADOS")
        print("=" * 80)
        
        # 1. Validar correção dos sábados
        correcao_ok = validar_correcao_sabados()
        
        # 2. Testar com funcionário real
        teste_ok = testar_funcionario_salario_alto()
        
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Sábados corrigidos: {'✅ SIM' if correcao_ok else '❌ NÃO'}")
        print(f"   KPIs funcionando: {'✅ SIM' if teste_ok else '❌ NÃO'}")
        
        if correcao_ok and teste_ok:
            print(f"\n🎉 SISTEMA TOTALMENTE CORRIGIDO!")
            print(f"   As horas extras de sábado agora são calculadas corretamente")
        else:
            print(f"\n⚠️  AINDA HÁ PROBLEMAS PARA RESOLVER")