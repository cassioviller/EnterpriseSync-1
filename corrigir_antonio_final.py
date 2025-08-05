#!/usr/bin/env python3
"""
CORREÇÃO FINAL: Antonio - 31/07/2025
Corrigir horário de trabalho para 07:12-17:00 e recalcular horas extras
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from datetime import date, time

def corrigir_antonio_completo():
    """Correção completa do Antonio"""
    
    with app.app_context():
        print("🎯 CORREÇÃO COMPLETA: Antônio Silva Nunes")
        print("=" * 60)
        
        # 1. Encontrar o funcionário
        funcionario = Funcionario.query.filter(
            Funcionario.nome.like('%Antônio%')
        ).first()
        
        if not funcionario:
            print("❌ Funcionário não encontrado")
            return
        
        print(f"✅ Funcionário: {funcionario.nome}")
        
        # 2. Corrigir horário de trabalho
        horario = funcionario.horario_trabalho
        if horario:
            print(f"📋 Horário atual: {horario.entrada} - {horario.saida}")
            
            # Corrigir para 07:12 - 17:00
            horario.entrada = time(7, 12)
            horario.saida = time(17, 0)
            
            print(f"✅ Horário corrigido para: {horario.entrada} - {horario.saida}")
        
        # 3. Encontrar e corrigir registro de 31/07/2025
        registro = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data == date(2025, 7, 31)
        ).first()
        
        if not registro:
            print("❌ Registro de 31/07/2025 não encontrado")
            return
        
        print(f"📅 Registro encontrado: {registro.hora_entrada} - {registro.hora_saida}")
        print(f"⏱️ Antes: {registro.horas_trabalhadas}h trabalhadas, {registro.horas_extras}h extras")
        
        # 4. Recalcular manualmente com a lógica correta
        # Horário real: 07:30 - 18:00
        # Horário padrão: 07:12 - 17:00
        
        entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute  # 450 min
        entrada_prev_min = 7 * 60 + 12  # 432 min (07:12)
        saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute  # 1080 min
        saida_prev_min = 17 * 60  # 1020 min (17:00)
        
        # Calcular extras
        minutos_entrada_antecipada = max(0, entrada_prev_min - entrada_real_min)  # 0 (chegou tarde)
        minutos_saida_posterior = max(0, saida_real_min - saida_prev_min)  # 60 min
        total_extras_min = minutos_entrada_antecipada + minutos_saida_posterior  # 60 min
        horas_extras_corretas = total_extras_min / 60.0  # 1.0h
        
        # Calcular horas trabalhadas
        duracao_normal = (saida_prev_min - entrada_prev_min) / 60.0  # 9.8h
        horas_trabalhadas_corretas = duracao_normal + horas_extras_corretas  # 10.8h
        
        print(f"🔍 CÁLCULO DETALHADO:")
        print(f"   Entrada: {registro.hora_entrada} vs {time(7, 12)} - Antecipada: {minutos_entrada_antecipada} min")
        print(f"   Saída: {registro.hora_saida} vs {time(17, 0)} - Posterior: {minutos_saida_posterior} min")
        print(f"   Total extras: {total_extras_min} min = {horas_extras_corretas:.2f}h")
        print(f"   Horas trabalhadas: {horas_trabalhadas_corretas:.2f}h")
        
        # 5. Aplicar correções
        registro.horas_extras = horas_extras_corretas
        registro.horas_trabalhadas = horas_trabalhadas_corretas
        
        try:
            db.session.commit()
            print("✅ CORREÇÃO APLICADA COM SUCESSO!")
            print(f"   ⚡ Horas extras: {registro.horas_extras}h")
            print(f"   ⏱️ Horas trabalhadas: {registro.horas_trabalhadas}h")
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    corrigir_antonio_completo()