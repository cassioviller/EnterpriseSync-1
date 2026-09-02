"""utils_facial_sface — embedding facial SFace via OpenCV puro, sem TensorFlow.

Substitui `DeepFace.build_model('SFace')` (ponto_views.py): é o MESMO
modelo SFace, servido por `cv2.FaceRecognizerSF` sobre o ONNX oficial do
opencv_zoo (`modelos_ml/face_recognition_sface_2021dec.onnx`, sha256 no
arquivo .sha256 ao lado). Limiar de cosseno 0.363 = o default documentado
do SFace no OpenCV.

Contrato de entrada: imagem BGR já RECORTADA no rosto — o app recorta
antes de embeddar, mesmo contrato do caminho DeepFace. A Task 8 troca os
chamadores para cá; até lá os dois caminhos coexistem.
"""
import os
import threading

import cv2
import numpy as np

_ONNX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'modelos_ml', 'face_recognition_sface_2021dec.onnx')
LIMIAR_COSSENO = 0.363

_lock = threading.Lock()
_modelo = None


def _get_modelo():
    global _modelo
    if _modelo is None:
        with _lock:
            if _modelo is None:
                _modelo = cv2.FaceRecognizerSF.create(_ONNX, '')
    return _modelo


def gerar_embedding_sface(imagem_bgr: np.ndarray) -> np.ndarray:
    """Embedding 128-d do rosto (float32). A imagem deve vir
    recortada/alinhada no rosto; aqui só se normaliza o tamanho para o
    input do modelo (112x112, o nativo do SFace)."""
    rec = _get_modelo()
    face = cv2.resize(imagem_bgr, (112, 112))
    return rec.feature(face).flatten()


def comparar_embeddings_sface(e1: np.ndarray, e2: np.ndarray) -> float:
    """Similaridade de cosseno entre dois embeddings (maior = mais
    parecido; match quando >= LIMIAR_COSSENO)."""
    rec = _get_modelo()
    return float(rec.match(np.asarray(e1, dtype=np.float32).reshape(1, -1),
                           np.asarray(e2, dtype=np.float32).reshape(1, -1),
                           cv2.FaceRecognizerSF_FR_COSINE))
