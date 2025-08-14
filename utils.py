from models import db
from datetime import datetime, timedelta, date, time
from sqlalchemy import func
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import calendar
import os
import re
from werkzeug.utils import secure_filename
from flask import current_app

def _round2(x: float) -> float:
    """Arredondar para 2 casas decimais (meio para cima)"""
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _particionar_semanas(inicio: date, fim: date, semana_comeca_em: str = "domingo"):
    """Particiona período em semanas (domingo-sábado por padrão)"""
    semanas = []
    cur = inicio
    
    # Alinhar início conforme configuração
    if semana_comeca_em == "domingo":
        # Ir para o domingo anterior/igual
        cur -= timedelta(days=(cur.weekday() + 1) % 7)
    else:  # segunda-feira
        cur -= timedelta(days=cur.weekday())
    
    while cur <= fim:
        ini_sem = cur
        fim_sem = cur + timedelta(days=6)
        
        semanas.append((max(ini_sem, inicio), min(fim_sem, fim)))
        cur = fim_sem + timedelta(days=1)
    
    return semanas

def calcular_dsr_modo_estrito(salario_mensal: float, registros_faltas, data_inicio: date, data_fim: date, horas_dia_padrao: float = 8.8):
    """
    Calcula DSR em modo estrito (Lei 605/49) - semana a semana
    Retorna desconto por faltas + DSRs perdidos por semana
    """
    if salario_mensal <= 0 or horas_dia_padrao <= 0:
        return {"desconto_total": 0, "faltas_total": 0, "semanas_com_perda": 0}
    
    valor_dia = salario_mensal / 30.0
    
    # Indexar faltas injustificadas por data
    injust_por_dia = defaultdict(float)
    for registro in registros_faltas:
        if registro.tipo_registro != 'falta':  # Só faltas injustificadas
            continue
        if registro.data < data_inicio or registro.data > data_fim:
            continue
        
        # Assumir falta de dia inteiro (pode ser expandido para frações)
        injust_por_dia[registro.data] = 1.0
    
    # Particionar em semanas (domingo-sábado)
    semanas = _particionar_semanas(data_inicio, data_fim, "domingo")
    
    faltas_injustificadas_total = 0.0
    semanas_com_perda_dsr = 0
    
    for (ini_sem, fim_sem) in semanas:
        soma_semana = 0.0
        data_atual = ini_sem
        
        while data_atual <= fim_sem:
            soma_semana += injust_por_dia.get(data_atual, 0.0)
            data_atual += timedelta(days=1)
        
        # Se houve falta na semana, perde DSR
        if soma_semana > 0:
            semanas_com_perda_dsr += 1
        
        faltas_injustificadas_total += soma_semana
    
    desconto_por_faltas = _round2(valor_dia * faltas_injustificadas_total)
    desconto_por_dsr = _round2(valor_dia * semanas_com_perda_dsr)
    desconto_total = _round2(desconto_por_faltas + desconto_por_dsr)
    
    return {
        "desconto_total": desconto_total,
        "desconto_por_faltas": desconto_por_faltas,
        "desconto_por_dsr": desconto_por_dsr,
        "faltas_total": _round2(faltas_injustificadas_total),
        "semanas_com_perda": semanas_com_perda_dsr,
        "valor_dia": _round2(valor_dia)
    }

