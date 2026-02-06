# ================================
# BLUEPRINT DE PONTO - CELULAR COMPARTILHADO
# Sistema de Ponto Eletrônico SIGE v8.0
# ================================

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
import pytz
from app import db

# Fuso horário do Brasil (Brasília)
TIMEZONE_BRASIL = pytz.timezone('America/Sao_Paulo')

def get_datetime_brasil():
    """Retorna o datetime atual no fuso horário de Brasília"""
    return datetime.now(TIMEZONE_BRASIL)

def get_date_brasil():
    """Retorna a data atual no fuso horário de Brasília"""
    return datetime.now(TIMEZONE_BRASIL).date()

def get_time_brasil():
    """Retorna a hora atual no fuso horário de Brasília"""
    return datetime.now(TIMEZONE_BRASIL).time()
from models import Obra, Funcionario, RegistroPonto, ConfiguracaoHorario, DispositivoObra, FuncionarioObrasPonto, FotoFacialFuncionario
from ponto_service import PontoService
from multitenant_helper import get_admin_id as get_tenant_admin_id
from decorators import admin_required
from utils_facial import (
    comparar_faces_deepface, 
    validar_qualidade_foto,
    validar_qualidade_foto_avancada,
    reconhecer_com_multiplas_fotos,
    identificar_funcionario_multiplas_fotos,
    THRESHOLD_CONFIANCA,
    MIN_CONFIANCA_PERCENTUAL
)
from utils_geofencing import validar_localizacao_na_obra
import logging
import numpy as np
import base64
import tempfile
import os

logger = logging.getLogger(__name__)

# Cache global de embeddings com auto-reload baseado em mtime
_cache_facial = None
_cache_loaded = False
_cache_mtime = 0  # Timestamp de modificação do arquivo quando carregado
_deepface_model_loaded = False
_sface_model = None  # Cache do modelo TensorFlow em memória
_face_cascade = None  # Cache do classificador Haar para detecção facial

PIPELINE_VERSION = "4.0-face-detection"

def get_face_cascade():
    """Retorna o classificador Haar cacheado para detecção facial"""
    global _face_cascade
    if _face_cascade is not None:
        return _face_cascade
    import cv2
    _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    logger.info("✅ Haar cascade carregado e cacheado")
    return _face_cascade

def get_sface_model():
    """Retorna o modelo SFace cacheado em memória usando DeepFace.build_model"""
    global _sface_model
    if _sface_model is not None:
        logger.debug("✅ Usando modelo SFace já cacheado em memória")
        return _sface_model
    
    try:
        import time
        start = time.time()
        from deepface import DeepFace
        
        logger.info("🔄 Carregando modelo SFace pela primeira vez...")
        _sface_model = DeepFace.build_model('SFace')
        
        elapsed = time.time() - start
        logger.info(f"✅ Modelo SFace carregado e cacheado em {elapsed:.2f}s")
        logger.info(f"✅ Tipo do modelo: {type(_sface_model)}")
        logger.info(f"✅ Input shape: {_sface_model.input_shape if hasattr(_sface_model, 'input_shape') else 'N/A'}")
        
        return _sface_model
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar SFace: {e}")
        return None

def preload_deepface_model():
    """Pré-carrega o modelo DeepFace para evitar delay na primeira requisição"""
    global _deepface_model_loaded, _sface_model
    if _deepface_model_loaded and _sface_model is not None:
        return True
    try:
        import time
        start = time.time()
        
        logger.info("🔄 Pré-carregando modelo SFace diretamente...")
        
        # Tentar carregar modelo diretamente (mais rápido)
        model = get_sface_model()
        if model is not None:
            _deepface_model_loaded = True
            logger.info(f"✅ Modelo SFace pré-carregado em {time.time() - start:.2f}s")
            return True
        
        # Fallback: carregar via DeepFace.represent
        from deepface import DeepFace
        import numpy as np
        
        logger.info("🔄 Fallback: pré-carregando via DeepFace.represent...")
        
        dummy_img = np.zeros((112, 112, 3), dtype=np.uint8)
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            from PIL import Image
            Image.fromarray(dummy_img).save(tmp.name)
            tmp_path = tmp.name
        try:
            DeepFace.represent(
                img_path=tmp_path,
                model_name='SFace',
                enforce_detection=False,
                detector_backend='skip',
                align=False
            )
            _deepface_model_loaded = True
            logger.info(f"✅ Modelo DeepFace SFace pré-carregado em {time.time() - start:.2f}s")
            return True
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        logger.warning(f"⚠️ Erro ao pré-carregar modelo DeepFace: {e}")
        return False


def validar_formato_embedding(embedding):
    """
    Valida se o embedding está no formato correto.
    
    Formato correto:
    - Tipo: list
    - Tamanho: 128 elementos
    - Elementos: float
    - NÃO deve ser lista aninhada
    
    Returns:
        tuple: (valido: bool, mensagem: str)
    """
    # 1. Verificar tipo
    if not isinstance(embedding, list):
        return False, f"Tipo inválido: {type(embedding)} (esperado: list)"
    
    # 2. Verificar se não é lista aninhada
    if len(embedding) > 0 and isinstance(embedding[0], list):
        return False, f"Lista aninhada detectada! Primeiro elemento: {type(embedding[0])}"
    
    # 3. Verificar tamanho
    if len(embedding) != 128:
        return False, f"Tamanho inválido: {len(embedding)} (esperado: 128)"
    
    # 4. Verificar elementos
    if not all(isinstance(x, (int, float)) for x in embedding):
        return False, "Elementos devem ser números (int ou float)"
    
    return True, "Embedding válido"


def gerar_embedding_otimizado(img_path):
    """
    Gera embedding usando modelo SFace cacheado em memória.
    Usa model.forward() do SFaceClient que é MUITO mais rápido que DeepFace.represent().
    
    IMPORTANTE: SFace usa OpenCV DNN, não Keras!
    - Entrada: BGR normalizado para [0, 1]
    - Shape: (batch, 112, 112, 3)
    """
    import time
    import cv2
    import numpy as np
    
    start_total = time.time()
    logger.info(f"🔍 gerar_embedding_otimizado - INÍCIO (img: {img_path})")
    
    # Tentar usar modelo cacheado primeiro
    model = get_sface_model()
    if model is not None:
        try:
            logger.info(f"🔍 gerar_embedding_otimizado - Usando modelo cacheado")
            
            # 1. Ler imagem (OpenCV lê em BGR)
            t0 = time.time()
            img = cv2.imread(img_path)
            if img is None:
                raise ValueError("Não foi possível ler a imagem")
            logger.info(f"⏱️ cv2.imread: {time.time()-t0:.3f}s (shape: {img.shape})")
            
            # 2. Detectar rosto usando Haar cascade (CRITICAL FIX)
            t0 = time.time()
            face_cascade = get_face_cascade()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            elapsed_detection = time.time() - t0
            logger.info(f"⏱️ Face detection: {elapsed_detection:.3f}s ({len(faces)} face(s) found)")
            
            # 3. Crop face region or fallback to full image (use largest face)
            t0 = time.time()
            if len(faces) > 0:
                if len(faces) > 1:
                    faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                    x, y, w, h = faces_sorted[0]
                else:
                    x, y, w, h = faces[0]
                margin = 0.2
                img_h, img_w = img.shape[:2]
                x1 = max(0, int(x - w * margin))
                y1 = max(0, int(y - h * margin))
                x2 = min(img_w, int(x + w + w * margin))
                y2 = min(img_h, int(y + h + h * margin))
                face_crop = img[y1:y2, x1:x2]
                img_resized = cv2.resize(face_crop, (112, 112))
                logger.info(f"✅ Face cropped: ({x},{y},{w},{h}) -> margin crop ({x1},{y1})-({x2},{y2})")
            else:
                logger.warning(f"⚠️ No face detected in {img_path}, using full image resize (fallback)")
                img_resized = cv2.resize(img, (112, 112))
            logger.info(f"⏱️ crop+resize: {time.time()-t0:.3f}s")
            
            # 4. Normalizar para [0, 1] - SFace espera esse formato
            t0 = time.time()
            img_normalized = img_resized.astype(np.float32) / 255.0
            img_batch = np.expand_dims(img_normalized, axis=0)
            logger.info(f"⏱️ normalize+batch: {time.time()-t0:.3f}s")
            
            # 5. Gerar embedding usando forward() (OpenCV DNN)
            t0 = time.time()
            embedding = model.forward(img_batch)
            elapsed_forward = time.time() - t0
            elapsed_total = time.time() - start_total
            logger.info(f"⚡ model.forward(): {elapsed_forward:.3f}s | TOTAL: {elapsed_total:.3f}s")
            
            # IMPORTANTE: Remover dimensão do batch
            # model.forward() retorna shape (1, 128), precisamos de (128,)
            if isinstance(embedding, np.ndarray):
                logger.info(f"📊 Embedding shape ANTES: {embedding.shape}")
                
                # Remover dimensão do batch se existir
                if len(embedding.shape) > 1 and embedding.shape[0] == 1:
                    embedding = embedding[0]  # De (1, 128) para (128,)
                    logger.info(f"📊 Embedding shape DEPOIS: {embedding.shape}")
                
                # Converter para lista simples
                embedding_list = embedding.tolist()
                
                # Validar formato
                if isinstance(embedding_list, list) and len(embedding_list) == 128:
                    logger.info(f"✅ Embedding formato correto: lista de {len(embedding_list)} elementos")
                    logger.info(f"✅ gerar_embedding_otimizado - SUCESSO em {elapsed_total:.3f}s")
                    return embedding_list
                else:
                    logger.error(f"❌ Embedding formato inválido: {type(embedding_list)}, len={len(embedding_list) if isinstance(embedding_list, list) else 'N/A'}")
                    raise ValueError(f"Embedding com formato inválido")
            
            # Se não for numpy array, tentar converter
            if isinstance(embedding, list):
                # Se for lista aninhada, pegar primeiro elemento
                if len(embedding) > 0 and isinstance(embedding[0], list):
                    logger.warning(f"⚠️ Embedding é lista aninhada, corrigindo...")
                    embedding = embedding[0]
                return embedding
            
            return list(embedding)
            
        except Exception as e:
            elapsed = time.time() - start_total
            logger.warning(f"⚠️ Erro ao usar modelo cacheado após {elapsed:.3f}s: {e}")
            logger.warning(f"⚠️ Tipo do erro: {type(e).__name__}")
            import traceback
            logger.warning(f"⚠️ Traceback: {traceback.format_exc()}")
    else:
        logger.warning("⚠️ Modelo NÃO está em cache! Usando fallback...")
    
    # Fallback para DeepFace.represent (lento mas funciona)
    logger.warning(f"🔄 gerar_embedding_otimizado - Usando FALLBACK (DeepFace.represent)")
    start_fallback = time.time()
    try:
        from deepface import DeepFace
        result = DeepFace.represent(
            img_path=img_path,
            model_name='SFace',
            enforce_detection=False,
            detector_backend='skip',
            align=False
        )
        
        if result and len(result) > 0:
            elapsed_fallback = time.time() - start_fallback
            elapsed_total = time.time() - start_total
            logger.warning(f"🔄 DeepFace.represent: {elapsed_fallback:.2f}s | TOTAL: {elapsed_total:.2f}s")
            return result[0]['embedding']
    except Exception as e:
        logger.error(f"❌ Erro no fallback: {e}")
    
    return None

