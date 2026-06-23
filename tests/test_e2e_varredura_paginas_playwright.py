"""
E2E (Playwright, browser real) — VARREDURA de todas as páginas do SIGE.

Visita a página-âncora (landing) de cada módulo do menu, logado como admin,
e verifica que ela:
  - responde HTTP < 400 (não é 404/500),
  - não é uma página de erro (sem "Traceback", "Internal Server Error", etc.),
  - não dispara erro JS crítico no console,
  - contém um marcador positivo do módulo (texto esperado).

As URLs são resolvidas em runtime via url_for (sem hardcode de paths), então o
teste acompanha refactors de rota. Cada página vira um caso parametrizado.

Pré-requisito: servidor em localhost:5000 com seed Alfa.
Execução:
    pytest tests/test_e2e_varredura_paginas_playwright.py -v
    bash run_tests.sh --varredura
"""
import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get("PW_BASE_URL", "http://localhost:5000")
TIMEOUT_MS = int(os.environ.get("SIGE_TIMEOUT_MS", "30000"))
DEMO_USER = "admin_alfa"
DEMO_PASS = "Alfa@2026"

# Texto que, se aparecer no corpo, indica página de erro do servidor.
ERRO_SERVIDOR = [
    "traceback (most recent call last)",
    "internal server error",
    "werkzeug.exceptions",
    "500 internal",
    "jinja2.exceptions",
    "sqlalchemy.exc",
]

# Erros de console ignoráveis (ruído de libs/3rd-party, não regressão do app).
JS_IGNORAR = [
    "favicon", "net::err_aborted", "net::err_failed", "net::err_internet",
    "extension", "chrome-extension", "the server responded with a status of 4",
    "feather", "tom-select", "download the react",
    # DataTables busca o i18n pt-BR de um CDN externo (bloqueado por CORS no
    # ambiente de teste). É só localização da tabela — não é regressão do app.
    "datatables", "cdn.datatables", "access-control-allow-origin", "cors policy",
]

# (nome, endpoint Flask, [marcadores positivos — pelo menos um deve aparecer])
# Endpoints sem argumentos (páginas-âncora de cada módulo).
PAGINAS_SPEC = [
    # Núcleo
    ("dashboard",            "main.dashboard",                  ["Dashboard", "Obras", "Resumo"]),
    ("obras",                "main.obras",                      ["Obra"]),
    ("funcionarios",         "main.funcionarios",               ["Funcionár"]),
    ("usuarios",             "main.usuarios",                   ["Usuár"]),
    # Comercial
    ("propostas",            "propostas.index",                 ["Proposta"]),
    ("orcamentos",           "orcamentos.listar",               ["Orçamento"]),
    ("orcamento_novo",       "orcamentos.novo",                 ["Orçamento", "Novo"]),
    ("crm_lista",            "crm.lista",                       ["CRM", "Lead", "Funil"]),
    ("crm_kanban",           "crm.kanban",                      ["Kanban", "Lead", "CRM"]),
    ("clientes",             "clientes.listar",                 ["Cliente"]),
    # Catálogos
    ("catalogo_insumos",     "catalogo.insumos_list",           ["Insumo"]),
    ("catalogo_servicos",    "catalogo.servicos_list",          ["Serviço"]),
    # importacao/catalogos não são registrados no app importado direto (só sob
    # main:app/gunicorn) — usa path literal, que o servidor real atende.
    ("catalogos_hub",        "/catalogos/",                     ["Catálogo", "Categoria"]),
    # Cronograma / custos
    ("cronograma",           "cronograma.index",                ["Cronograma"]),
    ("gestao_custos",        "gestao_custos.index",             ["Custo", "Despesa", "Obra", "Gestão"]),
    # Financeiro
    ("financeiro_dash",      "financeiro.dashboard",            ["Financeiro", "Caixa", "Saldo"]),
    ("contas_receber",       "financeiro.listar_contas_receber",["Receber"]),
    ("fluxo_caixa",          "financeiro.fluxo_caixa",          ["Fluxo de Caixa", "Fluxo"]),
    ("bancos",               "financeiro.listar_bancos",        ["Banco"]),
    ("importacao",           "/importacao/",                    ["Importa"]),
    # Operacional de obra
    ("almoxarifado",         "almoxarifado.dashboard",          ["Almoxarifado", "Estoque", "Item"]),
    ("almox_itens",          "almoxarifado.itens",              ["Item", "Estoque"]),
    ("compras",              "compras.index",                   ["Compra"]),
    ("alimentacao",          "alimentacao.index",               ["Alimentação", "Restaurante", "Refeição"]),
    ("frota",                "frota.dashboard",                 ["Frota", "Veículo"]),
    # Folha / contabilidade / métricas
    ("folha_relatorios",     "folha.relatorios",                ["Folha", "Relatório"]),
    ("metricas_func",        "metricas.funcionarios",           ["Métrica", "Produtividade", "Funcionár"]),
    ("metricas_ranking",     "metricas.ranking",                ["Ranking", "Métrica"]),
    # Configurações
    ("config_empresa",       "configuracoes.empresa",           ["Empresa", "Configura"]),
    ("config_departamentos", "configuracoes.departamentos",     ["Departamento", "Configura"]),
    ("manual",               "manual.index",                    ["Manual"]),

    # ── Loop 3 — demais módulos do menu ─────────────────────────────────────
    ("rdo",                  "/rdo",                            ["RDO", "Relatório", "Diário", "Obra"]),
    ("ponto",                "ponto.index",                     ["Ponto", "Registro", "Obra"]),
    ("ponto_obras",          "ponto.lista_obras",               ["Ponto", "Obra"]),
    ("equipe",               "/equipe/",                        ["Equipe", "Aloca", "Funcionár"]),
    ("transporte",           "transporte.index",                ["Transporte"]),
    ("contabilidade",        "/contabilidade/dashboard",        ["Contábil", "Contabil", "Lançamento", "Plano"]),
    ("folha_dashboard",      "folha.dashboard",                 ["Folha", "Pagamento", "Salár"]),
    ("frota_lista",          "frota.lista",                     ["Frota", "Veículo"]),
    ("compras_nova",         "compras.nova",                    ["Compra", "Nova", "Requisição"]),
    ("compras_aprovacao",    "compras.aprovacao",               ["Compra", "Aprov"]),
    ("almox_entrada",        "almoxarifado.entrada",            ["Entrada", "Item", "Estoque"]),
    ("almox_moviment",       "almoxarifado.movimentacoes",      ["Moviment", "Estoque", "Item"]),
    ("crm_novo",             "crm.novo",                        ["Lead", "Novo", "CRM"]),
    ("reembolsos",           "reembolso.index",                 ["Reembolso"]),
    ("produtividade",        "cronograma.produtividade_dashboard", ["Produtividade", "Cronograma"]),
    ("custos_escritorio",    "custos.dashboard_custos",         ["Custo", "Escritório", "Despesa"]),
    ("metricas_servico",     "metricas.empresa_por_servico",    ["Métrica", "Serviço"]),
]


