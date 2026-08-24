"""O capítulo normativo do cronograma — reunião de 2026-08-20.

O Paulo pediu na mesma frase em que pediu o do RDO ("ok, ok, manual pro
cronograma, beleza"), e ele ficou de fora dos cinco planos daquele dia. É o
irmão do `23a`: o capítulo 24 ensina onde clicar, este define quando mexer.

Guarda igual à do RDO: sem banco, sem browser, lê o capítulo pelo mesmo
carregador que a tela usa.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from views.manual_views import _carregar_capitulos

SLUG = '24a_cronograma_padrao_revisao'


@pytest.fixture(scope='module')
def capitulo():
    for c in _carregar_capitulos():
        if c.slug == SLUG:
            return c
    pytest.fail(f'capítulo {SLUG} não encontrado em manual/')


def test_capitulo_entra_no_manual(capitulo):
    assert capitulo.titulo, 'o arquivo precisa começar com um H1'
    assert not capitulo.em_construcao, \
        'o texto contém "capítulo em construção" e a UI vai marcá-lo como vazio'


def test_capitulo_fica_depois_do_cronograma():
    """A ordem no sumário é a ordem alfabética do nome do arquivo."""
    slugs = [c.slug for c in _carregar_capitulos()]
    assert slugs.index('24_cronograma') < slugs.index(SLUG) < slugs.index('25_financeiro')


@pytest.mark.parametrize('assunto', [
    'linha de base',
    'planejado',
    'revisão',
    'motivo',
    'desvio',
    'predecessora',
])
def test_capitulo_cobre_os_pontos_da_reuniao(capitulo, assunto):
    """Os pontos que a reunião de 20/08 elegeu: linha de base congelada, o
    planejado que se move, revisão numerada com motivo, e o desvio entre os
    dois. Se algum sair do texto, este teste avisa."""
    assert assunto.lower() in capitulo.html.lower(), \
        f'o capítulo não fala de "{assunto}"'


def test_percentual_do_pai_registra_a_decisao_de_24_08():
    """A regra que confundiu o Paulo na reunião tem de estar escrita, com o
    número. Se alguém trocar a fórmula para média simples por item, o capítulo
    passa a mentir — e este teste avisa junto com
    `test_rollup_pondera_por_duracao_e_nao_por_contagem`."""
    cap = next(c for c in _carregar_capitulos() if c.slug == SLUG)
    html = cap.html.lower()
    assert 'ponderada pela duração' in html, \
        'o capítulo precisa dizer QUAL é a fórmula do percentual do grupo'
    assert '96,4' in html, \
        'o capítulo precisa trazer o número do exemplo — é ele que evita a ' \
        'leitura de que o cálculo está quebrado'
