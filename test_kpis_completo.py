#!/usr/bin/env python3
"""
Teste Completo dos KPIs - SIGE v6.0
Verifica todas as funcionalidades e correções implementadas
"""

import os
import sys
from datetime import date, datetime, timedelta
from app import app, db
from models import *
from kpis_engine_v3 import calcular_kpis_funcionario_v3

def executar_todos_os_testes():
    """
    Executa todos os testes do sistema SIGE v6.0
    """
    with app.app_context():
        print("🚀 INICIANDO TESTES COMPLETOS DO SIGE v6.0")
        print("=" * 80)
        
        # Lista de testes
        testes = [
            teste_funcionario_joao,
            teste_separacao_faltas,
            teste_calculo_absenteismo,
            teste_horas_perdidas,
            teste_layout_kpis,
            teste_custos_funcionario,
            teste_dados_auxiliares,
            teste_edge_cases,
            teste_integridade_dados,
            teste_performance_kpis
        ]
        
        resultados = []
        
        for teste in testes:
            try:
                print(f"\n🔍 Executando: {teste.__name__}")
                resultado = teste()
                resultados.append((teste.__name__, resultado, None))
                print(f"✅ {teste.__name__}: {'PASSOU' if resultado else 'FALHOU'}")
            except Exception as e:
                resultados.append((teste.__name__, False, str(e)))
                print(f"❌ {teste.__name__}: ERRO - {str(e)}")
        
        # Relatório final
        print("\n" + "=" * 80)
        print("📊 RELATÓRIO FINAL DOS TESTES")
        print("=" * 80)
        
        passou = sum(1 for _, resultado, _ in resultados if resultado)
        total = len(resultados)
        
        print(f"✅ Testes que passaram: {passou}/{total}")
        print(f"❌ Testes que falharam: {total - passou}/{total}")
        print(f"📈 Taxa de sucesso: {(passou/total)*100:.1f}%")
        
        print("\n📋 DETALHES:")
        for nome, resultado, erro in resultados:
            status = "✅ PASSOU" if resultado else "❌ FALHOU"
            print(f"  {status}: {nome}")
            if erro:
                print(f"    Erro: {erro}")
        
        if passou == total:
            print("\n🎉 TODOS OS TESTES PASSARAM! Sistema funcionando corretamente.")
        else:
            print(f"\n⚠️ {total - passou} teste(s) falharam. Verifique os problemas acima.")
        
        return passou == total