def redimensionar_imagem_para_reconhecimento(foto_base64, max_width=640, max_height=480):
    """
    Redimensiona imagem para resolução ideal para reconhecimento facial.
    Imagens menores = processamento mais rápido, sem perda de precisão.
    """
    try:
        import io
        from PIL import Image
        
        if ',' in foto_base64:
            foto_base64 = foto_base64.split(',')[1]
        
        img_data = base64.b64decode(foto_base64)
        img = Image.open(io.BytesIO(img_data))
        
        width, height = img.size
        
        if width <= max_width and height <= max_height:
            return foto_base64
        
        ratio = min(max_width / width, max_height / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        if img_resized.mode != 'RGB':
            img_resized = img_resized.convert('RGB')
        
        buffer = io.BytesIO()
        img_resized.save(buffer, format='JPEG', quality=85, optimize=True)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        logger.debug(f"📐 Imagem redimensionada: {width}x{height} → {new_width}x{new_height}")
        
        return img_base64
        
    except Exception as e:
        logger.error(f"Erro ao redimensionar imagem: {e}")
        return foto_base64

def carregar_cache_facial():
    """
    Carrega o cache de embeddings do arquivo.
    Verifica automaticamente se o arquivo no disco foi atualizado (mtime)
    para recarregar entre workers do Gunicorn.
    """
    global _cache_facial, _cache_loaded, _cache_mtime
    
    try:
        from gerar_cache_facial import carregar_cache, CACHE_PATH
        
        file_mtime = 0
        if os.path.exists(CACHE_PATH):
            file_mtime = os.path.getmtime(CACHE_PATH)
        
        if _cache_loaded and file_mtime <= _cache_mtime:
            return _cache_facial
        
        if _cache_loaded and file_mtime > _cache_mtime:
            logger.info(f"🔄 Cache atualizado no disco detectado (mtime: {file_mtime} > {_cache_mtime}), recarregando...")
        
        _cache_facial = carregar_cache()
        _cache_loaded = True
        _cache_mtime = file_mtime
        
        if _cache_facial:
            cache_version = _cache_facial.get('pipeline_version', 'unknown')
            if cache_version != PIPELINE_VERSION:
                logger.warning(f"⚠️ [CACHE OBSOLETO] Cache pipeline={cache_version}, atual={PIPELINE_VERSION}. Regenere o cache via /ponto/api/cache/gerar!")
            total = len(_cache_facial.get('embeddings', {}))
            logger.info(f"✅ Cache facial carregado: {total} funcionários (mtime={file_mtime}, pipeline={cache_version})")
        else:
            logger.warning("⚠️ Cache facial vazio ou não encontrado")
        return _cache_facial
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar cache facial: {e}")
        _cache_loaded = True
        _cache_mtime = 0
        return None

def recarregar_cache_facial():
    """Força recarga do cache"""
    global _cache_facial, _cache_loaded, _cache_mtime
    _cache_loaded = False
    _cache_facial = None
    _cache_mtime = 0
    return carregar_cache_facial()

def identificar_por_cache(foto_base64, admin_id, threshold=0.64):
    """
    Identifica funcionário usando cache de embeddings (muito mais rápido).
    
    Args:
        foto_base64: Foto capturada em base64
        admin_id: ID do tenant
        threshold: Limiar de distância para match (0.64 = balanceado)
    
    Returns:
        tuple: (funcionario_id, distancia, erro)
    """
    import time
    start_func = time.time()
    timings = {}
    
    try:
        t0 = time.time()
        from deepface import DeepFace
        timings['import'] = time.time() - t0
    except ImportError:
        return None, None, "DeepFace não instalado"
    
    t0 = time.time()
    cache = carregar_cache_facial()
    timings['load_cache'] = time.time() - t0
    
    if not cache or 'embeddings' not in cache:
        logger.warning("⚠️ Cache não disponível para reconhecimento")
        return None, None, "Cache não disponível"
    
    t0 = time.time()
    embeddings_cache = cache['embeddings']
    admin_id_int = int(admin_id) if admin_id else None
    
    # Log detalhado para debug multi-tenant
    logger.info(f"🔍 Buscando embeddings para admin_id={admin_id_int} (type: {type(admin_id_int).__name__})")
    logger.info(f"📊 Cache total: {len(embeddings_cache)} funcionários")
    
    embeddings_tenant = {}
    admin_ids_no_cache = set()
    
    for fid, data in embeddings_cache.items():
        cache_admin_id = data.get('admin_id')
        cache_admin_id_int = int(cache_admin_id) if cache_admin_id is not None else None
        admin_ids_no_cache.add(cache_admin_id_int)
        
        if cache_admin_id_int == admin_id_int:
            embeddings_tenant[fid] = data
    
    timings['filter_tenant'] = time.time() - t0
    
    # Log dos admin_ids encontrados no cache
    logger.info(f"📊 Admin IDs no cache: {sorted(list(admin_ids_no_cache))}")
    logger.info(f"📊 Match para admin_id={admin_id_int}: {len(embeddings_tenant)} funcionários")
    
    if not embeddings_tenant:
        logger.error(f"❌ NENHUM embedding encontrado para admin_id={admin_id_int}!")
        logger.error(f"   Admin IDs disponíveis: {sorted(list(admin_ids_no_cache))}")
        return None, None, f"Nenhum embedding no cache para admin_id={admin_id_int}. Disponíveis: {sorted(list(admin_ids_no_cache))}"
    
    logger.info(f"⏱️ Cache: import={timings['import']:.2f}s, load={timings['load_cache']:.2f}s, filter={timings['filter_tenant']:.3f}s - {len(embeddings_tenant)} func.")
    
    try:
        if foto_base64.startswith('data:'):
            foto_base64 = foto_base64.split(',')[1]
        
        start_resize = time.time()
        foto_base64 = redimensionar_imagem_para_reconhecimento(foto_base64, max_width=640, max_height=480)
        elapsed_resize = time.time() - start_resize
        logger.info(f"⏱️ Redimensionamento: {elapsed_resize:.3f}s")
        
        foto_bytes = base64.b64decode(foto_base64)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(foto_bytes)
            tmp_path = tmp.name
        
        logger.info(f"📁 Arquivo temporário: {tmp_path} ({len(foto_bytes)} bytes)")
        
        try:
            start_represent = time.time()
            # Usar função otimizada com modelo cacheado
            embedding_list = gerar_embedding_otimizado(tmp_path)
            elapsed_represent = time.time() - start_represent
            logger.info(f"⏱️ gerar_embedding_otimizado retornou em: {elapsed_represent:.3f}s")
            
            if embedding_list is None:
                return None, None, "Nenhum rosto detectado na foto"
            
            # Normalizar embedding L2 para consistência com cache
            embedding_array = np.array(embedding_list, dtype=np.float32)
            norm = np.linalg.norm(embedding_array)
            if norm > 0:
                embedding_capturado = embedding_array / norm
            else:
                embedding_capturado = embedding_array
            
            logger.info(f"⏱️ Embedding total: {elapsed_represent:.3f}s (norm L2: {np.linalg.norm(embedding_capturado):.4f})")
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
        melhor_match_id = None
        menor_distancia = float('inf')
        melhor_foto_desc = None
        total_comparacoes = 0
        
        # Log do embedding capturado (primeiros 5 valores)
        logger.info(f"📊 Embedding capturado: dims={len(embedding_capturado)}, primeiros 5={embedding_capturado[:5].tolist()}")
        
        for func_id, data in embeddings_tenant.items():
            embeddings_list = data.get('embeddings', [])
            
            if not embeddings_list:
                if 'embedding' in data:
                    embeddings_list = [{'embedding': data['embedding'], 'descricao': 'Foto principal'}]
                else:
                    continue
            
            for emb_info in embeddings_list:
                if isinstance(emb_info, dict):
                    embedding_cache = np.array(emb_info['embedding'], dtype=np.float32)
                    descricao = emb_info.get('descricao', 'Foto')
                else:
                    embedding_cache = np.array(emb_info, dtype=np.float32)
                    descricao = 'Foto'
                
                distancia = np.linalg.norm(embedding_capturado - embedding_cache)
                total_comparacoes += 1
                
                if total_comparacoes <= 3:
                    cache_norm = np.linalg.norm(embedding_cache)
                    logger.info(f"📊 Comparação #{total_comparacoes}: func={func_id} ({data.get('nome', '?')}), dist={distancia:.4f}, cache_norm={cache_norm:.4f}, primeiros3_cache={embedding_cache[:3].tolist()}")
                
                if distancia < menor_distancia:
                    menor_distancia = distancia
                    melhor_match_id = func_id
                    melhor_foto_desc = descricao
        
        total_time = time.time() - start_func
        
        if menor_distancia <= threshold:
            logger.info(f"✅ Match: func={melhor_match_id}, dist={menor_distancia:.4f} | TOTAL={total_time:.2f}s (represent={time.time()-start_represent:.2f}s)")
            return melhor_match_id, menor_distancia, None
        else:
            logger.info(f"❌ Sem match: dist={menor_distancia:.4f} > {threshold} | TOTAL={total_time:.2f}s")
            return None, menor_distancia, f"Distância {menor_distancia:.4f} acima do threshold {threshold}"
            
    except Exception as e:
        logger.error(f"Erro na identificação por cache: {e}")
        return None, None, str(e)

ponto_bp = Blueprint('ponto', __name__, url_prefix='/ponto')

# Pré-carregar modelo DeepFace e cache facial no import do módulo
try:
    import threading
    def _async_preload():
        try:
            preload_deepface_model()
            # Também pré-carregar o cache facial para cada worker
            cache = carregar_cache_facial()
            if cache:
                total = len(cache.get('embeddings', {}))
                logger.info(f"✅ Cache facial pré-carregado no worker: {total} funcionários")
            else:
                logger.info("ℹ️ Nenhum cache facial disponível no startup (gere via /ponto/api/cache/gerar)")
        except Exception as e:
            logger.warning(f"⚠️ Preload async falhou: {e}")
    
    threading.Thread(target=_async_preload, daemon=True).start()
    logger.info("🚀 Iniciando pré-carregamento assíncrono do modelo DeepFace + cache facial")
except Exception as e:
    logger.warning(f"⚠️ Não foi possível iniciar preload: {e}")

# Rota de debug para verificar se o blueprint está funcionando
@ponto_bp.route('/debug')
def ponto_debug():
    """Rota de debug para verificar se o blueprint está acessível"""
    import sys
    return f"""
    <html>
    <head><title>Debug Ponto</title></head>
    <body style="font-family: monospace; padding: 20px;">
        <h1 style="color: green;">Blueprint Ponto OK!</h1>
        <p>Python: {sys.version}</p>
        <p>Hora Brasil: {get_datetime_brasil().strftime('%d/%m/%Y %H:%M:%S')}</p>
        <p>Blueprints carregados corretamente.</p>
        <p><a href="/ponto">Ir para /ponto</a></p>
    </body>
    </html>
    """


@ponto_bp.route('/')
@login_required
def index():
    """Página inicial do ponto - lista todos os funcionários ativos"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar todos os funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Para cada funcionário, verificar se já bateu ponto hoje
        hoje = date.today()
        funcionarios_com_status = []
        
        for func in funcionarios:
            registro_hoje = RegistroPonto.query.filter_by(
                funcionario_id=func.id,
                data=hoje,
                admin_id=admin_id
            ).first()
            
            funcionarios_com_status.append({
                'funcionario': func,
                'registro_hoje': registro_hoje
            })
        
        return render_template('ponto/lista_funcionarios.html',
                             funcionarios=funcionarios_com_status,
                             hoje=hoje)
        
    except Exception as e:
        import traceback
        erro_completo = traceback.format_exc()
        logger.error(f"Erro ao listar funcionários: {e}\n{erro_completo}")
        # Mostrar erro na tela para debug em produção
        return f"""
        <html>
        <head><title>Erro Ponto</title></head>
        <body style="font-family: monospace; padding: 20px; background: #f8f9fa;">
            <h1 style="color: red;">Erro ao carregar página de Ponto</h1>
            <h3>Mensagem: {str(e)}</h3>
            <pre style="background: #fff; padding: 15px; border: 1px solid #ccc; overflow-x: auto;">
{erro_completo}
            </pre>
            <p><a href="/dashboard">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """, 500


@ponto_bp.route('/funcionario/<int:funcionario_id>')
@login_required
def bater_ponto_funcionario(funcionario_id):
    """Página de batida de ponto individual - mostra horário e dropdown de obras"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se funcionário existe e pertence ao admin
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first_or_404()
        
        # Buscar registro de ponto de hoje
        hoje = date.today()
        registro_hoje = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=hoje,
            admin_id=admin_id
        ).first()
        
        # Buscar obras configuradas para o funcionário
        obras_configuradas = FuncionarioObrasPonto.query.filter_by(
            funcionario_id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).all()
        
        # Se tem obras configuradas, mostrar apenas essas. Caso contrário, todas as ativas
        if obras_configuradas:
            obras_ids = [config.obra_id for config in obras_configuradas]
            obras = Obra.query.filter(
                Obra.id.in_(obras_ids),
                Obra.admin_id == admin_id,
                Obra.ativo == True
            ).order_by(Obra.nome).all()
        else:
            # Sem configuração específica: mostrar todas as obras ativas
            obras = Obra.query.filter_by(
                admin_id=admin_id,
                ativo=True
            ).order_by(Obra.nome).all()
        
        # Horário atual (Brasil)
        agora = get_datetime_brasil()
        hora_atual = agora.hour
        minuto_atual = agora.minute
        
        # Determinar tipo sugerido baseado no horário (pré-definido)
        # entrada: 00:00 - 11:30
        # almoco_saida: 11:31 - 12:30
        # almoco_retorno: 12:31 - 14:00
        # saida: 14:01 - 23:59
        if hora_atual < 11 or (hora_atual == 11 and minuto_atual <= 30):
            tipo_sugerido = 'entrada'
        elif hora_atual == 11 or (hora_atual == 12 and minuto_atual <= 30):
            tipo_sugerido = 'almoco_saida'
        elif hora_atual == 12 or (hora_atual <= 14 and minuto_atual <= 0) or hora_atual == 13:
            tipo_sugerido = 'almoco_retorno'
        else:
            tipo_sugerido = 'saida'
        
        # Se o tipo sugerido já foi registrado, encontrar o próximo disponível
        if registro_hoje:
            if tipo_sugerido == 'entrada' and registro_hoje.hora_entrada:
                if not registro_hoje.hora_almoco_saida:
                    tipo_sugerido = 'almoco_saida'
                elif not registro_hoje.hora_almoco_retorno:
                    tipo_sugerido = 'almoco_retorno'
                elif not registro_hoje.hora_saida:
                    tipo_sugerido = 'saida'
            elif tipo_sugerido == 'almoco_saida' and registro_hoje.hora_almoco_saida:
                if not registro_hoje.hora_almoco_retorno:
                    tipo_sugerido = 'almoco_retorno'
                elif not registro_hoje.hora_saida:
                    tipo_sugerido = 'saida'
            elif tipo_sugerido == 'almoco_retorno' and registro_hoje.hora_almoco_retorno:
                if not registro_hoje.hora_saida:
                    tipo_sugerido = 'saida'
        
        return render_template('ponto/bater_ponto_individual.html',
                             funcionario=funcionario,
                             registro_hoje=registro_hoje,
                             obras=obras,
                             agora=agora,
                             hoje=hoje,
                             tipo_sugerido=tipo_sugerido)
        
    except Exception as e:
        logger.error(f"Erro ao carregar página de batida de ponto: {e}")
        flash(f'Erro ao carregar página: {str(e)}', 'error')
        return redirect(url_for('ponto.index'))


