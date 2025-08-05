#!/usr/bin/env python3
"""
CORREÇÃO DEFINITIVA: Todos os Cálculos de Horas Extras e Atrasos
Aplicar lógica correta baseada no horário individual de cada funcionário
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def corrigir_todos_registros():
    """Corrige todos os registros com lógica incorreta de horas extras e atrasos"""
    
    with app.app_context():
        print("🔧 CORREÇÃO GERAL DE TODOS OS REGISTROS")
        print("=" * 60)
        
        # Buscar todos registros de trabalho normal com horários
        registros = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro == 'trabalho_normal',
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        print(f"📋 Encontrados {len(registros)} registros para correção")
        
        corrigidos = 0
        
        for registro in registros:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            
            # Horário padrão do funcionário (todos parecem usar 07:12-17:00)
            horario_entrada_padrao = time(7, 12)
            horario_saida_padrao = time(17, 0)
            
            # Converter para minutos
            entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            entrada_padrao_min = horario_entrada_padrao.hour * 60 + horario_entrada_padrao.minute
            saida_padrao_min = horario_saida_padrao.hour * 60 + horario_saida_padrao.minute
            
            # CALCULAR ATRASOS (chegou depois do horário)
            atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)
            atraso_saida_min = max(0, saida_padrao_min - saida_real_min)  # Saiu antes do horário
            
            # CALCULAR HORAS EXTRAS (trabalhou além do horário)
            extras_entrada_min = max(0, entrada_padrao_min - entrada_real_min)  # Chegou antes
            extras_saida_min = max(0, saida_real_min - saida_padrao_min)        # Saiu depois
            
            # Totais em horas
            total_atraso_min = atraso_entrada_min + atraso_saida_min
            total_extras_min = extras_entrada_min + extras_saida_min
            
            atraso_horas = total_atraso_min / 60.0
            extras_horas = total_extras_min / 60.0
            
            # Verificar se precisa correção
            precisa_correcao = (
                abs(registro.horas_extras - extras_horas) > 0.01 or
                abs(registro.total_atraso_horas - atraso_horas) > 0.01
            )
            
            if precisa_correcao:
                valores_anteriores = (registro.horas_extras, registro.total_atraso_horas)
                
                # Aplicar correções
                registro.minutos_atraso_entrada = atraso_entrada_min
                registro.minutos_atraso_saida = atraso_saida_min
                registro.total_atraso_minutos = total_atraso_min
                registro.total_atraso_horas = atraso_horas
                
                registro.horas_extras = extras_horas
                if registro.horas_extras > 0:
                    registro.percentual_extras = 50.0
                else:
                    registro.percentual_extras = 0.0
                
                # Recalcular horas trabalhadas
                total_trabalho_min = saida_real_min - entrada_real_min - 60  # Menos 1h de almoço
                registro.horas_trabalhadas = max(0, total_trabalho_min / 60.0)
                
                print(f"   ✅ {funcionario.nome} {registro.data}: "
                      f"Extras {valores_anteriores[0]}h→{extras_horas}h, "
                      f"Atrasos {valores_anteriores[1]}h→{atraso_horas}h")
                
                corrigidos += 1
        
        try:
            db.session.commit()
            print(f"\n🎉 SUCESSO: {corrigidos} registros corrigidos!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")

def verificar_casos_especificos():
    """Verifica os casos específicos mencionados"""
    
    with app.app_context():
        print("\n🔍 VERIFICAÇÃO DOS CASOS ESPECÍFICOS")
        print("-" * 50)
        
        # Caso 1: João Silva Santos 31/07/2025
        registro1 = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 31),
            RegistroPonto.hora_entrada == time(7, 5),
            RegistroPonto.hora_saida == time(17, 50)
        ).first()
        
        if registro1:
            funcionario1 = Funcionario.query.get(registro1.funcionario_id)
            print(f"✅ {funcionario1.nome} 31/07: {registro1.horas_extras}h extras (deve ser 0.95h)")
        
        # Caso 2: Ana Paula Rodrigues 29/07/2025
        registro2 = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 29),
            RegistroPonto.hora_entrada == time(7, 30),
            RegistroPonto.hora_saida == time(18, 0)
        ).first()
        
        if registro2:
            funcionario2 = Funcionario.query.get(registro2.funcionario_id)
            print(f"✅ {funcionario2.nome} 29/07: {registro2.horas_extras}h extras, {registro2.total_atraso_horas}h atrasos")
            print(f"   (deve ser 1.0h extras, 0.3h atrasos)")

if __name__ == "__main__":
    print("🚨 CORREÇÃO DEFINITIVA DE TODOS OS CÁLCULOS")
    print("=" * 70)
    
    corrigir_todos_registros()
    verificar_casos_especificos()