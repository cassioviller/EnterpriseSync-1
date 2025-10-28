"""
Serviço de Cálculo de Folha de Pagamento
Centraliza todos os cálculos de folha, INSS, IR, FGTS e horas extras
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional
from sqlalchemy import extract, func
from models import db, Funcionario, RegistroPonto, ParametrosLegais, ConfiguracaoSalarial, BeneficioFuncionario, CalendarioUtil
from utils import calcular_valor_hora_periodo


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
# FUNÇÕES DE CÁLCULO DE HORAS
# ========================================

def calcular_horas_mes(funcionario_id: int, ano: int, mes: int) -> Dict:
    """
    Calcula horas trabalhadas no mês baseado nos registros de ponto (CONFORME CLT)
    DIFERENCIA HE 50% (sábado/dia útil) de HE 100% (domingo/feriado)
    
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
            'faltas': int
        }
    """
    try:
        import calendar
        from datetime import timedelta
        
        # PRÉ-CARREGAR feriados do mês (otimização N+1)
        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
        
        feriados_calendario = CalendarioUtil.query.filter(
            CalendarioUtil.data >= primeiro_dia,
            CalendarioUtil.data <= ultimo_dia,
            CalendarioUtil.eh_feriado == True
        ).all()
        
        # Criar set de datas de feriados para lookup O(1)
        datas_feriados = {f.data for f in feriados_calendario}
        
        # Buscar registros de ponto do mês
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            extract('year', RegistroPonto.data) == ano,
            extract('month', RegistroPonto.data) == mes
        ).all()
        
        total_horas = Decimal('0')
        horas_extras_50 = Decimal('0')  # HE 50% (sábado ou dia útil)
        horas_extras_100 = Decimal('0')  # HE 100% (domingo ou feriado)
        dias_trabalhados = 0
        total_minutos_atraso = 0  # Somar atrasos do mês
        
        for registro in registros:
            if registro.horas_trabalhadas:
                total_horas += Decimal(str(registro.horas_trabalhadas))
                dias_trabalhados += 1
            
            # Somar atrasos do registro
            if registro.total_atraso_minutos:
                total_minutos_atraso += registro.total_atraso_minutos
            
            if registro.horas_extras:
                # Verificar tipo de hora extra pelo dia da semana, tipo_registro OU calendário
                dia_semana = registro.data.weekday()
                tipo = registro.tipo_registro or ''
                
                # Verificar se é feriado no calendário (lookup O(1) em set)
                eh_feriado_calendario = registro.data in datas_feriados
                
                # HE 100%: Domingo OU Feriado (tipo_registro OU calendário)
                if dia_semana == 6 or 'domingo' in tipo.lower() or 'feriado' in tipo.lower() or eh_feriado_calendario:
                    horas_extras_100 += Decimal(str(registro.horas_extras))
                else:
                    # HE 50%: Sábado ou dia útil
                    horas_extras_50 += Decimal(str(registro.horas_extras))
        
        # Calcular dias úteis CORRETAMENTE (contando calendário real)
        # Já temos primeiro_dia, ultimo_dia e datas_feriados carregados acima
        
        dias_uteis_esperados = 0
        domingos_feriados = 0
        sabados = 0
        dia_atual = primeiro_dia
        
        while dia_atual <= ultimo_dia:
            # Verificar se é feriado (lookup O(1) em set)
            eh_feriado = dia_atual in datas_feriados
            
            if dia_atual.weekday() == 6 or eh_feriado:  # Domingo OU Feriado
                domingos_feriados += 1
            elif dia_atual.weekday() == 5:  # Sábado
                sabados += 1
            else:  # Segunda a sexta (exceto feriados)
                dias_uteis_esperados += 1
            dia_atual += timedelta(days=1)
        
        # Calcular faltas (dias úteis esperados - dias trabalhados)
        faltas = max(0, dias_uteis_esperados - dias_trabalhados)
        
        # Total de extras (compatibilidade)
        total_extras = horas_extras_50 + horas_extras_100
        
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
            'total_minutos_atraso': total_minutos_atraso
        }
        
    except Exception as e:
        print(f"Erro ao calcular horas do mês: {e}")
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
            'total_minutos_atraso': 0
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


def calcular_salario_bruto(funcionario: Funcionario, horas_info: Dict, data_inicio: date, data_fim: date) -> Decimal:
    """
    Calcula salário bruto considerando tipo de salário e horas extras
    
    Args:
        funcionario: Objeto Funcionario
        horas_info: Dicionário com informações de horas trabalhadas
        data_inicio: Data de início do período
        data_fim: Data de fim do período
        
    Returns:
        Decimal: Valor do salário bruto
    """
    try:
        # Buscar configuração salarial vigente
        config = ConfiguracaoSalarial.query.filter_by(
            funcionario_id=funcionario.id,
            ativo=True
        ).filter(
            ConfiguracaoSalarial.data_fim.is_(None) | 
            (ConfiguracaoSalarial.data_fim >= date.today())
        ).first()
        
        if not config:
            # Usar salário base do funcionário
            salario_base = Decimal(str(funcionario.salario or 0))
            tipo_salario = 'MENSAL'
        else:
            salario_base = config.salario_base
            tipo_salario = config.tipo_salario
        
        # Calcular de acordo com o tipo
        if tipo_salario == 'HORISTA':
            # Salário = valor hora * horas trabalhadas
            if config and config.valor_hora:
                valor_hora = config.valor_hora
            else:
                valor_hora = Decimal(str(calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)))
            salario_normal = valor_hora * Decimal(str(horas_info['total']))
        else:
            # Salário mensal fixo
            salario_normal = salario_base
        
        # Calcular horas extras (DIFERENCIANDO HE 50% E HE 100%)
        valor_hora_normal = Decimal(str(calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)))
        
        # HE 50% (sábado ou dia útil)
        valor_he_50 = valor_hora_normal * Decimal('1.5') * Decimal(str(horas_info.get('extras_50', 0)))
        
        # HE 100% (domingo ou feriado)
        valor_he_100 = valor_hora_normal * Decimal('2.0') * Decimal(str(horas_info.get('extras_100', 0)))
        
        # Total de horas extras
        valor_extras = valor_he_50 + valor_he_100
        
        # Calcular DSR sobre horas extras
        valor_dsr = calcular_dsr(horas_info, valor_hora_normal)
        
        # Descontar faltas (se houver)
        valor_desconto_faltas = valor_hora_normal * 8 * Decimal(str(horas_info['faltas']))
        
        # Descontar atrasos (se houver) - converter minutos em horas
        if horas_info.get('total_minutos_atraso', 0) > 0:
            horas_atraso = Decimal(str(horas_info['total_minutos_atraso'])) / Decimal('60')
            valor_desconto_atrasos = valor_hora_normal * horas_atraso
        else:
            valor_desconto_atrasos = Decimal('0')
        
        salario_bruto = salario_normal + valor_extras + valor_dsr - valor_desconto_faltas - valor_desconto_atrasos
        
        return salario_bruto
        
    except Exception as e:
        print(f"Erro ao calcular salário bruto: {e}")
        return Decimal('0')


# ========================================
# CÁLCULOS DE DESCONTOS
# ========================================

def calcular_inss(salario_bruto: Decimal) -> Decimal:
    """
    Calcula INSS progressivo conforme tabela vigente
    
    Args:
        salario_bruto: Valor do salário bruto
        
    Returns:
        Decimal: Valor do desconto de INSS
    """
    if salario_bruto <= 0:
        return Decimal('0')
    
    inss_total = Decimal('0')
    salario_restante = salario_bruto
    limite_anterior = Decimal('0')
    
    for faixa in TABELA_INSS_2025:
        if salario_restante <= 0:
            break
        
        # Calcular faixa de incidência
        valor_faixa = min(salario_restante, faixa['limite'] - limite_anterior)
        
        # Aplicar alíquota
        inss_faixa = valor_faixa * (faixa['aliquota'] / 100)
        inss_total += inss_faixa
        
        # Atualizar valores
        salario_restante -= valor_faixa
        limite_anterior = faixa['limite']
    
    return inss_total.quantize(Decimal('0.01'))


def calcular_irrf(salario_bruto: Decimal, inss: Decimal, dependentes: int = 0) -> Decimal:
    """
    Calcula Imposto de Renda Retido na Fonte
    
    Args:
        salario_bruto: Valor do salário bruto
        inss: Valor do INSS calculado
        dependentes: Número de dependentes
        
    Returns:
        Decimal: Valor do IR a ser retido
    """
    # Base de cálculo = Salário Bruto - INSS - Deduções por dependente
    base_calculo = salario_bruto - inss - (Decimal(str(dependentes)) * DEDUCAO_DEPENDENTE_IR)
    
    if base_calculo <= TABELA_IR_2025[0]['limite']:
        return Decimal('0')
    
    # Encontrar faixa aplicável
    for faixa in TABELA_IR_2025:
        if base_calculo <= faixa['limite']:
            ir = (base_calculo * (faixa['aliquota'] / 100)) - faixa['parcela_deduzir']
            return max(Decimal('0'), ir).quantize(Decimal('0.01'))
    
    return Decimal('0')


def calcular_descontos(salario_bruto: Decimal, funcionario: Funcionario) -> Dict:
    """
    Calcula todos os descontos (INSS, IR, benefícios, etc)
    
    Args:
        salario_bruto: Valor do salário bruto
        funcionario: Objeto Funcionario
        
    Returns:
        dict: Dicionário com todos os descontos
    """
    # INSS
    inss = calcular_inss(salario_bruto)
    
    # Buscar dependentes da configuração salarial
    config = ConfiguracaoSalarial.query.filter_by(
        funcionario_id=funcionario.id,
        ativo=True
    ).first()
    dependentes = config.dependentes if config else 0
    
    # IR
    irrf = calcular_irrf(salario_bruto, inss, dependentes)
    
    # Benefícios com desconto
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
        
        # Calcular desconto do funcionário
        if beneficio.percentual_desconto:
            desconto = valor_beneficio * (beneficio.percentual_desconto / 100)
            desconto_beneficios += desconto
    
    # Total de descontos
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

def calcular_encargos_patronais(salario_bruto: Decimal) -> Dict:
    """
    Calcula encargos patronais (FGTS, INSS Patronal, etc)
    
    Args:
        salario_bruto: Valor do salário bruto
        
    Returns:
        dict: Dicionário com todos os encargos
    """
    # FGTS (8%)
    fgts = salario_bruto * (ALIQUOTA_FGTS / 100)
    
    # INSS Patronal (20% base + RAT 1-3% + Terceiros ~5.8%)
    # Simplificado: 20% base
    inss_patronal = salario_bruto * Decimal('0.20')
    
    # Total de encargos
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

def processar_folha_funcionario(funcionario: Funcionario, ano: int, mes: int) -> Dict:
    """
    Processa a folha completa de um funcionário
    
    Args:
        funcionario: Objeto Funcionario
        ano: Ano de referência
        mes: Mês de referência
        
    Returns:
        dict: Dados completos da folha processada
    """
    try:
        # Calcular datas do período
        import calendar
        data_inicio = date(ano, mes, 1)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_fim = date(ano, mes, ultimo_dia)
        
        # 1. Calcular horas do mês
        horas_info = calcular_horas_mes(funcionario.id, ano, mes)
        
        # 2. Calcular salário bruto
        salario_bruto = calcular_salario_bruto(funcionario, horas_info, data_inicio, data_fim)
        
        # 3. Calcular descontos
        descontos = calcular_descontos(salario_bruto, funcionario)
        
        # 4. Calcular encargos patronais
        encargos = calcular_encargos_patronais(salario_bruto)
        
        # 5. Calcular salário líquido
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
        print(f"Erro ao processar folha do funcionário {funcionario.id}: {e}")
        return None
