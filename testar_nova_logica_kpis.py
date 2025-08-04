#!/usr/bin/env python3
"""
🧪 TESTE: Nova Lógica de KPIs - Soma Direta da Coluna horas_extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from sqlalchemy import func
from datetime import date

def testar_soma_direta_horas_extras():
    """Testar a nova lógica: soma direta da coluna horas_extras"""
    print("🧪 TESTE: Nova Lógica KPIs - Soma Direta")
    print("=" * 60)
    
    # Pegar funcionário com registros
    funcionario = Funcionario.query.join(RegistroPonto).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).first()
    
    if not funcionario:
        print("❌ Nenhum funcionário com registros encontrado")
        return
    
    print(f"👤 Testando: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    
    # NOVA LÓGICA: Soma direta da coluna horas_extras
    total_horas_extras = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None),
        RegistroPonto.horas_extras > 0  # Apenas valores positivos
    ).scalar() or 0
    
    print(f"\n📊 NOVA LÓGICA:")
    print(f"   Soma direta horas_extras: {total_horas_extras:.1f}h")
    
    # Listar registros individuais
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras > 0
    ).all()
    
    print(f"\n📋 REGISTROS COM HORAS EXTRAS ({len(registros)}):")
    total_manual = 0
    for reg in registros:
        print(f"   {reg.data} | {reg.tipo_registro} | "
              f"Extras: {reg.horas_extras:.1f}h | "
              f"Percentual: {reg.percentual_extras or 0:.0f}%")
        total_manual += reg.horas_extras or 0
    
    print(f"\n✅ VERIFICAÇÃO:")
    print(f"   Soma SQL: {total_horas_extras:.1f}h")
    print(f"   Soma manual: {total_manual:.1f}h")
    print(f"   Match: {'✅ SIM' if abs(total_horas_extras - total_manual) < 0.1 else '❌ NÃO'}")
    
    return funcionario, total_horas_extras

def testar_calculo_valor_com_percentual():
    """Testar cálculo do valor usando percentual_extras"""
    print(f"\n💰 TESTE: Cálculo Valor com Percentual")
    print("=" * 60)
    
    # Pegar funcionário com registros
    funcionario = Funcionario.query.join(RegistroPonto).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras > 0
    ).first()
    
    if not funcionario:
        print("❌ Nenhum funcionário com horas extras encontrado")
        return
    
    print(f"👤 Testando: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    
    # Valor hora base
    valor_hora_base = funcionario.salario / 220  # 220 horas/mês padrão
    print(f"💵 Valor/hora base: R$ {valor_hora_base:.2f}")
    
    # Buscar registros com horas extras
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras > 0
    ).all()
    
    valor_total = 0.0
    
    print(f"\n📋 CÁLCULO DETALHADO:")
    for reg in registros:
        horas_extras = reg.horas_extras or 0
        
        # Usar percentual_extras ou fallback
        if reg.percentual_extras and reg.percentual_extras > 0:
            percentual = reg.percentual_extras / 100
            multiplicador = 1 + percentual
        else:
            # Fallback baseado no tipo
            if reg.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
                multiplicador = 1.5  # 50% adicional
            elif reg.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                multiplicador = 2.0  # 100% adicional  
            else:
                multiplicador = 1.6  # 60% adicional
        
        valor_registro = horas_extras * valor_hora_base * multiplicador
        valor_total += valor_registro
        
        print(f"   {reg.data} | {reg.tipo_registro} | "
              f"{horas_extras:.1f}h × R${valor_hora_base:.2f} × {multiplicador:.1f} = R${valor_registro:.2f}")
    
    print(f"\n💰 VALOR TOTAL: R$ {valor_total:.2f}")
    
    return valor_total

def comparar_com_kpi_engine():
    """Comparar com o resultado do KPI engine"""
    print(f"\n🤖 COMPARAÇÃO: KPI Engine vs Nova Lógica")
    print("=" * 60)
    
    try:
        from kpis_engine import KPIsEngine
        
        # Pegar funcionário para teste
        funcionario = Funcionario.query.join(RegistroPonto).filter(
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).first()
        
        if not funcionario:
            print("❌ Nenhum funcionário encontrado")
            return
        
        print(f"👤 Comparando: {funcionario.nome}")
        
        # Calcular via KPI engine
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(
            funcionario.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        # Calcular via nova lógica (soma direta)
        total_direto = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31),
            RegistroPonto.horas_extras.isnot(None),
            RegistroPonto.horas_extras > 0
        ).scalar() or 0
        
        print(f"\n📊 COMPARAÇÃO:")
        print(f"   KPI Engine: {kpis['horas_extras']:.1f}h")
        print(f"   Soma Direta: {total_direto:.1f}h")
        print(f"   Valor KPI: R$ {kpis['eficiencia']:.2f}")
        
        diferenca_horas = abs(kpis['horas_extras'] - total_direto)
        if diferenca_horas < 0.1:
            print(f"✅ HORAS EXTRAS CORRETAS! Diferença: {diferenca_horas:.2f}h")
        else:
            print(f"❌ DIFERENÇA NAS HORAS! Diferença: {diferenca_horas:.2f}h")
        
        return kpis, total_direto
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return None, None

if __name__ == "__main__":
    with app.app_context():
        print("🧪 TESTE COMPLETO - NOVA LÓGICA KPIs")
        print("=" * 80)
        
        # 1. Testar soma direta
        func_teste, horas_diretas = testar_soma_direta_horas_extras()
        
        # 2. Testar cálculo de valor
        valor_calculado = testar_calculo_valor_com_percentual()
        
        # 3. Comparar com KPI engine
        kpis, total_direto = comparar_com_kpi_engine()
        
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Nova lógica funciona: {'✅ SIM' if horas_diretas > 0 else '❌ NÃO'}")
        print(f"   KPI Engine correto: {'✅ SIM' if kpis and abs(kpis['horas_extras'] - total_direto) < 0.1 else '❌ NÃO'}")
        print(f"   Valor calculado: R$ {valor_calculado:.2f}" if valor_calculado else "N/A")