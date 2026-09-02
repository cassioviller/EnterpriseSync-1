"""O isolamento entre módulos que usam o Playwright síncrono, conferido no gate.

Por que este arquivo existe: em 02/09 a suíte completa rodou inteira pela
primeira vez (46:08) e devolveu 12 failed + 68 errors. As 80 ocorrências eram
UM defeito só:

    playwright._impl._errors.Error: It looks like you are using Playwright
    Sync API inside the asyncio loop. Please use the Async API instead.

Causa medida: `tests/test_browser_all_modules.py:307` declarava a fixture
`browser_session` com `scope="session"` segurando um `with sync_playwright()`
aberto. Fixture de sessão só é desmontada no fim da sessão INTEIRA do pytest —
então o event loop do Playwright seguia RODANDO enquanto os outros 254 arquivos
rodavam, e todo `sync_playwright()` seguinte batia em `_loop.is_running()`
(`playwright/sync_api/_context_manager.py:47`).

O primeiro arquivo browser da rodada envenenava todos os demais. Era por isso
que a jornada E2E "nunca rodou": ela erra 100% das vezes dentro da suíte
completa e PASSA quando roda sozinha — as duas coisas medidas em 02/09.

São duas provas, e ambas precisam existir:

  1. `test_contexto_sync_aberto_recusa_o_proximo` prova que o MECANISMO é real.
     Sem ela a regra de escopo abaixo seria regra de estilo, e seguiria verde
     mesmo que o Playwright deixasse de se importar com loops abertos — ou
     seja, a guarda passaria a não guardar nada sem avisar ninguém.

  2. `test_modulo_playwright_nao_tem_fixture_de_sessao` prova que nenhum módulo
     desta árvore volta a cair na armadilha.

⚠️ A seleção dos módulos é varredura de texto — isso é SELEÇÃO, não oráculo. O
oráculo é o escopo lido do objeto de fixture real que o pytest vai usar. Um
arquivo que escondesse o import escaparia da seleção; os IDs parametrizados
mostram quais arquivos entraram, e é neles que se confere.
"""
import importlib.util
import os
import sys

import pytest
from playwright.sync_api import sync_playwright
from playwright._impl._errors import Error as PlaywrightError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.integration

DIR_TESTES = os.path.dirname(os.path.abspath(__file__))


def _modulos_que_usam_playwright_sincrono():
    """Seleção (não oráculo): arquivos de teste que citam `sync_playwright`."""
    achados = []
    for nome in sorted(os.listdir(DIR_TESTES)):
        if not nome.startswith("test_") or not nome.endswith(".py"):
            continue
        caminho = os.path.join(DIR_TESTES, nome)
        with open(caminho, encoding="utf-8") as fh:
            if "sync_playwright" in fh.read():
                achados.append(nome)
    return achados


MODULOS = _modulos_que_usam_playwright_sincrono()


def _escopo_declarado(obj):
    """Escopo lido do objeto de fixture real, não do texto do arquivo.

    O pytest 8.4 embrulha a função em `FixtureFunctionDefinition` e guarda o
    marcador em `_fixture_function_marker`; versões anteriores penduravam
    `_pytestfixturefunction` na própria função. Aceita os dois para que a
    guarda não vire silenciosamente vazia numa atualização do pytest.
    """
    marcador = getattr(obj, "_fixture_function_marker", None) or getattr(
        obj, "_pytestfixturefunction", None
    )
    return getattr(marcador, "scope", None)


def _importa(nome_arquivo):
    spec = importlib.util.spec_from_file_location(
        f"_guarda_{nome_arquivo[:-3]}", os.path.join(DIR_TESTES, nome_arquivo)
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_a_selecao_encontrou_modulos_playwright():
    """Sem isto, apagar a árvore de testes deixaria a guarda verde e vazia."""
    assert len(MODULOS) >= 10, (
        f"A varredura achou só {len(MODULOS)} módulo(s) usando sync_playwright. "
        "Em 02/09 eram 18. Se a família encolheu de verdade, atualize este piso; "
        "se não encolheu, a seleção quebrou e a guarda abaixo não está guardando nada."
    )


def test_contexto_sync_aberto_recusa_o_proximo():
    """O mecanismo, provado de fato: contexto aberto envenena o próximo.

    Não sobe Chromium — só o driver do Playwright (~1 s), então cabe no gate.
    Se este teste passar a falhar, o Playwright mudou de comportamento e a
    regra de escopo abaixo perdeu a razão de existir: releia as duas antes de
    mexer em qualquer uma.
    """
    primeiro = sync_playwright().start()
    try:
        with pytest.raises(PlaywrightError, match="asyncio loop"):
            sync_playwright().start()
    finally:
        primeiro.stop()

    # E o fechamento libera — é isso que torna `scope="module"` uma cura, e não
    # um paliativo.
    terceiro = sync_playwright().start()
    terceiro.stop()


@pytest.mark.parametrize("nome_arquivo", MODULOS)
def test_modulo_playwright_nao_tem_fixture_de_sessao(nome_arquivo):
    """Em módulo que usa o Playwright síncrono, fixture de sessão é a armadilha.

    A regra é deliberadamente larga: proíbe QUALQUER fixture de sessão nesses
    arquivos, não só a que segura o browser. Distinguir uma da outra exigiria
    ler o corpo da função — prova por texto, que aqui não vale — e o custo de
    obedecer é uma palavra (`module`).
    """
    modulo = _importa(nome_arquivo)
    ofensoras = sorted(
        nome
        for nome, obj in vars(modulo).items()
        if _escopo_declarado(obj) == "session"
    )
    assert not ofensoras, (
        f"{nome_arquivo} declara fixture de sessão: {', '.join(ofensoras)}.\n"
        "Fixture de sessão que segure `sync_playwright()` mantém o event loop "
        "rodando por toda a sessão do pytest e derruba TODO teste de browser "
        "que rodar depois, em qualquer arquivo (02/09: 80 baixas de uma vez). "
        "Use scope='module': o browser continua compartilhado dentro do "
        "arquivo e o loop é liberado ao fim dele."
    )
