from models import db
# ===== SISTEMA DE CÓDIGO DE BARRAS AVANÇADO - CONFORME REUNIÃO TÉCNICA =====

import re
from models import Produto, CategoriaProduto
import random
import string
from datetime import datetime
import base64
import io

# Imports opcionais para funcionalidades avançadas
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

# ===== VALIDAÇÃO DE CÓDIGOS DE BARRAS =====

def validar_codigo_barras(codigo):
    """Validar código de barras EAN-13, EAN-8, Code-128, QR Code"""
    if not codigo or len(codigo.strip()) == 0:
        return {'valido': False, 'erro': 'Código vazio'}
    
    # Limpar código
    codigo = re.sub(r'[^0-9A-Za-z]', '', codigo.strip())
    
    # EAN-13 (13 dígitos)
    if len(codigo) == 13 and codigo.isdigit():
        return validar_ean13(codigo)
    
    # EAN-8 (8 dígitos)
    elif len(codigo) == 8 and codigo.isdigit():
        return validar_ean8(codigo)
    
    # Code-128 ou QR Code (alfanumérico, 4-50 caracteres)
    elif 4 <= len(codigo) <= 50:
        return {'valido': True, 'tipo': 'CODE128', 'codigo': codigo}
    
    return {'valido': False, 'erro': f'Formato inválido. Tamanho: {len(codigo)}'}

def validar_ean13(codigo):
    """Validar EAN-13 com dígito verificador"""
    try:
        # Calcular dígito verificador
        soma = 0
        for i in range(12):
            peso = 1 if i % 2 == 0 else 3
            soma += int(codigo[i]) * peso
        
        digito_verificador = (10 - (soma % 10)) % 10
        
        if int(codigo[12]) == digito_verificador:
            return {'valido': True, 'tipo': 'EAN13', 'codigo': codigo}
        else:
            return {'valido': False, 'erro': 'Dígito verificador inválido'}
            
    except (ValueError, IndexError):
        return {'valido': False, 'erro': 'Erro no cálculo do dígito verificador'}

def validar_ean8(codigo):
    """Validar EAN-8 com dígito verificador"""
    try:
        # Calcular dígito verificador
        soma = 0
        for i in range(7):
            peso = 3 if i % 2 == 0 else 1
            soma += int(codigo[i]) * peso
        
        digito_verificador = (10 - (soma % 10)) % 10
        
        if int(codigo[7]) == digito_verificador:
            return {'valido': True, 'tipo': 'EAN8', 'codigo': codigo}
        else:
            return {'valido': False, 'erro': 'Dígito verificador inválido'}
            
    except (ValueError, IndexError):
        return {'valido': False, 'erro': 'Erro no cálculo do dígito verificador'}

# ===== GERAÇÃO DE CÓDIGOS INTERNOS =====

def gerar_codigo_interno(admin_id, categoria_codigo=None):
    """Gerar código interno único baseado em categoria"""
    if not categoria_codigo:
        categoria_codigo = "PRD"
    
    # Buscar último código da categoria
    ultimo_produto = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.codigo_interno.like(f'{categoria_codigo}%')
    ).order_by(Produto.codigo_interno.desc()).first()
    
    if ultimo_produto and len(ultimo_produto.codigo_interno) >= 6:
        try:
            # Extrair número do código (exemplo: ELE001 -> 001)
            numero_str = ultimo_produto.codigo_interno[3:]
            ultimo_numero = int(numero_str)
            novo_numero = ultimo_numero + 1
        except (ValueError, IndexError):
            novo_numero = 1
    else:
        novo_numero = 1
    
    return f"{categoria_codigo}{novo_numero:03d}"

