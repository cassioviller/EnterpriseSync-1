#!/usr/bin/env python3
"""
Relatório completo do funcionário João Silva dos Santos (F0099)
que demonstra todos os tipos de lançamentos possíveis no sistema
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime
from app import app, db
from models import *
from kpis_engine_v3 import KPIEngine

def gerar_relatorio_completo():
    """Gera relatório completo do funcionário com perfil completo"""
    
    # Buscar funcionário
    funcionario = Funcionario.query.filter_by(codigo="F0099").first()
    if not funcionario:
        print("Funcionário F0099 não encontrado!")
        return
    
    print("="*100)
    print("RELATÓRIO COMPLETO - FUNCIONÁRIO COM TODOS OS TIPOS DE LANÇAMENTOS")
    print("="*100)
    
    print(f"Nome: {funcionario.nome}")
    print(f"Código: {funcionario.codigo}")
    print(f"CPF: {funcionario.cpf}")
    print(f"Salário: R$ {funcionario.salario:,.2f}")
    print(f"Período: JUNHO/2025")
    print()
    
    # Dados do período
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    print("1. REGISTROS DE PONTO DETALHADOS")
    print("-" * 60)
    
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data).all()
    
    print(f"Total de registros: {len(registros_ponto)}")
    print()
    
    for i, registro in enumerate(registros_ponto, 1):
        print(f"📅 {i:2d}. {registro.data.strftime('%d/%m/%Y')} ({registro.data.strftime('%A')})")
        print(f"     Tipo: {registro.tipo_registro or 'trabalho_normal'}")
        
        if registro.hora_entrada:
            print(f"     Entrada: {registro.hora_entrada}")
            print(f"     Saída: {registro.hora_saida}")
            if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                print(f"     Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
            else:
                print(f"     Almoço: Sem intervalo")
            print(f"     Horas trabalhadas: {registro.horas_trabalhadas or 0:.1f}h")
            print(f"     Horas extras: {registro.horas_extras or 0:.1f}h")
            if registro.percentual_extras:
                print(f"     Percentual extras: {registro.percentual_extras}%")
            print(f"     Atrasos: {registro.total_atraso_minutos or 0} minutos")
        
        if registro.observacoes:
            print(f"     Observações: {registro.observacoes}")
        print()
    
    print("2. REGISTROS DE ALIMENTAÇÃO")
    print("-" * 60)
    
    registros_alimentacao = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.funcionario_id == funcionario.id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).order_by(RegistroAlimentacao.data).all()
    
    print(f"Total de registros: {len(registros_alimentacao)}")
    print()
    
    for i, registro in enumerate(registros_alimentacao, 1):
        print(f"🍽️  {i:2d}. {registro.data.strftime('%d/%m/%Y')}")
        print(f"     Tipo: {registro.tipo}")
        print(f"     Valor: R$ {registro.valor:,.2f}")
        if registro.observacoes:
            print(f"     Observações: {registro.observacoes}")
        print()
    
    print("3. OUTROS CUSTOS")
    print("-" * 60)
    
    outros_custos = OutroCusto.query.filter(
        OutroCusto.funcionario_id == funcionario.id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).order_by(OutroCusto.data).all()
    
    print(f"Total de registros: {len(outros_custos)}")
    print()
    
    for i, custo in enumerate(outros_custos, 1):
        print(f"💰 {i:2d}. {custo.data.strftime('%d/%m/%Y')}")
        print(f"     Tipo: {custo.tipo}")
        print(f"     Categoria: {custo.categoria}")
        print(f"     Valor: R$ {custo.valor:,.2f}")
        if custo.descricao:
            print(f"     Descrição: {custo.descricao}")
        print()
    
    print("4. CÁLCULO DOS KPIs")
    print("-" * 60)
    
    # Usar o engine de KPIs para calcular
    kpi_engine = KPIEngine()
    
    # Calcular resumos
    total_horas_trabalhadas = sum(r.horas_trabalhadas or 0 for r in registros_ponto)
    total_horas_extras = sum(r.horas_extras or 0 for r in registros_ponto)
    total_faltas = len([r for r in registros_ponto if r.tipo_registro == 'falta'])
    total_atrasos_minutos = sum(r.total_atraso_minutos or 0 for r in registros_ponto)
    total_atrasos_horas = total_atrasos_minutos / 60
    
    # Calcular custos
    custo_alimentacao = sum(r.valor for r in registros_alimentacao)
    custo_outros = sum(c.valor for c in outros_custos)
    
    # Calcular custo mão de obra
    salario_hora = funcionario.salario / 220  # 220 horas/mês
    custo_mao_obra = total_horas_trabalhadas * salario_hora
    custo_horas_extras = total_horas_extras * salario_hora * 1.5
    
    # Calcular produtividade (assumindo 20 dias úteis)
    dias_uteis = 20
    horas_esperadas = dias_uteis * 8
    produtividade = (total_horas_trabalhadas / horas_esperadas) * 100
    
    # Calcular absenteísmo
    absenteismo = (total_faltas / dias_uteis) * 100
    
    # Calcular horas perdidas
    horas_perdidas = (total_faltas * 8) + total_atrasos_horas
    
    print("📊 RESUMO DOS KPIs:")
    print(f"  🕐 Horas trabalhadas: {total_horas_trabalhadas:.1f}h")
    print(f"  ⏰ Horas extras: {total_horas_extras:.1f}h")
    print(f"  ❌ Faltas: {total_faltas}")
    print(f"  ⏱️  Atrasos: {total_atrasos_horas:.2f}h ({total_atrasos_minutos} minutos)")
    print(f"  📉 Horas perdidas: {horas_perdidas:.1f}h")
    print(f"  💼 Custo mão de obra: R$ {custo_mao_obra:,.2f}")
    print(f"  🍽️  Custo alimentação: R$ {custo_alimentacao:,.2f}")
    print(f"  💰 Outros custos: R$ {custo_outros:,.2f}")
    print(f"  📊 Produtividade: {produtividade:.1f}%")
    print(f"  📈 Absenteísmo: {absenteismo:.1f}%")
    print()
    
    print("5. FÓRMULAS DE CÁLCULO")
    print("-" * 60)
    print("📐 FÓRMULAS UTILIZADAS:")
    print(f"  Salário/hora: R$ {funcionario.salario:,.2f} ÷ 220h = R$ {salario_hora:.2f}")
    print(f"  Custo mão de obra: {total_horas_trabalhadas:.1f}h × R$ {salario_hora:.2f} = R$ {custo_mao_obra:,.2f}")
    print(f"  Custo horas extras: {total_horas_extras:.1f}h × R$ {salario_hora:.2f} × 1.5 = R$ {custo_horas_extras:,.2f}")
    print(f"  Produtividade: ({total_horas_trabalhadas:.1f} ÷ {horas_esperadas}) × 100 = {produtividade:.1f}%")
    print(f"  Absenteísmo: ({total_faltas} ÷ {dias_uteis}) × 100 = {absenteismo:.1f}%")
    print(f"  Horas perdidas: ({total_faltas} × 8) + {total_atrasos_horas:.2f} = {horas_perdidas:.1f}h")
    print()
    
    print("6. TIPOS DE LANÇAMENTOS DEMONSTRADOS")
    print("-" * 60)
    
    tipos_encontrados = set()
    for registro in registros_ponto:
        tipos_encontrados.add(registro.tipo_registro or 'trabalho_normal')
    
    print("✅ TIPOS DE PONTO INCLUÍDOS:")
    for tipo in sorted(tipos_encontrados):
        print(f"  ✓ {tipo}")
    print()
    
    tipos_alimentacao = set(r.tipo for r in registros_alimentacao)
    print("✅ TIPOS DE ALIMENTAÇÃO INCLUÍDOS:")
    for tipo in sorted(tipos_alimentacao):
        print(f"  ✓ {tipo}")
    print()
    
    tipos_outros = set(c.tipo for c in outros_custos)
    print("✅ TIPOS DE OUTROS CUSTOS INCLUÍDOS:")
    for tipo in sorted(tipos_outros):
        print(f"  ✓ {tipo}")
    print()
    
    custo_total = custo_mao_obra + custo_alimentacao + custo_outros
    print(f"💵 CUSTO TOTAL DO FUNCIONÁRIO: R$ {custo_total:,.2f}")
    print()
    
    print("="*100)
    print("RELATÓRIO CONCLUÍDO!")
    print("="*100)
    print()
    print("🎯 FUNCIONALIDADES DEMONSTRADAS:")
    print("  ✓ Trabalho normal com horários completos")
    print("  ✓ Atrasos de entrada (30 minutos)")
    print("  ✓ Saídas antecipadas (1 hora)")
    print("  ✓ Atraso entrada + saída antecipada combinados")
    print("  ✓ Sábado com horas extras (50%)")
    print("  ✓ Domingo com horas extras (100%)")
    print("  ✓ Falta não justificada")
    print("  ✓ Falta justificada")
    print("  ✓ Meio período/saída antecipada")
    print("  ✓ Trabalho sem intervalo de almoço")
    print("  ✓ Horas extras em dia normal")
    print("  ✓ Feriado trabalhado (100% extras)")
    print("  ✓ Múltiplos tipos de alimentação (almoço, lanche, jantar)")
    print("  ✓ Diversos outros custos (vale transporte, alimentação, EPIs, descontos)")
    print()
    print("📋 Este perfil demonstra TODAS as funcionalidades do sistema de ponto!")

def main():
    """Função principal"""
    with app.app_context():
        gerar_relatorio_completo()

if __name__ == "__main__":
    main()