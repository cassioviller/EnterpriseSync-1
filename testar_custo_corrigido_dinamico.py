#!/usr/bin/env python3
"""
TESTE DO CÁLCULO DINÂMICO CORRIGIDO
Testa a nova lógica de cálculo baseada em dias úteis reais
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def testar_calculo_danilo():
    """Testa o novo cálculo para Danilo"""
    
    with app.app_context():
        print("TESTE CÁLCULO DINÂMICO - DANILO")
        print("=" * 50)
        
        # Buscar Danilo
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return
        
        # Calcular KPIs com nova lógica
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(
            danilo.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"Funcionário: {danilo.nome}")
        print(f"Salário: R$ {danilo.salario:,.2f}")
        print(f"Período: Julho/2025")
        
        # Dados do cálculo
        horas_trabalhadas = kpis.get('horas_trabalhadas', 0)
        custo_calculado = kpis.get('custo_mao_obra', 0)
        
        print(f"\nRESULTADOS:")
        print(f"Horas trabalhadas: {horas_trabalhadas}h")
        print(f"Custo calculado: R$ {custo_calculado:,.2f}")
        
        # Cálculo manual para validar
        dias_uteis_julho = 23  # Calculado: julho/2025 tem 23 dias úteis
        horas_mensais = dias_uteis_julho * 8
        valor_hora_correto = danilo.salario / horas_mensais
        custo_manual = horas_trabalhadas * valor_hora_correto
        
        print(f"\nVALIDAÇÃO MANUAL:")
        print(f"Dias úteis julho/2025: {dias_uteis_julho}")
        print(f"Horas mensais: {horas_mensais}h")
        print(f"Valor/hora: R$ {valor_hora_correto:.2f}")
        print(f"Custo manual: R$ {custo_manual:.2f}")
        
        # Comparar
        diferenca = abs(custo_calculado - custo_manual)
        if diferenca < 1.0:
            print(f"✅ CÁLCULO CORRETO - Diferença: R$ {diferenca:.2f}")
        else:
            print(f"❌ AINDA HÁ DIFERENÇA: R$ {diferenca:.2f}")
        
        return custo_calculado, custo_manual

if __name__ == "__main__":
    print("VALIDAÇÃO DO CÁLCULO DINÂMICO")
    print("=" * 60)
    
    try:
        resultado = testar_calculo_danilo()
        if resultado:
            custo_calc, custo_manual = resultado
            print(f"\n✅ Teste concluído")
            print(f"Engine: R$ {custo_calc:.2f}")
            print(f"Manual: R$ {custo_manual:.2f}")
    except Exception as e:
        print(f"❌ Erro: {e}")
        print("Engine precisa ser corrigida")