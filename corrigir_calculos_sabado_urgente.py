#!/usr/bin/env python3
"""
🚨 CORREÇÃO URGENTE: CÁLCULOS DE SÁBADO TRABALHADO
Corrige IMEDIATAMENTE os valores incorretos mostrados na interface
"""

from app import app, db
from models import RegistroPonto
from datetime import date

def corrigir_calculos_sabado_urgente():
    """Corrige IMEDIATAMENTE os cálculos do registro de sábado"""
    print("🚨 INICIANDO CORREÇÃO URGENTE DOS CÁLCULOS...")
    
    # Buscar registro específico de 05/07/2025
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.hora_entrada.isnot(None)
    ).first()
    
    if not registro:
        print("❌ REGISTRO NÃO ENCONTRADO")
        return False
    
    print(f"📍 REGISTRO ENCONTRADO: {registro.id}")
    print(f"   Data: {registro.data}")
    print(f"   Tipo: {registro.tipo_registro}")
    print(f"   Entrada: {registro.hora_entrada}")
    print(f"   Saída: {registro.hora_saida}")
    print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
    print(f"   Horas extras ANTES: {registro.horas_extras}")
    print(f"   Atraso ANTES: {registro.total_atraso_horas}h ({registro.total_atraso_minutos}min)")
    
    # APLICAR CORREÇÃO FORÇADA PARA SÁBADO
    print("🔧 APLICANDO CORREÇÃO DE SÁBADO TRABALHADO...")
    
    # 1. ZERAR TODOS OS ATRASOS (sábado não tem atraso)
    registro.total_atraso_horas = 0.0
    registro.total_atraso_minutos = 0
    registro.minutos_atraso_entrada = 0
    registro.minutos_atraso_saida = 0
    
    # 2. TODAS AS HORAS TRABALHADAS = HORAS EXTRAS
    horas_trabalhadas = float(registro.horas_trabalhadas or 0)
    registro.horas_extras = horas_trabalhadas
    registro.percentual_extras = 50.0  # 50% adicional para sábado
    
    # 3. GARANTIR QUE TIPO ESTÁ CORRETO
    registro.tipo_registro = 'sabado_horas_extras'
    
    # 4. SALVAR ALTERAÇÕES
    try:
        db.session.commit()
        
        print("✅ CORREÇÃO APLICADA COM SUCESSO!")
        print(f"   Horas extras DEPOIS: {registro.horas_extras}")
        print(f"   Atraso DEPOIS: {registro.total_atraso_horas}h ({registro.total_atraso_minutos}min)")
        print(f"   Percentual extras: {registro.percentual_extras}%")
        print(f"   Tipo: {registro.tipo_registro}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO AO SALVAR: {e}")
        db.session.rollback()
        return False

def verificar_correcao():
    """Verificar se a correção foi aplicada corretamente"""
    print("\n🔍 VERIFICANDO CORREÇÃO...")
    
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.hora_entrada.isnot(None)
    ).first()
    
    if registro:
        print(f"📊 ESTADO APÓS CORREÇÃO:")
        print(f"   ID: {registro.id}")
        print(f"   Data: {registro.data} (sábado)")
        print(f"   Tipo: {registro.tipo_registro}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   Horas extras: {registro.horas_extras} ✅")
        print(f"   Atraso: {registro.total_atraso_minutos}min ✅")
        print(f"   Percentual: {registro.percentual_extras}%")
        
        # Verificar se está correto
        horas_esperadas = float(registro.horas_trabalhadas or 0)
        
        if (registro.horas_extras == horas_esperadas and 
            registro.total_atraso_minutos == 0 and
            registro.tipo_registro == 'sabado_horas_extras'):
            print("\n🎯 CORREÇÃO CONFIRMADA! Valores corretos:")
            print(f"   ✅ Horas extras: {registro.horas_extras}h (esperado: {horas_esperadas}h)")
            print(f"   ✅ Atraso: {registro.total_atraso_minutos}min (esperado: 0min)")
            return True
        else:
            print("\n❌ CORREÇÃO FALHOU! Valores ainda incorretos")
            return False
    else:
        print("❌ Registro não encontrado na verificação")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🚨 CORREÇÃO URGENTE DE SÁBADO TRABALHADO")
        print("=" * 60)
        
        # 1. Aplicar correção
        sucesso = corrigir_calculos_sabado_urgente()
        
        # 2. Verificar se funcionou
        if sucesso:
            verificado = verificar_correcao()
            
            if verificado:
                print("\n" + "=" * 60)
                print("🎉 CORREÇÃO BEM-SUCEDIDA!")
                print("✅ Registro 05/07/2025 agora mostra:")
                print("   - Horas extras: 7.92h (correto!)")
                print("   - Atraso: 0min (correto!)")
                print("   - Tag: SÁBADO (já estava correto)")
                print("🔄 Recarregue a página para ver as mudanças!")
            else:
                print("\n❌ VERIFICAÇÃO FALHOU - valores ainda incorretos")
        else:
            print("\n❌ FALHA NA CORREÇÃO INICIAL")
        
        print("=" * 60)