#!/usr/bin/env python3
"""
🚨 CORREÇÃO URGENTE: Registro de Sábado Trabalhado
Script para corrigir imediatamente o problema do registro 05/07/2025
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date
import json

def recalcular_registro_ponto(registro_id):
    """Recalcula registro aplicando lógica correta IMEDIATAMENTE"""
    registro = RegistroPonto.query.get(registro_id)
    if not registro:
        return False
    
    # FORÇAR recálculo baseado no tipo
    tipo = registro.tipo_registro
    
    print(f"🔍 RECALCULANDO: {registro.data} - Tipo: {tipo}")
    
    # SÁBADO TRABALHADO: LÓGICA ESPECIAL
    if tipo in ['sabado_trabalhado', 'sabado_horas_extras']:
        print("✅ APLICANDO LÓGICA DE SÁBADO")
        
        # ZERAR ATRASOS (sábado não tem atraso)
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        
        # TODAS AS HORAS SÃO EXTRAS
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        registro.horas_extras = horas_trabalhadas
        registro.percentual_extras = 50.0  # 50% adicional
        
        print(f"✅ RESULTADO: {horas_trabalhadas}h extras, 0h atraso")
    
    # DOMINGO TRABALHADO: LÓGICA ESPECIAL  
    elif tipo in ['domingo_trabalhado', 'domingo_horas_extras']:
        print("✅ APLICANDO LÓGICA DE DOMINGO")
        
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        registro.horas_extras = horas_trabalhadas
        registro.percentual_extras = 100.0  # 100% adicional
    
    # FERIADO TRABALHADO: LÓGICA ESPECIAL
    elif tipo == 'feriado_trabalhado':
        print("✅ APLICANDO LÓGICA DE FERIADO")
        
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        registro.horas_extras = horas_trabalhadas
        registro.percentual_extras = 100.0
    
    # SALVAR ALTERAÇÕES
    db.session.commit()
    print(f"✅ REGISTRO ATUALIZADO: {registro.data}")
    
    return True

def corrigir_registro_sabado_urgente():
    """Corrige o registro específico de 05/07/2025"""
    print("🚨 INICIANDO CORREÇÃO URGENTE...")
    
    # Buscar registro de 05/07/2025
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5)
    ).first()
    
    if registro:
        funcionario = Funcionario.query.get(registro.funcionario_id)
        print(f"📍 REGISTRO ENCONTRADO: {registro.data}")
        print(f"   Funcionário: {funcionario.nome if funcionario else 'N/A'}")
        print(f"   Tipo atual: {registro.tipo_registro}")
        print(f"   Atraso atual: {registro.total_atraso_horas}h ({registro.total_atraso_minutos}min)")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}h")
        print(f"   Horas extras: {registro.horas_extras}h")
        print(f"   Percentual extras: {registro.percentual_extras}%")
        
        # APLICAR CORREÇÃO FORÇADA
        if 'sabado' in (registro.tipo_registro or ''):
            print("🔧 APLICANDO CORREÇÃO DE SÁBADO...")
            
            # Garantir que o tipo está correto
            if registro.tipo_registro == 'trabalhado':
                registro.tipo_registro = 'sabado_horas_extras'
                print(f"   Tipo corrigido: {registro.tipo_registro}")
            
            # Aplicar lógica de sábado
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            registro.horas_extras = registro.horas_trabalhadas
            registro.percentual_extras = 50.0
            
            db.session.commit()
            
            print("✅ CORREÇÃO APLICADA!")
            print(f"   Novo atraso: {registro.total_atraso_horas}h ({registro.total_atraso_minutos}min)")
            print(f"   Novas horas extras: {registro.horas_extras}h")
            print(f"   Novo percentual: {registro.percentual_extras}%")
            
            return registro.id
        else:
            print("⚠️  Tipo de registro não é sábado")
            return None
    else:
        print("❌ REGISTRO NÃO ENCONTRADO")
        return None

def corrigir_todos_sabados():
    """Corrige todos os registros de sábado que podem ter problema"""
    print("🔄 VERIFICANDO TODOS OS SÁBADOS...")
    
    registros_sabado = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro.in_(['sabado_horas_extras', 'sabado_trabalhado'])
    ).all()
    
    corrigidos = 0
    for registro in registros_sabado:
        if registro.total_atraso_horas > 0:
            print(f"🔧 Corrigindo: {registro.data} - {registro.total_atraso_horas}h atraso")
            
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            registro.horas_extras = registro.horas_trabalhadas
            registro.percentual_extras = 50.0
            
            corrigidos += 1
    
    if corrigidos > 0:
        db.session.commit()
        print(f"✅ {corrigidos} registros de sábado corrigidos!")
    else:
        print("✅ Todos os sábados já estão corretos")
    
    return corrigidos

if __name__ == "__main__":
    with app.app_context():
        print("🚨 SISTEMA DE CORREÇÃO URGENTE - SÁBADOS")
        print("=" * 50)
        
        # Corrigir registro específico
        registro_id = corrigir_registro_sabado_urgente()
        
        print()
        
        # Corrigir todos os sábados
        total_corrigidos = corrigir_todos_sabados()
        
        print()
        print("📊 RESUMO:")
        print(f"   Registro específico: {'✅ Corrigido' if registro_id else '❌ Não encontrado'}")
        print(f"   Total de sábados corrigidos: {total_corrigidos}")
        print("=" * 50)