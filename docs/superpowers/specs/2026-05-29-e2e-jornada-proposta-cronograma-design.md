# Spec — Teste E2E Playwright: Catálogo → Proposta → Link do Cliente → Cronograma

**Data:** 2026-05-29
**Autor:** Cássio Viller (via brainstorming)
**Status:** Aprovado para implementação

## 1. Objetivo

Criar **um** teste E2E novo, em **Playwright (browser real)**, que percorre de ponta a ponta a
jornada comercial completa do SIGE, exercitando as telas reais:

1. Cadastro de **insumo** no catálogo
2. Cadastro de **serviço** + **composição** (insumo × coeficiente)
3. **Vínculo** de um cronograma-template ao serviço
4. Criação de um **template de proposta**
5. Criação de uma **proposta** a partir do template + serviço(s)
6. **Pré-configuração do cronograma** da proposta (passo obrigatório — ver §6)
7. **Envio** da proposta e captura do **link público do cliente**
8. Abertura do **link do cliente** (anônimo) com **asserções rigorosas** de layout/uso do template
9. **Aprovação** da proposta pelo cliente, pelo próprio link
10. Verificação, **via UI**, de que o **cronograma automático** foi materializado e **vinculado ao serviço**

O teste substitui, na prática, a cobertura frágil/espalhada atual (seletores CSS quebradiços,
ciclo do cliente coberto só via HTTP) por um fluxo único, robusto e legível.

### Não-objetivos (YAGNI)

- **Não** refatorar `test_browser_all_modules.py` nem os demais testes existentes.
- **Não** cobrir o caminho de aprovação pelo admin (apenas o caminho do cliente).
- **Não** cobrir fluxo de rejeição da proposta.
- **Não** fazer cleanup destrutivo dos dados criados (segue padrão da suíte).

## 2. Contexto e descobertas

- A biblioteca **Playwright já está atual (1.58.0)**. O "desatualizado" é o **código de teste**:
  seletores hardcoded (`.swal2-popup`, `#formNovaProposta`, `button.btn-success:has-text("Aprovar")`),
  workarounds para gates que mudaram, e ciclo do cliente coberto só via HTTP.
- **Não existe nenhum `data-testid`** nos templates de catálogo/proposta hoje — causa raiz da fragilidade.
- O fluxo real foi mapeado (rotas e handlers confirmados):
  - Catálogo: `views/catalogo_views.py` (insumos, serviços, composição, vínculo de template).
  - Propostas/templates: `propostas_consolidated.py`.
  - Aprovação → cronograma: `handlers/propostas_handlers.py` + `services/cronograma_proposta.py`.
- **Seed Alfa** (`scripts/seed_demo_alfa.py`) já cria `CronogramaTemplate` com subatividades:
  `"Alvenaria de bloco cerâmico — padrão"`, `"Contrapiso desempenado — padrão"`,
  `"Pintura interna — padrão"`. A etapa 3 vincula o serviço novo a um desses (preferência:
  Alvenaria), **sem precisar criar a árvore de cronograma pela UI**.

## 3. Decisões (do brainstorming)

| Tema | Decisão |
|------|---------|
| Entregável | **1 teste E2E novo dedicado** (deixa o resto da suíte como está) |
| Dados | **Criar tudo via UI** (insumo, serviço+composição, template, proposta) |
| Revisão do link do cliente | **Asserções rigorosas** (conteúdo do template bate exatamente + nada interno vaza) |
| Aprovação + verificação | **Cliente aprova pelo link** + verificação do cronograma **via UI** |
| Seletores | **Adicionar `data-testid`** (edições aditivas nos templates) |

## 4. Arquitetura

**Arquivo:** `tests/test_e2e_jornada_proposta_cronograma_playwright.py`

- **pytest + Playwright sync**, Chromium headless, contra `localhost:5000`.
- Reaproveita fixtures de `tests/conftest.py`: `sige_base_url`, `sige_timeout_ms`,
  `browser_launch_options`.
- Estrutura: classe `TestJornadaPropostaCronograma` com **etapas sequenciais numeradas**
  (`test_01_*`, `test_02_*`, …) executadas em ordem.
- **Sessão de browser logada** compartilhada via fixture de escopo de classe (login único como
  admin Alfa). Estado entre etapas (IDs criados, token do cliente, nomes únicos) guardado em
  atributos de classe / objeto de contexto compartilhado.
- **Login:** `/login` com `admin_alfa` / `Alfa@2026` (campos `input[name=username]`,
  `input[name=password]`), padrão já usado na suíte.
