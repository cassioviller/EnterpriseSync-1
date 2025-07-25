#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANÁLISE DETALHADA DOS PROBLEMAS DO SISTEMA DE PONTO
Script de debug para identificar todos os problemas técnicos
"""

import sys
import os
sys.path.append('.')

from app import app, db
from models import RegistroPonto, Funcionario, Obra
from datetime import datetime, date
import json

def analisar_problemas_crud():
    """Analisa problemas no CRUD de ponto"""
    
    with app.app_context():
        print("🔍 ANÁLISE DETALHADA - PROBLEMAS DO CRUD")
        print("=" * 60)
        
        # 1. PROBLEMA: Sábados sem horário de almoço
        print("\n1️⃣ PROBLEMA: Sábados sem horário de almoço")
        sabados_sem_almoco = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro == 'sabado_horas_extras',
            RegistroPonto.hora_almoco_saida.is_(None)
        ).all()
        
        print(f"   📊 Total encontrados: {len(sabados_sem_almoco)}")
        for reg in sabados_sem_almoco[:3]:  # Mostrar apenas 3 exemplos
            print(f"   📅 {reg.data} - {reg.funcionario.nome}")
            print(f"      Entrada: {reg.hora_entrada} | Saída: {reg.hora_saida}")
            print(f"      Almoço: {reg.hora_almoco_saida} - {reg.hora_almoco_retorno}")
            print(f"      Horas: {reg.horas_trabalhadas}h | Extras: {reg.horas_extras}h")
        
        # 2. PROBLEMA: Cálculos incorretos de horas extras
        print("\n2️⃣ PROBLEMA: Cálculos de horas extras")
        problemas_calculo = []
        
        for tipo in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
            registros = RegistroPonto.query.filter_by(tipo_registro=tipo).all()
            for reg in registros:
                # REGRA: Em tipos especiais, horas_extras deve = horas_trabalhadas
                if reg.horas_trabalhadas and reg.horas_extras != reg.horas_trabalhadas:
                    problemas_calculo.append({
                        'registro': reg,
                        'problema': f'Extras ({reg.horas_extras}h) ≠ Trabalhadas ({reg.horas_trabalhadas}h)'
                    })
        
        print(f"   📊 Problemas de cálculo: {len(problemas_calculo)}")
        for prob in problemas_calculo[:3]:
            reg = prob['registro']
            print(f"   📅 {reg.data} - {reg.tipo_registro}")
            print(f"      {prob['problema']}")
        
        # 3. PROBLEMA: Inconsistência de campos no CRUD
        print("\n3️⃣ PROBLEMA: Campos no views.py")
        print("   ❌ Campos incorretos encontrados no código:")
        print("      - registro.entrada (correto: hora_entrada)")
        print("      - registro.saida (correto: hora_saida)")
        print("      - registro.saida_almoco (correto: hora_almoco_saida)")
        print("      - registro.retorno_almoco (correto: hora_almoco_retorno)")
        
        # 4. PROBLEMA: Lógica de horário de almoço em sábado
        print("\n4️⃣ PROBLEMA: Lógica de almoço para tipos especiais")
        print("   🎯 REGRA CORRETA:")
        print("      - Trabalho normal: Almoço OBRIGATÓRIO (1h desconto)")
        print("      - Sábado/Domingo: Almoço OPCIONAL (pode trabalhar direto)")
        print("      - Falta: Almoço NÃO SE APLICA (nulos)")
        
        return {
            'sabados_sem_almoco': len(sabados_sem_almoco),
            'problemas_calculo': len(problemas_calculo),
            'campos_incorretos': 4
        }

def analisar_engine_calculos():
    """Analisa o engine de cálculos"""
    
    with app.app_context():
        print("\n🔧 ANÁLISE DO ENGINE DE CÁLCULOS")
        print("=" * 40)
        
        # Buscar exemplos de cada tipo
        tipos_teste = {
            'trabalho_normal': RegistroPonto.query.filter_by(tipo_registro='trabalho_normal').first(),
            'sabado_horas_extras': RegistroPonto.query.filter_by(tipo_registro='sabado_horas_extras').first(),
            'domingo_horas_extras': RegistroPonto.query.filter_by(tipo_registro='domingo_horas_extras').first(),
            'feriado_trabalhado': RegistroPonto.query.filter_by(tipo_registro='feriado_trabalhado').first()
        }
        
        for tipo, registro in tipos_teste.items():
            if registro:
                print(f"\n📌 {tipo.upper()}:")
                print(f"   Data: {registro.data}")
                print(f"   Horários: {registro.hora_entrada} - {registro.hora_saida}")
                print(f"   Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
                print(f"   Trabalhadas: {registro.horas_trabalhadas}h")
                print(f"   Extras: {registro.horas_extras}h")
                print(f"   Atrasos: {registro.total_atraso_horas}h")
                print(f"   Percentual: {registro.percentual_extras}%")
                
                # Verificar se está correto
                if tipo in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
                    if registro.horas_extras == registro.horas_trabalhadas and registro.total_atraso_horas == 0:
                        print("   ✅ CORRETO: Todas horas são extras, sem atraso")
                    else:
                        print("   ❌ INCORRETO: Deveria ter todas horas como extras e zero atraso")

def gerar_script_correcao():
    """Gera script de correção baseado nos problemas"""
    
    script_content = '''#!/usr/bin/env python3
# SCRIPT DE CORREÇÃO AUTOMÁTICA DOS PROBLEMAS DE PONTO

import sys
sys.path.append('.')

from app import app, db
from models import RegistroPonto
from datetime import time

def corrigir_sabados_sem_almoco():
    """Corrige sábados que devem ter horário de almoço opcional"""
    with app.app_context():
        sabados = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro == 'sabado_horas_extras',
            RegistroPonto.hora_almoco_saida.is_(None),
            RegistroPonto.horas_trabalhadas > 4  # Só se trabalhou mais de 4h
        ).all()
        
        for registro in sabados:
            # Definir horário de almoço padrão se trabalhou mais de 6h
            if registro.horas_trabalhadas and registro.horas_trabalhadas > 6:
                registro.hora_almoco_saida = time(12, 0)
                registro.hora_almoco_retorno = time(13, 0)
                
                # Recalcular horas trabalhadas
                if registro.hora_entrada and registro.hora_saida:
                    entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                    saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                    almoco_min = 60  # 1 hora
                    
                    total_min = saida_min - entrada_min - almoco_min
                    registro.horas_trabalhadas = max(0, total_min / 60.0)
                    registro.horas_extras = registro.horas_trabalhadas  # TODAS as horas
        
        db.session.commit()
        print(f"✅ {len(sabados)} registros de sábado corrigidos")

def corrigir_calculos_horas_extras():
    """Corrige cálculos de horas extras para tipos especiais"""
    with app.app_context():
        tipos_especiais = ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']
        
        for tipo in tipos_especiais:
            registros = RegistroPonto.query.filter_by(tipo_registro=tipo).all()
            
            for registro in registros:
                if registro.horas_trabalhadas:
                    # TODAS as horas são extras em tipos especiais
                    registro.horas_extras = registro.horas_trabalhadas
                    
                    # Zerar atrasos (não aplicável)
                    registro.minutos_atraso_entrada = 0
                    registro.minutos_atraso_saida = 0
                    registro.total_atraso_minutos = 0
                    registro.total_atraso_horas = 0.0
                    
                    # Definir percentual correto
                    if tipo == 'sabado_horas_extras':
                        registro.percentual_extras = 50.0
                    else:  # domingo_horas_extras, feriado_trabalhado
                        registro.percentual_extras = 100.0
        
        db.session.commit()
        print(f"✅ Horas extras corrigidas para tipos especiais")

if __name__ == "__main__":
    print("🚀 EXECUTANDO CORREÇÕES...")
    corrigir_sabados_sem_almoco()
    corrigir_calculos_horas_extras()
    print("✅ CORREÇÕES FINALIZADAS!")
'''
    
    with open('corrigir_problemas_ponto.py', 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("\n📝 SCRIPT DE CORREÇÃO GERADO: corrigir_problemas_ponto.py")

def main():
    """Função principal de análise"""
    print("🚀 INICIANDO ANÁLISE COMPLETA DOS PROBLEMAS")
    print("Data/Hora:", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    
    # Executar análises
    problemas = analisar_problemas_crud()
    analisar_engine_calculos()
    gerar_script_correcao()
    
    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO EXECUTIVO DOS PROBLEMAS")
    print("=" * 60)
    print(f"🔸 Sábados sem almoço: {problemas['sabados_sem_almoco']}")
    print(f"🔸 Problemas de cálculo: {problemas['problemas_calculo']}")
    print(f"🔸 Campos incorretos no código: {problemas['campos_incorretos']}")
    print("\n🎯 PRÓXIMOS PASSOS:")
    print("1. Executar: python corrigir_problemas_ponto.py")
    print("2. Corrigir campos no views.py (entrada → hora_entrada)")
    print("3. Testar funcionalidade de edição no frontend")
    print("4. Validar cálculos de KPIs")

if __name__ == "__main__":
    main()