"""
Service Layer para processamento de fotos de RDO
Responsável por: validação, otimização, compressão e armazenamento
SIGE v9.0.4 - Sistema de Fotos RDO com Persistência Base64
"""

import os
import base64
from io import BytesIO
from PIL import Image
from werkzeug.utils import secure_filename
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ✅ CONFIGURAÇÃO STORAGE PERSISTENTE (v9.0.3 - PRODUÇÃO SAFE)
# Prioridade:
# 1. UPLOADS_PATH (variável de ambiente) → /persistent-storage/uploads (produção)
# 2. Fallback → static/uploads (desenvolvimento)
def get_upload_base():
    """Retorna caminho base para uploads baseado no ambiente"""
    # Tenta variável de ambiente primeiro (produção com volume persistente)
    uploads_path = os.environ.get('UPLOADS_PATH')
    
    if uploads_path:
        # Produção: usa volume persistente
        base = os.path.join(uploads_path, 'rdo')
        logger.info(f"📦 PRODUÇÃO: Usando storage persistente → {base}")
        
        # ✅ VALIDAÇÃO: Verifica se volume está montado e gravável
        try:
            os.makedirs(base, exist_ok=True)
            # Testa escrita
            test_file = os.path.join(base, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"✅ Volume persistente GRAVÁVEL: {base}")
        except Exception as e:
            logger.error(f"❌ ERRO: Volume persistente NÃO gravável: {base}")
            logger.error(f"   Erro: {e}")
            logger.warning(f"⚠️ FALLBACK: Usando storage local temporário (fotos serão perdidas!)")
            # Fallback para static/uploads se volume não estiver montado
            base = os.path.join(os.getcwd(), 'static', 'uploads', 'rdo')
            os.makedirs(base, exist_ok=True)
    else:
        # Desenvolvimento: usa static/uploads (será resetado, mas OK para dev)
        base = os.path.join(os.getcwd(), 'static', 'uploads', 'rdo')
        logger.info(f"💻 DESENVOLVIMENTO: Usando storage local → {base}")
        os.makedirs(base, exist_ok=True)
    
    return base

UPLOAD_BASE = get_upload_base()


def caminho_absoluto(caminho_relativo):
    """Resolve o caminho gravado no banco para um caminho absoluto real.

    Fase 5 — conserta a inconsistência que impede o volume persistente de
    funcionar. `salvar_foto_rdo` (linha 377) devolve sempre o relativo
    `uploads/rdo/<admin>/<rdo>/<arquivo>`, mas GRAVA em `UPLOAD_BASE`,
    que é `$UPLOADS_PATH/rdo` quando a variável existe. Quem serve a foto
    (crud_rdo_completo.py) montava
    `os.path.join(os.getcwd(), 'static', caminho)` — que só acerta quando
    UPLOADS_PATH está VAZIO. Definir a variável quebrava a exibição de
    todas as fotos, o que na prática impedia migrar para o volume.
    (O descasamento do servir foi corrigido em 23/07 com
    `_resolver_arquivo_foto`; esta função centraliza a resolução e
    acrescenta a recusa de travessia, que o resolver não tinha.)

    Devolve `None` para caminho vazio, absoluto ou com travessia de
    diretório — o valor vem do banco, mas isso não é motivo para confiar.
    """
    if not caminho_relativo:
        return None
    relativo = str(caminho_relativo).strip().lstrip('/')
    if not relativo or os.path.isabs(caminho_relativo):
        return None

    # `uploads/rdo/...` é o formato gravado; o prefixo `uploads/` mapeia
    # para a raiz de UPLOAD_BASE menos o sufixo 'rdo'.
    if relativo.startswith('uploads/'):
        sufixo = relativo[len('uploads/'):]
        if os.environ.get('UPLOADS_PATH'):
            base = os.environ['UPLOADS_PATH']
            candidato = os.path.join(base, sufixo)
        else:
            candidato = os.path.join(os.getcwd(), 'static', relativo)
    else:
        candidato = os.path.join(os.getcwd(), 'static', relativo)

    candidato = os.path.normpath(candidato)
    raiz = os.path.normpath(
        os.environ.get('UPLOADS_PATH')
        or os.path.join(os.getcwd(), 'static', 'uploads'))
    if not candidato.startswith(raiz + os.sep) and candidato != raiz:
        logger.error("🚫 caminho fora da raiz de uploads recusado: %r",
                     caminho_relativo)
        return None
    return candidato
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_FOTOS_POR_RDO = 20
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
QUALIDADE_WEBP = 70
MAX_DIMENSAO = 1920
THUMBNAIL_SIZE = 200


