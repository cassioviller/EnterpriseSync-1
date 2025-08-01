#!/usr/bin/env python3
"""
TESTE LÓGICA CORRIGIDA FINAL
Se funcionário trabalhou normalmente, custo = salário
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario
from kpis_engine import KPIsEngine
from datetime import date

def testar_logica_final():
    """Testa a lógica corrigida"""
    
    with app.app_context():
        print("TESTE LÓGICA CORRIGIDA FINAL")
        print("=" * 50)
        
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return
        
        # Calcular com nova engine
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(
            danilo.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        horas_trabalhadas = kpis.get('horas_trabalhadas', 0)
        custo_calculado = kpis.get('custo_mao_obra', 0)
        
        print(f"Funcionário: {danilo.nome}")
        print(f"Salário: R$ {danilo.salario:,.2f}")
        print(f"Horas trabalhadas: {horas_trabalhadas}h")
        print(f"Custo calculado: R$ {custo_calculado:,.2f}")
        
        # Expectativa: se trabalhou normalmente, custo = salário
        print(f"\nANÁLISE:")
        if abs(custo_calculado - danilo.salario) < 1.0:
            print("✅ CORRETO! Custo igual ao salário")
            print("✅ Funcionário trabalhou normalmente")
        else:
            diferenca = custo_calculado - danilo.salario
            print(f"❌ Diferença: R$ {diferenca:.2f}")
            
            if diferenca < 0:
                print("❌ Custo menor que salário (possível erro)")
            else:
                print("❌ Custo maior que salário (horas extras?)")
        
        return custo_calculado

if __name__ == "__main__":
    resultado = testar_logica_final()
    
    print(f"\n" + "=" * 50)
    print("EXPLICAÇÃO:")
    print("Se Danilo trabalhou 184h em julho,")
    print("e não teve faltas nem horas extras,") 
    print("então o custo deveria ser exatamente R$ 2.800,00")
    print("(o valor do salário mensal)")