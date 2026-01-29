"""
Utilitários para Reconhecimento Facial usando DeepFace
SIGE v9.0 - Sistema de Gestão Empresarial
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

def comparar_faces_deepface(foto_cadastro_base64, foto_capturada_base64, modelo='SFace'):
    """
    Compara duas imagens em base64 usando DeepFace.
    
    Args:
        foto_cadastro_base64: Foto cadastrada do funcionário em base64
        foto_capturada_base64: Foto capturada no momento do registro em base64
        modelo: Modelo a ser utilizado (SFace é leve e rápido, VGG-Face é pesado)
    
    Returns:
        tuple: (match: bool, distancia: float, erro: str|None)
               - match: True se as faces são da mesma pessoa
               - distancia: Valor de distância (quanto menor, mais similar)
               - erro: Mensagem de erro se houver problema na detecção
    """
    try:
        from deepface import DeepFace
        
        img1 = decodificar_base64_para_numpy(foto_cadastro_base64)
        img2 = decodificar_base64_para_numpy(foto_capturada_base64)
        
        if img1 is None or img2 is None:
            logger.error("Falha ao decodificar uma ou ambas as imagens")
            return False, 1.0, "Erro ao processar imagem"
        
        resultado = DeepFace.verify(
            img1_path=img1,
            img2_path=img2,
            model_name=modelo,
            detector_backend='opencv',
            enforce_detection=False
        )
        
        match = resultado.get('verified', False)
        distancia = resultado.get('distance', 1.0)
        
        logger.info(f"Reconhecimento facial: match={match}, distancia={distancia:.4f}")
        
        return match, distancia, None
        
    except ValueError as e:
        error_msg = str(e)
        if "Face could not be detected" in error_msg or "no face" in error_msg.lower():
            logger.warning(f"Nenhuma face detectada: {e}")
            return False, 1.0, "Nenhuma face detectada na imagem. Posicione seu rosto corretamente."
        logger.error(f"Erro de validação DeepFace: {e}")
        return False, 1.0, f"Erro na validação facial: {error_msg}"
    except Exception as e:
        logger.error(f"Erro no reconhecimento facial DeepFace: {e}")
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
        from deepface import DeepFace
        
        img = decodificar_base64_para_numpy(foto_base64)
        
        if img is None:
            return False
        
        faces = DeepFace.extract_faces(
            img_path=img,
            detector_backend='opencv',
            enforce_detection=False
        )
        
        return len(faces) > 0 and faces[0].get('confidence', 0) > 0.5
        
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
