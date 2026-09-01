"""Depois da troca, o caminho facial não importa deepface nem tensorflow.

Prova por comportamento: importa os módulos do ponto facial, exercita a
comparação PÚBLICA (`comparar_faces_deepface`, nome mantido — só o miolo
trocou) e a geração de embedding do ponto, e afirma que nem deepface nem
tensorflow entraram em sys.modules — se algum caminho ainda os importar,
mesmo lazy dentro de função, o teste acusa.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §opencv.
"""
import base64
import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _limpar_modulos_ml():
    for m in list(sys.modules):
        if m.startswith(('deepface', 'tensorflow', 'tf_keras', 'keras')):
            del sys.modules[m]


def _intrusos():
    return sorted(m for m in sys.modules
                  if m.startswith(('deepface', 'tensorflow', 'tf_keras')))


def _foto_base64(seed):
    """JPEG base64 determinístico no formato que o ponto recebe."""
    from PIL import Image
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (25, 25, 3))
    img = np.kron(base, np.ones((8, 8, 1))).astype('uint8')
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode()


def test_comparacao_facial_funciona_sem_deepface_no_processo():
    _limpar_modulos_ml()

    import utils_facial
    from utils_facial_sface import (comparar_embeddings_sface,
                                    gerar_embedding_sface)

    # o caminho novo direto…
    a = gerar_embedding_sface(np.zeros((112, 112, 3), dtype='uint8'))
    comparar_embeddings_sface(a, a)

    # …e a função pública que o ponto chama (ponto_views.py:1714) — é nela
    # que o import lazy do deepface vivia; exercitá-la é o que prova a troca.
    match, distancia, erro = utils_facial.comparar_faces_deepface(
        _foto_base64(1), _foto_base64(1))
    assert erro is None
    assert match is True, 'a MESMA imagem tem de ser match dela mesma'
    assert distancia < 0.001

    assert _intrusos() == [], (
        f'caminho facial ainda importa: {_intrusos()}')


def test_embedding_do_ponto_funciona_sem_deepface_no_processo():
    """O caminho do ponto (gerar_embedding_otimizado, usado pelo cache e
    pelo reconhecimento) também tem de viver sem deepface."""
    import tempfile

    import cv2
    from PIL import Image

    _limpar_modulos_ml()

    import ponto_views  # dispara o preload assíncrono — que deve ser nativo

    rng = np.random.default_rng(7)
    img = np.kron(rng.integers(0, 255, (25, 25, 3)),
                  np.ones((8, 8, 1))).astype('uint8')
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        Image.fromarray(img).save(tmp.name)
        caminho = tmp.name
    try:
        embedding = ponto_views.gerar_embedding_otimizado(caminho)
    finally:
        os.remove(caminho)

    assert embedding is not None and len(embedding) == 128

    # o preload roda em thread no import — espera ele assentar antes de
    # varrer sys.modules, senão o intruso entraria depois do assert
    import threading
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.name.startswith(
                ('preload', 'Thread')):
            t.join(timeout=30)

    assert _intrusos() == [], (
        f'caminho do ponto ainda importa: {_intrusos()}')
