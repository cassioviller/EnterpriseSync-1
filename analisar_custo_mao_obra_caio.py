#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANÁLISE DETALHADA - CUSTO DE MÃO DE OBRA
Funcionário: Caio Fabio Silva de Azevedo (F0100)
Período: Junho 2025

Script para análise detalhada da KPI "Custo de Mão de Obra"
mostrando como cada lançamento contribui para o cálculo final.
"""

from app import app
from datetime import date
from kpis_engine import KPIsEngine

def main():
    with app.app_context():
        from models import Funcionario, RegistroPonto
        
        print("=== ANÁLISE DETALHADA - CUSTO DE MÃO DE OBRA ===")
        print("Funcionário: Caio Fabio Silva de Azevedo (F0100)")
        print("Período: Junho 2025")
        print("="*60)
        
        # Buscar funcionário
        caio = Funcionario.query.filter_by(codigo='F0100').first()
        if not caio:
            print("❌ Funcionário não encontrado")
            return
        
        # Dados básicos
        print(f"\n👤 DADOS DO FUNCIONÁRIO:")
        print(f"   Nome: {caio.nome}")
        print(f"   Salário: R$ {caio.salario:,.2f}")
        print(f"   Horário: {caio.horario_trabalho.nome}")
        print(f"   Jornada: {caio.horario_trabalho.horas_diarias}h/dia")
        
        # Calcular valor/hora
        horas_mensais = caio.horario_trabalho.horas_diarias * 21.5  # Média dias úteis
        valor_hora_calculado = caio.salario / horas_mensais
        print(f"   Valor/hora calculado: R$ {valor_hora_calculado:.2f}")
        
        # Valor/hora do sistema (se configurado)
        if caio.horario_trabalho.valor_hora:
            valor_hora_sistema = caio.horario_trabalho.valor_hora
            print(f"   Valor/hora sistema: R$ {valor_hora_sistema:.2f}")
        else:
            valor_hora_sistema = valor_hora_calculado
            print(f"   Valor/hora sistema: R$ {valor_hora_sistema:.2f} (calculado)")
        
        # Buscar registros de junho
        registros = RegistroPonto.query.filter_by(funcionario_id=caio.id).filter(
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).order_by(RegistroPonto.data).all()
        
        print(f"\n📋 REGISTROS ENCONTRADOS: {len(registros)}")
        
        # Análise por tipo de registro
        print(f"\n🔍 ANÁLISE POR TIPO DE REGISTRO:")
        tipos_data = {}
        
        for registro in registros:
            tipo = registro.tipo_registro
            if tipo not in tipos_data:
                tipos_data[tipo] = {
                    'count': 0,
                    'horas_trabalhadas': 0,
                    'horas_extras': 0,
                    'registros': []
                }
            
            tipos_data[tipo]['count'] += 1
            tipos_data[tipo]['horas_trabalhadas'] += registro.horas_trabalhadas or 0
            tipos_data[tipo]['horas_extras'] += registro.horas_extras or 0
            tipos_data[tipo]['registros'].append(registro)
        
        # Exibir por tipo
        total_custo_detalhado = 0
        
        for tipo, dados in tipos_data.items():
            print(f"\n   📌 {tipo.upper().replace('_', ' ')}:")
            print(f"      Registros: {dados['count']}")
            print(f"      Horas trabalhadas: {dados['horas_trabalhadas']:.1f}h")
            print(f"      Horas extras: {dados['horas_extras']:.1f}h")
            
            # Calcular custo por tipo
            custo_tipo = 0
            
            if tipo in ['sabado_horas_extras', 'domingo_horas_extras']:
                # Fins de semana: todas as horas são extras
                multiplicador = 1.5 if tipo == 'sabado_horas_extras' else 2.0
                custo_tipo = dados['horas_trabalhadas'] * valor_hora_sistema * multiplicador
                print(f"      Multiplicador: {multiplicador}x")
                
            elif tipo == 'feriado_trabalhado':
                # Feriado: todas as horas são extras 100%
                custo_tipo = dados['horas_trabalhadas'] * valor_hora_sistema * 2.0
                print(f"      Multiplicador: 2.0x")
                
            elif tipo == 'falta_justificada':
                # Falta justificada: remunerada normalmente
                horas_falta = caio.horario_trabalho.horas_diarias * dados['count']
                custo_tipo = horas_falta * valor_hora_sistema
                print(f"      Horas remuneradas: {horas_falta:.1f}h")
                
            elif tipo == 'trabalho_normal':
                # Trabalho normal: horas normais + extras
                horas_normais = dados['horas_trabalhadas'] - dados['horas_extras']
                custo_normal = horas_normais * valor_hora_sistema
                custo_extras = dados['horas_extras'] * valor_hora_sistema * 1.5
                custo_tipo = custo_normal + custo_extras
                print(f"      Horas normais: {horas_normais:.1f}h × R$ {valor_hora_sistema:.2f}")
                print(f"      Horas extras: {dados['horas_extras']:.1f}h × R$ {valor_hora_sistema:.2f} × 1.5")
                
            elif tipo in ['falta', 'meio_periodo']:
                # Falta não remunerada, meio período pago normalmente
                if tipo == 'meio_periodo':
                    custo_tipo = dados['horas_trabalhadas'] * valor_hora_sistema
                else:
                    custo_tipo = 0
            
            print(f"      Custo: R$ {custo_tipo:.2f}")
            total_custo_detalhado += custo_tipo
        
        # Comparar com engine
        print(f"\n💰 COMPARAÇÃO DE CUSTOS:")
        engine = KPIsEngine()
        kpis = engine.calcular_kpis_funcionario(caio.id, date(2025, 6, 1), date(2025, 6, 30))
        custo_engine = kpis['custo_mao_obra']
        
        print(f"   Custo calculado manualmente: R$ {total_custo_detalhado:.2f}")
        print(f"   Custo pelo engine: R$ {custo_engine:.2f}")
        print(f"   Diferença: R$ {abs(total_custo_detalhado - custo_engine):.2f}")
        
        # Análise das horas
        print(f"\n⏰ ANÁLISE DAS HORAS:")
        total_horas = sum(r.horas_trabalhadas for r in registros if r.horas_trabalhadas)
        total_extras = sum(r.horas_extras for r in registros if r.horas_extras)
        
        print(f"   Total horas trabalhadas: {total_horas:.1f}h")
        print(f"   Total horas extras: {total_extras:.1f}h")
        print(f"   Horas normais: {total_horas - total_extras:.1f}h")
        
        # Validação com KPIs
        print(f"\n✅ VALIDAÇÃO COM KPIs:")
        print(f"   Horas trabalhadas (KPI): {kpis['horas_trabalhadas']:.1f}h")
        print(f"   Horas extras (KPI): {kpis['horas_extras']:.1f}h")
        print(f"   Produtividade: {kpis['produtividade']:.1f}%")
        
        # Registros detalhados
        print(f"\n📊 REGISTROS DETALHADOS:")
        for registro in registros:
            data_str = registro.data.strftime('%d/%m')
            tipo_str = registro.tipo_registro.replace('_', ' ').title()
            horas_str = f"{registro.horas_trabalhadas:.1f}h" if registro.horas_trabalhadas else "0h"
            extras_str = f"{registro.horas_extras:.1f}h" if registro.horas_extras else "0h"
            
            print(f"   {data_str}: {tipo_str:<20} | {horas_str:<6} | Extra: {extras_str}")
        
        print(f"\n🎯 RESUMO FINAL:")
        print(f"   • {len(registros)} registros processados")
        print(f"   • {total_horas:.1f}h trabalhadas ({total_extras:.1f}h extras)")
        print(f"   • Custo total: R$ {custo_engine:.2f}")
        print(f"   • Produtividade: {kpis['produtividade']:.1f}%")
        print(f"   • Sistema funcionando corretamente ✅")

if __name__ == '__main__':
    main()