def calcular_horas_trabalhadas(hora_entrada, hora_saida, hora_almoco_saida=None, hora_almoco_retorno=None, data=None):
    """
    Calcula as horas trabalhadas e horas extras baseado no horário real de trabalho
    
    HORÁRIO PADRÃO: 7h12 às 17h (9h48min no local, menos 1h almoço = 8h48min = 8.8h efetivas)
    
    Regras de horas extras:
    - Dias normais: acima de 8.8h efetivas (50% adicional)
    - Sábados: todas as horas são extras (50% adicional)
    - Domingos/Feriados: todas as horas são extras (100% adicional)
    """
    if not hora_entrada or not hora_saida:
        return {'total': 0, 'extras': 0}
    
    # Converter para datetime para facilitar cálculos
    entrada = datetime.combine(datetime.today(), hora_entrada)
    saida = datetime.combine(datetime.today(), hora_saida)
    
    # Se saída é no dia seguinte
    if saida < entrada:
        saida += timedelta(days=1)
    
    # Calcular tempo total no local
    tempo_total = saida - entrada
    
    # Descontar almoço se informado
    if hora_almoco_saida and hora_almoco_retorno:
        almoco_saida = datetime.combine(datetime.today(), hora_almoco_saida)
        almoco_retorno = datetime.combine(datetime.today(), hora_almoco_retorno)
        
        if almoco_retorno < almoco_saida:
            almoco_retorno += timedelta(days=1)
        
        tempo_almoco = almoco_retorno - almoco_saida
        tempo_total -= tempo_almoco
    
    # Converter para horas decimais (tempo efetivo de trabalho)
    horas_trabalhadas = tempo_total.total_seconds() / 3600
    
    # ATENÇÃO: Esta função foi substituída pela lógica consolidada
    # Usar apenas para referência. A lógica real está em kpis_engine.py
    # HORÁRIO PADRÃO: 07:12-17:00 para todos os funcionários
    
    # Calcular horas extras baseado na nova lógica consolidada
    if data and data.weekday() == 5:  # Sábado
        horas_extras = horas_trabalhadas  # Todas as horas são extras (50%)
    elif data and data.weekday() == 6:  # Domingo
        horas_extras = horas_trabalhadas  # Todas as horas são extras (100%)
    else:
        # Dias normais: usar lógica de entrada antecipada + saída posterior
        # Esta função é mantida para compatibilidade, mas a lógica real
        # está implementada em kpis_engine.py com base no horário individual
        horas_extras = max(0, horas_trabalhadas - 8.8)
    
    return {
        'total': round(horas_trabalhadas, 2),
        'extras': round(horas_extras, 2)
    }

def calcular_valor_hora_corrigido(funcionario):
    """
    Calcula o valor/hora correto baseado no horário de trabalho do funcionário
    
    FÓRMULA CORRIGIDA:
    - Se funcionário tem horário cadastrado: usar horas_diarias do horário
    - Se não tem horário: usar padrão 8.8h (7h12-17h com 1h almoço)  
    - valor_hora = salario_mensal / horas_mensais_reais
    """
    if not funcionario or not funcionario.salario:
        return 0.0
    
    from calendar import monthrange
    
    # Data atual para cálculo
    hoje = datetime.now().date()
    
    # Calcular dias úteis do mês atual
    ano = hoje.year
    mes = hoje.month
    
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = hoje.replace(day=dia)
        # 0=segunda, 1=terça, ..., 6=domingo
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    # Determinar horas diárias baseado no horário do funcionário
    if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
        horas_diarias = float(funcionario.horario_trabalho.horas_diarias)
    else:
        # Padrão: 7h12-17h = 9h48min - 1h almoço = 8h48min = 8.8h
        horas_diarias = 8.8
    
    # Horas mensais reais = dias_úteis × horas_diarias
    horas_mensais_reais = dias_uteis * horas_diarias
    
    # Valor/hora = salário ÷ horas mensais reais
    if horas_mensais_reais > 0:
        valor_hora = float(funcionario.salario) / horas_mensais_reais
    else:
        valor_hora = 0.0
    
    return round(valor_hora, 2)

def calcular_valor_hora_periodo(funcionario, data_inicio, data_fim):
    """
    Calcula o valor/hora baseado no período específico (mês dos dados)
    
    CORREÇÃO: Em vez de usar mês atual (agosto), usa o mês do período analisado
    """
    if not funcionario or not funcionario.salario:
        return 0.0
    
    from calendar import monthrange
    
    # Usar o mês do período analisado (não o mês atual!)
    data_ref = data_inicio if data_inicio else datetime.now().date()
    ano = data_ref.year
    mes = data_ref.month
    
    # Calcular dias úteis do mês do período
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = data_ref.replace(day=dia)
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    # Determinar horas diárias
    if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
        horas_diarias = float(funcionario.horario_trabalho.horas_diarias)
    else:
        horas_diarias = 8.8
    
    # Horas mensais do período específico
    horas_mensais_reais = dias_uteis * horas_diarias
    
    # Valor/hora baseado no período
    if horas_mensais_reais > 0:
        valor_hora = float(funcionario.salario) / horas_mensais_reais
    else:
        valor_hora = 0.0
    
    return round(valor_hora, 2)

