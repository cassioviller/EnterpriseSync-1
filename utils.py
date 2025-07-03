from datetime import datetime, timedelta
from models import CustoObra, RegistroPonto, RegistroAlimentacao
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

def calcular_custo_real_obra(obra_id):
    """
    Calcula o custo real total de uma obra
    """
    custos = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter(CustoObra.obra_id == obra_id).group_by(CustoObra.tipo).all()
    
    custo_total = sum(custo.total for custo in custos)
    
    # Adicionar custo de mão de obra baseado nos registros de ponto
    registros_ponto = RegistroPonto.query.filter_by(obra_id=obra_id).all()
    custo_mao_obra = 0
    
    for registro in registros_ponto:
        if registro.funcionario_ref and registro.funcionario_ref.salario:
            # Assumindo salário por hora baseado em 220 horas mensais
            salario_hora = registro.funcionario_ref.salario / 220
            custo_mao_obra += (registro.horas_trabalhadas * salario_hora)
            custo_mao_obra += (registro.horas_extras * salario_hora * 1.5)  # 50% adicional para horas extras
    
    return {
        'custos_detalhados': dict(custos),
        'custo_mao_obra': custo_mao_obra,
        'custo_total': custo_total + custo_mao_obra
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
