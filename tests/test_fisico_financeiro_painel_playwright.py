import pytest

pytestmark = pytest.mark.browser


@pytest.mark.browser
def test_painel_ff_carrega(sige_base_url, browser_launch_options):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(**browser_launch_options)
        page = browser.new_page()
        resp = page.goto(f"{sige_base_url}/cronograma/obra/1/fisico-financeiro",
                         wait_until="domcontentloaded")
        assert resp is not None and resp.status < 500
        browser.close()
