#!/usr/bin/env python3
"""
CORREÇÃO FINAL: Lógica de Horas Extras por Entrada Antecipada + Saída Posterior
Sistema SIGE - Data: 05 de Agosto de 2025

PROBLEMA IDENTIFICADO:
- Registro 31/07/2025: 07:05-17:50 (horário padrão 07:12-17:00)
- Sistema mostrava: 1.8h extras (INCORRETO)
- Deveria ser: 7min entrada + 50min saída = 57min = 0.95h extras

CORREÇÃO:
- Calcular minutos extras por entrada antecipada
- Calcular minutos extras por saída posterior
- Somar e converter para horas corretamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import time

def corrigir_logica_horas_extras():
    """
    Aplica a lógica correta de horas extras:
    Extras = Entrada antecipada + Saída posterior (em minutos)
    """
    print("🔧 INICIANDO CORREÇÃO: Lógica Correta de Horas Extras")
    print("=" * 80)
    
    with app.app_context():
        # Buscar registros de trabalho normal que podem ter horas extras incorretas
        registros = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro.in_(['trabalho_normal', 'trabalhado']),
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        registros_corrigidos = 0
        
        print(f"📊 Analisando {len(registros)} registros de trabalho normal")
        print()
        
        for registro in registros:
            funcionario = registro.funcionario_ref
            
            # Obter horário de trabalho do funcionário
            horario = funcionario.horario_trabalho
            if not horario:
                # Usar horário padrão se não houver específico
                horario_entrada = time(8, 0)   # 08:00
                horario_saida = time(17, 0)    # 17:00
            else:
                horario_entrada = horario.entrada
                horario_saida = horario.saida
            
            # Calcular horas extras corretamente
            minutos_extras_total = 0
            
            # EXTRAS POR ENTRADA ANTECIPADA
            if registro.hora_entrada < horario_entrada:
                entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                entrada_prev_min = horario_entrada.hour * 60 + horario_entrada.minute
                minutos_entrada_antecipada = entrada_prev_min - entrada_real_min
                minutos_extras_total += minutos_entrada_antecipada
            
            # EXTRAS POR SAÍDA POSTERIOR  
            if registro.hora_saida > horario_saida:
                saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                saida_prev_min = horario_saida.hour * 60 + horario_saida.minute
                minutos_saida_posterior = saida_real_min - saida_prev_min
                minutos_extras_total += minutos_saida_posterior
            
            # Converter para horas
            horas_extras_corretas = round(minutos_extras_total / 60.0, 2)
            horas_extras_antigas = registro.horas_extras or 0.0
            
            # Verificar se precisa correção
            if abs(horas_extras_corretas - horas_extras_antigas) > 0.01:
                registro.horas_extras = horas_extras_corretas
                
                # Definir percentual
                if horas_extras_corretas > 0:
                    registro.percentual_extras = 50.0
                else:
                    registro.percentual_extras = 0.0
                
                registros_corrigidos += 1
                
                # Log da correção detalhada
                print(f"✅ ID {registro.id} - {funcionario.nome} ({registro.data})")
                print(f"   Horário padrão: {horario_entrada.strftime('%H:%M')} às {horario_saida.strftime('%H:%M')}")
                print(f"   Horário real: {registro.hora_entrada.strftime('%H:%M')} às {registro.hora_saida.strftime('%H:%M')}")
                print(f"   Minutos extras: {minutos_extras_total} min")
                print(f"   Horas extras: {horas_extras_antigas}h → {horas_extras_corretas}h")
                print()
        
        # Salvar alterações
        if registros_corrigidos > 0:
            db.session.commit()
            print(f"💾 {registros_corrigidos} registros corrigidos e salvos!")
        else:
            print("ℹ️ Nenhuma correção necessária!")
        
        print("=" * 80)
        print("🎯 CORREÇÃO FINALIZADA!")

if __name__ == "__main__":
    corrigir_logica_horas_extras()