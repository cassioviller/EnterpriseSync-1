"""Motor de captura — o que o manual do RDO acrescentou — e o roteiro do RDO.

Sem banco, sem browser: exercita a lista e o guarda, como
tests/test_manual_compras_roteiro.py. Plano:
docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from anotar_captura import Acao, MarcacaoQuebrada, Tela, executar


class _PaginaFalsa:
    """O mínimo de `page` que `executar` usa, com registro do que foi chamado."""

    def __init__(self, existe=True):
        self.existe = existe
        self.chamadas = []

    def query_selector(self, seletor):
        return object() if self.existe else None

    def click(self, seletor):
        self.chamadas.append(('click', seletor))

    def set_input_files(self, seletor, arquivos):
        self.chamadas.append(('files', seletor, tuple(arquivos)))

    def wait_for_timeout(self, ms):
        self.chamadas.append(('wait', ms))

    def wait_for_load_state(self, estado):
        self.chamadas.append(('load', estado))


def test_clicar_clica_sem_esperar_navegacao():
    pagina = _PaginaFalsa()
    executar(pagina, [Acao('clicar', '#btn-equipe-7')])
    assert ('click', '#btn-equipe-7') in pagina.chamadas
    assert not any(c[0] == 'load' for c in pagina.chamadas), \
        'clicar abre modal na MESMA página — não pode esperar navegação'


def test_anexar_manda_os_arquivos_separados_por_ponto_e_virgula():
    pagina = _PaginaFalsa()
    executar(pagina, [Acao('anexar', '#fileInputNovoGal', '/tmp/a.png;/tmp/b.png')])
    assert ('files', '#fileInputNovoGal', ('/tmp/a.png', '/tmp/b.png')) in pagina.chamadas


def test_acao_nova_tambem_para_se_o_seletor_nao_existe():
    pagina = _PaginaFalsa(existe=False)
    with pytest.raises(MarcacaoQuebrada):
        executar(pagina, [Acao('clicar', '#sumiu')])
    with pytest.raises(MarcacaoQuebrada):
        executar(pagina, [Acao('anexar', '#sumiu', '/tmp/a.png')])


def test_tela_nasce_sem_permanecer_e_sem_guardar_id():
    """Os defaults mantêm o roteiro de compras exatamente como era."""
    t = Tela(slug='x', titulo='X', papel='anon', rota='/x', resumo='x')
    assert t.permanece is False
    assert t.guarda_id == ''
