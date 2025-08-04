#!/usr/bin/env python3
"""
🔧 CORREÇÃO FINAL: Converter todos os registros de sábado para o tipo correto
Aplicar lógica: horas extras = horas trabalhadas, atraso = 0
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def corrigir_todos_sabados():
    """Corrige todos os registros de sábado"""
    print("🔧 CORREÇÃO FINAL DOS REGISTROS DE SÁBADO")
    print("=" * 60)
    
    # 1. Converter sabado_horas_extras para sabado_trabalhado
    registros_antigos = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro == 'sabado_horas_extras'
    ).all()
    
    print(f"📊 Encontrados {len(registros_antigos)} registros com tipo antigo")
    
    for registro in registros_antigos:
        registro.tipo_registro = 'sabado_trabalhado'
        print(f"   ✅ ID {registro.id}: convertido para sabado_trabalhado")
    
    # 2. Aplicar lógica para todos os registros de sábado
    todos_sabados = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado'
    ).all()
    
    print(f"\n🔧 Aplicando lógica em {len(todos_sabados)} registros de sábado:")
    
    for registro in todos_sabados:
        funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
        nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        if registro.horas_trabalhadas and registro.horas_trabalhadas > 0:
            # LÓGICA: horas extras = horas trabalhadas
            registro.horas_extras = float(registro.horas_trabalhadas)
            registro.percentual_extras = 50.0
        else:
            registro.horas_extras = 0.0
            registro.percentual_extras = 0.0
        
        # SEMPRE zero atraso
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        
        if registro.horas_trabalhadas and registro.horas_trabalhadas > 0:
            print(f"   ✅ {nome}: {registro.horas_extras:.1f}h extras, 0min atraso")
    
    try:
        db.session.commit()
        print(f"\n✅ CORREÇÃO APLICADA EM {len(todos_sabados)} REGISTROS!")
        return True
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        db.session.rollback()
        return False

def verificar_joao_silva():
    """Verificação específica do João Silva Santos"""
    print("\n🎯 VERIFICAÇÃO ESPECÍFICA - João Silva Santos:")
    
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.funcionario_id == 96
    ).first()
    
    if registro:
        print(f"   Tipo: '{registro.tipo_registro}'")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas:.1f}h")
        print(f"   Horas extras: {registro.horas_extras:.1f}h")
        print(f"   Atraso: {registro.total_atraso_minutos}min")
        
        # Verificar se está correto
        if (registro.tipo_registro == 'sabado_trabalhado' and 
            registro.horas_extras == registro.horas_trabalhadas and 
            registro.total_atraso_minutos == 0):
            print("   ✅ TUDO CORRETO!")
            print(f"   📋 Vai exibir: {registro.horas_trabalhadas:.1f}h - 50%")
            print(f"   📋 Atraso: -")
            return True
        else:
            print("   ❌ AINDA INCORRETO!")
            return False
    else:
        print("   ❌ Registro não encontrado!")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🚀 CORREÇÃO FINAL DOS SÁBADOS")
        print("=" * 80)
        
        # 1. Corrigir todos os registros
        sucesso = corrigir_todos_sabados()
        
        if sucesso:
            # 2. Verificar João Silva especificamente
            correto = verificar_joao_silva()
            
            print("\n" + "=" * 80)
            if correto:
                print("🎯 CORREÇÃO 100% CONCLUÍDA!")
                print("✅ Tipo correto: sabado_trabalhado")
                print("✅ Template atualizado para ambos os tipos")
                print("✅ Lógica aplicada: horas extras = horas trabalhadas")
                print("✅ Atraso sempre zero em sábados")
                print("\n🔄 Recarregue a página (Ctrl+Shift+R) para ver!")
            else:
                print("❌ AINDA HÁ PROBLEMAS!")
        else:
            print("\n❌ FALHA NA CORREÇÃO!")
        
        print("=" * 80)