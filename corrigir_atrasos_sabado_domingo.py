#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CORREÇÃO: Atrasos em Sábado/Domingo/Feriado Trabalhado

Em trabalho de fim de semana e feriados, todas as horas são extras,
portanto não existe conceito de atraso. Este script corrige registros
existentes zerando atrasos incorretamente calculados.
"""

import sys
import os
sys.path.append('.')

from app import app, db
from models import RegistroPonto
from datetime import datetime

def corrigir_atrasos_tipos_especiais():
    """Zera atrasos para tipos onde toda hora é extra"""
    
    with app.app_context():
        print("🔧 CORREÇÃO DE ATRASOS - Sábado/Domingo/Feriado")
        print("=" * 50)
        
        # Buscar registros dos tipos especiais que têm atrasos calculados
        tipos_especiais = ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']
        
        registros_para_corrigir = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro.in_(tipos_especiais),
            RegistroPonto.total_atraso_minutos > 0
        ).all()
        
        print(f"📊 Registros encontrados para correção: {len(registros_para_corrigir)}")
        
        if not registros_para_corrigir:
            print("✅ Nenhuma correção necessária!")
            return
        
        # Listar registros antes da correção
        print("\n📋 REGISTROS ANTES DA CORREÇÃO:")
        for reg in registros_para_corrigir:
            print(f"  • {reg.data} - {reg.funcionario.nome} - {reg.tipo_registro}")
            print(f"    Atraso atual: {reg.total_atraso_minutos}min ({reg.total_atraso_horas:.2f}h)")
        
        # Aplicar correções
        corrigidos = 0
        for registro in registros_para_corrigir:
            # Zerar todos os campos de atraso
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            registro.total_atraso_minutos = 0
            registro.total_atraso_horas = 0.0
            corrigidos += 1
        
        # Salvar mudanças
        try:
            db.session.commit()
            print(f"\n✅ {corrigidos} registros corrigidos com sucesso!")
            
            # Verificar resultados
            print("\n📊 VERIFICAÇÃO PÓS-CORREÇÃO:")
            registros_verificacao = RegistroPonto.query.filter(
                RegistroPonto.tipo_registro.in_(tipos_especiais),
                RegistroPonto.total_atraso_minutos > 0
            ).all()
            
            if not registros_verificacao:
                print("✅ Todos os atrasos de tipos especiais foram zerados!")
            else:
                print(f"⚠️  Ainda existem {len(registros_verificacao)} registros com atraso")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao salvar correções: {e}")

def verificar_regra_aplicada():
    """Verifica se a regra está sendo aplicada corretamente"""
    
    with app.app_context():
        print("\n🔍 VERIFICAÇÃO DA REGRA:")
        print("=" * 30)
        
        # Contar registros por tipo
        tipos_especiais = ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']
        
        for tipo in tipos_especiais:
            total_registros = RegistroPonto.query.filter(
                RegistroPonto.tipo_registro == tipo
            ).count()
            
            com_atraso = RegistroPonto.query.filter(
                RegistroPonto.tipo_registro == tipo,
                RegistroPonto.total_atraso_minutos > 0
            ).count()
            
            print(f"📌 {tipo.replace('_', ' ').title()}:")
            print(f"   Total de registros: {total_registros}")
            print(f"   Com atraso: {com_atraso}")
            print(f"   ✅ Corretos: {total_registros - com_atraso}")

if __name__ == "__main__":
    print("🚀 INICIANDO CORREÇÃO DE ATRASOS")
    print("Data/Hora:", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    print()
    
    corrigir_atrasos_tipos_especiais()
    verificar_regra_aplicada()
    
    print("\n🎯 REGRA IMPLEMENTADA:")
    print("   Sábado/Domingo/Feriado = ZERO atraso")
    print("   (todas as horas são extras)")
    print("\n✅ CORREÇÃO FINALIZADA!")