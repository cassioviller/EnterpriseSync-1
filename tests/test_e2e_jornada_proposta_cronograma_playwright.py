"""
E2E (Playwright, browser real) — jornada comercial completa do SIGE:
Catálogo (insumo → serviço + composição + vínculo de cronograma) → template de proposta →
proposta → revisão + pré-config de cronograma → envio → link do cliente (asserções rigorosas) →
aprovação pelo cliente → verificação do cronograma automático via UI.

Pré-requisito: servidor em localhost:5000 com seed Alfa (scripts/seed_demo_alfa.py).
Execução:
    pytest tests/test_e2e_jornada_proposta_cronograma_playwright.py -v
    bash run_tests.sh --jornada

Notas de ambiente confirmadas no spike:
- Login: campos username/password + csrf_token (form real), botão submit.
- Form de nova proposta: GET /propostas/nova -> render nova_proposta.html -> POST /propostas/criar.
- Cronograma da obra: GET /cronograma/obra/<obra_id>.
- O processo de teste compartilha o MESMO banco Postgres do servidor (dados criados via browser
  são visíveis nas consultas _db()).
"""
import os
import time

import pytest
from playwright.sync_api import sync_playwright, Page, expect

BASE_URL = os.environ.get("PW_BASE_URL", "http://localhost:5000")
TIMEOUT_MS = int(os.environ.get("SIGE_TIMEOUT_MS", "30000"))
DEMO_USER = "admin_alfa"
DEMO_PASS = "Alfa@2026"
# Template de cronograma seedado que será vinculado ao serviço (seed_demo_alfa.py:698)
CRONOGRAMA_TEMPLATE_NOME = "Alvenaria de bloco cerâmico — padrão"

# Sufixo único por execução (runtime real; não depende do harness)
SUF = os.environ.get("E2E_SUF") or time.strftime("%H%M%S")


class Contexto:
    """Estado compartilhado entre as etapas sequenciais."""
    insumo_nome = f"Cimento E2E {SUF}"
    servico_nome = f"Servico E2E {SUF}"
    template_nome = f"Template E2E {SUF}"
    cliente_nome = f"Cliente E2E {SUF}"
    numero_proposta = f"E2E-{SUF}"
    apresentacao = f"APRESENTACAO-E2E-{SUF}"
    pagamento = f"PAGAMENTO-E2E-{SUF}"
    garantia = f"GARANTIA-E2E-{SUF}"
    clausula_titulo = f"CLAUSULA-TIT-{SUF}"
    clausula_texto = f"CLAUSULA-TXT-{SUF}"
    prazo_dias = 45
    validade_dias = 30
    quantidade = 250
    preco_unit = "80,00"
    # preenchidos em runtime:
    insumo_id = None
    servico_id = None
    template_id = None
    proposta_id = None
    token = None
    obra_id = None


CTX = Contexto()


def _db(fn):
    """Executa fn() dentro do app context Flask e retorna o valor.

    O import de app/models dispara as migrações automáticas UMA vez por processo
    (no primeiro import); as chamadas subsequentes são apenas consultas.
    """
    from app import app as flask_app
    with flask_app.app_context():
        return fn()


@pytest.fixture(scope="class")
def page():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(TIMEOUT_MS)
        # login admin via formulário real (inclui csrf_token)
        pg.goto(f"{BASE_URL}/login")
        pg.fill("input[name=username]", DEMO_USER)
        pg.fill("input[name=password]", DEMO_PASS)
        pg.click("button[type=submit]")
        pg.wait_for_load_state("networkidle")
        assert "/login" not in pg.url, f"login falhou, url atual: {pg.url}"
        yield pg
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
class TestJornadaPropostaCronograma:
    def test_00_login_ok(self, page: Page):
        assert "/login" not in page.url

    def test_01_criar_insumo(self, page: Page):
        page.goto(f"{BASE_URL}/catalogo/insumos/novo")
        page.fill("[data-testid=insumo-nome]", CTX.insumo_nome)
        page.select_option("[data-testid=insumo-tipo]", value="MATERIAL")
        page.fill("[data-testid=insumo-unidade]", "kg")
        page.fill("[data-testid=insumo-preco]", "1,50")
        page.click("[data-testid=insumo-salvar]")
        page.wait_for_load_state("networkidle")

        def _find():
            from models import Insumo
            obj = Insumo.query.filter_by(nome=CTX.insumo_nome).first()
            return obj.id if obj else None

        CTX.insumo_id = _db(_find)
        assert CTX.insumo_id, "insumo não foi persistido"

    def test_02_criar_servico(self, page: Page):
        page.goto(f"{BASE_URL}/catalogo/servicos/novo")
        page.fill("[data-testid=servico-nome]", CTX.servico_nome)
        page.fill("[data-testid=servico-categoria]", "Vedação")
        page.fill("[data-testid=servico-unidade]", "m2")
        page.click("[data-testid=servico-salvar]")
        page.wait_for_load_state("networkidle")

        def _find():
            from models import Servico
            obj = Servico.query.filter_by(nome=CTX.servico_nome).first()
            return obj.id if obj else None

        CTX.servico_id = _db(_find)
        assert CTX.servico_id, "serviço não foi persistido"
        # salvar redireciona direto para a composição
        assert f"/catalogo/servicos/{CTX.servico_id}/composicao" in page.url

    def test_03_composicao_e_vinculo_cronograma(self, page: Page):
        page.goto(f"{BASE_URL}/catalogo/servicos/{CTX.servico_id}/composicao")
        page.wait_for_load_state("networkidle")
        # O select de insumo é um TomSelect que só carrega 10 opções no DOM;
        # usamos a API do TomSelect para adicionar/selecionar o insumo criado.
        page.wait_for_function(
            "() => document.getElementById('comp-insumo-select') "
            "&& document.getElementById('comp-insumo-select').tomselect"
        )
        page.evaluate(
            """(o) => {
                const sel = document.getElementById('comp-insumo-select');
                const ts = sel.tomselect;
                ts.addOption({value: String(o.id), text: o.nome});
                ts.addItem(String(o.id));
            }""",
            {"id": CTX.insumo_id, "nome": CTX.insumo_nome},
        )
        page.fill("[data-testid=composicao-coeficiente]", "1")
        page.click("[data-testid=composicao-add]")
        page.wait_for_load_state("networkidle")
        expect(page.locator("[data-testid=composicao-tabela]")).to_contain_text(CTX.insumo_nome)

        # vincular o template de cronograma seedado (select por value — o label
        # concatena " — categoria", então buscamos o id no banco)
        def _tpl_id():
            from models import CronogramaTemplate
            obj = CronogramaTemplate.query.filter_by(nome=CRONOGRAMA_TEMPLATE_NOME).first()
            return obj.id if obj else None

        tpl_id = _db(_tpl_id)
        assert tpl_id, f"template de cronograma '{CRONOGRAMA_TEMPLATE_NOME}' não existe no seed"
        page.select_option("[data-testid=servico-template-select]", value=str(tpl_id))
        page.click("[data-testid=servico-template-salvar]")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".alert-success[role=alert]")).to_contain_text("vinculado")

        def _svc_tpl():
            from models import Servico
            return Servico.query.get(CTX.servico_id).template_padrao_id

        assert _db(_svc_tpl) == tpl_id, "vínculo serviço→cronograma não persistiu"
