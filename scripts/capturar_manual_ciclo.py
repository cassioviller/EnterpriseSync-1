"""Captura screenshots de cada tela do ciclo SIGE para o manual visual."""
import os, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"
USER = "admin_E2E208-T7X5RN"
PASS = "TesteE2E@2026"

ORCAMENTO_ID = 132
PROPOSTA_ID = 1222
TOKEN = "0q6NLxH3agXCaQ69P7EYXDBjYNfjudTKK9K3WZBNo60"
OBRA_ID = 1276
SERVICO_ALV = 1012
SERVICO_PIN = 1013

OUT = Path("docs/manual_ciclo/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("01_login",                       "/login",                                          "anon"),
    ("02_dashboard",                   "/",                                               "auth"),
    ("03_lista_insumos",               "/catalogo/insumos?busca=E2E210-RICO",             "auth"),
    ("04_form_novo_insumo",            "/catalogo/insumos/novo",                          "auth"),
    ("05_lista_servicos",              "/catalogo/servicos?busca=E2E210-RICO",            "auth"),
    ("06_composicao_alvenaria",        f"/catalogo/servicos/{SERVICO_ALV}/composicao",    "auth"),
    ("07_composicao_pintura",          f"/catalogo/servicos/{SERVICO_PIN}/composicao",    "auth"),
    ("08_orcamento_editar",            f"/orcamentos/{ORCAMENTO_ID}/editar",              "auth"),
    ("09_proposta_visualizar",         f"/propostas/{PROPOSTA_ID}",                       "auth"),
    ("10_portal_cliente",              f"/propostas/cliente/{TOKEN}",                     "anon"),
    ("11_obra_detalhes",               f"/obras/{OBRA_ID}",                               "auth"),
    ("12_lista_compras",               f"/compras/?obra_id={OBRA_ID}",                    "auth"),
    ("13_form_nova_compra",            "/compras/nova",                                   "auth"),
    ("14_rdo_lista",                   f"/funcionario/rdo/consolidado?obra_id={OBRA_ID}", "auth"),
    ("15_rdo_form_novo",               f"/rdo/novo?obra_id={OBRA_ID}",                    "auth"),
]

def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    assert "/login" not in page.url, f"Login falhou, URL final: {page.url}"
    print("[OK] Login")

def shoot(page, fname, url):
    full = f"{BASE}{url}"
    print(f"  -> {fname}: {url}")
    try:
        page.goto(full, wait_until="networkidle", timeout=15000)
    except Exception as e:
        print(f"     warn networkidle: {e}; tentando domcontentloaded")
        page.goto(full, wait_until="domcontentloaded", timeout=15000)
    time.sleep(1.2)  # esperar Select2 / charts renderizarem
    try:
        page.evaluate("document.querySelectorAll('.modal.show, .modal-backdrop').forEach(e=>e.remove())")
    except Exception:
        pass
    out = OUT / f"{fname}.png"
    page.screenshot(path=str(out), full_page=True)
    print(f"     saved {out} ({out.stat().st_size} bytes)")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    auth_ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    anon_ctx = browser.new_context(viewport={"width": 1366, "height": 900})

    auth_page = auth_ctx.new_page()
    login(auth_page)

    anon_page = anon_ctx.new_page()

    for fname, url, mode in PAGES:
        page = auth_page if mode == "auth" else anon_page
        try:
            shoot(page, fname, url)
        except Exception as e:
            print(f"     ERRO em {fname}: {e}")

    browser.close()

print("\nFEITO. Arquivos:")
for f in sorted(OUT.glob("*.png")):
    print(f"  {f}")