- **Sufixo único por execução:** sufixo (ex. timestamp/uuid curto) injetado via variável de
  ambiente e aplicado a todos os nomes criados (`Cimento E2E <suf>`, `Serviço E2E <suf>`,
  `Template E2E <suf>`, cliente `Cliente E2E <suf>`), evitando colisão entre execuções e com o seed.
- Registro de marcadores existentes: `@pytest.mark.browser`, `@pytest.mark.integration`.

## 5. Etapas detalhadas

### Etapa 1 — Login
Loga como admin Alfa; afirma que não voltou para `/login`.

### Etapa 2 — Criar insumo
`/catalogo/insumos/novo`: nome único, tipo (ex. MATERIAL), unidade, preço. Submete e afirma flash
de sucesso; captura o `insumo_id` (da URL de edição ou da listagem).

### Etapa 3 — Criar serviço + composição + vínculo de cronograma
- `/catalogo/servicos/novo`: nome único, categoria, unidade. Captura `servico_id`.
- `/catalogo/servicos/<id>/composicao`: adiciona o insumo da etapa 2 com coeficiente > 0
  (`/composicao/add`). Afirma que a linha de composição aparece.
- `/catalogo/servicos/<id>/composicao` (modal/seção de template): vincula o serviço ao
  `CronogramaTemplate` **"Alvenaria de bloco cerâmico — padrão"** (`/servicos/<id>/template`).
  Afirma flash `'Cronograma "…" vinculado ao serviço.'`. **Sem esse vínculo o cronograma
  automático não materializa.**

### Etapa 4 — Criar template de proposta
`/propostas/templates/novo` → `criar`: preenche com **valores únicos e marcáveis** que serão
verificados depois no link do cliente:
- `texto_apresentacao` (string única, ex. `APRESENTACAO-E2E-<suf>`)
- `condicoes_pagamento`, `garantias` (strings únicas)
- `prazo_entrega_dias`, `validade_dias` (números específicos)
- ≥1 **cláusula configurável** (título + texto únicos)

Captura `template_id`.

### Etapa 5 — Criar proposta a partir do template + serviço
- `/propostas/criar`: dados do cliente (nome/email/telefone únicos) + `template_id` da etapa 4.
  Captura `proposta_id`.
- Adiciona **item** vinculado ao serviço da etapa 3 (`servico_id`), com quantidade e preço.
  Afirma que o item aparece na proposta com o serviço vinculado.

### Etapa 6 — Pré-configurar cronograma (obrigatório)
- `GET /propostas/<id>/cronograma-revisar`: confirma que a árvore de preview mostra o serviço e
  suas subatividades (vindas do template Alvenaria).
- `POST /propostas/<id>/cronograma-default`: salva o snapshot em `cronograma_default_json`.
  Afirma sucesso. **Sem isso, a aprovação cairia no gate #200 e o cronograma não materializaria.**

### Etapa 7 — Enviar e capturar o link do cliente
Aciona **Enviar** na proposta. Captura o `token_cliente` e monta a URL pública
`/propostas/cliente/<token>`.

### Etapa 8 — Link do cliente: asserções rigorosas (sessão anônima)
Abre `/propostas/cliente/<token>` em **contexto de browser novo, sem login**. Afirma:
- **Template renderizado e batendo exatamente:** texto de apresentação, condições de pagamento,
  garantias, cada cláusula configurável (título+texto), prazo e validade — todos os valores
  únicos da etapa 4 presentes na página.
- **Itens/serviço:** descrição, quantidade, unidade, preço unitário e subtotal do serviço,
  com **valores em formato BR** (`R$ x.xxx,xx`).
- **Sem vazamento interno:** ausência de controles de admin (editar/excluir, menus internos,
  widget de revisão de cronograma, IDs internos crus).
- Botões **Aprovar** e **Rejeitar** presentes e clicáveis.
- **(Opcional)** screenshot full-page (desktop) salvo em `tests/reports/` como artefato.

### Etapa 9 — Cliente aprova pelo link
Na sessão anônima, clica **Aprovar** (`data-testid="portal-aprovar"`). Afirma confirmação de
aprovação na própria página.

### Etapa 10 — Verificar cronograma automático via UI
Volta como admin:
- Localiza a **obra** gerada pela aprovação (lista de obras / link a partir da proposta aprovada).
- Abre o **cronograma da obra**.
- Afirma que **as tarefas foram materializadas**: o nó do serviço criado aparece, com as
  subatividades do template Alvenaria (Marcação, Elevação, Chapisco).
