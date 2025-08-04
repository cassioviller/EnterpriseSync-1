#!/usr/bin/env python3
"""
🔧 APLICAÇÃO URGENTE: Lógica específica para sábado trabalhado
Força horas extras = horas trabalhadas e atraso = 0
"""

from app import app, db
from models import RegistroPonto
from datetime import date

def aplicar_logica_sabado_urgente():
    """Aplica lógica urgente para sábado trabalhado"""
    print("🔧 APLICANDO LÓGICA URGENTE DE SÁBADO TRABALHADO")
    print("=" * 60)
    
    # Atualizar TODOS os registros de sábado trabalhado
    registros_sabado = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro == 'sabado_horas_extras'
    ).all()
    
    print(f"📊 Encontrados {len(registros_sabado)} registros de sábado")
    
    for registro in registros_sabado:
        print(f"\n🔧 Processando registro ID {registro.id}:")
        print(f"   Data: {registro.data}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
        
        if registro.horas_trabalhadas and registro.horas_trabalhadas > 0:
            # LÓGICA ESPECÍFICA: horas extras = horas trabalhadas
            registro.horas_extras = float(registro.horas_trabalhadas)
            registro.percentual_extras = 50.0
            print(f"   ✅ Horas extras definidas: {registro.horas_extras}h")
        else:
            registro.horas_extras = 0.0
            registro.percentual_extras = 0.0
            print(f"   📝 Sem horas trabalhadas - extras = 0")
        
        # SEMPRE zero atraso em sábado
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        
        print(f"   ✅ Atraso: {registro.total_atraso_minutos}min")
    
    try:
        db.session.commit()
        print(f"\n✅ LÓGICA APLICADA EM {len(registros_sabado)} REGISTROS!")
        return True
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    with app.app_context():
        sucesso = aplicar_logica_sabado_urgente()
        
        if sucesso:
            print("\n🎯 TESTE ESPECÍFICO - João Silva Santos 05/07/2025:")
            
            # Verificar registro específico
            registro = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 5),
                RegistroPonto.funcionario_id == 96,
                RegistroPonto.tipo_registro == 'sabado_horas_extras'
            ).first()
            
            if registro:
                print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
                print(f"   Horas extras: {registro.horas_extras}")
                print(f"   Atraso: {registro.total_atraso_minutos}min")
                print(f"   Percentual: {registro.percentual_extras}%")
                
                esperado_extras = registro.horas_trabalhadas
                
                if (registro.horas_extras == esperado_extras and 
                    registro.total_atraso_minutos == 0):
                    print("   ✅ DADOS CORRETOS APLICADOS!")
                    print(f"   📋 Template deve mostrar: {esperado_extras:.1f}h - 50%")
                    print(f"   📋 Atraso deve mostrar: -")
                else:
                    print("   ❌ AINDA INCORRETO!")
            else:
                print("   ❌ Registro não encontrado!")
        
        print("\n🔄 RECARREGUE A PÁGINA PARA VER AS MUDANÇAS!")