#!/usr/bin/env python3
"""
TESTE FINAL - CÁLCULO 8H48MIN
Testa se a engine está calculando corretamente com a jornada real
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def testar_calculo_final():
    """Teste final do cálculo com jornada 8h48min"""
    
    with app.app_context():
        print("TESTE FINAL - JORNADA 8H48MIN")
        print("=" * 50)
        
        # Buscar Danilo
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return
        
        print(f"Funcionário: {danilo.nome}")
        print(f"Salário: R$ {danilo.salario:,.2f}")
        
        # Usar a engine para calcular
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(
            danilo.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        horas_trabalhadas = kpis.get('horas_trabalhadas', 0)
        custo_engine = kpis.get('custo_mao_obra', 0)
        
        print(f"\nRESULTADO DA ENGINE:")
        print(f"Horas trabalhadas: {horas_trabalhadas}h")
        print(f"Custo calculado: R$ {custo_engine:,.2f}")
        
        # Validação manual com jornada 8h48min
        print(f"\nVALIDAÇÃO MANUAL:")
        print(f"Jornada: 7h12 às 17h = 9h48min no local")
        print(f"Almoço: 1h")
        print(f"Horas efetivas/dia: 8h48min = 8.8h")
        print(f"Dias úteis julho/2025: 23")
        print(f"Horas mensais: 23 × 8.8h = 202.4h")
        
        valor_hora_correto = danilo.salario / 202.4
        custo_manual = horas_trabalhadas * valor_hora_correto
        
        print(f"Valor/hora: R$ {danilo.salario:,.2f} ÷ 202.4h = R$ {valor_hora_correto:.2f}")
        print(f"Custo manual: {horas_trabalhadas}h × R$ {valor_hora_correto:.2f} = R$ {custo_manual:.2f}")
        
        # Comparar
        diferenca = abs(custo_engine - custo_manual)
        percentual_diferenca = (diferenca / custo_manual) * 100 if custo_manual > 0 else 0
        
        print(f"\nCOMPARAÇÃO:")
        print(f"Engine: R$ {custo_engine:.2f}")
        print(f"Manual: R$ {custo_manual:.2f}")
        print(f"Diferença: R$ {diferenca:.2f} ({percentual_diferenca:.1f}%)")
        
        if diferenca < 10.0:  # Tolerância de R$ 10
            print("✅ CÁLCULO CORRETO!")
            return True
        else:
            print("❌ Ainda há diferença significativa")
            return False

def explicar_calculo():
    """Explica o cálculo detalhadamente"""
    
    print("\nEXPLICAÇÃO DO CÁLCULO")
    print("=" * 40)
    
    print("📋 JORNADA DE TRABALHO:")
    print("   • Entrada: 7h12")
    print("   • Saída: 17h")
    print("   • Tempo no local: 9h48min")
    print("   • Almoço: 1h")
    print("   • Horas efetivas: 8h48min = 8.8h")
    
    print("\n📅 JULHO 2025:")
    print("   • Total de dias: 31")
    print("   • Dias úteis (seg-sex): 23")
    print("   • Fins de semana: 8 dias")
    print("   • Feriados: 0")
    
    print("\n💰 CÁLCULO FINANCEIRO:")
    print("   • Salário: R$ 2.800,00")
    print("   • Horas mensais: 23 × 8.8h = 202.4h")
    print("   • Valor/hora: R$ 2.800 ÷ 202.4h = R$ 13.83")
    
    print("\n⏰ PARA 184H TRABALHADAS:")
    print("   • Custo: 184h × R$ 13.83 = R$ 2.544,72")
    print("   • Análise: 184h ÷ 202.4h = 90.9% das horas esperadas")

if __name__ == "__main__":
    print("VALIDAÇÃO FINAL DO CÁLCULO")
    print("=" * 60)
    
    # Teste principal
    sucesso = testar_calculo_final()
    
    # Explicação detalhada
    explicar_calculo()
    
    print("\n" + "=" * 60)
    if sucesso:
        print("✅ IMPLEMENTAÇÃO CONCLUÍDA COM SUCESSO!")
        print("✅ Cálculo baseado na jornada real de trabalho")
        print("✅ Considera dias úteis específicos de cada mês")
        print("✅ Valor/hora dinâmico e preciso")
    else:
        print("⚠️  Implementação em progresso")
        print("⚠️  Engine precisa de ajustes finais")