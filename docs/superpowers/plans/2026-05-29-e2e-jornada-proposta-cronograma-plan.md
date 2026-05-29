# Plano de Implementação — Teste E2E Playwright: Catálogo → Proposta → Link do Cliente → Cronograma

**Spec:** `docs/superpowers/specs/2026-05-29-e2e-jornada-proposta-cronograma-design.md`
**Branch:** `spec/e2e-jornada-proposta-cronograma` (continuar nela)
**Data:** 2026-05-29

## Objetivo

Criar `tests/test_e2e_jornada_proposta_cronograma_playwright.py`: um teste E2E em Playwright
(browser real) que percorre cadastro de insumo → serviço+composição → vínculo de cronograma →
template de proposta → criação da proposta → revisão+pré-config do cronograma → envio → abertura do
link do cliente (asserções rigorosas) → aprovação pelo cliente → verificação via UI do cronograma
automático materializado e vinculado ao serviço. Inclui adição **aditiva** de `data-testid` nos
templates para tornar os seletores estáveis.

## Visão de arquitetura

- **Stack:** pytest + Playwright **sync** (Chromium headless), app Flask em `localhost:5000`,
  banco com seed Alfa (`scripts/seed_demo_alfa.py`).
- **Login:** `admin_alfa` / `Alfa@2026` via `/login` (campos `input[name=username]`,
  `input[name=password]`).
- **Padrão de teste:** classe `TestJornadaPropostaCronograma`, etapas `test_01_*`…`test_NN_*`
  executadas em ordem; estado compartilhado num objeto `Contexto` de escopo de classe; sessão de
  browser logada via fixture de classe; sufixo único por execução (`SUF`) em todos os nomes.
- **Recuperação de IDs/token:** preferir consulta ao banco via Flask app context (helper
  `_db_query`, padrão já usado em `tests/test_browser_all_modules.py::_get_admin_id`), em vez de
  raspar HTML — mais robusto.

## Rotas e gates confirmados (referência)

| Ação | Rota | Arquivo:linha | Observações |
|------|------|---------------|-------------|
| Criar insumo | POST `/catalogo/insumos/novo` | views/catalogo_views.py:96 | template `insumo_form.html` |
| Criar serviço | POST `/catalogo/servicos/novo` | catalogo_views.py:366 | template `servico_form.html` |
| Add composição | POST `/catalogo/servicos/<id>/composicao/add` | catalogo_views.py:445 | select Tom Select `#comp-insumo-select` |
| Vincular cronograma | POST `/catalogo/servicos/<id>/template` | catalogo_views.py:424 | campo `template_padrao_id` |
| Criar template proposta | POST `/propostas/templates/criar` | propostas_consolidated.py:2025 | template `template_form.html` |
| Criar proposta (+itens) | POST `/propostas/criar` | propostas_consolidated.py:526 | template `nova_proposta.html`; itens no MESMO form (`.servico-item`) |
| Editar/revisar proposta | POST `/propostas/<id>/atualizar` (form em `editar.html`) | propostas_consolidated.py:~1500 | limpa pendências de revisão (`clausula_revisado_flag`, `campo_revisao_ack`) |
| Pré-config cronograma | POST `/propostas/<id>/cronograma-default` | propostas_consolidated.py:2225 | hidden `cronograma_marcado_json` (`#preconfigJson`), botão `#btnSalvarPreconfig` |
| Enviar | POST `/propostas/<id>/enviar` | propostas_consolidated.py:1349 | exige `status='rascunho'` **e** `pode_enviar()` |
| Link público | GET `/propostas/cliente/<token>` | propostas_consolidated.py:2393 | anônimo |
| Cliente aprova | POST `/propostas/cliente/<token>/aprovar` | propostas_consolidated.py:2443 | emite `proposta_aprovada`, atômico |
| Cronograma da obra | GET `/cronograma?obra_id=<id>` | templates/obras/cronograma.html | tarefas em `tr.tarefa-row`; badge "do contrato" quando `gerada_por_proposta_item_id` |

