#!/usr/bin/env python3
"""
🎯 CORREÇÃO: Entrada Antecipada Como Horas Extras
CENÁRIO: 07:07-17:29 vs padrão 07:12-17:00
EXTRAS: 5min (entrada antecipada) + 29min (saída posterior) = 34min total
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import datetime

def corrigir_entrada_antecipada():
    with app.app_context():
        print("🎯 CORREÇÃO: Entrada Antecipada = Horas Extras")
        print("=" * 55)
        
        # Buscar registro específico da imagem: 21/07/2025, 07:07-17:29
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == datetime(2025, 7, 21).date()
        ).filter(
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado")
            return
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        horario = funcionario.horario_trabalho
        
        print(f"📋 SITUAÇÃO ENCONTRADA:")
        print(f"   • Funcionário: {funcionario.nome}")
        print(f"   • Data: {registro.data}")
        print(f"   • Entrada real: {registro.hora_entrada}")
        print(f"   • Saída real: {registro.hora_saida}")
        print(f"   • Horário padrão: {horario.entrada}-{horario.saida}")
        
        # CALCULAR EXTRAS MANUALMENTE
        entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
        entrada_prev_min = horario.entrada.hour * 60 + horario.entrada.minute
        saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
        saida_prev_min = horario.saida.hour * 60 + horario.saida.minute
        
        extras_entrada = 0
        extras_saida = 0
        
        # Entrada antecipada
        if registro.hora_entrada < horario.entrada:
            extras_entrada = entrada_prev_min - entrada_real_min
            
        # Saída posterior
        if registro.hora_saida > horario.saida:
            extras_saida = saida_real_min - saida_prev_min
            
        extras_total_min = extras_entrada + extras_saida
        
        print(f"\n🔍 CÁLCULO CORRETO:")
        print(f"   • Entrada antecipada: {extras_entrada} min")
        print(f"   • Saída posterior: {extras_saida} min")
        print(f"   • Total extras: {extras_total_min} min = {extras_total_min/60:.2f}h")
        
        # Aplicar nova lógica usando o engine
        engine = KPIsEngine()
        engine.calcular_e_atualizar_ponto(registro.id)
        
        # Recarregar registro
        db.session.refresh(registro)
        
        print(f"\n✅ RESULTADO APÓS CORREÇÃO:")
        print(f"   • Horas extras: {registro.horas_extras}h ({registro.horas_extras * 60:.0f} min)")
        print(f"   • Percentual: {registro.percentual_extras}%")
        
        # VALIDAÇÃO
        esperado_h = extras_total_min / 60.0
        correto = abs(registro.horas_extras - esperado_h) < 0.01
        
        print(f"\n🎯 VALIDAÇÃO:")
        print(f"   • Esperado: {esperado_h:.2f}h")
        print(f"   • Calculado: {registro.horas_extras}h")
        print(f"   • Correto: {'✅' if correto else '❌'}")
        
        if registro.hora_entrada.hour == 7 and registro.hora_entrada.minute == 7:
            print(f"   • Caso específico 07:07-17:29: {'✅' if correto else '❌'}")

if __name__ == "__main__":
    corrigir_entrada_antecipada()