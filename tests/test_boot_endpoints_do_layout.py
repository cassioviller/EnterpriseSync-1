"""A guarda de boot contra blueprint que falha em silêncio — 2026-08-19.

🔬 O caso real que originou isto, medido num servidor vivo em 19/08:

  1. 📖 `compras_views.py:10` faz `from app import db` no topo, e
     📖 `app.py` importa `compras_views` DENTRO do bloco de registro — um ciclo.
     No boot normal ele se resolve por ordem.
  2. Num `--reload` do gunicorn a ordem inverteu: `from app import db` reentrou
     num módulo pela metade e levantou ImportError.
  3. 📖 O `except` do registro **logou WARNING e seguiu**. O app subiu sem
     compras.

Resultado: 📖 `base_completo.html:959` chama `url_for('compras.index')` sem
condição, e **toda página autenticada** passou a devolver 500 — não só as de
compras. 🔬 Medido: `/compras/` em 404, dashboard em 500, e o diagnóstico era
UMA linha de WARNING no meio de sessenta linhas de `[OK]`.

São dois riscos distintos, e um teste para cada:

  1. **A guarda deixar de existir ou deixar de reprovar.** Se ela voltar a
     passar batido, o modo de falha acima volta inteiro.
  2. **Alguém escrever `url_for('x.y')` no layout para um endpoint que não
     existe.** O erro só apareceria ao renderizar, em produção, na cara do
     usuário — e em TODA página, porque o layout é comum.

Nenhum dos dois precisa de navegador. O segundo boota o app, que é o preço de
conferir contra o `url_map` de verdade em vez de contra uma lista copiada.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _conferir_endpoints_do_layout


class _AppFalso:
    """O mínimo que a guarda usa: `root_path` e um `url_map` iterável."""

    def __init__(self, root_path, endpoints):
        self.root_path = root_path
        self.url_map = type('Mapa', (), {
            'iter_rules': lambda _self: [type('R', (), {'endpoint': e})()
                                         for e in endpoints]})()


def test_a_guarda_reprova_endpoint_ausente(tmp_path):
    """O risco nº 1. Se este teste passar a falhar, o app volta a poder subir
    quebrado servindo 500 em toda página."""
    (tmp_path / 'templates').mkdir()
    (tmp_path / 'templates' / 'base.html').write_text(
        """<a href="{{ url_for('compras.index') }}">Compras</a>
           <a href="{{ url_for('main.dashboard') }}">Início</a>""",
        encoding='utf-8')

    with pytest.raises(RuntimeError) as erro:
        _conferir_endpoints_do_layout(_AppFalso(str(tmp_path), {'main.dashboard'}))

    assert 'compras.index' in str(erro.value), 'o erro tem de dizer QUAL endpoint'
    assert 'main.dashboard' not in str(erro.value), 'não acusa quem está registrado'
    assert 'WARN' in str(erro.value), \
        'o erro tem de apontar para a linha de WARNING que explica a causa'


def test_a_guarda_nao_reprova_layout_completo(tmp_path):
    (tmp_path / 'templates').mkdir()
    (tmp_path / 'templates' / 'base.html').write_text(
        "<a href=\"{{ url_for('main.dashboard') }}\">Início</a>", encoding='utf-8')

    _conferir_endpoints_do_layout(_AppFalso(str(tmp_path), {'main.dashboard'}))


def test_url_for_de_variavel_nao_e_conferido(tmp_path):
    """O que não dá para conferir daqui não se finge que confere: `url_for(x)`
    resolve em tempo de render. A guarda olha só literais — e é melhor uma
    guarda honestamente parcial do que uma que quebra o boot por engano."""
    (tmp_path / 'templates').mkdir()
    (tmp_path / 'templates' / 'base.html').write_text(
        "<a href=\"{{ url_for(item.rota) }}\">{{ item.nome }}</a>", encoding='utf-8')

    _conferir_endpoints_do_layout(_AppFalso(str(tmp_path), set()))


def test_o_layout_de_verdade_nao_referencia_endpoint_inexistente():
    """O risco nº 2, contra o `url_map` real. É o mesmo que a guarda faz no
    boot; aqui ele roda no gate, que é onde se quer descobrir.

    🔬 Importa `main`, e NÃO `app`, e a diferença é o achado de 19/08: quatro
    blueprints do layout (`cadastros_hub`, `catalogos`, `custos_escritorio`,
    `importacao`) só são registrados no `main.py`. Conferir contra o `app`
    sozinho acusaria quatro ausências que não existem no processo real.
    """
    import main
    registrados = {r.endpoint for r in main.app.url_map.iter_rules()}
    padrao = re.compile(r"url_for\(\s*'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_]+)'")
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    faltando = {}
    for nome in ('base_completo.html', 'base.html', 'base_iframe.html'):
        caminho = os.path.join(raiz, 'templates', nome)
        if not os.path.exists(caminho):
            continue
        with open(caminho, encoding='utf-8') as fh:
            ausentes = sorted(set(padrao.findall(fh.read())) - registrados)
        if ausentes:
            faltando[nome] = ausentes

    assert not faltando, (
        f'o layout base referencia endpoint que não existe: {faltando}. '
        f'Como o layout é comum, isto derruba TODA página autenticada.')
