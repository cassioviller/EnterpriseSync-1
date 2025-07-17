#!/usr/bin/env python3
"""
Script para recalcular atrasos em todos os registros de ponto existentes
Garante que os KPIs reflitam corretamente os valores da tabela
"""

from app import app, db
from kpis_engine_v3 import atualizar_calculos_ponto
from models import RegistroPonto

def recalcular_atrasos():
    """Recalcula atrasos para todos os registros de ponto"""
    
    with app.app_context():
        print("🔄 Iniciando recálculo de atrasos para todos os registros de ponto...")
        
        # Buscar todos os registros de ponto
        registros = RegistroPonto.query.all()
        total = len(registros)
        
        print(f"📊 Encontrados {total} registros para recalcular")
        
        processados = 0
        for i, registro in enumerate(registros, 1):
            try:
                # Recalcular usando a função do engine
                atualizar_calculos_ponto(registro.id)
                processados += 1
                
                if i % 50 == 0:  # Progresso a cada 50 registros
                    print(f"📈 Progresso: {i}/{total} ({(i/total*100):.1f}%)")
                    
            except Exception as e:
                print(f"❌ Erro ao processar registro {registro.id}: {e}")
                continue
        
        print(f"✅ Recálculo concluído!")
        print(f"📊 Registros processados: {processados}/{total}")
        print(f"📈 Taxa de sucesso: {(processados/total*100):.1f}%")

if __name__ == "__main__":
    recalcular_atrasos()