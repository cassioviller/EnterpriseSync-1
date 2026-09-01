"""O SFace nativo do OpenCV produz o mesmo veredito que o DeepFace.

A equivalência aqui é MEDIDA contra o oráculo (o caminho DeepFace ainda
instalado), não afirmada: (1) o peso que o DeepFace carrega é o MESMO
arquivo ONNX byte a byte (sha256), e o SFaceClient dele é
cv2.FaceRecognizerSF — o exato engine do caminho novo; (2) para a mesma
imagem, os dois caminhos produzem o mesmo embedding; (3) para os mesmos
pares, o mesmo veredito de match.

Desvio registrado do plano: o repositório não tem fotos reais de rosto, e
ruído sintético NÃO discrimina (dois ruídos ficam a cosseno ~0.70 nos
DOIS caminhos — medido em 01/09). Afirmar "imagens diferentes < limiar"
seria falso para ambos; o que o ponto precisa é que o caminho novo decida
IGUAL ao velho, e é isso que se afirma. A discriminação entre pessoas
reais vem do modelo ser byte-idêntico ao que já roda hoje.

Os testes do oráculo pulam quando o deepface não está instalado (Task 8 o
remove) — os absolutos (forma, determinismo, match de si mesma) ficam.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §opencv.
"""
import hashlib
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ONNX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'modelos_ml', 'face_recognition_sface_2021dec.onnx')

pytestmark = pytest.mark.skipif(
    not os.path.exists(ONNX),
    reason='modelo ONNX do SFace não baixado (Task 7 Step 1)')

_tem_deepface = True
try:  # o oráculo é opcional: a Task 8 remove o deepface do ambiente
    import deepface  # noqa: F401
except Exception:
    _tem_deepface = False

precisa_oraculo = pytest.mark.skipif(
    not _tem_deepface, reason='deepface removido (Task 8) — oráculo indisponível')


def _rosto_sintetico(seed):
    """Imagem BGR determinística no contrato de entrada (rosto já
    recortado). Blocos 8x8 — textura estável sob resize; o que se afirma
    com ela é concordância entre caminhos, não semântica facial."""
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (25, 25, 3))
    return np.kron(base, np.ones((8, 8, 1))).astype('uint8')  # 200x200x3


# ── Absolutos do caminho novo (sobrevivem à remoção do deepface) ──────────

def test_embedding_tem_a_forma_do_sface():
    from utils_facial_sface import gerar_embedding_sface
    emb = gerar_embedding_sface(_rosto_sintetico(1))
    assert emb is not None and emb.size == 128  # SFace = 128 dims


def test_o_embedding_e_deterministico_e_a_mesma_imagem_e_match():
    """Mesma entrada = mesmo vetor (é o que permite cachear
    cache_facial.pkl) e match de si mesma a cosseno ~1."""
    from utils_facial_sface import (LIMIAR_COSSENO,
                                    comparar_embeddings_sface,
                                    gerar_embedding_sface)
    a = gerar_embedding_sface(_rosto_sintetico(3))
    b = gerar_embedding_sface(_rosto_sintetico(3))
    assert np.array_equal(a, b)
    assert comparar_embeddings_sface(a, b) >= LIMIAR_COSSENO


# ── Equivalência medida contra o oráculo DeepFace ─────────────────────────

def _sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


@precisa_oraculo
def test_o_peso_do_deepface_e_o_mesmo_onnx_byte_a_byte():
    """O SFaceClient do DeepFace carrega ~/.deepface/weights/...onnx via
    cv2.FaceRecognizerSF — se os bytes são os mesmos, o modelo é o mesmo."""
    peso_deepface = os.path.join(
        os.path.expanduser('~'), '.deepface', 'weights',
        'face_recognition_sface_2021dec.onnx')
    if not os.path.exists(peso_deepface):
        pytest.skip('oráculo nunca baixou o peso nesta máquina')
    assert _sha256(peso_deepface) == _sha256(ONNX)


@precisa_oraculo
def test_mesma_imagem_mesmo_embedding_e_mesmo_veredito_que_o_deepface():
    """Para a MESMA entrada uint8 112x112, o embedding dos dois caminhos é
    o mesmo vetor (cosseno ~1) e o veredito de cada par coincide."""
    import cv2
    from deepface import DeepFace

    from utils_facial_sface import (LIMIAR_COSSENO,
                                    comparar_embeddings_sface,
                                    gerar_embedding_sface)

    oraculo = DeepFace.build_model('SFace')

    def _par(img):
        """(embedding nativo, embedding do oráculo) sobre bytes idênticos.

        O forward do oráculo recebe normalizado e faz `(x*255).astype(uint8)`
        — o roundtrip é conferido para garantir que os dois caminhos viram
        exatamente os mesmos bytes."""
        face = cv2.resize(img, (112, 112))
        norm = face.astype(np.float64) / 255.0
        assert np.array_equal((norm * 255).astype(np.uint8), face), (
            'roundtrip de normalização mudou bytes — ajuste a imagem do teste')
        nativo = gerar_embedding_sface(face)
        do_oraculo = np.asarray(oraculo.forward(norm[np.newaxis]),
                                dtype=np.float32)
        return nativo, do_oraculo

    n1, o1 = _par(_rosto_sintetico(1))
    n2, o2 = _par(_rosto_sintetico(2))

    # 1) mesmo embedding para a mesma imagem, caminho a caminho
    assert comparar_embeddings_sface(n1, o1) > 0.999
    assert comparar_embeddings_sface(n2, o2) > 0.999

    # 2) mesmo veredito para os mesmos pares — o cosseno dos dois caminhos
    #    coincide, logo a decisão contra o limiar coincide
    par_nativo = comparar_embeddings_sface(n1, n2)
    par_oraculo = comparar_embeddings_sface(o1, o2)
    assert abs(par_nativo - par_oraculo) < 1e-3
    assert ((par_nativo >= LIMIAR_COSSENO)
            == (par_oraculo >= LIMIAR_COSSENO))
