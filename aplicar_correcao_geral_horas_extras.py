#!/usr/bin/env python3
"""
CORREÇÃO DEFINITIVA: Horas Extras Baseadas no Horário Individual
Corrigir cálculo de horas extras para usar antecipação + prolongamento
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, datetime, time

def encontrar_registro_correto():
    """Encontra e corrige o registro específico mencionado"""
    
    with app.app_context():
        print("🔍 BUSCANDO REGISTRO 31/07/2025 07:05-17:50")
        print("=" * 60)
        
        # Buscar registro específico
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 31),
            RegistroPonto.hora_entrada == time(7, 5),
            RegistroPonto.hora_saida == time(17, 50)
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado!")
            return None
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        print(f"📋 REGISTRO ENCONTRADO:")
        print(f"   Funcionário: {funcionario.nome}")
        print(f"   Data: {registro.data}")
        print(f"   Entrada: {registro.hora_entrada}")
        print(f"   Saída: {registro.hora_saida}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}h")
        print(f"   Horas extras atual: {registro.horas_extras}h")
        
        return registro, funcionario

def aplicar_correcao_logica(registro, funcionario):
    """Aplica a correção de horas extras baseada na lógica correta"""
    
    print(f"\n🔧 APLICANDO CORREÇÃO DE LÓGICA")
    print("-" * 50)
    
    # Horário padrão do funcionário
    horario_entrada = getattr(funcionario, 'horario_entrada', None) or time(7, 12)  # 07:12 padrão
    horario_saida = getattr(funcionario, 'horario_saida', None) or time(17, 0)      # 17:00 padrão
    
    print(f"📅 Horário padrão: {horario_entrada} - {horario_saida}")
    print(f"📅 Horário real: {registro.hora_entrada} - {registro.hora_saida}")
    
    # Converter para minutos para cálculo preciso
    def time_to_minutes(t):
        return t.hour * 60 + t.minute
    
    entrada_padrao_min = time_to_minutes(horario_entrada)
    saida_padrao_min = time_to_minutes(horario_saida)
    entrada_real_min = time_to_minutes(registro.hora_entrada)
    saida_real_min = time_to_minutes(registro.hora_saida)
    
    # Calcular antecipação de entrada (07:12 - 07:05 = 7 minutos)
    antecipacao_min = max(0, entrada_padrao_min - entrada_real_min)
    
    # Calcular prolongamento de saída (17:50 - 17:00 = 50 minutos)
    prolongamento_min = max(0, saida_real_min - saida_padrao_min)
    
    # Total de horas extras em minutos
    total_extras_min = antecipacao_min + prolongamento_min
    
    # Converter para horas decimais
    horas_extras_corretas = total_extras_min / 60.0
    
    print(f"\n📊 CÁLCULOS:")
    print(f"   Antecipação entrada: {entrada_padrao_min - entrada_real_min}min")
    print(f"   Prolongamento saída: {saida_real_min - saida_padrao_min}min")
    print(f"   Total extras: {total_extras_min}min = {horas_extras_corretas:.2f}h")
    
    # Aplicar correção
    valor_anterior = registro.horas_extras
    registro.horas_extras = round(horas_extras_corretas, 2)
    
    print(f"\n✅ CORREÇÃO APLICADA:")
    print(f"   Antes: {valor_anterior}h")
    print(f"   Depois: {registro.horas_extras}h")
    
    return registro

def aplicar_correcao_geral():
    """Aplica a correção para todos os registros com horas extras incorretas"""
    
    with app.app_context():
        print("\n🔧 APLICANDO CORREÇÃO GERAL")
        print("=" * 60)
        
        # Buscar todos os registros com horas extras > 0
        registros = RegistroPonto.query.filter(
            RegistroPonto.horas_extras > 0,
            RegistroPonto.tipo_registro.in_(['trabalho_normal', 'trabalho_meio_periodo'])
        ).all()
        
        print(f"📋 Encontrados {len(registros)} registros com horas extras")
        
        corrigidos = 0
        
        for registro in registros:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            
            # Horário padrão do funcionário
            horario_entrada = getattr(funcionario, 'horario_entrada', None) or time(7, 12)
            horario_saida = getattr(funcionario, 'horario_saida', None) or time(17, 0)
            
            # Calcular horas extras corretas
            def time_to_minutes(t):
                return t.hour * 60 + t.minute
            
            entrada_padrao_min = time_to_minutes(horario_entrada)
            saida_padrao_min = time_to_minutes(horario_saida)
            entrada_real_min = time_to_minutes(registro.hora_entrada)
            saida_real_min = time_to_minutes(registro.hora_saida)
            
            antecipacao_min = max(0, entrada_padrao_min - entrada_real_min)
            prolongamento_min = max(0, saida_real_min - saida_padrao_min)
            total_extras_min = antecipacao_min + prolongamento_min
            horas_extras_corretas = total_extras_min / 60.0
            
            # Aplicar correção se diferente
            if abs(registro.horas_extras - horas_extras_corretas) > 0.01:
                valor_anterior = registro.horas_extras
                registro.horas_extras = round(horas_extras_corretas, 2)
                
                print(f"   ✅ {funcionario.nome} {registro.data}: {valor_anterior}h → {registro.horas_extras}h")
                corrigidos += 1
        
        try:
            db.session.commit()
            print(f"\n🎉 SUCESSO: {corrigidos} registros corrigidos!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")

if __name__ == "__main__":
    print("🚨 CORREÇÃO DE HORAS EXTRAS - LÓGICA INDIVIDUAL")
    print("=" * 70)
    
    # Encontrar e corrigir registro específico
    resultado = encontrar_registro_correto()
    
    if resultado:
        registro, funcionario = resultado
        registro_corrigido = aplicar_correcao_logica(registro, funcionario)
        
        # Confirmar correção geral
        resposta = input("\n❓ Aplicar correção para TODOS os registros? (s/n): ")
        
        if resposta.lower() == 's':
            aplicar_correcao_geral()
        else:
            # Salvar apenas o registro específico
            try:
                db.session.commit()
                print("✅ Registro específico corrigido!")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro: {str(e)}")
    else:
        print("\n⚠️ Aplicando correção geral...")
        aplicar_correcao_geral()