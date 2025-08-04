#!/usr/bin/env python3
"""
🔧 CORREÇÃO URGENTE: Sábados com horas_extras = 0 
Corrigir os 21 registros de sábado que têm horas trabalhadas mas horas_extras = 0
"""

from app import app, db
from models import RegistroPonto, Funcionario

def corrigir_sabados_com_horas_extras_zero():
    """Corrigir registros de sábado com horas_extras = 0"""
    print("🔧 CORREÇÃO: Sábados com Horas Extras = 0")
    print("=" * 60)
    
    # Buscar registros problemáticos
    registros_problema = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.horas_trabalhadas > 0,
        RegistroPonto.horas_extras == 0
    ).all()
    
    print(f"📊 REGISTROS COM PROBLEMA: {len(registros_problema)}")
    
    if len(registros_problema) == 0:
        print("✅ Não há registros com problema")
        return 0
    
    # Mostrar alguns exemplos
    print(f"\n📋 EXEMPLOS DE REGISTROS COM PROBLEMA:")
    for i, registro in enumerate(registros_problema[:10]):
        funcionario = Funcionario.query.get(registro.funcionario_id)
        nome = funcionario.nome if funcionario else 'N/A'
        print(f"   {registro.data} | {nome} | "
              f"Trab: {registro.horas_trabalhadas:.1f}h | Extras: {registro.horas_extras:.1f}h")
    
    if len(registros_problema) > 10:
        print(f"   ... e mais {len(registros_problema) - 10} registros")
    
    # Aplicar correção
    print(f"\n🔧 APLICANDO CORREÇÃO...")
    registros_corrigidos = 0
    horas_adicionadas = 0
    
    for registro in registros_problema:
        # Em sábado trabalhado, horas_extras = horas_trabalhadas
        horas_antes = registro.horas_extras or 0
        registro.horas_extras = registro.horas_trabalhadas
        registro.percentual_extras = 50.0  # 50% adicional para sábado
        
        horas_adicionadas += (registro.horas_extras - horas_antes)
        registros_corrigidos += 1
    
    # Salvar as mudanças
    db.session.commit()
    
    print(f"✅ CORREÇÃO APLICADA:")
    print(f"   Registros corrigidos: {registros_corrigidos}")
    print(f"   Horas extras adicionadas: {horas_adicionadas:.1f}h")
    print(f"   Lógica: sábado_trabalhado → horas_extras = horas_trabalhadas")
    
    return registros_corrigidos, horas_adicionadas

def verificar_impacto_correcao():
    """Verificar o impacto da correção nos KPIs"""
    print(f"\n🔍 VERIFICAÇÃO PÓS-CORREÇÃO")
    print("=" * 60)
    
    from kpis_engine import KPIsEngine
    from datetime import date
    
    # Testar com João Silva Santos
    funcionario = Funcionario.query.filter_by(nome='João Silva Santos').first()
    if not funcionario:
        print("❌ João Silva Santos não encontrado")
        return
    
    print(f"👤 Testando: {funcionario.nome} (ID: {funcionario.id})")
    
    # Calcular KPIs
    engine = KPIsEngine()
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    kpis = engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    print(f"\n📊 KPIS APÓS CORREÇÃO:")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    
    # Verificar registros individuais
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.horas_extras > 0
    ).all()
    
    print(f"\n📋 REGISTROS COM HORAS EXTRAS ({len(registros)}):")
    total_manual = 0
    for reg in registros:
        print(f"   {reg.data} | {reg.tipo_registro} | {reg.horas_extras:.1f}h")
        total_manual += reg.horas_extras or 0
    
    print(f"\n📈 COMPARAÇÃO:")
    print(f"   Total manual: {total_manual:.1f}h")
    print(f"   KPI calculado: {kpis['horas_extras']:.1f}h")
    print(f"   Match: {'✅ SIM' if abs(total_manual - kpis['horas_extras']) < 0.1 else '❌ NÃO'}")
    
    # Expectativa: deve mostrar pelo menos 7.9h + outras horas
    if kpis['horas_extras'] >= 7.9:
        print(f"\n✅ CORREÇÃO BEM-SUCEDIDA!")
        print(f"   Agora mostra {kpis['horas_extras']:.1f}h (inclui sábados)")
    else:
        print(f"\n❌ AINDA HÁ PROBLEMA")
        print(f"   Mostra apenas {kpis['horas_extras']:.1f}h")

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO URGENTE - SÁBADOS COM HORAS_EXTRAS = 0")
        print("=" * 80)
        
        # 1. Corrigir registros problemáticos
        corrigidos, horas_add = corrigir_sabados_com_horas_extras_zero()
        
        if corrigidos > 0:
            # 2. Verificar impacto
            verificar_impacto_correcao()
            
            print(f"\n🎯 RESULTADO FINAL:")
            print(f"   {corrigidos} registros corrigidos")
            print(f"   {horas_add:.1f}h de horas extras adicionadas")
            print(f"   Sistema deve mostrar valores corretos agora")
            print(f"\n⚠️  REINICIAR SERVIDOR para aplicar nas KPIs")
        else:
            print(f"\n✅ Sistema já estava correto")