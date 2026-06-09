"""
Configuração global do pytest para a suíte SIGE v9.0.

Configurações aplicadas em tempo de execução:
- BASE_URL: lido de PW_BASE_URL (padrão: http://localhost:5000)
- TIMEOUT_MS: lido de SIGE_TIMEOUT_MS (padrão: 30 000 ms)
- Headless: sempre True (sem exibir janela)
- Marcadores registados: browser, integration, smoke
"""

import os
import pytest

# ---------------------------------------------------------------------------
# Arquivos standalone (não-pytest) que devem ser ignorados pelo coletor
# ---------------------------------------------------------------------------
collect_ignore_glob = [
    "test_insumo_coeficiente_padrao.py",
    "test_orcamento_formato_br.py",
    "test_task_45_catalogo_eventos.py",
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
    """Registra os blueprints carregados via try/except no main.py (importacao,
    catalogos) ANTES de qualquer request — após o 1º request o Flask trava o
    registro de blueprints. Idempotente; sessão inteira. Sem isto, o teste HTTP
    que registra primeiro tranca o app e os demais erram ao registrar."""
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
    return {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
