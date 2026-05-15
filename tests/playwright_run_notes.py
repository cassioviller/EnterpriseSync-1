"""
playwright.config.py
Configuração centralizada para a suíte de testes Playwright do SIGE.

Uso:
    # Executar todos os testes com relatório HTML
    pytest tests/test_browser_all_modules.py \
        --base-url http://localhost:5000 \
        --html=tests/reports/playwright_report.html \
        --self-contained-html \
        -v

    # Modo headed (janela visível)
    pytest tests/test_browser_all_modules.py --headed -v

    # Apenas um bloco
    pytest tests/test_browser_all_modules.py::TestBloco1Auth -v

Variáveis de ambiente:
    PW_BASE_URL   — URL base do servidor (default: http://localhost:5000)
    PW_HEADED     — "1" para rodar em modo headed
"""

# URL base usada pelos testes standalone (sync_playwright)
BASE_URL = "http://localhost:5000"

# Timeout padrão em milissegundos
DEFAULT_TIMEOUT = 30_000

# Diretório de relatórios
REPORTS_DIR = "tests/reports"

# Conta demo do tenant Alfa
DEMO_EMAIL = "admin@construtoraalfa.com.br"
DEMO_PASSWORD = "Alfa@2026"
