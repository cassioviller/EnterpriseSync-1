"""
Configuração global do pytest para a suíte SIGE v9.0.

Configurações aplicadas em tempo de execução:
- BASE_URL: lido de PW_BASE_URL (padrão: http://localhost:5000)
- TIMEOUT_MS: lido de SIGE_TIMEOUT_MS (padrão: 30 000 ms)
- Headless: sempre True (sem exibir janela)
- Marcadores registados: browser, integration, smoke
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Raiz do projeto no sys.path — robustez de invocação.
# ---------------------------------------------------------------------------
# Vários módulos (financeiro_service, app, main, models…) ficam na raiz. Com
# `python -m pytest` o CWD entra no sys.path automaticamente, mas o console
# script `.pythonlibs/bin/pytest` (usado pelo run_tests.sh) NÃO o adiciona —
# aí a coleção de testes que importam módulos-raiz (ex.: test_agregar_fluxo_
# mensal → `from financeiro_service import …`) falha conforme a ordem. Inserir
# a raiz aqui (conftest carrega antes de tudo) garante import estável.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# App canônico (== `main:app`) montado no MOMENTO DA COLEÇÃO.
# ---------------------------------------------------------------------------
# Este `import main` roda quando o pytest importa o conftest — ANTES de coletar
# qualquer módulo de teste e ANTES de qualquer request. `app.py` registra ~37
# blueprints; `main.py` adiciona os outros ~17 (custos_escritorio, financeiro,
# etc.). Templates como `base_completo.html` referenciam endpoints que só
# existem após `main.py` (ex.: `custos_escritorio.painel_mensal`,
# `financeiro.dashboard`). Como o Flask TRAVA o registro de blueprints após a
# 1ª request, se um módulo de teste disparar uma request no import-time da
# coleção o registro tranca incompleto e renders falham com BuildError de forma
# não-determinística. Importar `main` aqui (nível de módulo do conftest)
# garante os 54 blueprints registrados antes de tudo. Sem efeitos colaterais:
# o servidor só sobe sob `if __name__ == '__main__'`.
try:
    import main  # noqa: F401
except Exception:
    pass

# ---------------------------------------------------------------------------
# Arquivos standalone (não-pytest) que devem ser ignorados pelo coletor
# ---------------------------------------------------------------------------
collect_ignore_glob = [
    # (vazio) — test_task_45_catalogo_eventos.py foi convertido para pytest
    # com fixtures reais (admin/cliente/proposta/obra) e saiu deste ignore.
]


# ---------------------------------------------------------------------------
# Marcadores customizados
# ---------------------------------------------------------------------------
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "smoke: testes de fumaça (smoke tests)")
    config.addinivalue_line("markers", "integration: testes de integração E2E")
    config.addinivalue_line(
        "markers", "browser: testes que requerem Playwright (browser real)"
    )


@pytest.fixture(scope="session", autouse=True)
def _registrar_blueprints_opcionais():
    """Monta o app CANÔNICO (o mesmo que o gunicorn serve via `main:app`) ANTES
    de qualquer request — após o 1º request o Flask trava o registro de
    blueprints. `app.py` registra ~37 blueprints; `main.py` adiciona os outros
    ~17 (importacao, catalogos, custos_escritorio, etc.). Templates como
    `base_completo.html` referenciam endpoints que só existem após `main.py`
    (ex.: `custos_escritorio.painel_mensal`), então qualquer teste que renderiza
    uma página herdando dessa base FALHA com BuildError se rodar com o app de 37.
    Importar `main` é idempotente e não tem efeitos colaterais (só registra
    blueprints; o servidor só sobe sob `if __name__ == '__main__'`)."""
    try:
        import main  # noqa: F401 — registra todos os blueprints no app compartilhado
    except Exception:
        # Fallback mínimo: ao menos os dois que os testes HTTP mais exercitam.
        try:
            from app import app
            if "importacao" not in app.blueprints:
                from importacao_views import importacao_bp
                app.register_blueprint(importacao_bp)
            if "catalogos" not in app.blueprints:
                from views.catalogos_views import catalogos_bp
                app.register_blueprint(catalogos_bp)
        except Exception:
            pass
    yield


# ---------------------------------------------------------------------------
# Fixtures de configuração consumidas pelo test_browser_all_modules.py
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sige_base_url() -> str:
    """URL-base do servidor SIGE a testar.  Sobrescreva via PW_BASE_URL."""
    return os.environ.get("PW_BASE_URL", "http://localhost:5000")


@pytest.fixture(scope="session")
def sige_timeout_ms() -> int:
    """Timeout de navegação em milissegundos. Sobrescreva via SIGE_TIMEOUT_MS."""
    return int(os.environ.get("SIGE_TIMEOUT_MS", "30000"))


@pytest.fixture(scope="session")
def browser_launch_options() -> dict:
    """Opções de lançamento do browser Chromium."""
    import shutil
    opts: dict = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    # Usar Chromium do sistema quando o binário do Playwright não está disponível
    system_chromium = (
        os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
    )
    if system_chromium:
        opts["executable_path"] = system_chromium
    return opts