def gerar_codigo_barras_interno(admin_id, produto_id):
    """Gerar código de barras EAN-13 interno"""
    # Usar prefixo específico da empresa (200-299 para uso interno)
    prefixo_empresa = "200"
    
    # Combinar admin_id e produto_id para garantir unicidade
    codigo_produto = f"{admin_id:04d}{produto_id:05d}"
    
    # Truncar se necessário para caber no EAN-13
    if len(codigo_produto) > 9:
        codigo_produto = codigo_produto[-9:]
    
    # Completar com zeros à esquerda se necessário
    codigo_produto = codigo_produto.zfill(9)
    
    # Construir código base (12 dígitos)
    codigo_base = prefixo_empresa + codigo_produto
    
    # Calcular dígito verificador
    soma = 0
    for i in range(12):
        peso = 1 if i % 2 == 0 else 3
        soma += int(codigo_base[i]) * peso
    
    digito_verificador = (10 - (soma % 10)) % 10
    
    return codigo_base + str(digito_verificador)

# ===== BUSCA INTELIGENTE =====

def buscar_produto_por_codigo(codigo, admin_id):
    """Buscar produto por código de barras ou interno"""
    # Primeiro, validar código
    validacao = validar_codigo_barras(codigo)
    if not validacao['valido']:
        return {'encontrado': False, 'erro': validacao['erro']}
    
    # Buscar por código de barras
    produto_barras = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.codigo_barras == codigo,
        Produto.ativo == True
    ).first()
    
    if produto_barras:
        return {
            'encontrado': True,
            'produto': produto_barras,
            'tipo_busca': 'codigo_barras'
        }
    
    # Buscar por código interno
    produto_interno = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.codigo_interno == codigo,
        Produto.ativo == True
    ).first()
    
    if produto_interno:
        return {
            'encontrado': True,
            'produto': produto_interno,
            'tipo_busca': 'codigo_interno'
        }
    
    # Buscar similares por nome (sugestões)
    produtos_similares = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.nome.ilike(f'%{codigo}%'),
        Produto.ativo == True
    ).limit(5).all()
    
    return {
        'encontrado': False,
        'sugestoes': produtos_similares,
        'codigo_buscado': codigo
    }

def sugerir_produtos_similares(nome_produto, admin_id, limite=5):
    """Sugerir produtos similares baseado no nome"""
    # Dividir nome em palavras-chave
    palavras = re.findall(r'\w+', nome_produto.lower())
    
    if not palavras:
        return []
    
    # Construir query de busca
    condicoes = []
    for palavra in palavras:
        if len(palavra) >= 3:  # Ignorar palavras muito pequenas
            condicoes.append(Produto.nome.ilike(f'%{palavra}%'))
    
    if not condicoes:
        return []
    
    # Buscar produtos
    query = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.ativo == True
    )
    
    # Aplicar condições OR
    from sqlalchemy import or_
    query = query.filter(or_(*condicoes))
    
    produtos = query.limit(limite).all()
    
    # Calcular score de similaridade simples
    resultado = []
    for produto in produtos:
        score = calcular_similaridade(nome_produto, produto.nome)
        resultado.append({
            'produto': produto,
            'score': score
        })
    
    # Ordenar por score
    resultado.sort(key=lambda x: x['score'], reverse=True)
    
    return [item['produto'] for item in resultado]

def calcular_similaridade(texto1, texto2):
    """Calcular similaridade entre dois textos (algoritmo simples)"""
    palavras1 = set(re.findall(r'\w+', texto1.lower()))
    palavras2 = set(re.findall(r'\w+', texto2.lower()))
    
    if not palavras1 or not palavras2:
        return 0
    
    intersecao = len(palavras1.intersection(palavras2))
    uniao = len(palavras1.union(palavras2))
    
    return intersecao / uniao if uniao > 0 else 0

# ===== GERAÇÃO DE QR CODE =====

def gerar_qr_code_produto(produto_id):
    """Gerar QR Code para produto"""
    if not QRCODE_AVAILABLE:
        # Retornar placeholder se qrcode não estiver disponível
        return "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2Y4ZjlmYSIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjEyIiBmaWxsPSIjNmM3NTdkIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+UVIgQ29kZTwvdGV4dD48L3N2Zz4="
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Dados do QR Code
        dados = {
            'tipo': 'produto_sige',
            'produto_id': produto_id,
            'timestamp': datetime.now().isoformat()
        }
        
        qr.add_data(str(dados))
        qr.make(fit=True)
        
        # Criar imagem
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Converter para base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        # Fallback em caso de erro
        return "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2ZkYzJhNSIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjEwIiBmaWxsPSIjODU0ZDBlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+RXJybyBRUjwvdGV4dD48L3N2Zz4="

