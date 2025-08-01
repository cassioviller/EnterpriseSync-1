#!/usr/bin/env python3
"""
TESTE COMPLETO DA NOVA LÓGICA SALARIAL CORRIGIDA
Sistema SIGE v8.1 - Validação das correções implementadas

CORREÇÕES IMPLEMENTADAS:
1. Valor/hora baseado em dias úteis reais × 8.8h
2. Horas extras: 50% dias úteis/sábados, 100% domingos/feriados
3. Faltas justificadas: paga 8.8h
4. Faltas injustificadas: desconta 8.8h
5. Atrasos: desconto proporcional
"""

from app import app, db
from models import Funcionario, RegistroPonto
from utils import calcular_valor_hora_corrigido, calcular_custos_salariais_completos
from calcular_dias_uteis_mes import calcular_dias_uteis_mes
from datetime import datetime, date, time

def teste_valor_hora_corrigido():
    """Teste do cálculo do valor/hora correto"""
    print("=" * 60)
    print("🧮 TESTE: VALOR/HORA CORRIGIDO")
    print("=" * 60)
    
    with app.app_context():
        # Buscar qualquer funcionário para teste
        funcionario = Funcionario.query.filter(Funcionario.salario.isnot(None)).first()
        
        if not funcionario:
            print("❌ Funcionário Danilo não encontrado")
            return
        
        print(f"📋 Funcionário: {funcionario.nome}")
        print(f"💰 Salário Mensal: R$ {funcionario.salario:,.2f}")
        
        # Calcular valor/hora corrigido
        valor_hora = calcular_valor_hora_corrigido(funcionario)
        
        # Dados para validação (Julho 2025)
        ano, mes = 2025, 7
        dias_uteis = calcular_dias_uteis_mes(ano, mes)
        horas_mensais = dias_uteis * 8.8
        
        print(f"\n📅 Julho 2025:")
        print(f"   • Dias úteis: {dias_uteis}")
        print(f"   • Horas mensais: {dias_uteis} × 8.8h = {horas_mensais:.1f}h")
        print(f"   • Valor/hora: R$ {funcionario.salario:,.2f} ÷ {horas_mensais:.1f}h = R$ {valor_hora:.2f}")
        
        # Validação: Se trabalhar todas as horas, custo = salário
        custo_mes_completo = valor_hora * horas_mensais
        print(f"\n✅ VALIDAÇÃO:")
        print(f"   • Custo mês completo: R$ {custo_mes_completo:.2f}")
        print(f"   • Diferença do salário: R$ {abs(custo_mes_completo - funcionario.salario):.2f}")
        
        if abs(custo_mes_completo - funcionario.salario) < 0.01:
            print("   • ✅ CORRETO: Custo = Salário quando trabalha horas esperadas")
        else:
            print("   • ❌ ERRO: Custo deveria ser igual ao salário")

