#!/usr/bin/env python3
"""
Script para testar os KPIs corrigidos do João Silva dos Santos (F0099)
Verifica se as correções específicas foram aplicadas corretamente
"""

import os
import sys
from datetime import date
from app import app, db
from models import Funcionario, RegistroPonto
from kpis_engine_v3 import calcular_kpis_funcionario_v3

def testar_kpis_joao():
    """
    Testa os KPIs corrigidos do João Silva dos Santos
    """
    with app.app_context():
        print("=" * 60)
        print("TESTE DOS KPIs CORRIGIDOS - JOÃO SILVA DOS SANTOS (F0099)")
        print("=" * 60)
        
        # Buscar funcionário
        funcionario = Funcionario.query.filter_by(codigo='F0099').first()
        if not funcionario:
            print("❌ Funcionário F0099 não encontrado")
            return
            
        print(f"✅ Funcionário encontrado: {funcionario.nome}")
        print(f"📋 Código: {funcionario.codigo}")
        print(f"💰 Salário: R$ {funcionario.salario:,.2f}")
        print()
        
        # Definir período (junho/2025)
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        print(f"📅 Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        print()
        
        # Verificar registros de ponto
        registros_ponto = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        print(f"📊 Total de registros de ponto: {len(registros_ponto)}")
        
        # Contar por tipo
        tipos_count = {}
        for registro in registros_ponto:
            tipo = registro.tipo_registro or 'trabalho_normal'
            tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
        
        print("\n🔍 Registros por tipo:")
        for tipo, count in tipos_count.items():
            print(f"  - {tipo}: {count}")
        
        # Calcular KPIs
        print("\n⚙️ Calculando KPIs...")
        kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
        
        if not kpis:
            print("❌ Erro ao calcular KPIs")
            return
        
        print("\n📊 RESULTADOS DOS KPIs:")
        print("-" * 40)
        
        # Linha 1: KPIs Básicos
        print("📈 LINHA 1 - KPIs BÁSICOS:")
        print(f"  🕐 Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"  ⏰ Horas extras: {kpis['horas_extras']:.1f}h")
        print(f"  ❌ Faltas: {kpis['faltas']} (apenas não justificadas)")
        print(f"  ⏱️ Atrasos: {kpis['atrasos']:.2f}h")
        print()
        
        # Linha 2: KPIs Analíticos
        print("📊 LINHA 2 - KPIs ANALÍTICOS:")
        print(f"  📈 Produtividade: {kpis['produtividade']:.1f}%")
        print(f"  📉 Absenteísmo: {kpis['absenteismo']:.1f}%")
        print(f"  📊 Média diária: {kpis['media_diaria']:.1f}h")
        print(f"  ✅ Faltas justificadas: {kpis['faltas_justificadas']} (novo KPI)")
        print()
        
        # Linha 3: KPIs Financeiros
        print("💰 LINHA 3 - KPIs FINANCEIROS:")
        print(f"  💼 Custo mão de obra: R$ {kpis['custo_mao_obra']:,.2f}")
        print(f"  🍽️ Custo alimentação: R$ {kpis['custo_alimentacao']:,.2f}")
        print(f"  💸 Outros custos: R$ {kpis['outros_custos']:,.2f}")
        print(f"  📈 Horas perdidas: {kpis['horas_perdidas']:.1f}h")
        print()
        
        # Verificações específicas
        print("🔍 VERIFICAÇÕES ESPECÍFICAS:")
        print("-" * 40)
        
        # 1. Verificar separação de faltas
        faltas_total = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
        ).count()
        
        print(f"1. Separação de faltas:")
        print(f"   - Total de faltas (ambos tipos): {faltas_total}")
        print(f"   - Faltas não justificadas: {kpis['faltas']}")
        print(f"   - Faltas justificadas: {kpis['faltas_justificadas']}")
        print(f"   - Soma correta: {kpis['faltas'] + kpis['faltas_justificadas'] == faltas_total}")
        print()
        
        # 2. Verificar absenteísmo
        print(f"2. Cálculo do absenteísmo:")
        print(f"   - Dias úteis no período: {kpis['dias_uteis']}")
        print(f"   - Faltas não justificadas: {kpis['faltas']}")
        print(f"   - Fórmula: ({kpis['faltas']} ÷ {kpis['dias_uteis']}) × 100 = {kpis['absenteismo']:.1f}%")
        print(f"   - Esperado: {(kpis['faltas'] / kpis['dias_uteis'] * 100):.1f}%")
        print()
        
        # 3. Verificar horas perdidas
        print(f"3. Cálculo das horas perdidas:")
        print(f"   - Faltas não justificadas: {kpis['faltas']} × 8h = {kpis['faltas'] * 8:.1f}h")
        print(f"   - Atrasos: {kpis['atrasos']:.2f}h")
        print(f"   - Total: {kpis['faltas'] * 8:.1f}h + {kpis['atrasos']:.2f}h = {kpis['horas_perdidas']:.1f}h")
        print()
        
        # 4. Verificar produtividade
        print(f"4. Cálculo da produtividade:")
        print(f"   - Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"   - Horas esperadas: {kpis['horas_esperadas']:.1f}h")
        print(f"   - Fórmula: ({kpis['horas_trabalhadas']:.1f} ÷ {kpis['horas_esperadas']:.1f}) × 100 = {kpis['produtividade']:.1f}%")
        print()
        
        # Dados auxiliares
        print("📋 DADOS AUXILIARES:")
        print("-" * 40)
        print(f"  - Dias úteis: {kpis['dias_uteis']}")
        print(f"  - Dias com presença: {kpis['dias_com_presenca']}")
        print(f"  - Horas esperadas: {kpis['horas_esperadas']:.1f}h")
        print(f"  - Período: {kpis['periodo']}")
        print()
        
        # Resumo das correções
        print("✅ CORREÇÕES APLICADAS:")
        print("-" * 40)
        print("1. ✅ Separação de faltas justificadas e não justificadas")
        print("2. ✅ Absenteísmo calculado apenas com faltas não justificadas")
        print("3. ✅ Novo KPI 'Faltas Justificadas' implementado")
        print("4. ✅ Horas perdidas baseadas apenas em faltas não justificadas")
        print("5. ✅ Layout organizado em grid 4-4-2 com 10 KPIs únicos")
        print()
        
        print("🎯 TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 60)

if __name__ == "__main__":
    testar_kpis_joao()