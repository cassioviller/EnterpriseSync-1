"""
ENGINE DE CÁLCULO DE KPIs v4.0 - SIGE
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Implementa sistema completo de KPIs integrado com horários de trabalho
conforme especificação técnica v4.0.

Recursos principais:
1. Integração com horários de trabalho cadastrados
2. Cálculo preciso de produtividade baseado em horário específico
3. 15 KPIs organizados em layout 4-4-4-3
4. Quantificação do valor das faltas justificadas
5. Cálculos financeiros precisos

Data: 14 de Julho de 2025
"""

from datetime import datetime, date, time, timedelta
from sqlalchemy import and_, func, text
from app import db
import calendar


def calcular_kpis_funcionario_v4(funcionario_id, data_inicio=None, data_fim=None):
    """
    Engine de KPIs v4.0 - INTEGRADO COM HORÁRIOS DE TRABALHO
    
    Calcula todos os 15 KPIs baseados no horário específico do funcionário
    
    Args:
        funcionario_id: ID do funcionário
        data_inicio: Data de início do período (opcional)
        data_fim: Data de fim do período (opcional)
    
    Returns:
        dict: Dicionário com os 15 KPIs calculados e informações do horário
    """
    try:
        from models import Funcionario, HorarioTrabalho, RegistroPonto, RegistroAlimentacao, OutroCusto
        
        # 1. BUSCAR FUNCIONÁRIO E HORÁRIO
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return None
        
        # 2. OBTER HORÁRIO DE TRABALHO ESPECÍFICO
        horario_info = obter_horario_funcionario(funcionario)
        
        # 3. DEFINIR PERÍODO
        if not data_inicio:
            data_inicio = date.today().replace(day=1)
        if not data_fim:
            data_fim = date.today()
        
        # 4. BUSCAR REGISTROS DO PERÍODO
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        # 5. PROCESSAR REGISTROS
        dados_processados = processar_registros_com_horario(registros, horario_info)
        
        # 6. CALCULAR KPIs BÁSICOS
        kpis_basicos = calcular_kpis_basicos(dados_processados, horario_info)
        
        # 7. CALCULAR KPIs ANALÍTICOS
        kpis_analiticos = calcular_kpis_analiticos(dados_processados, horario_info)
        
        # 8. CALCULAR KPIs FINANCEIROS
        kpis_financeiros = calcular_kpis_financeiros(funcionario, dados_processados, horario_info, data_inicio, data_fim)
        
        # 9. CALCULAR KPIs RESUMO
        kpis_resumo = calcular_kpis_resumo(funcionario, dados_processados, horario_info)
        
        # 10. CONSOLIDAR RESULTADO
        return {
            **kpis_basicos,
            **kpis_analiticos, 
            **kpis_financeiros,
            **kpis_resumo,
            'horario_info': horario_info,
            'periodo': f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        }
        
    except Exception as e:
        print(f"Erro ao calcular KPIs v4.0: {str(e)}")
        return None


def obter_horario_funcionario(funcionario):
    """
    Obtém informações do horário de trabalho do funcionário
    
    Args:
        funcionario: Objeto Funcionario
    
    Returns:
        dict: Informações do horário de trabalho
    """
    # Valores padrão
    horario_info = {
        'nome': 'Padrão',
        'entrada': time(8, 0),
        'saida': time(17, 0),
        'almoco_inicio': time(12, 0),
        'almoco_fim': time(13, 0),
        'horas_diarias': 8.0,
        'dias_semana': 'seg-sex',
        'valor_hora': 0.0
    }
    
    # Buscar horário específico
    if hasattr(funcionario, 'horario_trabalho_id') and funcionario.horario_trabalho_id:
        from models import HorarioTrabalho
        horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
        if horario:
            # Calcular horas líquidas
            total_horas = calcular_diferenca_horas(horario.entrada, horario.saida)
            almoco_horas = calcular_diferenca_horas(horario.saida_almoco, horario.retorno_almoco)
            horas_liquidas = total_horas - almoco_horas
            
            horario_info.update({
                'nome': horario.nome,
                'entrada': horario.entrada,
                'saida': horario.saida,
                'almoco_inicio': horario.saida_almoco,
                'almoco_fim': horario.retorno_almoco,
                'horas_diarias': horas_liquidas,
                'dias_semana': horario.dias_semana or 'seg-sex'
            })
    
    # Calcular valor/hora baseado no horário específico
    if funcionario.salario and horario_info['horas_diarias'] > 0:
        # Considerar 22 dias úteis médios por mês
        horas_mensais = horario_info['horas_diarias'] * 22
        horario_info['valor_hora'] = funcionario.salario / horas_mensais
    
    return horario_info