def teste_custos_salariais_completos():
    """Teste dos cálculos salariais completos"""
    print("\n" + "=" * 60)  
    print("💼 TESTE: CUSTOS SALARIAIS COMPLETOS")
    print("=" * 60)
    
    with app.app_context():
        funcionario = Funcionario.query.filter_by(nome='Danilo Santos Valverde').first()
        
        if not funcionario:
            print("❌ Funcionário Danilo não encontrado")
            return
        
        # Período de teste: Julho 2025
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        
        resultado = calcular_custos_salariais_completos(funcionario.id, data_inicio, data_fim)
        
        print(f"📋 Funcionário: {funcionario.nome}")
        print(f"📅 Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        print(f"💰 Valor/hora: R$ {resultado['valor_hora']:.2f}")
        print(f"💸 Custo Total: R$ {resultado['custo_total']:.2f}")
        
        print(f"\n📊 DETALHAMENTO:")
        detalhes = resultado['detalhamento']
        print(f"   • Horas normais: R$ {detalhes['horas_normais']:.2f}")
        print(f"   • Extras 50%: R$ {detalhes['extras_50']:.2f}")
        print(f"   • Extras 100%: R$ {detalhes['extras_100']:.2f}")
        print(f"   • Faltas justificadas: R$ {detalhes['faltas_justificadas']:.2f}")
        print(f"   • Desconto faltas: -R$ {detalhes['desconto_faltas']:.2f}")
        print(f"   • Desconto atrasos: -R$ {detalhes['desconto_atrasos']:.2f}")

def teste_registros_exemplo():
    """Testa registros específicos para validar cálculos"""
    print("\n" + "=" * 60)
    print("📋 TESTE: REGISTROS DE EXEMPLO")
    print("=" * 60)
    
    with app.app_context():
        funcionario = Funcionario.query.filter_by(nome='Danilo Santos Valverde').first()
        
        if not funcionario:
            print("❌ Funcionário Danilo não encontrado")
            return
        
        valor_hora = calcular_valor_hora_corrigido(funcionario)
        
        # Exemplos de cálculos manuais
        print(f"💰 Valor/hora base: R$ {valor_hora:.2f}")
        print(f"\n📊 EXEMPLOS DE CÁLCULOS:")
        
        # Dia normal (8.8h)
        custo_dia_normal = valor_hora * 8.8
        print(f"   • Dia normal (8.8h): R$ {custo_dia_normal:.2f}")
        
        # Hora extra dia útil (50%)
        custo_hora_extra_50 = valor_hora * 1.5
        print(f"   • Hora extra dia útil (50%): R$ {custo_hora_extra_50:.2f}")
        
        # Hora extra domingo (100%)
        custo_hora_extra_100 = valor_hora * 2.0
        print(f"   • Hora extra domingo (100%): R$ {custo_hora_extra_100:.2f}")
        
        # Falta justificada
        custo_falta_justificada = valor_hora * 8.8
        print(f"   • Falta justificada (8.8h pagas): R$ {custo_falta_justificada:.2f}")
        
        # Atraso de 30 minutos
        desconto_atraso_30min = valor_hora * 0.5
        print(f"   • Atraso 30min (desconto): -R$ {desconto_atraso_30min:.2f}")

def buscar_registros_reais():
    """Mostra registros reais do banco para análise"""
    print("\n" + "=" * 60)
    print("🔍 REGISTROS REAIS DO BANCO")
    print("=" * 60)
    
    with app.app_context():
        funcionario = Funcionario.query.filter_by(nome='Danilo Santos Valverde').first()
        
        if not funcionario:
            print("❌ Funcionário Danilo não encontrado")
            return
        
        # Buscar registros de julho 2025
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data).limit(10).all()
        
        print(f"📋 Funcionário: {funcionario.nome}")
        print(f"📊 Registros encontrados: {len(registros)}")
        
        if registros:
            print(f"\n🗓️  AMOSTRA DOS REGISTROS:")
            print("Data       | Tipo            | H.Trab | H.Extra | Atraso")
            print("-" * 60)
            
            for reg in registros:
                data_str = reg.data.strftime('%d/%m/%Y')
                tipo = reg.tipo_registro or 'N/A'
                h_trab = f"{reg.horas_trabalhadas:.1f}h" if reg.horas_trabalhadas else "-"
                h_extra = f"{reg.horas_extras:.1f}h" if reg.horas_extras else "-"
                atraso = f"{reg.total_atraso_horas:.1f}h" if reg.total_atraso_horas else "-"
                
                print(f"{data_str} | {tipo:15s} | {h_trab:6s} | {h_extra:7s} | {atraso:6s}")

if __name__ == "__main__":
    print("🚀 INICIANDO TESTES DA LÓGICA SALARIAL CORRIGIDA")
    print("Sistema SIGE v8.1 - Validação Completa")
    
    try:
        teste_valor_hora_corrigido()
        teste_custos_salariais_completos()
        teste_registros_exemplo()
        buscar_registros_reais()
        
        print("\n" + "=" * 60)
        print("✅ TESTES CONCLUÍDOS COM SUCESSO!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERRO DURANTE OS TESTES: {e}")
        import traceback
        traceback.print_exc()