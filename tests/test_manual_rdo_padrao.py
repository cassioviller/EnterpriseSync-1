"""O capítulo normativo do RDO — reunião de 2026-08-20.

Plano: docs/superpowers/plans/2026-08-20-manual-padrao-preenchimento-rdo.md

O manual só serve ao propósito que o Paulo descreveu — "caso ele me
questionar, tá escrito aqui" — se ele de fato ENTRAR no manual e cobrir os
pontos que hoje ficam a critério de cada encarregado. Este teste é o guarda
disso: sem banco, sem browser, lê o capítulo pelo mesmo carregador que a
tela usa.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from views.manual_views import _carregar_capitulos

SLUG = '23a_rdo_padrao_preenchimento'


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


def test_capitulo_fica_entre_rdo_e_cronograma():
    """A ordem no sumário é a ordem alfabética do nome do arquivo."""
    slugs = [c.slug for c in _carregar_capitulos()]
    assert slugs.index('23_rdo') < slugs.index(SLUG) < slugs.index('24_cronograma')


@pytest.mark.parametrize('assunto', [
    'efetivo',
    'terceiro',
    'ocorrência',
    'foto',
    'clima',
])
def test_capitulo_cobre_os_pontos_obrigatorios(capitulo, assunto):
    """As seções que a reunião elegeu como a fonte das divergências entre o
    RDO do Alan e o do Abel. Se alguma sair do texto, este teste avisa."""
    assert assunto.lower() in capitulo.html.lower(), \
        f'o capítulo não fala de "{assunto}"'
