#!/usr/bin/env python3
"""
🚨 CORREÇÃO URGENTE: TODOS OS REGISTROS DE SÁBADO 05/07/2025
Corrige TODOS os registros para mostrar horas extras corretas e atraso = 0
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def corrigir_todos_sabados():
    """Corrige TODOS os registros de sábado 05/07/2025"""
    print("🚨 CORREÇÃO URGENTE - TODOS OS SÁBADOS 05/07/2025")
    print("=" * 60)
    
    # Buscar TODOS os registros de 05/07/2025 com horários
    registros = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.hora_entrada.isnot(None)
    ).all()
    
    print(f"📊 ENCONTRADOS {len(registros)} REGISTROS DE SÁBADO COM HORÁRIOS")
    
    for i, registro in enumerate(registros, 1):
        funcionario = Funcionario.query.get(registro.funcionario_id)
        nome_funcionario = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        print(f"\n🔧 REGISTRO {i}/{len(registros)}: ID {registro.id}")
        print(f"   Funcionário: {nome_funcionario}")
        print(f"   Entrada: {registro.hora_entrada}")
        print(f"   Saída: {registro.hora_saida}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   Horas extras ANTES: {registro.horas_extras}")
        print(f"   Atraso ANTES: {registro.total_atraso_minutos}min")
        
        # APLICAR CORREÇÃO FORÇADA
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        
        # 1. ZERAR TODOS OS ATRASOS (sábado não tem atraso)
        registro.total_atraso_horas = 0.0
        registro.total_atraso_minutos = 0
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        
        # 2. TODAS AS HORAS = HORAS EXTRAS
        registro.horas_extras = horas_trabalhadas
        registro.percentual_extras = 50.0
        
        # 3. TIPO CORRETO
        registro.tipo_registro = 'sabado_horas_extras'
        
        print(f"   Horas extras DEPOIS: {registro.horas_extras} ✅")
        print(f"   Atraso DEPOIS: {registro.total_atraso_minutos}min ✅")
    
    try:
        db.session.commit()
        print(f"\n✅ {len(registros)} REGISTROS CORRIGIDOS COM SUCESSO!")
        return len(registros)
        
    except Exception as e:
        print(f"\n❌ ERRO AO SALVAR: {e}")
        db.session.rollback()
        return 0

def verificar_correcoes():
    """Verificar se todas as correções foram aplicadas"""
    print("\n🔍 VERIFICAÇÃO FINAL...")
    
    registros = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.hora_entrada.isnot(None)
    ).all()
    
    print(f"📊 VERIFICANDO {len(registros)} REGISTROS:")
    
    todos_corretos = True
    
    for registro in registros:
        funcionario = Funcionario.query.get(registro.funcionario_id)
        nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        horas_esperadas = float(registro.horas_trabalhadas or 0)
        
        # Verificar se está correto
        correto = (
            registro.horas_extras == horas_esperadas and
            registro.total_atraso_minutos == 0 and
            registro.tipo_registro == 'sabado_horas_extras'
        )
        
        status = "✅" if correto else "❌"
        
        print(f"   {status} {nome}: {registro.horas_extras}h extras, {registro.total_atraso_minutos}min atraso")
        
        if not correto:
            todos_corretos = False
    
    return todos_corretos

if __name__ == "__main__":
    with app.app_context():
        print("🚨 CORREÇÃO URGENTE - TODOS OS SÁBADOS")
        print("=" * 60)
        
        # 1. Corrigir todos
        quantidade = corrigir_todos_sabados()
        
        if quantidade > 0:
            # 2. Verificar
            if verificar_correcoes():
                print("\n" + "=" * 60)
                print("🎉 CORREÇÃO TOTAL BEM-SUCEDIDA!")
                print(f"✅ {quantidade} registros de sábado corrigidos")
                print("✅ PROBLEMA RESOLVIDO:")
                print("   - Horas extras: agora mostra valores corretos (ex: 7.92h)")
                print("   - Atraso: agora mostra 0min sempre")
                print("   - Tag: SÁBADO (já estava correto)")
                print("\n🔄 RECARREGUE A PÁGINA PARA VER AS MUDANÇAS!")
            else:
                print("\n❌ ALGUMAS CORREÇÕES FALHARAM")
        else:
            print("\n❌ FALHA TOTAL NA CORREÇÃO")
        
        print("=" * 60)