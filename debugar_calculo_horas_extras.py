#!/usr/bin/env python3
"""
🔍 DEBUG: Investigar por que horas extras estão sendo calculadas incorretamente
PROBLEMA: 34min virando 1.4h, 1h38 virando 2.4h
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import datetime, time

def debugar_calculo():
    with app.app_context():
        print("🔍 DEBUG: Cálculo de Horas Extras")
        print("=" * 50)
        
        # Buscar registro específico do dia 21/07 (07:07-17:29)
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == datetime(2025, 7, 21).date(),
            RegistroPonto.horas_extras > 0
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado")
            return
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        horario = funcionario.horario_trabalho
        
        print(f"📋 REGISTRO ANALISADO:")
        print(f"   • Funcionário: {funcionario.nome}")
        print(f"   • Data: {registro.data}")
        print(f"   • Entrada: {registro.hora_entrada}")
        print(f"   • Saída: {registro.hora_saida}")
        print(f"   • Padrão: {horario.entrada}-{horario.saida}")
        print(f"   • Horas trabalhadas: {registro.horas_trabalhadas}h")
        print(f"   • Horas extras: {registro.horas_extras}h")
        
        # CALCULAR MANUALMENTE
        entrada_real = registro.hora_entrada
        saida_real = registro.hora_saida
        entrada_padrao = horario.entrada
        saida_padrao = horario.saida
        
        # Converter para minutos
        entrada_real_min = entrada_real.hour * 60 + entrada_real.minute
        entrada_prev_min = entrada_padrao.hour * 60 + entrada_padrao.minute
        saida_real_min = saida_real.hour * 60 + saida_real.minute
        saida_prev_min = saida_padrao.hour * 60 + saida_padrao.minute
        
        # Calcular extras entrada e saída separadamente
        extras_entrada = 0
        extras_saida = 0
        
        if entrada_real < entrada_padrao:
            extras_entrada = entrada_prev_min - entrada_real_min
            
        if saida_real > saida_padrao:
            extras_saida = saida_real_min - saida_prev_min
            
        extras_total_esperado = extras_entrada + extras_saida
        
        print(f"\n🔍 CÁLCULO MANUAL:")
        print(f"   • Entrada real: {entrada_real_min} min")
        print(f"   • Entrada padrão: {entrada_prev_min} min")
        print(f"   • Extras entrada: {extras_entrada} min")
        print(f"   • Saída real: {saida_real_min} min")
        print(f"   • Saída padrão: {saida_prev_min} min")
        print(f"   • Extras saída: {extras_saida} min")
        print(f"   • Total esperado: {extras_total_esperado} min = {extras_total_esperado/60:.2f}h")
        
        # Comparar com o que está no banco
        extras_banco_min = registro.horas_extras * 60
        
        print(f"\n📊 COMPARAÇÃO:")
        print(f"   • Esperado: {extras_total_esperado} min")
        print(f"   • No banco: {extras_banco_min:.0f} min")
        print(f"   • Diferença: {abs(extras_banco_min - extras_total_esperado):.0f} min")
        
        # ANALISAR PROBLEMA
        if extras_banco_min > extras_total_esperado:
            fator = extras_banco_min / extras_total_esperado if extras_total_esperado > 0 else 0
            print(f"\n⚠️ PROBLEMA IDENTIFICADO:")
            print(f"   • Valor inflado por fator: {fator:.2f}x")
            print(f"   • Possível causa: Somando horas_trabalhadas em vez de apenas extras")

if __name__ == "__main__":
    debugar_calculo()