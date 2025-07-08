"""
ENGINE DE CÁLCULO DE KPIs v3.0 - SIGE
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Implementa as regras de negócio específicas para cálculo correto de KPIs
conforme especificação técnica v3.0.

Regras fundamentais:
1. Faltas = dias úteis sem registro de entrada
2. Atrasos = entrada tardia + saída antecipada (em HORAS)
3. Horas Perdidas = Faltas (em horas) + Atrasos (em horas)
4. Custo = Tempo trabalhado + Faltas justificadas

Data: 04 de Julho de 2025
"""

from datetime import datetime, date, timedelta
from sqlalchemy import and_, func, text
from app import db
import calendar


def calcular_kpis_funcionario_v3(funcionario_id, data_inicio=None, data_fim=None):
    """
    Calcula KPIs de um funcionário conforme especificação v3.0
    
    Args:
        funcionario_id: ID do funcionário
        data_inicio: Data de início do período (opcional)
        data_fim: Data de fim do período (opcional)
    
    Returns:
        dict: Dicionário com os 10 KPIs calculados
    """
    from models import Funcionario, RegistroPonto, RegistroAlimentacao, Ocorrencia, TipoOcorrencia
    
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
    
    # 1. HORAS TRABALHADAS
    horas_trabalhadas = db.session.query(
        func.coalesce(func.sum(RegistroPonto.horas_trabalhadas), 0)
    ).filter(
        and_(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.hora_entrada.isnot(None)
        )
    ).scalar() or 0
    
    # 2. HORAS EXTRAS
    horas_extras = db.session.query(
        func.coalesce(func.sum(RegistroPonto.horas_extras), 0)
    ).filter(
        and_(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_extras > 0
        )
    ).scalar() or 0
    
    # 3. FALTAS (dias úteis sem registro de entrada)
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    
    dias_com_presenca = db.session.query(
        func.count(RegistroPonto.data.distinct())
    ).filter(
        and_(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.hora_entrada.isnot(None)
        )
    ).scalar() or 0
    
    # 3. FALTAS (apenas registros explícitos de falta no sistema)
    faltas = db.session.query(RegistroPonto).filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
    ).count()
    
    # 4. ATRASOS (em horas)
    # Buscar atrasos em minutos e converter para horas
    total_atrasos_minutos = db.session.query(
        func.coalesce(func.sum(RegistroPonto.total_atraso_minutos), 0)
    ).filter(
        and_(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.total_atraso_minutos > 0
        )
    ).scalar() or 0
    
    # Converter minutos para horas
    total_atrasos_horas = total_atrasos_minutos / 60.0
    
    # 5. PRODUTIVIDADE (horas_trabalhadas/horas_esperadas × 100)
    horas_esperadas = dias_uteis * 8  # 8 horas por dia útil
    produtividade = (horas_trabalhadas / horas_esperadas * 100) if horas_esperadas > 0 else 0
    
    # 6. ABSENTEÍSMO (faltas registradas/dias_úteis × 100)
    absenteismo = (faltas / dias_uteis * 100) if dias_uteis > 0 else 0
    
    # 7. MÉDIA DIÁRIA (horas trabalhadas / dias com presença)
    media_diaria = (horas_trabalhadas / dias_com_presenca) if dias_com_presenca > 0 else 0
    
    # 8. HORAS PERDIDAS (faltas registradas em horas + atrasos em horas)
    horas_faltas = faltas * 8  # 8 horas por falta registrada no sistema
    horas_perdidas = horas_faltas + total_atrasos_horas
    
    # 9. CUSTO MÃO DE OBRA (horas trabalhadas + faltas justificadas)
    # Buscar faltas justificadas: ocorrências aprovadas que cobrem dias úteis
    faltas_justificadas_count = 0
    
    try:
        ocorrencias_aprovadas = db.session.query(Ocorrencia).filter(
            and_(
                Ocorrencia.funcionario_id == funcionario_id,
                Ocorrencia.data_inicio <= data_fim,
                Ocorrencia.data_fim >= data_inicio,
                Ocorrencia.status == 'Aprovado'
            )
        ).all()
        
        # Contar dias úteis cobertos por ocorrências justificadas
        for ocorrencia in ocorrencias_aprovadas:
            inicio_periodo = max(ocorrencia.data_inicio, data_inicio)
            fim_periodo = min(ocorrencia.data_fim, data_fim)
            faltas_justificadas_count += calcular_dias_uteis(inicio_periodo, fim_periodo)
            
    except Exception as e:
        # Fallback se tabela Ocorrencia não existir
        faltas_justificadas_count = 0
    
    faltas_justificadas = faltas_justificadas_count
    
    # Calcular custo
    salario_hora = funcionario.salario / 220 if funcionario.salario else 0  # 220 horas/mês
    horas_para_custo = horas_trabalhadas + (faltas_justificadas * 8)
    custo_mao_obra = horas_para_custo * salario_hora
    
    # 10. CUSTO ALIMENTAÇÃO
    custo_alimentacao = db.session.query(
        func.coalesce(func.sum(RegistroAlimentacao.valor), 0)
    ).filter(
        and_(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        )
    ).scalar() or 0
    
    return {
        'funcionario': funcionario,
        'horas_trabalhadas': float(horas_trabalhadas),
        'horas_extras': float(horas_extras),
        'faltas': int(faltas),
        'atrasos': float(total_atrasos_horas),
        'produtividade': float(produtividade),
        'absenteismo': float(absenteismo),
        'media_diaria': float(media_diaria),
        'horas_perdidas': float(horas_perdidas),
        'custo_mao_obra': float(custo_mao_obra),
        'custo_alimentacao': float(custo_alimentacao),
        'dias_uteis': dias_uteis,
        'dias_com_presenca': dias_com_presenca,
        'faltas_justificadas': faltas_justificadas,
        'horas_esperadas': horas_esperadas,
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