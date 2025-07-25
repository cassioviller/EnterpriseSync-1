from datetime import datetime, timedelta, date, time
from sqlalchemy import func
import calendar
import os
import re
from werkzeug.utils import secure_filename
from flask import current_app

def calcular_horas_trabalhadas(hora_entrada, hora_saida, hora_almoco_saida=None, hora_almoco_retorno=None, data=None):
    """
    Calcula as horas trabalhadas e horas extras
    Considera adicional de 50% para sábados
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
    
    # Calcular horas extras
    if data and data.weekday() == 5:  # Sábado (0=segunda, 5=sábado)
        # No sábado, todas as horas são consideradas extras
        horas_extras = horas_trabalhadas
    elif data and data.weekday() == 6:  # Domingo
        # No domingo, todas as horas são consideradas extras
        horas_extras = horas_trabalhadas
    else:
        # Dias normais: extras acima de 8 horas
        horas_extras = max(0, horas_trabalhadas - 8)
    
    return {
        'total': round(horas_trabalhadas, 2),
        'extras': round(horas_extras, 2)
    }

def gerar_codigo_funcionario():
    """Gera código único para funcionário no formato VV001, VV002, etc."""
    from models import Funcionario  # Import local para evitar circular imports
    
    # Buscar o maior número entre códigos VV
    ultimo_funcionario = Funcionario.query.filter(
        Funcionario.codigo.like('VV%')
    ).order_by(Funcionario.codigo.desc()).first()
    
    if ultimo_funcionario and ultimo_funcionario.codigo:
        # Extrair número do último código (VV010 -> 010)
        numero_str = ultimo_funcionario.codigo[2:]  # Remove 'VV'
        try:
            ultimo_numero = int(numero_str)
            novo_numero = ultimo_numero + 1
        except (ValueError, TypeError):
            novo_numero = 1
    else:
        novo_numero = 1
    
    return f"VV{novo_numero:03d}"

def salvar_foto_funcionario(foto, codigo):
    """Salva foto do funcionário e retorna o nome do arquivo"""
    if not foto:
        return None
    
    # Criar diretório se não existe
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'funcionarios')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Nome seguro do arquivo
    filename = secure_filename(foto.filename)
    extensao = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    
    # Nome final: codigo_funcionario.extensao
    nome_arquivo = f"{codigo}.{extensao}"
    caminho_completo = os.path.join(upload_dir, nome_arquivo)
    
    # Salvar arquivo
    foto.save(caminho_completo)
    
    # Retornar caminho relativo para salvar no banco
    return f"uploads/funcionarios/{nome_arquivo}"

def validar_cpf(cpf):
    """Valida CPF brasileiro"""
    if not cpf:
        return False
    
    # Remove caracteres não numéricos
    cpf = re.sub(r'[^0-9]', '', cpf)
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return False
    
    # Verifica se não é uma sequência de números iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Algoritmo de validação do CPF
    def calcular_digito(cpf_parcial, peso_inicial):
        soma = sum(int(cpf_parcial[i]) * (peso_inicial - i) for i in range(len(cpf_parcial)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto
    
    # Verifica primeiro dígito
    if int(cpf[9]) != calcular_digito(cpf[:9], 10):
        return False
    
    # Verifica segundo dígito
    if int(cpf[10]) != calcular_digito(cpf[:10], 11):
        return False
    
    return True

def calcular_custo_real_obra(obra_id, data_inicio, data_fim):
    """Calcula custo real de uma obra no período"""
    from app import db
    from models import CustoObra, RegistroPonto, RegistroAlimentacao, CustoVeiculo, OutroCusto, Funcionario
    
    # Custos diretos da obra
    custos_obra = db.session.query(func.sum(CustoObra.valor)).filter(
        CustoObra.obra_id == obra_id,
        CustoObra.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Custos de mão de obra (registros de ponto relacionados à obra)
    registros_ponto = db.session.query(RegistroPonto).filter(
        RegistroPonto.obra_id == obra_id,
        RegistroPonto.data.between(data_inicio, data_fim)
    ).all()
    
    custos_mao_obra = 0
    for registro in registros_ponto:
        funcionario = db.session.query(Funcionario).get(registro.funcionario_id)
        if funcionario and funcionario.salario:
            # Calcular custo baseado em horas trabalhadas e salário
            salario_hora = funcionario.salario / 220  # 220 horas mensais
            horas = registro.horas_trabalhadas or 0
            horas_extras = registro.horas_extras or 0
            custos_mao_obra += (horas * salario_hora) + (horas_extras * salario_hora * 1.5)
    
    # Custos de alimentação
    custos_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.obra_id == obra_id,
        RegistroAlimentacao.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Custos de veículos
    custos_veiculos = db.session.query(func.sum(CustoVeiculo.valor)).filter(
        CustoVeiculo.obra_id == obra_id,
        CustoVeiculo.data_custo.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Outros custos
    outros_custos = db.session.query(func.sum(OutroCusto.valor)).filter(
        OutroCusto.obra_id == obra_id,
        OutroCusto.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    custo_total = custos_obra + custos_mao_obra + custos_alimentacao + custos_veiculos + outros_custos
    
    return {
        'custo_total': float(custo_total),
        'custos_obra': float(custos_obra),
        'custos_mao_obra': float(custos_mao_obra),
        'custos_alimentacao': float(custos_alimentacao),
        'custos_veiculos': float(custos_veiculos),
        'outros_custos': float(outros_custos)
    }

def calcular_custos_mes(admin_id, data_inicio, data_fim):
    """Calcula custos mensais por categoria para um admin"""
    from app import db
    from models import RegistroAlimentacao, CustoVeiculo, RegistroPonto, OutroCusto, Funcionario
    
    # Alimentação
    custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).join(
        RegistroAlimentacao.funcionario_ref
    ).filter(
        RegistroAlimentacao.funcionario_ref.has(admin_id=admin_id),
        RegistroAlimentacao.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Transporte (veículos) - join com veiculo para acessar admin_id
    custo_transporte = db.session.query(func.sum(CustoVeiculo.valor)).join(
        CustoVeiculo.veiculo_ref
    ).filter(
        CustoVeiculo.veiculo_ref.has(admin_id=admin_id),
        CustoVeiculo.data_custo.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Mão de obra - calcular baseado em registros de ponto
    registros_ponto = db.session.query(RegistroPonto).join(
        RegistroPonto.funcionario_ref
    ).filter(
        RegistroPonto.funcionario_ref.has(admin_id=admin_id),
        RegistroPonto.data.between(data_inicio, data_fim)
    ).all()
    
    custo_mao_obra = 0
    for registro in registros_ponto:
        funcionario = db.session.query(Funcionario).get(registro.funcionario_id)
        if funcionario and funcionario.salario:
            salario_hora = funcionario.salario / 220
            horas = registro.horas_trabalhadas or 0
            horas_extras = registro.horas_extras or 0
            custo_mao_obra += (horas * salario_hora) + (horas_extras * salario_hora * 1.5)
    
    # Outros custos
    outros_custos = db.session.query(func.sum(OutroCusto.valor)).join(
        OutroCusto.funcionario_ref
    ).filter(
        OutroCusto.funcionario_ref.has(admin_id=admin_id),
        OutroCusto.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    return {
        'alimentacao': float(custo_alimentacao),
        'transporte': float(custo_transporte),
        'mao_obra': float(custo_mao_obra),
        'outros': float(outros_custos),
        'total': float(custo_alimentacao + custo_transporte + custo_mao_obra + outros_custos)
    }

def formatar_cpf(cpf):
    """Formata CPF no padrão XXX.XXX.XXX-XX"""
    if not cpf:
        return ""
    
    # Remove caracteres não numéricos
    cpf = re.sub(r'[^0-9]', '', cpf)
    
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    
    return cpf

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
            horas_trabalhadas = registro.horas_trabalhadas or 0
            horas_extras = registro.horas_extras or 0
            custo_mao_obra += (horas_trabalhadas * salario_hora)
            custo_mao_obra += (horas_extras * salario_hora * 1.5)
            
            # Custo de faltas justificadas (empresa perde dinheiro)
            if registro.observacoes and 'falta justificada' in registro.observacoes.lower():
                custo_faltas_justificadas += salario_hora * 8  # 8 horas por dia
    
    # Outros custos (vale transporte, descontos, etc.)
    custo_outros = db.session.query(func.sum(OutroCusto.valor)).filter(
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).scalar() or 0
    
    return {
        'alimentacao': custo_alimentacao,
        'transporte': custo_transporte,
        'mao_obra': custo_mao_obra,
        'faltas_justificadas': custo_faltas_justificadas,
        'outros': custo_outros,
        'total': custo_alimentacao + custo_transporte + custo_mao_obra + custo_faltas_justificadas + custo_outros
    }

def calcular_kpis_funcionario_periodo(funcionario_id, data_inicio=None, data_fim=None):
    """
    Calcula KPIs individuais de um funcionário para um período específico
    """
    from app import db
    from models import Funcionario, RegistroPonto, RegistroAlimentacao, CustoVeiculo, UsoVeiculo
    
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    if not data_fim:
        data_fim = date.today()
    
    funcionario = Funcionario.query.get(funcionario_id)
    if not funcionario:
        return None
    
    # Registros de ponto no período
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    # Cálculo de horas trabalhadas
    total_horas_trabalhadas = 0
    total_horas_extras = 0
    dias_faltas_justificadas = 0
    custo_faltas_justificadas = 0
    
    for registro in registros_ponto:
        horas_trabalhadas = registro.horas_trabalhadas or 0
        horas_extras = registro.horas_extras or 0
        total_horas_trabalhadas += horas_trabalhadas
        total_horas_extras += horas_extras
        
        # Contar faltas justificadas
        if registro.observacoes and 'falta justificada' in registro.observacoes.lower():
            dias_faltas_justificadas += 1
            if funcionario.salario:
                salario_hora = funcionario.salario / 220
                custo_faltas_justificadas += salario_hora * 8  # 8 horas por dia
    
    # Custo de mão de obra
    custo_mao_obra = 0
    if funcionario.salario:
        salario_hora = funcionario.salario / 220
        custo_mao_obra = (total_horas_trabalhadas * salario_hora) + (total_horas_extras * salario_hora * 1.5)
    
    # Custo de alimentação
    custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.funcionario_id == funcionario_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    # Custo de transporte (baseado no uso de veículos)
    custo_transporte = 0
    usos_veiculo = UsoVeiculo.query.filter(
        UsoVeiculo.funcionario_id == funcionario_id,
        UsoVeiculo.data_uso >= data_inicio,
        UsoVeiculo.data_uso <= data_fim
    ).all()
    
    # Assumindo um custo médio por uso de veículo (pode ser refinado)
    custo_transporte = len(usos_veiculo) * 50.0  # R$ 50 por uso estimado
    
    # Custo total do funcionário
    custo_total = custo_mao_obra + custo_alimentacao + custo_transporte + custo_faltas_justificadas
    
    # Calcular dias úteis no período (segunda a sexta)
    dias_uteis = 0
    data_atual = data_inicio
    while data_atual <= data_fim:
        if data_atual.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
        data_atual = data_atual + timedelta(days=1)
    
    # Dias trabalhados (com registros de ponto)
    dias_trabalhados = len(registros_ponto)
    
    # Calcular faltas (apenas registros explícitos de falta no sistema)
    faltas = len([r for r in registros_ponto if r.tipo_registro in ['falta', 'falta_justificada']])
    
    # Calcular atrasos (número de dias com atraso)
    atrasos = len([r for r in registros_ponto if (getattr(r, 'total_atraso_horas', 0) or 0) > 0])
    
    # Calcular horas esperadas (dias úteis × 8 horas)
    horas_esperadas = dias_uteis * 8
    
    # Calcular horas perdidas (faltas × 8h + total de minutos de atraso ÷ 60)
    horas_perdidas_faltas = faltas * 8
    total_minutos_atraso = sum(getattr(r, 'total_atraso_minutos', 0) or 0 for r in registros_ponto)
    horas_perdidas_atrasos = total_minutos_atraso / 60
    horas_perdidas_total = horas_perdidas_faltas + horas_perdidas_atrasos
    
    # Taxa de absenteísmo = (horas perdidas / horas esperadas) × 100
    if horas_esperadas > 0:
        absenteismo = (horas_perdidas_total / horas_esperadas) * 100
    else:
        absenteismo = 0
    
    # Calcular média de horas diárias
    if dias_trabalhados > 0:
        media_horas_diarias = total_horas_trabalhadas / dias_trabalhados
    else:
        media_horas_diarias = 0
    
    # Calcular pontualidade (% de dias sem atraso)
    dias_sem_atraso = len([r for r in registros_ponto if (getattr(r, 'total_atraso_minutos', 0) or 0) == 0])
    if dias_trabalhados > 0:
        pontualidade = (dias_sem_atraso / dias_trabalhados) * 100
    else:
        pontualidade = 100
    
    # Calcular produtividade (% de eficiência)
    if horas_esperadas > 0:
        produtividade = (total_horas_trabalhadas / horas_esperadas) * 100
    else:
        produtividade = 0
    
    return {
        'funcionario': funcionario,
        'horas_trabalhadas': total_horas_trabalhadas,
        'horas_extras': total_horas_extras,
        'h_extras': total_horas_extras,  # Alias para compatibilidade com template
        'faltas': faltas,
        'atrasos': atrasos,
        'dias_faltas_justificadas': dias_faltas_justificadas,
        'custo_mao_obra': custo_mao_obra,
        'custo_alimentacao': custo_alimentacao,
        'custo_transporte': custo_transporte,
        'custo_faltas_justificadas': custo_faltas_justificadas,
        'custo_total': custo_total,
        'absenteismo': absenteismo,
        'produtividade': produtividade,  # Novo KPI
        'dias_uteis': dias_uteis,
        'dias_trabalhados': dias_trabalhados,
        'media_horas_diarias': media_horas_diarias,
        'media_diaria': media_horas_diarias,  # Alias para compatibilidade
        'total_atrasos': atrasos,
        'total_minutos_atraso': total_minutos_atraso,
        'horas_perdidas_total': horas_perdidas_total,
        'horas_esperadas': horas_esperadas,
        'pontualidade': pontualidade
    }

def calcular_kpis_funcionarios_geral(data_inicio=None, data_fim=None, admin_id=None):
    """
    Calcula KPIs gerais de todos os funcionários para um período
    Agora com suporte a filtro por admin_id para multi-tenant
    """
    from models import Funcionario
    from flask_login import current_user
    
    # Se admin_id não foi fornecido, usar o admin logado atual
    if admin_id is None and current_user and current_user.is_authenticated:
        admin_id = current_user.id
    
    # Filtrar funcionários pelo admin
    if admin_id:
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True, admin_id=admin_id).all()
    else:
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).all()
    
    total_funcionarios = len(funcionarios_ativos)
    total_custo_geral = 0
    total_horas_geral = 0
    total_faltas_geral = 0
    total_custo_faltas_geral = 0
    
    funcionarios_kpis = []
    
    for funcionario in funcionarios_ativos:
        kpi = calcular_kpis_funcionario_periodo(funcionario.id, data_inicio, data_fim)
        if kpi:
            funcionarios_kpis.append(kpi)
            total_custo_geral += kpi['custo_total']
            total_horas_geral += kpi['horas_trabalhadas']
            total_faltas_geral += kpi['dias_faltas_justificadas']
            total_custo_faltas_geral += kpi['custo_faltas_justificadas']
    
    return {
        'total_funcionarios': total_funcionarios,
        'total_custo_geral': total_custo_geral,
        'total_horas_geral': total_horas_geral,
        'total_faltas_geral': total_faltas_geral,
        'total_custo_faltas_geral': total_custo_faltas_geral,
        'funcionarios_kpis': funcionarios_kpis
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

def gerar_dias_uteis_mes(ano, mes):
    """
    Gera lista de dias úteis (segunda a sexta) do mês
    """
    dias_uteis = []
    cal = calendar.monthcalendar(ano, mes)
    
    for semana in cal:
        for dia_semana, dia in enumerate(semana):
            if dia > 0 and dia_semana < 5:  # Segunda a sexta (0-4)
                dias_uteis.append(date(ano, mes, dia))
    
    return dias_uteis

def calcular_ocorrencias_funcionario(funcionario_id, ano, mes):
    """
    Calcula faltas, atrasos e meio período baseado apenas nos registros reais existentes:
    - Faltas: registros com linhas completamente vazias (como nas imagens)
    - Atrasos: chegada após 08:10 (10 min tolerância)
    - Meio período: saída antes de 16:30 (30 min tolerância)
    """
    # Buscar funcionário e horário padrão
    funcionario = Funcionario.query.filter_by(id=funcionario_id).first()
    if not funcionario:
        return {
            'faltas': 0,
            'atrasos': 0,
            'meio_periodo': 0,
            'total_minutos_atraso': 0,
            'total_horas_perdidas': 0
        }
    
    # Horário padrão (08:00 - 17:00 com 1h almoço)
    horario_entrada_padrao = time(8, 0)
    horario_saida_padrao = time(17, 0)
    tolerancia_minutos = 10  # 10 minutos de tolerância
    
    # Buscar TODOS os registros do mês (incluindo os vazios)
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        func.extract('year', RegistroPonto.data) == ano,
        func.extract('month', RegistroPonto.data) == mes
    ).all()
    
    faltas = 0
    atrasos = 0
    meio_periodo = 0
    total_minutos_atraso = 0
    total_horas_perdidas = 0
    
    # Iterar apenas sobre os registros que existem no banco
    for registro in registros:
        # SITUAÇÃO 1: Linha completamente vazia (como nas imagens: 30/06, 23/06, 19/06)
        if (not registro.hora_entrada and not registro.hora_saida and 
            not registro.hora_almoco_saida and not registro.hora_almoco_retorno):
            faltas += 1
            total_horas_perdidas += 8.0
            continue
            
        # SITUAÇÃO 2: Registro incompleto (tem data mas sem entrada/saída)
        if not registro.hora_entrada or not registro.hora_saida:
            faltas += 1
            total_horas_perdidas += 8.0
            continue
        
        # SITUAÇÃO 3: Verificar ATRASO
        entrada_real = registro.hora_entrada
        entrada_padrao_datetime = datetime.combine(registro.data, horario_entrada_padrao)
        entrada_real_datetime = datetime.combine(registro.data, entrada_real)
        
        minutos_atraso = (entrada_real_datetime - entrada_padrao_datetime).total_seconds() / 60
        
        if minutos_atraso > tolerancia_minutos:
            atrasos += 1
            total_minutos_atraso += minutos_atraso
            # Horas perdidas por atraso
            total_horas_perdidas += minutos_atraso / 60
        
        # SITUAÇÃO 4: Verificar MEIO PERÍODO / SAÍDA ANTECIPADA
        saida_real = registro.hora_saida
        saida_padrao_datetime = datetime.combine(registro.data, horario_saida_padrao)
        saida_real_datetime = datetime.combine(registro.data, saida_real)
        
        # Se saiu antes do horário (mais de 30 minutos)
        minutos_saida_antecipada = (saida_padrao_datetime - saida_real_datetime).total_seconds() / 60
        
        if minutos_saida_antecipada > 30:  # Mais de 30 minutos = meio período
            meio_periodo += 1
            # Calcular horas perdidas
            horas_perdidas_saida = minutos_saida_antecipada / 60
            total_horas_perdidas += horas_perdidas_saida
    
    return {
        'faltas': faltas,
        'atrasos': atrasos,
        'meio_periodo': meio_periodo,
        'total_minutos_atraso': total_minutos_atraso,
        'total_horas_perdidas': total_horas_perdidas,
        'detalhes': {
            'horas_perdidas_faltas': faltas * 8.0,
            'horas_perdidas_atrasos': total_minutos_atraso / 60,
            'horas_perdidas_meio_periodo': total_horas_perdidas - (faltas * 8.0) - (total_minutos_atraso / 60)
        }
    }

def calcular_kpis_funcionario_completo(funcionario_id, ano=None, mes=None):
    """
    Calcula KPIs completos com detecção automática de faltas, atrasos e meio período
    """
    if not ano or not mes:
        hoje = datetime.now()
        ano = hoje.year
        mes = hoje.month
    
    # Calcular ocorrências
    ocorrencias = calcular_ocorrencias_funcionario(funcionario_id, ano, mes)
    
    # Buscar dados de horas trabalhadas
    registros_query = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        func.extract('year', RegistroPonto.data) == ano,
        func.extract('month', RegistroPonto.data) == mes,
        RegistroPonto.hora_entrada.isnot(None),
        RegistroPonto.hora_saida.isnot(None)
    ).all()
    
    total_horas_trabalhadas = 0
    total_horas_extras = 0
    dias_trabalhados = len(registros_query)
    
    for registro in registros_query:
        if registro.horas_trabalhadas:
            total_horas_trabalhadas += registro.horas_trabalhadas
        if registro.horas_extras:
            total_horas_extras += registro.horas_extras
    
    # Calcular horas esperadas do mês (dias úteis x 8h)
    dias_uteis = gerar_dias_uteis_mes(ano, mes)
    horas_esperadas = len(dias_uteis) * 8.0
    
    # Calcular absenteísmo
    absenteismo = 0.0
    if horas_esperadas > 0:
        absenteismo = (ocorrencias['total_horas_perdidas'] / horas_esperadas) * 100
    
    # Calcular média diária
    media_diaria = 0.0
    if dias_trabalhados > 0:
        media_diaria = total_horas_trabalhadas / dias_trabalhados
    
    return {
        'horas_trabalhadas': total_horas_trabalhadas,
        'horas_extras': total_horas_extras,
        'faltas': ocorrencias['faltas'],
        'atrasos': ocorrencias['atrasos'],
        'meio_periodo': ocorrencias['meio_periodo'],
        'absenteismo': round(absenteismo, 1),
        'media_diaria': round(media_diaria, 1),
        'dias_trabalhados': dias_trabalhados,
        'horas_esperadas': horas_esperadas,
        'horas_perdidas_total': ocorrencias['total_horas_perdidas'],
        'total_minutos_atraso': ocorrencias['total_minutos_atraso'],
        'detalhes': ocorrencias['detalhes']
    }

def processar_meio_periodo_exemplo():
    """
    Exemplo da lógica de meio período conforme a imagem:
    Dia 12/06: Funcionário trabalhou 08:00-14:30 = 6.5h (descontando 1h almoço)
    Horas perdidas = 8h - 6.5h = 1.5h
    """
    # Exemplo prático
    entrada = time(8, 0)      # 08:00
    saida = time(14, 30)      # 14:30
    almoco = 1.0              # 1 hora de almoço
    
    # Calcular horas trabalhadas
    entrada_dt = datetime.combine(date.today(), entrada)
    saida_dt = datetime.combine(date.today(), saida)
    
    total_minutos = (saida_dt - entrada_dt).total_seconds() / 60
    horas_trabalhadas = (total_minutos - (almoco * 60)) / 60
    
    jornada_padrao = 8.0
    horas_perdidas = jornada_padrao - horas_trabalhadas
    
    return {
        'entrada': entrada.strftime('%H:%M'),
        'saida': saida.strftime('%H:%M'),
        'horas_trabalhadas': horas_trabalhadas,
        'horas_perdidas': horas_perdidas,
        'situacao': 'Meio Período' if horas_perdidas > 0.5 else 'Normal'
    }