def _resolver_paginas():
    """Resolve cada endpoint → path relativo via url_for (test_request_context)."""
    from app import app as flask_app
    from flask import url_for
    resolvidas = []
    with flask_app.test_request_context():
        for nome, endpoint, markers in PAGINAS_SPEC:
            if endpoint.startswith("/"):
                path = endpoint  # path literal (blueprint não registrado no import)
            else:
                try:
                    path = url_for(endpoint)
                except Exception as e:
                    path = None
                    print(f"[WARN] não resolveu {endpoint}: {e}")
            resolvidas.append((nome, endpoint, path, markers))
    return resolvidas


PAGINAS = _resolver_paginas()


@pytest.fixture(scope="session")
def page():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(TIMEOUT_MS)
        pg.goto(f"{BASE_URL}/login")
        pg.fill("input[name=username]", DEMO_USER)
        pg.fill("input[name=password]", DEMO_PASS)
        pg.click("button[type=submit]")
        pg.wait_for_load_state("networkidle")
        assert "/login" not in pg.url, f"login falhou: {pg.url}"
        yield pg
        browser.close()


@pytest.mark.browser
@pytest.mark.parametrize(
    "nome,endpoint,path,markers",
    PAGINAS,
    ids=[p[0] for p in PAGINAS],
)
def test_pagina(page: Page, nome, endpoint, path, markers):
    assert path, f"endpoint {endpoint} não resolveu para um path"

    erros_js = []
    page.on("pageerror", lambda e: erros_js.append(str(e)))
    page.on("console", lambda m: erros_js.append(m.text) if m.type == "error" else None)

    resp = page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

    # (1) HTTP não-erro
    assert resp is not None, f"{nome}: sem resposta de {path}"
    assert resp.status < 400, f"{nome}: HTTP {resp.status} em {path}"

    corpo = page.locator("body").inner_text()
    low = corpo.lower()

    # (2) não é página de erro do servidor
    for marca in ERRO_SERVIDOR:
        assert marca not in low, f"{nome}: página de erro do servidor em {path} ({marca})"

    # (3) marcador positivo do módulo (pelo menos um)
    assert any(m.lower() in low for m in markers), (
        f"{nome}: nenhum marcador {markers} encontrado em {path}"
    )

    # (4) sem erro JS crítico
    criticos = [
        e for e in erros_js
        if not any(ig in e.lower() for ig in JS_IGNORAR)
    ]
    assert not criticos, f"{nome}: erro JS crítico em {path}: {criticos[:3]}"
