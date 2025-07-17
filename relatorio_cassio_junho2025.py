#!/usr/bin/env python3
"""
Relatório Completo das KPIs - Cássio Viller Silva de Azevedo - Junho/2025
SIGE v6.3 - Sistema Integrado de Gestão Empresarial
"""

import os
import sys
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configurar conexão com o banco
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///sige.db')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def buscar_funcionario_cassio():
    """Buscar dados do funcionário Cássio"""
    query = text("""
        SELECT f.id, f.codigo, f.nome, f.salario, d.nome as departamento, fn.nome as funcao
        FROM funcionario f
        LEFT JOIN departamento d ON f.departamento_id = d.id
        LEFT JOIN funcao fn ON f.funcao_id = fn.id
        WHERE f.nome LIKE '%Cássio%'
    """)
    
    result = session.execute(query).fetchone()
    return result

def buscar_registros_ponto(funcionario_id, data_inicio, data_fim):
    """Buscar registros de ponto do funcionário"""
    query = text("""
        SELECT data, tipo_registro, hora_entrada, hora_saida, 
               hora_almoco_saida, hora_almoco_retorno,
               horas_trabalhadas, horas_extras, total_atraso_horas,
               minutos_atraso_entrada, minutos_atraso_saida, total_atraso_minutos
        FROM registro_ponto
        WHERE funcionario_id = :funcionario_id
        AND data >= :data_inicio
        AND data <= :data_fim
        ORDER BY data
    """)
    
    result = session.execute(query, {
        'funcionario_id': funcionario_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim
    }).fetchall()
    
    return result

def buscar_registros_alimentacao(funcionario_id, data_inicio, data_fim):
    """Buscar registros de alimentação"""
    query = text("""
        SELECT data, valor, tipo, observacoes, restaurante_id
        FROM registro_alimentacao
        WHERE funcionario_id = :funcionario_id
        AND data >= :data_inicio
        AND data <= :data_fim
        ORDER BY data
    """)
    
    result = session.execute(query, {
        'funcionario_id': funcionario_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim
    }).fetchall()
    
    return result

def buscar_outros_custos(funcionario_id, data_inicio, data_fim):
    """Buscar outros custos"""
    query = text("""
        SELECT data, tipo, valor, descricao
        FROM outro_custo
        WHERE funcionario_id = :funcionario_id
        AND data >= :data_inicio
        AND data <= :data_fim
        ORDER BY data
    """)
    
    try:
        result = session.execute(query, {
            'funcionario_id': funcionario_id,
            'data_inicio': data_inicio,
            'data_fim': data_fim
        }).fetchall()
        
        return result
    except Exception as e:
        print(f"Erro ao buscar outros custos: {e}")
        return []

