#!/usr/bin/env python3
"""
🔧 APLICAÇÃO DEFINITIVA DA LÓGICA DE SÁBADO TRABALHADO
Corrige TODOS os cálculos para o registro de 05/07/2025
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def aplicar_logica_sabado_completa():
    """Aplica a lógica completa de sábado trabalhado para todos os registros"""
    print("🔧 APLICANDO LÓGICA COMPLETA DE SÁBADO TRABALHADO")
    print("=" * 60)
    
    # Buscar TODOS os registros de 05/07/2025 (sábado)
    registros = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5)
    ).all()
    
    print(f"📊 Encontrados {len(registros)} registros do dia 05/07/2025")
    
    for registro in registros:
        funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
        nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        print(f"\n🔧 PROCESSANDO: {nome}")
        print(f"   ID do registro: {registro.id}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   Entrada: {registro.hora_entrada}")
        print(f"   Saída: {registro.hora_saida}")
        
        # Se tem horários de entrada e saída registrados, aplicar lógica
        if registro.hora_entrada and registro.hora_saida and registro.horas_trabalhadas and registro.horas_trabalhadas > 0:
            print("   ✅ Registro válido com horas trabalhadas")
            
            # LÓGICA DE SÁBADO TRABALHADO:
            # 1. Tipo = sabado_horas_extras
            registro.tipo_registro = 'sabado_horas_extras'
            
            # 2. TODAS as horas trabalhadas = horas extras (50% adicional)
            horas_trabalhadas = float(registro.horas_trabalhadas)
            registro.horas_extras = horas_trabalhadas
            registro.percentual_extras = 50.0
            
            # 3. ZERO atraso (sábados não têm atraso)
            registro.total_atraso_minutos = 0
            registro.total_atraso_horas = 0.0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            
            print(f"   ✅ APLICADO:")
            print(f"      Tipo: {registro.tipo_registro}")
            print(f"      Horas extras: {registro.horas_extras}h")
            print(f"      Percentual: {registro.percentual_extras}%")
            print(f"      Atraso: {registro.total_atraso_minutos}min")
            
        else:
            print("   ⚠️  Registro sem horas válidas - mantendo como está")
            # Mesmo assim, garantir zero atraso
            registro.total_atraso_minutos = 0
            registro.total_atraso_horas = 0.0
            registro.tipo_registro = 'sabado_horas_extras'
    
    try:
        db.session.commit()
        print("\n✅ LÓGICA DE SÁBADO APLICADA COM SUCESSO!")
        return True
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        db.session.rollback()
        return False

def verificar_resultado():
    """Verifica se a lógica foi aplicada corretamente"""
    print("\n🔍 VERIFICAÇÃO DO RESULTADO")
    print("=" * 60)
    
    # Buscar o registro específico do João Silva Santos
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.funcionario_id == 96  # João Silva Santos
    ).first()
    
    if registro:
        funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
        
        print(f"📋 VERIFICAÇÃO - {funcionario.nome}:")
        print(f"   Tipo: '{registro.tipo_registro}'")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   Horas extras: {registro.horas_extras}")
        print(f"   Percentual: {registro.percentual_extras}%")
        print(f"   Atraso: {registro.total_atraso_minutos}min")
        
        # Verificar se está correto
        if (registro.tipo_registro == 'sabado_horas_extras' and 
            registro.horas_extras > 0 and 
            registro.total_atraso_minutos == 0 and
            registro.percentual_extras == 50.0):
            print("   ✅ CORRETO!")
            return True
        else:
            print("   ❌ AINDA INCORRETO!")
            return False
    else:
        print("   ❌ Registro não encontrado!")
        return False

def verificar_todos_registros():
    """Verifica todos os registros de sábado"""
    print("\n📊 VERIFICAÇÃO GERAL")
    print("=" * 60)
    
    registros = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.horas_trabalhadas > 0
    ).all()
    
    print(f"📈 Registros com horas trabalhadas: {len(registros)}")
    
    corretos = 0
    for registro in registros:
        funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
        nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        # Verificar se está correto
        if (registro.tipo_registro == 'sabado_horas_extras' and 
            registro.horas_extras > 0 and 
            registro.total_atraso_minutos == 0):
            print(f"   ✅ {nome}: {registro.horas_extras}h extras, 0min atraso")
            corretos += 1
        else:
            print(f"   ❌ {nome}: {registro.horas_extras}h extras, {registro.total_atraso_minutos}min atraso")
    
    print(f"\n📊 RESULTADO: {corretos}/{len(registros)} corretos")
    return corretos == len(registros)

if __name__ == "__main__":
    with app.app_context():
        print("🚀 CORREÇÃO DEFINITIVA DOS CÁLCULOS DE SÁBADO")
        print("=" * 80)
        
        # 1. Aplicar lógica completa
        sucesso = aplicar_logica_sabado_completa()
        
        if sucesso:
            # 2. Verificar resultado específico
            resultado_especifico = verificar_resultado()
            
            # 3. Verificar todos os registros
            resultado_geral = verificar_todos_registros()
            
            print("\n" + "=" * 80)
            if resultado_especifico and resultado_geral:
                print("🎯 CORREÇÃO 100% CONCLUÍDA!")
                print("✅ João Silva Santos 05/07/2025 deve mostrar:")
                print("   - Horas extras: 7.9h - 50%")
                print("   - Atraso: - (zero)")
                print("   - Tag: SÁBADO")
                print("\n🔄 Recarregue a página para ver as mudanças!")
            else:
                print("❌ AINDA HÁ PROBLEMAS - verificar manualmente")
        else:
            print("\n❌ FALHA NA APLICAÇÃO DA LÓGICA")
        
        print("=" * 80)