def teste_funcionario_joao():
    """
    Testa os KPIs do funcionário João Silva dos Santos (F0099)
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        print("  ❌ Funcionário F0099 não encontrado")
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    if not kpis:
        print("  ❌ Erro ao calcular KPIs")
        return False
    
    # Verificações específicas
    verificacoes = [
        (kpis['faltas'] == 1, f"Faltas não justificadas: {kpis['faltas']} (esperado: 1)"),
        (abs(kpis['absenteismo'] - 5.0) < 0.1, f"Absenteísmo: {kpis['absenteismo']}% (esperado: 5.0%)"),
        (abs(kpis['horas_perdidas'] - 10.25) < 0.1, f"Horas perdidas: {kpis['horas_perdidas']}h (esperado: 10.25h)"),
        (kpis['horas_extras'] == 18.0, f"Horas extras: {kpis['horas_extras']}h (esperado: 18.0h)"),
        ('faltas_justificadas' in kpis, "KPI 'Faltas Justificadas' existe"),
        ('custo_total' in kpis, "KPI 'Custo Total' existe"),
        ('eficiencia' in kpis, "KPI 'Eficiência' existe"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_separacao_faltas():
    """
    Testa se a separação de faltas justificadas e não justificadas está funcionando
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Contar faltas no banco
    faltas_nao_justificadas = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro == 'falta'
    ).count()
    
    faltas_justificadas = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro == 'falta_justificada'
    ).count()
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    verificacoes = [
        (kpis['faltas'] == faltas_nao_justificadas, f"Faltas não justificadas: KPI={kpis['faltas']}, BD={faltas_nao_justificadas}"),
        (kpis['faltas_justificadas'] == faltas_justificadas, f"Faltas justificadas: KPI={kpis['faltas_justificadas']}, BD={faltas_justificadas}"),
        (faltas_nao_justificadas >= 0, "Faltas não justificadas >= 0"),
        (faltas_justificadas >= 0, "Faltas justificadas >= 0"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_calculo_absenteismo():
    """
    Testa se o cálculo do absenteísmo está correto
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    # Calcular absenteísmo manualmente
    dias_uteis = kpis['dias_uteis']
    faltas_nao_justificadas = kpis['faltas']
    absenteismo_esperado = (faltas_nao_justificadas / dias_uteis * 100) if dias_uteis > 0 else 0
    
    verificacoes = [
        (abs(kpis['absenteismo'] - absenteismo_esperado) < 0.1, 
         f"Absenteísmo: {kpis['absenteismo']}% vs esperado: {absenteismo_esperado:.1f}%"),
        (kpis['absenteismo'] <= 100, f"Absenteísmo não pode ser > 100%: {kpis['absenteismo']}%"),
        (kpis['absenteismo'] >= 0, f"Absenteísmo não pode ser negativo: {kpis['absenteismo']}%"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_horas_perdidas():
    """
    Testa se o cálculo das horas perdidas está correto
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    # Calcular horas perdidas manualmente
    horas_perdidas_esperadas = (kpis['faltas'] * 8) + kpis['atrasos']
    
    verificacoes = [
        (abs(kpis['horas_perdidas'] - horas_perdidas_esperadas) < 0.1,
         f"Horas perdidas: {kpis['horas_perdidas']}h vs esperado: {horas_perdidas_esperadas:.1f}h"),
        (kpis['horas_perdidas'] >= 0, f"Horas perdidas não pode ser negativo: {kpis['horas_perdidas']}h"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_layout_kpis():
    """
    Testa se todos os KPIs necessários estão presentes (Layout 4-4-4-3)
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    # KPIs obrigatórios para layout 4-4-4-3 (15 KPIs)
    kpis_obrigatorios = [
        # Linha 1: Básicos (4)
        'horas_trabalhadas', 'horas_extras', 'faltas', 'atrasos',
        # Linha 2: Analíticos (4)
        'produtividade', 'absenteismo', 'media_diaria', 'faltas_justificadas',
        # Linha 3: Financeiros (4)
        'custo_mao_obra', 'custo_alimentacao', 'custo_transporte', 'outros_custos',
        # Linha 4: Resumo (3)
        'custo_total', 'eficiencia', 'horas_perdidas'
    ]
    
    verificacoes = []
    for kpi in kpis_obrigatorios:
        existe = kpi in kpis
        verificacoes.append((existe, f"KPI '{kpi}' existe"))
        print(f"    {'✅' if existe else '❌'} KPI '{kpi}': {'Existe' if existe else 'FALTANDO'}")
        if not existe:
            return False
    
    print(f"    ✅ Total de KPIs encontrados: {len([k for k in kpis_obrigatorios if k in kpis])}/{len(kpis_obrigatorios)}")
    
    # Verificar se é exatamente 15 KPIs principais
    return len(kpis_obrigatorios) == 15

def teste_custos_funcionario():
    """
    Testa se os cálculos de custos estão corretos
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    # Calcular custo total manualmente
    custo_total_esperado = (kpis['custo_mao_obra'] + kpis['custo_alimentacao'] + 
                           kpis['custo_transporte'] + kpis['outros_custos'])
    
    verificacoes = [
        (kpis['custo_mao_obra'] > 0, f"Custo mão de obra: R$ {kpis['custo_mao_obra']:,.2f}"),
        (kpis['custo_alimentacao'] >= 0, f"Custo alimentação: R$ {kpis['custo_alimentacao']:,.2f}"),
        (kpis['outros_custos'] >= 0, f"Outros custos: R$ {kpis['outros_custos']:,.2f}"),
        (isinstance(kpis['custo_mao_obra'], (int, float)), "Custo mão de obra é numérico"),
        (abs(kpis['custo_total'] - custo_total_esperado) < 0.01, 
         f"Custo total: R$ {kpis['custo_total']:,.2f} vs esperado: R$ {custo_total_esperado:,.2f}"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_dados_auxiliares():
    """
    Testa se os dados auxiliares estão corretos
    """
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    
    verificacoes = [
        (kpis['dias_uteis'] == 20, f"Dias úteis junho/2025: {kpis['dias_uteis']} (esperado: 20)"),
        (kpis['horas_esperadas'] == 160, f"Horas esperadas: {kpis['horas_esperadas']}h (esperado: 160h)"),
        (kpis['dias_com_presenca'] > 0, f"Dias com presença: {kpis['dias_com_presenca']}"),
        ('periodo' in kpis, "Campo 'periodo' existe"),
        ('salario_hora' in kpis, "Campo 'salario_hora' existe"),
        (kpis['salario_hora'] > 0, f"Salário/hora: R$ {kpis['salario_hora']:,.2f}"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_edge_cases():
    """
    Testa casos extremos e validações
    """
    # Teste com funcionário sem registros
    funcionario_sem_registros = Funcionario.query.filter(
        ~Funcionario.id.in_(
            db.session.query(RegistroPonto.funcionario_id).distinct()
        )
    ).first()
    
    if funcionario_sem_registros:
        kpis_vazio = calcular_kpis_funcionario_v3(funcionario_sem_registros.id)
        if kpis_vazio:
            verificacoes = [
                (kpis_vazio['horas_trabalhadas'] == 0, "Funcionário sem registros: 0 horas trabalhadas"),
                (kpis_vazio['faltas'] == 0, "Funcionário sem registros: 0 faltas"),
                (kpis_vazio['absenteismo'] == 0, "Funcionário sem registros: 0% absenteísmo"),
            ]
            
            for passou, mensagem in verificacoes:
                print(f"    {'✅' if passou else '❌'} {mensagem}")
                if not passou:
                    return False
    
    # Teste com período inválido
    try:
        kpis_periodo_invalido = calcular_kpis_funcionario_v3(1, date(2025, 12, 1), date(2025, 11, 1))
        print("    ✅ Sistema lida com período inválido sem crash")
    except:
        print("    ❌ Sistema falha com período inválido")
        return False
    
    # Teste com funcionário inexistente
    try:
        kpis_inexistente = calcular_kpis_funcionario_v3(99999)
        if kpis_inexistente is None:
            print("    ✅ Sistema retorna None para funcionário inexistente")
        else:
            print("    ❌ Sistema deveria retornar None para funcionário inexistente")
            return False
    except:
        print("    ❌ Sistema falha com funcionário inexistente")
        return False
    
    return True

def teste_integridade_dados():
    """
    Testa a integridade dos dados no banco
    """
    # Verificar se existem funcionários
    total_funcionarios = Funcionario.query.count()
    print(f"    📊 Total de funcionários: {total_funcionarios}")
    
    # Verificar se existem registros de ponto
    total_registros_ponto = RegistroPonto.query.count()
    print(f"    📊 Total de registros de ponto: {total_registros_ponto}")
    
    # Verificar se existe o funcionário João (F0099)
    joao = Funcionario.query.filter_by(codigo='F0099').first()
    
    verificacoes = [
        (total_funcionarios > 0, f"Existem funcionários no sistema: {total_funcionarios}"),
        (total_registros_ponto > 0, f"Existem registros de ponto: {total_registros_ponto}"),
        (joao is not None, "Funcionário João (F0099) existe"),
    ]
    
    if joao:
        registros_joao = RegistroPonto.query.filter_by(funcionario_id=joao.id).count()
        verificacoes.append((registros_joao > 0, f"João tem registros de ponto: {registros_joao}"))
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    return True

def teste_performance_kpis():
    """
    Testa a performance do cálculo de KPIs
    """
    import time
    
    funcionario = Funcionario.query.filter_by(codigo='F0099').first()
    if not funcionario:
        return False
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Medir tempo de execução
    start_time = time.time()
    kpis = calcular_kpis_funcionario_v3(funcionario.id, data_inicio, data_fim)
    end_time = time.time()
    
    tempo_execucao = end_time - start_time
    
    verificacoes = [
        (kpis is not None, "KPIs calculados com sucesso"),
        (tempo_execucao < 5.0, f"Tempo de execução aceitável: {tempo_execucao:.2f}s (< 5s)"),
    ]
    
    for passou, mensagem in verificacoes:
        print(f"    {'✅' if passou else '❌'} {mensagem}")
        if not passou:
            return False
    
    print(f"    ⏱️ Tempo de execução: {tempo_execucao:.3f} segundos")
    return True

if __name__ == "__main__":
    resultado = executar_todos_os_testes()
    sys.exit(0 if resultado else 1)