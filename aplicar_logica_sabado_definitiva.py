#!/usr/bin/env python3
"""
🎯 APLICAÇÃO DEFINITIVA: Lógica Correta Atrasos vs Horas Extras
Ana Paula - 29/07/2025: 07:30 entrada, 18:00 saída
Padrão Comercial Vale Verde: 07:12-17:00
RESULTADO: 18min atraso + 1h extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import datetime, time

def aplicar_logica_definitiva():
    with app.app_context():
        print("🎯 APLICAÇÃO: Lógica Definitiva Ana Paula 29/07/2025")
        print("=" * 60)
        
        # Buscar Ana Paula
        ana_paula = Funcionario.query.filter(Funcionario.nome.ilike('%Ana Paula%')).first()
        
        # Buscar registro do dia 29/07
        registro = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == ana_paula.id,
            RegistroPonto.data == datetime(2025, 7, 29).date()
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado")
            return
            
        print(f"📋 SITUAÇÃO ATUAL:")
        print(f"   • Horário padrão: {ana_paula.horario_trabalho.nome}")
        print(f"   • Entrada padrão: {ana_paula.horario_trabalho.entrada}")
        print(f"   • Saída padrão: {ana_paula.horario_trabalho.saida}")
        print(f"   • Entrada real: {registro.hora_entrada}")
        print(f"   • Saída real: {registro.hora_saida}")
        
        # APLICAR LÓGICA CORRETA
        # Horário Comercial Vale Verde: 07:12-17:00
        entrada_padrao = ana_paula.horario_trabalho.entrada  # 07:12
        saida_padrao = ana_paula.horario_trabalho.saida      # 17:00
        
        # CALCULAR ATRASO (entrada)
        if registro.hora_entrada > entrada_padrao:
            entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            entrada_prev_min = entrada_padrao.hour * 60 + entrada_padrao.minute
            atraso_min = entrada_real_min - entrada_prev_min
        else:
            atraso_min = 0
            
        # CALCULAR HORAS EXTRAS (saída)
        if registro.hora_saida > saida_padrao:
            saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            saida_prev_min = saida_padrao.hour * 60 + saida_padrao.minute
            extras_min = saida_real_min - saida_prev_min
        else:
            extras_min = 0
            
        print(f"\n🔍 CÁLCULOS:")
        print(f"   • Entrada: {registro.hora_entrada} vs {entrada_padrao}")
        print(f"   • Atraso: {atraso_min} min = {atraso_min/60:.2f}h")
        print(f"   • Saída: {registro.hora_saida} vs {saida_padrao}")
        print(f"   • Extras: {extras_min} min = {extras_min/60:.2f}h")
        
        # APLICAR CORREÇÕES
        registro.minutos_atraso_entrada = atraso_min
        registro.total_atraso_minutos = atraso_min
        registro.total_atraso_horas = atraso_min / 60.0
        registro.horas_extras = extras_min / 60.0
        registro.percentual_extras = 50.0 if extras_min > 0 else 0.0
        
        # Recalcular horas trabalhadas
        entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
        saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
        almoco_min = 60  # 1 hora
        total_min = saida_min - entrada_min - almoco_min
        registro.horas_trabalhadas = total_min / 60.0
        
        db.session.commit()
        
        print(f"\n✅ RESULTADO FINAL:")
        print(f"   • Atraso: {registro.minutos_atraso_entrada} min")
        print(f"   • Horas extras: {registro.horas_extras} h")
        print(f"   • Horas trabalhadas: {registro.horas_trabalhadas} h")
        
        # VALIDAÇÃO
        atraso_ok = registro.minutos_atraso_entrada == 18
        extras_ok = registro.horas_extras == 1.0
        
        print(f"\n🎯 VALIDAÇÃO:")
        print(f"   • 18min atraso: {'✅' if atraso_ok else '❌'}")
        print(f"   • 1h extras: {'✅' if extras_ok else '❌'}")
        print(f"   • Lógica correta: {'✅' if atraso_ok and extras_ok else '❌'}")

if __name__ == "__main__":
    aplicar_logica_definitiva()