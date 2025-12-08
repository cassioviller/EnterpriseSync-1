"""
Serviço de Cálculo de Folha de Pagamento
Centraliza todos os cálculos de folha, INSS, IR, FGTS e horas extras
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional
from sqlalchemy import extract, func
from models import db, Funcionario, RegistroPonto, ParametrosLegais, ConfiguracaoSalarial, BeneficioFuncionario, CalendarioUtil, HorarioDia, HorarioTrabalho
from utils import calcular_valor_hora_periodo
import logging

logger = logging.getLogger(__name__)


# ========================================
# TABELAS DE CÁLCULO (2025)
# ========================================

TABELA_INSS_2025 = [
    {'limite': Decimal('1412.00'), 'aliquota': Decimal('7.5')},
    {'limite': Decimal('2666.68'), 'aliquota': Decimal('9.0')},
    {'limite': Decimal('4000.03'), 'aliquota': Decimal('12.0')},
    {'limite': Decimal('7786.02'), 'aliquota': Decimal('14.0')},
]

TABELA_IR_2025 = [
    {'limite': Decimal('2259.20'), 'aliquota': Decimal('0'), 'parcela_deduzir': Decimal('0')},
    {'limite': Decimal('2826.65'), 'aliquota': Decimal('7.5'), 'parcela_deduzir': Decimal('169.44')},
    {'limite': Decimal('3751.05'), 'aliquota': Decimal('15.0'), 'parcela_deduzir': Decimal('381.44')},
    {'limite': Decimal('4664.68'), 'aliquota': Decimal('22.5'), 'parcela_deduzir': Decimal('662.77')},
    {'limite': Decimal('999999.99'), 'aliquota': Decimal('27.5'), 'parcela_deduzir': Decimal('896.00')},
]

DEDUCAO_DEPENDENTE_IR = Decimal('189.59')
SALARIO_MINIMO_2025 = Decimal('1412.00')
ALIQUOTA_FGTS = Decimal('8.0')


# ========================================
# FUNÇÕES PARA PARÂMETROS LEGAIS DINÂMICOS
# ========================================

_cache_parametros_legais = {}

def _obter_parametros_legais(admin_id: int, ano: int):
    """
    Busca ParametrosLegais por admin_id e ano_vigencia.
    Cacheia o resultado para evitar queries repetidas no mesmo cálculo.
    
    Args:
        admin_id: ID do administrador
        ano: Ano de vigência dos parâmetros
        
    Returns:
        ParametrosLegais ou None se não encontrar
    """
    cache_key = (admin_id, ano)
    
    if cache_key in _cache_parametros_legais:
        return _cache_parametros_legais[cache_key]
    
    try:
        params = ParametrosLegais.query.filter_by(
            admin_id=admin_id,
            ano_vigencia=ano,
            ativo=True
        ).first()
        
        _cache_parametros_legais[cache_key] = params
        
        if params:
            logger.debug(f"[_obter_parametros_legais] Encontrado ParametrosLegais para admin={admin_id}, ano={ano}")
        else:
            logger.debug(f"[_obter_parametros_legais] Não encontrado ParametrosLegais para admin={admin_id}, ano={ano}, usando fallback")
        
        return params
    except Exception as e:
        logger.error(f"[_obter_parametros_legais] Erro ao buscar parâmetros: {e}")
        return None


def limpar_cache_parametros_legais():
    """Limpa o cache de parâmetros legais (útil após atualizações)"""
    global _cache_parametros_legais
    _cache_parametros_legais = {}
    logger.debug("[limpar_cache_parametros_legais] Cache limpo")


def _gerar_tabela_inss(params):
    """
    Gera tabela INSS a partir de ParametrosLegais.
    
    Args:
        params: Objeto ParametrosLegais ou None
        
    Returns:
        Lista de dicionários com faixas de INSS
    """
    if not params:
        return TABELA_INSS_2025
    
    return [
        {'limite': Decimal(str(params.inss_faixa1_limite)), 'aliquota': Decimal(str(params.inss_faixa1_percentual))},
        {'limite': Decimal(str(params.inss_faixa2_limite)), 'aliquota': Decimal(str(params.inss_faixa2_percentual))},
        {'limite': Decimal(str(params.inss_faixa3_limite)), 'aliquota': Decimal(str(params.inss_faixa3_percentual))},
        {'limite': Decimal(str(params.inss_faixa4_limite)), 'aliquota': Decimal(str(params.inss_faixa4_percentual))},
    ]


def _gerar_tabela_irrf(params):
    """
    Gera tabela IRRF a partir de ParametrosLegais.
    
    Args:
        params: Objeto ParametrosLegais ou None
        
    Returns:
        Lista de dicionários com faixas de IRRF
    """
    if not params:
        return TABELA_IR_2025
    
    return [
        {'limite': Decimal(str(params.irrf_isencao)), 'aliquota': Decimal('0'), 'parcela_deduzir': Decimal('0')},
        {'limite': Decimal(str(params.irrf_faixa1_limite)), 'aliquota': Decimal(str(params.irrf_faixa1_percentual)), 'parcela_deduzir': Decimal(str(params.irrf_faixa1_deducao))},
        {'limite': Decimal(str(params.irrf_faixa2_limite)), 'aliquota': Decimal(str(params.irrf_faixa2_percentual)), 'parcela_deduzir': Decimal(str(params.irrf_faixa2_deducao))},
        {'limite': Decimal(str(params.irrf_faixa3_limite)), 'aliquota': Decimal(str(params.irrf_faixa3_percentual)), 'parcela_deduzir': Decimal(str(params.irrf_faixa3_deducao))},
        {'limite': Decimal('999999.99'), 'aliquota': Decimal(str(params.irrf_faixa4_percentual)), 'parcela_deduzir': Decimal(str(params.irrf_faixa4_deducao))},
    ]


def _obter_aliquota_fgts(params) -> Decimal:
    """
    Obtém alíquota de FGTS do ParametrosLegais ou usa fallback.
    
    Args:
        params: Objeto ParametrosLegais ou None
        
    Returns:
        Decimal: Alíquota de FGTS
    """
    if params and params.fgts_percentual:
        return Decimal(str(params.fgts_percentual))
    return ALIQUOTA_FGTS


def _obter_salario_minimo(params) -> Decimal:
    """
    Obtém salário mínimo do ParametrosLegais ou usa fallback.
    
    Args:
        params: Objeto ParametrosLegais ou None
        
    Returns:
        Decimal: Valor do salário mínimo
    """
    if params and params.salario_minimo:
        return Decimal(str(params.salario_minimo))
    return SALARIO_MINIMO_2025


def _obter_deducao_dependente(params) -> Decimal:
    """
    Obtém valor de dedução por dependente do ParametrosLegais ou usa fallback.
    
    Args:
        params: Objeto ParametrosLegais ou None
        
    Returns:
        Decimal: Valor de dedução por dependente
    """
    if params and params.irrf_dependente_valor:
        return Decimal(str(params.irrf_dependente_valor))
    return DEDUCAO_DEPENDENTE_IR


# ========================================
# FUNÇÕES DE CÁLCULO DE HORAS
# ========================================

def _calcular_horas_contratuais_reais(horario_padrao, ano: int, mes: int, feriados_set=None) -> Decimal:
    """
    Calcula horas contratuais reais considerando calendário e feriados.
    Itera pelo calendário real do mês usando os HorarioDia associados.
    
    Args:
        horario_padrao: Objeto HorarioTrabalho com os dias configurados
        ano: Ano de referência
        mes: Mês de referência
        feriados_set: Set opcional de datas de feriados (para evitar nova query)
        
    Returns:
        Decimal: Total de horas contratuais do mês
    """
    import calendar
    from datetime import timedelta
    
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    
    if feriados_set is None:
        feriados_db = CalendarioUtil.query.filter(
            CalendarioUtil.data >= primeiro_dia,
            CalendarioUtil.data <= ultimo_dia,
            CalendarioUtil.eh_feriado == True
        ).all()
        feriados_set = {f.data for f in feriados_db}
    
    horarios_dia_map = {}
    for hd in horario_padrao.dias:
        horarios_dia_map[hd.dia_semana] = hd
    
    total_horas = Decimal('0')
    dia_atual = primeiro_dia
    
    while dia_atual <= ultimo_dia:
        dia_semana = dia_atual.weekday()  # 0=Segunda, 6=Domingo
        
        horario_dia = horarios_dia_map.get(dia_semana)
        
        if horario_dia and horario_dia.trabalha and dia_atual not in feriados_set:
            horas_dia = horario_dia.calcular_horas()
            total_horas += horas_dia
        
        dia_atual += timedelta(days=1)
    
    logger.debug(f"[_calcular_horas_contratuais_reais] Horário '{horario_padrao.nome}' - {mes}/{ano}: {total_horas}h contratuais")
    return total_horas


def _calcular_horas_contrato_dia(horario_padrao, dia_semana: int) -> Decimal:
    """
    Calcula as horas contratuais de um dia específico da semana.
    
    Args:
        horario_padrao: Objeto HorarioTrabalho
        dia_semana: Dia da semana (0=Segunda, 6=Domingo)
        
    Returns:
        Decimal: Horas contratuais do dia (0 se não for dia de trabalho)
    """
    horario_dia = HorarioDia.query.filter_by(
        horario_id=horario_padrao.id,
        dia_semana=dia_semana
    ).first()
    
    if not horario_dia or not horario_dia.trabalha:
        return Decimal('0')
    
    return horario_dia.calcular_horas()


def calcular_horas_mes(funcionario_id: int, ano: int, mes: int) -> Dict:
    """
    Calcula horas trabalhadas no mês baseado nos registros de ponto (CONFORME CLT)
    DIFERENCIA HE 50% (sábado/dia útil) de HE 100% (domingo/feriado)
    
    NOVA LÓGICA: Compara ponto vs horário contratual (HorarioDia)
    Se funcionário não tiver HorarioTrabalho, usa lógica legada.
    
    Returns:
        dict: {
            'total': float,
            'extras': float,
            'extras_50': float,
            'extras_100': float,
            'dias_trabalhados': int,
            'dias_uteis_esperados': int,
            'domingos_feriados': int,
            'sabados': int,
            'faltas': int,
            'horas_falta': float,
            'horas_contratuais_mes': float,
            'total_minutos_atraso': int
        }
    """
    try:
        import calendar
        from datetime import timedelta
        
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            logger.warning(f"[calcular_horas_mes] Funcionário {funcionario_id} não encontrado")
            return _resultado_vazio_horas()
        
        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
        
        feriados_calendario = CalendarioUtil.query.filter(
            CalendarioUtil.data >= primeiro_dia,
            CalendarioUtil.data <= ultimo_dia,
            CalendarioUtil.eh_feriado == True
        ).all()
        datas_feriados = {f.data for f in feriados_calendario}
        
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            extract('year', RegistroPonto.data) == ano,
            extract('month', RegistroPonto.data) == mes
        ).all()
        
        horario_trabalho = funcionario.horario_trabalho
        
        if horario_trabalho and horario_trabalho.dias.count() > 0:
            return _calcular_horas_mes_novo(
                funcionario, horario_trabalho, registros, 
                primeiro_dia, ultimo_dia, datas_feriados, ano, mes
            )
        else:
            logger.debug(f"[calcular_horas_mes] Func {funcionario_id} sem HorarioTrabalho, usando lógica legada")
            return _calcular_horas_mes_legado(
                funcionario_id, registros, primeiro_dia, ultimo_dia, datas_feriados
            )
        
    except Exception as e:
        logger.error(f"Erro ao calcular horas do mês: {e}", exc_info=True)
        return _resultado_vazio_horas()


def _resultado_vazio_horas() -> Dict:
    """Retorna resultado vazio para casos de erro ou funcionário não encontrado"""
    return {
        'total': 0,
        'extras': 0,
        'extras_50': 0,
        'extras_100': 0,
        'dias_trabalhados': 0,
        'dias_uteis_esperados': 0,
        'domingos_feriados': 0,
        'sabados': 0,
        'faltas': 0,
        'horas_falta': 0.0,
        'horas_contratuais_mes': 0.0,
        'total_minutos_atraso': 0
    }


def _calcular_horas_mes_novo(
    funcionario: Funcionario,
    horario_trabalho: HorarioTrabalho,
    registros: list,
    primeiro_dia: date,
    ultimo_dia: date,
    datas_feriados: set,
    ano: int,
    mes: int
) -> Dict:
    """
    Nova lógica de cálculo baseada em HorarioDia.
    Compara horas trabalhadas com horas contratuais para cada dia.
    """
    from datetime import timedelta
    
    horarios_dia_map = {hd.dia_semana: hd for hd in horario_trabalho.dias}
    
    registros_por_data = {}
    for reg in registros:
        registros_por_data[reg.data] = reg
    
    total_horas = Decimal('0')
    horas_extras_50 = Decimal('0')
    horas_extras_100 = Decimal('0')
    horas_falta = Decimal('0')
    horas_contratuais_mes = Decimal('0')
    dias_trabalhados = 0
    total_minutos_atraso = 0
    
    dias_uteis_esperados = 0
    domingos_feriados = 0
    sabados = 0
    
    dia_atual = primeiro_dia
    while dia_atual <= ultimo_dia:
        dia_semana = dia_atual.weekday()  # 0=Segunda, 6=Domingo
        eh_feriado = dia_atual in datas_feriados
        
        horario_dia = horarios_dia_map.get(dia_semana)
        
        eh_dia_trabalho = horario_dia and horario_dia.trabalha and not eh_feriado
        
        if eh_dia_trabalho:
            horas_contratuais_dia = horario_dia.calcular_horas()
            horas_contratuais_mes += horas_contratuais_dia
            dias_uteis_esperados += 1
        else:
            horas_contratuais_dia = Decimal('0')
        
        if dia_semana == 6 or eh_feriado:
            domingos_feriados += 1
        elif dia_semana == 5 and not (horario_dia and horario_dia.trabalha):
            sabados += 1
        
        registro = registros_por_data.get(dia_atual)
        
        if registro and registro.horas_trabalhadas:
            horas_reais = Decimal(str(registro.horas_trabalhadas))
            total_horas += horas_reais
            dias_trabalhados += 1
            
            if registro.total_atraso_minutos:
                total_minutos_atraso += registro.total_atraso_minutos
            
            delta = horas_reais - horas_contratuais_dia
            
            if delta > 0:
                if dia_semana == 6 or eh_feriado:
                    horas_extras_100 += delta
                else:
                    horas_extras_50 += delta
            elif delta < 0:
                horas_falta += abs(delta)
        
        elif eh_dia_trabalho:
            horas_falta += horas_contratuais_dia
        
        dia_atual += timedelta(days=1)
    
    faltas_dias = max(0, dias_uteis_esperados - dias_trabalhados)
    total_extras = horas_extras_50 + horas_extras_100
    
    logger.debug(
        f"[_calcular_horas_mes_novo] Func {funcionario.id} ({funcionario.nome}) - "
        f"Horas contratuais: {horas_contratuais_mes}, Trabalhadas: {total_horas}, "
        f"HE50: {horas_extras_50}, HE100: {horas_extras_100}, Faltas(h): {horas_falta}"
    )
    
    return {
        'total': float(total_horas),
        'extras': float(total_extras),
        'extras_50': float(horas_extras_50),
        'extras_100': float(horas_extras_100),
        'dias_trabalhados': dias_trabalhados,
        'dias_uteis_esperados': dias_uteis_esperados,
        'domingos_feriados': domingos_feriados,
        'sabados': sabados,
        'faltas': faltas_dias,
        'horas_falta': float(horas_falta),
        'horas_contratuais_mes': float(horas_contratuais_mes),
        'total_minutos_atraso': total_minutos_atraso
    }


def _calcular_horas_mes_legado(
    funcionario_id: int,
    registros: list,
    primeiro_dia: date,
    ultimo_dia: date,
    datas_feriados: set
) -> Dict:
    """
    Lógica legada para funcionários sem HorarioTrabalho definido.
    Assume segunda a sexta, 8h/dia.
    """
    from datetime import timedelta
    
    total_horas = Decimal('0')
    horas_extras_50 = Decimal('0')
    horas_extras_100 = Decimal('0')
    dias_trabalhados = 0
    total_minutos_atraso = 0
    
    for registro in registros:
        if registro.horas_trabalhadas:
            total_horas += Decimal(str(registro.horas_trabalhadas))
            dias_trabalhados += 1
        
        if registro.total_atraso_minutos:
            total_minutos_atraso += registro.total_atraso_minutos
        
        if registro.horas_extras:
            dia_semana = registro.data.weekday()
            tipo = registro.tipo_registro or ''
            eh_feriado = registro.data in datas_feriados
            
            if dia_semana == 6 or 'domingo' in tipo.lower() or 'feriado' in tipo.lower() or eh_feriado:
                horas_extras_100 += Decimal(str(registro.horas_extras))
            else:
                horas_extras_50 += Decimal(str(registro.horas_extras))
    
    dias_uteis_esperados = 0
    domingos_feriados = 0
    sabados = 0
    dia_atual = primeiro_dia
    
    while dia_atual <= ultimo_dia:
        eh_feriado = dia_atual in datas_feriados
        
        if dia_atual.weekday() == 6 or eh_feriado:
            domingos_feriados += 1
        elif dia_atual.weekday() == 5:
            sabados += 1
        else:
            dias_uteis_esperados += 1
        dia_atual += timedelta(days=1)
    
    faltas = max(0, dias_uteis_esperados - dias_trabalhados)
    total_extras = horas_extras_50 + horas_extras_100
    
    horas_contratuais_mes = dias_uteis_esperados * 8
    horas_falta = faltas * 8
    
    return {
        'total': float(total_horas),
        'extras': float(total_extras),
        'extras_50': float(horas_extras_50),
        'extras_100': float(horas_extras_100),
        'dias_trabalhados': dias_trabalhados,
        'dias_uteis_esperados': dias_uteis_esperados,
        'domingos_feriados': domingos_feriados,
        'sabados': sabados,
        'faltas': faltas,
        'horas_falta': float(horas_falta),
        'horas_contratuais_mes': float(horas_contratuais_mes),
        'total_minutos_atraso': total_minutos_atraso
    }


def calcular_dsr(horas_info: Dict, valor_hora_normal: Decimal) -> Decimal:
    """
    Calcula DSR (Descanso Semanal Remunerado) sobre horas extras
    Conforme Lei 605/49 - Funcionário PERDE DSR em caso de faltas injustificadas
    CONSIDERA HE 50% E HE 100% SEPARADAMENTE
    
    Args:
        horas_info: Dicionário com informações de horas e dias
        valor_hora_normal: Valor da hora normal
        
    Returns:
        Decimal: Valor do DSR sobre horas extras
    """
    try:
        dias_trabalhados = horas_info.get('dias_trabalhados', 0)
        domingos_feriados = horas_info.get('domingos_feriados', 0)
        horas_extras_50 = horas_info.get('extras_50', 0)
        horas_extras_100 = horas_info.get('extras_100', 0)
        faltas = horas_info.get('faltas', 0)
        
        # Se tiver faltas injustificadas, perde DSR proporcional
        # Lei 605/49: Falta injustificada = perde DSR da semana
        if faltas > 0:
            # Calcular quantos domingos/sábados perder (1 DSR a cada 6 dias úteis)
            domingos_perdidos = int(faltas / 6) + (1 if faltas % 6 > 0 else 0)
            domingos_feriados = max(0, domingos_feriados - domingos_perdidos)
        
        if dias_trabalhados == 0 or domingos_feriados == 0:
            return Decimal('0')
        
        if horas_extras_50 == 0 and horas_extras_100 == 0:
            return Decimal('0')
        
        # Calcular valor das horas extras (HE 50% e HE 100% separados)
        valor_he_50 = valor_hora_normal * Decimal('1.5') * Decimal(str(horas_extras_50))
        valor_he_100 = valor_hora_normal * Decimal('2.0') * Decimal(str(horas_extras_100))
        valor_he_total = valor_he_50 + valor_he_100
        
        # DSR = (Valor HE Total / Dias TRABALHADOS) * Domingos/Feriados
        # CORREÇÃO: Usa dias_trabalhados, não dias_uteis_esperados
        dsr_sobre_he = (valor_he_total / Decimal(str(dias_trabalhados))) * Decimal(str(domingos_feriados))
        
        return dsr_sobre_he.quantize(Decimal('0.01'))
        
    except Exception as e:
        print(f"Erro ao calcular DSR: {e}")
        return Decimal('0')


def calcular_valor_hora_dinamico(funcionario: Funcionario, horas_info: Dict, data_inicio: date, data_fim: date) -> Decimal:
    """
    Calcula o valor da hora baseado nas horas contratuais REAIS do mês.
    
    NOVA LÓGICA: valor_hora = salario_base / horas_contratuais_mes
    Em vez de usar 220 fixo, usa as horas contratuais calculadas pelo HorarioDia.
    
    Args:
        funcionario: Objeto Funcionario
        horas_info: Dicionário com 'horas_contratuais_mes' calculado
        data_inicio: Data de início do período
        data_fim: Data de fim do período
        
    Returns:
        Decimal: Valor da hora normal
    """
    try:
        config = ConfiguracaoSalarial.query.filter_by(
            funcionario_id=funcionario.id,
            ativo=True
        ).filter(
            ConfiguracaoSalarial.data_fim.is_(None) | 
            (ConfiguracaoSalarial.data_fim >= date.today())
        ).first()
        
        if config:
            salario_base = config.salario_base
            if config.tipo_salario == 'HORISTA' and config.valor_hora:
                return config.valor_hora
        else:
            salario_base = Decimal(str(funcionario.salario or 0))
        
        if salario_base <= 0:
            return Decimal('0')
        
        horas_contratuais = Decimal(str(horas_info.get('horas_contratuais_mes', 0)))
        
        if horas_contratuais > 0:
            valor_hora = salario_base / horas_contratuais
            logger.debug(
                f"[calcular_valor_hora_dinamico] Func {funcionario.id}: "
                f"Salário {salario_base} / {horas_contratuais}h = R${valor_hora:.2f}/hora"
            )
            return valor_hora
        else:
            valor_hora_legado = Decimal(str(calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)))
            logger.debug(f"[calcular_valor_hora_dinamico] Func {funcionario.id}: usando valor_hora legado {valor_hora_legado}")
            return valor_hora_legado
            
    except Exception as e:
        logger.error(f"Erro ao calcular valor hora dinâmico: {e}", exc_info=True)
        return Decimal(str(calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)))


def calcular_salario_bruto(funcionario: Funcionario, horas_info: Dict, data_inicio: date, data_fim: date) -> Decimal:
    """
    Calcula salário bruto considerando tipo de salário e horas extras.
    
    ATUALIZADO: Usa horas contratuais reais do mês para calcular valor_hora
    e desconto de faltas baseado em horas_falta quando disponível.
    
    Args:
        funcionario: Objeto Funcionario
        horas_info: Dicionário com informações de horas trabalhadas
        data_inicio: Data de início do período
        data_fim: Data de fim do período
        
    Returns:
        Decimal: Valor do salário bruto
    """
    try:
        config = ConfiguracaoSalarial.query.filter_by(
            funcionario_id=funcionario.id,
            ativo=True
        ).filter(
            ConfiguracaoSalarial.data_fim.is_(None) | 
            (ConfiguracaoSalarial.data_fim >= date.today())
        ).first()
        
        if not config:
            salario_base = Decimal(str(funcionario.salario or 0))
            tipo_salario = 'MENSAL'
        else:
            salario_base = config.salario_base
            tipo_salario = config.tipo_salario
        
        if tipo_salario == 'HORISTA':
            if config and config.valor_hora:
                valor_hora = config.valor_hora
            else:
                valor_hora = calcular_valor_hora_dinamico(funcionario, horas_info, data_inicio, data_fim)
            salario_normal = valor_hora * Decimal(str(horas_info['total']))
        else:
            salario_normal = salario_base
        
        valor_hora_normal = calcular_valor_hora_dinamico(funcionario, horas_info, data_inicio, data_fim)
        
        valor_he_50 = valor_hora_normal * Decimal('1.5') * Decimal(str(horas_info.get('extras_50', 0)))
        valor_he_100 = valor_hora_normal * Decimal('2.0') * Decimal(str(horas_info.get('extras_100', 0)))
        valor_extras = valor_he_50 + valor_he_100
        
        valor_dsr = calcular_dsr(horas_info, valor_hora_normal)
        
        horas_falta = horas_info.get('horas_falta', 0)
        if horas_falta > 0:
            valor_desconto_faltas = valor_hora_normal * Decimal(str(horas_falta))
        else:
            valor_desconto_faltas = valor_hora_normal * 8 * Decimal(str(horas_info.get('faltas', 0)))
        
        if horas_info.get('total_minutos_atraso', 0) > 0:
            horas_atraso = Decimal(str(horas_info['total_minutos_atraso'])) / Decimal('60')
            valor_desconto_atrasos = valor_hora_normal * horas_atraso
        else:
            valor_desconto_atrasos = Decimal('0')
        
        salario_bruto = salario_normal + valor_extras + valor_dsr - valor_desconto_faltas - valor_desconto_atrasos
        
        logger.debug(
            f"[calcular_salario_bruto] Func {funcionario.id}: "
            f"Normal={salario_normal}, HE={valor_extras}, DSR={valor_dsr}, "
            f"DescFaltas={valor_desconto_faltas}, DescAtrasos={valor_desconto_atrasos}, "
            f"Bruto={salario_bruto}"
        )
        
        return salario_bruto
        
    except Exception as e:
        logger.error(f"Erro ao calcular salário bruto: {e}", exc_info=True)
        return Decimal('0')


# ========================================
# CÁLCULOS DE DESCONTOS
# ========================================

def calcular_inss(salario_bruto: Decimal, tabela_inss=None) -> Decimal:
    """
    Calcula INSS progressivo conforme tabela vigente.
    
    Args:
        salario_bruto: Valor do salário bruto
        tabela_inss: Tabela de faixas do INSS (opcional, usa TABELA_INSS_2025 como fallback)
        
    Returns:
        Decimal: Valor do desconto de INSS
    """
    if salario_bruto <= 0:
        return Decimal('0')
    
    if tabela_inss is None:
        tabela_inss = TABELA_INSS_2025
    
    inss_total = Decimal('0')
    salario_restante = salario_bruto
    limite_anterior = Decimal('0')
    
    for faixa in tabela_inss:
        if salario_restante <= 0:
            break
        
        valor_faixa = min(salario_restante, faixa['limite'] - limite_anterior)
        
        inss_faixa = valor_faixa * (faixa['aliquota'] / 100)
        inss_total += inss_faixa
        
        salario_restante -= valor_faixa
        limite_anterior = faixa['limite']
    
    return inss_total.quantize(Decimal('0.01'))


def calcular_irrf(salario_bruto: Decimal, inss: Decimal, dependentes: int = 0, tabela_irrf=None, deducao_dependente=None) -> Decimal:
    """
    Calcula Imposto de Renda Retido na Fonte.
    
    Args:
        salario_bruto: Valor do salário bruto
        inss: Valor do INSS calculado
        dependentes: Número de dependentes
        tabela_irrf: Tabela de faixas do IRRF (opcional, usa TABELA_IR_2025 como fallback)
        deducao_dependente: Valor de dedução por dependente (opcional, usa DEDUCAO_DEPENDENTE_IR como fallback)
        
    Returns:
        Decimal: Valor do IR a ser retido
    """
    if tabela_irrf is None:
        tabela_irrf = TABELA_IR_2025
    
    if deducao_dependente is None:
        deducao_dependente = DEDUCAO_DEPENDENTE_IR
    
    base_calculo = salario_bruto - inss - (Decimal(str(dependentes)) * deducao_dependente)
    
    if base_calculo <= tabela_irrf[0]['limite']:
        return Decimal('0')
    
    for faixa in tabela_irrf:
        if base_calculo <= faixa['limite']:
            ir = (base_calculo * (faixa['aliquota'] / 100)) - faixa['parcela_deduzir']
            return max(Decimal('0'), ir).quantize(Decimal('0.01'))
    
    return Decimal('0')


def calcular_descontos(salario_bruto: Decimal, funcionario: Funcionario, params=None) -> Dict:
    """
    Calcula todos os descontos (INSS, IR, benefícios, etc).
    
    Args:
        salario_bruto: Valor do salário bruto
        funcionario: Objeto Funcionario
        params: Objeto ParametrosLegais (opcional, usa fallback se não informado)
        
    Returns:
        dict: Dicionário com todos os descontos
    """
    if params:
        tabela_inss = _gerar_tabela_inss(params)
        tabela_irrf = _gerar_tabela_irrf(params)
        deducao_dep = _obter_deducao_dependente(params)
    else:
        tabela_inss = None
        tabela_irrf = None
        deducao_dep = None
    
    inss = calcular_inss(salario_bruto, tabela_inss)
    
    config = ConfiguracaoSalarial.query.filter_by(
        funcionario_id=funcionario.id,
        ativo=True
    ).first()
    dependentes = config.dependentes if config else 0
    
    irrf = calcular_irrf(salario_bruto, inss, dependentes, tabela_irrf, deducao_dep)
    
    beneficios = BeneficioFuncionario.query.filter_by(
        funcionario_id=funcionario.id,
        ativo=True
    ).filter(
        BeneficioFuncionario.data_fim.is_(None) |
        (BeneficioFuncionario.data_fim >= date.today())
    ).all()
    
    total_beneficios = Decimal('0')
    desconto_beneficios = Decimal('0')
    
    for beneficio in beneficios:
        valor_beneficio = beneficio.valor
        total_beneficios += valor_beneficio
        
        if beneficio.percentual_desconto:
            desconto = valor_beneficio * (beneficio.percentual_desconto / 100)
            desconto_beneficios += desconto
    
    total_descontos = inss + irrf + desconto_beneficios
    
    return {
        'inss': float(inss),
        'ir': float(irrf),
        'beneficios': float(desconto_beneficios),
        'total': float(total_descontos),
        'inss_decimal': inss,
        'ir_decimal': irrf
    }


# ========================================
# ENCARGOS PATRONAIS
# ========================================

def calcular_encargos_patronais(salario_bruto: Decimal, params=None) -> Dict:
    """
    Calcula encargos patronais (FGTS, INSS Patronal, etc).
    
    Args:
        salario_bruto: Valor do salário bruto
        params: Objeto ParametrosLegais (opcional, usa fallback se não informado)
        
    Returns:
        dict: Dicionário com todos os encargos
    """
    aliquota_fgts = _obter_aliquota_fgts(params)
    
    fgts = salario_bruto * (aliquota_fgts / 100)
    
    inss_patronal = salario_bruto * Decimal('0.20')
    
    total_encargos = fgts + inss_patronal
    
    return {
        'fgts': float(fgts),
        'inss_patronal': float(inss_patronal),
        'total': float(total_encargos),
        'fgts_decimal': fgts,
        'inss_patronal_decimal': inss_patronal
    }


# ========================================
# PROCESSAMENTO COMPLETO
# ========================================

def processar_folha_funcionario(funcionario: Funcionario, ano: int, mes: int, params=None) -> Dict:
    """
    Processa a folha completa de um funcionário.
    
    Args:
        funcionario: Objeto Funcionario
        ano: Ano de referência
        mes: Mês de referência
        params: Objeto ParametrosLegais (opcional, busca automaticamente se não informado)
        
    Returns:
        dict: Dados completos da folha processada
    """
    try:
        import calendar
        data_inicio = date(ano, mes, 1)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_fim = date(ano, mes, ultimo_dia)
        
        if params is None and funcionario.admin_id:
            params = _obter_parametros_legais(funcionario.admin_id, ano)
        
        horas_info = calcular_horas_mes(funcionario.id, ano, mes)
        
        salario_bruto = calcular_salario_bruto(funcionario, horas_info, data_inicio, data_fim)
        
        descontos = calcular_descontos(salario_bruto, funcionario, params)
        
        encargos = calcular_encargos_patronais(salario_bruto, params)
        
        salario_liquido = salario_bruto - Decimal(str(descontos['total']))
        
        return {
            'funcionario_id': funcionario.id,
            'funcionario_nome': funcionario.nome,
            'salario_base': float(funcionario.salario or 0),
            'horas_trabalhadas': horas_info['total'],
            'horas_extras': horas_info['extras'],
            'dias_trabalhados': horas_info['dias_trabalhados'],
            'faltas': horas_info['faltas'],
            'total_proventos': float(salario_bruto),
            'inss': descontos['inss'],
            'irrf': descontos['ir'],
            'outros_descontos': descontos['beneficios'],
            'total_descontos': descontos['total'],
            'salario_liquido': float(salario_liquido),
            'fgts': encargos['fgts'],
            'encargos_patronais': encargos['total'],
            'custo_total_empresa': float(salario_bruto) + encargos['total']
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar folha do funcionário {funcionario.id}: {e}", exc_info=True)
        return None