def calcular_custos_salariais_completos(funcionario_id, data_inicio, data_fim):
    """
    Calcula todos os custos salariais baseado na lógica correta:
    
    1. Horas normais: valor_hora × horas
    2. Horas extras dias úteis: valor_hora × 1.5 × horas_extras
    3. Horas extras sábados: valor_hora × 1.5 × horas_extras  
    4. Horas extras domingos/feriados: valor_hora × 2.0 × horas_extras
    5. Faltas justificadas: valor_hora × 8.8h (dia pago)
    6. Faltas injustificadas: -valor_hora × 8.8h (desconto)
    7. Atrasos: -valor_hora × horas_atraso (desconto proporcional)
    """
    
    funcionario = Funcionario.query.get(funcionario_id)
    if not funcionario:
        return {
            'custo_total': 0.0,
            'valor_hora': 0.0,
            'detalhamento': {}
        }
    
    # Calcular valor/hora correto
    valor_hora = calcular_valor_hora_corrigido(funcionario)
    
    # Buscar registros do período
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    # Inicializar contadores
    custo_horas_normais = 0.0
    custo_extras_50 = 0.0  # Dias úteis e sábados
    custo_extras_100 = 0.0  # Domingos e feriados
    custo_faltas_justificadas = 0.0
    desconto_faltas_injustificadas = 0.0
    desconto_atrasos = 0.0
    
    for registro in registros:
        tipo = registro.tipo_registro or 'trabalho_normal'
        
        # HORAS NORMAIS E EXTRAS
        if registro.horas_trabalhadas and registro.horas_trabalhadas > 0:
            horas_trab = float(registro.horas_trabalhadas)
            horas_extras = float(registro.horas_extras or 0)
            
            if tipo in ['trabalho_normal', 'trabalhado']:
                # Dia normal: até 8.8h normais, resto extras 50%
                horas_normais = min(horas_trab - horas_extras, 8.8)
                custo_horas_normais += valor_hora * horas_normais
                
                if horas_extras > 0:
                    custo_extras_50 += valor_hora * 1.5 * horas_extras
                    
            elif tipo == 'sabado_horas_extras':
                # Sábado: todas extras 50%
                custo_extras_50 += valor_hora * 1.5 * horas_trab
                
            elif tipo in ['domingo_horas_extras', 'feriado_trabalhado']:
                # Domingo/Feriado: todas extras 100%
                custo_extras_100 += valor_hora * 2.0 * horas_trab
        
        # FALTAS JUSTIFICADAS (pagar dia completo)
        if tipo == 'falta_justificada':
            custo_faltas_justificadas += valor_hora * 8.8
        
        # FALTAS INJUSTIFICADAS (descontar dia)
        elif tipo == 'falta':
            desconto_faltas_injustificadas += valor_hora * 8.8
        
        # ATRASOS (desconto proporcional)
        if registro.total_atraso_horas and registro.total_atraso_horas > 0:
            desconto_atrasos += valor_hora * float(registro.total_atraso_horas)
    
    # CUSTO TOTAL
    custo_total = (
        custo_horas_normais + 
        custo_extras_50 + 
        custo_extras_100 + 
        custo_faltas_justificadas - 
        desconto_faltas_injustificadas - 
        desconto_atrasos
    )
    
    return {
        'custo_total': round(custo_total, 2),
        'valor_hora': valor_hora,
        'detalhamento': {
            'horas_normais': round(custo_horas_normais, 2),
            'extras_50': round(custo_extras_50, 2),
            'extras_100': round(custo_extras_100, 2),
            'faltas_justificadas': round(custo_faltas_justificadas, 2),
            'desconto_faltas': round(desconto_faltas_injustificadas, 2),
            'desconto_atrasos': round(desconto_atrasos, 2)
        }
    }