@ponto_bp.route('/obra/<int:obra_id>')
@login_required
def obra_dashboard(obra_id):
    """Tela principal do celular da obra - mostra todos os funcionários"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se obra existe e pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
        
        # Obter status de todos os funcionários
        status_funcionarios = PontoService.obter_status_obra(obra_id)
        
        # Estatísticas do dia
        total_funcionarios = len(status_funcionarios)
        presentes = len([f for f in status_funcionarios if f['registro'] and f['registro'].hora_entrada])
        faltaram = total_funcionarios - presentes
        atrasados = len([f for f in status_funcionarios if f['registro'] and f['registro'].minutos_atraso_entrada and f['registro'].minutos_atraso_entrada > 0])
        
        estatisticas = {
            'total_funcionarios': total_funcionarios,
            'presentes': presentes,
            'faltaram': faltaram,
            'atrasados': atrasados
        }
        
        return render_template('ponto/obra_dashboard.html',
                             obra=obra,
                             funcionarios=status_funcionarios,
                             estatisticas=estatisticas,
                             hoje=date.today())
        
    except Exception as e:
        logger.error(f"Erro no dashboard da obra: {e}")
        flash(f'Erro ao carregar dashboard: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@ponto_bp.route('/api/bater-ponto', methods=['POST'])
@login_required
def api_bater_ponto():
    """API para registrar ponto via celular da obra"""
    try:
        data = request.get_json()
        
        funcionario_id = data.get('funcionario_id')
        tipo_ponto = data.get('tipo_ponto')
        obra_id = data.get('obra_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not all([funcionario_id, tipo_ponto, obra_id]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios não informados'}), 400
        
        resultado = PontoService.bater_ponto_obra(
            funcionario_id=funcionario_id,
            tipo_ponto=tipo_ponto,
            obra_id=obra_id,
            latitude=latitude,
            longitude=longitude
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Erro na API de bater ponto: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_ponto(registro_id):
    """Exclui um registro de ponto"""
    try:
        admin_id = get_tenant_admin_id()
        
        registro = RegistroPonto.query.filter_by(
            id=registro_id,
            admin_id=admin_id
        ).first()
        
        if not registro:
            return jsonify({'success': False, 'error': 'Registro não encontrado'}), 404
        
        db.session.delete(registro)
        db.session.commit()
        
        logger.info(f"Registro de ponto {registro_id} excluído com sucesso")
        return jsonify({'success': True, 'message': 'Registro excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir registro de ponto {registro_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/api/status-obra/<int:obra_id>')
@login_required
def api_status_obra(obra_id):
    """API para obter status atualizado da obra"""
    try:
        status_funcionarios = PontoService.obter_status_obra(obra_id)
        
        # Serializar dados para JSON
        funcionarios_json = []
        for item in status_funcionarios:
            funcionario_data = {
                'id': item['funcionario'].id,
                'nome': item['funcionario'].nome,
                'funcao': item['funcionario'].funcao.nome if item['funcionario'].funcao else 'N/A',
                'proximo_ponto': item['proximo_ponto'],
                'status_visual': item['status_visual'],
                'horas_ate_agora': str(item['horas_ate_agora']) if item['horas_ate_agora'] else '0:00:00'
            }
            
            if item['registro']:
                funcionario_data['registro'] = {
                    'entrada': item['registro'].hora_entrada.strftime('%H:%M') if item['registro'].hora_entrada else None,
                    'saida_almoco': item['registro'].hora_almoco_saida.strftime('%H:%M') if item['registro'].hora_almoco_saida else None,
                    'volta_almoco': item['registro'].hora_almoco_retorno.strftime('%H:%M') if item['registro'].hora_almoco_retorno else None,
                    'saida': item['registro'].hora_saida.strftime('%H:%M') if item['registro'].hora_saida else None,
                    'horas_trabalhadas': f"{item['registro'].horas_trabalhadas:.2f}" if item['registro'].horas_trabalhadas else None,
                    'horas_extras': f"{item['registro'].horas_extras:.2f}" if item['registro'].horas_extras else None,
                    'minutos_atraso': item['registro'].minutos_atraso_entrada if item['registro'].minutos_atraso_entrada else 0
                }
            else:
                funcionario_data['registro'] = None
            
            funcionarios_json.append(funcionario_data)
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_json,
            'timestamp': get_datetime_brasil().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro na API de status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/api/registrar-falta', methods=['POST'])
@login_required
@admin_required
def api_registrar_falta():
    """API para registrar falta de funcionário"""
    try:
        data = request.get_json()
        
        funcionario_id = data.get('funcionario_id')
        data_falta_str = data.get('data')
        data_falta = datetime.strptime(data_falta_str, '%Y-%m-%d').date()
        
        # ✅ FIX: Aceitar 'motivo' OU 'tipo_registro' para compatibilidade
        motivo = data.get('motivo') or data.get('tipo_registro', 'falta')  # 'falta' ou 'falta_justificada'
        observacoes = data.get('observacoes')
        
        logger.info(f"📝 Registrando falta: funcionario={funcionario_id}, data={data_falta}, tipo={motivo}")
        
        resultado = PontoService.registrar_falta(
            funcionario_id=funcionario_id,
            data_falta=data_falta,
            motivo=motivo,
            observacoes=observacoes
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Erro ao registrar falta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/relatorio/obra/<int:obra_id>')
@login_required
def relatorio_obra(obra_id):
    """Relatório de ponto da obra"""
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
        
        # Filtros de data
        data_inicio_str = request.args.get('data_inicio')
        data_fim_str = request.args.get('data_fim')
        
        if not data_inicio_str:
            data_inicio = date.today().replace(day=1)  # Primeiro dia do mês
        else:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        
        if not data_fim_str:
            data_fim = date.today()
        else:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        # Buscar registros do período
        registros = RegistroPonto.query.filter(
            RegistroPonto.obra_id == obra_id,
            RegistroPonto.admin_id == admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(
            RegistroPonto.data.desc(),
            RegistroPonto.funcionario_id
        ).all()
        
        # Agrupar por funcionário
        funcionarios_dados = {}
        for registro in registros:
            func_id = registro.funcionario_id
            if func_id not in funcionarios_dados:
                funcionarios_dados[func_id] = {
                    'funcionario': registro.funcionario,
                    'registros': [],
                    'total_horas': 0.0,
                    'total_extras': 0.0,
                    'total_faltas': 0,
                    'total_atrasados': 0
                }
            
            funcionarios_dados[func_id]['registros'].append(registro)
            
            if registro.horas_trabalhadas:
                funcionarios_dados[func_id]['total_horas'] += registro.horas_trabalhadas
            
            if registro.horas_extras:
                funcionarios_dados[func_id]['total_extras'] += registro.horas_extras
            
            if registro.tipo_registro in ['falta', 'falta_justificada']:
                funcionarios_dados[func_id]['total_faltas'] += 1
            
            if registro.minutos_atraso_entrada and registro.minutos_atraso_entrada > 0:
                funcionarios_dados[func_id]['total_atrasados'] += 1
        
        return render_template('ponto/relatorio_obra.html',
                             obra=obra,
                             funcionarios_dados=funcionarios_dados,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"Erro no relatório da obra: {e}")
        flash(f'Erro ao gerar relatório: {str(e)}', 'error')
        return redirect(url_for('ponto.obra_dashboard', obra_id=obra_id))


@ponto_bp.route('/configuracao/obra/<int:obra_id>')
@login_required
@admin_required
def configuracao_obra(obra_id):
    """Configuração de horários da obra"""
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
        
        # Buscar ou criar configuração
        config = ConfiguracaoHorario.query.filter_by(
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not config:
            config = ConfiguracaoHorario(
                obra_id=obra_id,
                admin_id=admin_id
            )
        
        return render_template('ponto/configuracao_obra.html',
                             obra=obra,
                             config=config)
        
    except Exception as e:
        logger.error(f"Erro na configuração da obra: {e}")
        flash(f'Erro ao carregar configuração: {str(e)}', 'error')
        return redirect(url_for('ponto.obra_dashboard', obra_id=obra_id))


@ponto_bp.route('/api/salvar-configuracao', methods=['POST'])
@login_required
@admin_required
def api_salvar_configuracao():
    """API para salvar configuração de horários"""
    try:
        data = request.get_json()
        admin_id = get_tenant_admin_id()
        
        obra_id = data.get('obra_id')
        entrada_padrao = datetime.strptime(data.get('entrada_padrao'), '%H:%M').time()
        saida_padrao = datetime.strptime(data.get('saida_padrao'), '%H:%M').time()
        almoco_inicio = datetime.strptime(data.get('almoco_inicio'), '%H:%M').time()
        almoco_fim = datetime.strptime(data.get('almoco_fim'), '%H:%M').time()
        tolerancia_atraso = int(data.get('tolerancia_atraso', 15))
        carga_horaria_diaria = int(data.get('carga_horaria_diaria', 480))
        
        # Buscar ou criar configuração
        config = ConfiguracaoHorario.query.filter_by(
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not config:
            config = ConfiguracaoHorario(
                obra_id=obra_id,
                admin_id=admin_id
            )
            db.session.add(config)
        
        config.entrada_padrao = entrada_padrao
        config.saida_padrao = saida_padrao
        config.almoco_inicio = almoco_inicio
        config.almoco_fim = almoco_fim
        config.tolerancia_atraso = tolerancia_atraso
        config.carga_horaria_diaria = carga_horaria_diaria
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuração salva com sucesso'})
        
    except Exception as e:
        logger.error(f"Erro ao salvar configuração: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/lista-obras')
@login_required
def lista_obras():
    """Lista de obras para seleção do ponto"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar obras ativas
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Total de funcionários ativos (qualquer um pode bater ponto em qualquer obra)
        total_funcionarios_ativos = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).count()
        
        # Contar funcionários que já bateram ponto hoje em cada obra
        obras_com_dados = []
        hoje = date.today()
        
        for obra in obras:
            registros_hoje = RegistroPonto.query.filter_by(
                obra_id=obra.id,
                data=hoje,
                admin_id=admin_id
            ).count()
            
            obras_com_dados.append({
                'obra': obra,
                'registros_hoje': registros_hoje,
                'total_funcionarios': total_funcionarios_ativos
            })
        
        return render_template('ponto/lista_obras.html',
                             obras_com_dados=obras_com_dados)
        
    except Exception as e:
        logger.error(f"Erro ao listar obras: {e}")
        flash(f'Erro ao carregar obras: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@ponto_bp.route('/configuracao/funcionario/<int:funcionario_id>/obras', methods=['GET', 'POST'])
@login_required
@admin_required
def configurar_obras_funcionario(funcionario_id):
    """Configurar quais obras aparecem no dropdown de ponto para o funcionário"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se funcionário existe e pertence ao admin
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first_or_404()
        
        if request.method == 'POST':
            # Receber lista de obras selecionadas
            obras_selecionadas = request.form.getlist('obras_ids')
            
            # Remover configurações antigas
            FuncionarioObrasPonto.query.filter_by(
                funcionario_id=funcionario_id,
                admin_id=admin_id
            ).delete()
            
            # Adicionar novas configurações
            for obra_id in obras_selecionadas:
                config = FuncionarioObrasPonto(
                    funcionario_id=funcionario_id,
                    obra_id=int(obra_id),
                    admin_id=admin_id,
                    ativo=True
                )
                db.session.add(config)
            
            db.session.commit()
            flash('Obras configuradas com sucesso!', 'success')
            return redirect(url_for('ponto.configurar_obras_funcionario', funcionario_id=funcionario_id))
        
        # GET - Mostrar formulário
        # Buscar todas as obras ativas
        todas_obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Buscar obras já configuradas para o funcionário
        obras_configuradas = FuncionarioObrasPonto.query.filter_by(
            funcionario_id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).all()
        
        obras_ids_selecionadas = [config.obra_id for config in obras_configuradas]
        
        return render_template('ponto/configurar_obras_funcionario.html',
                             funcionario=funcionario,
                             todas_obras=todas_obras,
                             obras_ids_selecionadas=obras_ids_selecionadas)
        
    except Exception as e:
        logger.error(f"Erro ao configurar obras do funcionário: {e}")
        flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('ponto.index'))


@ponto_bp.route('/configuracao/obras-funcionarios')
@login_required
@admin_required
def listar_configuracoes():
    """Lista todos os funcionários com suas obras configuradas"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar todos os funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Para cada funcionário, buscar obras configuradas
        funcionarios_configs = []
        for func in funcionarios:
            configs = FuncionarioObrasPonto.query.filter_by(
                funcionario_id=func.id,
                admin_id=admin_id,
                ativo=True
            ).all()
            
            obras = [config.obra for config in configs]
            
            funcionarios_configs.append({
                'funcionario': func,
                'obras_configuradas': obras,
                'total_obras': len(obras)
            })
        
        return render_template('ponto/listar_configuracoes.html',
                             funcionarios_configs=funcionarios_configs)
        
    except Exception as e:
        logger.error(f"Erro ao listar configurações: {e}")
        flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


# ================================
# IMPORTAÇÃO DE PONTOS VIA EXCEL
# ================================

@ponto_bp.route('/importar')
@login_required
@admin_required
def pagina_importar():
    """Página de importação de pontos via Excel"""
    return render_template('ponto/importar_ponto.html', now=get_datetime_brasil())


@ponto_bp.route('/importar/download-modelo')
@login_required
@admin_required
def download_modelo():
    """Gera e faz download da planilha modelo Excel com competência selecionada"""
    from services.ponto_importacao import PontoExcelService
    from flask import make_response
    from datetime import datetime
    
    try:
        admin_id = get_tenant_admin_id()
        
        # Parsear competência dos parâmetros (formato: YYYY-MM)
        competencia_str = request.args.get('competencia', '')
        mes_referencia = None
        
        if competencia_str:
            try:
                # Validar formato YYYY-MM
                ano, mes = competencia_str.split('-')
                ano = int(ano)
                mes = int(mes)
                
                # Validar valores
                if mes < 1 or mes > 12:
                    raise ValueError("Mês inválido")
                
                # Não permitir meses futuros
                hoje = date.today()
                if ano > hoje.year or (ano == hoje.year and mes > hoje.month):
                    flash('Não é possível gerar modelo para meses futuros.', 'warning')
                    ano, mes = hoje.year, hoje.month
                
                mes_referencia = date(ano, mes, 1)
                logger.info(f"Competência selecionada: {mes_referencia.strftime('%m/%Y')}")
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Competência inválida '{competencia_str}': {e}")
                mes_referencia = None
        
        # Se não especificado ou inválido, usar mês atual
        if mes_referencia is None:
            hoje = date.today()
            mes_referencia = date(hoje.year, hoje.month, 1)
            logger.info(f"Usando competência padrão (mês atual): {mes_referencia.strftime('%m/%Y')}")
        
        # Buscar funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.codigo).all()
        
        if not funcionarios:
            flash('Nenhum funcionário ativo encontrado para gerar o modelo.', 'warning')
            return redirect(url_for('ponto.pagina_importar'))
        
        # Buscar obras ativas
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Gerar planilha com obras e competência selecionada
        excel_buffer = PontoExcelService.gerar_planilha_modelo(funcionarios, obras, mes_referencia)
        
        # Criar response com nome do arquivo incluindo a competência
        filename = f'modelo_ponto_{mes_referencia.strftime("%Y%m")}.xlsx'
        response = make_response(excel_buffer.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        logger.info(f"Admin {admin_id} baixou modelo de importação para {mes_referencia.strftime('%m/%Y')} com {len(funcionarios)} funcionários")
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao gerar planilha modelo: {e}", exc_info=True)
        flash(f'Erro ao gerar planilha modelo: {str(e)}', 'error')
        return redirect(url_for('ponto.pagina_importar'))


@ponto_bp.route('/importar/processar', methods=['POST'])
@login_required
@admin_required
def processar_importacao():
    """Processa upload e importação da planilha Excel"""
    from services.ponto_importacao import PontoExcelService
    from werkzeug.utils import secure_filename
    from io import BytesIO
    
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se arquivo foi enviado
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo foi enviado.', 'error')
            return redirect(url_for('ponto.pagina_importar'))
        
        file = request.files['arquivo']
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('ponto.pagina_importar'))
        
        # Validar extensão
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            flash('Formato de arquivo inválido. Envie um arquivo Excel (.xlsx ou .xls).', 'error')
            return redirect(url_for('ponto.pagina_importar'))
        
        # Ler arquivo
        excel_file = BytesIO(file.read())
        
        # Criar mapa de funcionários ativos (código -> id)
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).all()
        
        funcionarios_map = {func.codigo: func.id for func in funcionarios}
        
        # Validar e preparar dados
        registros_validos, erros = PontoExcelService.validar_e_importar(
            excel_file,
            funcionarios_map,
            admin_id
        )
        
        # Importar registros válidos
        total_importados = 0
        total_duplicados = 0
        total_atualizados = 0
        
        for registro in registros_validos:
            # Verificar se já existe registro para este funcionário nesta data
            registro_existente = RegistroPonto.query.filter_by(
                funcionario_id=registro['funcionario_id'],
                data=registro['data'],
                admin_id=admin_id
            ).first()
            
            if registro_existente:
                # Atualizar registro existente
                registro_existente.hora_entrada = registro['hora_entrada']
                registro_existente.hora_saida = registro['hora_saida']
                registro_existente.hora_almoco_saida = registro['hora_almoco_saida']
                registro_existente.hora_almoco_retorno = registro['hora_almoco_retorno']
                total_atualizados += 1
            else:
                # Criar novo registro
                novo_registro = RegistroPonto(**registro)
                db.session.add(novo_registro)
                total_importados += 1
        
        # Commit
        db.session.commit()
        
        # Mensagem de resultado
        mensagens = []
        if total_importados > 0:
            mensagens.append(f"{total_importados} novos registros importados")
        if total_atualizados > 0:
            mensagens.append(f"{total_atualizados} registros atualizados")
        if erros:
            mensagens.append(f"{len(erros)} erros encontrados")
        
        if total_importados > 0 or total_atualizados > 0:
            flash(f"✅ Importação concluída: {', '.join(mensagens)}", 'success')
        
        if erros:
            # Limitar erros exibidos para não sobrecarregar a interface
            erros_exibir = erros[:10]
            for erro in erros_exibir:
                flash(f"⚠️ {erro}", 'warning')
            
            if len(erros) > 10:
                flash(f"... e mais {len(erros) - 10} erros.", 'warning')
        
        logger.info(
            f"Admin {admin_id} importou pontos: "
            f"{total_importados} novos, {total_atualizados} atualizados, {len(erros)} erros"
        )
        
        return redirect(url_for('ponto.pagina_importar'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao processar importação: {e}", exc_info=True)
        flash(f'Erro ao processar importação: {str(e)}', 'error')
        return redirect(url_for('ponto.pagina_importar'))


# ================================
# API DE RECONHECIMENTO FACIAL
# ================================

@ponto_bp.route('/api/registrar-facial', methods=['POST'])
@login_required
def registrar_ponto_facial_api():
    """API para registrar ponto com validação por reconhecimento facial"""
    try:
        data = request.get_json()
        funcionario_id = data.get('funcionario_id')
        foto_capturada_base64 = data.get('foto_base64')
        obra_id = data.get('obra_id')
        tipo_ponto_manual = data.get('tipo_ponto')  # Tipo selecionado manualmente pelo usuário
        
        if not funcionario_id or not foto_capturada_base64:
            return jsonify({
                'success': False, 
                'message': 'Dados incompletos. Funcionário e foto são obrigatórios.'
            }), 400
        
        MAX_BASE64_SIZE = 2 * 1024 * 1024
        if len(foto_capturada_base64) > MAX_BASE64_SIZE:
            return jsonify({
                'success': False, 
                'message': 'Foto muito grande. Máximo permitido: 2MB'
            }), 400
        
        admin_id = get_tenant_admin_id()
        
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not funcionario:
            return jsonify({
                'success': False, 
                'message': 'Funcionário não encontrado ou inativo.'
            }), 404
        
        if not funcionario.foto_base64:
            return jsonify({
                'success': False, 
                'message': f'{funcionario.nome} não possui foto cadastrada. Por favor, cadastre uma foto primeiro.'
            }), 400
        
        valido, msg_qualidade = validar_qualidade_foto(foto_capturada_base64)
        if not valido:
            return jsonify({
                'success': False, 
                'message': f'Foto inválida: {msg_qualidade}'
            }), 400
        
        match, distancia, erro_facial = comparar_faces_deepface(
            funcionario.foto_base64, 
            foto_capturada_base64,
            modelo='SFace'
        )
        
        if erro_facial:
            return jsonify({
                'success': False, 
                'message': erro_facial,
                'match': False
            }), 400
        
        THRESHOLD_DISTANCIA = 0.60
        
        if not match or distancia > THRESHOLD_DISTANCIA:
            logger.warning(
                f"Reconhecimento facial falhou para funcionário {funcionario_id}. "
                f"Match: {match}, Distância: {distancia:.4f}"
            )
            return jsonify({
                'success': False, 
                'message': f'Reconhecimento facial não confirmado. Tente novamente com melhor iluminação.',
                'match': False,
                'distancia': round(distancia, 4)
            }), 403
        
        hoje = get_date_brasil()
        agora = get_time_brasil()
        
        registro = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=hoje,
            admin_id=admin_id
        ).first()
        
        if not registro:
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                data=hoje,
                admin_id=admin_id,
                obra_id=obra_id
            )
            db.session.add(registro)
        
        tipo_registrado = None
        
        # Se tipo foi selecionado manualmente, usar esse
        if tipo_ponto_manual:
            if tipo_ponto_manual == 'entrada':
                if registro.hora_entrada:
                    return jsonify({
                        'success': False, 
                        'message': 'Entrada já foi registrada hoje.'
                    }), 400
                registro.hora_entrada = agora
                tipo_registrado = 'entrada'
            elif tipo_ponto_manual == 'almoco_saida':
                if registro.hora_almoco_saida:
                    return jsonify({
                        'success': False, 
                        'message': 'Saída para almoço já foi registrada hoje.'
                    }), 400
                registro.hora_almoco_saida = agora
                tipo_registrado = 'saída para almoço'
            elif tipo_ponto_manual == 'almoco_retorno':
                if registro.hora_almoco_retorno:
                    return jsonify({
                        'success': False, 
                        'message': 'Retorno do almoço já foi registrado hoje.'
                    }), 400
                registro.hora_almoco_retorno = agora
                tipo_registrado = 'retorno do almoço'
            elif tipo_ponto_manual == 'saida':
                if registro.hora_saida:
                    return jsonify({
                        'success': False, 
                        'message': 'Saída já foi registrada hoje.'
                    }), 400
                registro.hora_saida = agora
                tipo_registrado = 'saída'
        else:
            # Modo automático sequencial (fallback)
            if not registro.hora_entrada:
                registro.hora_entrada = agora
                tipo_registrado = 'entrada'
            elif registro.hora_entrada and not registro.hora_almoco_saida:
                registro.hora_almoco_saida = agora
                tipo_registrado = 'saída para almoço'
            elif registro.hora_almoco_saida and not registro.hora_almoco_retorno:
                registro.hora_almoco_retorno = agora
                tipo_registrado = 'retorno do almoço'
            elif not registro.hora_saida:
                registro.hora_saida = agora
                tipo_registrado = 'saída'
            else:
                return jsonify({
                    'success': False, 
                    'message': 'Jornada completa já registrada para hoje. Todos os horários já foram preenchidos.'
                }), 400
        
        registro.foto_registro_base64 = None
        registro.reconhecimento_facial_sucesso = True
        registro.confianca_reconhecimento = distancia
        registro.modelo_utilizado = 'SFace'
        
        db.session.commit()
        
        logger.info(
            f"Ponto registrado com reconhecimento facial: "
            f"Funcionário {funcionario.nome} ({funcionario_id}), "
            f"Tipo: {tipo_registrado}, Distância: {distancia:.4f}"
        )
        
        return jsonify({
            'success': True,
            'message': f'Ponto de {tipo_registrado} registrado com sucesso para {funcionario.nome}!',
            'tipo_registrado': tipo_registrado,
            'hora': agora.strftime('%H:%M:%S'),
            'distancia': round(distancia, 4),
            'match': True
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao registrar ponto facial: {e}", exc_info=True)
        return jsonify({
            'success': False, 
            'message': f'Erro ao processar reconhecimento: {str(e)}'
        }), 500


@ponto_bp.route('/api/verificar-foto-funcionario/<int:funcionario_id>')
@login_required
def verificar_foto_funcionario(funcionario_id):
    """Verifica se funcionário tem foto cadastrada para reconhecimento facial"""
    try:
        admin_id = get_tenant_admin_id()
        
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first()
        
        if not funcionario:
            return jsonify({'success': False, 'tem_foto': False, 'message': 'Funcionário não encontrado'})
        
        tem_foto = bool(funcionario.foto_base64)
        
        return jsonify({
            'success': True,
            'tem_foto': tem_foto,
            'funcionario_nome': funcionario.nome,
            'message': 'Foto disponível' if tem_foto else f'{funcionario.nome} não possui foto cadastrada'
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar foto do funcionário: {e}")
        return jsonify({'success': False, 'tem_foto': False, 'message': str(e)})


# ================================
# IDENTIFICAÇÃO FACIAL AUTOMÁTICA
# ================================

@ponto_bp.route('/facial')
@login_required
def ponto_facial_automatico():
    """Página de ponto por reconhecimento facial automático"""
    try:
        preload_deepface_model()
        carregar_cache_facial()
        
        admin_id = get_tenant_admin_id()
        
        # Buscar obras ativas para seleção
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Contar funcionários com foto cadastrada
        funcionarios_com_foto = Funcionario.query.filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            Funcionario.foto_base64 != None,
            Funcionario.foto_base64 != ''
        ).count()
        
        return render_template('ponto/ponto_facial_automatico.html',
                             obras=obras,
                             funcionarios_com_foto=funcionarios_com_foto)
        
    except Exception as e:
        logger.error(f"Erro ao carregar página de ponto facial: {e}")
        flash(f'Erro ao carregar página: {str(e)}', 'error')
        return redirect(url_for('ponto.index'))


@ponto_bp.route('/api/cache/gerar', methods=['POST'])
@login_required
@admin_required
def gerar_cache_embeddings():
    """API para gerar/regenerar cache de embeddings faciais"""
    try:
        from gerar_cache_facial import gerar_cache, CACHE_PATH
        admin_id = get_tenant_admin_id()
        
        # Opção para incluir fotos inativas (via query parameter)
        incluir_inativas = request.args.get('incluir_inativas', 'false').lower() == 'true'
        
        logger.info(f"🔄 INICIANDO geração de cache facial para admin_id={admin_id}")
        logger.info(f"📁 Cache será salvo em: {CACHE_PATH}")
        logger.info(f"📸 Incluir fotos inativas: {incluir_inativas}")
        
        resultado = gerar_cache(admin_id, incluir_inativas=incluir_inativas)
        
        logger.info(f"📊 Resultado: {resultado}")
        
        if resultado['success']:
            import os
            if os.path.exists(CACHE_PATH):
                size = os.path.getsize(CACHE_PATH)
                mtime = os.path.getmtime(CACHE_PATH)
                import datetime
                mod_time = datetime.datetime.fromtimestamp(mtime)
                logger.info(f"✅ Cache salvo: {size} bytes, modificado em {mod_time}")
            else:
                logger.error(f"❌ ERRO: Arquivo de cache não foi criado em {CACHE_PATH}")
            
            recarregar_cache_facial()
            
            cache_reload = carregar_cache_facial()
            if cache_reload:
                total_in_memory = len(cache_reload.get('embeddings', {}))
                logger.info(f"✅ Cache recarregado na memória: {total_in_memory} funcionários")
            
            return jsonify({
                'success': True,
                'message': f"Cache gerado com sucesso! {resultado['processados']} funcionários processados.",
                'processados': resultado['processados'],
                'total': resultado['total'],
                'erros': len(resultado.get('erros', [])),
                'cache_path': str(CACHE_PATH)
            })
        else:
            logger.error(f"❌ Erro na geração: {resultado.get('error')}")
            return jsonify({
                'success': False,
                'message': resultado.get('error', 'Erro desconhecido')
            }), 500
            
    except Exception as e:
        logger.error(f"❌ EXCEÇÃO ao gerar cache: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Erro ao gerar cache: {str(e)}'
        }), 500


@ponto_bp.route('/api/cache/status', methods=['GET'])
@login_required
def status_cache_embeddings():
    """API para verificar status do cache de embeddings"""
    try:
        admin_id = get_tenant_admin_id()
        admin_id_int = int(admin_id) if admin_id else None
        
        logger.debug(f"🔍 Status cache - admin_id: {admin_id} (type: {type(admin_id).__name__})")
        
        cache = carregar_cache_facial()
        
        if not cache:
            logger.warning("⚠️ Cache não encontrado no arquivo")
            return jsonify({
                'disponivel': False,
                'message': 'Cache não encontrado. Gere o cache primeiro.'
            })
        
        all_embeddings = cache.get('embeddings', {})
        logger.debug(f"📊 Cache total: {len(all_embeddings)} funcionários")
        
        embeddings_tenant = {}
        for fid, data in all_embeddings.items():
            cache_admin_id = data.get('admin_id')
            cache_admin_id_int = int(cache_admin_id) if cache_admin_id is not None else None
            
            if cache_admin_id_int == admin_id_int:
                embeddings_tenant[fid] = data
                logger.debug(f"  ✅ Match: Func {fid} ({data.get('nome')}) - admin_id={cache_admin_id}")
            else:
                logger.debug(f"  ❌ Skip: Func {fid} - admin_id={cache_admin_id} != {admin_id_int}")
        
        total_fotos = sum(len(data.get('embeddings', [])) for data in embeddings_tenant.values())
        
        # Calcular média de fotos por funcionário
        media_fotos = total_fotos / len(embeddings_tenant) if len(embeddings_tenant) > 0 else 0
        
        # Adicionar aviso se média baixa
        aviso = None
        if len(embeddings_tenant) > 0 and media_fotos < 3:
            aviso = {
                'tipo': 'warning',
                'mensagem': f'Média de {media_fotos:.1f} fotos por funcionário. Recomendado: 3-5 fotos para melhor precisão.'
            }
        
        logger.info(f"📊 Cache status: {len(embeddings_tenant)} funcionários, {total_fotos} fotos (média: {media_fotos:.1f}) para admin_id={admin_id_int}")
        
        return jsonify({
            'disponivel': True,
            'versao': cache.get('versao', '1.0'),
            'gerado_em': cache.get('gerado_em', cache.get('generated_at')),
            'modelo': cache.get('modelo', cache.get('model', 'SFace')),
            'total_embeddings': len(embeddings_tenant),
            'total_fotos': total_fotos,
            'media_fotos': round(media_fotos, 1),
            'aviso': aviso,
            'funcionarios': [
                {
                    'id': fid, 
                    'nome': data.get('nome', 'N/A'), 
                    'fotos': len(data.get('embeddings', []))
                }
                for fid, data in embeddings_tenant.items()
            ],
            'debug': {
                'admin_id_logado': admin_id_int,
                'total_cache': len(all_embeddings)
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no status cache: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'disponivel': False,
            'message': f'Erro: {str(e)}'
        }), 500


@ponto_bp.route('/api/cache/verificar')
@login_required
def verificar_cache():
    """Verifica compatibilidade do cache comparando embedding ao vivo vs cacheado"""
    import time
    
    admin_id = get_tenant_admin_id()
    cache = carregar_cache_facial()
    
    if not cache or 'embeddings' not in cache:
        return jsonify({'status': 'error', 'message': 'Cache não disponível'}), 404
    
    cache_version = cache.get('pipeline_version', cache.get('versao', 'unknown'))
    results = {
        'cache_version': cache_version,
        'current_pipeline': PIPELINE_VERSION,
        'compatible': cache_version == PIPELINE_VERSION,
        'generated_at': cache.get('generated_at', 'unknown'),
        'total_funcionarios': len(cache.get('embeddings', {})),
        'verificacoes': []
    }
    
    embeddings_cache = cache['embeddings']
    admin_id_int = int(admin_id) if admin_id else None
    
    tested = 0
    for func_id, data in embeddings_cache.items():
        cache_admin_id = int(data.get('admin_id', 0)) if data.get('admin_id') is not None else None
        if cache_admin_id != admin_id_int:
            continue
        if tested >= 2:
            break
            
        embs = data.get('embeddings', [])
        if not embs:
            continue
        
        first_emb = embs[0]
        cached_emb = np.array(first_emb['embedding'] if isinstance(first_emb, dict) else first_emb, dtype=np.float32)
        cached_norm = float(np.linalg.norm(cached_emb))
        
        func = Funcionario.query.get(func_id)
        if not func:
            continue
        
        fotos = FotoFacialFuncionario.query.filter_by(
            funcionario_id=func_id, admin_id=admin_id_int, ativa=True
        ).order_by(FotoFacialFuncionario.ordem).first()
        
        if not fotos:
            continue
        
        try:
            foto_b64 = fotos.foto_base64
            if foto_b64.startswith('data:'):
                foto_b64 = foto_b64.split(',')[1]
            
            foto_bytes = base64.b64decode(foto_b64)
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(foto_bytes)
                tmp_path = tmp.name
            
            try:
                start = time.time()
                fresh_emb_list = gerar_embedding_otimizado(tmp_path)
                elapsed = time.time() - start
                
                if fresh_emb_list:
                    fresh_emb = np.array(fresh_emb_list, dtype=np.float32)
                    fresh_norm = float(np.linalg.norm(fresh_emb))
                    
                    if cached_norm > 0:
                        cached_normalized = cached_emb / cached_norm
                    else:
                        cached_normalized = cached_emb
                    if fresh_norm > 0:
                        fresh_normalized = fresh_emb / fresh_norm
                    else:
                        fresh_normalized = fresh_emb
                    
                    dist = float(np.linalg.norm(fresh_normalized - cached_normalized))
                    
                    results['verificacoes'].append({
                        'func_id': func_id,
                        'nome': data.get('nome', '?'),
                        'distancia_cache_vs_live': round(dist, 4),
                        'cached_norm': round(cached_norm, 4),
                        'fresh_norm': round(fresh_norm, 4),
                        'tempo_embedding': round(elapsed, 3),
                        'compativel': dist < 0.3,
                        'cached_first3': cached_emb[:3].tolist(),
                        'fresh_first3': fresh_emb[:3].tolist()
                    })
                    tested += 1
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            results['verificacoes'].append({
                'func_id': func_id,
                'nome': data.get('nome', '?'),
                'erro': str(e)
            })
            tested += 1
    
    if results['verificacoes']:
        all_compatible = all(v.get('compativel', False) for v in results['verificacoes'] if 'erro' not in v)
        results['status'] = 'compatible' if all_compatible else 'INCOMPATIBLE - regenerate cache!'
    else:
        results['status'] = 'no_data_to_verify'
    
    return jsonify(results)


@ponto_bp.route('/api/cache/validar', methods=['GET'])
@login_required
def validar_cache_embeddings():
    """API para validar o cache de embeddings faciais"""
    try:
        from gerar_cache_facial import validar_cache
        
        resultado = validar_cache()
        
        if resultado.get('valid'):
            return jsonify({
                'success': True,
                'message': 'Cache válido!',
                **resultado
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado.get('error', 'Cache inválido'),
                **resultado
            }), 400
            
    except Exception as e:
        logger.error(f"❌ Erro ao validar cache: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro: {str(e)}'
        }), 500


@ponto_bp.route('/api/cache/debug', methods=['GET'])
@login_required
@admin_required
def debug_cache_embeddings():
    """API de debug para mostrar estrutura completa do cache"""
    try:
        admin_id = get_tenant_admin_id()
        admin_id_int = int(admin_id) if admin_id else None
        
        cache = carregar_cache_facial()
        
        if not cache:
            return jsonify({
                'error': 'Cache não encontrado',
                'admin_id_logado': admin_id_int
            }), 404
        
        all_embeddings = cache.get('embeddings', {})
        
        # Coletar todos os admin_ids únicos no cache
        admin_ids_no_cache = {}
        for fid, data in all_embeddings.items():
            aid = data.get('admin_id')
            aid_int = int(aid) if aid is not None else None
            if aid_int not in admin_ids_no_cache:
                admin_ids_no_cache[aid_int] = []
            admin_ids_no_cache[aid_int].append({
                'id': fid,
                'nome': data.get('nome', 'N/A'),
                'fotos': len(data.get('embeddings', []))
            })
        
        return jsonify({
            'admin_id_logado': admin_id_int,
            'versao': cache.get('versao', '1.0'),
            'metodo': cache.get('method', 'desconhecido'),
            'normalizado': cache.get('normalized', False),
            'generated_at': cache.get('generated_at'),
            'total_funcionarios_cache': len(all_embeddings),
            'admin_ids_no_cache': {
                str(k): {
                    'total': len(v),
                    'funcionarios': v
                } for k, v in admin_ids_no_cache.items()
            },
            'match_atual': admin_id_int in admin_ids_no_cache
        })
        
    except Exception as e:
        logger.error(f"❌ Erro debug cache: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'error': str(e)
        }), 500


@ponto_bp.route('/api/identificar-e-registrar', methods=['POST'])
@login_required
def identificar_e_registrar():
    """API para identificar funcionário automaticamente e registrar ponto"""
    import time
    start_total = time.time()
    logger.info(f"🚀 ========== INÍCIO identificar-e-registrar ==========")
    
    try:
        # NOTA: preload_deepface_model() removido - já é executado no startup!
        # O modelo está pré-carregado em memória desde a inicialização do servidor
        
        if not request.is_json:
            return jsonify({
                'success': False, 
                'message': 'Requisição inválida. Envie os dados em formato JSON.'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False, 
                'message': 'Dados não recebidos. Por favor, tente novamente.'
            }), 400
        
        foto_capturada_base64 = data.get('foto_base64')
        obra_id = data.get('obra_id')
        tipo_ponto = data.get('tipo_ponto')  # entrada, almoco_saida, almoco_retorno, saida
        
        # Campos de geolocalização
        latitude_func = data.get('latitude')
        longitude_func = data.get('longitude')
        
        if not foto_capturada_base64:
            return jsonify({
                'success': False, 
                'message': 'Foto não recebida. Por favor, tire uma foto.'
            }), 400
        
        # Validar tamanho da foto
        MAX_BASE64_SIZE = 2 * 1024 * 1024
        if len(foto_capturada_base64) > MAX_BASE64_SIZE:
            return jsonify({
                'success': False, 
                'message': 'Foto muito grande. Máximo permitido: 2MB'
            }), 400
        
        admin_id = get_tenant_admin_id()
        
        # Validar obra_id pertence ao tenant (se fornecido)
        if obra_id:
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra:
                obra_id = None  # Ignorar obra inválida em vez de falhar
        
        # Buscar todos os funcionários ativos (com foto na tabela principal OU na tabela de múltiplas fotos)
        funcionarios_com_foto_principal = Funcionario.query.filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            Funcionario.foto_base64 != None,
            Funcionario.foto_base64 != ''
        ).all()
        
        # Também buscar funcionários que têm fotos na nova tabela de múltiplas fotos
        funcionarios_com_multiplas_fotos = db.session.query(Funcionario).join(
            FotoFacialFuncionario,
            Funcionario.id == FotoFacialFuncionario.funcionario_id
        ).filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            FotoFacialFuncionario.ativa == True
        ).distinct().all()
        
        # Combinar listas sem duplicatas
        funcionarios_ids = set()
        funcionarios = []
        for f in funcionarios_com_foto_principal + funcionarios_com_multiplas_fotos:
            if f.id not in funcionarios_ids:
                funcionarios_ids.add(f.id)
                funcionarios.append(f)
        
        if not funcionarios:
            return jsonify({
                'success': False, 
                'message': 'Nenhum funcionário com foto cadastrada. Cadastre fotos dos funcionários primeiro.'
            }), 404
        
        # Validar qualidade da foto capturada (versão avançada)
        logger.info(f"⏱️ Iniciando validação de qualidade da foto...")
        start_validacao = time.time()
        valido, msg_qualidade, detalhes = validar_qualidade_foto_avancada(foto_capturada_base64)
        elapsed_validacao = time.time() - start_validacao
        logger.info(f"⏱️ Validação de qualidade: {elapsed_validacao:.3f}s (válido: {valido})")
        if not valido:
            return jsonify({
                'success': False, 
                'message': f'Foto inválida: {msg_qualidade}',
                'detalhes': detalhes
            }), 400
        
        # Usar threshold mais rigoroso para evitar falsos positivos (era 0.55)
        THRESHOLD_DISTANCIA = THRESHOLD_CONFIANCA  # 0.40
        melhor_match = None
        menor_distancia = float('inf')
        
        # OTIMIZAÇÃO: Tentar identificação via cache primeiro (muito mais rápido)
        start_cache = time.time()
        logger.info("⏱️ [CACHE] Tentando identificação via cache de embeddings...")
        func_id, distancia_cache, erro_cache = identificar_por_cache(
            foto_capturada_base64, admin_id, THRESHOLD_DISTANCIA
        )
        cache_elapsed = time.time() - start_cache
        
        if func_id and not erro_cache:
            # IMPORTANTE: Validar que o funcionário pertence ao tenant correto
            melhor_match = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
            if melhor_match:
                menor_distancia = distancia_cache
                logger.info(f"✅ [CACHE HIT] Identificado via cache em {cache_elapsed:.2f}s: {melhor_match.nome} (dist: {distancia_cache:.4f})")
            else:
                logger.warning(f"⚠️ [CACHE] func_id={func_id} não pertence ao tenant {admin_id}")
                erro_cache = "Funcionário não encontrado no tenant"
        else:
            logger.warning(f"⚠️ [CACHE MISS] Cache falhou em {cache_elapsed:.2f}s - motivo: {erro_cache}")
        
        # FALLBACK: Método com múltiplas fotos se cache não disponível ou falhou
        if erro_cache or not melhor_match:
            logger.warning(f"🐌 [FALLBACK] Usando método LENTO com múltiplas fotos (cache indisponível: {erro_cache})")
            logger.info(f"🐌 [FALLBACK] Comparando com {len(funcionarios)} funcionários um a um...")
            
            for funcionario in funcionarios:
                try:
                    # Usar nova função que compara com TODAS as fotos do funcionário
                    match, distancia, foto_desc = reconhecer_com_multiplas_fotos(
                        foto_capturada_base64,
                        funcionario,
                        threshold=THRESHOLD_DISTANCIA
                    )
                    
                    logger.debug(f"Comparação com {funcionario.nome}: match={match}, distância={distancia:.4f}, foto={foto_desc}")
                    
                    if match and distancia < menor_distancia:
                        menor_distancia = distancia
                        melhor_match = funcionario
                        logger.info(f"Novo melhor match: {funcionario.nome} via '{foto_desc}' (dist: {distancia:.4f})")
                        
                except Exception as e:
                    logger.warning(f"Falha ao comparar com funcionário {funcionario.id}: {e}")
                    continue
        
        # Verificar se encontrou match válido
        if not melhor_match or menor_distancia > THRESHOLD_DISTANCIA:
            logger.warning(f"Identificação falhou. Melhor distância: {menor_distancia:.4f}")
            return jsonify({
                'success': False, 
                'message': 'Funcionário não identificado. Tente novamente com melhor iluminação ou registre manualmente.',
                'distancia': round(menor_distancia, 4) if menor_distancia != float('inf') else None
            }), 404
        
        funcionario = melhor_match
        logger.info(f"Funcionário identificado: {funcionario.nome} (distância: {menor_distancia:.4f})")
        
        # GEOFENCING: Validar localização se obra tiver coordenadas
        distancia_obra = None
        if obra_id and latitude_func is not None and longitude_func is not None:
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if obra:
                valido_geo, distancia_obra, msg_geo = validar_localizacao_na_obra(
                    latitude_func, longitude_func, obra
                )
                logger.info(f"Geofencing para {funcionario.nome}: {msg_geo}")
                
                if not valido_geo:
                    return jsonify({
                        'success': False,
                        'message': f'Você está fora da área permitida da obra. {msg_geo}',
                        'funcionario_nome': funcionario.nome,
                        'distancia_obra': round(distancia_obra, 1) if distancia_obra else None
                    }), 403
        
        # Registrar o ponto
        hoje = get_date_brasil()
        agora = get_time_brasil()
        
        registro = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=hoje,
            admin_id=admin_id
        ).first()
        
        if not registro:
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                data=hoje,
                admin_id=admin_id,
                obra_id=obra_id,
                latitude=latitude_func,
                longitude=longitude_func,
                distancia_obra_metros=distancia_obra
            )
            db.session.add(registro)
        else:
            # Atualizar localização se fornecida
            if latitude_func is not None:
                registro.latitude = latitude_func
            if longitude_func is not None:
                registro.longitude = longitude_func
            if distancia_obra is not None:
                registro.distancia_obra_metros = distancia_obra
        
        tipo_registrado = None
        
        # Se tipo foi selecionado manualmente, usar esse
        if tipo_ponto:
            if tipo_ponto == 'entrada':
                if registro.hora_entrada:
                    return jsonify({
                        'success': False, 
                        'message': f'{funcionario.nome}: Entrada já foi registrada hoje.',
                        'funcionario_nome': funcionario.nome
                    }), 400
                registro.hora_entrada = agora
                tipo_registrado = 'entrada'
            elif tipo_ponto == 'almoco_saida':
                if registro.hora_almoco_saida:
                    return jsonify({
                        'success': False, 
                        'message': f'{funcionario.nome}: Saída para almoço já foi registrada hoje.',
                        'funcionario_nome': funcionario.nome
                    }), 400
                registro.hora_almoco_saida = agora
                tipo_registrado = 'saída para almoço'
            elif tipo_ponto == 'almoco_retorno':
                if registro.hora_almoco_retorno:
                    return jsonify({
                        'success': False, 
                        'message': f'{funcionario.nome}: Retorno do almoço já foi registrado hoje.',
                        'funcionario_nome': funcionario.nome
                    }), 400
                registro.hora_almoco_retorno = agora
                tipo_registrado = 'retorno do almoço'
            elif tipo_ponto == 'saida':
                if registro.hora_saida:
                    return jsonify({
                        'success': False, 
                        'message': f'{funcionario.nome}: Saída já foi registrada hoje.',
                        'funcionario_nome': funcionario.nome
                    }), 400
                registro.hora_saida = agora
                tipo_registrado = 'saída'
        else:
            # Modo automático sequencial
            if not registro.hora_entrada:
                registro.hora_entrada = agora
                tipo_registrado = 'entrada'
            elif registro.hora_entrada and not registro.hora_almoco_saida:
                registro.hora_almoco_saida = agora
                tipo_registrado = 'saída para almoço'
            elif registro.hora_almoco_saida and not registro.hora_almoco_retorno:
                registro.hora_almoco_retorno = agora
                tipo_registrado = 'retorno do almoço'
            elif not registro.hora_saida:
                registro.hora_saida = agora
                tipo_registrado = 'saída'
            else:
                return jsonify({
                    'success': False, 
                    'message': f'{funcionario.nome}: Jornada completa já registrada hoje.',
                    'funcionario_nome': funcionario.nome
                }), 400
        
        # Salvar metadados do reconhecimento
        registro.reconhecimento_facial_sucesso = True
        registro.confianca_reconhecimento = menor_distancia
        registro.modelo_utilizado = 'SFace'
        
        db.session.commit()
        
        tempo_total = time.time() - start_total
        
        # Log de performance com indicador visual
        if tempo_total < 2.0:
            logger.info(f"⚡ RECONHECIMENTO RÁPIDO: {tempo_total:.2f}s - {funcionario.nome}")
        elif tempo_total < 5.0:
            logger.warning(f"⚠️ RECONHECIMENTO MÉDIO: {tempo_total:.2f}s - {funcionario.nome}")
        else:
            logger.warning(f"🐌 RECONHECIMENTO LENTO: {tempo_total:.2f}s - {funcionario.nome} - Investigar!")
        
        logger.info(
            f"Ponto registrado: {funcionario.nome} ({funcionario.id}), "
            f"Tipo: {tipo_registrado}, Distância: {menor_distancia:.4f}, Tempo: {tempo_total:.2f}s"
        )
        
        logger.info(f"✅ ========== FIM identificar-e-registrar (SUCESSO) em {tempo_total:.2f}s ==========")
        
        return jsonify({
            'success': True,
            'message': f'{funcionario.nome}: {tipo_registrado} registrado(a) com sucesso!',
            'funcionario_id': funcionario.id,
            'funcionario_nome': funcionario.nome,
            'funcionario_codigo': funcionario.codigo,
            'tipo_registrado': tipo_registrado,
            'hora': agora.strftime('%H:%M:%S'),
            'distancia': round(menor_distancia, 4),
            'distancia_obra': round(distancia_obra, 1) if distancia_obra else None,
            'tempo_processamento': round(tempo_total, 2)
        })
        
    except Exception as e:
        elapsed = time.time() - start_total
        db.session.rollback()
        logger.error(f"Erro na identificação facial automática: {e}", exc_info=True)
        logger.error(f"❌ ========== FIM identificar-e-registrar (ERRO) em {elapsed:.2f}s ==========")
        return jsonify({
            'success': False, 
            'message': f'Erro ao processar identificação: {str(e)}'
        }), 500


