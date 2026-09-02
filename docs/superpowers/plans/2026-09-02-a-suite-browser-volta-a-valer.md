# A suíte browser volta a valer — Implementation Plan

> **Estado em 2026-09-02:** ✅ **FECHADO — 7/7 tasks.**
>
> | Task | Estado |
> |---|---|
> | 1 — a guarda de seletor entra no gate | ✅ `5416d581` — 19 testes novos, com RED provado quebrando o template de propósito |
> | 2 — o helper de proposta usa o `<select>` | ✅ `f62de068` |
> | 3 — a NF do teste de almoxarifado nasce única | ✅ `cc5e3ad2`, e `8f2a4694` (o teste parava de aceitar a recusa A09 como sucesso) |
> | 4 — `_flash_em_pagina` para de devolver painel estático | ✅ `92840194` |
> | 5 — a suíte inteira, destacada | ✅ **3435 passed, 1 failed, 8 skipped, 72 xfailed**. 🔬 A primeira rodada deu 12 failed + 68 errors, e era **um defeito só**: fixture de sessão segurando `sync_playwright()` (`a80f1ddc`, guarda em `tests/test_contrato_isolamento_playwright.py`). Dela nasceu o runner retomável (`1573f348`) |
> | 6 — a jornada E2E, que nunca rodou | ✅ **19 passed, 0 failed em 50.4s** (`160c7282`) — com ela a **Onda 6 fecha inteira** |
> | 7 — o gate consolida e os três registros fecham | ✅ **gate 3247 passed, 8 skipped, 201 deselected, 72 xfailed, 0 failed** (47:43) — 54 acima do piso de 01/09, com dono para cada um |
>
> **O único vermelho da suíte é o achado P4 do RDO unificado**, registrado em
> `docs/auditoria/achados-code-review-2026-08-25.md` — decisão de produto, não
> conserto desta rodada.
>
> 🔬 **Nenhum código de produção mudou nesta rodada**, como a constraint mandava.
> As 4 falhas eram teste desatualizado: `1394d907` (05/08) trocou o input de
> cliente por `<select>` e o helper do browser nunca soube; `bbe74f00` (04/08)
> pôs dedup de NF e os testes gravavam NF fixa contra banco persistente.
>
> 📖 Os checkboxes de Step das Tasks 1–6 ficam como estavam: o registro de
> execução desta casa é a tabela acima com o commit de cada task — mesmo
> formato de `2026-08-28-o-que-nao-persiste.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Devolver a `tests/test_browser_all_modules.py` a capacidade de provar
alguma coisa — consertando as 4 falhas cuja causa raiz já está medida, pondo no
**gate** a guarda que teria pego as duas em 05/08, e rodando a jornada E2E que
nunca rodou.

**Architecture:** As 4 falhas **não são regressão de produção**. São duas
famílias de podridão de teste, cada uma com um mecanismo diferente, e o plano
ataca os dois mecanismos, não os 4 sintomas. **(a) Deriva de seletor:** o
formulário de proposta trocou `input[name="cliente_nome"]` por
`<select name="cliente_id">` em 05/08 e o helper do browser nunca soube — a
prova só existia numa suíte que não roda no gate, então o vermelho ficou
invisível por 28 dias. A correção do seletor é de uma linha; **a correção do
mecanismo é uma guarda no gate**, e é ela que dá valor a esta rodada.
**(b) Teste não idempotente:** os dois testes de almoxarifado gravam nota fiscal
de valor **fixo** contra um banco **persistente**, e o guard A09 (correto, de
04/08) os recusa a partir da segunda execução. Passam uma vez e queimam o
próprio fixture. A correção é a NF nascer única por rodada — o mesmo padrão que
o teste de proposta ao lado já usa.

Um terceiro achado entra junto porque foi ele que escondeu os outros dois:
`_flash_em_pagina` casa `.alert-info` genérico e devolveu o painel **estático**
da página de entrada em vez do flash real, entregando ao diagnóstico uma
mensagem sem sentido. Enquanto ele mentir, toda falha de flash desta suíte
chega ilegível.

**Tech Stack:** pytest 8.4.1, Playwright (Chromium headless), Flask, Jinja2,
SQLAlchemy 2.x, PostgreSQL. Servidor gunicorn de pé em `localhost:5000` para as
famílias browser.

**Spec:** Não há spec — este plano nasce de um diagnóstico. A evidência que faz
as vezes de spec está na seção "Evidência" abaixo, medida em 02/09, e é dela que
cada task argumenta. O plano fecha dois itens de registro já existentes:
**Task 12 / Step 2** de `2026-09-01-as-decisoes-viram-codigo.md` e **Task 6** de
`2026-08-25-onda-6-os-testes-prometidos.md` — que é a última da Onda 6, e
portanto derruba a **Task 6** de `2026-08-31-fecho-do-que-esta-aberto.md`.

## Global Constraints

- **Gate:** `bash run_tests.sh --gate` (= `pytest tests/ -m "not browser"`).
- **Piso vigente, medido em 01/09** (`gate_decisoes_1901.log`):
  **3193 passed, 8 skipped, 201 deselected, 72 xfailed, 0 failed** (42:24).
  A Task 1 deste plano **sobe** o passed; diga em quanto.
- **O skipped nunca sobe.** Piso: **skipped = 8**. Se subir, pare e descubra por
  quê antes de seguir.
- **TDD sem exceção.** RED conferido e **citado no commit**.
- ⚠️ **Um teste de guarda tem de reprovar também quando o próprio gatilho para
  de funcionar.** A Task 1 é guarda pura e passaria verde contra o código de
  hoje — por isso o RED dela é provado **quebrando o template de propósito** e
  revertendo. Sem esse passo a guarda não prova nada.
- **Nenhum teste prova por `inspect.getsource()`.** O que se afirma é olhado no
  HTML da resposta, no banco ou no `url_map`.
- **Não conserte produção nesta rodada.** 🔬 Nem o `<select>` de cliente (A22 —
  digitar nome livre era o que duplicava Cliente) nem o guard A09 (dedup de NF)
  estão errados. Quem está errado é o teste. Se alguma task deste plano parecer
  pedir mudança em `propostas_consolidated.py` ou
  `views/almoxarifado/movimentos.py`, **pare**: o diagnóstico está errado, não o
  código.
- **A branch de trabalho é `sdd/a-porta-irma`.** Não abra branch por plano.
- **Servidor de pé.** As Tasks 5 e 6 exigem gunicorn em `localhost:5000`
  (`PW_BASE_URL` sobrescreve). Sem ele a família browser não roda — e "não
  rodou" nunca é "passou".

---

## Evidência (medida em 02/09)

### (a) Deriva de seletor — as 2 falhas de proposta

`tests/test_browser_all_modules.py:710`, dentro do helper `_criar_proposta`:

```python
page.fill('input[name="cliente_nome"]', cliente)
```

O campo não existe mais. Contado no diff do commit que o removeu:

```
$ git show 1394d907^:templates/propostas/nova_proposta.html | grep -c 'name="cliente_nome"'
1
$ git show 1394d907:templates/propostas/nova_proposta.html  | grep -c 'name="cliente_nome"'
0
```

`1394d907` (**2026-08-05**, "feat(crm): a cadeia CRM→proposta→obra carrega o
cliente, e o form usa select") o substituiu por, em `nova_proposta.html:84`:

```html
<select class="form-select" name="cliente_id" id="cliente_id"
        data-testid="proposta-cliente-id" required>