def validar_imagem(file):
    """
    Valida arquivo de imagem
    
    Args:
        file: FileStorage object do Flask
        
    Returns:
        tuple: (bool, str) - (válido, mensagem_erro)
    """
    # Verificar se arquivo existe
    if not file or file.filename == '':
        return False, "Nenhum arquivo selecionado"
    
    # Validar extensão
    extensao = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if extensao not in ALLOWED_EXTENSIONS:
        return False, f"Formato não permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Validar tamanho
    file.seek(0, os.SEEK_END)
    tamanho = file.tell()
    file.seek(0)  # Resetar cursor
    
    if tamanho > MAX_FILE_SIZE:
        tamanho_mb = tamanho / (1024 * 1024)
        return False, f"Arquivo muito grande ({tamanho_mb:.1f}MB). Máximo: 5MB"
    
    # Tentar abrir como imagem (valida MIME real)
    try:
        # Usar Image.open() sem verify() - mais tolerante
        img = Image.open(file)
        img.load()  # Força carregamento para detectar corrupção real
        file.seek(0)  # Resetar cursor
        return True, ""
    except Exception as e:
        logger.error(f"Erro ao validar imagem: {e}")
        return False, "Arquivo corrompido ou não é uma imagem válida"


def otimizar_para_webp(caminho_origem, caminho_destino, qualidade=QUALIDADE_WEBP, max_size=MAX_DIMENSAO):
    """
    Otimiza imagem: redimensiona e converte para WebP
    
    Por quê WebP?
    - 25-35% menor que JPEG na mesma qualidade
    - Suportado em 95%+ dos browsers
    - Mantém qualidade visual excelente
    
    Args:
        caminho_origem: Caminho do arquivo original
        caminho_destino: Caminho para salvar WebP otimizado
        qualidade: Qualidade de compressão (0-100)
        max_size: Dimensão máxima em pixels
        
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        with Image.open(caminho_origem) as img:
            # Converter para RGB se necessário (PNG com transparência)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            
            # Redimensionar mantendo aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Salvar como WebP
            img.save(caminho_destino, 'WEBP', quality=qualidade, method=6)
            
        logger.debug(f"✅ Imagem otimizada: {caminho_destino}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao otimizar imagem {caminho_origem}: {e}")
        return False


def gerar_thumbnail(caminho_origem, caminho_destino, size=THUMBNAIL_SIZE):
    """
    Gera thumbnail quadrado
    
    Por quê thumbnails?
    - Galeria carrega 100x mais rápido
    - Economiza banda mobile
    - Lazy loading eficiente
    
    Args:
        caminho_origem: Caminho do arquivo original
        caminho_destino: Caminho para salvar thumbnail
        size: Tamanho do thumbnail (quadrado)
        
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        with Image.open(caminho_origem) as img:
            # Converter para RGB se necessário
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            
            # Crop central para quadrado
            width, height = img.size
            side = min(width, height)
            left = (width - side) / 2
            top = (height - side) / 2
            right = (width + side) / 2
            bottom = (height + side) / 2
            
            img_cropped = img.crop((left, top, right, bottom))
            img_cropped.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Salvar como WebP
            img_cropped.save(caminho_destino, 'WEBP', quality=QUALIDADE_WEBP)
            
        logger.debug(f"✅ Thumbnail gerado: {caminho_destino}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar thumbnail {caminho_origem}: {e}")
        return False