def calcular_diferenca_horas(hora_inicio, hora_fim):
    """
    Calcula diferença entre horários considerando virada de dia
    
    Args:
        hora_inicio: Hora de início
        hora_fim: Hora de fim
    
    Returns:
        float: Diferença em horas decimais
    """
    inicio_decimal = hora_inicio.hour + hora_inicio.minute / 60
    fim_decimal = hora_fim.hour + hora_fim.minute / 60
    
    if fim_decimal < inicio_decimal:  # Virada de dia (ex: 22:00 - 06:00)
        return (24 - inicio_decimal) + fim_decimal
    else:
        return fim_decimal - inicio_decimal


def processar_registros_com_horario(registros, horario_info):
    """
    Processa registros considerando horário específico
    
    Args:
        registros: Lista de registros de ponto
        horario_info: Informações do horário de trabalho
    
    Returns:
        dict: Dados processados
    """
    # Tipos que contam como dias úteis programados (excluindo fins de semana)
    tipos_dias_uteis = [
        'trabalho_normal', 'feriado_trabalhado', 'meio_periodo', 
        'falta', 'falta_justificada', 'atraso', 'saida_antecipada'
    ]
    
    dados = {
        'registros_programados': [],
        'horas_trabalhadas': 0.0,
        'horas_extras': 0.0,
        'faltas_nao_justificadas': 0,
        'faltas_justificadas': 0,
        'atrasos_total': 0.0,
        'dias_com_lancamento': 0
    }
    
    dias_unicos = set()
    
    for registro in registros:
        # Contar apenas dias úteis programados
        if registro.tipo_registro in tipos_dias_uteis:
            if registro.data not in dias_unicos:
                dias_unicos.add(registro.data)
                dados['dias_com_lancamento'] += 1
            dados['registros_programados'].append(registro)
        
        # Somar horas trabalhadas
        if registro.horas_trabalhadas:
            dados['horas_trabalhadas'] += registro.horas_trabalhadas
        
        # Identificar horas extras
        if registro.horas_extras:
            dados['horas_extras'] += registro.horas_extras
        elif registro.tipo_registro in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
            # Todas as horas destes tipos são extras
            dados['horas_extras'] += registro.horas_trabalhadas or 0
        
        # Contar faltas
        if registro.tipo_registro == 'falta':
            dados['faltas_nao_justificadas'] += 1
        elif registro.tipo_registro == 'falta_justificada':
            dados['faltas_justificadas'] += 1
        
        # Calcular atrasos usando total_atraso_minutos se disponível
        if hasattr(registro, 'total_atraso_minutos') and registro.total_atraso_minutos:
            dados['atrasos_total'] += registro.total_atraso_minutos / 60
    
    return dados


def calcular_kpis_basicos(dados, horario_info):
    """
    Calcula KPIs básicos (linha 1: 4 KPIs)
    
    Args:
        dados: Dados processados dos registros
        horario_info: Informações do horário
    
    Returns:
        dict: KPIs básicos
    """
    return {
        'horas_trabalhadas': round(dados['horas_trabalhadas'], 1),
        'horas_extras': round(dados['horas_extras'], 1),
        'faltas': dados['faltas_nao_justificadas'],
        'atrasos': round(dados['atrasos_total'], 2)
    }