def gerar_codigo_funcionario():
    """Gera código único para funcionário no formato VV001, VV002, etc."""
    
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
    """Salva foto do funcionário como base64 e arquivo, retorna o nome do arquivo e base64"""
    if not foto:
        return None, None
    
    import base64
    import io
    from PIL import Image
    
    try:
        # Ler dados da foto
        foto.seek(0)
        foto_data = foto.read()
        
        # Criar diretório se não existe
        upload_dir = os.path.join(current_app.static_folder, 'uploads', 'funcionarios')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Nome seguro do arquivo
        filename = secure_filename(foto.filename)
        extensao = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
        
        # Redimensionar imagem para economizar espaço
        image = Image.open(io.BytesIO(foto_data))
        image = image.convert('RGB')  # Converter para RGB se necessário
        
        # Redimensionar para máximo 200x200 pixels mantendo proporção
        image.thumbnail((200, 200), Image.Resampling.LANCZOS)
        
        # Salvar como JPEG otimizado
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='JPEG', quality=85, optimize=True)
        img_buffer.seek(0)
        foto_otimizada = img_buffer.getvalue()
        
        # Converter para base64
        foto_base64 = base64.b64encode(foto_otimizada).decode('utf-8')
        foto_base64_completo = f"data:image/jpeg;base64,{foto_base64}"
        
        # Nome final: codigo_funcionario.jpg (sempre JPG para consistência)
        nome_arquivo = f"{codigo}.jpg"
        caminho_completo = os.path.join(upload_dir, nome_arquivo)
        
        # Salvar arquivo físico (para fallback)
        with open(caminho_completo, 'wb') as f:
            f.write(foto_otimizada)
        
        # Retornar caminho relativo e base64
        return f"uploads/funcionarios/{nome_arquivo}", foto_base64_completo
        
    except Exception as e:
        print(f"Erro ao processar foto: {e}")
        return None, None

def obter_foto_funcionario(funcionario):
    """Retorna a foto do funcionário: base64 primeiro, depois arquivo, ou avatar SVG gerado"""
    if funcionario.foto_base64:
        return funcionario.foto_base64
    
    if funcionario.foto and os.path.exists(os.path.join('static', funcionario.foto)):
        return url_for('static', filename=funcionario.foto)
    
    # Gerar avatar SVG como fallback
    import hashlib
    hash_nome = hashlib.md5(funcionario.nome.encode()).hexdigest()
    cor_fundo = f"#{hash_nome[:6]}"
    
    palavras = funcionario.nome.split()
    iniciais = ""
    if len(palavras) >= 2:
        iniciais = palavras[0][0] + palavras[-1][0]
    else:
        iniciais = palavras[0][:2] if palavras else "??"
    
    svg_content = f'''<svg width="120" height="120" viewBox="0 0 120 120" style="background-color: {cor_fundo}; border-radius: 50%;">
  <text x="60" y="70" font-family="Arial, sans-serif" font-size="40" font-weight="bold" 
        text-anchor="middle" fill="white">{iniciais.upper()}</text>
</svg>'''
    
    import base64
    svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{svg_base64}"

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

def calcular_valor_hora_funcionario(funcionario, data_referencia):
    """
    Calcular valor hora do funcionário baseado em dias úteis reais do mês
    
    Args:
        funcionario: Instância do modelo Funcionario
        data_referencia: datetime.date do mês de referência
    
    Returns:
        float: Valor da hora normal do funcionário
    """
    from calendar import monthrange
    
    if not funcionario.salario:
        return 0.0
    
    # Calcular dias úteis reais do mês
    ano = data_referencia.year
    mes = data_referencia.month
    
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = data_referencia.replace(day=dia)
        # 0=segunda, 1=terça, ..., 6=domingo
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    # Usar horário específico do funcionário
    if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
        horas_diarias = funcionario.horario_trabalho.horas_diarias
    else:
        horas_diarias = 8.8  # Padrão baseado no horário Carlos Alberto
    
    # Horas mensais = horas/dia × dias úteis do mês
    horas_mensais = horas_diarias * dias_uteis
    
    return funcionario.salario / horas_mensais if horas_mensais > 0 else 0.0

