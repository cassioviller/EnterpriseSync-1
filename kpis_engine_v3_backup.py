"""
ENGINE DE CÁLCULO DE KPIs v3.1 - SIGE
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Implementa as regras de negócio específicas para cálculo correto de KPIs
conforme especificação técnica v3.1.

Regras fundamentais:
1. Produtividade = horas trabalhadas ÷ (dias_com_lancamento × 8)
2. Absenteísmo = faltas ÷ dias_com_lancamento
3. Média Diária = horas trabalhadas ÷ dias_com_lancamento
4. Horas Perdidas = (faltas × 8) + atrasos em horas

Data: 13 de Julho de 2025
"""

from datetime import datetime, date, timedelta
from sqlalchemy import and_, func, text
from app import db
import calendar


def contar_dias_com_lancamento(registros):
    """
    Conta dias únicos que representam tempo programado para trabalho
    """
    tipos_programados = [
        'trabalho_normal', 'sabado_horas_extras', 'domingo_horas_extras',
        'feriado_trabalhado', 'meio_periodo', 'falta', 'falta_justificada',
        'atraso', 'saida_antecipada'
    ]
    
    # Filtrar apenas registros de dias programados
    registros_programados = [
        r for r in registros 
        if r.tipo_registro in tipos_programados
    ]
    
    # Contar dias únicos
    dias_unicos = set(r.data for r in registros_programados)
    
    return len(dias_unicos)


def contar_horas_trabalhadas(registros):
    """
    Conta horas efetivamente trabalhadas (exclui faltas)
    """
    tipos_com_horas = [
        'trabalho_normal', 'sabado_horas_extras', 'domingo_horas_extras',
        'feriado_trabalhado', 'meio_periodo', 'atraso', 'saida_antecipada'
    ]
    
    horas_total = 0
    for registro in registros:
        if registro.tipo_registro in tipos_com_horas:
            horas_total += registro.horas_trabalhadas or 0
    
    return horas_total


def contar_faltas(registros):
    """
    Conta faltas não justificadas
    """
    faltas = [r for r in registros if r.tipo_registro == 'falta']
    return len(faltas)


def contar_faltas_justificadas(registros):
    """
    Conta faltas justificadas
    """
    faltas_just = [r for r in registros if r.tipo_registro == 'falta_justificada']
    return len(faltas_just)


def contar_horas_extras(registros):
    """
    Conta horas extras
    """
    horas_extras = 0
    for registro in registros:
        if registro.horas_extras:
            horas_extras += registro.horas_extras
    return horas_extras


def contar_atrasos_em_horas(registros):
    """
    Conta atrasos em horas
    """
    atrasos_total = 0
    for registro in registros:
        if registro.total_atraso_horas:
            atrasos_total += registro.total_atraso_horas
    return atrasos_total


