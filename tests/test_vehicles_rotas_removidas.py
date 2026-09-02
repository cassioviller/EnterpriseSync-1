"""D3, segunda leva — as 18 rotas de views/vehicles.py não existem mais.

As seis quebradas saíram em 0b3f932c; estas 18 funcionavam, mas estavam
mortas pela interface — a capacidade viva é o frota_bp, para onde os
templates postam. A única referência viva encontrada no Step 1 (o botão
de excluir de veiculos_lista.html, renderizado pelo frota_views.py:109,
postando no shim 307 /veiculos/<id>/excluir) foi apontada direto para
frota.deletar_veiculo NESTA task — por isso as 18 saem completas, sem
sobrevivente. Decisão: decisoes-respondidas.md §vehicles.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints todos
from app import app

# Transcritas de `grep -n "@main_bp.route" views/vehicles.py` em 01/09,
# com <int:...> instanciado em 1 — as 18 linhas, na ordem do fonte.
URLS = [
    '/veiculos/1/ultima-km',
    '/veiculos/1/kpis',
    '/veiculos/1/excluir',
    '/veiculos/uso/1/detalhes',
    '/veiculos/uso/1/editar',
    '/veiculos/custo/1/deletar',
    '/veiculos/1/custos',
    '/veiculos/1/exportar',
    '/veiculos/lancamentos',
    '/veiculos/relatorios',
    '/veiculos/relatorios/exportar',
    '/veiculos',
    '/veiculos/novo',
    '/veiculos/1',
    '/veiculos/1/uso/novo',
    '/veiculos/1/editar',
    '/api/veiculos/1',
    '/api/veiculos/uso/1/finalizar',
]


@pytest.mark.parametrize('url', URLS)
def test_a_url_nao_existe_mais(url):
    with app.test_client() as client:
        r = client.get(url)
        # 404 = removida. 405 seria rota viva com método errado — reprova.
        # 302 para login também reprova: significa que a rota ainda existe
        # (o 404 do Flask nasce ANTES de qualquer @login_required).
        assert r.status_code == 404, f'{url} ainda responde {r.status_code}'


def test_o_botao_de_excluir_do_template_aponta_para_a_frota():
    """A guarda do gatilho: o template vivo (frota renderiza
    veiculos_lista.html) tem de postar na rota viva da frota — se alguém
    reapontar para /veiculos/<id>/excluir, o botão quebra em silêncio
    (a rota não existe mais) e este teste acusa."""
    caminho = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'templates', 'veiculos_lista.html')
    with open(caminho, encoding='utf-8') as f:
        conteudo = f.read()
    assert '/veiculos/${veiculoId}/excluir' not in conteudo, (
        'o botão de excluir ainda posta no shim removido')
    assert '/frota/${veiculoId}/deletar' in conteudo, (
        'o botão de excluir tem de postar em frota.deletar_veiculo')