def calcular_custos_mes(admin_id, data_inicio, data_fim):
    """Calcula custos mensais por categoria para um admin"""
    
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
        
        # Contar custo de faltas justificadas
        if registro.tipo_registro == 'falta_justificada' and funcionario.salario:
            salario_hora = funcionario.salario / 220
            custo_faltas_justificadas += salario_hora * 8  # 8 horas por dia
    
    # Calcular valor das horas extras com percentual correto da CLT
    valor_horas_extras = 0.0
    if funcionario.salario:
        # Usar função corrigida que calcula baseado no período específico
        valor_hora_base = calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
        
        # Calcular valor total das horas extras por tipo de registro  
        for registro in registros_ponto:
            if registro.horas_extras and registro.horas_extras > 0:
                # Multiplicador conforme legislação brasileira (CLT)
                if registro.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                    multiplicador = 2.0  # 100% adicional
                else:
                    multiplicador = 1.5  # 50% adicional padrão
                
                valor_extras_registro = registro.horas_extras * valor_hora_base * multiplicador
                valor_horas_extras += valor_extras_registro
    
    # Custo de mão de obra
    custo_mao_obra = 0
    if funcionario.salario:
        salario_base = funcionario.salario
        custo_mao_obra = salario_base + valor_horas_extras
    
    # CORRIGIDO: Usar nova lógica com kpi_associado
    
    # Custo de alimentação (RegistroAlimentacao + OutroCusto com kpi_associado='custo_alimentacao')
    custo_alimentacao_registro = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.funcionario_id == funcionario_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    custo_alimentacao_outro = db.session.query(func.sum(OutroCusto.valor)).filter(
        OutroCusto.funcionario_id == funcionario_id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim,
        OutroCusto.kpi_associado == 'custo_alimentacao'
    ).scalar() or 0
    
    custo_alimentacao = custo_alimentacao_registro + custo_alimentacao_outro
    
    # Custo de transporte (OutroCusto com kpi_associado='custo_transporte')
    custo_transporte = db.session.query(func.sum(OutroCusto.valor)).filter(
        OutroCusto.funcionario_id == funcionario_id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim,
        OutroCusto.kpi_associado == 'custo_transporte'
    ).scalar() or 0
    
    # Outros custos (OutroCusto com kpi_associado='outros_custos')
    outros_custos = db.session.query(func.sum(OutroCusto.valor)).filter(
        OutroCusto.funcionario_id == funcionario_id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim,
        OutroCusto.kpi_associado == 'outros_custos'
    ).scalar() or 0
    
    # Custo total do funcionário
    custo_total = custo_mao_obra + custo_alimentacao + custo_transporte + outros_custos + custo_faltas_justificadas
    
    # Calcular dias úteis no período (segunda a sexta)
    dias_uteis = 0
    data_atual = data_inicio
    while data_atual <= data_fim:
        if data_atual.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
        data_atual = data_atual + timedelta(days=1)
    
    # Dias trabalhados (apenas registros de trabalho efetivo)
    dias_trabalhados = len([r for r in registros_ponto if r.tipo_registro not in ['falta', 'falta_justificada']])
    
    # Calcular faltas normais (não justificadas)
    faltas = len([r for r in registros_ponto if r.tipo_registro == 'falta'])
    
    # Calcular valor monetário das faltas com DSR (Lei 605/49 + CLT)
    valor_faltas = 0.0
    valor_dia = 0.0

    semanas_com_falta = 0
    
    if faltas > 0 and funcionario.salario:
        valor_dia = funcionario.salario / 30  # Valor do dia
        
        # CÁLCULO DE FALTAS INJUSTIFICADAS - MODO ESTRITO (Lei 605/49)
        # Análise semana a semana conforme legislação brasileira
        registros_faltas = [r for r in registros_ponto if r.tipo_registro == 'falta']
        dsr_estrito = calcular_dsr_modo_estrito(funcionario.salario, registros_faltas, data_inicio, data_fim)
        valor_faltas = dsr_estrito["desconto_total"]
        semanas_com_falta = dsr_estrito["semanas_com_perda"]
    
    # Calcular faltas justificadas (já contado no loop acima, mas vamos recalcular para garantir)
    dias_faltas_justificadas = len([r for r in registros_ponto if r.tipo_registro == 'falta_justificada'])
    
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
    
    # Calcular média de horas diárias baseada em dias úteis
    # Se não faltou nem atrasou, deve dar próximo de 8.8h
    if dias_uteis > 0:
        media_horas_diarias = total_horas_trabalhadas / dias_uteis
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
        'valor_horas_extras': valor_horas_extras,  # Valor monetário das horas extras
        'valor_hora_atual': valor_hora_base,  # Valor hora atual do funcionário
        'faltas': faltas,
        'valor_faltas': valor_faltas,  # Método estrito Lei 605/49 (DSR semana a semana)
        'valor_dia': valor_dia,  # Valor do dia para transparência
        'semanas_com_falta': semanas_com_falta,  # Semanas que perderam DSR
        'atrasos': atrasos,
        'dias_faltas_justificadas': dias_faltas_justificadas,
        'custo_mao_obra': custo_mao_obra,
        'custo_alimentacao': custo_alimentacao,
        'custo_transporte': custo_transporte,
        'outros_custos': outros_custos,
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

