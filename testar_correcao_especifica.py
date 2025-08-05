#!/usr/bin/env python3
"""
Teste específico para correção do registro 31/07/2025 07:05-17:50
"""
from app import app, db
from models import RegistroPonto, Funcionario
from datetime import time, date

with app.app_context():
    # Buscar registros de 31/07/2025 com horas extras altas
    registros = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 31),
        RegistroPonto.horas_extras > 1.0
    ).all()
    
    print(f"📊 REGISTROS 31/07/2025 COM HORAS EXTRAS > 1.0h:")
    print()
    
    for registro in registros:
        funcionario = registro.funcionario_ref
        horario = funcionario.horario_trabalho
        
        if horario:
            print(f"✅ {funcionario.nome} (ID: {registro.id})")
            print(f"   📅 {registro.data}")
            print(f"   🕐 {registro.hora_entrada} às {registro.hora_saida}")
            print(f"   📋 Horário padrão: {horario.entrada} às {horario.saida}")
            print(f"   ⏱️ Horas trabalhadas: {registro.horas_trabalhadas}h")
            print(f"   ⚡ Horas extras: {registro.horas_extras}h")
            print(f"   📝 Tipo: {registro.tipo_registro}")
            
            # Calcular certo
            if registro.hora_entrada and registro.hora_saida and horario:
                entrada_prev_min = horario.entrada.hour * 60 + horario.entrada.minute
                entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                saida_prev_min = horario.saida.hour * 60 + horario.saida.minute  
                saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                
                minutos_entrada_antecipada = max(0, entrada_prev_min - entrada_real_min)
                minutos_saida_posterior = max(0, saida_real_min - saida_prev_min)
                total_extras_min = minutos_entrada_antecipada + minutos_saida_posterior
                horas_extras_corretas = total_extras_min / 60.0
                
                print(f"   🔍 Cálculo correto:")
                print(f"      Entrada antecipada: {minutos_entrada_antecipada} min")
                print(f"      Saída posterior: {minutos_saida_posterior} min")
                print(f"      Total extras: {total_extras_min} min = {horas_extras_corretas:.2f}h")
                
                if abs(registro.horas_extras - horas_extras_corretas) > 0.01:
                    print(f"   ❌ PRECISA CORREÇÃO: {registro.horas_extras}h → {horas_extras_corretas:.2f}h")
                else:
                    print(f"   ✅ JÁ CORRETO")
            print()