"""
Script para recalcular automaticamente todos os registros de ponto
Garante que os campos calculados estejam corretos conforme v3.0
"""

from app import app, db
from models import RegistroPonto
from kpis_engine_v3 import atualizar_calculos_ponto

def recalcular_todos_registros():
    """
    Recalcula todos os registros de ponto existentes
    """
    with app.app_context():
        # Buscar todos os registros de ponto
        registros = RegistroPonto.query.all()
        
        print(f"Recalculando {len(registros)} registros de ponto...")
        
        total_processados = 0
        for registro in registros:
            try:
                # Atualizar cálculos automáticos
                atualizar_calculos_ponto(registro.id)
                total_processados += 1
                
                if total_processados % 50 == 0:
                    print(f"Processados {total_processados}/{len(registros)} registros...")
                    
            except Exception as e:
                print(f"Erro ao processar registro {registro.id}: {e}")
                continue
        
        print(f"Recalculação concluída! Total processados: {total_processados}")

if __name__ == "__main__":
    recalcular_todos_registros()