#!/usr/bin/env python3
"""
🎯 RECÁLCULO GERAL: Corrigir todos os registros com horas extras incorretas
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import datetime

def recalcular_todos():
    with app.app_context():
        print("🎯 RECÁLCULO: Todos os Registros Problemáticos")
        print("=" * 55)
        
        # Buscar todos os registros com horas extras > 0
        registros_problematicos = RegistroPonto.query.filter(
            RegistroPonto.horas_extras > 0,
            RegistroPonto.data >= datetime(2025, 7, 20).date(),
            RegistroPonto.data <= datetime(2025, 7, 25).date()
        ).all()
        
        print(f"📊 ENCONTRADOS: {len(registros_problematicos)} registros")
        
        correcoes = 0
        
        for registro in registros_problematicos:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            
            if not funcionario.horario_trabalho:
                continue
                
            # Só corrigir tipos normais
            tipos_especiais = ['sabado_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']
            if registro.tipo_registro in tipos_especiais:
                continue
                
            horario = funcionario.horario_trabalho
            
            # Calcular extras corretos
            entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute if registro.hora_entrada else 0
            entrada_prev_min = horario.entrada.hour * 60 + horario.entrada.minute
            saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute if registro.hora_saida else 0
            saida_prev_min = horario.saida.hour * 60 + horario.saida.minute
            
            extras_entrada = 0
            extras_saida = 0
            
            # Entrada antecipada
            if registro.hora_entrada and registro.hora_entrada < horario.entrada:
                extras_entrada = entrada_prev_min - entrada_real_min
                
            # Saída posterior
            if registro.hora_saida and registro.hora_saida > horario.saida:
                extras_saida = saida_real_min - saida_prev_min
                
            extras_corretos = (extras_entrada + extras_saida) / 60.0
            
            # Só corrigir se estiver diferente
            if abs(registro.horas_extras - extras_corretos) > 0.01:
                print(f"   • {funcionario.nome} {registro.data}: {registro.horas_extras}h → {extras_corretos:.2f}h")
                registro.horas_extras = extras_corretos
                registro.percentual_extras = 50.0 if extras_corretos > 0 else 0.0
                correcoes += 1
        
        db.session.commit()
        
        print(f"\n✅ CORREÇÕES APLICADAS: {correcoes} registros")
        
        # Verificar resultado
        print(f"\n📋 VERIFICAÇÃO PÓS-CORREÇÃO:")
        registros_pos = RegistroPonto.query.filter(
            RegistroPonto.data.in_([datetime(2025, 7, 21).date(), datetime(2025, 7, 23).date(), datetime(2025, 7, 24).date()]),
            RegistroPonto.horas_extras > 0
        ).count()
        
        print(f"   • Registros com extras restantes: {registros_pos}")

if __name__ == "__main__":
    recalcular_todos()