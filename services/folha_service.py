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

# ========================================
# CONSTANTES DE FALLBACK (APENAS EMERGÊNCIA)
# ========================================
# IMPORTANTE: Estas tabelas só são usadas se ParametrosLegais não estiver
# configurado no banco. O sistema emitirá um WARNING quando isso acontecer.
# A fonte de verdade deve ser SEMPRE o banco de dados (tabela parametros_legais).
# ========================================

_FALLBACK_TABELA_INSS_2025 = [
    {'limite': Decimal('1412.00'), 'aliquota': Decimal('7.5')},
    {'limite': Decimal('2666.68'), 'aliquota': Decimal('9.0')},
    {'limite': Decimal('4000.03'), 'aliquota': Decimal('12.0')},
    {'limite': Decimal('7786.02'), 'aliquota': Decimal('14.0')},
]

_FALLBACK_TABELA_IR_2025 = [
    {'limite': Decimal('2259.20'), 'aliquota': Decimal('0'), 'parcela_deduzir': Decimal('0')},
    {'limite': Decimal('2826.65'), 'aliquota': Decimal('7.5'), 'parcela_deduzir': Decimal('169.44')},
    {'limite': Decimal('3751.05'), 'aliquota': Decimal('15.0'), 'parcela_deduzir': Decimal('381.44')},
    {'limite': Decimal('4664.68'), 'aliquota': Decimal('22.5'), 'parcela_deduzir': Decimal('662.77')},
    {'limite': Decimal('999999.99'), 'aliquota': Decimal('27.5'), 'parcela_deduzir': Decimal('896.00')},
]

_FALLBACK_DEDUCAO_DEPENDENTE_IR = Decimal('189.59')
_FALLBACK_SALARIO_MINIMO = Decimal('1412.00')
ALIQUOTA_FGTS = Decimal('8.0')

