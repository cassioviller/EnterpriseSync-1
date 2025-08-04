#!/usr/bin/env python3
"""
🎯 CORREÇÃO: Horas Extras Incorretas Ana Paula 28/07/2025
PROBLEMA: Mostra 0.5h extras quando deveria ser apenas 0.3h de atraso
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import datetime, time

def corrigir_calculo_especifico():
    """Corrigir cálculo de horas para o registro específico"""
    with app.app_context():
        print("🔧 CORREÇÃO: Horas Ana Paula 28/07/2025")
        print("=" * 50)
        
        # Buscar registro específico
        ana_paula = Funcionario.query.filter(Funcionario.nome.ilike('%Ana Paula%')).first()
        registro = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == ana_paula.id,
            RegistroPonto.data == datetime(2025, 7, 28).date()
        ).first()
        
        print(f"📋 SITUAÇÃO ATUAL:")
        print(f"   • Entrada: {registro.hora_entrada} (previsto 07:12)")
        print(f"   • Saída: {registro.hora_saida} (previsto 17:00)")  
        print(f"   • Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   • Horas extras: {registro.horas_extras}")
        print(f"   • Atraso: {registro.total_atraso_horas}")
        print(f"   • Percentual extras: {registro.percentual_extras}%")
        
        # ANÁLISE:
        # Entrada: 07:30 (18min atraso)
        # Saída: 17:00 (no horário)
        # Trabalhou: 07:30-12:00 + 13:00-17:00 = 4.5h + 4h = 8.5h
        # Jornada normal: 07:12-12:00 + 13:00-17:00 = 4.8h + 4h = 8.8h
        # Resultado: 8.5h trabalhadas (8.8h previstas - 0.3h atraso)
        
        print(f"\n🔍 ANÁLISE CORRETA:")
        print(f"   • Jornada prevista: 8.8h (07:12-12:00 + 13:00-17:00)")
        print(f"   • Jornada real: 8.5h (07:30-12:00 + 13:00-17:00)")
        print(f"   • Diferença: -0.3h (atraso, não extras)")
        
        # Forçar recálculo correto
        engine = KPIsEngine()
        resultado = engine.calcular_e_atualizar_ponto(registro.id)
        
        # Recarregar registro
        db.session.refresh(registro)
        
        print(f"\n✅ APÓS RECÁLCULO:")
        print(f"   • Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   • Horas extras: {registro.horas_extras}")
        print(f"   • Atraso: {registro.total_atraso_horas}")
        print(f"   • Resultado recálculo: {resultado}")

if __name__ == "__main__":
    corrigir_calculo_especifico()