def calcular_kpis_manual(funcionario_id, funcionario_salario, data_inicio, data_fim):
    """Calcular KPIs manualmente"""
    registros = buscar_registros_ponto(funcionario_id, data_inicio, data_fim)
    alimentacao = buscar_registros_alimentacao(funcionario_id, data_inicio, data_fim)
    outros_custos = buscar_outros_custos(funcionario_id, data_inicio, data_fim)
    
    # Calcular totais
    total_horas_trabalhadas = sum(r.horas_trabalhadas or 0 for r in registros)
    total_horas_extras = sum(r.horas_extras or 0 for r in registros)
    total_atrasos_horas = sum(r.total_atraso_horas or 0 for r in registros)
    
    # Contar faltas por tipo
    faltas_nao_justificadas = sum(1 for r in registros if r.tipo_registro == 'falta')
    faltas_justificadas = sum(1 for r in registros if r.tipo_registro == 'falta_justificada')
    
    # Contar dias com lançamento (trabalho programado)
    dias_com_lancamento = sum(1 for r in registros if r.tipo_registro in [
        'trabalho_normal', 'feriado_trabalhado', 'meio_periodo', 'falta', 'falta_justificada'
    ])
    
    # Calcular dias úteis (aproximado - 21 dias em junho/2025)
    dias_uteis = 21
    
    # Calcular KPIs
    produtividade = (total_horas_trabalhadas / (dias_uteis * 8)) * 100 if dias_uteis > 0 else 0
    absenteismo = (faltas_nao_justificadas / dias_com_lancamento) * 100 if dias_com_lancamento > 0 else 0
    media_diaria = total_horas_trabalhadas / len([r for r in registros if r.hora_entrada]) if len([r for r in registros if r.hora_entrada]) > 0 else 0
    horas_perdidas = (faltas_nao_justificadas * 8) + total_atrasos_horas
    
    # Calcular custos
    valor_hora = funcionario_salario / 220 if funcionario_salario else 0
    custo_mao_obra = (total_horas_trabalhadas * valor_hora) + (total_horas_extras * valor_hora * 1.5)
    custo_alimentacao = sum(r.valor for r in alimentacao)
    
    # Separar custos de transporte e outros
    custo_transporte = sum(r.valor for r in outros_custos if 'transporte' in r.tipo.lower())
    outros_custos_valor = sum(r.valor for r in outros_custos if 'transporte' not in r.tipo.lower())
    
    # Calcular eficiência e valor falta justificada
    eficiencia = max(0, produtividade - min(faltas_nao_justificadas * 5, 20))
    valor_falta_justificada = faltas_justificadas * 8 * valor_hora
    
    return {
        'horas_trabalhadas': total_horas_trabalhadas,
        'horas_extras': total_horas_extras,
        'faltas': faltas_nao_justificadas,
        'atrasos_horas': total_atrasos_horas,
        'produtividade': produtividade,
        'absenteismo': absenteismo,
        'media_diaria': media_diaria,
        'faltas_justificadas': faltas_justificadas,
        'custo_mao_obra': custo_mao_obra,
        'custo_alimentacao': custo_alimentacao,
        'custo_transporte': custo_transporte,
        'outros_custos': outros_custos_valor,
        'horas_perdidas': horas_perdidas,
        'eficiencia': eficiencia,
        'valor_falta_justificada': valor_falta_justificada,
        'dias_uteis': dias_uteis,
        'dias_com_lancamento': dias_com_lancamento,
        'valor_hora': valor_hora
    }

