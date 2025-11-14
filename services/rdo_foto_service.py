"""
Service Layer para processamento de fotos de RDO
Responsável por: validação, otimização, compressão e armazenamento
SIGE v9.0 - Sistema de Fotos RDO com Storage Persistente
"""

import os
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
    
    # Retornar caminhos relativos (para URL)
    base_relativo = f"uploads/rdo/{admin_id}/{rdo_id}"
    
    resultado = {
        'arquivo_original': f"{base_relativo}/{os.path.basename(caminho_original)}",
        'arquivo_otimizado': f"{base_relativo}/{os.path.basename(caminho_otimizado)}",
        'thumbnail': f"{base_relativo}/{os.path.basename(caminho_thumbnail)}",
        'nome_original': file.filename,
        'tamanho_bytes': tamanho
    }
    
    logger.info(f"✅ Foto processada com sucesso: {file.filename}")
    return resultado
