"""
Utilitários para Reconhecimento Facial — SFace nativo via OpenCV
SIGE v9.0 - Sistema de Gestão Empresarial

Trocado em 01/09/2026 (Task 8, plano as-decisoes-viram-codigo): o miolo
saiu do DeepFace para `utils_facial_sface` (cv2.FaceRecognizerSF sobre o
MESMO modelo SFace — equivalência medida em
tests/test_sface_nativo_equivalencia.py). Os nomes públicos ficaram —
`comparar_faces_deepface` inclusive — para os chamadores não mudarem.
"""

import base64
import io
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

def decodificar_base64_para_numpy(base64_string):
    """
    Decodifica uma imagem em base64 para um array numpy.
    Aceita formatos com ou sem prefixo data:image/...
    """
    try:
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
        
        img_data = base64.b64decode(base64_string)
        img = Image.open(io.BytesIO(img_data))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        return np.array(img)
    except Exception as e:
        logger.error(f"Erro ao decodificar imagem base64: {e}")
        return None

_cascade_haar = None  # cache do detector (o mesmo backend 'opencv' de antes)


def _get_cascade_haar():
    global _cascade_haar
    if _cascade_haar is None:
        import cv2
        _cascade_haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    return _cascade_haar


def _recortar_rosto_bgr(img_rgb):
    """RGB numpy → BGR recortado no maior rosto (Haar, margem de 20% —
    o mesmo recorte de ponto_views.gerar_embedding_otimizado). Sem rosto
    detectado, devolve a imagem inteira — espelho do
    `enforce_detection=False` do caminho DeepFace antigo."""
    import cv2
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    faces = _get_cascade_haar().detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return img_bgr
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    margem = 0.2
    alt, larg = img_bgr.shape[:2]
    x1 = max(0, int(x - w * margem))
    y1 = max(0, int(y - h * margem))
    x2 = min(larg, int(x + w + w * margem))
    y2 = min(alt, int(y + h + h * margem))
    return img_bgr[y1:y2, x1:x2]


def comparar_faces_deepface(foto_cadastro_base64, foto_capturada_base64, modelo='SFace'):
    """
    Compara duas imagens em base64 — SFace nativo (nome mantido: o miolo
    trocou em 01/09/2026, os chamadores não).

    Args:
        foto_cadastro_base64: Foto cadastrada do funcionário em base64
        foto_capturada_base64: Foto capturada no momento do registro em base64
        modelo: mantido por compatibilidade de assinatura; só SFace existe

    Returns:
        tuple: (match: bool, distancia: float, erro: str|None)
               - match: True se as faces são da mesma pessoa
               - distancia: distância de cosseno (quanto menor, mais
                 similar — mesma escala que o DeepFace.verify devolvia)
               - erro: Mensagem de erro se houver problema na detecção
    """
    try:
        from utils_facial_sface import (LIMIAR_COSSENO,
                                        comparar_embeddings_sface,
                                        gerar_embedding_sface)

        img1 = decodificar_base64_para_numpy(foto_cadastro_base64)
        img2 = decodificar_base64_para_numpy(foto_capturada_base64)

        if img1 is None or img2 is None:
            logger.error("Falha ao decodificar uma ou ambas as imagens")
            return False, 1.0, "Erro ao processar imagem"

        e1 = gerar_embedding_sface(_recortar_rosto_bgr(img1))
        e2 = gerar_embedding_sface(_recortar_rosto_bgr(img2))

        similaridade = comparar_embeddings_sface(e1, e2)
        distancia = 1.0 - similaridade  # escala do DeepFace.verify (cosseno)
        match = similaridade >= LIMIAR_COSSENO

        logger.info(f"Reconhecimento facial: match={match}, distancia={distancia:.4f}")

        return match, distancia, None

    except Exception as e:
        logger.error(f"Erro no reconhecimento facial: {e}")
        return False, 1.0, f"Erro no reconhecimento: {str(e)}"

def detectar_face(foto_base64):
    """
    Detecta se há uma face válida na imagem.

    Args:
        foto_base64: Imagem em base64

    Returns:
        bool: True se uma face foi detectada
    """
    try:
        img = decodificar_base64_para_numpy(foto_base64)

        if img is None:
            return False

        import cv2
        gray = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_RGB2BGR),
                            cv2.COLOR_BGR2GRAY)
        faces = _get_cascade_haar().detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        return len(faces) > 0

    except Exception as e:
        logger.error(f"Erro na detecção facial: {e}")
        return False

