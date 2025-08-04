#!/usr/bin/env python3
"""
🔧 CORREÇÃO URGENTE: Horas extras de sábado não aparecendo nos KPIs
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def corrigir_horas_extras_sabado():
    """Corrigir registros de sábado que têm horas_trabalhadas mas horas_extras = 0"""
    print("🔧 CORREÇÃO: Horas Extras de Sábado")
    print("=" * 60)
    
    # Buscar todos os registros de sábado com horas trabalhadas mas sem horas extras
    registros_problema = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.horas_trabalhadas > 0,
        (RegistroPonto.horas_extras == 0) | (RegistroPonto.horas_extras.is_(None))
    ).all()
    
    print(f"📊 REGISTROS COM PROBLEMA: {len(registros_problema)}")
    
    if len(registros_problema) == 0:
        print("✅ Não há registros com problema")
        return
    
    # Mostrar registros com problema
    for registro in registros_problema[:10]:  # Mostrar apenas os primeiros 10
        funcionario = Funcionario.query.get(registro.funcionario_id)
        print(f"   {registro.data} | {funcionario.nome if funcionario else 'N/A'} | "
              f"Trab: {registro.horas_trabalhadas:.1f}h | Extras: {registro.horas_extras or 0:.1f}h")
    
    # Corrigir: em sábado, horas trabalhadas = horas extras
    print(f"\n🔧 APLICANDO CORREÇÃO...")
    registros_corrigidos = 0
    
    for registro in registros_problema:
        # Em sábado, todas as horas são extras
        registro.horas_extras = registro.horas_trabalhadas
        registro.percentual_extras = 50.0  # 50% adicional conforme legislação
        registros_corrigidos += 1
    
    # Salvar as mudanças
    db.session.commit()
    
    print(f"✅ CORREÇÃO APLICADA:")
    print(f"   Registros corrigidos: {registros_corrigidos}")
    print(f"   Lógica aplicada: horas_extras = horas_trabalhadas em sábados")
    print(f"   Percentual definido: 50% adicional")
    
    return registros_corrigidos

def verificar_funcionario_especifico():
    """Verificar funcionário específico com salário 2153.26"""
    print(f"\n🔍 VERIFICAÇÃO: Funcionário Salário R$ 2.153,26")
    print("=" * 60)
    
    # Buscar funcionário
    funcionario = Funcionario.query.filter(
        Funcionario.salario == 2153.26
    ).first()
    
    if not funcionario:
        print("❌ Funcionário não encontrado")
        return
    
    print(f"👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
    
    # Buscar registros de julho 2025
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras > 0
    ).all()
    
    print(f"\n📊 REGISTROS COM HORAS EXTRAS ({len(registros)}):")
    total_extras = 0
    for registro in registros:
        print(f"   {registro.data} | {registro.tipo_registro} | "
              f"Trab: {registro.horas_trabalhadas:.1f}h | Extras: {registro.horas_extras:.1f}h")
        total_extras += registro.horas_extras or 0
    
    print(f"\n📈 TOTAL HORAS EXTRAS: {total_extras:.1f}h")
    
    return funcionario, total_extras

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO URGENTE - HORAS EXTRAS SÁBADO")
        print("=" * 80)
        
        # 1. Corrigir registros de sábado
        corrigidos = corrigir_horas_extras_sabado()
        
        # 2. Verificar funcionário específico
        funcionario, total = verificar_funcionario_especifico()
        
        if funcionario:
            print(f"\n🎯 RESULTADO:")
            print(f"   Funcionário: {funcionario.nome}")
            print(f"   Total horas extras após correção: {total:.1f}h")
            print(f"   Status: {'✅ CORRETO' if total > 7 else '❌ AINDA COM PROBLEMA'}")
        
        print(f"\n⚠️  IMPORTANTE:")
        print(f"   Reiniciar servidor para aplicar mudanças nos KPIs")
        print(f"   Refresh na página para ver os novos valores")