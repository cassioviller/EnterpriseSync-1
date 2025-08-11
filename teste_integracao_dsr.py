#!/usr/bin/env python3
"""
Teste de integração do sistema DSR com o SIGE
Simula dados reais e testa a função integrada
"""

from datetime import date, datetime
import sys
import os

# Adicionar o diretório atual ao path para importar utils
sys.path.append('.')

# Mock básico para os modelos (para teste isolado)
class MockRegistroPonto:
    def __init__(self, data, tipo_registro):
        self.data = data
        self.tipo_registro = tipo_registro

class MockFuncionario:
    def __init__(self, nome, salario):
        self.nome = nome
        self.salario = salario

def teste_funcao_utils():
    """Testa a função DSR do utils.py"""
    print("🔧 TESTE INTEGRAÇÃO - Função utils.py")
    print("=" * 50)
    
    try:
        from utils import calcular_dsr_modo_estrito
        
        # Dados de teste
        salario = 2106.0
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        
        # Mock registros de faltas
        registros_faltas = [
            MockRegistroPonto(date(2025, 7, 8), 'falta'),   # Semana 2
            MockRegistroPonto(date(2025, 7, 15), 'falta'),  # Semana 3
            MockRegistroPonto(date(2025, 7, 16), 'falta'),  # Semana 3 (mesma semana)
            MockRegistroPonto(date(2025, 7, 29), 'falta'),  # Semana 5
        ]
        
        resultado = calcular_dsr_modo_estrito(salario, registros_faltas, data_inicio, data_fim)
        
        print(f"✅ Função importada com sucesso!")
        print(f"💰 Valor por dia: R$ {resultado['valor_dia']:.2f}")
        print(f"📊 Faltas total: {resultado['faltas_total']}")
        print(f"📅 Semanas com perda: {resultado['semanas_com_perda']}")
        print(f"💸 Desconto total: R$ {resultado['desconto_total']:.2f}")
        
        # Validar resultado esperado
        valor_dia_esperado = salario / 30
        faltas_esperadas = 4
        semanas_esperadas = 3  # 3 semanas diferentes com faltas
        desconto_esperado = (faltas_esperadas * valor_dia_esperado) + (semanas_esperadas * valor_dia_esperado)
        
        print()
        print("🎯 VALIDAÇÃO:")
        print(f"   Valor dia esperado: R$ {valor_dia_esperado:.2f} ✅" if abs(resultado['valor_dia'] - valor_dia_esperado) < 0.01 else f" ❌")
        print(f"   Faltas esperadas: {faltas_esperadas} ✅" if resultado['faltas_total'] == faltas_esperadas else f" ❌")
        print(f"   Semanas esperadas: {semanas_esperadas} ✅" if resultado['semanas_com_perda'] == semanas_esperadas else f" ❌")
        print(f"   Desconto esperado: R$ {desconto_esperado:.2f} ✅" if abs(resultado['desconto_total'] - desconto_esperado) < 0.01 else f" ❌")
        
    except Exception as e:
        print(f"❌ Erro ao importar/testar: {e}")
        print(f"   Tipo do erro: {type(e).__name__}")
        import traceback
        traceback.print_exc()

def teste_calculo_kpis_mock():
    """Simula o cálculo de KPIs com DSR"""
    print()
    print("🎭 SIMULAÇÃO - Cálculo KPIs com DSR")
    print("=" * 50)
    
    # Dados exemplo
    funcionario = MockFuncionario("Carlos Alberto", 2106.0)
    
    # Simulação do cálculo simplificado vs estrito
    faltas = 4
    valor_dia = funcionario.salario / 30
    
    # Método simplificado (atual)
    valor_simplificado = faltas * (2 * valor_dia)
    
    # Método estrito (simulado)
    semanas_com_falta = 3  # 3 semanas diferentes
    valor_estrito = (faltas * valor_dia) + (semanas_com_falta * valor_dia)
    
    print(f"👤 Funcionário: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario:,.2f}")
    print(f"📊 Faltas: {faltas}")
    print()
    
    print("🔹 MÉTODO SIMPLIFICADO (atual):")
    print(f"   {faltas} faltas × 2 dias = {faltas * 2} dias")
    print(f"   {faltas * 2} × R$ {valor_dia:.2f} = -R$ {valor_simplificado:.2f}")
    print()
    
    print("🔹 MÉTODO ESTRITO (Lei 605/49):")
    print(f"   Faltas: {faltas} × R$ {valor_dia:.2f} = -R$ {faltas * valor_dia:.2f}")
    print(f"   DSRs perdidos: {semanas_com_falta} × R$ {valor_dia:.2f} = -R$ {semanas_com_falta * valor_dia:.2f}")
    print(f"   Total: -R$ {valor_estrito:.2f}")
    print()
    
    print("💡 RESULTADO TEMPLATE:")
    print(f"   Card Faltas: \"{faltas}\"")
    print(f"   Valor simplificado: \"-R$ {valor_simplificado:,.2f} (Falta+DSR) Simplificado\"")
    if valor_estrito != valor_simplificado:
        print(f"   Valor estrito: \"Estrito: -R$ {valor_estrito:,.2f}\"")
    print()

if __name__ == "__main__":
    teste_funcao_utils()
    teste_calculo_kpis_mock()