**Gates que o teste precisa respeitar (descobertos na exploração):**
1. **Gate de revisão de cláusulas (#31):** proposta criada de template tem cláusulas pendentes;
   `enviar` só funciona após revisão (salvar o form `editar` com flags de revisão).
2. **Gate de cronograma (#200):** sem `cronograma_default_json` salvo, a aprovação NÃO materializa o
   cronograma (obra cai em revisão inicial). Por isso a pré-config (`cronograma-default`) é obrigatória.
3. **Vínculo tarefa↔serviço não é exposto no HTML do cronograma da obra hoje** → será adicionado via
   `data-testid`/`data-servico-id` no `tr.tarefa-row` (Task de edição de template).

## Convenção de `data-testid`

kebab-case, prefixo de domínio. Aplicados de forma **aditiva** (não remover classes/ids atuais).
Lista canônica abaixo, por template.

---

## TAREFAS

> Cada tarefa: editar/criar arquivos indicados, rodar o comando, confirmar saída, commitar.
> Pré-condição global: servidor SIGE rodando em `localhost:5000` com seed Alfa aplicado
> (`bash run_tests.sh` sobe o servidor; o seed deve estar no banco).

### Task 0 — Scaffolding do teste, fixtures, helpers e alias de execução

**Arquivo (criar):** `tests/test_e2e_jornada_proposta_cronograma_playwright.py`

Conteúdo inicial (sem etapas ainda — só infra que compila e roda "vazio"):

```python
"""
E2E (Playwright, browser real) — jornada comercial completa do SIGE:
Catálogo (insumo → serviço + composição + vínculo de cronograma) → template de proposta →
proposta → revisão + pré-config de cronograma → envio → link do cliente (asserções rigorosas) →
aprovação pelo cliente → verificação do cronograma automático via UI.

Pré-requisito: servidor em localhost:5000 com seed Alfa (scripts/seed_demo_alfa.py).
Execução:
    pytest tests/test_e2e_jornada_proposta_cronograma_playwright.py -v
    bash run_tests.sh --jornada
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

# Sufixo único por execução (não usa Date.now do harness; runtime real é ok aqui)
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
    preco_unit = 80.00
    # preenchidos em runtime:
    insumo_id = None
    servico_id = None
    template_id = None
    proposta_id = None
    token = None
    obra_id = None


CTX = Contexto()


def _db(fn):
    """Executa fn(db_session_models) dentro do app context Flask. Retorna o valor."""
    import main  # noqa: importa app
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
        # login admin
        pg.goto(f"{BASE_URL}/login")
        pg.fill("input[name=username]", DEMO_USER)
        pg.fill("input[name=password]", DEMO_PASS)
        pg.click("button[type=submit]")
        pg.wait_for_load_state("networkidle")
        assert "/login" not in pg.url, "login falhou"
        yield pg
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
class TestJornadaPropostaCronograma:
    def test_00_login_ok(self, page: Page):
        assert "/login" not in page.url
```

**Editar:** `run_tests.sh` — adicionar alias `--jornada`:
no bloco `while [[ $# -gt 0 ]]; do case "$1" in`, acrescentar antes do `*)`:
```bash
        --jornada)      BLOCO_FILTER="JORNADA"; shift ;;
```
e onde o pytest é montado, tratar `JORNADA` apontando para o novo arquivo
(`tests/test_e2e_jornada_proposta_cronograma_playwright.py`) em vez de `test_browser_all_modules.py`.
(Confirmar a montagem exata do comando pytest no script ao editar.)

**Rodar / esperado:**
```bash
bash run_tests.sh   # garante servidor up
pytest tests/test_e2e_jornada_proposta_cronograma_playwright.py::TestJornadaPropostaCronograma::test_00_login_ok -v
# esperado: 1 passed
```

**Commit:** `test(e2e): scaffolding da jornada proposta→cronograma (login + fixtures)`

---

### Task 1 — Spike: confirmar comportamento ao vivo e congelar a sequência de requests

**Objetivo:** de-riscar os gates antes de escrever as etapas. Não produz código de teste final;
produz um documento curto de notas (`tests/_notes_jornada_spike.md`, git-ignore opcional) e confirma:

Passos (executar manualmente/via script de uso único, logado como admin Alfa):
- [ ] Criar insumo, serviço, composição, vínculo de cronograma pela UI e confirmar os flashes.
- [ ] Criar proposta de template via `/propostas/nova` → `/propostas/criar`; anotar para onde
      redireciona e como obter `proposta_id` e `token_cliente` (confirmar via
      `_db`: `Proposta.query.filter_by(numero=...)`).
- [ ] Verificar se a proposta recém-criada já é `pode_enviar()` ou se precisa salvar o form
      `editar` com `clausula_revisado_flag`/`campo_revisao_ack`. **Registrar a sequência mínima
      de POST que limpa as pendências.**
- [ ] Abrir `/propostas/<id>/cronograma-revisar`, marcar nós e salvar `cronograma-default`;
      confirmar que `proposta.cronograma_default_json` fica preenchido.
- [ ] `POST /propostas/<id>/enviar`; confirmar `status='enviada'`.
- [ ] `GET /propostas/cliente/<token>` anônimo (novo context sem login) renderiza.
- [ ] `POST /propostas/cliente/<token>/aprovar`; confirmar que cria `Obra` e materializa
      `TarefaCronograma` (consultar via `_db`). Anotar `obra_id` e como achar a obra (por
      `proposta_id`/`numero`).
- [ ] Abrir `/cronograma?obra_id=<id>` e confirmar as tarefas e o badge "do contrato".

**Saída:** notas com a sequência exata confirmada. As tarefas seguintes assumem essa sequência.
**Commit:** `docs(e2e): notas de spike da jornada (sequência de requests confirmada)` (ou nenhum, se notas forem ignoradas).

---

### Task 2 — `data-testid` no catálogo de insumos + etapa "criar insumo"

**Editar:** `templates/catalogo/insumo_form.html` — adicionar (aditivo):
- linha 15 (nome): `data-testid="insumo-nome"`
- linha 19 (tipo, select): `data-testid="insumo-tipo"`
- linha 28 (unidade): `data-testid="insumo-unidade"`
- linha 105 (preco): `data-testid="insumo-preco"`
- linha 109 (botão submit): `data-testid="insumo-salvar"`

**Editar:** test — adicionar etapa:
```python
    def test_01_criar_insumo(self, page: Page):
        page.goto(f"{BASE_URL}/catalogo/insumos/novo")
        page.fill("[data-testid=insumo-nome]", CTX.insumo_nome)
        page.select_option("[data-testid=insumo-tipo]", index=1)   # primeiro tipo válido
        page.fill("[data-testid=insumo-unidade]", "kg")
        page.fill("[data-testid=insumo-preco]", "1,50")
        page.click("[data-testid=insumo-salvar]")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".alert-success")).to_be_visible()
        CTX.insumo_id = _db(lambda: __import__("models").Insumo.query
                            .filter_by(nome=CTX.insumo_nome).first().id)
        assert CTX.insumo_id
```

**Rodar:** `pytest …::test_01_criar_insumo -v` → 1 passed.
**Commit:** `test(e2e): etapa criar insumo + data-testid no insumo_form`

---

### Task 3 — `data-testid` no serviço + etapa "criar serviço"

**Editar:** `templates/catalogo/servico_form.html`:
- linha 15 (nome): `data-testid="servico-nome"`
- linha 19 (categoria): `data-testid="servico-categoria"`
- linha 23 (unidade_medida): `data-testid="servico-unidade"`
- linha 41 (submit): `data-testid="servico-salvar"`

**Editar:** test:
```python
    def test_02_criar_servico(self, page: Page):
        page.goto(f"{BASE_URL}/catalogo/servicos/novo")
        page.fill("[data-testid=servico-nome]", CTX.servico_nome)
        page.fill("[data-testid=servico-categoria]", "Vedação")
        page.fill("[data-testid=servico-unidade]", "m2")
        page.click("[data-testid=servico-salvar]")
        page.wait_for_load_state("networkidle")
        CTX.servico_id = _db(lambda: __import__("models").Servico.query
                             .filter_by(nome=CTX.servico_nome).first().id)
        assert CTX.servico_id
```

**Rodar / Commit:** `test(e2e): etapa criar serviço + data-testid no servico_form`

---

### Task 4 — `data-testid` na composição + etapas "composição" e "vínculo cronograma"

**Editar:** `templates/catalogo/composicao_servico.html`:
- linha 255 (`#comp-insumo-select`, Tom Select): `data-testid="composicao-insumo"`
- linha 264 (`#comp-coef-input`): `data-testid="composicao-coeficiente"`
- linha 270 (botão adicionar): `data-testid="composicao-add"`
- linha 281 (tabela de composições): `data-testid="composicao-tabela"`
- linha 214 (select `template_padrao_id`): `data-testid="servico-template-select"`
- linha 229 (botão salvar vínculo): `data-testid="servico-template-salvar"`

**Editar:** test — Tom Select substitui o `<select>`; usar `select_option` no elemento
subjacente (Playwright consegue setar o `<select>` escondido) e disparar `change`, **ou** abrir o
widget e clicar a opção. Caminho robusto:
```python
    def test_03_composicao_e_vinculo_cronograma(self, page: Page):
        page.goto(f"{BASE_URL}/catalogo/servicos/{CTX.servico_id}/composicao")
        # Tom Select: setar o <select> subjacente por value (id do insumo) e disparar change
        page.select_option("[data-testid=composicao-insumo]", value=str(CTX.insumo_id))
        page.fill("[data-testid=composicao-coeficiente]", "1,0")
        page.click("[data-testid=composicao-add]")
        page.wait_for_load_state("networkidle")
        expect(page.locator("[data-testid=composicao-tabela]")
               ).to_contain_text(CTX.insumo_nome)
        # vincular cronograma-template seedado
        page.select_option("[data-testid=servico-template-select]",
                           label=CRONOGRAMA_TEMPLATE_NOME)
        page.click("[data-testid=servico-template-salvar]")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".alert-success")).to_contain_text("vinculado")
        # confirma vínculo no banco
        tpl_id = _db(lambda: __import__("models").Servico.query
                     .get(CTX.servico_id).template_padrao_id)
        assert tpl_id is not None
```
> Se `select_option` não disparar a sincronização do Tom Select, fallback: clicar no controle Tom
> Select (`.ts-control`) e clicar a opção por texto. A Task 1 (spike) confirma qual caminho funciona.

**Rodar / Commit:** `test(e2e): composição + vínculo de cronograma + data-testid`

---

### Task 5 — `data-testid` no template de proposta + etapa "criar template"

**Editar:** `templates/propostas/template_form.html`:
- linha 82 (nome): `data-testid="template-nome"`
- linha 114 (texto_apresentacao): `data-testid="template-apresentacao"`
- linha 157 (condicoes_pagamento): `data-testid="template-pagamento"`
- linha 162 (garantias): `data-testid="template-garantias"`
- linha 202 (prazo_entrega_dias): `data-testid="template-prazo"`
- linha 207 (validade_dias): `data-testid="template-validade"`
- linha 234 (clausula_titulo): `data-testid="template-clausula-titulo"`
- linha 240 (clausula_texto): `data-testid="template-clausula-texto"`
- linha 288 (btnAdicionarClausula): `data-testid="template-add-clausula"`
- linha 296 (submit): `data-testid="template-salvar"`

**Editar:** test:
```python
    def test_04_criar_template_proposta(self, page: Page):
        page.goto(f"{BASE_URL}/propostas/templates/novo")
        page.fill("[data-testid=template-nome]", CTX.template_nome)
        page.fill("[data-testid=template-apresentacao]", CTX.apresentacao)
        page.fill("[data-testid=template-pagamento]", CTX.pagamento)
        page.fill("[data-testid=template-garantias]", CTX.garantia)
        page.fill("[data-testid=template-prazo]", str(CTX.prazo_dias))
        page.fill("[data-testid=template-validade]", str(CTX.validade_dias))
        # 1ª cláusula (já existe 1 bloco; preencher; se vazio, clicar add antes)
        page.fill("[data-testid=template-clausula-titulo]", CTX.clausula_titulo)
        page.fill("[data-testid=template-clausula-texto]", CTX.clausula_texto)
        page.click("[data-testid=template-salvar]")
        page.wait_for_load_state("networkidle")
        CTX.template_id = _db(lambda: __import__("models").PropostaTemplate.query
                              .filter_by(nome=CTX.template_nome).first().id)
        assert CTX.template_id
```
> Se houver >1 bloco de cláusula repetível, mirar o primeiro com `.first`. Confirmar no spike.

**Rodar / Commit:** `test(e2e): criar template de proposta + data-testid`

---

### Task 6 — `data-testid` na nova proposta + etapa "criar proposta com item de serviço"

**Editar:** `templates/propostas/nova_proposta.html`:
- linha 53 (`#template_id`): `data-testid="proposta-template"`
- linha 78 (cliente_nome): `data-testid="proposta-cliente-nome"`
- linha 82 (cliente_email): `data-testid="proposta-cliente-email"`
- linha 88 (cliente_telefone): `data-testid="proposta-cliente-telefone"`
- linha 105 (numero_proposta): `data-testid="proposta-numero"`
- linha 110 (assunto): `data-testid="proposta-assunto"`
- na linha do item `.servico-item` (linha ~162-214): adicionar nos campos do item
  `.servico-catalogo-search` → `data-testid="proposta-item-busca"`;
  `.servico-descricao` → `data-testid="proposta-item-descricao"`;
  `.servico-quantidade` → `data-testid="proposta-item-quantidade"`;
  `.servico-valor-unitario` → `data-testid="proposta-item-preco"`
  (como é template repetível por JS, garantir que o markup base do item — provavelmente um
  `<template>`/primeiro bloco — receba os atributos; confirmar no spike onde o JS clona).
- linha 388 (submit Criar Proposta): `data-testid="proposta-salvar"`

**Editar:** test:
```python
    def test_05_criar_proposta(self, page: Page):
        page.goto(f"{BASE_URL}/propostas/nova")
        page.fill("[data-testid=proposta-cliente-nome]", CTX.cliente_nome)
        page.fill("[data-testid=proposta-cliente-email]", "cliente.e2e@example.com")
        page.fill("[data-testid=proposta-cliente-telefone]", "(11) 90000-0000")
        page.fill("[data-testid=proposta-numero]", CTX.numero_proposta)
        page.fill("[data-testid=proposta-assunto]", f"Obra E2E {SUF}")
        page.select_option("[data-testid=proposta-template]", value=str(CTX.template_id))
        # item de serviço (1º bloco .servico-item)
        item = page.locator(".servico-item").first
        item.locator("[data-testid=proposta-item-busca]").fill(CTX.servico_nome)
        # selecionar do datalist: confirmar no spike se preenche descrição/preço sozinho;
        # senão, preencher manualmente:
        item.locator("[data-testid=proposta-item-descricao]").fill(CTX.servico_nome)
        item.locator("[data-testid=proposta-item-quantidade]").fill(str(CTX.quantidade))
        item.locator("[data-testid=proposta-item-preco]").fill("80,00")
        page.click("[data-testid=proposta-salvar]")
        page.wait_for_load_state("networkidle")
        prop = _db(lambda: __import__("models").Proposta.query
                   .filter_by(numero=CTX.numero_proposta).first())
        CTX.proposta_id = _db(lambda: __import__("models").Proposta.query
                              .filter_by(numero=CTX.numero_proposta).first().id)
        CTX.token = _db(lambda: __import__("models").Proposta.query
                        .filter_by(numero=CTX.numero_proposta).first().token_cliente)
        assert CTX.proposta_id and CTX.token
```

**Rodar / Commit:** `test(e2e): criar proposta com item de serviço + data-testid`

---

### Task 7 — Etapa "revisar cláusulas/campos" (limpar gate de envio)

Implementar conforme sequência confirmada no spike (Task 1). Caminho esperado: abrir
`/propostas/<id>/editar`, marcar as cláusulas/campos como revisados e salvar (`/atualizar`).

**Editar:** `templates/propostas/editar.html` — adicionar `data-testid` no botão de salvar
(`data-testid="proposta-editar-salvar"`) e, se houver, no controle "marcar tudo como revisado".

**Editar:** test:
```python
    def test_06_revisar_para_envio(self, page: Page):
        page.goto(f"{BASE_URL}/propostas/{CTX.proposta_id}/editar")
        # marcar revisões conforme spike (flags clausula_revisado_flag / campo_revisao_ack)
        # ... (sequência confirmada na Task 1) ...
        page.click("[data-testid=proposta-editar-salvar]")
        page.wait_for_load_state("networkidle")
        pode = _db(lambda: __import__("models").Proposta.query
                   .get(CTX.proposta_id).pode_enviar())
        assert pode is True
```

**Rodar / Commit:** `test(e2e): revisar cláusulas/campos para liberar envio + data-testid`

---

### Task 8 — `data-testid` no cronograma-revisar + etapa "pré-config do cronograma"

**Editar:** `templates/propostas/cronograma_revisar.html`:
- nós `.chk-node` / `.node-label` (macro `render_nodes`): adicionar
  `data-testid="cronograma-node"` no container do nó e expor o nome em `.node-label`.
- linha 329 (`#btnSalvarPreconfig`): adicionar `data-testid="cronograma-preconfig-salvar"`.

**Editar:** test:
```python
    def test_07_preconfig_cronograma(self, page: Page):
        page.goto(f"{BASE_URL}/propostas/{CTX.proposta_id}/cronograma-revisar")
        # confirma que a árvore mostra o serviço e subatividades do template Alvenaria
        expect(page.locator("[data-testid=cronograma-node]").first).to_be_visible()
        # marcar nós necessários (checkboxes .chk-node) — manter marcação default
        page.click("[data-testid=cronograma-preconfig-salvar]")
        page.wait_for_load_state("networkidle")
        cdj = _db(lambda: __import__("models").Proposta.query
                  .get(CTX.proposta_id).cronograma_default_json)
        assert cdj   # snapshot salvo → destrava materialização na aprovação
```

**Rodar / Commit:** `test(e2e): pré-config do cronograma (cronograma-default) + data-testid`

---

### Task 9 — `data-testid` no botão Enviar + etapa "enviar proposta"

**Editar:** `templates/propostas/visualizar.html` (ou onde está o botão que dá POST em
`/propostas/<id>/enviar`) — `data-testid="proposta-enviar"` no botão/submit.

**Editar:** test:
```python
    def test_08_enviar_proposta(self, page: Page):
        page.goto(f"{BASE_URL}/propostas/{CTX.proposta_id}")   # /visualizar
        page.click("[data-testid=proposta-enviar]")
        page.wait_for_load_state("networkidle")
        status = _db(lambda: (__import__("models").Proposta.query
                     .get(CTX.proposta_id).status or "").lower())
        assert status == "enviada"
```

**Rodar / Commit:** `test(e2e): enviar proposta + data-testid no botão enviar`

---

### Task 10 — `data-testid` no portal do cliente + etapa "link do cliente: asserções rigorosas"

**Editar:** `templates/propostas/portal_cliente.html` (e partial `_clausulas.html`,
`_servico_card.html`):
- bloco de apresentação/descrição (linha 516): `data-testid="portal-apresentacao"`
- container de cláusulas (linha 640 / dentro de `_clausulas.html`): cada cláusula com
  `data-testid="portal-clausula"` (título e texto acessíveis)
- card de item (`_servico_card.html`): `data-testid="portal-item"`, com sub-hooks para
  descrição/quantidade/preço/subtotal
- total geral (linha 508/578): `data-testid="portal-total"`
- condições de pagamento e garantias: `data-testid="portal-pagamento"` / `data-testid="portal-garantias"`
- botão Aprovar (linha 704): `data-testid="portal-aprovar"`
- botão Rejeitar (linha 728): `data-testid="portal-rejeitar"`
- (não adicionar testid a nada que seja admin — confirmar que não há)

**Editar:** test — **novo browser context anônimo** (sem login):
```python
    def test_09_portal_cliente_layout(self, page: Page):
        # contexto anônimo separado
        ctx2 = page.context.browser.new_context()
        cli = ctx2.new_page()
        cli.set_default_timeout(TIMEOUT_MS)
        cli.goto(f"{BASE_URL}/propostas/cliente/{CTX.token}")
        # template renderizado, conteúdo exato:
        expect(cli.locator("[data-testid=portal-apresentacao]")).to_contain_text(CTX.apresentacao)
        expect(cli.locator("[data-testid=portal-pagamento]")).to_contain_text(CTX.pagamento)
        expect(cli.locator("[data-testid=portal-garantias]")).to_contain_text(CTX.garantia)
        expect(cli.locator("[data-testid=portal-clausula]")).to_contain_text(CTX.clausula_titulo)
        expect(cli.locator("[data-testid=portal-clausula]")).to_contain_text(CTX.clausula_texto)
        # item/serviço + valor BR
        expect(cli.locator("[data-testid=portal-item]")).to_contain_text(CTX.servico_nome)
        expect(cli.locator("[data-testid=portal-total]")).to_contain_text("R$")
        # sem vazamento interno
        body = cli.locator("body").inner_text().lower()
        for proibido in ["admin", "custo_real", "editar proposta", "cronograma-revisar"]:
            assert proibido not in body, f"vazou controle interno: {proibido}"
        # aprovar/rejeitar presentes
        expect(cli.locator("[data-testid=portal-aprovar]")).to_be_visible()
        expect(cli.locator("[data-testid=portal-rejeitar]")).to_be_visible()
        # (opcional) screenshot artefato
        cli.screenshot(path=f"tests/reports/portal_cliente_{SUF}.png", full_page=True)
        # guarda a página do cliente para a próxima etapa
        self.__class__._cli = cli
```
> Ajustar a lista `proibido` conforme o que o spike confirmar visível/oculto na página.

**Rodar / Commit:** `test(e2e): link do cliente com asserções rigorosas + data-testid no portal`

---

### Task 11 — Etapa "cliente aprova pelo link"

**Editar:** test:
```python
    def test_10_cliente_aprova(self, page: Page):
        cli = self.__class__._cli
        cli.click("[data-testid=portal-aprovar]")
        # se houver modal de confirmação (modalAprovar), confirmar:
        # cli.click("[data-testid=portal-aprovar-confirmar]")  # add testid no submit do modal
        cli.wait_for_load_state("networkidle")
        status = _db(lambda: (__import__("models").Proposta.query
                     .get(CTX.proposta_id).status or "").lower())
        assert status in ("aprovada", "aprovado")
        # obra criada pela aprovação
        CTX.obra_id = _db(lambda: __import__("handlers_lookup").obra_id_da_proposta(CTX.proposta_id))
        assert CTX.obra_id
```
> O modal de aprovação (`#modalAprovar`, campo `observacoes`) provavelmente exige um 2º clique no
> submit do modal — adicionar `data-testid="portal-aprovar-confirmar"` nesse submit (Task 10) e o
> clique aqui. Confirmar no spike.
> `obra_id_da_proposta` é uma consulta inline (ex.: `Obra.query.filter_by(...proposta_id...)` ou via
> `ItemMedicaoComercial`); a query exata é confirmada no spike e escrita aqui sem placeholder.

**Rodar / Commit:** `test(e2e): cliente aprova pelo link e gera obra`

---

### Task 12 — `data-testid` no cronograma da obra + etapa "verificar cronograma automático"

**Editar:** `templates/obras/cronograma.html` (linha 127-137, `tr.tarefa-row`):
- adicionar `data-testid="cronograma-tarefa"` na `tr`
- expor o serviço de origem: `data-servico-id="{{ t.gerada_por_proposta_item.servico_id or '' }}"`
  e `data-testid="cronograma-tarefa-servico"` no badge "do contrato", para verificação do vínculo.
  (Validar no backend que `t.gerada_por_proposta_item` está acessível no template; se não,
  ajustar a view `/cronograma` para passar o servico_id — mudança mínima, confirmar.)

**Editar:** test:
```python
    def test_11_verifica_cronograma_obra(self, page: Page):
        page.goto(f"{BASE_URL}/cronograma?obra_id={CTX.obra_id}")
        page.wait_for_load_state("networkidle")
        tarefas = page.locator("[data-testid=cronograma-tarefa]")
        expect(tarefas.first).to_be_visible()
        texto = tarefas.all_inner_texts()
        joined = "\n".join(texto)
        # subatividades do template Alvenaria materializadas
        for nome in ["Marcação", "Elevação", "Chapisco"]:
            assert nome in joined, f"subatividade ausente no cronograma: {nome}"
        # vínculo com o serviço criado (via data-servico-id no nó do contrato)
        vinc = page.locator(f"[data-servico-id='{CTX.servico_id}']")
        expect(vinc.first).to_be_visible()
```

**Rodar / Commit:** `test(e2e): verifica cronograma automático e vínculo serviço via UI`

---

### Task 13 — Execução completa, estabilização e limpeza

- [ ] Rodar a jornada inteira em ordem:
  ```bash
  bash run_tests.sh   # servidor up
  pytest tests/test_e2e_jornada_proposta_cronograma_playwright.py -v
  # esperado: todas as etapas (test_00..test_11) passed
  ```
- [ ] Rodar 2x seguidas (sufixo muda por execução) para confirmar idempotência/isolamento.
- [ ] Remover seletores frágeis remanescentes; garantir que pontos críticos usam `data-testid`.
- [ ] Remover notas de spike se não forem versionadas; revisar imports e helpers `_db`.
- [ ] Atualizar `tests/playwright_run_notes.py` / README de testes se necessário com o alias `--jornada`.
- **Commit:** `test(e2e): jornada proposta→cronograma verde de ponta a ponta`

---

## Auto-revisão do plano (checklist writing-plans)

1. **Cobertura do spec:** todas as 10 etapas do spec (§5) mapeadas em tarefas (Tasks 2–12);
   `data-testid` (spec §7) distribuído por template em cada tarefa; verificação via UI (spec §5
   etapa 10) na Task 12; asserções rigorosas (spec §4) na Task 10. ✅
2. **Gates do spec §6:** revisão de cláusulas (Task 7) e pré-config de cronograma (Task 8)
   presentes e obrigatórios. ✅
3. **Dependências entre tarefas:** Task 1 (spike) congela a sequência que Tasks 7, 11 e o
   datalist da Task 6 dependem — declarado explicitamente. ✅
4. **Sem placeholders de implementação:** código concreto por etapa; os 3 pontos dependentes de
   comportamento ao vivo (revisão p/ envio, datalist de catálogo, query da obra) são resolvidos no
   spike e escritos sem `TBD`. ✅

## Handoff de execução

Duas opções:
- **Inline com checkpoints:** executar Task a Task, rodando pytest e commitando a cada uma.
- **Subagente por tarefa:** um agente fresco por tarefa, recebendo este plano + o spec.

Recomendado: inline, porque cada etapa depende do estado da anterior e do servidor vivo.
