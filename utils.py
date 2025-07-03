from datetime import datetime, timedelta, date
from models import CustoObra, RegistroPonto, RegistroAlimentacao, CustoVeiculo
from sqlalchemy import func
from app import db

def calcular_horas_trabalhadas(hora_entrada, hora_saida, hora_almoco_saida=None, hora_almoco_retorno=None):
    """
    Calcula as horas trabalhadas e horas extras
    """
    if not hora_entrada or not hora_saida:
        return {'total': 0, 'extras': 0}
    
    # Converter para datetime para facilitar cálculos
    entrada = datetime.combine(datetime.today(), hora_entrada)
    saida = datetime.combine(datetime.today(), hora_saida)
    
    # Se saída é no dia seguinte
    if saida < entrada:
        saida += timedelta(days=1)
    
    # Calcular tempo total
    tempo_total = saida - entrada
    
    # Descontar almoço se informado
    if hora_almoco_saida and hora_almoco_retorno:
        almoco_saida = datetime.combine(datetime.today(), hora_almoco_saida)
        almoco_retorno = datetime.combine(datetime.today(), hora_almoco_retorno)
        
        if almoco_retorno < almoco_saida:
            almoco_retorno += timedelta(days=1)
        
        tempo_almoco = almoco_retorno - almoco_saida
        tempo_total -= tempo_almoco
    
    # Converter para horas decimais
    horas_trabalhadas = tempo_total.total_seconds() / 3600
    
    # Calcular horas extras (acima de 8 horas)
    horas_extras = max(0, horas_trabalhadas - 8)
    
    return {
        'total': round(horas_trabalhadas, 2),
        'extras': round(horas_extras, 2)
    }

def calcular_custo_real_obra(obra_id, data_inicio=None, data_fim=None):
    """
    Calcula o custo real total de uma obra em um período específico
    """
    # Query base para custos da obra
    query_custos = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter(CustoObra.obra_id == obra_id)
    
    # Aplicar filtros de data se fornecidos
    if data_inicio:
        query_custos = query_custos.filter(CustoObra.data >= data_inicio)
    if data_fim:
        query_custos = query_custos.filter(CustoObra.data <= data_fim)
    
    custos = query_custos.group_by(CustoObra.tipo).all()
    custo_total = sum(custo.total for custo in custos)
    
    # Adicionar custo de mão de obra baseado nos registros de ponto
    query_ponto = RegistroPonto.query.filter_by(obra_id=obra_id)
    if data_inicio:
        query_ponto = query_ponto.filter(RegistroPonto.data >= data_inicio)
    if data_fim:
        query_ponto = query_ponto.filter(RegistroPonto.data <= data_fim)
    
    registros_ponto = query_ponto.all()
    custo_mao_obra = 0
    
    for registro in registros_ponto:
        if registro.funcionario_ref and registro.funcionario_ref.salario:
            # Assumindo salário por hora baseado em 220 horas mensais
            salario_hora = registro.funcionario_ref.salario / 220
            custo_mao_obra += (registro.horas_trabalhadas * salario_hora)
            custo_mao_obra += (registro.horas_extras * salario_hora * 1.5)  # 50% adicional para horas extras
    
    # Adicionar custo de alimentação
    query_alimentacao = RegistroAlimentacao.query.filter_by(obra_id=obra_id)
    if data_inicio:
        query_alimentacao = query_alimentacao.filter(RegistroAlimentacao.data >= data_inicio)
    if data_fim:
        query_alimentacao = query_alimentacao.filter(RegistroAlimentacao.data <= data_fim)
    
    custo_alimentacao = query_alimentacao.with_entities(func.sum(RegistroAlimentacao.valor)).scalar() or 0
    
    return {
        'custos_detalhados': dict(custos),
        'custo_mao_obra': custo_mao_obra,
        'custo_alimentacao': custo_alimentacao,
        'custo_total': custo_total + custo_mao_obra + custo_alimentacao
    }

def calcular_custos_mes(data_inicio=None, data_fim=None):
    """
    Calcula custos totais do mês: alimentação + transporte + mão de obra + faltas justificadas
    """
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    if not data_fim:
        data_fim = date.today()
    
    # Custos de alimentação
    custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    # Custos de transporte (veículos)
    custo_transporte = db.session.query(func.sum(CustoVeiculo.valor)).filter(
        CustoVeiculo.data_custo >= data_inicio,
        CustoVeiculo.data_custo <= data_fim
    ).scalar() or 0
    
    # Custos de mão de obra (salários por horas trabalhadas)
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    custo_mao_obra = 0
    custo_faltas_justificadas = 0
    
    for registro in registros_ponto:
        if registro.funcionario_ref and registro.funcionario_ref.salario:
            salario_hora = registro.funcionario_ref.salario / 220
            custo_mao_obra += (registro.horas_trabalhadas * salario_hora)
            custo_mao_obra += (registro.horas_extras * salario_hora * 1.5)
            
            # Custo de faltas justificadas (empresa perde dinheiro)
            if registro.observacoes and 'falta justificada' in registro.observacoes.lower():
                custo_faltas_justificadas += salario_hora * 8  # 8 horas por dia
    
    # Outros custos operacionais
    custo_outros = db.session.query(func.sum(CustoObra.valor)).filter(
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    ).scalar() or 0
    
    return {
        'alimentacao': custo_alimentacao,
        'transporte': custo_transporte,
        'mao_obra': custo_mao_obra,
        'faltas_justificadas': custo_faltas_justificadas,
        'outros': custo_outros,
        'total': custo_alimentacao + custo_transporte + custo_mao_obra + custo_faltas_justificadas + custo_outros
    }

def formatar_cpf(cpf):
    """
    Formata CPF para exibição
    """
    if not cpf:
        return ''
    
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    
    return cpf

def formatar_cnpj(cnpj):
    """
    Formata CNPJ para exibição
    """
    if not cnpj:
        return ''
    
    # Remove caracteres não numéricos
    cnpj = ''.join(filter(str.isdigit, cnpj))
    
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    
    return cnpj

def formatar_telefone(telefone):
    """
    Formata telefone para exibição
    """
    if not telefone:
        return ''
    
    # Remove caracteres não numéricos
    telefone = ''.join(filter(str.isdigit, telefone))
    
    if len(telefone) == 11:
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    elif len(telefone) == 10:
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    
    return telefone