# ================================
# GERENCIAMENTO DE FOTOS FACIAIS
# ================================

@ponto_bp.route('/gerenciar-fotos-faciais')
@login_required
def listar_funcionarios_fotos_faciais():
    """Lista todos os funcionários para gerenciar fotos faciais"""
    admin_id = get_tenant_admin_id()
    
    funcionarios = Funcionario.query.filter_by(
        admin_id=admin_id,
        ativo=True
    ).order_by(Funcionario.nome).all()
    
    # Contagem de fotos para cada funcionário
    for func in funcionarios:
        func.qtd_fotos = FotoFacialFuncionario.query.filter_by(
            funcionario_id=func.id,
            admin_id=admin_id,
            ativa=True
        ).count()
    
    return render_template(
        'ponto/gerenciar_fotos_lista.html',
        funcionarios=funcionarios,
        titulo='Gerenciar Fotos Faciais'
    )


@ponto_bp.route('/funcionario/<int:funcionario_id>/fotos-faciais')
@login_required
def gerenciar_fotos_faciais(funcionario_id):
    """Página para gerenciar múltiplas fotos faciais de um funcionário"""
    admin_id = get_tenant_admin_id()
    
    funcionario = Funcionario.query.filter_by(
        id=funcionario_id,
        admin_id=admin_id
    ).first_or_404()
    
    fotos = FotoFacialFuncionario.query.filter_by(
        funcionario_id=funcionario_id,
        admin_id=admin_id
    ).order_by(FotoFacialFuncionario.ordem, FotoFacialFuncionario.created_at).all()
    
    return render_template(
        'ponto/gerenciar_fotos_faciais.html',
        funcionario=funcionario,
        fotos=fotos
    )


