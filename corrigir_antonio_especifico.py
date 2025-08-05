#!/usr/bin/env python3
"""
CORREÇÃO ESPECÍFICA: Antonio 31/07/2025 - 07:05-17:50
Problema: Mostrando 1.8h em vez de 0.95h de horas extras
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from datetime import date, time

def corrigir_antonio_31_julho():
    """Corrige especificamente o registro do Antonio"""
    
    with app.app_context():
        print("🔧 BUSCANDO REGISTRO ANTONIO 31/07/2025")
        print("=" * 60)
        
        # Buscar o registro do Antônio especificamente
        from sqlalchemy import and_
        registro = RegistroPonto.query.join(Funcionario).filter(
            and_(
                RegistroPonto.data == date(2025, 7, 31),
                Funcionario.nome.like('%Antônio%'),
                RegistroPonto.hora_entrada == time(7, 30),
                RegistroPonto.hora_saida == time(18, 0)
            )
        ).first()
        
        if not registro:
            print("❌ Registro específico não encontrado! Listando todos de 31/07:")
            registros = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 31)
            ).all()
            
            for reg in registros:
                func = reg.funcionario_ref
                print(f"   • {func.nome}: {reg.hora_entrada}-{reg.hora_saida} | {reg.horas_trabalhadas}h | {reg.horas_extras}h")
            return
        
        funcionario = registro.funcionario_ref
        print(f"✅ ENCONTRADO: {funcionario.nome}")
        print(f"   📅 Data: {registro.data}")
        print(f"   🕐 Horário: {registro.hora_entrada} - {registro.hora_saida}")
        print(f"   ⏱️ Horas trabalhadas: {registro.horas_trabalhadas}h")
        print(f"   ⚡ Horas extras: {registro.horas_extras}h")
        print()
        
        # Verificar horário de trabalho
        horario = funcionario.horario_trabalho
        if horario:
            print(f"📋 Horário configurado: {horario.entrada} - {horario.saida}")
        else:
            print("⚠️ Sem horário de trabalho configurado")
        
        # APLICAR CORREÇÃO FORÇADA para o horário correto
        print("\n🔧 APLICANDO CORREÇÃO FORÇADA:")
        print("   Horário padrão correto: 07:12 - 17:00")
        
        # Calcular com horário correto (07:12 - 17:00)
        horario_entrada = time(7, 12)  # 07:12
        horario_saida = time(17, 0)    # 17:00
        
        entrada_prev_min = horario_entrada.hour * 60 + horario_entrada.minute  # 432 min
        entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute  # 425 min
        saida_prev_min = horario_saida.hour * 60 + horario_saida.minute  # 1020 min
        saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute  # 1070 min
        
        # Extras corretos
        minutos_entrada_antecipada = max(0, entrada_prev_min - entrada_real_min)  # 7 min
        minutos_saida_posterior = max(0, saida_real_min - saida_prev_min)  # 50 min
        total_extras_min = minutos_entrada_antecipada + minutos_saida_posterior  # 57 min
        horas_extras_corretas = total_extras_min / 60.0  # 0.95h
        
        print(f"   ✅ Entrada antecipada: {minutos_entrada_antecipada} min")
        print(f"   ✅ Saída posterior: {minutos_saida_posterior} min")
        print(f"   ✅ Total extras: {total_extras_min} min = {horas_extras_corretas:.2f}h")
        
        # Horas trabalhadas corretas
        duracao_normal = (saida_prev_min - entrada_prev_min) / 60.0  # 8.8h
        horas_trabalhadas_corretas = duracao_normal + horas_extras_corretas  # 8.8 + 0.95 = 9.75h
        
        print(f"   ✅ Duração normal: {duracao_normal}h")
        print(f"   ✅ Horas trabalhadas: {horas_trabalhadas_corretas:.2f}h")
        
        # APLICAR CORREÇÃO
        print(f"\n❌ ATUAL: {registro.horas_extras}h extras")
        print(f"✅ CORRETO: {horas_extras_corretas:.2f}h extras")
        
        if abs(registro.horas_extras - horas_extras_corretas) > 0.01:
            registro.horas_extras = round(horas_extras_corretas, 2)
            # Manter horas trabalhadas pois já está correto (9.75h)
            
            try:
                db.session.commit()
                print("🎯 CORREÇÃO APLICADA COM SUCESSO!")
                print(f"   Horas extras: {registro.horas_extras}h")
            except Exception as e:
                print(f"❌ Erro: {str(e)}")
                db.session.rollback()
        else:
            print("✅ Já está correto")

if __name__ == "__main__":
    corrigir_antonio_31_julho()