# Flag para controlar alertas de fallback (evita spam de logs)
_fallback_warning_emitted = set()


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
    global _fallback_warning_emitted
    
    if not params:
        warning_key = 'inss_fallback'
        if warning_key not in _fallback_warning_emitted:
            logger.warning(
                "⚠️ ATENÇÃO: Usando tabela INSS de FALLBACK (hardcoded). "
                "Configure ParametrosLegais no banco de dados para o ano vigente!"
            )
            _fallback_warning_emitted.add(warning_key)
        return _FALLBACK_TABELA_INSS_2025
    
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
    global _fallback_warning_emitted
    
    if not params:
        warning_key = 'irrf_fallback'
        if warning_key not in _fallback_warning_emitted:
            logger.warning(
                "⚠️ ATENÇÃO: Usando tabela IRRF de FALLBACK (hardcoded). "
                "Configure ParametrosLegais no banco de dados para o ano vigente!"
            )
            _fallback_warning_emitted.add(warning_key)
        return _FALLBACK_TABELA_IR_2025
    
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
    return _FALLBACK_SALARIO_MINIMO


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
    return _FALLBACK_DEDUCAO_DEPENDENTE_IR


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
    # Usar .all() para evitar erro com lazy='dynamic'
    try:
        if hasattr(horario_padrao.dias, 'all'):
            dias_list = horario_padrao.dias.all()
        else:
            dias_list = list(horario_padrao.dias)
        for hd in dias_list:
            horarios_dia_map[hd.dia_semana] = hd
    except Exception as e:
        logger.warning(f"Erro ao carregar HorarioDia: {e}")
    
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
        
        tolerancia_minutos = 10
        if funcionario.admin_id:
            params = _obter_parametros_legais(funcionario.admin_id, ano)
            if params and hasattr(params, 'tolerancia_minutos') and params.tolerancia_minutos is not None:
                tolerancia_minutos = params.tolerancia_minutos
        
        if horario_trabalho and horario_trabalho.dias.count() > 0:
            return _calcular_horas_mes_novo(
                funcionario, horario_trabalho, registros, 
                primeiro_dia, ultimo_dia, datas_feriados, ano, mes,
                tolerancia_minutos=tolerancia_minutos
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
    mes: int,
    tolerancia_minutos: int = 10
) -> Dict:
    """
    Nova lógica de cálculo baseada em HorarioDia.
    Compara horas trabalhadas com horas contratuais para cada dia.
    
    ATUALIZADO (Dez/2025): Aplica tolerância configurável para evitar
    que pequenas variações de minutos sejam computadas como extras ou atrasos.
    
    Args:
        funcionario: Objeto Funcionario
        horario_trabalho: Objeto HorarioTrabalho com dias associados
        registros: Lista de RegistroPonto do período
        primeiro_dia: Data de início do período
        ultimo_dia: Data de fim do período
        datas_feriados: Set de datas que são feriados
        ano: Ano de referência
        mes: Mês de referência
        tolerancia_minutos: Minutos de tolerância para extras/atrasos (default: 10)
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
    
    tolerancia_horas = Decimal(str(tolerancia_minutos)) / Decimal('60')
    
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
            
            # REGRA DE TOLERÂNCIA ATUALIZADA (Jan/2026):
            # Se a diferença estiver DENTRO da tolerância → NÃO desconta/credita nada
            # Se a diferença ULTRAPASSAR a tolerância → desconta/credita TODO o valor
            # Exemplo: tolerância 10min, atraso 11min → desconta 11min (não apenas 1min)
            
            if abs(delta) <= tolerancia_horas:
                # Dentro da tolerância - não aplica desconto nem hora extra
                pass
            elif delta > 0:
                # Horas a mais - TODAS contam como extra se ultrapassou tolerância
                delta_efetivo = delta  # Desconta/credita TUDO, não subtrai tolerância
                if dia_semana == 6 or eh_feriado:
                    horas_extras_100 += delta_efetivo
                else:
                    horas_extras_50 += delta_efetivo
            elif delta < 0:
                # Horas a menos - TODAS contam como falta se ultrapassou tolerância
                delta_efetivo = abs(delta)  # Desconta TUDO, não subtrai tolerância
                horas_falta += delta_efetivo
        
        elif eh_dia_trabalho:
            horas_falta += horas_contratuais_dia
        
        dia_atual += timedelta(days=1)
    
    faltas_dias = max(0, dias_uteis_esperados - dias_trabalhados)
    total_extras = horas_extras_50 + horas_extras_100
    
    logger.debug(
        f"[_calcular_horas_mes_novo] Func {funcionario.id} ({funcionario.nome}) - "
        f"Tolerância: {tolerancia_minutos}min, Horas contratuais: {horas_contratuais_mes}, "
        f"Trabalhadas: {total_horas}, HE50: {horas_extras_50}, HE100: {horas_extras_100}, Faltas(h): {horas_falta}"
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
        'total_minutos_atraso': total_minutos_atraso,
        'tolerancia_minutos': tolerancia_minutos
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
        dias_uteis_esperados = horas_info.get('dias_uteis_esperados', dias_trabalhados)
        domingos_feriados = horas_info.get('domingos_feriados', 0)
        horas_extras_50 = horas_info.get('extras_50', 0)
        horas_extras_100 = horas_info.get('extras_100', 0)
        
        # ATUALIZADO Jan/2026: NÃO reduzir DSR aqui por faltas
        # A perda de DSR por faltas é tratada separadamente como desconto_dsr_faltas
        # (salário/30 por dia de falta) conforme simulação do usuário
        
        if dias_uteis_esperados == 0 or domingos_feriados == 0:
            return Decimal('0')
        
        if horas_extras_50 == 0 and horas_extras_100 == 0:
            return Decimal('0')
        
        # Calcular valor das horas extras (HE 50% e HE 100% separados)
        valor_he_50 = valor_hora_normal * Decimal('1.5') * Decimal(str(horas_extras_50))
        valor_he_100 = valor_hora_normal * Decimal('2.0') * Decimal(str(horas_extras_100))
        valor_he_total = valor_he_50 + valor_he_100
        
        # DSR = (Valor HE Total / Dias Úteis Esperados) * Domingos/Feriados
        # ATUALIZADO: Usa dias_uteis_esperados para cálculo consistente com simulação
        dsr_sobre_he = (valor_he_total / Decimal(str(dias_uteis_esperados))) * Decimal(str(domingos_feriados))
        
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


def calcular_salario_bruto(funcionario: Funcionario, horas_info: Dict, data_inicio: date, data_fim: date) -> Dict:
    """
    Calcula salário bruto considerando tipo de salário e horas extras.
    
    ATUALIZADO (Dez/2025): Retorna dicionário com salário bruto (base para impostos)
    e descontos de faltas/atrasos separados (aplicados apenas no líquido).
    
    CORREÇÃO IMPORTANTE: O desconto de faltas NÃO deve reduzir a base de cálculo
    do INSS/IRRF. O salário bruto (base para impostos) é calculado sobre o que
    o funcionário teria direito se não tivesse faltado. O desconto de faltas
    é aplicado apenas no cálculo do salário líquido final.
    
    Args:
        funcionario: Objeto Funcionario
        horas_info: Dicionário com informações de horas trabalhadas
        data_inicio: Data de início do período
        data_fim: Data de fim do período
        
    Returns:
        Dict: {
            'salario_bruto': Decimal - base para INSS/IRRF (sem faltas),
            'total_proventos': Decimal - soma de todos os proventos,
            'desconto_faltas': Decimal - valor a descontar do líquido,
            'desconto_atrasos': Decimal - valor a descontar do líquido,
            'salario_normal': Decimal - salário base,
            'valor_extras': Decimal - valor das horas extras,
            'valor_dsr': Decimal - DSR sobre extras,
            'valor_hora': Decimal - valor da hora calculado
        }
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
        
        # Desconto de horas (faltas parciais, atrasos, saídas antecipadas)
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
        
        # NOVO (Jan/2026): Desconto de DSR por falta injustificada
        # Regra: Cada dia de falta injustificada = perde 1 DSR (salário/30)
        # Conforme Lei 605/49 - perda do repouso semanal remunerado
        faltas_dias = horas_info.get('faltas', 0)
        if faltas_dias > 0:
            valor_desconto_dsr_faltas = (salario_base / Decimal('30')) * Decimal(str(faltas_dias))
        else:
            valor_desconto_dsr_faltas = Decimal('0')
        
        salario_bruto = salario_normal + valor_extras + valor_dsr
        
        total_proventos = salario_bruto - valor_desconto_faltas - valor_desconto_atrasos - valor_desconto_dsr_faltas
        
        logger.debug(
            f"[calcular_salario_bruto] Func {funcionario.id}: "
            f"Normal={salario_normal}, HE={valor_extras}, DSR={valor_dsr}, "
            f"Bruto(base impostos)={salario_bruto}, "
            f"DescFaltas={valor_desconto_faltas}, DescAtrasos={valor_desconto_atrasos}, "
            f"DescDSRFaltas={valor_desconto_dsr_faltas}, "
            f"TotalProventos(líquido)={total_proventos}"
        )
        
        return {
            'salario_bruto': salario_bruto,
            'total_proventos': total_proventos,
            'desconto_faltas': valor_desconto_faltas,
            'desconto_atrasos': valor_desconto_atrasos,
            'desconto_dsr_faltas': valor_desconto_dsr_faltas,
            'salario_normal': salario_normal,
            'valor_extras': valor_extras,
            'valor_he_50': valor_he_50,
            'valor_he_100': valor_he_100,
            'valor_dsr': valor_dsr,
            'valor_hora': valor_hora_normal
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular salário bruto: {e}", exc_info=True)
        return {
            'salario_bruto': Decimal('0'),
            'total_proventos': Decimal('0'),
            'desconto_faltas': Decimal('0'),
            'desconto_atrasos': Decimal('0'),
            'desconto_dsr_faltas': Decimal('0'),
            'salario_normal': Decimal('0'),
            'valor_extras': Decimal('0'),
            'valor_he_50': Decimal('0'),
            'valor_he_100': Decimal('0'),
            'valor_dsr': Decimal('0'),
            'valor_hora': Decimal('0')
        }


# ========================================
# CÁLCULOS DE DESCONTOS
# ========================================

def calcular_inss(salario_bruto: Decimal, tabela_inss=None) -> Decimal:
    """
    Calcula INSS progressivo conforme tabela vigente.
    
    Args:
        salario_bruto: Valor do salário bruto
        tabela_inss: Tabela de faixas do INSS (gerada via _gerar_tabela_inss)
        
    Returns:
        Decimal: Valor do desconto de INSS
    """
    if salario_bruto <= 0:
        return Decimal('0')
    
    if tabela_inss is None:
        tabela_inss = _gerar_tabela_inss(None)
    
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
        tabela_irrf: Tabela de faixas do IRRF (gerada via _gerar_tabela_irrf)
        deducao_dependente: Valor de dedução por dependente (obtido via _obter_deducao_dependente)
        
    Returns:
        Decimal: Valor do IR a ser retido
    """
    if tabela_irrf is None:
        tabela_irrf = _gerar_tabela_irrf(None)
    
    if deducao_dependente is None:
        deducao_dependente = _obter_deducao_dependente(None)
    
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
        params: Objeto ParametrosLegais (OBRIGATÓRIO para cálculos precisos)
        
    Returns:
        dict: Dicionário com todos os descontos
        
    Raises:
        ValueError: Se params não for fornecido (modo estrito)
    """
    if not params:
        logger.error(
            "⛔ ERRO: ParametrosLegais não fornecido para calcular_descontos(). "
            "O sistema requer parâmetros legais do banco de dados para cálculos precisos. "
            "Configure ParametrosLegais para o ano vigente antes de processar folhas."
        )
        raise ValueError(
            "ParametrosLegais não configurado. "
            "Configure os parâmetros legais (INSS/IRRF) para o ano antes de processar folhas."
        )
    
    tabela_inss = _gerar_tabela_inss(params)
    tabela_irrf = _gerar_tabela_irrf(params)
    deducao_dep = _obter_deducao_dependente(params)
    
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
    
    ATUALIZADO (Dez/2025): Corrigido cálculo para que o desconto de faltas
    seja aplicado apenas no líquido, não na base de INSS/IRRF.
    
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
        
        if params is None:
            logger.error(
                f"⛔ ERRO: ParametrosLegais não encontrado para admin_id={funcionario.admin_id}, ano={ano}. "
                "Configure os parâmetros legais antes de processar folhas."
            )
            raise ValueError(
                f"ParametrosLegais não configurado para o ano {ano}. "
                "Configure os parâmetros legais (INSS/IRRF) em Configurações > Parâmetros Legais."
            )
        
        horas_info = calcular_horas_mes(funcionario.id, ano, mes)
        
        resultado_bruto = calcular_salario_bruto(funcionario, horas_info, data_inicio, data_fim)
        
        salario_bruto = resultado_bruto['salario_bruto']
        desconto_faltas = resultado_bruto['desconto_faltas']
        desconto_atrasos = resultado_bruto['desconto_atrasos']
        total_proventos = resultado_bruto['total_proventos']
        
        descontos = calcular_descontos(salario_bruto, funcionario, params)
        
        encargos = calcular_encargos_patronais(salario_bruto, params)
        
        salario_liquido = total_proventos - Decimal(str(descontos['total']))
        
        logger.debug(
            f"[processar_folha_funcionario] Func {funcionario.id}: "
            f"Bruto(base impostos)={salario_bruto}, TotalProventos={total_proventos}, "
            f"DescFaltas={desconto_faltas}, Descontos(INSS+IRRF)={descontos['total']}, "
            f"Líquido={salario_liquido}"
        )
        
        return {
            'funcionario_id': funcionario.id,
            'funcionario_nome': funcionario.nome,
            'salario_base': float(funcionario.salario or 0),
            'horas_trabalhadas': horas_info['total'],
            'horas_extras': horas_info['extras'],
            'horas_extras_50': horas_info.get('extras_50', 0),
            'horas_extras_100': horas_info.get('extras_100', 0),
            'dias_trabalhados': horas_info['dias_trabalhados'],
            'faltas': horas_info['faltas'],
            'horas_falta': horas_info.get('horas_falta', 0),
            'salario_bruto': float(salario_bruto),
            'total_proventos': float(total_proventos),
            'desconto_faltas': float(desconto_faltas),
            'desconto_atrasos': float(desconto_atrasos),
            'valor_he_50': float(resultado_bruto.get('valor_he_50', 0)),
            'valor_he_100': float(resultado_bruto.get('valor_he_100', 0)),
            'valor_dsr': float(resultado_bruto.get('valor_dsr', 0)),
            'inss': descontos['inss'],
            'irrf': descontos['ir'],
            'outros_descontos': descontos['beneficios'],
            'total_descontos': descontos['total'] + float(desconto_faltas) + float(desconto_atrasos),
            'salario_liquido': float(salario_liquido),
            'fgts': encargos['fgts'],
            'encargos_patronais': encargos['total'],
            'custo_total_empresa': float(salario_bruto) + encargos['total']
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar folha do funcionário {funcionario.id}: {e}", exc_info=True)
        return None


# ========================================
# FUNÇÕES PARA DASHBOARD DE CUSTOS POR OBRA
# ========================================

def salvar_folha_processada(funcionario_id: int, obra_id: Optional[int], ano: int, mes: int, 
                            dados_folha: Dict, admin_id: int) -> bool:
    """
    Salva os resultados do processamento de folha na tabela FolhaProcessada.
    Permite consultas eficientes para dashboards de custos por obra.
    
    Args:
        funcionario_id: ID do funcionário
        obra_id: ID da obra (pode ser None se funcionário não alocado)
        ano: Ano de referência
        mes: Mês de referência
        dados_folha: Dicionário retornado por processar_folha_funcionario()
        admin_id: ID do administrador (multi-tenant)
    
    Returns:
        bool: True se salvou com sucesso, False caso contrário
    """
    try:
        from models import FolhaProcessada
        
        folha_existente = FolhaProcessada.query.filter_by(
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            ano=ano,
            mes=mes
        ).first()
        
        if folha_existente:
            folha_existente.salario_base = Decimal(str(dados_folha.get('salario_base', 0)))
            folha_existente.salario_bruto = Decimal(str(dados_folha.get('salario_bruto', 0)))
            folha_existente.total_proventos = Decimal(str(dados_folha.get('total_proventos', 0)))
            folha_existente.total_descontos = Decimal(str(dados_folha.get('total_descontos', 0)))
            folha_existente.salario_liquido = Decimal(str(dados_folha.get('salario_liquido', 0)))
            folha_existente.valor_he_50 = Decimal(str(dados_folha.get('valor_he_50', 0)))
            folha_existente.valor_he_100 = Decimal(str(dados_folha.get('valor_he_100', 0)))
            folha_existente.valor_dsr = Decimal(str(dados_folha.get('valor_dsr', 0)))
            folha_existente.encargos_fgts = Decimal(str(dados_folha.get('fgts', 0)))
            folha_existente.encargos_inss_patronal = Decimal(str(dados_folha.get('encargos_patronais', 0))) * Decimal('0.7')
            folha_existente.custo_total_empresa = Decimal(str(dados_folha.get('custo_total_empresa', 0)))
            folha_existente.inss_funcionario = Decimal(str(dados_folha.get('inss', 0)))
            folha_existente.irrf = Decimal(str(dados_folha.get('irrf', 0)))
            folha_existente.desconto_faltas = Decimal(str(dados_folha.get('desconto_faltas', 0)))
            folha_existente.desconto_atrasos = Decimal(str(dados_folha.get('desconto_atrasos', 0)))
            folha_existente.horas_trabalhadas = Decimal(str(dados_folha.get('horas_trabalhadas', 0)))
            folha_existente.horas_extras_50 = Decimal(str(dados_folha.get('horas_extras_50', 0)))
            folha_existente.horas_extras_100 = Decimal(str(dados_folha.get('horas_extras_100', 0)))
            folha_existente.horas_falta = Decimal(str(dados_folha.get('horas_falta', 0)))
            folha_existente.processado_em = datetime.utcnow()
            
            logger.debug(f"[salvar_folha_processada] Atualizado: func={funcionario_id}, obra={obra_id}, {mes:02d}/{ano}")
        else:
            nova_folha = FolhaProcessada(
                funcionario_id=funcionario_id,
                obra_id=obra_id,
                admin_id=admin_id,
                ano=ano,
                mes=mes,
                salario_base=Decimal(str(dados_folha.get('salario_base', 0))),
                salario_bruto=Decimal(str(dados_folha.get('salario_bruto', 0))),
                total_proventos=Decimal(str(dados_folha.get('total_proventos', 0))),
                total_descontos=Decimal(str(dados_folha.get('total_descontos', 0))),
                salario_liquido=Decimal(str(dados_folha.get('salario_liquido', 0))),
                valor_he_50=Decimal(str(dados_folha.get('valor_he_50', 0))),
                valor_he_100=Decimal(str(dados_folha.get('valor_he_100', 0))),
                valor_dsr=Decimal(str(dados_folha.get('valor_dsr', 0))),
                encargos_fgts=Decimal(str(dados_folha.get('fgts', 0))),
                encargos_inss_patronal=Decimal(str(dados_folha.get('encargos_patronais', 0))) * Decimal('0.7'),
                custo_total_empresa=Decimal(str(dados_folha.get('custo_total_empresa', 0))),
                inss_funcionario=Decimal(str(dados_folha.get('inss', 0))),
                irrf=Decimal(str(dados_folha.get('irrf', 0))),
                desconto_faltas=Decimal(str(dados_folha.get('desconto_faltas', 0))),
                desconto_atrasos=Decimal(str(dados_folha.get('desconto_atrasos', 0))),
                horas_trabalhadas=Decimal(str(dados_folha.get('horas_trabalhadas', 0))),
                horas_extras_50=Decimal(str(dados_folha.get('horas_extras_50', 0))),
                horas_extras_100=Decimal(str(dados_folha.get('horas_extras_100', 0))),
                horas_falta=Decimal(str(dados_folha.get('horas_falta', 0))),
                processado_em=datetime.utcnow()
            )
            db.session.add(nova_folha)
            logger.debug(f"[salvar_folha_processada] Criado: func={funcionario_id}, obra={obra_id}, {mes:02d}/{ano}")
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"[salvar_folha_processada] Erro ao salvar: {e}", exc_info=True)
        db.session.rollback()
        return False


def obter_dados_folha_obra(obra_id: int, data_inicio: date, data_fim: date, admin_id: Optional[int] = None) -> Dict:
    """
    Retorna dados consolidados de folha de pagamento para uma obra em um período.
    Usa dados da tabela FolhaProcessada para consultas eficientes.
    
    Args:
        obra_id: ID da obra
        data_inicio: Data inicial do período
        data_fim: Data final do período
        admin_id: ID do admin (opcional, para multi-tenancy)
    
    Returns:
        dict com:
            - funcionarios: lista de funcionários com dados individuais
            - totais: dicionário com totais consolidados
            - composicao: breakdown dos componentes do custo
            - evolucao_mensal: dados para gráfico de evolução
    """
    try:
        from models import FolhaProcessada, Funcionario, RegistroPonto
        
        ano_inicio = data_inicio.year
        mes_inicio = data_inicio.month
        ano_fim = data_fim.year
        mes_fim = data_fim.month
        
        query = FolhaProcessada.query.filter(
            FolhaProcessada.obra_id == obra_id
        )
        
        if ano_inicio == ano_fim:
            query = query.filter(
                FolhaProcessada.ano == ano_inicio,
                FolhaProcessada.mes >= mes_inicio,
                FolhaProcessada.mes <= mes_fim
            )
        else:
            query = query.filter(
                db.or_(
                    db.and_(FolhaProcessada.ano == ano_inicio, FolhaProcessada.mes >= mes_inicio),
                    db.and_(FolhaProcessada.ano > ano_inicio, FolhaProcessada.ano < ano_fim),
                    db.and_(FolhaProcessada.ano == ano_fim, FolhaProcessada.mes <= mes_fim)
                )
            )
        
        if admin_id:
            query = query.filter(FolhaProcessada.admin_id == admin_id)
        
        folhas = query.all()
        
        dados_por_funcionario = {}
        dados_por_mes = {}
        
        for folha in folhas:
            func_id = folha.funcionario_id
            mes_ref = f"{folha.ano}-{folha.mes:02d}"
            
            if func_id not in dados_por_funcionario:
                funcionario = Funcionario.query.get(func_id)
                dados_por_funcionario[func_id] = {
                    'funcionario': funcionario,
                    'total_salario_bruto': Decimal('0'),
                    'total_encargos': Decimal('0'),
                    'total_custo': Decimal('0'),
                    'total_horas_normais': Decimal('0'),
                    'total_he_50': Decimal('0'),
                    'total_he_100': Decimal('0'),
                    'total_faltas': Decimal('0')
                }
            
            dados_por_funcionario[func_id]['total_salario_bruto'] += folha.salario_bruto or Decimal('0')
            encargos = (folha.encargos_fgts or Decimal('0')) + (folha.encargos_inss_patronal or Decimal('0'))
            dados_por_funcionario[func_id]['total_encargos'] += encargos
            dados_por_funcionario[func_id]['total_custo'] += folha.custo_total_empresa or Decimal('0')
            
            horas_normais = (folha.horas_trabalhadas or Decimal('0')) - \
                           (folha.horas_extras_50 or Decimal('0')) - \
                           (folha.horas_extras_100 or Decimal('0'))
            dados_por_funcionario[func_id]['total_horas_normais'] += max(horas_normais, Decimal('0'))
            dados_por_funcionario[func_id]['total_he_50'] += folha.horas_extras_50 or Decimal('0')
            dados_por_funcionario[func_id]['total_he_100'] += folha.horas_extras_100 or Decimal('0')
            dados_por_funcionario[func_id]['total_faltas'] += folha.horas_falta or Decimal('0')
            
            if mes_ref not in dados_por_mes:
                dados_por_mes[mes_ref] = {
                    'salario_base': Decimal('0'),
                    'he_50': Decimal('0'),
                    'he_100': Decimal('0'),
                    'dsr': Decimal('0'),
                    'encargos': Decimal('0'),
                    'total': Decimal('0')
                }
            
            dados_por_mes[mes_ref]['salario_base'] += folha.salario_base or Decimal('0')
            dados_por_mes[mes_ref]['he_50'] += folha.valor_he_50 or Decimal('0')
            dados_por_mes[mes_ref]['he_100'] += folha.valor_he_100 or Decimal('0')
            dados_por_mes[mes_ref]['dsr'] += folha.valor_dsr or Decimal('0')
            dados_por_mes[mes_ref]['encargos'] += encargos
            dados_por_mes[mes_ref]['total'] += folha.custo_total_empresa or Decimal('0')
        
        total_custo = sum(d['total_custo'] for d in dados_por_funcionario.values())
        total_horas = sum(
            d['total_horas_normais'] + d['total_he_50'] + d['total_he_100'] 
            for d in dados_por_funcionario.values()
        )
        total_he = sum(d['total_he_50'] + d['total_he_100'] for d in dados_por_funcionario.values())
        custo_por_hora = total_custo / total_horas if total_horas > 0 else Decimal('0')
        percentual_he = (total_he / total_horas * 100) if total_horas > 0 else Decimal('0')
        
        total_salario_base = sum(d['total_salario_bruto'] for d in dados_por_funcionario.values())
        total_encargos = sum(d['total_encargos'] for d in dados_por_funcionario.values())
        total_he_50_valor = sum(dados_por_mes[m]['he_50'] for m in dados_por_mes)
        total_he_100_valor = sum(dados_por_mes[m]['he_100'] for m in dados_por_mes)
        total_dsr_valor = sum(dados_por_mes[m]['dsr'] for m in dados_por_mes)
        
        composicao = [
            {'categoria': 'Salário Base', 'valor': float(total_salario_base), 'cor': '#4CAF50'},
            {'categoria': 'HE 50%', 'valor': float(total_he_50_valor), 'cor': '#FF9800'},
            {'categoria': 'HE 100%', 'valor': float(total_he_100_valor), 'cor': '#F44336'},
            {'categoria': 'DSR s/ Extras', 'valor': float(total_dsr_valor), 'cor': '#9C27B0'},
            {'categoria': 'Encargos Patronais', 'valor': float(total_encargos), 'cor': '#2196F3'}
        ]
        
        evolucao = [
            {
                'mes': mes_ref,
                'mes_label': f"{mes_ref.split('-')[1]}/{mes_ref.split('-')[0][-2:]}",
                'custo': float(dados['total']),
                'salario': float(dados['salario_base']),
                'encargos': float(dados['encargos'])
            }
            for mes_ref, dados in sorted(dados_por_mes.items())
        ]
        
        funcionarios_lista = [
            {
                'id': func_id,
                'nome': dados['funcionario'].nome if dados['funcionario'] else f"ID {func_id}",
                'cargo': dados['funcionario'].funcao_ref.nome if dados['funcionario'] and dados['funcionario'].funcao_ref else '-',
                'salarioBruto': float(dados['total_salario_bruto']),
                'encargos': float(dados['total_encargos']),
                'custoTotal': float(dados['total_custo']),
                'horasNormais': float(dados['total_horas_normais']),
                'he50': float(dados['total_he_50']),
                'he100': float(dados['total_he_100']),
                'horasFalta': float(dados['total_faltas'])
            }
            for func_id, dados in dados_por_funcionario.items()
        ]
        
        funcionarios_lista.sort(key=lambda x: x['custoTotal'], reverse=True)
        
        return {
            'funcionarios': funcionarios_lista,
            'totais': {
                'custo_total': float(total_custo),
                'total_horas': float(total_horas),
                'custo_por_hora': float(custo_por_hora),
                'percentual_he': float(percentual_he),
                'total_he': float(total_he),
                'total_funcionarios': len(funcionarios_lista)
            },
            'composicao': composicao,
            'evolucao_mensal': evolucao
        }
        
    except Exception as e:
        logger.error(f"[obter_dados_folha_obra] Erro: {e}", exc_info=True)
        return {
            'funcionarios': [],
            'totais': {
                'custo_total': 0,
                'total_horas': 0,
                'custo_por_hora': 0,
                'percentual_he': 0,
                'total_he': 0,
                'total_funcionarios': 0
            },
            'composicao': [],
            'evolucao_mensal': []
        }


def processar_e_salvar_folha_obra(obra_id: int, ano: int, mes: int, admin_id: int) -> Dict:
    """
    Processa e salva folhas de todos os funcionários que trabalharam em uma obra no período.
    Útil para recalcular dados de custo de uma obra.
    
    Args:
        obra_id: ID da obra
        ano: Ano de referência
        mes: Mês de referência
        admin_id: ID do administrador
    
    Returns:
        dict com estatísticas do processamento
    """
    try:
        from models import RegistroPonto
        
        funcionarios_ids = db.session.query(RegistroPonto.funcionario_id).filter(
            RegistroPonto.obra_id == obra_id,
            extract('year', RegistroPonto.data) == ano,
            extract('month', RegistroPonto.data) == mes
        ).distinct().all()
        
        funcionarios_ids = [f[0] for f in funcionarios_ids]
        
        processados = 0
        erros = 0
        
        for func_id in funcionarios_ids:
            try:
                funcionario = Funcionario.query.get(func_id)
                if not funcionario:
                    continue
                
                dados_folha = processar_folha_funcionario(funcionario, ano, mes)
                
                if dados_folha:
                    if salvar_folha_processada(func_id, obra_id, ano, mes, dados_folha, admin_id):
                        processados += 1
                    else:
                        erros += 1
                else:
                    erros += 1
                    
            except Exception as e:
                logger.error(f"[processar_e_salvar_folha_obra] Erro func={func_id}: {e}")
                erros += 1
        
        return {
            'obra_id': obra_id,
            'ano': ano,
            'mes': mes,
            'funcionarios_encontrados': len(funcionarios_ids),
            'processados_com_sucesso': processados,
            'erros': erros
        }
        
    except Exception as e:
        logger.error(f"[processar_e_salvar_folha_obra] Erro geral: {e}", exc_info=True)
        return {
            'obra_id': obra_id,
            'ano': ano,
            'mes': mes,
            'funcionarios_encontrados': 0,
            'processados_com_sucesso': 0,
            'erros': 1,
            'erro_mensagem': str(e)
        }