def validar_qualidade_foto(foto_base64, min_width=200, min_height=200):
    """
    Valida a qualidade mínima de uma foto para reconhecimento facial.
    
    Args:
        foto_base64: Imagem em base64
        min_width: Largura mínima em pixels
        min_height: Altura mínima em pixels
    
    Returns:
        tuple: (valida: bool, mensagem: str)
    """
    try:
        if ',' in foto_base64:
            foto_base64 = foto_base64.split(',')[1]
        
        img_data = base64.b64decode(foto_base64)
        img = Image.open(io.BytesIO(img_data))
        
        width, height = img.size
        
        if width < min_width or height < min_height:
            return False, f"Imagem muito pequena. Mínimo: {min_width}x{min_height}px"
        
        return True, "Foto válida"
        
    except Exception as e:
        logger.error(f"Erro ao validar qualidade da foto: {e}")
        return False, f"Erro ao processar imagem: {str(e)}"


# ============================================================
# SISTEMA DE RECONHECIMENTO FACIAL COM MÚLTIPLAS FOTOS v2.0
# ============================================================

# Configurações de reconhecimento facial
# Recalibrado em 01/09/2026 para o ponto de operação documentado do SFace
# (cosseno >= 0.363 = match, ou seja, distância < 1 - 0.363). O valor
# antigo era 0.80 ("prioriza recall"): aceitava cosseno > 0.20 — frouxo
# demais para o mesmo modelo servido nativo.
THRESHOLD_CONFIANCA = 0.637  # antes: 0.80
MODELO_RECONHECIMENTO = 'SFace'  # Modelo rápido e preciso
MIN_CONFIANCA_PERCENTUAL = 60  # Mínimo 60% de confiança para aceitar

def validar_qualidade_foto_avancada(foto_base64, min_width=150, min_height=150):
    """
    Valida qualidade da foto com verificações avançadas:
    - Tamanho mínimo
    - Brilho adequado (não muito escuro/claro)
    - Presença de face
    
    Args:
        foto_base64: Imagem em base64
        min_width: Largura mínima em pixels
        min_height: Altura mínima em pixels
    
    Returns:
        tuple: (valida: bool, mensagem: str, detalhes: dict)
    """
    try:
        if ',' in foto_base64:
            foto_base64 = foto_base64.split(',')[1]
        
        img_data = base64.b64decode(foto_base64)
        img = Image.open(io.BytesIO(img_data))
        
        width, height = img.size
        detalhes = {'width': width, 'height': height}
        
        # Verificar tamanho
        if width < min_width or height < min_height:
            return False, f"Imagem muito pequena ({width}x{height}px). Mínimo: {min_width}x{min_height}px", detalhes
        
        # Verificar brilho
        img_gray = img.convert('L')
        img_array = np.array(img_gray)
        brilho_medio = np.mean(img_array)
        detalhes['brilho'] = round(brilho_medio, 2)
        
        if brilho_medio < 30:
            return False, "Foto muito escura. Use melhor iluminação", detalhes
        
        if brilho_medio > 230:
            return False, "Foto muito clara. Reduza a iluminação", detalhes
        
        # Foto passou em todas as validações
        return True, "Foto com qualidade adequada", detalhes
        
    except Exception as e:
        logger.error(f"Erro ao validar qualidade avançada: {e}")
        return False, f"Erro ao processar imagem: {str(e)}", {}


def obter_todas_fotos_funcionario(funcionario):
    """
    Obtém todas as fotos ativas de um funcionário, incluindo foto principal.
    
    Args:
        funcionario: Objeto Funcionario do SQLAlchemy
    
    Returns:
        list: Lista de dicts com foto_base64 e descricao
    """
    fotos = []
    
    # Primeiro, tentar obter fotos da tabela FotoFacialFuncionario
    try:
        from models import FotoFacialFuncionario
        fotos_cadastradas = FotoFacialFuncionario.query.filter_by(
            funcionario_id=funcionario.id,
            ativa=True
        ).order_by(FotoFacialFuncionario.ordem).all()
        
        for foto in fotos_cadastradas:
            fotos.append({
                'foto_base64': foto.foto_base64,
                'descricao': foto.descricao or 'Foto cadastrada',
                'id': foto.id
            })
    except Exception as e:
        logger.warning(f"Erro ao buscar fotos múltiplas: {e}")
    
    # Se não houver fotos na nova tabela, usar foto principal do funcionário
    if not fotos and funcionario.foto_base64:
        fotos.append({
            'foto_base64': funcionario.foto_base64,
            'descricao': 'Foto principal',
            'id': None
        })
    
    return fotos