def calcular_kpis_funcionario_v3(funcionario_id, data_inicio=None, data_fim=None):
    """
    Calcula KPIs de um funcionário conforme especificação v3.1
    
    Args:
        funcionario_id: ID do funcionário
        data_inicio: Data de início do período (opcional)
        data_fim: Data de fim do período (opcional)
    
    Returns:
        dict: Dicionário com os 15 KPIs calculados
    """
    from models import Funcionario, RegistroPonto, RegistroAlimentacao, OutroCusto
    
    # Buscar funcionário
    funcionario = Funcionario.query.get(funcionario_id)
    if not funcionario:
        return None
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        hoje = date.today()
        data_inicio = hoje.replace(day=1)
    if not data_fim:
        data_fim = date.today()
    
    # Buscar todos os registros do período
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    # NOVA LÓGICA: Usar funções auxiliares baseadas em dias_com_lancamento
    dias_com_lancamento = contar_dias_com_lancamento(registros)
    horas_trabalhadas = contar_horas_trabalhadas(registros)
    faltas = contar_faltas(registros)
    faltas_justificadas = contar_faltas_justificadas(registros)
    horas_extras = contar_horas_extras(registros)
    atrasos_em_horas = contar_atrasos_em_horas(registros)
    
    # PRODUTIVIDADE CORRIGIDA (baseada em dias_com_lancamento)
    if dias_com_lancamento > 0:
        horas_esperadas = dias_com_lancamento * 8
        produtividade = (horas_trabalhadas / horas_esperadas) * 100
    else:
        produtividade = 0
        horas_esperadas = 0
    
    # ABSENTEÍSMO CORRIGIDO (baseado em dias_com_lancamento)
    if dias_com_lancamento > 0:
        absenteismo = (faltas / dias_com_lancamento) * 100
    else:
        absenteismo = 0
    
    # MÉDIA DIÁRIA CORRIGIDA (baseada em dias_com_lancamento)
    if dias_com_lancamento > 0:
        media_diaria = horas_trabalhadas / dias_com_lancamento
    else:
        media_diaria = 0
    
    # HORAS PERDIDAS (faltas não justificadas em horas + atrasos em horas)
    horas_perdidas = (faltas * 8) + atrasos_em_horas
    
    # EFICIÊNCIA (produtividade ajustada por qualidade)
    eficiencia = produtividade * (1 - (absenteismo / 100)) if absenteismo < 100 else 0
    
    # Calcular custos
    salario_hora = funcionario.salario / 220 if funcionario.salario else 0  # 220 horas/mês
    
    # Custo mão de obra (incluindo horas extras)
    custo_normal = horas_trabalhadas * salario_hora
    custo_extras = horas_extras * salario_hora * 1.5  # 50% adicional médio
    custo_mao_obra = custo_normal + custo_extras
    
    # Custo alimentação
    custo_alimentacao = db.session.query(
        func.coalesce(func.sum(RegistroAlimentacao.valor), 0)
    ).filter(
        and_(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        )
    ).scalar() or 0
    
    # Custo transporte (aproximação)
    custo_transporte = 0.0
    
    # Outros custos
    outros_custos = db.session.query(
        func.coalesce(func.sum(OutroCusto.valor), 0)
    ).filter(
        and_(
            OutroCusto.funcionario_id == funcionario_id,
            OutroCusto.data >= data_inicio,
            OutroCusto.data <= data_fim
        )
    ).scalar() or 0
    
    # Custo total
    custo_total = custo_mao_obra + custo_alimentacao + custo_transporte + outros_custos
    
    return {
        'funcionario': funcionario,
        
        # LINHA 1: KPIs Básicos (4)
        'horas_trabalhadas': float(horas_trabalhadas),
        'horas_extras': float(horas_extras),
        'faltas': int(faltas),
        'atrasos': float(atrasos_em_horas),
        
        # LINHA 2: KPIs Analíticos (4) - TODOS CORRIGIDOS
        'produtividade': float(round(produtividade, 1)),
        'absenteismo': float(round(absenteismo, 1)),
        'media_diaria': float(round(media_diaria, 1)),
        'faltas_justificadas': int(faltas_justificadas),
        
        # LINHA 3: KPIs Financeiros (4)
        'custo_mao_obra': float(custo_mao_obra),
        'custo_alimentacao': float(custo_alimentacao),
        'custo_transporte': float(custo_transporte),
        'outros_custos': float(outros_custos),
        
        # LINHA 4: KPIs Resumo (3)
        'custo_total': float(custo_total),
        'eficiencia': float(round(eficiencia, 1)),
        'horas_perdidas': float(round(horas_perdidas, 1)),
        
        # Dados auxiliares
        'dias_com_lancamento': dias_com_lancamento,
        'horas_esperadas': horas_esperadas,
        'periodo': f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    }
        'media_diaria': float(media_diaria),
        'faltas_justificadas': int(faltas_justificadas),
        
        # LINHA 3: KPIs Financeiros (4)
        'custo_mao_obra': float(custo_mao_obra),
        'custo_alimentacao': float(custo_alimentacao),
        'custo_transporte': float(custo_transporte),
        'outros_custos': float(outros_custos),
        
        # LINHA 4: KPIs Resumo (3)
        'custo_total': float(custo_total),
        'eficiencia': float(eficiencia),
        'horas_perdidas': float(horas_perdidas),
        
        # Dados auxiliares
        'dias_uteis': dias_uteis,
        'dias_com_presenca': dias_com_presenca,
        'horas_esperadas': horas_esperadas,
        'salario_hora': float(salario_hora),
        'periodo': f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    }


def calcular_dias_uteis(data_inicio, data_fim):
    """
    Calcula número de dias úteis no período (segunda a sexta, exceto feriados)
    
    Args:
        data_inicio: Data de início
        data_fim: Data de fim
    
    Returns:
        int: Número de dias úteis
    """
    # Feriados nacionais completos para 2025
    feriados_2025 = [
        date(2025, 1, 1),   # Ano Novo
        date(2025, 2, 17),  # Carnaval (Segunda-feira)
        date(2025, 2, 18),  # Carnaval (Terça-feira)
        date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
        date(2025, 4, 21),  # Tiradentes
        date(2025, 5, 1),   # Dia do Trabalhador
        date(2025, 6, 19),  # Corpus Christi
        date(2025, 9, 7),   # Independência
        date(2025, 10, 12), # Nossa Senhora Aparecida
        date(2025, 11, 2),  # Finados
        date(2025, 11, 15), # Proclamação da República
        date(2025, 12, 25), # Natal
    ]
    
    dias_uteis = 0
    data_atual = data_inicio
    
    while data_atual <= data_fim:
        # Segunda a sexta (0-6, onde 0=segunda)
        if data_atual.weekday() < 5:
            # Verificar se não é feriado
            if data_atual not in feriados_2025:
                dias_uteis += 1
        
        data_atual += timedelta(days=1)
    
    return dias_uteis