@ponto_bp.route('/api/funcionario/<int:funcionario_id>/foto-facial', methods=['POST'])
@login_required
def adicionar_foto_facial(funcionario_id):
    """Adiciona uma nova foto facial para o funcionário"""
    admin_id = get_tenant_admin_id()
    
    funcionario = Funcionario.query.filter_by(
        id=funcionario_id,
        admin_id=admin_id
    ).first()
    
    if not funcionario:
        return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
    
    try:
        data = request.get_json()
        foto_base64 = data.get('foto_base64')
        descricao = data.get('descricao', '').strip()
        
        if not foto_base64:
            return jsonify({'success': False, 'message': 'Foto não fornecida'}), 400
        
        valida, mensagem, detalhes = validar_qualidade_foto_avancada(foto_base64)
        if not valida:
            return jsonify({
                'success': False, 
                'message': mensagem,
                'detalhes': detalhes
            }), 400
        
        ultima_ordem = db.session.query(db.func.max(FotoFacialFuncionario.ordem)).filter_by(
            funcionario_id=funcionario_id,
            admin_id=admin_id
        ).scalar() or 0
        
        nova_foto = FotoFacialFuncionario(
            funcionario_id=funcionario_id,
            foto_base64=foto_base64,
            descricao=descricao or f'Foto {ultima_ordem + 1}',
            ordem=ultima_ordem + 1,
            ativa=True,
            admin_id=admin_id
        )
        
        db.session.add(nova_foto)
        db.session.commit()
        
        recarregar_cache_facial()
        
        logger.info(f"Nova foto facial adicionada para funcionário {funcionario.nome} (ID: {funcionario_id})")
        
        return jsonify({
            'success': True,
            'message': 'Foto adicionada com sucesso',
            'foto_id': nova_foto.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao adicionar foto facial: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Erro ao salvar foto: {str(e)}'}), 500


@ponto_bp.route('/api/foto-facial/<int:foto_id>', methods=['DELETE'])
@login_required
def excluir_foto_facial(foto_id):
    """Exclui uma foto facial"""
    admin_id = get_tenant_admin_id()
    
    foto = FotoFacialFuncionario.query.filter_by(
        id=foto_id,
        admin_id=admin_id
    ).first()
    
    if not foto:
        return jsonify({'success': False, 'message': 'Foto não encontrada'}), 404
    
    try:
        funcionario_id = foto.funcionario_id
        db.session.delete(foto)
        db.session.commit()
        
        recarregar_cache_facial()
        
        logger.info(f"Foto facial {foto_id} excluída do funcionário {funcionario_id}")
        
        return jsonify({'success': True, 'message': 'Foto excluída com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir foto facial: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Erro ao excluir foto: {str(e)}'}), 500


@ponto_bp.route('/api/foto-facial/<int:foto_id>/ativar', methods=['POST'])
@login_required
def ativar_foto_facial(foto_id):
    """Ativa ou desativa uma foto facial"""
    admin_id = get_tenant_admin_id()
    
    foto = FotoFacialFuncionario.query.filter_by(
        id=foto_id,
        admin_id=admin_id
    ).first()
    
    if not foto:
        return jsonify({'success': False, 'message': 'Foto não encontrada'}), 404
    
    try:
        foto.ativa = not foto.ativa
        db.session.commit()
        
        recarregar_cache_facial()
        
        status = 'ativada' if foto.ativa else 'desativada'
        logger.info(f"Foto facial {foto_id} {status}")
        
        return jsonify({
            'success': True,
            'message': f'Foto {status} com sucesso',
            'ativa': foto.ativa
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao ativar/desativar foto facial: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Erro ao atualizar foto: {str(e)}'}), 500
