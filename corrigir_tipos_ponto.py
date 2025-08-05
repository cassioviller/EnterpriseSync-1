#!/usr/bin/env python3
"""
🎯 CORREÇÃO CRÍTICA: Tipos de Registro Causando Horas Extras Incorretas
PROBLEMA: Registros normais sendo tratados como especiais
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import datetime

def corrigir_tipos_registro():
    with app.app_context():
        print("🎯 CORREÇÃO: Tipos de Registro Problemáticos")
        print("=" * 55)
        
        # Buscar registro específico problemático
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == datetime(2025, 7, 21).date(),
            RegistroPonto.horas_extras == 4.0
        ).first()
        
        if not registro:
            print("❌ Registro problemático não encontrado")
            return
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        print(f"📋 REGISTRO PROBLEMÁTICO:")
        print(f"   • Funcionário: {funcionario.nome}")
        print(f"   • Data: {registro.data}")
        print(f"   • Tipo: '{registro.tipo_registro}'")
        print(f"   • Entrada: {registro.hora_entrada}")
        print(f"   • Saída: {registro.hora_saida}")
        print(f"   • Horas trabalhadas: {registro.horas_trabalhadas}h")
        print(f"   • Horas extras: {registro.horas_extras}h")
        
        # IDENTIFICAR PROBLEMA
        horario = funcionario.horario_trabalho
        entrada_padrao = horario.entrada
        saida_padrao = horario.saida
        
        # Verificar se é tipo especial que faz TODAS as horas serem extras
        tipos_especiais = ['sabado_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']
        
        print(f"\n🔍 DIAGNÓSTICO:")
        print(f"   • Tipo especial: {'Sim' if registro.tipo_registro in tipos_especiais else 'Não'}")
        print(f"   • Horário padrão: {entrada_padrao}-{saida_padrao}")
        
        if registro.tipo_registro not in tipos_especiais:
            # Calcular extras corretos manualmente
            entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            entrada_prev_min = entrada_padrao.hour * 60 + entrada_padrao.minute
            saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            saida_prev_min = saida_padrao.hour * 60 + saida_padrao.minute
            
            extras_entrada = max(0, entrada_prev_min - entrada_real_min) if registro.hora_entrada < entrada_padrao else 0
            extras_saida = max(0, saida_real_min - saida_prev_min) if registro.hora_saida > saida_padrao else 0
            extras_corretos = (extras_entrada + extras_saida) / 60.0
            
            print(f"   • Extras entrada: {extras_entrada} min")
            print(f"   • Extras saída: {extras_saida} min")
            print(f"   • Total correto: {extras_corretos:.2f}h")
            print(f"   • Atual (errado): {registro.horas_extras}h")
            
            # APLICAR CORREÇÃO
            registro.horas_extras = extras_corretos
            registro.percentual_extras = 50.0 if extras_corretos > 0 else 0.0
            db.session.commit()
            
            print(f"\n✅ CORREÇÃO APLICADA:")
            print(f"   • Horas extras: {registro.horas_extras}h")
            print(f"   • Percentual: {registro.percentual_extras}%")
        else:
            print("   • Tipo especial detectado - horas extras corretas")

if __name__ == "__main__":
    corrigir_tipos_registro()