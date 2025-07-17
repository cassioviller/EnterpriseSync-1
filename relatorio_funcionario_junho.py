#!/usr/bin/env python3
"""
Relatório completo de funcionário para junho 2025
Mostra todos os dados usados para KPIs, cálculos e valores exibidos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar

# Importar depois de configurar o path
from app import app, db
from models import *
from kpis_engine_v3 import calcular_kpis_funcionario_v3

def is_dia_util(data):
    """Verifica se é dia útil (seg-sex, exceto feriados)"""
    feriados_2025 = [
        date(2025, 1, 1),   # Confraternização Universal
        date(2025, 2, 17),  # Carnaval
        date(2025, 2, 18),  # Carnaval
        date(2025, 4, 18),  # Paixão de Cristo
        date(2025, 4, 21),  # Tiradentes
        date(2025, 5, 1),   # Dia do Trabalho
        date(2025, 6, 19),  # Corpus Christi
        date(2025, 9, 7),   # Independência do Brasil
        date(2025, 10, 12), # Nossa Senhora Aparecida
        date(2025, 11, 2),  # Finados
        date(2025, 11, 15), # Proclamação da República
        date(2025, 12, 25)  # Natal
    ]
    
    # Verifica se é fim de semana (sábado=5, domingo=6)
    if data.weekday() >= 5:
        return False
    
    # Verifica se é feriado
    if data in feriados_2025:
        return False
    
    return True

def calcular_dias_uteis_mes(ano, mes):
    """Calcula o número de dias úteis no mês"""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    
    dias_uteis = 0
    data_atual = primeiro_dia
    
    while data_atual <= ultimo_dia:
        if is_dia_util(data_atual):
            dias_uteis += 1
        data_atual += timedelta(days=1)
    
    return dias_uteis

def gerar_relatorio_funcionario_junho(funcionario_nome=None):
    """Gera relatório completo de funcionário para junho 2025"""
    
    # Definir período
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Buscar funcionário
    if funcionario_nome:
        funcionario = Funcionario.query.filter(Funcionario.nome.ilike(f"%{funcionario_nome}%")).first()
    else:
        funcionario = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
    
    if not funcionario:
        print("Funcionário não encontrado!")
        return
    
    print("="*100)
    print(f"RELATÓRIO COMPLETO - FUNCIONÁRIO: {funcionario.nome}")
    print(f"CÓDIGO: {funcionario.codigo}")
    print(f"PERÍODO: JUNHO/2025 (01/06/2025 a 30/06/2025)")
    print("="*100)
    
    # ============================================
    # 1. DADOS BÁSICOS DO FUNCIONÁRIO
    # ============================================
    print("\n1. DADOS BÁSICOS DO FUNCIONÁRIO")
    print("-" * 50)
    print(f"Nome: {funcionario.nome}")
    print(f"Código: {funcionario.codigo}")
    print(f"CPF: {funcionario.cpf}")
    print(f"Salário mensal: R$ {funcionario.salario:,.2f}")
    print(f"Salário por hora: R$ {funcionario.salario/220:.2f}")
    departamento = Departamento.query.get(funcionario.departamento_id) if funcionario.departamento_id else None
    funcao = Funcao.query.get(funcionario.funcao_id) if funcionario.funcao_id else None
    print(f"Departamento: {departamento.nome if departamento else 'N/A'}")
    print(f"Função: {funcao.nome if funcao else 'N/A'}")
    print(f"Data de admissão: {funcionario.data_admissao}")
    print(f"Status: {'Ativo' if funcionario.ativo else 'Inativo'}")
    
    # ============================================
    # 2. ANÁLISE DO PERÍODO (JUNHO 2025)
    # ============================================
    print("\n2. ANÁLISE DO PERÍODO (JUNHO 2025)")
    print("-" * 50)
    
    # Calcular dias úteis
    dias_uteis = calcular_dias_uteis_mes(2025, 6)
    total_dias = 30
    
    print(f"Total de dias no mês: {total_dias}")
    print(f"Dias úteis (seg-sex, exceto feriados): {dias_uteis}")
    print(f"Horas esperadas (8h/dia útil): {dias_uteis * 8}h")
    
    # Listar dias úteis
    print("\nDias úteis em junho 2025:")
    data_atual = data_inicio
    dias_uteis_lista = []
    while data_atual <= data_fim:
        if is_dia_util(data_atual):
            dias_uteis_lista.append(data_atual)
            print(f"  - {data_atual.strftime('%d/%m/%Y')} ({data_atual.strftime('%A')})")
        data_atual += timedelta(days=1)
    
    # Listar feriados
    print("\nFeriados em junho 2025:")
    if date(2025, 6, 19) >= data_inicio and date(2025, 6, 19) <= data_fim:
        print("  - 19/06/2025 (Corpus Christi)")
    else:
        print("  - Nenhum feriado no período")
    
    # ============================================
    # 3. REGISTROS DE PONTO DETALHADOS
    # ============================================
    print("\n3. REGISTROS DE PONTO DETALHADOS")
    print("-" * 50)
    
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data).all()
    
    total_horas_trabalhadas = 0
    total_horas_extras = 0
    total_faltas = 0
    total_atrasos_minutos = 0
    total_registros = len(registros_ponto)
    
    print(f"Total de registros encontrados: {total_registros}")
    print("\nDetalhamento por dia:")
    
    for registro in registros_ponto:
        print(f"\n  📅 {registro.data.strftime('%d/%m/%Y')} ({registro.data.strftime('%A')})")
        print(f"     Tipo: {registro.tipo_registro or 'trabalho_normal'}")
        obra = Obra.query.get(registro.obra_id) if registro.obra_id else None
        print(f"     Obra: {obra.nome if obra else 'N/A'}")
        
        if registro.hora_entrada:
            print(f"     Entrada: {registro.hora_entrada}")
            print(f"     Saída: {registro.hora_saida}")
            if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                print(f"     Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
            else:
                print(f"     Almoço: Sem intervalo")
            print(f"     Horas trabalhadas: {registro.horas_trabalhadas:.1f}h")
            print(f"     Horas extras: {registro.horas_extras:.1f}h")
            if registro.percentual_extras:
                print(f"     Percentual extras: {registro.percentual_extras:.0f}%")
            print(f"     Atrasos: {registro.total_atraso_minutos:.0f} minutos")
            
            total_horas_trabalhadas += registro.horas_trabalhadas or 0
            total_horas_extras += registro.horas_extras or 0
            total_atrasos_minutos += registro.total_atraso_minutos or 0
        else:
            print(f"     Status: {registro.tipo_registro}")
            if registro.tipo_registro == 'falta':
                total_faltas += 1
        
        if registro.observacoes:
            print(f"     Observações: {registro.observacoes}")
    
    print(f"\n📊 RESUMO DOS REGISTROS DE PONTO:")
    print(f"  - Total de registros: {total_registros}")
    print(f"  - Horas trabalhadas: {total_horas_trabalhadas:.1f}h")
    print(f"  - Horas extras: {total_horas_extras:.1f}h")
    print(f"  - Faltas: {total_faltas}")
    print(f"  - Atrasos: {total_atrasos_minutos:.0f} minutos ({total_atrasos_minutos/60:.2f}h)")
    
    # ============================================
    # 4. REGISTROS DE ALIMENTAÇÃO
    # ============================================
    print("\n4. REGISTROS DE ALIMENTAÇÃO")
    print("-" * 50)
    
    registros_alimentacao = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.funcionario_id == funcionario.id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).order_by(RegistroAlimentacao.data).all()
    
    total_alimentacao = 0
    
    if registros_alimentacao:
        print(f"Total de registros de alimentação: {len(registros_alimentacao)}")
        print("\nDetalhamento:")
        
        for registro in registros_alimentacao:
            print(f"\n  🍽️  {registro.data.strftime('%d/%m/%Y')}")
            print(f"     Restaurante: {registro.restaurante.nome}")
            print(f"     Tipo: {registro.tipo_refeicao}")
            print(f"     Valor: R$ {registro.valor:.2f}")
            if registro.observacoes:
                print(f"     Observações: {registro.observacoes}")
            total_alimentacao += registro.valor
    else:
        print("Nenhum registro de alimentação encontrado no período")
    
    print(f"\n📊 RESUMO ALIMENTAÇÃO:")
    print(f"  - Total de refeições: {len(registros_alimentacao)}")
    print(f"  - Valor total: R$ {total_alimentacao:.2f}")
    
    # ============================================
    # 5. OUTROS CUSTOS
    # ============================================
    print("\n5. OUTROS CUSTOS")
    print("-" * 50)
    
    outros_custos = OutroCusto.query.filter(
        OutroCusto.funcionario_id == funcionario.id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).order_by(OutroCusto.data).all()
    
    total_outros_custos = 0
    
    if outros_custos:
        print(f"Total de outros custos: {len(outros_custos)}")
        print("\nDetalhamento:")
        
        for custo in outros_custos:
            print(f"\n  💰 {custo.data.strftime('%d/%m/%Y')}")
            print(f"     Tipo: {custo.tipo}")
            print(f"     Categoria: {custo.categoria}")
            print(f"     Valor: R$ {custo.valor:.2f}")
            if custo.descricao:
                print(f"     Descrição: {custo.descricao}")
            total_outros_custos += custo.valor
    else:
        print("Nenhum outro custo encontrado no período")
    
    print(f"\n📊 RESUMO OUTROS CUSTOS:")
    print(f"  - Total de lançamentos: {len(outros_custos)}")
    print(f"  - Valor total: R$ {total_outros_custos:.2f}")
    
    # ============================================
    # 6. CÁLCULO DOS KPIs
    # ============================================
    print("\n6. CÁLCULO DOS KPIs")
    print("-" * 50)
    
    # Calcular KPIs usando o engine
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    print("📈 FÓRMULAS E CÁLCULOS DETALHADOS:")
    print()
    
    # Horas trabalhadas
    print(f"🕐 HORAS TRABALHADAS:")
    print(f"  Fórmula: Soma das horas trabalhadas de todos os registros")
    print(f"  Cálculo: {total_horas_trabalhadas:.1f}h")
    print(f"  Valor no KPI: {kpis['horas_trabalhadas']:.1f}h")
    print()
    
    # Horas extras
    print(f"⏰ HORAS EXTRAS:")
    print(f"  Fórmula: Soma das horas extras de todos os registros")
    print(f"  Cálculo: {total_horas_extras:.1f}h")
    print(f"  Valor no KPI: {kpis['horas_extras']:.1f}h")
    print()
    
    # Faltas
    print(f"❌ FALTAS:")
    print(f"  Fórmula: Contagem de registros com tipo 'falta'")
    print(f"  Cálculo: {total_faltas} faltas")
    print(f"  Valor no KPI: {kpis['faltas']}")
    print()
    
    # Atrasos
    print(f"⏱️  ATRASOS:")
    print(f"  Fórmula: Soma dos atrasos em minutos ÷ 60")
    print(f"  Cálculo: {total_atrasos_minutos:.0f} minutos ÷ 60 = {total_atrasos_minutos/60:.2f}h")
    print(f"  Valor no KPI: {kpis['atrasos']:.2f}h")
    print()
    
    # Horas perdidas
    print(f"📉 HORAS PERDIDAS:")
    print(f"  Fórmula: (faltas × 8) + atrasos")
    print(f"  Cálculo: ({total_faltas} × 8) + {total_atrasos_minutos/60:.2f} = {(total_faltas * 8) + (total_atrasos_minutos/60):.1f}h")
    print(f"  Valor no KPI: {kpis['horas_perdidas']:.1f}h")
    print()
    
    # Custo mão de obra
    salario_hora = funcionario.salario / 220
    custo_normal = total_horas_trabalhadas * salario_hora
    custo_extra = total_horas_extras * salario_hora * 1.5
    custo_total_calculado = custo_normal + custo_extra
    
    print(f"💼 CUSTO MÃO DE OBRA:")
    print(f"  Fórmula: (horas_trabalhadas × salário_hora) + (horas_extras × salário_hora × 1.5)")
    print(f"  Salário/hora: R$ {funcionario.salario:,.2f} ÷ 220 = R$ {salario_hora:.2f}")
    print(f"  Custo normal: {total_horas_trabalhadas:.1f}h × R$ {salario_hora:.2f} = R$ {custo_normal:.2f}")
    print(f"  Custo extras: {total_horas_extras:.1f}h × R$ {salario_hora:.2f} × 1.5 = R$ {custo_extra:.2f}")
    print(f"  Cálculo: R$ {custo_normal:.2f} + R$ {custo_extra:.2f} = R$ {custo_total_calculado:.2f}")
    print(f"  Valor no KPI: R$ {kpis['custo_mao_obra']:,.2f}")
    print()
    
    # Custo alimentação
    print(f"🍽️  CUSTO ALIMENTAÇÃO:")
    print(f"  Fórmula: Soma dos valores de alimentação")
    print(f"  Cálculo: R$ {total_alimentacao:.2f}")
    print(f"  Valor no KPI: R$ {kpis['custo_alimentacao']:,.2f}")
    print()
    
    # Outros custos
    print(f"💰 OUTROS CUSTOS:")
    print(f"  Fórmula: Soma dos outros custos")
    print(f"  Cálculo: R$ {total_outros_custos:.2f}")
    print(f"  Valor no KPI: R$ {kpis['outros_custos']:,.2f}")
    print()
    
    # Produtividade
    horas_esperadas = dias_uteis * 8
    produtividade_calculada = (total_horas_trabalhadas / horas_esperadas) * 100
    
    print(f"📊 PRODUTIVIDADE:")
    print(f"  Fórmula: (horas_trabalhadas ÷ horas_esperadas) × 100")
    print(f"  Horas esperadas: {dias_uteis} dias úteis × 8h = {horas_esperadas}h")
    print(f"  Cálculo: ({total_horas_trabalhadas:.1f} ÷ {horas_esperadas}) × 100 = {produtividade_calculada:.1f}%")
    print(f"  Valor no KPI: {kpis['produtividade']:.1f}%")
    print()
    
    # Absenteísmo
    absenteismo_calculado = (total_faltas / dias_uteis) * 100
    
    print(f"📈 ABSENTEÍSMO:")
    print(f"  Fórmula: (faltas ÷ dias_úteis) × 100")
    print(f"  Cálculo: ({total_faltas} ÷ {dias_uteis}) × 100 = {absenteismo_calculado:.1f}%")
    print(f"  Valor no KPI: {kpis['absenteismo']:.1f}%")
    print()
    
    # ============================================
    # 7. RESUMO FINAL DOS KPIs
    # ============================================
    print("\n7. RESUMO FINAL DOS KPIs (FILTRO JUNHO/2025)")
    print("-" * 50)
    
    print("📋 VALORES EXIBIDOS NO SISTEMA:")
    print(f"  🕐 Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"  ⏰ Horas extras: {kpis['horas_extras']:.1f}h")
    print(f"  ❌ Faltas: {kpis['faltas']}")
    print(f"  ⏱️  Atrasos: {kpis['atrasos']:.2f}h")
    print(f"  📉 Horas perdidas: {kpis['horas_perdidas']:.1f}h")
    print(f"  💼 Custo mão de obra: R$ {kpis['custo_mao_obra']:,.2f}")
    print(f"  🍽️  Custo alimentação: R$ {kpis['custo_alimentacao']:,.2f}")
    print(f"  🚗 Custo transporte: R$ {kpis['custo_transporte']:,.2f}")
    print(f"  💰 Outros custos: R$ {kpis['outros_custos']:,.2f}")
    print(f"  📊 Produtividade: {kpis['produtividade']:.1f}%")
    print(f"  📈 Absenteísmo: {kpis['absenteismo']:.1f}%")
    
    custo_total_funcionario = kpis['custo_mao_obra'] + kpis['custo_alimentacao'] + kpis['custo_transporte'] + kpis['outros_custos']
    print(f"\n💵 CUSTO TOTAL DO FUNCIONÁRIO: R$ {custo_total_funcionario:,.2f}")
    
    print("\n" + "="*100)
    print("RELATÓRIO CONCLUÍDO!")
    print("="*100)
    
    return kpis

def main():
    """Função principal"""
    with app.app_context():
        # Gerar relatório para o funcionário Cássio
        gerar_relatorio_funcionario_junho("Cássio Viller Silva de Azevedo")

if __name__ == "__main__":
    main()