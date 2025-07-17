#!/usr/bin/env python3
"""
Script para testar todos os KPIs do sistema SIGE v5.0
Verifica se os cálculos estão corretos e funcionando
"""

from app import app, db
from datetime import date, datetime
from models import Funcionario, OutroCusto, CustoVeiculo, RegistroAlimentacao, RegistroPonto
from kpis_engine_v3 import calcular_kpis_funcionario_v3
from utils import calcular_custos_mes, calcular_kpis_funcionarios_geral

def testar_kpis_dashboard():
    """Testa os KPIs do dashboard"""
    print("=== TESTANDO KPIs DO DASHBOARD ===")
    
    # Período de teste (junho 2025)
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Testar custos mensais
    custos = calcular_custos_mes(data_inicio, data_fim)
    print(f"Custos do período {data_inicio} a {data_fim}:")
    print(f"  - Alimentação: R$ {custos['alimentacao']:,.2f}")
    print(f"  - Transporte: R$ {custos['transporte']:,.2f}")
    print(f"  - Mão de obra: R$ {custos['mao_obra']:,.2f}")
    print(f"  - Faltas justificadas: R$ {custos['faltas_justificadas']:,.2f}")
    print(f"  - Outros custos: R$ {custos['outros']:,.2f}")
    print(f"  - TOTAL: R$ {custos['total']:,.2f}")
    
    # Verificar se outros custos está sendo calculado corretamente
    outros_custos_db = db.session.query(OutroCusto).filter(
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).all()
    
    print(f"\nOUTROS CUSTOS DETALHADOS:")
    total_outros = 0
    for custo in outros_custos_db:
        print(f"  - {custo.funcionario.nome}: {custo.tipo} - R$ {custo.valor:,.2f} ({custo.data})")
        total_outros += custo.valor
    print(f"  TOTAL OUTROS CUSTOS: R$ {total_outros:,.2f}")
    
    return custos

def testar_kpis_funcionario():
    """Testa os KPIs de um funcionário específico"""
    print("\n=== TESTANDO KPIs DE FUNCIONÁRIO ===")
    
    # Buscar funcionário Cássio (que tem dados completos)
    funcionario = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
    if not funcionario:
        print("Funcionário Cássio não encontrado!")
        return
    
    # Período de teste (junho 2025)
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Calcular KPIs
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    print(f"KPIs do funcionário {funcionario.nome} ({funcionario.codigo}):")
    print(f"  - Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"  - Horas extras: {kpis['horas_extras']:.1f}h")
    print(f"  - Faltas: {kpis['faltas']}")
    print(f"  - Atrasos: {kpis['atrasos']:.2f}h")
    print(f"  - Horas perdidas: {kpis['horas_perdidas']:.1f}h")
    print(f"  - Custo mão de obra: R$ {kpis['custo_mao_obra']:,.2f}")
    print(f"  - Custo alimentação: R$ {kpis['custo_alimentacao']:,.2f}")
    print(f"  - Custo transporte: R$ {kpis['custo_transporte']:,.2f}")
    print(f"  - Outros custos: R$ {kpis['outros_custos']:,.2f}")
    print(f"  - Produtividade: {kpis['produtividade']:.1f}%")
    print(f"  - Absenteísmo: {kpis['absenteismo']:.1f}%")
    
    # Verificar dados específicos
    print(f"\nDETALHES:")
    print(f"  - Salário: R$ {funcionario.salario:,.2f}")
    print(f"  - Salário/hora: R$ {funcionario.salario/220:.2f}")
    print(f"  - Dias úteis: {kpis['dias_uteis']}")
    print(f"  - Dias com presença: {kpis['dias_com_presenca']}")
    print(f"  - Horas esperadas: {kpis['horas_esperadas']:.1f}h")
    
    return kpis

def testar_formula_horas_perdidas():
    """Testa especificamente a fórmula de horas perdidas"""
    print("\n=== TESTANDO FÓRMULA HORAS PERDIDAS ===")
    
    funcionario = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
    if not funcionario:
        print("Funcionário Cássio não encontrado!")
        return
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    faltas = kpis['faltas']
    atrasos = kpis['atrasos']
    horas_perdidas_calculadas = (faltas * 8) + atrasos
    
    print(f"Funcionário: {funcionario.nome}")
    print(f"Faltas: {faltas}")
    print(f"Atrasos: {atrasos:.2f}h")
    print(f"Fórmula: ({faltas} * 8) + {atrasos:.2f} = {horas_perdidas_calculadas:.2f}h")
    print(f"Sistema: {kpis['horas_perdidas']:.2f}h")
    print(f"Correto: {'✅' if abs(horas_perdidas_calculadas - kpis['horas_perdidas']) < 0.01 else '❌'}")

def testar_outros_custos_funcionario():
    """Testa outros custos específicos do funcionário"""
    print("\n=== TESTANDO OUTROS CUSTOS POR FUNCIONÁRIO ===")
    
    funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    for funcionario in funcionarios:
        outros_custos = db.session.query(OutroCusto).filter(
            OutroCusto.funcionario_id == funcionario.id,
            OutroCusto.data >= data_inicio,
            OutroCusto.data <= data_fim
        ).all()
        
        total_outros = sum(custo.valor for custo in outros_custos)
        
        print(f"\nFuncionário: {funcionario.nome} ({funcionario.codigo})")
        print(f"  Outros custos no período: R$ {total_outros:,.2f}")
        
        for custo in outros_custos:
            print(f"    - {custo.tipo}: R$ {custo.valor:,.2f} ({custo.data})")
        
        # Verificar se o KPI está correto
        kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
        print(f"  KPI outros custos: R$ {kpis['outros_custos']:,.2f}")
        print(f"  Correto: {'✅' if abs(total_outros - kpis['outros_custos']) < 0.01 else '❌'}")

def main():
    """Função principal de teste"""
    with app.app_context():
        print("TESTE COMPLETO DOS KPIs - SIGE v5.0")
        print("=" * 50)
        
        # Testar dashboard
        custos_dashboard = testar_kpis_dashboard()
        
        # Testar funcionário específico
        kpis_funcionario = testar_kpis_funcionario()
        
        # Testar fórmula de horas perdidas
        testar_formula_horas_perdidas()
        
        # Testar outros custos por funcionário
        testar_outros_custos_funcionario()
        
        print("\n" + "=" * 50)
        print("TESTE CONCLUÍDO!")
        print("Verifique os resultados acima para confirmar se todos os KPIs estão funcionando corretamente.")

if __name__ == "__main__":
    main()