def calcular_kpis_analiticos(dados, horario_info):
    """
    Calcula KPIs analíticos (linha 2: 4 KPIs)
    
    Args:
        dados: Dados processados dos registros
        horario_info: Informações do horário
    
    Returns:
        dict: KPIs analíticos
    """
    dias_programados = dados['dias_com_lancamento']
    horas_trabalhadas = dados['horas_trabalhadas']
    
    if dias_programados > 0:
        # Usar horário específico para calcular horas esperadas
        horas_esperadas = dias_programados * horario_info['horas_diarias']
        produtividade = (horas_trabalhadas / horas_esperadas) * 100 if horas_esperadas > 0 else 0
        absenteismo = (dados['faltas_nao_justificadas'] / dias_programados) * 100
        media_diaria = horas_trabalhadas / dias_programados
    else:
        produtividade = 0
        absenteismo = 0
        media_diaria = 0
    
    return {
        'produtividade': round(produtividade, 1),
        'absenteismo': round(absenteismo, 1),
        'media_diaria': round(media_diaria, 1),
        'faltas_justificadas': dados['faltas_justificadas']
    }


def calcular_kpis_financeiros(funcionario, dados, horario_info, data_inicio, data_fim):
    """
    Calcula KPIs financeiros (linha 3: 4 KPIs)
    
    Args:
        funcionario: Objeto funcionario
        dados: Dados processados dos registros
        horario_info: Informações do horário
        data_inicio: Data de início do período
        data_fim: Data de fim do período
    
    Returns:
        dict: KPIs financeiros
    """
    from models import RegistroAlimentacao, OutroCusto
    
    valor_hora = horario_info['valor_hora']
    horas_trabalhadas = dados['horas_trabalhadas']
    horas_extras = dados['horas_extras']
    
    # Custo mão de obra = salário base - desconto faltas + adicional extras
    custo_base = funcionario.salario or 0
    
    # Desconto por faltas não justificadas
    desconto_faltas = dados['faltas_nao_justificadas'] * horario_info['horas_diarias'] * valor_hora
    
    # Adicional por horas extras (assumindo 50% de adicional)
    adicional_extras = horas_extras * valor_hora * 0.5
    
    custo_mao_obra = custo_base - desconto_faltas + adicional_extras
    
    # Custo alimentação
    custo_alimentacao = db.session.query(func.coalesce(func.sum(RegistroAlimentacao.valor), 0)).filter(
        RegistroAlimentacao.funcionario_id == funcionario.id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    # Outros custos
    outros_custos = db.session.query(func.coalesce(func.sum(OutroCusto.valor), 0)).filter(
        OutroCusto.funcionario_id == funcionario.id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).scalar() or 0
    
    # Custo transporte (assumindo que vale transporte está em OutroCusto)
    custo_transporte = db.session.query(func.coalesce(func.sum(OutroCusto.valor), 0)).filter(
        OutroCusto.funcionario_id == funcionario.id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim,
        OutroCusto.tipo.ilike('%transporte%')
    ).scalar() or 0
    
    return {
        'custo_mao_obra': round(custo_mao_obra, 2),
        'custo_alimentacao': round(custo_alimentacao, 2),
        'custo_transporte': round(custo_transporte, 2),
        'outros_custos': round(outros_custos, 2)
    }


def calcular_kpis_resumo(funcionario, dados, horario_info):
    """
    Calcula KPIs resumo (linha 4: 3 KPIs)
    
    Args:
        funcionario: Objeto funcionario
        dados: Dados processados dos registros
        horario_info: Informações do horário
    
    Returns:
        dict: KPIs resumo
    """
    # Horas perdidas = faltas × horas/dia + atrasos
    horas_perdidas = (dados['faltas_nao_justificadas'] * horario_info['horas_diarias']) + dados['atrasos_total']
    
    # Eficiência = produtividade (pode ser expandido com outros fatores)
    dias_programados = dados['dias_com_lancamento']
    if dias_programados > 0:
        horas_esperadas = dias_programados * horario_info['horas_diarias']
        eficiencia = (dados['horas_trabalhadas'] / horas_esperadas) * 100 if horas_esperadas > 0 else 0
    else:
        eficiencia = 0
    
    # Valor da falta justificada = faltas justificadas × horas/dia × valor/hora
    valor_falta_justificada = dados['faltas_justificadas'] * horario_info['horas_diarias'] * horario_info['valor_hora']
    
    return {
        'horas_perdidas': round(horas_perdidas, 1),
        'eficiencia': round(eficiencia, 1),
        'valor_falta_justificada': round(valor_falta_justificada, 2)
    }