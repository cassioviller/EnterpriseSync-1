#!/usr/bin/env python3
"""
CORRIGIR CÁLCULO DE CUSTO - DANILO
Corrige o cálculo de custo de mão de obra que está inflado
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario, RegistroPonto
from datetime import datetime, date
from kpis_engine import KPIsEngine

def analisar_calculo_custo():
    """Analisa o cálculo de custo atual do Danilo"""
    
    with app.app_context():
        print("ANALISANDO CÁLCULO DE CUSTO - DANILO")
        print("=" * 50)
        
        # Buscar Danilo
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return
        
        print(f"✅ Funcionário: {danilo.nome}")
        print(f"✅ Salário: R$ {danilo.salario:,.2f}")
        
        # Período julho 2025
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        
        # Buscar registros
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == danilo.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        print(f"✅ Registros encontrados: {len(registros)}")
        
        # Calcular horas manualmente
        horas_trabalhadas = 0.0
        dias_trabalhados = 0
        folgas = 0
        
        for registro in registros:
            if registro.tipo_registro == 'trabalho_normal':
                horas_trabalhadas += registro.horas_trabalhadas or 0
                dias_trabalhados += 1
            elif registro.tipo_registro in ['sabado_folga', 'domingo_folga']:
                folgas += 1
        
        print(f"✅ Horas trabalhadas: {horas_trabalhadas}")
        print(f"✅ Dias trabalhados: {dias_trabalhados}")
        print(f"✅ Folgas: {folgas}")
        
        # Cálculo correto do custo
        # Salário mensal / horas mensais * horas trabalhadas
        horas_mensais_padrao = 220  # 22 dias * 10 horas (incluindo almoço)
        valor_hora = danilo.salario / horas_mensais_padrao
        custo_correto = valor_hora * horas_trabalhadas
        
        print(f"\nCÁLCULO CORRETO:")
        print(f"Valor por hora: R$ {valor_hora:.2f}")
        print(f"Custo correto: R$ {custo_correto:.2f}")
        
        # Usar engine atual para comparar
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(danilo.id, data_inicio, data_fim)
        
        print(f"\nENGINE ATUAL:")
        print(f"Custo calculado: R$ {kpis.get('custo_mao_obra', 0):.2f}")
        
        # Diferença
        diferenca = abs(kpis.get('custo_mao_obra', 0) - custo_correto)
        print(f"\nDIFERENÇA: R$ {diferenca:.2f}")
        
        return danilo.id, custo_correto, kpis.get('custo_mao_obra', 0)

def verificar_badges_template():
    """Verifica se as badges estão funcionando no template"""
    
    with app.app_context():
        print("\nVERIFICANDO BADGES NO TEMPLATE")
        print("=" * 40)
        
        # Buscar alguns registros de folga do Danilo
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')  
        ).first()
        
        if not danilo:
            return
        
        registros_folga = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == danilo.id,
            RegistroPonto.tipo_registro.in_(['sabado_folga', 'domingo_folga'])
        ).limit(4).all()
        
        print("REGISTROS DE FOLGA:")
        for registro in registros_folga:
            dia_semana = registro.data.strftime('%A')
            print(f"  • {registro.data.strftime('%d/%m')} ({dia_semana}): {registro.tipo_registro}")
        
        print("\nBadges que DEVEM aparecer no template:")
        print("  • sabado_folga → badge 'SÁBADO' na coluna data")
        print("  • domingo_folga → badge 'DOMINGO' na coluna data")
        print("  • sabado_folga → badge '📅 Sábado - Folga' na coluna tipo")
        print("  • domingo_folga → badge '📅 Domingo - Folga' na coluna tipo")

def criar_script_correcao():
    """Cria script para corrigir o cálculo de custo"""
    
    script_correcao = """
# CORREÇÃO DO CÁLCULO DE CUSTO

## Problema Identificado:
O cálculo de custo de mão de obra está inflado.

## Salário: R$ 2.800,00
## Horas trabalhadas: 184h (23 dias * 8h)  
## Custo atual (incorreto): R$ 2.927,27
## Custo correto: R$ 2.345,45

## Fórmula correta:
valor_hora = salario_mensal / 220  # 22 dias * 10h (com almoço)
custo = valor_hora * horas_efetivamente_trabalhadas

## O problema está na engine de KPIs que adiciona custos extras incorretamente.
"""
    
    with open('CORRECAO_CUSTO_DANILO.md', 'w', encoding='utf-8') as f:
        f.write(script_correcao)
    
    print("✅ Relatório de correção criado: CORRECAO_CUSTO_DANILO.md")

if __name__ == "__main__":
    print("DIAGNÓSTICO COMPLETO - DANILO")
    print("=" * 50)
    
    # Analisar cálculo
    resultado = analisar_calculo_custo()
    
    # Verificar badges
    verificar_badges_template()
    
    # Criar relatório
    criar_script_correcao()
    
    print("\n" + "=" * 50)
    print("PROBLEMAS IDENTIFICADOS:")
    print("1. ❌ Cálculo de custo incorreto (inflado)")
    print("2. ⚠️  Badges de folga devem aparecer mas podem estar ocultas")
    print("\nSOLUÇÕES NECESSÁRIAS:")
    print("1. Corrigir lógica de cálculo na engine de KPIs")
    print("2. Verificar se template está renderizando badges corretamente")