- Afirma o **vínculo tarefa ↔ serviço** (marcação exposta via `data-testid` na tela do cronograma —
  ex. atributo com o `servico_id`/nome do serviço no nó).

## 6. Mecanismo do cronograma automático (referência — "como isso é feito")

1. Aprovação (cliente ou admin) emite o evento `proposta_aprovada`.
2. `handlers/propostas_handlers.py::handle_proposta_aprovada`:
   - cria lançamento contábil (se valor > 0),
   - propaga proposta → **obra** (cada `PropostaItem` vira `ItemMedicaoComercial`),
   - chama `_materializar_cronograma_se_houver`.
3. `services/cronograma_proposta.py::materializar_cronograma`:
   - usa o snapshot `Proposta.cronograma_default_json` (salvo na etapa 6),
   - cria **3 níveis** de `TarefaCronograma`: Serviço → Grupos → Subatividades,
   - vincula cada tarefa ao item via `gerada_por_proposta_item_id`,
   - distribui **pesos** via `ItemMedicaoCronogramaTarefa` (proporção de horas),
   - é **idempotente** (não duplica em reprocessamento).
4. **Gate #200:** se `cronograma_default_json` estiver vazio, a obra redireciona para
   `/obras/<id>/cronograma-revisar-inicial` e **nada é materializado** automaticamente — por isso
   a etapa 6 é parte obrigatória da jornada.

## 7. Mudanças nos templates (`data-testid`, aditivas)

Adicionar `data-testid` (sem alterar comportamento/estilo) nos campos e botões que o teste usa.
Lista de alvos por template:

- **`templates/catalogo/` (insumo):** campos nome/tipo/unidade/preço, botão salvar.
- **`templates/catalogo/` (serviço):** campos nome/categoria/unidade, botão salvar.
- **`templates/catalogo/` (composição):** select de insumo, campo coeficiente, botão adicionar,
  linha de composição resultante; select/botão de vínculo de template.
- **`templates/propostas/` (novo template):** campos de apresentação/condições/garantias/prazo/
  validade, cláusula (título/texto), botão salvar.
- **`templates/propostas/` (nova proposta):** campos do cliente, select de template, linha de item
  (serviço/quantidade/preço), botão salvar; botão **Enviar**.
- **`templates/propostas/cronograma_revisar.html`:** nós da árvore de preview, botão salvar default.
- **`templates/propostas/portal_cliente.html`:** blocos de apresentação, cláusulas, itens, valores;
  botões **Aprovar**/**Rejeitar**.
- **View de cronograma da obra:** nós de tarefa + atributo de vínculo com serviço.

Convenção de nomes: kebab-case com prefixo de domínio — ex. `insumo-nome`, `servico-composicao-add`,
`proposta-item-descricao`, `portal-clausula`, `portal-aprovar`, `cronograma-tarefa`,
`cronograma-tarefa-servico`. A lista exata e final dos `data-testid` é definida na fase de plano,
ao inspecionar cada template.

## 8. Isolamento, execução e relatórios

- **Isolamento:** sufixo único em todos os nomes; sem dependência de ordem com outros testes.
- **Sem teardown destrutivo** por padrão. (Teardown opcional que arquiva/desativa o criado pode
  ser adicionado depois, se desejado.)
- **Execução:**
  - Direta: `pytest tests/test_e2e_jornada_proposta_cronograma_playwright.py -v`
  - Via `run_tests.sh`: novo alias `--jornada` apontando para o arquivo.
- **Relatórios:** HTML em `tests/reports/` (padrão da suíte); screenshot opcional do link do cliente.
- **Pré-requisito de dados:** seed Alfa aplicado (admin + CronogramaTemplates). O `run_tests.sh`
  já sobe o servidor; o seed deve estar presente no banco de teste.

## 9. Critérios de aceite

- O teste roda verde de ponta a ponta contra um banco com o seed Alfa.
- Cada etapa falha com mensagem clara apontando o ponto exato em caso de regressão.
- O link do cliente é validado por conteúdo exato do template + ausência de controles internos.
- Após a aprovação pelo cliente, o cronograma da obra mostra as tarefas materializadas e o vínculo
  com o serviço, verificado via UI.
- Nenhum seletor CSS frágil de biblioteca (ex. `.swal2-*`) é usado para os pontos críticos; os
  alvos usam `data-testid`.