def calcular_kpis_funcionarios_geral(data_inicio=None, data_fim=None, admin_id=None, incluir_inativos=False):
    """
    Calcula KPIs gerais de todos os funcionários para um período
    Agora com suporte a filtro por admin_id para multi-tenant
    
    Args:
        data_inicio: Data inicial do período
        data_fim: Data final do período
        admin_id: ID do admin para filtrar funcionários
        incluir_inativos: Se True, inclui funcionários inativos (padrão: False)
    """
    from flask_login import current_user
    
    # Se admin_id não foi fornecido, usar o admin logado atual
    if admin_id is None and current_user and current_user.is_authenticated:
        admin_id = current_user.id
    
    # NOVA LÓGICA: Incluir funcionários inativos que têm registros no período
    # Funcionários ativos são sempre incluídos
    # Funcionários inativos são incluídos apenas se tiverem registros no período filtrado
    
    from sqlalchemy import or_
    
    if admin_id:
        # Buscar funcionários ativos
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True, admin_id=admin_id).all()
        
        # Se há filtro de período, incluir inativos com registros no período
        if data_inicio and data_fim and not incluir_inativos:
            # Buscar funcionários inativos que têm registros no período
            funcionarios_com_registros = db.session.query(Funcionario).join(RegistroPonto).filter(
                Funcionario.admin_id == admin_id,
                Funcionario.ativo == False,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim
            ).distinct().all()
            
            funcionarios = funcionarios_ativos + funcionarios_com_registros
        elif incluir_inativos:
            funcionarios = Funcionario.query.filter_by(admin_id=admin_id).all()
        else:
            funcionarios = funcionarios_ativos
    else:
        # Mesma lógica para super admin
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).all()
        
        if data_inicio and data_fim and not incluir_inativos:
            funcionarios_com_registros = db.session.query(Funcionario).join(RegistroPonto).filter(
                Funcionario.ativo == False,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim
            ).distinct().all()
            
            funcionarios = funcionarios_ativos + funcionarios_com_registros
        elif incluir_inativos:
            funcionarios = Funcionario.query.all()
        else:
            funcionarios = funcionarios_ativos
    
    # Ordenar por nome
    funcionarios = sorted(funcionarios, key=lambda f: f.nome)
    
    # Para compatibilidade, manter nome da variável  
    funcionarios_ativos = funcionarios
    
    total_funcionarios = len(funcionarios_ativos)
    total_custo_geral = 0
    total_horas_geral = 0
    total_faltas_geral = 0
    total_faltas_justificadas_geral = 0
    total_custo_faltas_geral = 0
    total_dias_uteis = 0
    total_dias_trabalhados = 0
    
    funcionarios_kpis = []
    
    for funcionario in funcionarios_ativos:
        # NOVA LÓGICA: Processar funcionários ativos + inativos com registros no período
        # Não pular mais funcionários inativos que têm dados relevantes
            
        kpi = calcular_kpis_funcionario_periodo(funcionario.id, data_inicio, data_fim)
        if kpi:
            funcionarios_kpis.append(kpi)
            total_custo_geral += kpi['custo_total']
            total_horas_geral += kpi['horas_trabalhadas']
            total_faltas_geral += kpi['faltas']  # Faltas normais
            total_faltas_justificadas_geral += kpi['dias_faltas_justificadas']  # Faltas justificadas
            total_custo_faltas_geral += kpi['custo_faltas_justificadas']
            total_dias_uteis += kpi['dias_uteis']
            total_dias_trabalhados += kpi['dias_trabalhados']
    
    # Calcular taxa de absenteísmo geral (baseado no total de faltas)
    
    # CORREÇÃO: Filtrar registros apenas de funcionários ativos
    funcionarios_para_calculo = [f for f in funcionarios_ativos if incluir_inativos or f.ativo]
    total_dias_com_registros = sum(len(RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == f.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()) for f in funcionarios_para_calculo)
    
    total_faltas_todas = total_faltas_geral + total_faltas_justificadas_geral
    
    if total_dias_com_registros > 0:
        taxa_absenteismo_geral = (total_faltas_todas / total_dias_com_registros) * 100
    else:
        taxa_absenteismo_geral = 0.0
    
    return {
        'total_funcionarios': total_funcionarios,
        'total_custo_geral': total_custo_geral,
        'total_horas_geral': total_horas_geral,
        'total_faltas_geral': total_faltas_geral,  # Faltas normais
        'total_faltas_justificadas_geral': total_faltas_justificadas_geral,  # Faltas justificadas
        'total_custo_faltas_geral': total_custo_faltas_geral,
        'taxa_absenteismo_geral': taxa_absenteismo_geral,  # Taxa de absenteísmo
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