def gerar_relatorio():
    """Gerar relatório completo"""
    print("=" * 80)
    print("RELATÓRIO COMPLETO DAS KPIs - CÁSSIO VILLER SILVA DE AZEVEDO")
    print("PERÍODO: JUNHO/2025")
    print("SIGE v6.3 - Sistema Integrado de Gestão Empresarial")
    print("=" * 80)
    
    # Buscar funcionário
    funcionario = buscar_funcionario_cassio()
    if not funcionario:
        print("ERRO: Funcionário Cássio não encontrado!")
        return
    
    print(f"\n📋 DADOS DO FUNCIONÁRIO:")
    print(f"  ID: {funcionario.id}")
    print(f"  Código: {funcionario.codigo}")
    print(f"  Nome: {funcionario.nome}")
    print(f"  Salário: R$ {funcionario.salario:,.2f}")
    print(f"  Departamento: {funcionario.departamento or 'Não definido'}")
    print(f"  Função: {funcionario.funcao or 'Não definida'}")
    
    # Período
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Buscar registros
    registros = buscar_registros_ponto(funcionario.id, data_inicio, data_fim)
    alimentacao = buscar_registros_alimentacao(funcionario.id, data_inicio, data_fim)
    outros_custos = buscar_outros_custos(funcionario.id, data_inicio, data_fim)
    
    print(f"\n⏰ REGISTROS DE PONTO ({len(registros)} registros):")
    print("  Data       | Tipo              | Entrada | Saída   | Almoço      | Horas T. | Extras | Atrasos")
    print("  " + "-" * 85)
    
    for r in registros:
        almoco = f"{r.hora_almoco_saida}-{r.hora_almoco_retorno}" if r.hora_almoco_saida else "-"
        print(f"  {r.data} | {(r.tipo_registro or 'N/A'):<17} | {r.hora_entrada or '-':<7} | {r.hora_saida or '-':<7} | {almoco:<11} | {r.horas_trabalhadas or 0:>6.1f}h | {r.horas_extras or 0:>4.1f}h | {r.total_atraso_horas or 0:>5.1f}h")
    
    print(f"\n🍽️  REGISTROS DE ALIMENTAÇÃO ({len(alimentacao)} registros):")
    total_alimentacao = sum(r.valor for r in alimentacao)
    print(f"  Total gasto: R$ {total_alimentacao:,.2f}")
    
    print(f"\n💰 OUTROS CUSTOS ({len(outros_custos)} registros):")
    total_outros = sum(r.valor for r in outros_custos)
    print(f"  Total: R$ {total_outros:,.2f}")
    for r in outros_custos:
        print(f"  {r.data} | {r.tipo:<20} | R$ {r.valor:>8.2f} | {r.descricao or '-'}")
    
    # Calcular KPIs
    kpis = calcular_kpis_manual(funcionario.id, funcionario.salario, data_inicio, data_fim)
    
    print(f"\n📊 KPIS CALCULADOS (Layout 4-4-4-3):")
    print(f"\n  PRIMEIRA LINHA (4 indicadores):")
    print(f"    1. Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"    2. Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"    3. Faltas: {kpis['faltas']}")
    print(f"    4. Atrasos: {kpis['atrasos_horas']:.2f}h")
    
    print(f"\n  SEGUNDA LINHA (4 indicadores):")
    print(f"    5. Produtividade: {kpis['produtividade']:.1f}%")
    print(f"    6. Absenteísmo: {kpis['absenteismo']:.1f}%")
    print(f"    7. Média Diária: {kpis['media_diaria']:.1f}h")
    print(f"    8. Faltas Justificadas: {kpis['faltas_justificadas']}")
    
    print(f"\n  TERCEIRA LINHA (4 indicadores):")
    print(f"    9. Custo Mão de Obra: R$ {kpis['custo_mao_obra']:,.2f}")
    print(f"    10. Custo Alimentação: R$ {kpis['custo_alimentacao']:,.2f}")
    print(f"    11. Custo Transporte: R$ {kpis['custo_transporte']:,.2f}")
    print(f"    12. Outros Custos: R$ {kpis['outros_custos']:,.2f}")
    
    print(f"\n  QUARTA LINHA (3 indicadores):")
    print(f"    13. Horas Perdidas: {kpis['horas_perdidas']:.1f}h")
    print(f"    14. Eficiência: {kpis['eficiencia']:.1f}%")
    print(f"    15. Valor Falta Justificada: R$ {kpis['valor_falta_justificada']:,.2f}")
    
    print(f"\n🔍 DETALHAMENTO DOS CÁLCULOS:")
    print(f"  Dias úteis (junho/2025): {kpis['dias_uteis']} dias")
    print(f"  Dias com lançamento: {kpis['dias_com_lancamento']} dias")
    print(f"  Valor/hora: R$ {kpis['valor_hora']:.2f}")
    print(f"  Horas esperadas: {kpis['dias_uteis'] * 8}h (21 dias × 8h)")
    print(f"  Produtividade: {kpis['horas_trabalhadas']:.1f}h ÷ {kpis['dias_uteis'] * 8}h × 100 = {kpis['produtividade']:.1f}%")
    print(f"  Absenteísmo: {kpis['faltas']} faltas ÷ {kpis['dias_com_lancamento']} dias × 100 = {kpis['absenteismo']:.1f}%")
    print(f"  Horas perdidas: ({kpis['faltas']} × 8h) + {kpis['atrasos_horas']:.2f}h = {kpis['horas_perdidas']:.1f}h")
    print(f"  Eficiência: {kpis['produtividade']:.1f}% - ({kpis['faltas']} × 5%) = {kpis['eficiencia']:.1f}%")
    
    custo_total = kpis['custo_mao_obra'] + kpis['custo_alimentacao'] + kpis['custo_transporte'] + kpis['outros_custos']
    print(f"\n💵 CUSTO TOTAL DO FUNCIONÁRIO: R$ {custo_total:,.2f}")
    
    print(f"\n" + "=" * 80)
    print("RELATÓRIO GERADO COM SUCESSO!")
    print("=" * 80)

if __name__ == "__main__":
    gerar_relatorio()