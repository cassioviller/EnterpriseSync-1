"""
Serviço de Cálculo de Folha de Pagamento
Centraliza todos os cálculos de folha, INSS, IR, FGTS e horas extras
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional
from sqlalchemy import extract, func
from models import db, Funcionario, RegistroPonto, ParametrosLegais, ConfiguracaoSalarial, BeneficioFuncionario


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
    Calcula horas trabalhadas no mês baseado nos registros de ponto
    
    Returns:
        dict: {
            'total': float,
            'extras': float, 
            'dias_trabalhados': int,
            'faltas': int
        }
    """
    try:
        # Buscar registros de ponto do mês
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            extract('year', RegistroPonto.data) == ano,
            extract('month', RegistroPonto.data) == mes
        ).all()
        
        total_horas = Decimal('0')
        horas_extras = Decimal('0')
        dias_trabalhados = 0
        
        for registro in registros:
            if registro.horas_trabalhadas:
                total_horas += Decimal(str(registro.horas_trabalhadas))
                dias_trabalhados += 1
            
            if registro.horas_extras:
                horas_extras += Decimal(str(registro.horas_extras))
        
        # Calcular faltas (dias úteis esperados - dias trabalhados)
        import calendar
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias_uteis_esperados = dias_mes - 8  # Aproximado (descontando domingos e sábados)
        faltas = max(0, dias_uteis_esperados - dias_trabalhados)
        
        return {
            'total': float(total_horas),
            'extras': float(horas_extras),
            'dias_trabalhados': dias_trabalhados,
            'faltas': faltas
        }
        
    except Exception as e:
        print(f"Erro ao calcular horas do mês: {e}")
        return {
            'total': 0,
            'extras': 0,
            'dias_trabalhados': 0,
            'faltas': 0
        }


def calcular_salario_bruto(funcionario: Funcionario, horas_info: Dict) -> Decimal:
    """
    Calcula salário bruto considerando tipo de salário e horas extras
    
    Args:
        funcionario: Objeto Funcionario
        horas_info: Dicionário com informações de horas trabalhadas
        
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
            valor_hora = config.valor_hora if config else (salario_base / 220)
            salario_normal = valor_hora * Decimal(str(horas_info['total']))
        else:
            # Salário mensal fixo
            salario_normal = salario_base
        
        # Adicionar horas extras (50% de adicional)
        valor_hora_normal = salario_base / 220
        valor_extras = valor_hora_normal * Decimal('1.5') * Decimal(str(horas_info['extras']))
        
        # Descontar faltas (se houver)
        valor_desconto_faltas = valor_hora_normal * 8 * Decimal(str(horas_info['faltas']))
        
        salario_bruto = salario_normal + valor_extras - valor_desconto_faltas
        
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
        # 1. Calcular horas do mês
        horas_info = calcular_horas_mes(funcionario.id, ano, mes)
        
        # 2. Calcular salário bruto
        salario_bruto = calcular_salario_bruto(funcionario, horas_info)
        
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
