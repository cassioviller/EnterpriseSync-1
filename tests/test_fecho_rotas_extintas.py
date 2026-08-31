"""As rotas que este repositório extinguiu, e a prova de que não voltaram.

Segue o padrão de `tests/test_b5_fluxo_gemeos_e_orfaos.py:210`, que congela a
extinção da família `main.*` de custo de veículo: a morte é PROVADA pelo
`url_map`, não afirmada por comentário. Um `grep` diz que ninguém chama; só o
`url_map` diz que ninguém PODE chamar.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints
from app import app

pytestmark = pytest.mark.integration


def _endpoints():
    return {r.endpoint for r in app.url_map.iter_rules()}


def test_o_url_map_esta_populado():
    """A base de todas as afirmações de ausência deste arquivo.

    Um teste que afirma "endpoint X não existe" passa vacuamente se o
    `url_map` estiver vazio — e `main.py` registra cada blueprint dentro de
    um `try/except Exception` que só loga e segue, então um registro pode
    morrer em silêncio. Sem esta âncora, o arquivo inteiro viraria andaime
    no dia em que a inicialização quebrasse.

    Medido em 31/08: 759 endpoints com o app subindo inteiro. O piso de 500
    é folgado abaixo disso — pega colapso de inicialização, não variação
    normal de contagem de rotas.
    """
    endpoints = _endpoints()
    assert len(endpoints) > 500, (
        f'url_map com só {len(endpoints)} endpoints — o app não subiu '
        'inteiro, e as afirmações de ausência deste arquivo não valem')


def test_relatorios_financeiros_avancados_esta_extinto():
    """🔴 D4 — o módulo respondia `{"success": true, "dados": {}}` em vez de
    errar, por seis defeitos independentes.

    🔬 As duas rotas que renderizavam apontavam para
    `templates/relatorios/financeiros/*.html`, e o diretório
    `templates/relatorios/` não existe — nunca existiu na árvore. Um relatório
    que não tem template não é um relatório quebrado, é um relatório que nunca
    funcionou.

    Apagar foi mais honesto que consertar: ninguém reclamou em meses porque
    ninguém conseguia usar.
    """
    vivos = {e for e in _endpoints() if e.startswith('relatorios_financeiros.')}
    assert not vivos, (
        f'o blueprint relatorios_financeiros voltou a registrar rotas: {vivos}')