```

O `required` importa: sem ele a submissão seguiria e falharia adiante; com ele o
formulário nem submete. O helper foi escrito em `b30923b5` (**2026-07-22**),
duas semanas antes, e nunca foi atualizado.

🔬 **Não é regressão desta rodada, e isso está provado, não suposto:** varredura
de `tests/reports/*.txt` e `*.log` não acha **nenhum** `PASSED` histórico de
`TestIntegracaoPropostaObra::test_criar_proposta_flash_sucesso`. As quatro
ocorrências que existem são todas de 01/09 e todas vermelhas.

🔑 **O padrão da correção já existe na árvore e está testado.**
`tests/test_e2e_jornada_proposta_cronograma_playwright.py:91-120` foi corrigido
em **06/08** — um dia depois da quebra — com um helper `_garantir_cliente(nome)`
e `select_option("[data-testid=proposta-cliente-id]", ...)`. Só o
`test_browser_all_modules.py` ficou para trás. **A Task 2 copia esse padrão; não
inventa outro.**

### (b) Teste não idempotente — as 2 falhas de almoxarifado

`views/almoxarifado/movimentos.py:102` chama a guarda A09, introduzida por
`bbe74f00` (**2026-08-04**):

```python
_ja = entrada_ja_lancada(nota_fiscal, item_id, admin_id)
if _ja:
    flash(f'A nota fiscal "{nota_fiscal}" já deu entrada deste item em ...', 'warning')
    return redirect(url_for('almoxarifado.entrada'))
```

A chave é `(admin_id, nota_fiscal, item_id)`. Os testes gravam NF **fixa** —
`NF-E2E-001` (`:1081` e a asserção em `:1106`) e `NF-E2E-GCP` (`:1140` e a
asserção em `:1149`). Os dois movimentos estão no banco, com o horário exato da
suíte interrompida de 01/09:

```
id    nota_fiscal  item_id  admin_id  data_movimento
9415  NF-E2E-001   3        1         2026-09-01 19:37:37.822748
9416  NF-E2E-GCP   3        1         2026-09-01 19:37:40.454142
```

Isto reconcilia o placar que estava sem explicação: na `--suite` interrompida de
01/09 os 2 FAILED eram os de **proposta** (os de almox ainda passaram, e foi
nessa passagem que gravaram as duas linhas acima); na rerrodada das 21:31 os
mesmos dois de almox já vinham recusados, e o placar virou **4**.

A segunda falha é **consequência** da primeira, não achado próprio: `221 → 221`
em `GestaoCustoPai` porque a entrada foi recusada antes do `db.session.commit()`
e o `EventManager.emit('material_entrada', ...)` nunca chegou a ser chamado. O
handler está registrado e correto.

### (c) O helper de flash que escondeu (b)

`tests/test_browser_all_modules.py:112-120`:

```python
el = (page.query_selector(".alert-success")
      or page.query_selector(".alert-info")
      or page.query_selector(".alert-warning"))
return el.inner_text().strip() if el else ""
```

Três defeitos, e os três atuaram juntos:

1. **`.alert-info` casa painel estático.** `templates/almoxarifado/entrada.html:45`
   é `<div id="infoItem" class="alert alert-info border-0 mb-4" style="display: none;">`.
   Não é flash; é o cartão "Tipo de Controle / Unidade / Estoque Atual".
2. **Não confere visibilidade.** `innerText` de elemento com `display:none` cai
   para `textContent` por especificação — por isso o painel **oculto** devolveu
   texto. O helper não tinha como saber que estava lendo lixo.
3. **Nunca olha `.alert-danger`.** A metade das recusas do sistema é `danger`.
   Um teste que falha por recusa recebe `''` e reporta "flash não encontrado",
   escondendo a mensagem que diria por quê.

🔑 **O flash real tem assinatura própria e os painéis estáticos não a têm.**
`templates/base.html:992` e `templates/base_completo.html:1170` renderizam todo
flash como:

```html
<div class="alert alert-{{ cat }} alert-dismissible fade show" role="alert">
```

Conferido: `alert-dismissible` **não ocorre** em `templates/almoxarifado/entrada.html`
nem em `templates/propostas/nova_proposta.html`. `alert-dismissible` + `role="alert"`
+ visibilidade separa flash de painel.

### O mecanismo, que é o que esta rodada existe para consertar

As duas quebras de (a) viveram 28 dias porque a única prova que as veria mora
numa família que o gate **deseleciona** (`-m "not browser"`, 201 testes). O gate
rodou verde 3193/8/72 em 01/09 com o formulário de proposta inalcançável pelo
teste. **A Task 1 põe essa prova no gate**, em segundos e sem browser.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `tests/test_contrato_formularios_e2e.py` | **Criar** | Task 1 — a guarda de seletor, no gate |
| `tests/test_browser_all_modules.py:146-262` (`_garantir_dados_e2e`) | Modificar | Task 2 — provisiona o Cliente do tenant |
| `tests/test_browser_all_modules.py:691-765` (`_criar_proposta`) | Modificar | Task 2 — usa o `<select>` |
| `tests/test_browser_all_modules.py:1070-1162` (almox) | Modificar | Task 3 — NF única por rodada |
| `tests/test_browser_all_modules.py:112-120` (`_flash_em_pagina`) | Modificar | Task 4 — para de casar painel estático |
| `docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md` | Modificar | Task 7 — Task 12 Step 2 fecha |
| `docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md` | Modificar | Tasks 6 e 7 — Task 6 e o fecho da onda |
| `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md` | Modificar | Task 7 — Task 6 do mestre cai |

**Nenhum arquivo de produção é tocado por este plano.** Se um diff seu contém
`propostas_consolidated.py`, `views/almoxarifado/movimentos.py` ou qualquer
`templates/`, você saiu do plano.

---

### Task 1: A guarda de seletor entra no gate

> Esta é a task que dá valor à rodada. As Tasks 2 e 3 consertam 4 testes; esta
> impede que a próxima deriva de formulário viva 28 dias invisível.
>
> 🔬 **Esta task foi VALIDADA ao escrever o plano (02/09), não só imaginada.**
> O arquivo abaixo foi escrito, rodado e apagado para a Task 1 recriá-lo. Medido:
> **19 passed em 2.11s** (com o teste da Task 4 junto; esta task sozinha dá
> **18**); as duas rotas respondem **200** para um admin de tenant
> novo; os 10 seletores de proposta e os 7 de almoxarifado estão todos presentes;
> `name="cliente_nome"` e `alert-dismissible` estão ausentes dos dois templates.
> Os dois REDs deliberados (Steps 3 e o da Task 4) reprovaram exatamente como
> descrito. Se o seu resultado divergir, é achado — não ajuste o número.

O teste afirma o **contrato entre o formulário e a suíte browser**: os campos
que `test_browser_all_modules.py` e a jornada E2E preenchem existem no HTML
renderizado, e o campo que foi deliberadamente removido continua removido. Roda
sem browser, em segundos, dentro do gate.

**Files:**
- Create: `tests/test_contrato_formularios_e2e.py`
- Test: o próprio arquivo

**Interfaces:**
- Consumes: `tests/helpers_tenant.py` — `um_tenant(prefixo)` (devolve `Tenant`
  com `.admin_id` e `.cliente_id`) e `cliente_de(user_id)` (test client
  autenticado). Já existem; **não crie arreio novo**.
- Produces: nada que outra task consuma. É guarda terminal.

- [ ] **Step 1: Write the guard**

```python
"""O contrato entre os formulários e a suíte browser, conferido no gate.

Por que este arquivo existe: em 05/08 o formulário de nova proposta trocou
`input[name="cliente_nome"]` por `<select name="cliente_id">` (commit
1394d907, correção do A22 — nome digitado livre duplicava Cliente). O helper
`_criar_proposta` de `test_browser_all_modules.py` continuou preenchendo o
campo extinto e passou 28 dias vermelho sem ninguém ver, porque a única prova
que o veria mora na família `browser`, que o gate deseleciona.

Esta guarda põe a mesma prova no gate: sem browser, em segundos. Ela NÃO
testa comportamento de negócio — testa que os seletores que os testes E2E
digitam existem na página que eles abrem.

⚠️ Se um seletor daqui mudar de propósito, o conserto é atualizar ESTE arquivo
E os testes E2E na mesma rodada. Atualizar só o template é o defeito que este
arquivo existe para tornar barulhento.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


ROTAS = ('/propostas/nova', '/almoxarifado/entrada')


@pytest.fixture(scope='module')
def html_por_rota():
    """Um tenant, um GET por rota — reusado por todos os casos parametrizados.

    Escopo de MÓDULO de propósito: `um_tenant` escreve no banco, e criar um
    tenant por caso (são 18) encheria o banco de dev de lixo sem provar nada a
    mais. O contrato é sobre o TEMPLATE, que não varia por tenant.

    `com_fatos=False` porque os fatos operacionais (ponto, alimentação, custo)
    que o arreio semeia por padrão não são lidos por nenhuma destas páginas.
    """
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-contrato-formularios'
    # `um_tenant` escreve pela sessão do SQLAlchemy: precisa de app_context
    # explícito (o conftest só registra blueprints, não empurra contexto).
    with app.app_context():
        admin_id = um_tenant('contrato', com_fatos=False).admin_id
    c = cliente_de(admin_id)
    paginas = {}
    for rota in ROTAS:
        resp = c.get(rota)
        assert resp.status_code == 200, (
            f'{rota} respondeu {resp.status_code}, não 200 — a guarda de '
            f'seletor não chegou a olhar o formulário. Conserte a rota antes '
            f'do contrato.'
        )
        paginas[rota] = resp.get_data(as_text=True)
    return paginas


# Os seletores que os testes E2E digitam, por página. A fonte de cada um é o
# arquivo:linha que o usa — citado para que quem quebrar saiba o que consertar.
CONTRATO_PROPOSTA_NOVA = [
    # test_browser_all_modules.py::_criar_proposta + jornada:305-320
    'name="cliente_id"',
    'data-testid="proposta-cliente-id"',
    'name="numero_proposta"',
    'name="assunto"',
    'name="objeto"',
    'data-testid="proposta-salvar"',
    'id="formNovaProposta"',
    # as três classes de item que _criar_proposta preenche
    'servico-descricao',
    'servico-quantidade',
    'servico-valor-unitario',
]

# O campo que o A22 removeu de propósito. Se ele VOLTAR, o dedup de Cliente
# volta a ser furado — e esta linha é o alarme.
CONTRATO_PROPOSTA_EXTINTO = ['name="cliente_nome"']

CONTRATO_ALMOX_ENTRADA = [
    # test_browser_all_modules.py::_preencher_entrada_almoxarifado:1034-1066
    'id="formEntrada"',
    'id="item_id"',
    'id="tipo_controle"',
    'id="quantidade"',
    'id="valor_unitario"',
    'id="nota_fiscal"',
    'id="fornecedor_id"',
]


@pytest.mark.parametrize('marca', CONTRATO_PROPOSTA_NOVA)
def test_proposta_nova_tem_o_seletor(marca, html_por_rota):
    html = html_por_rota['/propostas/nova']
    assert marca in html, (
        f'/propostas/nova não contém {marca!r}. A suíte browser '
        f'(test_browser_all_modules.py::_criar_proposta) e a jornada E2E '
        f'digitam esse seletor — se o formulário mudou de propósito, atualize '
        f'os dois testes E ESTA lista na mesma rodada.'
    )


@pytest.mark.parametrize('marca', CONTRATO_PROPOSTA_EXTINTO)
def test_proposta_nova_nao_ressuscita_o_campo_extinto(marca, html_por_rota):
    html = html_por_rota['/propostas/nova']
    assert marca not in html, (
        f'/propostas/nova voltou a conter {marca!r}. O A22 (commit 1394d907) '
        f'removeu esse campo porque nome digitado livre criava Cliente '
        f'DUPLICADO com a obra amarrada nele. Se voltou, o dedup furou.'
    )


@pytest.mark.parametrize('marca', CONTRATO_ALMOX_ENTRADA)
def test_almoxarifado_entrada_tem_o_seletor(marca, html_por_rota):
    html = html_por_rota['/almoxarifado/entrada']
    assert marca in html, (
        f'/almoxarifado/entrada não contém {marca!r}. '
        f'test_browser_all_modules.py::_preencher_entrada_almoxarifado digita '
        f'esse seletor — atualize o teste E ESTA lista na mesma rodada.'
    )
```

- [ ] **Step 2: Rodar, e dizer a verdade sobre a cor**

Run: `python -m pytest tests/test_contrato_formularios_e2e.py -v`
Expected: **18 passed** em ~2s — 10 seletores de proposta + 1 campo extinto + 7
de almox. (A Task 4 acrescenta o 19º a este mesmo arquivo; aqui ele ainda não
existe. Se você vir 19, alguém já rodou a Task 4 — confira antes de seguir.) E isso está certo: o template de hoje **cumpre** o
contrato; quem não cumpria era o teste browser, e ele é consertado nas Tasks 2
e 3. Um teste que passa de primeira não prova nada sozinho — é o Step 3 que o
torna prova.

- [ ] **Step 3: Provar que a guarda não é vazia (o RED deliberado)**

Quebre o template de propósito, rode, confirme o vermelho, reverta:

```bash
sed -i 's/name="cliente_id"/name="cliente_nome"/' templates/propostas/nova_proposta.html
python -m pytest tests/test_contrato_formularios_e2e.py -v
```

Expected: **2 failed, 16 passed** — `test_proposta_nova_tem_o_seletor[name="cliente_id"]`
e `test_proposta_nova_nao_ressuscita_o_campo_extinto[name="cliente_nome"]`.
O segundo é o que importa: ele prova que a guarda vê o campo extinto **voltar**,
que é o defeito real do A22, e não só um seletor sumir.

```bash
git checkout templates/propostas/nova_proposta.html
python -m pytest tests/test_contrato_formularios_e2e.py -v
```

Expected: PASS de novo, e `git status` limpo em `templates/`.

⚠️ **Não commite com o template quebrado.** Confira `git diff --stat` antes do
Step 4: só `tests/test_contrato_formularios_e2e.py` pode aparecer.

- [x] **Step 4: Commit**

```bash
git add tests/test_contrato_formularios_e2e.py
git commit -m "test(browser): o contrato de seletor dos formularios E2E entra no gate

A deriva de 05/08 (1394d907, cliente_nome -> select cliente_id) viveu 28 dias
invisivel porque a unica prova que a veria mora na familia browser, que o gate
deseleciona. Esta guarda poe a mesma prova no gate, sem browser.

RED deliberado conferido: com 'sed s/name=\"cliente_id\"/name=\"cliente_nome\"/'
no template, 2 FAILED — o seletor vivo some E o campo extinto do A22 ressuscita.
Revertido; verde de novo. Guarda que nao reprova quando o gatilho quebra nao e
guarda.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RmFroFYjh8oazrQQXPXivX"
```

---

### Task 2: O helper de proposta usa o `<select>`

**Files:**
- Modify: `tests/test_browser_all_modules.py:146-262` (`_garantir_dados_e2e`)
- Modify: `tests/test_browser_all_modules.py:691-765` (`_criar_proposta`)

**Interfaces:**
- Consumes: nada da Task 1 (a guarda é terminal). O provisionador
  `_garantir_dados_e2e(admin_id)` já é chamado pela fixture `browser_session`
  em `:294`, dentro de app_context, e já é idempotente — a convenção de nome
  dele é o prefixo `__E2E `.
- Produces: `_criar_proposta(page) -> int` mantém a assinatura. Os dois testes
  da classe seguem chamando igual.

- [ ] **Step 1: Rodar os 2 testes para ver o RED que já existe**

Run:
```bash
python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoPropostaObra" -v
```
Expected: **2 FAILED** (`test_criar_proposta_flash_sucesso`,
`test_aprovar_proposta_gera_obra`) com
`playwright._impl._errors.TimeoutError: Page.fill: Timeout 30000ms exceeded.` e
`waiting for locator("input[name=\"cliente_nome\"]")`.

🔬 Este RED é real e reproduzível — medido em 01/09 21:31 e de novo agora. Não é
preciso fabricá-lo. **Cite este comando e esta saída no commit.**

- [ ] **Step 2: Provisionar o Cliente do tenant**

Em `_garantir_dados_e2e`, logo **depois** do bloco `# 1) Fornecedor` e antes de
`# 2) AlmoxarifadoItem`, acrescente o bloco 1b. E acrescente `Cliente` ao import
de `models` no topo da função (`:155-158`), que hoje é:

```python
    from models import (
        Fornecedor, AlmoxarifadoCategoria, AlmoxarifadoItem, Funcionario,
        PlanoContas, ParametrosLegais,
    )
```

passa a ser:

```python
    from models import (
        Cliente, Fornecedor, AlmoxarifadoCategoria, AlmoxarifadoItem,
        Funcionario, PlanoContas, ParametrosLegais,
    )
```

O bloco novo:

```python
    # 1b) Cliente do tenant — A22/B3.3: o formulário de nova proposta deixou de
    #     aceitar nome digitado (commit 1394d907, 05/08) e passou a ser um
    #     <select> de Cliente JÁ CADASTRADO, que é o ponto do A22: digitar nome
    #     livre duplicava Cliente a cada proposta, com a obra amarrada no
    #     duplicado. `_criar_proposta` precisa de um cadastro para selecionar.
    #     Mesma solução da jornada E2E (test_e2e_jornada_...:91).
    if Cliente.query.filter_by(
            admin_id=admin_id, nome="__E2E Cliente").first() is None:
        db.session.add(Cliente(
            admin_id=admin_id, nome="__E2E Cliente",
            email="cliente.e2e@example.com",
        ))
```

- [ ] **Step 3: Trocar o `fill` pelo `select_option` em `_criar_proposta`**

Em `_criar_proposta`, o bloco atual `:698-711` é:

```python
        ts = datetime.datetime.now().strftime("%H%M%S%f")
        cliente = f"Cliente E2E {ts}"
        assunto = f"Proposta E2E {ts}"

        # Navegar ao formulário de nova proposta
        page.goto(f"{BASE_URL}/propostas/nova", timeout=TIMEOUT_MS,
                  wait_until="domcontentloaded")
        assert "/login" not in page.url, "Sessão expirou ao acessar /propostas/nova"

        # Preencher campos principais (todos presentes no HTML estático).
        # NOTA: numero_proposta também tem required — deve ser preenchido.
        page.fill('input[name="numero_proposta"]', f"E2E-{ts}")
        page.fill('input[name="cliente_nome"]', cliente)
        page.fill('input[name="assunto"]', assunto)
```

Substitua por:

```python
        ts = datetime.datetime.now().strftime("%H%M%S%f")
        assunto = f"Proposta E2E {ts}"

        # A22/B3.3 — o cliente vem do CADASTRO, não de nome digitado. O
        # <select name="cliente_id"> é `required` (nova_proposta.html:84-85):
        # sem ele o formulário nem submete. O cadastro é provisionado de forma
        # idempotente por _garantir_dados_e2e (bloco 1b), chamado pela fixture.
        from app import app as _app_cliente
        from models import Cliente as _Cliente
        admin_id = _get_admin_id()   # já abre e fecha o próprio app_context
        with _app_cliente.app_context():
            _c = _Cliente.query.filter_by(
                admin_id=admin_id, nome="__E2E Cliente").first()
            assert _c is not None, \
                "__E2E Cliente não provisionado — _garantir_dados_e2e não rodou"
            cliente_id = _c.id

        # Navegar ao formulário de nova proposta
        page.goto(f"{BASE_URL}/propostas/nova", timeout=TIMEOUT_MS,
                  wait_until="domcontentloaded")
        assert "/login" not in page.url, "Sessão expirou ao acessar /propostas/nova"

        # Preencher campos principais (todos presentes no HTML estático).
        # NOTA: numero_proposta também tem required — deve ser preenchido.
        page.fill('input[name="numero_proposta"]', f"E2E-{ts}")
        page.select_option('[data-testid=proposta-cliente-id]', value=str(cliente_id))
        page.fill('input[name="assunto"]', assunto)
```

- [ ] **Step 4: Trocar o seletor de submit pelo `data-testid`**

O bloco `:720-729` clica em `#formNovaProposta button[type="submit"]`. O botão
existe (`nova_proposta.html:440`, dentro do form que abre em `:33` e fecha em
`:442`), mas o `data-testid="proposta-salvar"` é o seletor que a jornada E2E usa
e que está provado ponta a ponta. Substitua as duas ocorrências:

```python
        page.evaluate(
            "document.querySelector('[data-testid=\"proposta-salvar\"]')"
            ".scrollIntoView({block:'center', behavior:'instant'})"
        )
        page.wait_for_timeout(400)
        page.locator('[data-testid=proposta-salvar]').click(timeout=TIMEOUT_MS)
```

- [ ] **Step 5: Rodar os 2 testes**

Run:
```bash
python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoPropostaObra" -v
```
Expected: **3 passed** (os 2 consertados + `test_proposta_aprovada_aparece_na_lista`).

⚠️ Se `test_aprovar_proposta_gera_obra` falhar **depois** do submit (e não no
`fill`), o achado é NOVO e não é este plano: o fluxo de aprovação nunca foi
exercitado por teste verde. Registre em
`docs/auditoria/achados-code-review-2026-08-25.md` com `arquivo:linha` e
**pare** — não conserte no meio, é exatamente o que a Onda 6 proíbe.

- [ ] **Step 6: Commit**

```bash
git add tests/test_browser_all_modules.py
git commit -m "test(browser): o helper de proposta usa o select de Cliente, como a jornada ja usa

RED conferido: pytest 'tests/test_browser_all_modules.py::TestIntegracaoPropostaObra'
-> 2 FAILED com Page.fill timeout 30s em input[name=cliente_nome]. O campo saiu
do template em 1394d907 (05/08, A22) e o helper nunca soube — nenhum PASSED
historico dele existe em tests/reports/.

A jornada E2E ja tinha sido corrigida em 06/08 (_garantir_cliente + select por
data-testid); so este arquivo ficou para tras. Copia o mesmo padrao. Producao
nao muda: o select E o conserto do A22.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RmFroFYjh8oazrQQXPXivX"
```

---

### Task 3: A nota fiscal do teste de almoxarifado nasce única

**Files:**
- Modify: `tests/test_browser_all_modules.py:1070-1162` (os dois testes de entrada)

**Interfaces:**
- Consumes: `_preencher_entrada_almoxarifado(page, item_id, forn_id, quantidade,
  valor_unitario, nota_fiscal, observacoes="") -> str` — assinatura **não muda**;
  só o valor que os chamadores passam em `nota_fiscal`.
- Produces: nada.

- [ ] **Step 1: Rodar os 2 testes para ver o RED que já existe**

Run:
```bash
python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoAlmoxGestaoCusto" -v
```
Expected: **2 FAILED, 1 passed**. `test_entrada_material_flash_sucesso` com
`AssertionError: Flash de sucesso não encontrado ... Flash capturado: 'Tipo de
Controle ...'`, e `test_entrada_material_gera_gestao_custo_material` com
`AssertionError: ... Antes: 221, Depois: 221`.

🔬 RED real e reproduzível. **Cite no commit.**

- [ ] **Step 2: NF única em `test_entrada_material_flash_sucesso`**

O teste usa `NF-E2E-001` em dois lugares — no submit (`:1081`) e na consulta ao
banco (`:1106`). Os dois têm de usar a **mesma** variável. Logo depois do
`pytest.skip` de `item_id` (`:1073-1074`), acrescente:

```python
        # A09 — a NF é chave de dedup (admin_id, nota_fiscal, item_id) desde
        # bbe74f00 (04/08), e o guard é CORRETO: F5 numa tela de entrada é
        # rotina e duplicava estoque em silêncio. Com NF fixa este teste passa
        # UMA vez contra um banco persistente e é recusado para sempre depois —
        # foi o que aconteceu (movimentos 9415/9416, gravados em 01/09 19:37).
        # A NF nasce única por rodada, mesmo padrão do ts de _criar_proposta.
        nf = f"NF-E2E-001-{datetime.datetime.now():%H%M%S%f}"
```

Troque `nota_fiscal="NF-E2E-001",` (no `_preencher_entrada_almoxarifado`) por
`nota_fiscal=nf,`, e no bloco de verificação troque:

```python
                nota_fiscal="NF-E2E-001",
            ).first()

        assert movimento is not None, \
            "AlmoxarifadoMovimento com nota_fiscal='NF-E2E-001' não encontrado no banco"
```

por:

```python
                nota_fiscal=nf,
            ).first()

        assert movimento is not None, \
            f"AlmoxarifadoMovimento com nota_fiscal={nf!r} não encontrado no banco"
```

- [ ] **Step 3: NF única em `test_entrada_material_gera_gestao_custo_material`**

Mesmo tratamento. Depois do `pytest.skip` de `forn_id` (`:1122-1123`),
acrescente:

```python
        # A09 — ver a nota em test_entrada_material_flash_sucesso.
        nf = f"NF-E2E-GCP-{datetime.datetime.now():%H%M%S%f}"
```

Troque `nota_fiscal="NF-E2E-GCP",` por `nota_fiscal=nf,`; e no bloco de
verificação troque `nota_fiscal="NF-E2E-GCP",` por `nota_fiscal=nf,` e a
mensagem `"Movimento NF-E2E-GCP não encontrado no banco"` por
`f"Movimento {nf!r} não encontrado no banco"`.

- [ ] **Step 4: Rodar duas vezes seguidas — a idempotência é o ponto**

Run:
```bash
python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoAlmoxGestaoCusto" -v
python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoAlmoxGestaoCusto" -v
```
Expected: **3 passed** nas **duas** rodadas.

⚠️ Rodar uma vez só não prova nada aqui — o defeito é exatamente "passa na
primeira". A segunda rodada é a prova, e o commit tem de citar as duas.

- [ ] **Step 5: Commit**

```bash
git add tests/test_browser_all_modules.py
git commit -m "test(almox): a NF do teste de entrada nasce unica — o teste para de queimar o proprio fixture

RED conferido: pytest 'tests/test_browser_all_modules.py::TestIntegracaoAlmoxGestaoCusto'
-> 2 FAILED (flash ausente; GestaoCustoPai 221 -> 221). Causa: NF fixa
(NF-E2E-001 / NF-E2E-GCP) contra banco persistente + guard A09 de bbe74f00. Os
dois movimentos estao no banco desde 01/09 19:37 (ids 9415 e 9416) — o teste
passou UMA vez e se recusou desde entao.

O guard A09 esta CERTO e nao muda: a chave (admin_id, nota_fiscal, item_id)
existe porque F5 na tela de entrada duplicava estoque em silencio. Quem estava
errado era o teste.

Verde conferido em DUAS rodadas seguidas — a segunda e a prova, porque o defeito
era passar na primeira.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RmFroFYjh8oazrQQXPXivX"
```

---

### Task 4: `_flash_em_pagina` para de devolver painel estático

> Sem esta task as Tasks 2 e 3 ficam verdes e o helper continua mentindo na
> próxima falha. Foi ele que tornou o diagnóstico de (b) ilegível.

**Files:**
- Modify: `tests/test_browser_all_modules.py:112-120`

**Interfaces:**
- Consumes: nada.
- Produces: `_flash_em_pagina(page) -> str` — assinatura **não muda**. Passa a
  devolver o texto de **todos** os flashes visíveis, unidos por `" | "`, e `""`
  quando não há nenhum. Os chamadores (`:774`, `:1085`, e os de RDO/folha) já
  fazem `in flash_text.lower()`, então mais texto só ajuda.

- [ ] **Step 1: Write the failing test**

Acrescente a `tests/test_contrato_formularios_e2e.py` (o arquivo da Task 1 — o
assunto é o mesmo: o que a suíte browser lê da página):

```python
# ---------------------------------------------------------------------------
# O helper de flash da suíte browser não pode confundir painel com mensagem
# ---------------------------------------------------------------------------
# `_flash_em_pagina` casava `.alert-info` genérico e devolvia o cartão ESTÁTICO
# de /almoxarifado/entrada ("Tipo de Controle / Unidade / Estoque Atual") em vez
# do flash. Pior: o cartão nasce `display:none`, e innerText de elemento não
# renderizado cai para textContent por especificação — o helper leu texto de um
# elemento invisível e o reportou como mensagem do sistema. Foi isso que deixou
# a falha do A09 sem diagnóstico por uma rodada inteira.
#
# O flash real tem assinatura própria: base.html:992 e base_completo.html:1170
# renderizam TODO flash como `alert alert-<cat> alert-dismissible fade show`
# com `role="alert"`. Conferido: `alert-dismissible` não ocorre em
# templates/almoxarifado/entrada.html nem em templates/propostas/nova_proposta.html.

def test_painel_estatico_da_entrada_nao_se_parece_com_flash(html_por_rota):
    """O cartão informativo de /almoxarifado/entrada não pode casar o seletor
    de flash — se casar, o helper da suíte browser volta a mentir."""
    html = html_por_rota['/almoxarifado/entrada']
    assert 'alert-info' in html, (
        'o cartão estático sumiu de /almoxarifado/entrada — se foi de '
        'propósito, esta guarda perdeu o objeto e deve ser reescrita, não '
        'apagada: o ponto é que painel e flash não se confundam'
    )
    assert 'alert-dismissible' not in html, (
        '/almoxarifado/entrada passou a conter alert-dismissible. O seletor de '
        'flash de test_browser_all_modules.py::_flash_em_pagina se apoia em '
        'alert-dismissible para separar flash de painel — se um painel estático '
        'ganhar essa classe, o helper volta a devolver painel como mensagem.'
    )
```

- [ ] **Step 2: Run test to verify it fails — e por quê**

Run: `python -m pytest tests/test_contrato_formularios_e2e.py -k painel_estatico -v`
Expected: **PASS**.

🔬 Diga a verdade: este passa de primeira, porque o template de hoje já satisfaz
a condição. O RED dele é o mesmo padrão da Task 1 — prove que não é vazio:

```bash
sed -i 's/class="alert alert-info border-0 mb-4"/class="alert alert-info alert-dismissible border-0 mb-4"/' templates/almoxarifado/entrada.html
python -m pytest tests/test_contrato_formularios_e2e.py -k painel_estatico -v
```
Expected: **1 failed, 18 deselected** com a mensagem "passou a conter
alert-dismissible".

```bash
git checkout templates/almoxarifado/entrada.html
```

⚠️ Confirme `git status` limpo em `templates/` antes de seguir.

- [ ] **Step 3: Corrigir o helper**

Substitua `tests/test_browser_all_modules.py:112-120` inteiro:

```python
def _flash_em_pagina(page: Page) -> str:
    """Texto de TODOS os flashes visíveis da página, unidos por ' | '.

    ⚠️ Três defeitos da versão anterior, e os três atuaram juntos na rodada de
    01/09, deixando a recusa do A09 sem diagnóstico:

    1. casava `.alert-info` genérico — e /almoxarifado/entrada tem um cartão
       ESTÁTICO com essa classe (`entrada.html:45`), que não é flash;
    2. não conferia visibilidade — `innerText` de elemento `display:none` cai
       para `textContent` por especificação, então o cartão OCULTO devolveu
       texto como se fosse mensagem do sistema;
    3. nunca olhava `.alert-danger` — metade das recusas do sistema é `danger`,
       e um teste que falhasse por recusa recebia '' e reportava "flash não
       encontrado", escondendo a mensagem que diria por quê.

    O flash real tem assinatura própria: `base.html:992` e
    `base_completo.html:1170` renderizam todo flash como
    `alert alert-<cat> alert-dismissible fade show` com `role="alert"`.
    Nenhum painel estático das páginas que esta suíte visita usa
    `alert-dismissible` — guardado por
    `tests/test_contrato_formularios_e2e.py::test_painel_estatico_da_entrada_nao_se_parece_com_flash`.

    Devolve TODOS (não o primeiro): quando a rota flasha aviso E erro, ler só um
    esconde o outro.
    """
    try:
        els = page.query_selector_all('.alert-dismissible[role="alert"]')
        textos = [
            el.inner_text().strip()
            for el in els
            if el.is_visible() and el.inner_text().strip()
        ]
        return " | ".join(textos)
    except Exception:
        return ""
```

- [ ] **Step 4: Provar que o helper melhorou — o flash de recusa fica legível**

Este é o ponto da task: antes, uma recusa do A09 chegava ao relatório como
`'Tipo de Controle ...'`. Agora tem de chegar como a mensagem real. Force a
recusa reusando uma NF que já existe no banco:

⚠️ **Sem `git checkout` e sem `git stash` aqui.** O arquivo já carrega as
edições do Step 3, que ainda não estão commitadas; qualquer comando git que
restaure o arquivo as destrói. O experimento se desfaz por substituição textual
inversa — a mesma troca, ao contrário.

```bash
# ida: NF volta a ser fixa, só para encenar a recusa do A09
python - <<'PY'
import pathlib
p = pathlib.Path('tests/test_browser_all_modules.py')
s = p.read_text()
alvo = 'nf = f"NF-E2E-001-{datetime.datetime.now():%H%M%S%f}"'
assert alvo in s, 'Step 3 da Task 3 não está aplicado — pare'
p.write_text(s.replace(alvo, 'nf = "NF-E2E-001"  # TEMPORARIO'))
PY
python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoAlmoxGestaoCusto::test_entrada_material_flash_sucesso" -v
```

Expected: **1 FAILED**, e a mensagem do assert agora contém
`Flash capturado: 'A nota fiscal "NF-E2E-001" já deu entrada deste item em 01/09/2026...'`
— a mensagem **real** do guard A09, não o cartão estático. É essa legibilidade
que a task compra.

```bash
# volta: desfaz SÓ o hack, preservando tudo do Step 3
python - <<'PY'
import pathlib
p = pathlib.Path('tests/test_browser_all_modules.py')
s = p.read_text()
alvo = 'nf = "NF-E2E-001"  # TEMPORARIO'
assert alvo in s, 'o hack não está aplicado — nada a desfazer'
p.write_text(s.replace(alvo, 'nf = f"NF-E2E-001-{datetime.datetime.now():%H%M%S%f}"'))
PY
grep -n 'alert-dismissible\[role' tests/test_browser_all_modules.py
```

Expected do `grep`: **1 linha** — a prova de que o helper novo do Step 3
continua no arquivo. Se não aparecer, o Step 3 se perdeu: reaplique antes de
seguir.

- [ ] **Step 5: Rodar a família de integração inteira**

Run:
```bash
python -m pytest tests/test_browser_all_modules.py -k "Integracao" -v
```
Expected: **17 passed**.

- [ ] **Step 6: Commit**

```bash
git add tests/test_browser_all_modules.py tests/test_contrato_formularios_e2e.py
git commit -m "test(browser): o helper de flash para de devolver painel estatico como mensagem

_flash_em_pagina casava .alert-info generico e devolvia o cartao estatico de
/almoxarifado/entrada — que nasce display:none, e innerText de elemento nao
renderizado cai para textContent por especificacao. Foi por isso que a recusa do
A09 chegou ao relatorio como 'Tipo de Controle / Unidade / Estoque Atual' e o
diagnostico levou uma rodada inteira.

Passa a casar a assinatura do flash real (alert-dismissible + role=alert +
visivel, base.html:992), a devolver TODOS os flashes e a incluir danger.

RED deliberado da guarda conferido: com alert-dismissible injetado no cartao
estatico, 1 FAILED. Revertido. E encenando a recusa do A09 com NF fixa, a
mensagem do assert agora traz o texto real do guard.

17 passed em -k Integracao.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RmFroFYjh8oazrQQXPXivX"
```

---

### Task 5: A suíte browser inteira, destacada do terminal

> 🔬 Três gates morreram com a sessão em 01/09, e a `--suite` de 19:30 morreu a
> ~18%. Rode destacado ou vai morrer de novo.

**Files:** nenhum. Esta task mede.

- [ ] **Step 1: Rodar a suíte**

```bash
setsid nohup bash run_tests.sh --suite > tests/reports/suite_browser_$(date +%H%M).log 2>&1 &
```

(~50-60 min. `tests/reports/` está fora do git — o placar vive na mensagem de
commit e na nota do plano, nunca só no log.)

⚠️ Confirme que o gunicorn está de pé em `localhost:5000` **antes**. Sem
servidor, os 201 browser dão ERROR em bloco e o log parece catástrofe.

- [ ] **Step 2: Ler o placar e comparar**

Expected: **0 failed**; `skipped = 8` (o piso — 6 antigos + os 2 do oráculo
deepface); `xfailed = 72`; passed ≥ 3193 + os 201 de browser + os novos da
Task 1.

Se aparecer falha **fora** das 4 desta rodada: cada uma é achado, vai para
`docs/auditoria/achados-code-review-2026-08-25.md` com `arquivo:linha`, e **não
se conserta no meio**. Sem placar histórico da família browser, uma falha nova
não é presumida regressão — diga o que se sabe e o que não se sabe.

Se `skipped` subir de 8: **pare** e descubra por quê. Skip subindo é cobertura
saindo sem aviso.

- [ ] **Step 3: Commit do registro**

Só a nota; a suíte não muda código. Se nada mudou na árvore, este registro entra
junto do commit da Task 7.

---

### Task 6: A jornada E2E, que nunca rodou (Onda 6, Task 6)

> Esta é literalmente a Task 6 de `2026-08-25-onda-6-os-testes-prometidos.md`,
> aberta desde a Fase 0.5. Ela entra aqui porque a Task 5 acabou de deixar o
> caminho limpo, e porque é a **última** da Onda 6.

**Files:**
- Modify: `docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md`

- [ ] **Step 1: Rodar**

```bash
setsid nohup bash run_tests.sh --jornada > tests/reports/jornada_$(date +%H%M).log 2>&1 &
```

Alvo: `tests/test_e2e_jornada_proposta_cronograma_playwright.py` (é o que
`run_tests.sh:52` seleciona).

🔬 A jornada **já usa o padrão certo** de cliente (`_garantir_cliente` +
`select_option` por `data-testid`, corrigido em 06/08) — foi ela que deu à
Task 2 deste plano o padrão a copiar. Então ela **não** deve falhar pelo motivo
que derrubou o `test_browser_all_modules.py`. Se falhar por outro, é achado
novo e é a primeira notícia que se tem dela.

- [ ] **Step 2: Reportar honestamente**

Se falhar: **cada falha é achado**, vai para
`docs/auditoria/achados-code-review-2026-08-25.md` com `arquivo:linha`. **Não
conserte no meio** — a jornada é E2E e um conserto às pressas pode mascarar
defeito de outra onda. É a regra escrita na própria Onda 6.

Se passar: registre a contagem — **é a primeira vez que ela roda**.

- [ ] **Step 3: Marcar a Onda 6 e commitar**

Em `2026-08-25-onda-6-os-testes-prometidos.md`, marque `[x]` os três Steps da
Task 6 com o resultado, marque `[x]` o Step 3 da Task 1 (o commit dela já
aconteceu: `d5bfef01`), e preencha o "Fecho da onda" com as contagens reais.

```bash
git add docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md
git commit -m "docs(onda-6): a jornada E2E rodou pela primeira vez — a onda fecha

Task 6 da Onda 6, aberta desde a Fase 0.5. <placar real da jornada>.

Com ela a Onda 6 fecha inteira (Tasks 1-6), e com a Onda 6 cai a Task 6 de
fecho-do-que-esta-aberto.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RmFroFYjh8oazrQQXPXivX"
```

⚠️ Substitua `<placar real da jornada>` pela contagem medida. Placar inventado
em mensagem de commit é pior que placar ausente.

---

### Task 7: O gate consolida e os três registros fecham

**Files:**
- Modify: `docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md`
- Modify: `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md`

- [x] **Step 1: Gate único, destacado** — 02/09, `gate_browser_2154.log`: **3247 passed, 8 skipped, 201 deselected, 72 xfailed, 0 failed** (47:43). 🔬 O previsto era 3212 e **o número divergiu — eis o porquê, sem arredondar**: o Step só contava os 19 da Task 1, mas entraram no gate também os 15 de `test_suite_resumavel.py` (`1573f348`) e os 20 de `test_contrato_isolamento_playwright.py` (`a80f1ddc`), escritos depois deste plano. 19+15+20 = 54, e 3193+54 = 3247.

```bash
setsid nohup bash run_tests.sh --gate > tests/reports/gate_browser_$(date +%H%M).log 2>&1 &
```

Expected: **0 failed**, `skipped = 8`, `xfailed = 72`, passed = 3193 + os testes
da Task 1 (parametrizados: 10 + 1 + 7 + 1 = **19**), ou seja **3212**. Se o
número divergir, diga qual é e por quê — não arredonde.

- [x] **Step 2: Fechar a Task 12 do plano de 01/09**

Em `2026-09-01-as-decisoes-viram-codigo.md`, marque `- [x] **Step 2: Rodar a
suíte com browser**` e substitua o bloco `> **Estado em 01/09 ~19:45...**` pelo
desfecho: as 4 falhas eram teste desatualizado, não regressão — `1394d907`
(05/08, seletor) e `bbe74f00` (04/08, NF fixa vs. guard A09) — consertadas em
`2026-09-02-a-suite-browser-volta-a-valer.md`, com o placar da suíte. Marque
também o Step 6.

- [x] **Step 3: Derrubar a Task 6 do plano mestre** — a Onda 6 foi carimbada no próprio plano dela (`2026-08-25-onda-6-*.md`), que estava aberto: cabeçalho ✅ 6/6, os três Steps da Task 6 com o placar real da jornada, e o "Fecho da onda" resolvido item a item.

Em `2026-08-31-fecho-do-que-esta-aberto.md`, na tabela de estado do cabeçalho,
troque a linha da Task 6 por `✅` com os commits desta rodada, e atualize o
contador de "5 de 10 tasks fechadas" para **6 de 10**. Atualize o piso do gate
na seção Global Constraints para o número medido no Step 1.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md \
        docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md
git commit -m "docs: a suite browser volta a valer — as 4 falhas eram teste desatualizado, nao regressao

Fecha a Task 12/Step 2 de as-decisoes-viram-codigo e a Task 6 de
fecho-do-que-esta-aberto (via Onda 6). Gate <placar>; suite <placar>.

Causa raiz das 4, medida e nao suposta: 1394d907 (05/08) trocou o input de
cliente por select e o helper do browser nunca soube — nenhum PASSED historico
existe em tests/reports/; bbe74f00 (04/08) poe dedup de NF e os testes gravavam
NF fixa contra banco persistente. Nenhum codigo de producao mudou.

A guarda de seletor entrou no GATE (test_contrato_formularios_e2e.py): a deriva
so viveu 28 dias porque a prova morava numa familia que o gate deseleciona.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RmFroFYjh8oazrQQXPXivX"
```

---

## O que este plano NÃO faz, e para onde vai

A regra da casa: adiar sem registrar é como as issues chegaram a 31/08.

- **Os movimentos 9415 e 9416 (`NF-E2E-001`, `NF-E2E-GCP`) ficam no banco.**
  Decisão consciente. Com a NF única da Task 3 eles deixam de atrapalhar
  qualquer rodada futura, e apagar linha de um banco de dev compartilhado é
  efeito colateral que este plano não precisa. Eles são, aliás, a evidência
  física do diagnóstico. Se algum dia incomodarem:
  `DELETE FROM almoxarifado_movimento WHERE id IN (9415, 9416);`
- **Onda 4** (o relatório passa a funcionar — Tasks 1, 2, 3, 6, 7; as 4 e 5 já
  foram absorvidas e feitas) → as tasks **já estão escritas** em
  `2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md`. Conferido em 02/09:
  `views/almoxarifado/relatorios.py` e `services/evm.py` intocados desde 22/07.
  É a **Task 7** do plano mestre. Não duplicar aqui.
- **Resgate da Espinha Financeira** (9 de 10 tasks) → plano próprio; VIGA-I
  decidida (opção B) mas **`RATIFICAR` pendente**. Task 8 do mestre.
- **Fase 8** → segue travada pela **FASE8-T1** (medir o plano de contas em
  produção), que é trabalho humano e não tem acesso. Não desça para cá.
- **Família 404 / 70 xfail** → tasks já escritas em
  `2026-08-06-rodada-b6-varredura.md` §B6.4–B6.8.
- **Onda das automações** (A01, A08, A17, A20, A21, A23 abertas; A11, A13, A15,
  A16, A22 parciais) → plano a escrever, `2026-09-XX-onda-das-automacoes.md`.
- **As 8 issues de arquitetura** → Task 9 do mestre;
  `2026-08-31-issues-de-arquitetura.md` ainda não existe.
- **Merge de `sdd/a-porta-irma`** (72 commits à frente do `main`) → Task 10 do
  mestre, e ela é a última de propósito.