def reconhecer_com_multiplas_fotos(foto_capturada_base64, funcionario, threshold=None):
    """
    Compara foto capturada com TODAS as fotos cadastradas do funcionário.
    Retorna o melhor match encontrado.
    
    Args:
        foto_capturada_base64: Foto capturada em base64
        funcionario: Objeto Funcionario do SQLAlchemy
        threshold: Threshold de distância (padrão: THRESHOLD_CONFIANCA)
    
    Returns:
        tuple: (match: bool, melhor_distancia: float, melhor_foto_desc: str)
    """
    if threshold is None:
        threshold = THRESHOLD_CONFIANCA
    
    fotos = obter_todas_fotos_funcionario(funcionario)
    
    if not fotos:
        logger.warning(f"Funcionário {funcionario.nome} não tem fotos cadastradas")
        return False, 1.0, "Sem fotos cadastradas"
    
    melhor_distancia = float('inf')
    melhor_foto_desc = None
    
    for foto_info in fotos:
        try:
            match, distancia, erro = comparar_faces_deepface(
                foto_info['foto_base64'],
                foto_capturada_base64,
                modelo=MODELO_RECONHECIMENTO
            )
            
            if erro:
                logger.warning(f"Erro ao comparar com foto '{foto_info['descricao']}': {erro}")
                continue
            
            logger.debug(f"Comparação com '{foto_info['descricao']}': distancia={distancia:.4f}")
            
            # Guardar a melhor (menor distância)
            if distancia < melhor_distancia:
                melhor_distancia = distancia
                melhor_foto_desc = foto_info['descricao']
                
        except Exception as e:
            logger.error(f"Erro ao comparar foto '{foto_info['descricao']}': {e}")
            continue
    
    # Verificar se encontrou match válido
    if melhor_distancia < threshold:
        confianca_percentual = round((1 - melhor_distancia) * 100, 1)
        logger.info(f"Match encontrado com '{melhor_foto_desc}': {confianca_percentual}% confiança")
        return True, melhor_distancia, melhor_foto_desc
    else:
        logger.info(f"Sem match válido. Melhor distância: {melhor_distancia:.4f} (threshold: {threshold})")
        return False, melhor_distancia, melhor_foto_desc


def identificar_funcionario_multiplas_fotos(foto_capturada_base64, funcionarios_list, threshold=None):
    """
    Identifica um funcionário comparando foto capturada com TODAS as fotos
    de TODOS os funcionários da lista. Retorna o melhor match global.
    
    Args:
        foto_capturada_base64: Foto capturada em base64
        funcionarios_list: Lista de funcionários para comparar
        threshold: Threshold de distância (padrão: THRESHOLD_CONFIANCA)
    
    Returns:
        tuple: (funcionario: Funcionario|None, confianca: float, mensagem: str)
    """
    if threshold is None:
        threshold = THRESHOLD_CONFIANCA
    
    # Validar qualidade da foto capturada
    valida, msg_qualidade, _ = validar_qualidade_foto_avancada(foto_capturada_base64)
    if not valida:
        return None, 0, msg_qualidade
    
    melhor_funcionario = None
    melhor_distancia = float('inf')
    melhor_foto_desc = None
    
    for funcionario in funcionarios_list:
        match, distancia, foto_desc = reconhecer_com_multiplas_fotos(
            foto_capturada_base64,
            funcionario,
            threshold=threshold
        )
        
        if distancia < melhor_distancia:
            melhor_distancia = distancia
            melhor_funcionario = funcionario
            melhor_foto_desc = foto_desc
    
    # Verificar se encontrou match válido
    if melhor_distancia < threshold:
        confianca = (1 - melhor_distancia)
        confianca_percentual = round(confianca * 100, 1)
        
        # Verificar confiança mínima
        if confianca_percentual < MIN_CONFIANCA_PERCENTUAL:
            return None, confianca, f"Confiança baixa ({confianca_percentual}%). Mínimo: {MIN_CONFIANCA_PERCENTUAL}%"
        
        return melhor_funcionario, confianca, f"Reconhecido via '{melhor_foto_desc}' ({confianca_percentual}%)"
    else:
        return None, 0, f"Nenhum funcionário reconhecido (threshold: {threshold})"
