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
                // TomSelect usa valueField:'id' / labelField:'nome'
                ts.addOption({id: String(o.id), nome: o.nome});
                ts.refreshOptions(false);
                ts.addItem(String(o.id), true);
            }""",
            {"id": CTX.insumo_id, "nome": CTX.insumo_nome},
        )
        # garante que o select nativo recebeu o value (o que vai no POST)
        page.wait_for_function(
            "(id) => document.getElementById('comp-insumo-select').value === String(id)",
            arg=CTX.insumo_id,
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

    def test_04_criar_template_proposta(self, page: Page):
        # /templates/novo pré-preenche do template padrão do tenant; preenchemos
        # valores ÚNICOS próprios (fill substitui) para verificar depois no portal.
        page.goto(f"{BASE_URL}/propostas/templates/novo")
        page.wait_for_load_state("networkidle")
        page.fill("[data-testid=template-nome]", CTX.template_nome)
        page.fill("[data-testid=template-apresentacao]", CTX.apresentacao)
        page.fill("[data-testid=template-pagamento]", CTX.pagamento)
        page.fill("[data-testid=template-garantias]", CTX.garantia)
        page.fill("[data-testid=template-prazo]", str(CTX.prazo_dias))
        page.fill("[data-testid=template-validade]", str(CTX.validade_dias))
        # adiciona MINHA cláusula (último bloco) com valores únicos
        page.click("[data-testid=template-add-clausula]")
        ultima = page.locator("#clausulasContainer .clausula-item").last
        ultima.locator("input[name=clausula_titulo]").fill(CTX.clausula_titulo)
        ultima.locator("textarea[name=clausula_texto]").fill(CTX.clausula_texto)
        page.click("[data-testid=template-salvar]")
        page.wait_for_load_state("networkidle")

        def _find():
            from models import PropostaTemplate
            obj = PropostaTemplate.query.filter_by(nome=CTX.template_nome).first()
            return obj.id if obj else None

        CTX.template_id = _db(_find)
        assert CTX.template_id, "template de proposta não foi persistido"

    def test_05_criar_proposta(self, page: Page):
        page.goto(f"{BASE_URL}/propostas/nova")
        page.wait_for_load_state("networkidle")
        page.fill("[data-testid=proposta-cliente-nome]", CTX.cliente_nome)
        page.fill("[data-testid=proposta-cliente-email]", "cliente.e2e@example.com")
        page.fill("[data-testid=proposta-cliente-telefone]", "(11) 90000-0000")
        page.fill("[data-testid=proposta-numero]", CTX.numero_proposta)
        page.fill("[data-testid=proposta-assunto]", f"Obra E2E {SUF}")
        page.select_option("[data-testid=proposta-template]", value=str(CTX.template_id))

        item = page.locator(".servico-item").first
        item.locator("[data-testid=proposta-item-descricao]").fill(CTX.servico_nome)
        item.locator("[data-testid=proposta-item-quantidade]").fill(str(CTX.quantidade))
        item.locator("[data-testid=proposta-item-preco]").fill("80")
        # vincula o serviço do catálogo (hidden item_servico_id) — essencial para o
        # cronograma automático herdar o template de cronograma do serviço
        item.locator("[data-testid=proposta-item-servico-id]").evaluate(
            "(el, v) => el.value = v", str(CTX.servico_id)
        )
        page.click("[data-testid=proposta-salvar]")
        page.wait_for_load_state("networkidle")

        def _info():
            from models import Proposta, PropostaItem
            p = Proposta.query.filter_by(numero=CTX.numero_proposta).first()
            if not p:
                return None
            it = PropostaItem.query.filter_by(proposta_id=p.id).first()
            return {
                "id": p.id,
                "token": p.token_cliente,
                "servico_id": it.servico_id if it else None,
            }

        info = _db(_info)
        assert info, "proposta não foi persistida"
        CTX.proposta_id = info["id"]
        CTX.token = info["token"]
        assert info["servico_id"] == CTX.servico_id, "item não vinculou o serviço (servico_id)"
        assert CTX.token, "token do cliente ausente"

    def test_06_revisar_para_envio(self, page: Page):
        # Cláusulas copiadas do template entram com revisado_em=NULL (pendentes),
        # bloqueando pode_enviar(). Marcamos como revisadas e salvamos.
        page.goto(f"{BASE_URL}/propostas/editar/{CTX.proposta_id}")
        page.wait_for_load_state("networkidle")
        checks = page.locator(".clausula-revisado-check")
        for i in range(checks.count()):
            checks.nth(i).check()
        acks = page.locator("input[name=campo_revisao_ack]")
        for i in range(acks.count()):
            acks.nth(i).check()
        page.click("[data-testid=proposta-editar-salvar]")
        page.wait_for_load_state("networkidle")

        def _state():
            from models import Proposta, PropostaItem
            p = Proposta.query.get(CTX.proposta_id)
            it = PropostaItem.query.filter_by(proposta_id=p.id).first()
            return {"pode": p.pode_enviar(), "servico_id": it.servico_id if it else None}

        st = _db(_state)
        assert st["pode"] is True, "proposta ainda não liberada para envio (revisão pendente)"
        assert st["servico_id"] == CTX.servico_id, "salvar a edição perdeu o vínculo do serviço"

    def test_07_preconfig_cronograma(self, page: Page):
        # Sem cronograma_default_json salvo, a aprovação cai no gate #200 e o
        # cronograma NÃO materializa. Aqui pré-configuramos a partir do template
        # de cronograma herdado do serviço (Alvenaria).
        page.goto(f"{BASE_URL}/propostas/{CTX.proposta_id}/cronograma-revisar")
        page.wait_for_load_state("networkidle")
        nodes = page.locator("[data-testid=cronograma-node]")
        expect(nodes.first).to_be_visible()
        corpo = page.locator("body").inner_text()
        for nome in ["Marcação", "Elevação", "Chapisco"]:
            assert nome in corpo, f"subatividade do template Alvenaria ausente na árvore: {nome}"

        page.click("[data-testid=cronograma-preconfig-salvar]")
        page.wait_for_load_state("networkidle")

        def _cdj():
            from models import Proposta
            return Proposta.query.get(CTX.proposta_id).cronograma_default_json

        assert _db(_cdj), "cronograma_default_json não foi salvo (gate #200 não destravado)"
