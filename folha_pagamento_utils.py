from models import db
"""
Utilitários para o Módulo 6 - Sistema de Folha de Pagamento Automática
Funções para cálculo de horas, impostos e processamento da folha
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from flask_login import current_user
from models import *

# ================================
# CÁLCULOS DE HORAS TRABALHADAS
# ================================

def calcular_horas_mensal(funcionario_id, mes_referencia):
    """Calcular horas trabalhadas no mês baseado nos pontos"""
    
    inicio_mes = mes_referencia.replace(day=1)
    fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Obter pontos do mês
    pontos = Ponto.query.filter(
        Ponto.funcionario_id == funcionario_id,
        Ponto.data_ponto.between(inicio_mes, fim_mes)
    ).all()
    
    horas_normais = 0
    horas_extras_50 = 0
    horas_extras_100 = 0
    horas_noturnas = 0
    faltas_horas = 0
    atrasos_horas = 0
    dias_trabalhados = 0
    dias_faltas = 0
    
    # Contar dias úteis do mês
    dias_uteis = 0
    data_atual = inicio_mes
    while data_atual <= fim_mes:
        if data_atual.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
        data_atual += timedelta(days=1)
    
    # Processar cada ponto
    for ponto in pontos:
        if ponto.hora_entrada and ponto.hora_saida:
            # Calcular horas trabalhadas
            entrada = datetime.combine(ponto.data_ponto, ponto.hora_entrada)
            saida = datetime.combine(ponto.data_ponto, ponto.hora_saida)
            
            # Se saída for no dia seguinte
            if ponto.hora_saida < ponto.hora_entrada:
                saida += timedelta(days=1)
            
            horas_trabalhadas = (saida - entrada).total_seconds() / 3600
            
            # Descontar intervalo (1h para jornada > 6h)
            if horas_trabalhadas > 6:
                horas_trabalhadas -= 1
            
            # Classificar horas
            if ponto.data_ponto.weekday() == 6:  # Domingo
                # Todo trabalho no domingo é 100%
                horas_extras_100 += horas_trabalhadas
            else:  # Dias úteis
                if horas_trabalhadas <= 8:
                    horas_normais += horas_trabalhadas
                else:
                    horas_normais += 8
                    extras = horas_trabalhadas - 8
                    
                    # Primeiras 2h extras = 50%, depois 100%
                    if extras <= 2:
                        horas_extras_50 += extras
                    else:
                        horas_extras_50 += 2
                        horas_extras_100 += extras - 2
            
            # Calcular adicional noturno (22h às 5h)
            horas_noturnas += calcular_horas_noturnas(ponto.hora_entrada, ponto.hora_saida)
            
            dias_trabalhados += 1
            
        elif ponto.data_ponto.weekday() < 5:  # Falta em dia útil
            dias_faltas += 1
            faltas_horas += 8  # 8 horas por dia de falta
    
    # Calcular DSR
    horas_dsr = calcular_dsr_horas(horas_extras_50, horas_extras_100, horas_noturnas, dias_uteis)
    
    # Salvar ou atualizar cálculo
    calculo = CalculoHorasMensal.query.filter_by(
        funcionario_id=funcionario_id,
        mes_referencia=inicio_mes
    ).first()
    
    if not calculo:
        calculo = CalculoHorasMensal()
        calculo.funcionario_id = funcionario_id
        calculo.mes_referencia = inicio_mes
        calculo.admin_id = current_user.id if current_user else 1
        db.session.add(calculo)
    
    # Atualizar valores
    calculo.horas_normais = horas_normais
    calculo.horas_extras_50 = horas_extras_50
    calculo.horas_extras_100 = horas_extras_100
    calculo.horas_noturnas = horas_noturnas
    calculo.horas_dsr = horas_dsr
    calculo.faltas_horas = faltas_horas
    calculo.atrasos_horas = atrasos_horas
    calculo.dias_trabalhados = dias_trabalhados
    calculo.dias_faltas = dias_faltas
    calculo.dias_uteis_mes = dias_uteis
    calculo.processado_em = datetime.utcnow()
    
    db.session.commit()
    
    return calculo

def calcular_horas_noturnas(hora_entrada, hora_saida):
    """Calcular horas noturnas (22h às 5h) com adicional de 20%"""
    
    if not hora_entrada or not hora_saida:
        return 0
    
    # Período noturno: 22h às 5h
    inicio_noturno = time(22, 0)
    fim_noturno = time(5, 0)
    
    horas_noturnas = 0
    
    # Converter para datetime para facilitar cálculos
    entrada = datetime.combine(date.today(), hora_entrada)
    saida = datetime.combine(date.today(), hora_saida)
    
    # Se saída for no dia seguinte
    if hora_saida < hora_entrada:
        saida += timedelta(days=1)
    
    # Verificar interseção com período noturno
    inicio_noturno_dt = datetime.combine(date.today(), inicio_noturno)
    fim_noturno_dt = datetime.combine(date.today() + timedelta(days=1), fim_noturno)
    
    # Calcular interseção
    inicio_intersecao = max(entrada, inicio_noturno_dt)
    fim_intersecao = min(saida, fim_noturno_dt)
    
    if inicio_intersecao < fim_intersecao:
        horas_noturnas = (fim_intersecao - inicio_intersecao).total_seconds() / 3600
    
    return horas_noturnas

def calcular_dsr_horas(horas_extras_50, horas_extras_100, horas_noturnas, dias_uteis):
    """Calcular DSR baseado em horas extras e adicional noturno"""
    
    if dias_uteis == 0:
        return 0
    
    # DSR = (Horas extras + Adicional noturno) / Dias úteis * Domingos e feriados
    # Simplificado: assumir 4 domingos por mês
    domingos_mes = 4
    
    base_dsr = horas_extras_50 + horas_extras_100 + horas_noturnas
    dsr_horas = (base_dsr / dias_uteis) * domingos_mes if dias_uteis > 0 else 0
    
    return dsr_horas

# ================================
# CÁLCULOS DE IMPOSTOS
# ================================

def calcular_inss(salario_bruto, parametros_legais):
    """Calcular INSS com tabela progressiva 2024"""
    
    if salario_bruto <= parametros_legais.inss_faixa1_limite:
        return salario_bruto * (parametros_legais.inss_faixa1_percentual / 100)
    
    elif salario_bruto <= parametros_legais.inss_faixa2_limite:
        inss = parametros_legais.inss_faixa1_limite * (parametros_legais.inss_faixa1_percentual / 100)
        inss += (salario_bruto - parametros_legais.inss_faixa1_limite) * (parametros_legais.inss_faixa2_percentual / 100)
        return inss
    
    elif salario_bruto <= parametros_legais.inss_faixa3_limite:
        inss = parametros_legais.inss_faixa1_limite * (parametros_legais.inss_faixa1_percentual / 100)
        inss += (parametros_legais.inss_faixa2_limite - parametros_legais.inss_faixa1_limite) * (parametros_legais.inss_faixa2_percentual / 100)
        inss += (salario_bruto - parametros_legais.inss_faixa2_limite) * (parametros_legais.inss_faixa3_percentual / 100)
        return inss
    
    elif salario_bruto <= parametros_legais.inss_faixa4_limite:
        inss = parametros_legais.inss_faixa1_limite * (parametros_legais.inss_faixa1_percentual / 100)
        inss += (parametros_legais.inss_faixa2_limite - parametros_legais.inss_faixa1_limite) * (parametros_legais.inss_faixa2_percentual / 100)
        inss += (parametros_legais.inss_faixa3_limite - parametros_legais.inss_faixa2_limite) * (parametros_legais.inss_faixa3_percentual / 100)
        inss += (salario_bruto - parametros_legais.inss_faixa3_limite) * (parametros_legais.inss_faixa4_percentual / 100)
        return inss
    
    else:
        # Teto do INSS
        return parametros_legais.inss_teto

def calcular_irrf(salario_bruto, inss, dependentes, parametros_legais):
    """Calcular IRRF com tabela progressiva 2024"""
    
    # Base de cálculo = Salário bruto - INSS - (Dependentes * valor por dependente)
    base_calculo = salario_bruto - inss - (dependentes * parametros_legais.irrf_dependente_valor)
    
    if base_calculo <= parametros_legais.irrf_isencao:
        return 0
    
    elif base_calculo <= parametros_legais.irrf_faixa1_limite:
        irrf = base_calculo * (parametros_legais.irrf_faixa1_percentual / 100)
        return max(0, irrf - parametros_legais.irrf_faixa1_deducao)
    
    elif base_calculo <= parametros_legais.irrf_faixa2_limite:
        irrf = base_calculo * (parametros_legais.irrf_faixa2_percentual / 100)
        return max(0, irrf - parametros_legais.irrf_faixa2_deducao)
    
    elif base_calculo <= parametros_legais.irrf_faixa3_limite:
        irrf = base_calculo * (parametros_legais.irrf_faixa3_percentual / 100)
        return max(0, irrf - parametros_legais.irrf_faixa3_deducao)
    
    else:
        irrf = base_calculo * (parametros_legais.irrf_faixa4_percentual / 100)
        return max(0, irrf - parametros_legais.irrf_faixa4_deducao)

def calcular_fgts(salario_bruto, parametros_legais):
    """Calcular FGTS (8% sobre salário bruto)"""
    return salario_bruto * (parametros_legais.fgts_percentual / 100)

# ================================
# CONFIGURAÇÕES E BENEFÍCIOS
# ================================

def obter_configuracao_salarial_vigente(funcionario_id, data_referencia):
    """Obter configuração salarial vigente na data"""
    
    config = ConfiguracaoSalarial.query.filter(
        ConfiguracaoSalarial.funcionario_id == funcionario_id,
        ConfiguracaoSalarial.ativo == True,
        ConfiguracaoSalarial.data_inicio <= data_referencia
    ).filter(
        db.or_(
            ConfiguracaoSalarial.data_fim.is_(None),
            ConfiguracaoSalarial.data_fim >= data_referencia
        )
    ).first()
    
    return config

def calcular_proventos_funcionario(funcionario, config_salarial, calculo_horas, parametros):
    """Calcular todos os proventos do funcionário"""
    
    # Salário base
    if config_salarial.tipo_salario == 'MENSAL':
        salario_base = config_salarial.salario_base
    elif config_salarial.tipo_salario == 'HORISTA':
        salario_base = config_salarial.valor_hora * calculo_horas.horas_normais
    else:
        salario_base = config_salarial.salario_base  # Comissionado tem base + comissão
    
    # Valor hora para cálculos
    valor_hora = config_salarial.valor_hora or (config_salarial.salario_base / config_salarial.carga_horaria_mensal)
    
    # Horas extras
    horas_extras_50_valor = calculo_horas.horas_extras_50 * valor_hora * (1 + parametros.hora_extra_50_percentual / 100)
    horas_extras_100_valor = calculo_horas.horas_extras_100 * valor_hora * (1 + parametros.hora_extra_100_percentual / 100)
    horas_extras = horas_extras_50_valor + horas_extras_100_valor
    
    # Adicional noturno
    adicional_noturno = calculo_horas.horas_noturnas * valor_hora * (parametros.adicional_noturno_percentual / 100)
    
    # DSR
    dsr = calculo_horas.horas_dsr * valor_hora
    
    # Faltas e atrasos (descontos)
    faltas = calculo_horas.faltas_horas * valor_hora
    atrasos = calculo_horas.atrasos_horas * valor_hora
    
    # Comissões (se aplicável)
    comissoes = 0
    if config_salarial.tipo_salario == 'COMISSIONADO' and config_salarial.percentual_comissao:
        # Aqui você pode implementar lógica de comissão baseada em vendas/obras
        comissoes = 0  # Placeholder
    
    return {
        'salario_base': salario_base,
        'horas_extras': horas_extras,
        'adicional_noturno': adicional_noturno,
        'dsr': dsr,
        'comissoes': comissoes,
        'faltas': faltas,
        'atrasos': atrasos
    }

def calcular_descontos_obrigatorios(proventos, dependentes, parametros):
    """Calcular INSS, IRRF e FGTS"""
    
    salario_bruto = proventos['salario_base'] + proventos['horas_extras'] + proventos['adicional_noturno'] + proventos['dsr'] + proventos['comissoes']
    
    inss = calcular_inss(salario_bruto, parametros)
    irrf = calcular_irrf(salario_bruto, inss, dependentes, parametros)
    fgts = calcular_fgts(salario_bruto, parametros)
    
    return {
        'inss': inss,
        'irrf': irrf,
        'fgts': fgts
    }

def calcular_beneficios_funcionario(funcionario_id, mes_referencia):
    """Calcular descontos de benefícios"""
    
    beneficios = BeneficioFuncionario.query.filter(
        BeneficioFuncionario.funcionario_id == funcionario_id,
        BeneficioFuncionario.ativo == True,
        BeneficioFuncionario.data_inicio <= mes_referencia
    ).filter(
        db.or_(
            BeneficioFuncionario.data_fim.is_(None),
            BeneficioFuncionario.data_fim >= mes_referencia
        )
    ).all()
    
    vale_refeicao = 0
    vale_transporte = 0
    plano_saude = 0
    seguro_vida = 0
    
    for beneficio in beneficios:
        desconto = beneficio.valor * (beneficio.percentual_desconto / 100)
        
        if beneficio.tipo_beneficio == 'VR':
            vale_refeicao += desconto
        elif beneficio.tipo_beneficio == 'VT':
            vale_transporte += desconto
        elif beneficio.tipo_beneficio == 'PLANO_SAUDE':
            plano_saude += desconto
        elif beneficio.tipo_beneficio == 'SEGURO_VIDA':
            seguro_vida += desconto
    
    return {
        'vale_refeicao': vale_refeicao,
        'vale_transporte': vale_transporte,
        'plano_saude': plano_saude,
        'seguro_vida': seguro_vida,
        'total_descontos': vale_refeicao + vale_transporte + plano_saude + seguro_vida
    }

def calcular_lancamentos_recorrentes(funcionario_id, mes_referencia, salario_base):
    """Calcular lançamentos recorrentes"""
    
    lancamentos = LancamentoRecorrente.query.filter(
        LancamentoRecorrente.funcionario_id == funcionario_id,
        LancamentoRecorrente.ativo == True,
        LancamentoRecorrente.data_inicio <= mes_referencia
    ).filter(
        db.or_(
            LancamentoRecorrente.data_fim.is_(None),
            LancamentoRecorrente.data_fim >= mes_referencia
        )
    ).all()
    
    proventos = 0
    descontos = 0
    
    for lancamento in lancamentos:
        if lancamento.valor:
            valor = lancamento.valor
        elif lancamento.percentual:
            valor = salario_base * (lancamento.percentual / 100)
        else:
            valor = 0
        
        if lancamento.tipo == 'PROVENTO':
            proventos += valor
        else:
            descontos += valor
    
    return {
        'proventos': proventos,
        'descontos': descontos
    }

def calcular_adiantamentos_mes(funcionario_id, mes_referencia):
    """Calcular valor dos adiantamentos a descontar no mês"""
    
    adiantamentos = Adiantamento.query.filter(
        Adiantamento.funcionario_id == funcionario_id,
        Adiantamento.status == 'APROVADO',
        Adiantamento.parcelas_pagas < Adiantamento.parcelas
    ).all()
    
    total_descontar = 0
    
    for adiantamento in adiantamentos:
        # Verificar se deve descontar parcela este mês
        # Simplificado: descontar uma parcela por mês até quitar
        if adiantamento.parcelas_pagas < adiantamento.parcelas:
            total_descontar += adiantamento.valor_parcela or (adiantamento.valor_total / adiantamento.parcelas)
    
    return total_descontar

# ================================
# PROCESSAMENTO DA FOLHA
# ================================

def processar_folha_mensal(admin_id, mes_referencia):
    """Processar folha de pagamento completa do mês"""
    
    inicio_mes = mes_referencia.replace(day=1)
    fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Obter funcionários ativos
    funcionarios = Funcionario.query.filter_by(
        admin_id=admin_id,
        ativo=True
    ).all()
    
    # Obter parâmetros legais
    parametros = ParametrosLegais.query.filter_by(
        admin_id=admin_id,
        ano_vigencia=mes_referencia.year,
        ativo=True
    ).first()
    
    if not parametros:
        raise Exception(f"Parâmetros legais não configurados para {mes_referencia.year}")
    
    resultados = []
    
    for funcionario in funcionarios:
        try:
            # 1. Calcular horas do mês
            calculo_horas = calcular_horas_mensal(funcionario.id, inicio_mes)
            
            # 2. Obter configuração salarial
            config_salarial = obter_configuracao_salarial_vigente(funcionario.id, mes_referencia)
            if not config_salarial:
                continue
            
            # 3. Calcular proventos
            proventos = calcular_proventos_funcionario(funcionario, config_salarial, calculo_horas, parametros)
            
            # 4. Calcular descontos obrigatórios
            descontos_obrigatorios = calcular_descontos_obrigatorios(proventos, config_salarial.dependentes, parametros)
            
            # 5. Calcular benefícios
            beneficios = calcular_beneficios_funcionario(funcionario.id, mes_referencia)
            
            # 6. Calcular lançamentos recorrentes
            recorrentes = calcular_lancamentos_recorrentes(funcionario.id, mes_referencia, proventos['salario_base'])
            
            # 7. Calcular adiantamentos
            adiantamentos_valor = calcular_adiantamentos_mes(funcionario.id, mes_referencia)
            
            # 8. Calcular totais
            total_proventos = (
                proventos['salario_base'] +
                proventos['horas_extras'] +
                proventos['adicional_noturno'] +
                proventos['dsr'] +
                proventos['comissoes'] +
                recorrentes['proventos']
            )
            
            total_descontos = (
                descontos_obrigatorios['inss'] +
                descontos_obrigatorios['irrf'] +
                beneficios['total_descontos'] +
                recorrentes['descontos'] +
                adiantamentos_valor +
                proventos['faltas'] +
                proventos['atrasos']
            )
            
            salario_liquido = total_proventos - total_descontos
            
            # 9. Salvar folha de pagamento
            folha = FolhaPagamento.query.filter_by(
                funcionario_id=funcionario.id,
                mes_referencia=inicio_mes
            ).first()
            
            if not folha:
                folha = FolhaPagamento()
                folha.funcionario_id = funcionario.id
                folha.mes_referencia = inicio_mes
                folha.admin_id = admin_id
                db.session.add(folha)
            
            # Atualizar valores
            folha.salario_base = proventos['salario_base']
            folha.horas_extras = proventos['horas_extras']
            folha.adicional_noturno = proventos['adicional_noturno']
            folha.dsr = proventos['dsr']
            folha.comissoes = proventos['comissoes']
            folha.outros_proventos = recorrentes['proventos']
            folha.total_proventos = total_proventos
            
            folha.inss = descontos_obrigatorios['inss']
            folha.irrf = descontos_obrigatorios['irrf']
            folha.fgts = descontos_obrigatorios['fgts']
            folha.vale_refeicao = beneficios['vale_refeicao']
            folha.vale_transporte = beneficios['vale_transporte']
            folha.plano_saude = beneficios['plano_saude']
            folha.seguro_vida = beneficios['seguro_vida']
            folha.faltas = proventos['faltas']
            folha.atrasos = proventos['atrasos']
            folha.adiantamentos = adiantamentos_valor
            folha.outros_descontos = recorrentes['descontos']
            folha.total_descontos = total_descontos
            
            folha.salario_liquido = salario_liquido
            folha.calculado_em = datetime.utcnow()
            
            resultados.append({
                'funcionario': funcionario,
                'folha': folha,
                'sucesso': True
            })
            
        except Exception as e:
            resultados.append({
                'funcionario': funcionario,
                'erro': str(e),
                'sucesso': False
            })
    
    db.session.commit()
    
    return resultados

def criar_parametros_legais_padrao(admin_id, ano):
    """Criar parâmetros legais padrão para o ano"""
    
    parametros = ParametrosLegais()
    parametros.admin_id = admin_id
    parametros.ano_vigencia = ano
    
    db.session.add(parametros)
    db.session.commit()
    
    return parametros