# ===== CACHE DE CÓDIGOS LIDOS =====

# Cache simples em memória (em produção usar Redis)
cache_codigos_lidos = {}

def adicionar_ao_cache(codigo, produto_id, usuario_id):
    """Adicionar código ao cache de recentemente lidos"""
    timestamp = datetime.now()
    chave = f"{usuario_id}_{codigo}"
    
    cache_codigos_lidos[chave] = {
        'codigo': codigo,
        'produto_id': produto_id,
        'timestamp': timestamp,
        'usuario_id': usuario_id
    }
    
    # Limpar cache antigo (mais de 1 hora)
    limite_tempo = timestamp - timedelta(hours=1)
    chaves_antigas = [k for k, v in cache_codigos_lidos.items() 
                     if v['timestamp'] < limite_tempo]
    
    for chave_antiga in chaves_antigas:
        del cache_codigos_lidos[chave_antiga]

def obter_codigos_recentes(usuario_id, limite=10):
    """Obter códigos lidos recentemente pelo usuário"""
    codigos_usuario = [
        v for k, v in cache_codigos_lidos.items() 
        if v['usuario_id'] == usuario_id
    ]
    
    # Ordenar por timestamp (mais recente primeiro)
    codigos_usuario.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return codigos_usuario[:limite]

# ===== VALIDAÇÃO AVANÇADA =====

def validar_produto_para_codigo(produto_data):
    """Validar dados do produto antes de associar código"""
    erros = []
    
    # Nome obrigatório
    if not produto_data.get('nome', '').strip():
        erros.append('Nome do produto é obrigatório')
    
    # Unidade de medida
    unidades_validas = ['UN', 'KG', 'G', 'L', 'ML', 'M', 'CM', 'M2', 'M3', 'PAR', 'PC', 'CX', 'SC']
    if produto_data.get('unidade_medida') not in unidades_validas:
        erros.append(f'Unidade deve ser uma das: {", ".join(unidades_validas)}')
    
    # Categoria
    if not produto_data.get('categoria_id'):
        erros.append('Categoria é obrigatória')
    
    # Estoque mínimo
    try:
        estoque_min = float(produto_data.get('estoque_minimo', 0))
        if estoque_min < 0:
            erros.append('Estoque mínimo não pode ser negativo')
    except (ValueError, TypeError):
        erros.append('Estoque mínimo deve ser um número válido')
    
    return {
        'valido': len(erros) == 0,
        'erros': erros
    }

def detectar_codigo_duplicado(codigo, admin_id, excluir_produto_id=None):
    """Detectar se código de barras já existe"""
    query = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.codigo_barras == codigo,
        Produto.ativo == True
    )
    
    if excluir_produto_id:
        query = query.filter(Produto.id != excluir_produto_id)
    
    produto_existente = query.first()
    
    if produto_existente:
        return {
            'duplicado': True,
            'produto_existente': produto_existente
        }
    
    return {'duplicado': False}

# ===== ANÁLISE DE PADRÕES =====

def analisar_padroes_uso(admin_id, dias=30):
    """Analisar padrões de uso de códigos de barras"""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    data_limite = datetime.now() - timedelta(days=dias)
    
    # Produtos mais escaneados
    produtos_populares = db.session.query(
        Produto.id,
        Produto.nome,
        func.count(MovimentacaoEstoque.id).label('total_movimentacoes')
    ).join(
        MovimentacaoEstoque
    ).filter(
        Produto.admin_id == admin_id,
        MovimentacaoEstoque.data_movimentacao >= data_limite
    ).group_by(
        Produto.id,
        Produto.nome
    ).order_by(
        func.count(MovimentacaoEstoque.id).desc()
    ).limit(10).all()
    
    return {
        'produtos_populares': [
            {
                'produto_id': p.id,
                'nome': p.nome,
                'total_escaneamentos': p.total_movimentacoes
            }
            for p in produtos_populares
        ],
        'periodo_analise': f'{dias} dias'
    }