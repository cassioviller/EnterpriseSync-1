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


# ── Task 2: gerador de PDF parametrizado ─────────────────────────────────


def test_construir_pdf_monta_um_manual_de_uma_tela(tmp_path):
    from PIL import Image
    from manual_pdf import construir_pdf, escrever_markdown
    from anotar_captura import Campo

    shots = tmp_path / 'shots'
    shots.mkdir()
    Image.new('RGB', (640, 400), (240, 240, 240)).save(shots / 'x.png')
    roteiro = [Tela(slug='x', titulo='Uma tela', papel='anon', rota='/x',
                    resumo='Resumo.', campos=[Campo(1, '#a', 'Campo A', True)],
                    depois='Depois.', atencao='Atenção.',
                    ato='Ato único', ato_resumo='Só um ato.')]
    pdf, md = tmp_path / 'm.pdf', tmp_path / 'm.md'

    construir_pdf(roteiro, pdf=pdf, shots=shots, titulo='T', subtitulo='S',
                  intro=['Linha.'], quem={'anon': 'qualquer pessoa'})
    escrever_markdown(roteiro, md=md, titulo='T', gerador='g.py', roteiro_nome='r.py')

    assert pdf.exists() and pdf.stat().st_size > 1000
    texto = md.read_text(encoding='utf-8')
    assert '## Ato único' in texto and '![Uma tela](screenshots/x.png)' in texto
    assert '| 1 | Campo A * |' in texto


def test_construir_pdf_recusa_foto_faltando(tmp_path):
    from manual_pdf import construir_pdf
    roteiro = [Tela(slug='sem_foto', titulo='X', papel='anon', rota='/x', resumo='x')]
    with pytest.raises(SystemExit) as erro:
        construir_pdf(roteiro, pdf=tmp_path / 'm.pdf', shots=tmp_path, titulo='T',
                      subtitulo='S', intro=[], quem={})
    assert 'sem_foto' in str(erro.value)


# ── Task 4: o roteiro das 18 telas ────────────────────────────────────────


def _roteiro_de_teste():
    from roteiro_manual_rdo import montar
    ids = {'obra_id': 1, 't_blocos': 2, 't_estacas': 3, 't_pilares': 4, 't_marco': 5,
           'f_davi': 6, 'f_pedro': 7, 'sub_id': 8, 'hoje': '2026-08-21'}
    return montar(ids)


def test_roteiro_tem_slugs_unicos_e_em_ordem():
    slugs = [t.slug for t in _roteiro_de_teste()]
    assert len(slugs) == len(set(slugs))
    assert slugs == sorted(slugs), 'o prefixo numérico do slug é a ordem do manual'


def test_numeracao_das_caixas_e_contigua_em_cada_tela():
    for t in _roteiro_de_teste():
        numeros = [c.numero for c in t.campos]
        assert numeros == list(range(1, len(numeros) + 1)), (t.slug, numeros)


def test_toda_acao_usa_tipo_que_o_motor_conhece():
    from anotar_captura import TIPOS_DE_ACAO
    for t in _roteiro_de_teste():
        for a in t.acoes:
            assert a.tipo in TIPOS_DE_ACAO, (t.slug, a.tipo)


def test_rdo_id_so_aparece_depois_da_tela_que_o_guarda():
    """`{rdo_id}` numa rota ANTES do salvar é um manual que não tem como rodar."""
    liberado = set()
    for t in _roteiro_de_teste():
        for chave in ('rdo_id', 'rdo_retif_id'):
            if '{' + chave + '}' in t.rota:
                assert chave in liberado, (t.slug, chave)
        if t.guarda_id:
            liberado.add(t.guarda_id)


def test_tela_que_permanece_nao_tem_rota():
    for t in _roteiro_de_teste():
        if t.permanece:
            assert t.rota == '', (t.slug, 'permanece=True não navega — rota vazia')
        else:
            assert t.rota.startswith('/'), t.slug