def processar_imagem_base64(file):
    """
    Processa imagem e gera 3 versões em Base64 para armazenamento no banco
    
    Por quê Base64?
    - ✅ Fotos NUNCA são perdidas em deploy/restart
    - ✅ Backup automático com banco de dados
    - ✅ Funciona em qualquer ambiente (sem configuração)
    - ✅ Igual aos funcionários (padrão já testado)
    
    Args:
        file: FileStorage object do Flask
        
    Returns:
        dict: {
            'imagem_original_base64': 'data:image/webp;base64,...',
            'imagem_otimizada_base64': 'data:image/webp;base64,...',
            'thumbnail_base64': 'data:image/webp;base64,...',
            'tamanho_bytes': 123456,
            'nome_original': 'foto.jpg'
        }
    """
    try:
        # Abrir imagem original
        img_original = Image.open(file)
        
        # Converter para RGB se necessário (PNG com transparência)
        if img_original.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img_original.size, (255, 255, 255))
            if img_original.mode == 'RGBA':
                background.paste(img_original, mask=img_original.split()[-1])
            else:
                background.paste(img_original)
            img_original = background
        
        # =========================================================================
        # 1. IMAGEM ORIGINAL (mantém dimensões originais, converte para WebP)
        # =========================================================================
        buffer_original = BytesIO()
        img_original.save(buffer_original, format='WEBP', quality=85)
        buffer_original.seek(0)
        base64_original = base64.b64encode(buffer_original.read()).decode('utf-8')
        imagem_original_base64 = f"data:image/webp;base64,{base64_original}"
        
        # =========================================================================
        # 2. IMAGEM OTIMIZADA (1200px max para visualização)
        # =========================================================================
        img_otimizada = img_original.copy()
        img_otimizada.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        
        buffer_otimizada = BytesIO()
        img_otimizada.save(buffer_otimizada, format='WEBP', quality=70)
        buffer_otimizada.seek(0)
        base64_otimizada = base64.b64encode(buffer_otimizada.read()).decode('utf-8')
        imagem_otimizada_base64 = f"data:image/webp;base64,{base64_otimizada}"
        
        # =========================================================================
        # 3. THUMBNAIL (300px quadrado para listagem rápida)
        # =========================================================================
        img_thumb = img_original.copy()
        
        # Crop central para quadrado
        width, height = img_thumb.size
        side = min(width, height)
        left = (width - side) / 2
        top = (height - side) / 2
        right = (width + side) / 2
        bottom = (height + side) / 2
        
        img_thumb_cropped = img_thumb.crop((left, top, right, bottom))
        img_thumb_cropped.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        buffer_thumb = BytesIO()
        img_thumb_cropped.save(buffer_thumb, format='WEBP', quality=65)
        buffer_thumb.seek(0)
        base64_thumb = base64.b64encode(buffer_thumb.read()).decode('utf-8')
        thumbnail_base64 = f"data:image/webp;base64,{base64_thumb}"
        
        # Calcular tamanho total (soma das 3 versões)
        tamanho_total = len(base64_original) + len(base64_otimizada) + len(base64_thumb)
        
        # ✅ IMPORTANTE: Resetar cursor do arquivo para permitir reutilização
        file.seek(0)
        
        logger.info(f"✅ Imagem processada em base64: {file.filename}")
        logger.info(f"   📊 Original: {len(base64_original)} bytes")
        logger.info(f"   📊 Otimizada: {len(base64_otimizada)} bytes")
        logger.info(f"   📊 Thumbnail: {len(base64_thumb)} bytes")
        logger.info(f"   📊 Total: {tamanho_total} bytes")
        
        return {
            'imagem_original_base64': imagem_original_base64,
            'imagem_otimizada_base64': imagem_otimizada_base64,
            'thumbnail_base64': thumbnail_base64,
            'tamanho_bytes': tamanho_total,
            'nome_original': file.filename
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar imagem em base64: {e}")
        raise Exception(f"Erro ao processar imagem: {str(e)}")


def salvar_foto_rdo(file, admin_id, rdo_id):
    """
    Orquestra todo o fluxo de salvamento:
    1. Valida imagem
    2. Cria estrutura de diretórios
    3. Salva original
    4. Gera versão otimizada
    5. Gera thumbnail
    6. Retorna caminhos relativos
    
    Args:
        file: FileStorage object
        admin_id: ID do admin (multi-tenant)
        rdo_id: ID do RDO
        
    Returns:
        dict: {
            'arquivo_original': 'caminho/relativo',
            'arquivo_otimizado': 'caminho/relativo', 
            'thumbnail': 'caminho/relativo',
            'nome_original': 'nome.jpg',
            'tamanho_bytes': 123456
        }
        
    Raises:
        ValueError: Se validação falhar
        Exception: Se erro no processamento
    """
    # 1. Validar
    valido, erro = validar_imagem(file)
    if not valido:
        raise ValueError(erro)
    
    # 2. Criar diretórios (multi-tenant)
    pasta_tenant = os.path.join(UPLOAD_BASE, str(admin_id), str(rdo_id))
    os.makedirs(pasta_tenant, exist_ok=True)
    
    # 3. Gerar nomes seguros
    nome_seguro = secure_filename(file.filename)
    base_nome, ext_original = os.path.splitext(nome_seguro)
    timestamp = int(datetime.now().timestamp())
    
    # Caminhos absolutos
    caminho_original = os.path.join(pasta_tenant, f"{base_nome}_{timestamp}_original{ext_original}")
    caminho_otimizado = os.path.join(pasta_tenant, f"{base_nome}_{timestamp}.webp")
    caminho_thumbnail = os.path.join(pasta_tenant, f"{base_nome}_{timestamp}_thumb.webp")
    
    # 4. Salvar original
    file.save(caminho_original)
    tamanho = os.path.getsize(caminho_original)
    logger.info(f"📁 Arquivo original salvo: {caminho_original} ({tamanho} bytes)")
    
    # 5. Gerar otimizado
    if not otimizar_para_webp(caminho_original, caminho_otimizado):
        # Tentar limpar arquivo original se falhou
        try:
            os.remove(caminho_original)
        except:
            pass
        raise Exception("Erro ao otimizar imagem")
    
    # 6. Gerar thumbnail
    if not gerar_thumbnail(caminho_original, caminho_thumbnail):
        # Tentar limpar arquivos se falhou
        try:
            os.remove(caminho_original)
            os.remove(caminho_otimizado)
        except:
            pass
        raise Exception("Erro ao gerar thumbnail")
    
    # ── Fase 5 — base64 NÃO é mais gerada no upload ──────────────────
    # Até 2026-07-21 esta função gerava, além dos três arquivos em disco,
    # TRÊS cópias base64 do mesmo conteúdo, gravadas em colunas TEXT.
    # Medição do banco de desenvolvimento nesse dia:
    #   pg_total_relation_size('rdo_foto') = 16 GB (TOAST = 16 GB)
    #   28.870 fotos × ~442 KB de base64 cada
    #   28.860 delas JÁ tinham o arquivo em disco — pura duplicata.
    # A função `processar_imagem_base64` continua existindo: é o que o
    # script de migração usa para RECUPERAR as 10 fotos legadas que só
    # existem em base64, e o caminho de restauração de emergência.

    base_relativo = f"uploads/rdo/{admin_id}/{rdo_id}"

    resultado = {
        'arquivo_original': f"{base_relativo}/{os.path.basename(caminho_original)}",
        'arquivo_otimizado': f"{base_relativo}/{os.path.basename(caminho_otimizado)}",
        'thumbnail': f"{base_relativo}/{os.path.basename(caminho_thumbnail)}",
        'nome_original': file.filename,
        'tamanho_bytes': tamanho,
    }

    logger.info("✅ Foto processada (disco): %s → %s (%s bytes)",
                file.filename, resultado['arquivo_otimizado'], tamanho)
    return resultado