def atualizar_calculos_ponto(registro_ponto_id):
    """
    Atualiza cálculos automáticos de um registro de ponto
    Implementa triggers para cálculo de atrasos e horas
    
    Args:
        registro_ponto_id: ID do registro de ponto
    """
    from models import RegistroPonto, Funcionario
    
    registro = RegistroPonto.query.get(registro_ponto_id)
    if not registro:
        return
    
    funcionario = Funcionario.query.get(registro.funcionario_id)
    if not funcionario:
        return
    
    # Calcular horas trabalhadas
    if registro.hora_entrada and registro.hora_saida:
        entrada = datetime.combine(registro.data, registro.hora_entrada)
        saida = datetime.combine(registro.data, registro.hora_saida)
        
        # Descontar almoço se houver
        horas_almoco = 0
        if registro.hora_almoco_saida and registro.hora_almoco_retorno:
            saida_almoco = datetime.combine(registro.data, registro.hora_almoco_saida)
            retorno_almoco = datetime.combine(registro.data, registro.hora_almoco_retorno)
            horas_almoco = (retorno_almoco - saida_almoco).total_seconds() / 3600
        
        horas_trabalhadas = (saida - entrada).total_seconds() / 3600 - horas_almoco
        registro.horas_trabalhadas = max(0, horas_trabalhadas)
        
        # Calcular horas extras (acima de 8 horas)
        registro.horas_extras = max(0, horas_trabalhadas - 8)
    
    # Calcular atrasos usando horário de trabalho
    minutos_atraso_entrada = 0
    minutos_atraso_saida = 0
    
    if funcionario.horario_trabalho:
        if registro.hora_entrada and funcionario.horario_trabalho.entrada:
            if registro.hora_entrada > funcionario.horario_trabalho.entrada:
                entrada_esperada = datetime.combine(registro.data, funcionario.horario_trabalho.entrada)
                entrada_real = datetime.combine(registro.data, registro.hora_entrada)
                minutos_atraso_entrada = (entrada_real - entrada_esperada).total_seconds() / 60
        
        if registro.hora_saida and funcionario.horario_trabalho.saida:
            if registro.hora_saida < funcionario.horario_trabalho.saida:
                saida_esperada = datetime.combine(registro.data, funcionario.horario_trabalho.saida)
                saida_real = datetime.combine(registro.data, registro.hora_saida)
                minutos_atraso_saida = (saida_esperada - saida_real).total_seconds() / 60
    
    # Atualizar campos calculados
    registro.minutos_atraso_entrada = minutos_atraso_entrada
    registro.minutos_atraso_saida = minutos_atraso_saida
    registro.total_atraso_minutos = minutos_atraso_entrada + minutos_atraso_saida
    registro.total_atraso_horas = (minutos_atraso_entrada + minutos_atraso_saida) / 60
    
    db.session.commit()


def identificar_faltas_periodo(funcionario_id, data_inicio, data_fim):
    """
    Identifica dias de falta de um funcionário em um período específico
    
    Args:
        funcionario_id: ID do funcionário
        data_inicio: Data de início do período
        data_fim: Data de fim do período
    
    Returns:
        set: Conjunto de datas que são dias de falta
    """
    from models import RegistroPonto
    
    # Buscar registros de ponto do funcionário no período
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    # Criar conjunto de datas com registro de entrada
    datas_com_entrada = {r.data for r in registros_ponto if r.hora_entrada}
    
    # Feriados nacionais completos para 2025
    feriados_2025 = [
        date(2025, 1, 1),   # Ano Novo
        date(2025, 2, 17),  # Carnaval (Segunda-feira)
        date(2025, 2, 18),  # Carnaval (Terça-feira)
        date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
        date(2025, 4, 21),  # Tiradentes
        date(2025, 5, 1),   # Dia do Trabalhador
        date(2025, 6, 19),  # Corpus Christi
        date(2025, 9, 7),   # Independência
        date(2025, 10, 12), # Nossa Senhora Aparecida
        date(2025, 11, 2),  # Finados
        date(2025, 11, 15), # Proclamação da República
        date(2025, 12, 25), # Natal
    ]
    
    # Identificar todos os dias úteis no período
    dias_uteis_periodo = set()
    data_atual = data_inicio
    
    while data_atual <= data_fim:
        # Verificar se é dia útil (segunda a sexta e não é feriado)
        if data_atual.weekday() < 5 and data_atual not in feriados_2025:
            dias_uteis_periodo.add(data_atual)
        data_atual += timedelta(days=1)
    
    # Faltas = dias úteis sem registro de entrada
    faltas = dias_uteis_periodo - datas_com_entrada
    
    return faltas


def processar_registros_ponto_com_faltas(funcionario_id, data_inicio, data_fim):
    """
    Processa registros de ponto adicionando informação sobre faltas
    
    Args:
        funcionario_id: ID do funcionário
        data_inicio: Data de início do período
        data_fim: Data de fim do período
    
    Returns:
        tuple: (registros_ponto, faltas_identificadas)
    """
    from models import RegistroPonto
    
    # Buscar registros de ponto
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data.desc()).all()
    
    # Identificar faltas
    faltas = identificar_faltas_periodo(funcionario_id, data_inicio, data_fim)
    
    # Adicionar propriedade is_falta aos registros
    for registro in registros_ponto:
        registro.is_falta = (registro.data in faltas)
    
    return registros_ponto, faltas