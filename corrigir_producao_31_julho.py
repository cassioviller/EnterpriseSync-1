#!/usr/bin/env python3
"""
CORREÇÃO ESPECÍFICA PRODUÇÃO: 31/07/2025 João Silva Santos
Aplicar correção direta no banco de dados de produção
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def corrigir_registro_31_julho():
    """Corrige especificamente o registro de 31/07/2025"""
    
    with app.app_context():
        print("🔧 CORREÇÃO ESPECÍFICA: 31/07/2025 - PRODUÇÃO")
        print("=" * 60)
        
        # Buscar registro específico
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 31),
            RegistroPonto.hora_entrada == time(7, 5),
            RegistroPonto.hora_saida == time(17, 50)
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado!")
            return
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        print(f"📋 ANTES:")
        print(f"   Funcionário: {funcionario.nome}")
        print(f"   Data: {registro.data}")
        print(f"   Horários: {registro.hora_entrada} - {registro.hora_saida}")
        print(f"   Horas extras: {registro.horas_extras}h")
        print(f"   Percentual: {registro.percentual_extras}%")
        
        # APLICAR LÓGICA CORRETA
        # Padrão: 07:12-17:00
        # Real: 07:05-17:50
        # Antecipação: 07:12 - 07:05 = 7min
        # Prolongamento: 17:50 - 17:00 = 50min
        # Total extras: 7 + 50 = 57min = 0.95h
        
        registro.horas_extras = 0.95
        registro.percentual_extras = 50.0
        
        # Recalcular horas trabalhadas
        # 17:50 - 07:05 - 1h almoço = 10h45min - 1h = 9h45min = 9.75h
        registro.horas_trabalhadas = 9.75
        
        try:
            db.session.commit()
            
            print(f"\n✅ CORREÇÃO APLICADA:")
            print(f"   Horas extras: {registro.horas_extras}h")
            print(f"   Percentual: {registro.percentual_extras}%")
            print(f"   Horas trabalhadas: {registro.horas_trabalhadas}h")
            print(f"   ✅ DEVE MOSTRAR: 0.95h - 50%")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    corrigir_registro_31_julho()