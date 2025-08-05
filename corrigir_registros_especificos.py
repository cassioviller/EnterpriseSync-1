#!/usr/bin/env python3
"""
🎯 CORREÇÃO ESPECÍFICA: Registros da Imagem do Usuário
07:07-17:29 = 5min + 29min = 34min extras
07:05-18:31 = 7min + 91min = 98min extras (1h38)
07:06-17:30 = 6min + 30min = 36min extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import datetime, time

def corrigir_casos_especificos():
    with app.app_context():
        print("🎯 CORREÇÃO: Casos Específicos da Imagem")
        print("=" * 55)
        
        casos = [
            {'entrada': '07:07', 'saida': '17:29', 'data': '2025-07-21', 'extras_esperados': 34},
            {'entrada': '07:05', 'saida': '18:31', 'data': '2025-07-24', 'extras_esperados': 98}, # 7+91=98min
            {'entrada': '07:06', 'saida': '17:30', 'data': '2025-07-23', 'extras_esperados': 36}, # 6+30=36min
        ]
        
        corrigidos = 0
        
        for caso in casos:
            # Buscar registro específico
            registros = RegistroPonto.query.filter(
                RegistroPonto.data == datetime.strptime(caso['data'], '%Y-%m-%d').date(),
                db.func.to_char(RegistroPonto.hora_entrada, 'HH24:MI') == caso['entrada'],
                db.func.to_char(RegistroPonto.hora_saida, 'HH24:MI') == caso['saida']
            ).all()
            
            for registro in registros:
                funcionario = Funcionario.query.get(registro.funcionario_id)
                
                if not funcionario.horario_trabalho:
                    continue
                    
                horario = funcionario.horario_trabalho
                
                # Calcular extras corretos
                entrada_real = time(*map(int, caso['entrada'].split(':')))
                saida_real = time(*map(int, caso['saida'].split(':')))
                
                entrada_real_min = entrada_real.hour * 60 + entrada_real.minute
                entrada_prev_min = horario.entrada.hour * 60 + horario.entrada.minute
                saida_real_min = saida_real.hour * 60 + saida_real.minute
                saida_prev_min = horario.saida.hour * 60 + horario.saida.minute
                
                extras_entrada = max(0, entrada_prev_min - entrada_real_min) if entrada_real < horario.entrada else 0
                extras_saida = max(0, saida_real_min - saida_prev_min) if saida_real > horario.saida else 0
                extras_total_min = extras_entrada + extras_saida
                extras_total_h = extras_total_min / 60.0
                
                print(f"\n📋 {funcionario.nome} - {caso['data']}:")
                print(f"   • Horário: {caso['entrada']}-{caso['saida']}")
                print(f"   • Padrão: {horario.entrada}-{horario.saida}")
                print(f"   • Extras entrada: {extras_entrada} min")
                print(f"   • Extras saída: {extras_saida} min")
                print(f"   • Total: {extras_total_min} min = {extras_total_h:.2f}h")
                print(f"   • Esperado: {caso['extras_esperados']} min")
                print(f"   • Antes: {registro.horas_extras}h")
                
                # Aplicar correção
                registro.horas_extras = extras_total_h
                registro.percentual_extras = 50.0 if extras_total_h > 0 else 0.0
                
                print(f"   • Após: {registro.horas_extras}h")
                print(f"   • Status: {'✅' if abs(extras_total_min - caso['extras_esperados']) <= 1 else '❌'}")
                
                corrigidos += 1
        
        db.session.commit()
        
        print(f"\n✅ CORREÇÕES FINALIZADAS: {corrigidos} registros")
        
        # Verificação final
        print(f"\n📊 VERIFICAÇÃO FINAL:")
        for caso in casos:
            registros = RegistroPonto.query.filter(
                RegistroPonto.data == datetime.strptime(caso['data'], '%Y-%m-%d').date(),
                db.func.to_char(RegistroPonto.hora_entrada, 'HH24:MI') == caso['entrada'],
                db.func.to_char(RegistroPonto.hora_saida, 'HH24:MI') == caso['saida']
            ).first()
            
            if registros:
                extras_min = registros.horas_extras * 60
                status = '✅' if abs(extras_min - caso['extras_esperados']) <= 1 else '❌'
                print(f"   • {caso['entrada']}-{caso['saida']}: {extras_min:.0f}min {status}")

if __name__ == "__main__":
    corrigir_casos_especificos()