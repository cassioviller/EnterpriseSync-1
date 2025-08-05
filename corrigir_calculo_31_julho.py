#!/usr/bin/env python3
"""
CORREÇÃO ESPECÍFICA: Cálculo de Horas Extras 31/07/2025
Problema: 07:05-17:50 com horário 07:12-17:00 está calculando 1.8h em vez de 0.95h

CÁLCULO CORRETO:
- Horário padrão: 07:12 - 17:00
- Horário real: 07:05 - 17:50
- Entrada antecipada: 07:05 vs 07:12 = 7 minutos
- Saída posterior: 17:50 vs 17:00 = 50 minutos
- Total extras: 7 + 50 = 57 minutos = 0.95h
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from datetime import date, time

def corrigir_calculo_especifico():
    """Corrige o cálculo específico do registro 31/07/2025"""
    
    with app.app_context():
        print("🔧 CORREÇÃO ESPECÍFICA: 31/07/2025")
        print("=" * 50)
        
        # Buscar registro específico
        registros = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 31),
            RegistroPonto.hora_entrada == time(7, 5),
            RegistroPonto.hora_saida == time(17, 50)
        ).all()
        
        if not registros:
            # Buscar qualquer registro da data com horas similares
            registros = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 31),
                RegistroPonto.horas_extras > 1.0
            ).all()
            
        if not registros:
            print("❌ Nenhum registro encontrado na data!")
            return
            
        print(f"📊 Encontrados {len(registros)} registros para análise:")
        for i, reg in enumerate(registros):
            func = reg.funcionario_ref
            print(f"   {i+1}. {func.nome} - {reg.hora_entrada}-{reg.hora_saida} - {reg.horas_extras}h extras")
        
        # Pegar o primeiro registro
        registro = registros[0]
        
        if not registro:
            print("❌ Registro não encontrado!")
            return
        
        funcionario = registro.funcionario_ref
        horario = funcionario.horario_trabalho
        
        print(f"👤 Funcionário: {funcionario.nome}")
        print(f"📅 Data: {registro.data}")
        print(f"🕐 Horário real: {registro.hora_entrada} - {registro.hora_saida}")
        print(f"📋 Horário padrão: {horario.entrada} - {horario.saida}")
        print(f"⏱️ Horas trabalhadas atual: {registro.horas_trabalhadas}h")
        print(f"⚡ Horas extras atual: {registro.horas_extras}h")
        print()
        
        # Calcular correto
        entrada_prev_min = horario.entrada.hour * 60 + horario.entrada.minute  # 07:12 = 432 min
        entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute  # 07:05 = 425 min
        saida_prev_min = horario.saida.hour * 60 + horario.saida.minute  # 17:00 = 1020 min
        saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute  # 17:50 = 1070 min
        
        print("🔍 CÁLCULO DETALHADO:")
        print(f"   Entrada prevista: {horario.entrada} = {entrada_prev_min} min")
        print(f"   Entrada real: {registro.hora_entrada} = {entrada_real_min} min")
        print(f"   Saída prevista: {horario.saida} = {saida_prev_min} min")
        print(f"   Saída real: {registro.hora_saida} = {saida_real_min} min")
        print()
        
        # Calcular extras corretos
        minutos_entrada_antecipada = max(0, entrada_prev_min - entrada_real_min)
        minutos_saida_posterior = max(0, saida_real_min - saida_prev_min)
        total_extras_min = minutos_entrada_antecipada + minutos_saida_posterior
        horas_extras_corretas = total_extras_min / 60.0
        
        print("📊 RESULTADO:")
        print(f"   Entrada antecipada: {entrada_prev_min - entrada_real_min} = {minutos_entrada_antecipada} min")
        print(f"   Saída posterior: {saida_real_min - saida_prev_min} = {minutos_saida_posterior} min")
        print(f"   Total extras: {total_extras_min} min = {horas_extras_corretas:.2f}h")
        print()
        
        # Calcular horas trabalhadas normais
        duracao_horario_normal = (saida_prev_min - entrada_prev_min) / 60.0
        horas_trabalhadas_corretas = duracao_horario_normal + horas_extras_corretas
        
        print(f"   Duração horário normal: {duracao_horario_normal}h")
        print(f"   Horas trabalhadas totais: {horas_trabalhadas_corretas:.2f}h")
        print()
        
        if abs(registro.horas_extras - horas_extras_corretas) > 0.01:
            print("❌ PRECISA CORREÇÃO!")
            print(f"   Atual: {registro.horas_extras}h → Correto: {horas_extras_corretas:.2f}h")
            
            # Aplicar correção
            registro.horas_extras = round(horas_extras_corretas, 2)
            registro.horas_trabalhadas = round(horas_trabalhadas_corretas, 2)
            
            try:
                db.session.commit()
                print("✅ CORREÇÃO APLICADA COM SUCESSO!")
            except Exception as e:
                print(f"❌ Erro ao salvar: {str(e)}")
                db.session.rollback()
        else:
            print("✅ JÁ ESTÁ CORRETO!")

if __name__ == "__main__":
    corrigir_calculo_especifico()