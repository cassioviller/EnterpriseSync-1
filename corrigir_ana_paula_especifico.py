#!/usr/bin/env python3
"""
CORREÇÃO ESPECÍFICA: Ana Paula Rodrigues 29/07/2025
Aplicar lógica correta de atrasos e horas extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def corrigir_ana_paula():
    """Corrige especificamente o registro da Ana Paula"""
    
    with app.app_context():
        print("🔍 CORREÇÃO ANA PAULA RODRIGUES - 29/07/2025")
        print("=" * 60)
        
        # Buscar registro específico Ana Paula
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 29),
            RegistroPonto.hora_entrada == time(7, 30),
            RegistroPonto.hora_saida == time(18, 0)
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado!")
            return
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        print(f"📋 ANTES DA CORREÇÃO:")
        print(f"   Funcionário: {funcionario.nome}")
        print(f"   Horários: {registro.hora_entrada} - {registro.hora_saida}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}h")
        print(f"   Horas extras: {registro.horas_extras}h")
        print(f"   Atrasos: {registro.total_atraso_horas}h")
        
        # LÓGICA CORRETA
        horario_entrada_padrao = time(7, 12)  # 07:12
        horario_saida_padrao = time(17, 0)    # 17:00
        
        print(f"\n🔧 APLICANDO LÓGICA CORRETA:")
        print(f"   Padrão: {horario_entrada_padrao} - {horario_saida_padrao}")
        print(f"   Real: {registro.hora_entrada} - {registro.hora_saida}")
        
        # Converter para minutos
        entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute      # 07:30 = 450min
        saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute            # 18:00 = 1080min
        entrada_padrao_min = horario_entrada_padrao.hour * 60 + horario_entrada_padrao.minute  # 07:12 = 432min
        saida_padrao_min = horario_saida_padrao.hour * 60 + horario_saida_padrao.minute        # 17:00 = 1020min
        
        # CALCULAR ATRASO DE ENTRADA (chegou depois do horário)
        atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)  # 450 - 432 = 18min
        
        # CALCULAR HORAS EXTRAS DE SAÍDA (saiu depois do horário)
        extras_saida_min = max(0, saida_real_min - saida_padrao_min)        # 1080 - 1020 = 60min
        
        # CONVERTER PARA HORAS
        atraso_entrada_h = atraso_entrada_min / 60.0    # 18/60 = 0.3h
        extras_saida_h = extras_saida_min / 60.0        # 60/60 = 1.0h
        
        print(f"\n📊 CÁLCULOS:")
        print(f"   Atraso entrada: {entrada_real_min - entrada_padrao_min}min = {atraso_entrada_h}h")
        print(f"   Extras saída: {saida_real_min - saida_padrao_min}min = {extras_saida_h}h")
        
        # APLICAR CORREÇÕES
        # Atrasos
        registro.minutos_atraso_entrada = atraso_entrada_min
        registro.minutos_atraso_saida = 0  # Não saiu antes do horário
        registro.total_atraso_minutos = atraso_entrada_min
        registro.total_atraso_horas = atraso_entrada_h
        
        # Horas extras (apenas saída posterior)
        registro.horas_extras = extras_saida_h
        if registro.horas_extras > 0:
            registro.percentual_extras = 50.0
        else:
            registro.percentual_extras = 0.0
            
        # Horas trabalhadas (total menos almoço)
        total_minutos = saida_real_min - entrada_real_min - 60  # 1080 - 450 - 60 = 570min
        registro.horas_trabalhadas = total_minutos / 60.0       # 570/60 = 9.5h
        
        try:
            db.session.commit()
            
            print(f"\n✅ CORREÇÃO APLICADA:")
            print(f"   Horas trabalhadas: {registro.horas_trabalhadas}h")
            print(f"   Horas extras: {registro.horas_extras}h - {registro.percentual_extras}%")
            print(f"   Atrasos: {registro.total_atraso_horas}h")
            print(f"   ✅ DEVE MOSTRAR: 1.0h extras, 0.3h atraso")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    corrigir_ana_paula()