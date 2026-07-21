# Fase 6 — Orçamento versionado e aditivo contratual

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao contrato da obra um baseline versionado e imutável, e transformar "revisar a proposta de uma obra já vendida" — hoje um evento que duplica silenciosamente itens de medição, duplica receita contábil e reprecifica marcos já faturados — num **aditivo contratual explícito, aprovado e rastreável item a item**.

**Architecture:** Três donos distintos, um por pergunta. A **Proposta** continua dona da versão vigente perante o cliente (o mecanismo existe e funciona — não se mexe). O **Orçamento** ganha cadeia de revisões internas e trava de edição depois de gerar proposta. E nasce a peça que hoje não existe: **`ObraContratoVersao`**, uma cadeia temporal `[vigente_de, vigente_ate)` do valor contratado, com `AditivoContrato` como a única transação que a move. `Obra.valor_contrato` deixa de ser um campo editável e passa a ser **cache derivado** da versão vigente — mantido por um serviço único —, de modo que os ~20 pontos de leitura espalhados pelo sistema continuam funcionando sem alteração. A rastreabilidade item a item entra por dois elos self-FK (`PropostaItem.item_origem_id`, `OrcamentoItem.item_origem_id`) que hoje simplesmente não existem: é o que permite reconciliar a v2 contra a v1 em vez de somar as duas.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py` / `executar_migracoes`), PostgreSQL, pytest (`run_tests.sh --gate`), reportlab (já em `pyproject.toml:17`).

**Nota de granularidade:** esta fase é a 6ª de 9. As Fases 1–5 vão alterar schema e assinaturas antes dela. Por isso este plano é **mais curto e menos literal** que o da Fase 1: define arquivos, responsabilidades, contratos de função, testes e critérios — mas só traz código-fonte onde ele é **fato verificável hoje** (padrão de migration, padrão de teste, o comportamento atual medido). Onde o código dependeria de decisões das fases anteriores, o plano diz o contrato e manda o executor conferir a assinatura real. Isso é deliberado, não preguiça.

---

## 1. Contexto verificado no código

Tudo abaixo foi conferido em 2026-07-21 no commit `fb4147b`. Onde há número, ele foi lido; onde há medição, ela foi executada.

### 1.1 O dano do aditivo, medido

Executei o fluxo real de aprovação (mesmo `EventManager.emit('proposta_aprovada', …)` que as rotas usam), reutilizando os helpers de `tests/test_proposta_revisao_nao_duplica_obra.py`: v1 de R$ 100.000 aprovada → obra criada; v2 (aditivo) de R$ 120.000 herdando `obra_id` → aprovada.

```
apos v1: IMC=1 LANC=1 valor_contrato=100000.0
apos v2: IMC=2 LANC=2 valor_contrato=120000.0 soma_itens=220000.0
itens: [('Estrutura metálica', 100000.0), ('Estrutura metálica (revisada)', 120000.0)]
lancamentos: [(5405, 100000.0), (5406, 120000.0)]
```

Três defeitos numa aprovação só:

| Defeito | Consequência | Onde nasce |
|---|---|---|
| `ItemMedicaoComercial` **duplicado** (1 → 2), soma dos itens R$ 220.000 contra contrato de R$ 120.000 | `medicao_views.py:72` calcula `saldo = valor_contrato − soma_itens` → **−100.000**. O listener `models.py:6263` duplica junto o `ObraServicoCusto`, dobrando o orçado da obra | `handlers/propostas_handlers.py:35-45` — o dedupe é por `proposta_item_id`, e os itens da v2 são **linhas novas** com ids novos, logo `ids_existentes` sai vazio |
| **Lançamento contábil duplicado** — receita reconhecida de R$ 220.000 | Contabilidade e DRE erradas para toda obra que teve aditivo | `handlers/propostas_handlers.py:186-209` lança o `valor_total` **cheio** da v2, não o delta |
| `obra.valor_contrato` **sobrescrito retroativamente** | `MedicaoContrato.valor` é `pct × obra.valor_contrato` (`models.py:5586-5588`) — property calculada, sem congelamento. Toda medição de contrato já emitida muda de valor no instante da aprovação do aditivo | `event_manager.py:1041-1047` |

O terceiro item é uma correção **consciente** da Fase 0.5 (o comentário em `event_manager.py:1035-1040` explica por que o comportamento anterior, de só preencher campo vazio, era pior). Ela resolveu meio problema: o contrato passou a refletir a revisão, mas passou a reescrever o passado. A Fase 6 é a outra metade.

### 1.2 Estado do versionamento hoje

| Fato | Evidência |
|---|---|
| A **Proposta versiona de verdade**: `versao`, `proposta_origem_id`, `substituida_por_id`, `substituida_em`, e `cadeia_versoes()` que caminha a cadeia nos dois sentidos com guarda de ciclo | `models.py:3018-3029`, `models.py:3094-3125` |
| A cadeia **tem UI**: card "Versões desta Proposta" com badge de vigente | `templates/propostas/detalhes_proposta.html:358-395` |
| O **gate de edição funciona**: proposta fora de `rascunho` não pode ser editada por POST direto, tem de passar por nova versão | `propostas_consolidated.py:1511-1518` |
| `criar_nova_versao` clona itens **sem elo item↔item** — não há como saber qual linha da v2 substitui qual linha da v1 | `propostas_consolidated.py:1328-1350` |
| `criar_nova_versao` **perde silenciosamente** `tipo_medicao_override`, `dim_largura`, `dim_comprimento`, `dim_perimetro`, `dim_pe_direito`, `dim_area_manual` — os 6 campos de medição dimensional das migrations 179/180/181. Grep de `dim_`/`tipo_medicao_override` no bloco de clonagem: **zero ocorrências** | `propostas_consolidated.py:1328-1350` vs. `models.py:3199-3205` (colunas existem em `proposta_itens`) |
| `criar_nova_versao` **herda `obra_id`** da origem (correção R1 da Fase 0) e há guarda de reconciliação por cadeia no handler | `propostas_consolidated.py:1311-1317`; `event_manager.py:945-975` |
| O **`Orcamento` não versiona**: sem `versao`, sem `origem_id`, sem `vigente`. Status é texto livre `rascunho\|fechado\|convertido` | `models.py:6512-6557` |
| `duplicar()` cria um `Orcamento` novo **sem nenhuma FK de volta** — a cópia é órfã, não é revisão | `views/orcamentos_views.py:527-588` |
| **Não há trava de edição no Orçamento**: `atualizar`, `adicionar_item`, `atualizar_item`, `remover_item` não olham `status`. Dá para editar um orçamento já `convertido`, mudando o custo por baixo da proposta já enviada | `views/orcamentos_views.py:282-311`, `315`, `382`, `497` |
| `OrcamentoItem` também não tem elo item↔item entre revisões | `models.py:6560-6620` |
| A rota "PDF" da proposta **devolve HTML** (`return html_content`), não PDF | `propostas_consolidated.py:1165` |
| **Não existe comparador** de versões — nenhuma rota, nenhum template | grep `cadeia_versoes` → só `models.py:3094` e o template de detalhe |

### 1.3 A ligação proposta → obra → medição

| Fato | Evidência |
|---|---|
| `Obra.proposta_origem_id` → `propostas_comerciais.id`; `Obra.valor_contrato` é `Float` cru com default `0.0` | `models.py:269`, `models.py:254` |
| `Obra.regime_medicao` é `'fixa'` (marcos contratuais, `MedicaoContrato`) ou `'percentual'` (avanço físico, `MedicaoObra`), default `'fixa'` | `models.py:292`, migration 201 (`migrations.py:13688`) |
| No regime **`percentual`**, o valor medido sai de `ItemMedicaoComercial.valor_comercial` item a item; `valor_contrato` só entra no rateio da entrada e no % exibido | `services/medicao_service.py:122-163` |
| No regime **`fixa`**, o valor de cada marco é `pct × obra.valor_contrato`, recalculado a cada leitura | `models.py:5585-5588` |
| `MedicaoContrato` **não tem UI**: só é criada pelo importador físico-financeiro e lida pelo serviço de cronograma. Zero rotas | `services/importacao_fisico_financeiro.py:730-735`; `services/cronograma_fisico_financeiro.py:355-358`; grep em `views/` → nada |
| `ItemMedicaoComercial.proposta_item_id` é **UNIQUE global** — cada linha de proposta gera no máximo um item de medição | `models.py:5448` |
| `valor_contrato` é **editável em formulário livre**, sem nenhuma guarda | `views/obras.py:873` (POST de `editar_obra`, `views/obras.py:842`), campo em `templates/obra_form.html:491-498` |
| `materializar_cronograma` já é idempotente em duas camadas: por `gerada_por_proposta_item_id` e por chave natural (nome/subatividade + pai), reusando a tarefa existente | `services/cronograma_proposta.py:451`, `:479-505`, `:530-556` |
| `TarefaCronograma.ativa` (Boolean, default true) já existe desde a migration 208 — há como **desativar** tarefa sem apagar | `models.py:4947` |
| A maior migration registrada é a **213** | `migrations.py:4014` |

### 1.4 O precedente que este plano copia

`ObraOrcamentoOperacional` (`models.py:6930`) já resolve, para o **custo operacional**, exatamente o problema que a Fase 6 resolve para o **contrato**: cópia congelada na obra, itens com versões temporais `[vigente_de, vigente_ate)`, `modo_aplicacao` e `motivo` por versão (`models.py:6985-7010`). Leitura pela versão vigente na data de referência em `services/orcamento_operacional.py:137`. **O desenho de `ObraContratoVersao` deve espelhar esse, inclusive nos nomes de coluna**, para que quem já entende um entenda o outro.

---

## 2. O que JÁ existe e NÃO será refeito

Não gaste tempo nestes — todos verificados acima:

1. **BDI padrão TCU (Bloco 3).** `services/pricing.py` implementa `precificar`/`resolver_aliquotas` com cascata proposta → empresa → 0, guarda-corpo de T+L e a invariante `custo + indiretos + tributos + lucro == preço`. 252 linhas de teste em `tests/test_bdi_pricing.py`, migration 189 (`migrations.py:13538`), ADR `docs/adr/0001-bdi-por-dentro-padrao-tcu.md`. **Nada de BDI nesta fase.**
2. **Medição dimensional.** Migrations 179/180/181 já criaram `tipo_medicao` em `insumo`/`servico` e os 6 campos `dim_*`/`tipo_medicao_override` em `orcamento_item` e `proposta_itens`. A fase só precisa **parar de perdê-los na clonagem** (Task 6) — não criar coluna nenhuma.
3. **Versionamento da Proposta.** Cadeia, gate de edição, `cadeia_versoes()`, UI de versões, `PropostaHistorico`. A fase **acrescenta o elo item↔item**, não reescreve a cadeia.
4. **Preço de insumo versionado por vigência.** `PrecoBaseInsumo` + `Insumo.preco_vigente(data_ref)` (`models.py:6357-6367`). O orçamento já lê preço por data.
5. **Idempotência da materialização de cronograma.** Duas camadas, funcionando (`services/cronograma_proposta.py:479-505`). A fase só decide o que fazer com item **suprimido** (Task 9).
6. **Atomicidade da aprovação.** A rota `aprovar` é dona única da transação; handlers não commitam (`propostas_consolidated.py:2343-2369`). Mantenha essa propriedade — não introduza commit dentro de handler.
7. **Obra não duplica mais na revisão.** Correção R1 + 7 testes verdes em `tests/test_proposta_revisao_nao_duplica_obra.py` (rodados: `7 passed`). Não mexa nessa lógica de reconciliação de obra; a fase mexe no que acontece **depois** de achar a obra.
8. **`ObraOrcamentoOperacional`.** A cópia operacional editável do orçamento na obra já existe e já versiona por item. A Fase 6 **não** a substitui — ela cuida do lado custo; a Fase 6 cuida do lado contrato.

---

## 3. Decisões de projeto

Cada decisão de negócio abaixo tem uma **recomendação explícita**, e o plano segue com ela adotada. Todas estão repetidas em "Decisões que precisam do Cássio" (§8) para confirmação — **nenhuma bloqueia a execução**.

### D1 — Quem é o dono da versão vigente: Orçamento ou Proposta?

**Recomendado: nenhum dos dois sozinho. Três donos, uma pergunta cada.**

- **Orçamento** → dono da *revisão interna de custo*. Ganha cadeia (`origem_id`, `versao`) e trava de edição depois de gerar proposta. É o que o time de engenharia versiona.
- **Proposta** → dona da *versão comercial vigente perante o cliente*. Já é, e funciona. Não muda.
- **`ObraContratoVersao`** → dona do *valor contratado que governa faturamento*. É a peça que falta.

Fundamento: a pergunta 1 da DEVOLUTIVA (linha 281) trata Orçamento e Proposta como alternativas excludentes, mas o dano medido em §1.1 não vem de nenhum dos dois — vem de **`Obra.valor_contrato` ser um `Float` sem história**. Inverter a titularidade Proposta→Orçamento custaria caro e não corrigiria um único dos três defeitos. Separar as três perguntas corrige os três.

### D2 — O que caracteriza aditivo e o que caracteriza revisão?

**Recomendado: o divisor é a existência de contrato vigente, não o valor e não o estado da obra.**

- **Não existe** `ObraContratoVersao` vigente para a obra (ou não existe obra) → nova versão de proposta é **revisão**. Substitui livremente, sem trilha contratual. É o comportamento de hoje e está certo.
- **Existe** contrato vigente → toda nova versão aprovada é **aditivo**. Exige `AditivoContrato` com tipo, motivo e aprovação; **não pode** reescrever a versão anterior; abre uma versão nova com `vigente_de` = data da aprovação.

Fundamento contra as duas alternativas óbvias:
- *"Mudou o valor?"* — falha no aditivo de **prazo puro** e no aditivo de escopo em que supressão e acréscimo se compensam (delta zero, escopo diferente). Aditivo de valor zero é aditivo.
- *"A obra já começou?"* — depende da máquina de estados da **Fase 2**, que ainda não existe, e erra o caso real de contrato assinado com obra em `planejamento`. Além disso `Obra.status` é hoje `String(20)` de texto livre (`models.py:257`), inutilizável como critério.

"Existe contrato vigente" é observável no dado, é criado pela própria Fase 6, e não depende de fase futura.

### D3 — Aditivo re-materializa o cronograma?

**Recomendado: sim, mas apenas de forma incremental e aditiva. Nunca apaga, nunca re-sequencia.**

- Item **novo** no aditivo → materializa (o mecanismo idempotente de `services/cronograma_proposta.py:451` já faz isso corretamente).
- Item **alterado** (mesmo elo `item_origem_id`, quantidade/valor diferentes) → **não toca** na tarefa; só o `ItemMedicaoComercial` é atualizado. O cronograma é uma decisão de planejamento, não um derivado do preço.
- Item **suprimido** → tarefa recebe `ativa = False` (`models.py:4947`) e o `ItemMedicaoComercial` correspondente vai para `status='SUPRIMIDO'`. **Nunca `DELETE`.**

Fundamento: apagar `TarefaCronograma` destrói apontamento de RDO (`rdo_apontamento_cronograma`, o índice que a Fase 0.5 levou de 881 ms para 0,034 ms existe porque essa tabela é grande e quente) e deixa o rollback de importação do M05 sem destino. O flag `ativa` foi criado exatamente para este caso e está sem uso de negócio.

### D4 — O que acontece com medições já emitidas quando entra um aditivo?

**Recomendado: nada. Medição emitida é imutável.**

- `MedicaoContrato` ganha `contrato_versao_id` **NOT NULL** (com backfill). A property `valor` passa a ser `pct × versao_apontada.valor`, não `pct × obra.valor_contrato`. Marcos existentes ficam presos à versão em que nasceram.
- Ao aprovar um aditivo, apenas os marcos **ainda não recebidos** (`recebido_no_mes IS NULL`) são repontados para a nova versão — e isso é uma escolha do formulário do aditivo, com preview do antes/depois, não um efeito colateral silencioso.
- `MedicaoObra` já grava valores absolutos por período (`valor_medido_periodo`, `valor_executado_acumulado` — `models.py:5548-5566`), portanto já está protegida. Não precisa de mudança.

Fundamento: resolver por data (`MedicaoContrato.data`) seria mais barato, mas `data` é **nullable** (`models.py:5577`) e o importador nem sempre a preenche — uma FK explícita não tem esse buraco.

### D5 — Como o aditivo lança na contabilidade?

**Recomendado: lança o delta, e só o delta.** `LancamentoContabil` do aditivo tem `valor_total = valor_novo − valor_anterior`, `origem='ADITIVO'`, `origem_id = aditivo.id`. Delta negativo (supressão) inverte débito e crédito. Delta zero não lança.

Fundamento: hoje lança o valor cheio da v2 (medido: R$ 100.000 + R$ 120.000 = R$ 220.000 de receita para um contrato de R$ 120.000). Só o delta reconstitui o valor certo por soma, preservando o lançamento original da venda.

### D6 — `Obra.valor_contrato` some?

**Recomendado: não. Vira cache derivado, mantido por um único escritor.**

Há mais de 20 pontos de leitura (`custos_views.py:181`, `medicao_views.py:70`, `portal_obras_views.py:523`, `relatorios_financeiros_avancados.py:467`, `services/medicao_service.py:102`, `scripts/seed_demo_alfa.py:1084`, templates…). Removê-lo agora é uma refatoração de raio grande e sem ganho. Ele passa a ser espelho de `contrato_vigente(obra.id, obra.admin_id).valor`, escrito **só** por `services/contrato_obra.py`, e read-only na UI.

---

## 4. Dependências de fases anteriores

Declaradas, não assumidas. **Confira o nome real antes de importar — não reimplemente.**

| Fase | O que a Fase 6 consome | Como usar |
|---|---|---|
| **1 — Identidade e papéis** | O decorator de autorização por obra e o resolver `current_user → Funcionario`. O plano da Fase 1 os nomeia `utils/autorizacao.py` (`obras_visiveis`, `pode_ver_obra`, `obra_required`) e `utils/identidade.py` | Aprovar aditivo é ação de obra, não de tenant. Use o decorator de escopo de obra publicado pela Fase 1 nas rotas de `views/aditivos_views.py`. Se o nome mudou, ajuste o import |
| **2 — Máquina de estados da Obra** | A tabela de histórico de transição de estado | Aprovar aditivo **deve** registrar uma linha nesse histórico (evento `aditivo_aprovado`, sem mudar o estado). Se a Fase 2 não expuser API para "registrar evento sem transição", registre só em `AditivoContrato` e abra um TODO explícito — **não** invente transição de estado |
| **4 — Centro de custo obrigatório** | `obra_id`/centro de custo em `gestao_custo_pai` e nos lançamentos | O `LancamentoContabil` do delta (D5) e o `ObraServicoCusto` criado por item novo do aditivo precisam do centro de custo no formato que a Fase 4 definir. Se a Fase 4 tornar a coluna `NOT NULL`, o insert do aditivo quebra sem isso |
| **3, 5** | nada | — |

**Se alguma dessas fases não estiver concluída quando esta começar:** as Tasks 1–4, 6–8 e 10–12 são independentes delas e podem seguir. Só a Task 13 (UI/autorização) e a integração contábil da Task 8 têm acoplamento real.

---

## 5. Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `services/contrato_obra.py` | **novo** — único dono do baseline. `contrato_vigente(obra_id)`, `valor_vigente_em(obra_id, data)`, `abrir_aditivo(...)`, `aprovar_aditivo(...)`, `cancelar_aditivo(...)`. **Único lugar do sistema que escreve `Obra.valor_contrato`** |
| `services/proposta_diff.py` | **novo** — diff item a item entre duas Propostas da mesma cadeia, via `item_origem_id`. Classifica cada linha em `mantido` / `alterado` / `incluido` / `suprimido` |
| `services/orcamento_versao.py` | **novo** — cadeia de revisões do Orçamento: `criar_revisao(orc, motivo, usuario_id)`, `travar(orc)`, `diff_revisoes(a, b)` |
| `views/aditivos_views.py` | **novo** — blueprint `/obras/<int:obra_id>/aditivos`: listar, abrir, aprovar, cancelar, extrato de contrato |
| `templates/aditivos/listar.html`, `templates/aditivos/form.html` | **novos** — extrato de contrato (original + aditivos + vigente) e formulário de aditivo com preview do diff |
| `templates/orcamentos/comparar.html`, `templates/propostas/comparar.html` | **novos** — comparador lado a lado |
| `models.py` | `ObraContratoVersao`, `AditivoContrato`; `MedicaoContrato.contrato_versao_id` + reescrita da property `valor` (`models.py:5585-5588`); `PropostaItem.item_origem_id`; `OrcamentoItem.item_origem_id`; `Orcamento.origem_id`/`versao`/`motivo_revisao`/`travado_em` |
| `migrations.py` | migrations **270–276** + registro em `migrations_to_run` (após `migrations.py:4014`) |
| `handlers/propostas_handlers.py:15-70` | `_propagar_proposta_para_obra` passa a **reconciliar** por cadeia em vez de sempre inserir |
| `handlers/propostas_handlers.py:186-219` | lançamento contábil do aditivo = delta (D5) |
| `event_manager.py:1030-1048` | para de escrever `obra.valor_contrato` direto; delega a `services/contrato_obra.py` |
| `propostas_consolidated.py:1328-1350` | `criar_nova_versao` grava `item_origem_id` **e** os 6 campos dimensionais hoje perdidos |
| `views/orcamentos_views.py:527-588` | `duplicar` → revisão com FK de volta |
| `views/orcamentos_views.py:282,315,382,497` | trava de edição em orçamento travado |
| `views/obras.py:873` | bloqueia edição livre de `valor_contrato` |
| `templates/obra_form.html:491-498` | campo readonly + link "Aditivos" |
| `services/cronograma_proposta.py` | supressão desativa tarefa (`ativa=False`), nunca apaga |
| `tests/test_fase6_contrato_baseline.py` | **novo** — baseline, versões, backfill |
| `tests/test_fase6_aditivo.py` | **novo** — o cenário de §1.1 virado do avesso |
| `tests/test_fase6_rastreabilidade_itens.py` | **novo** — elo item↔item, diff, dimensionais preservados |
| `tests/test_fase6_orcamento_revisao.py` | **novo** — cadeia e trava do Orçamento |

---

## 6. Tarefas

### Task 1: Baseline do contrato — modelo `ObraContratoVersao` + migration 270 + backfill

**Files:**
- Modify: `models.py` (nova classe, próximo a `MedicaoContrato`, `models.py:5568`)
- Modify: `migrations.py` (função + registro após `migrations.py:4014`)
- Test: `tests/test_fase6_contrato_baseline.py`

Modelo, espelhando `ObraOrcamentoOperacionalItemVersao` (`models.py:6985`):

| Coluna | Tipo | Nota |
|---|---|---|
| `id` | Integer PK | |
| `obra_id` | FK `obra.id` ON DELETE CASCADE, NOT NULL, index | |
| `admin_id` | FK `usuario.id`, NOT NULL, index | invariante de tenant |
| `versao` | Integer NOT NULL | 1 = contrato original |
| `valor` | Numeric(15,2) NOT NULL | **Numeric, não Float** — `Obra.valor_contrato` é Float por herança; o baseline nasce certo |
| `prazo_dias` | Integer nullable | prazo contratual vigente |
| `vigente_de` | DateTime NOT NULL, index | |
| `vigente_ate` | DateTime nullable, index | NULL = versão atual |
| `origem_tipo` | String(30) NOT NULL | `'contrato_original'` \| `'aditivo'` \| `'backfill'` |
| `origem_proposta_id` | FK `propostas_comerciais.id` ON DELETE SET NULL, nullable | |
| `aditivo_id` | FK `aditivo_contrato.id` ON DELETE SET NULL, nullable | preenchido na Task 3 |
| `motivo` | Text nullable | |
| `criado_por_id` | FK `usuario.id`, nullable | |
| `created_at` | DateTime default utcnow | |

Índice `idx_contrato_versao_lookup (obra_id, vigente_de, vigente_ate)`, espelhando `models.py:6994`.

- [ ] **Step 1: Escreva o teste que falha**

`tests/test_fase6_contrato_baseline.py`, seguindo o padrão de `tests/test_proposta_revisao_nao_duplica_obra.py:1-58` (docstring explicando o porquê, `import main` no topo, `pytestmark = pytest.mark.integration`, fixture `_config` que liga `TESTING` e desliga CSRF, factories com sufixo `uuid.uuid4().hex[:8]`).

Testes:
1. Toda obra do tenant com `valor_contrato > 0` tem **exatamente uma** versão com `vigente_ate IS NULL`.
2. Nunca há duas versões vigentes simultâneas para a mesma obra.
3. Após o backfill, `contrato_vigente(obra.id, obra.admin_id).valor == Decimal(str(obra.valor_contrato))` para toda obra pré-existente.
4. Invariante de tenant: `ObraContratoVersao.admin_id == Obra.admin_id` em 100% das linhas.

- [ ] **Step 2: Rode e confirme que falha**

`python -m pytest tests/test_fase6_contrato_baseline.py -q` → erro de import (`cannot import name 'ObraContratoVersao'`).

- [ ] **Step 3: Modelo + migration 270**

Migration segue o padrão verificado de `_migration_197_medicao_contrato` (`migrations.py:13605-13630`): `with db.engine.begin() as conn`, `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, log de sucesso, `raise` no except.

```python
def _migration_270_obra_contrato_versao():
    """Fase 6 — baseline versionado do contrato da obra.

    Cria obra_contrato_versao e faz o backfill: cada obra com
    valor_contrato > 0 ganha a versão nº1 (origem_tipo='backfill'),
    vigente_de = obra.created_at (fallback data_inicio, fallback now).
    Idempotente. Não altera obra.valor_contrato.
    """
```

O backfill roda **dentro da mesma migration**, com `INSERT ... SELECT ... WHERE NOT EXISTS`, para não deixar janela de obra sem baseline.

- [ ] **Step 4: Rode o teste — deve passar**

- [ ] **Step 5: Commit** — `feat(fase6): baseline versionado do contrato da obra (migration 270)`

---

### Task 2: `services/contrato_obra.py` — leitura e o único escritor

**Files:**
- Create: `services/contrato_obra.py`
- Modify: `event_manager.py:1030-1048`
- Test: `tests/test_fase6_contrato_baseline.py` (acrescenta)

Contrato de função:

```
contrato_vigente(obra_id: int, admin_id: int) -> ObraContratoVersao | None
valor_vigente_em(obra_id: int, admin_id: int, quando: datetime) -> Decimal
abrir_versao(obra, valor, origem_tipo, *, origem_proposta_id=None,
             aditivo_id=None, motivo=None, criado_por_id=None,
             vigente_de=None) -> ObraContratoVersao
```

`abrir_versao` fecha a versão vigente (`vigente_ate = vigente_de` da nova), insere a nova, e **só então** atualiza `obra.valor_contrato = float(nova.valor)` — o cache de D6. Não commita (a rota chamadora é dona da transação, `propostas_consolidated.py:2343-2347`).

`event_manager.py:1041-1047` deixa de fazer a atribuição direta e passa a chamar `abrir_versao(..., origem_tipo='contrato_original', origem_proposta_id=proposta.id)` **apenas quando não há versão vigente**. Quando já há, não faz nada — quem move o baseline daí em diante é o aditivo (Task 3/7).

- [ ] **Step 1: Testes que falham** — versão fechada não muda mais de valor; `valor_vigente_em` de uma data anterior devolve o valor antigo; `obra.valor_contrato` sempre igual à versão vigente após qualquer operação.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Implemente o serviço e redirecione `event_manager`**
- [ ] **Step 4: Rode `tests/test_proposta_revisao_nao_duplica_obra.py` inteiro** — os 7 testes existentes têm de continuar verdes, inclusive `test_aprovar_revisao_atualiza_valor_de_contrato` (`tests/test_proposta_revisao_nao_duplica_obra.py:220-247`), que exige que a obra passe a 120.000 após a v2. Com a Task 7 ele passará pelo caminho do aditivo; **até lá**, mantenha `abrir_versao` sendo chamada também na reconciliação, para não regredir.
- [ ] **Step 5: Commit** — `feat(fase6): services/contrato_obra como único escritor de valor_contrato`

---

### Task 3: `AditivoContrato` + migration 271

**Files:**
- Modify: `models.py`, `migrations.py`
- Test: `tests/test_fase6_aditivo.py`

| Coluna | Tipo | Nota |
|---|---|---|
| `id`, `obra_id`, `admin_id` | | idem Task 1 |
| `numero` | String(30) NOT NULL | sequencial por obra: `AD-001`, `AD-002` |
| `tipo` | String(20) NOT NULL | `'acrescimo'` \| `'supressao'` \| `'prazo'` \| `'misto'` |
| `status` | String(20) NOT NULL default `'rascunho'` | `rascunho` → `aprovado` \| `cancelado` |
| `motivo` | Text NOT NULL | exigido — aditivo sem motivo é o que se quer eliminar |
| `valor_anterior` | Numeric(15,2) NOT NULL | congelado na abertura |
| `valor_novo` | Numeric(15,2) NOT NULL | |
| `prazo_delta_dias` | Integer nullable | |
| `proposta_id` | FK `propostas_comerciais.id` SET NULL | a versão de proposta que originou o aditivo |
| `criado_por_id`, `aprovado_por_id` | FK `usuario.id` | |
| `criado_em`, `aprovado_em` | DateTime | |

Property `valor_delta` = `valor_novo − valor_anterior`.

Unique `(obra_id, numero)`. Só um aditivo em `rascunho` por obra de cada vez (checagem no serviço, não constraint — supressão parcial de concorrência é aceitável aqui e uma constraint parcial complicaria o backfill).

- [ ] **Step 1: Teste que falha** — abrir aditivo em obra sem contrato vigente levanta erro; aprovar aditivo cria a versão nº2 e fecha a nº1; cancelar aditivo em rascunho não toca no baseline; aprovar aditivo já aprovado é no-op idempotente.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Modelo + migration 271 + `abrir_aditivo`/`aprovar_aditivo`/`cancelar_aditivo` em `services/contrato_obra.py`**
- [ ] **Step 4: Rode o teste**
- [ ] **Step 5: Commit** — `feat(fase6): AditivoContrato e transições (migration 271)`

---

### Task 4: `MedicaoContrato` presa à versão — migration 272

**Files:**
- Modify: `models.py:5568-5596` (coluna nova + reescrita da property `valor`, `models.py:5585-5588`)
- Modify: `migrations.py`
- Test: `tests/test_fase6_aditivo.py`

`MedicaoContrato.contrato_versao_id` → FK `obra_contrato_versao.id`, index. Backfill: aponta todo marco existente para a versão vigente da obra no momento da migration (que, depois da Task 1, é a nº1).

Property `valor` passa a `pct × (self.contrato_versao.valor if self.contrato_versao else obra.valor_contrato)` — o fallback protege linhas criadas por caminho que ainda não foi atualizado (`services/importacao_fisico_financeiro.py:730`, que também deve passar a preencher a FK).

**Este é o único ponto da fase que muda semântica de leitura em produção.** O teste tem de cobrir: marco criado antes do aditivo mantém o valor; marco repontado passa a valer pela versão nova; soma dos `pct` continua conferindo com `scripts/verificar_equivalencia_obra.py:105-107`.

- [ ] **Step 1: Teste que falha** — cenário: obra 100k com 2 marcos de 50%; aditivo para 120k; marco já recebido continua valendo 50.000; marco futuro repontado passa a 60.000.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Coluna, migration 272 com backfill, property reescrita, importador preenchendo a FK**
- [ ] **Step 4: Rode `tests/test_importacao_fisico_financeiro.py` também** — ele lê `MedicaoContrato.__table__.columns` (`tests/test_importacao_fisico_financeiro.py:29`) e é o guardião desse caminho
- [ ] **Step 5: Commit** — `feat(fase6): medição de contrato presa à versão do baseline (migration 272)`

---

### Task 5: Fechar a edição livre de `valor_contrato`

**Files:**
- Modify: `views/obras.py:873`
- Modify: `templates/obra_form.html:491-498`
- Test: `tests/test_fase6_contrato_baseline.py`

Regra: se a obra **tem** versão de contrato vigente, o POST de `editar_obra` **ignora** `valor_contrato` do form e emite flash explicando que a mudança se faz por aditivo, com link. Se **não tem** (obra criada à mão, sem proposta), o campo continua editável e a gravação passa por `abrir_versao(origem_tipo='contrato_original')` — assim toda obra acaba com baseline.

No template, quando há contrato vigente: `readonly` + `disabled` no input, badge com a versão vigente, e link para `/obras/<id>/aditivos`. Não remova o campo — `views/obras.py:391` (criação) ainda o usa.

- [ ] **Step 1: Teste que falha** — POST em `/obras/<id>/editar` com `valor_contrato` alterado numa obra com baseline não muda o valor e não cria versão.

Este é o primeiro teste da fase que faz HTTP autenticado. O login na suíte é **injeção de sessão**, não POST em `/login` — o padrão verificado está em `tests/test_fase0_autorizacao.py:55-60`:

```python
def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c
```

- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Implemente as duas pontas**
- [ ] **Step 4: Rode o teste**
- [ ] **Step 5: Commit** — `feat(fase6): valor de contrato só muda por aditivo`

---

### Task 6: Elo item↔item na proposta — migration 273 + fim da perda dos campos dimensionais

**Files:**
- Modify: `models.py:3164+` (`PropostaItem.item_origem_id`, self-FK `proposta_itens.id` ON DELETE SET NULL, nullable, index)
- Modify: `migrations.py`
- Modify: `propostas_consolidated.py:1328-1350`
- Test: `tests/test_fase6_rastreabilidade_itens.py`

Duas correções no mesmo bloco de clonagem:
1. Gravar `item_origem_id=it.id` — o elo que não existe.
2. Copiar `tipo_medicao_override`, `dim_largura`, `dim_comprimento`, `dim_perimetro`, `dim_pe_direito`, `dim_area_manual` — verificado ausentes hoje (§1.2). Sem isso, revisar uma proposta apaga a medição dimensional e o PDF perde as dimensões.

Migration **276** (Task 12) fará o backfill retroativo do elo nas cadeias já existentes, por casamento de `descricao` + `ordem` dentro da mesma cadeia. Aqui só a coluna.

- [ ] **Step 1: Teste que falha** — criar v1 com item dimensional preenchido, chamar a rota real `/propostas/<id>/nova-versao`, assertar que o item da v2 tem `item_origem_id` apontando para o da v1 **e** os 6 campos dimensionais idênticos.
- [ ] **Step 2: Rode e confirme a falha** — o teste falha duas vezes: coluna inexistente e campos zerados.
- [ ] **Step 3: Coluna, migration 273, clonagem corrigida**
- [ ] **Step 4: Rode o teste**
- [ ] **Step 5: Commit** — `fix(fase6): revisão de proposta preserva elo de item e medição dimensional (migration 273)`

---

### Task 7: Propagação reconciliadora — matar a duplicação de itens de medição

**Files:**
- Modify: `handlers/propostas_handlers.py:15-70`
- Test: `tests/test_fase6_aditivo.py`

Esta é a task que vira do avesso o resultado medido em §1.1. `_propagar_proposta_para_obra` deixa de ser "insere tudo que não tem `proposta_item_id`" e passa a reconciliar contra a cadeia:

Para cada `PropostaItem` da versão sendo aprovada, subindo por `item_origem_id` até achar um ancestral que já tenha `ItemMedicaoComercial` na obra:

| Caso | Ação |
|---|---|
| Achou ancestral com IMC | **Atualiza** o IMC: `nome`, `valor_comercial`, `quantidade`, `servico_id`, e reaponta `proposta_item_id` para a linha nova. **Nunca insere.** Atualiza o `ObraServicoCusto` pareado (`valor_orcado`) |
| Não achou (item novo do aditivo) | Insere, como hoje — o listener `models.py:6263` cria o `ObraServicoCusto` |
| Ancestral com IMC que **não tem** descendente nesta versão (item suprimido) | `status='SUPRIMIDO'`, `valor_comercial` mantido para histórico. **Nunca `DELETE`** — pode haver `MedicaoObraItem` apontando (`models.py:5548`) |

Cuidado: `ItemMedicaoComercial.proposta_item_id` é **UNIQUE global** (`models.py:5448`). Reapontar exige liberar o valor antigo na mesma transação. Um `flush()` entre o clear e o set resolve; sem ele o Postgres reclama.

Cuidado 2: se o item já foi medido (`percentual_executado_acumulado > 0`) e o aditivo **reduz** `valor_comercial` abaixo do já medido, a redução é ilegal — o aditivo tem de ser recusado com mensagem clara. Este é o único ponto da fase que pode barrar um aditivo por motivo aritmético.

- [ ] **Step 1: Teste que falha — reproduza a medição de §1.1**

Reaproveite os helpers de `tests/test_proposta_revisao_nao_duplica_obra.py:53-128` (`_ambiente`, `_aprovar`, `_clonar_como_revisao`, `_obras_do_tenant`) — eles já disparam o `EventManager.emit` real. Asserções:

```
apos v2:  ItemMedicaoComercial.count(obra) == 1        # hoje: 2
          soma(valor_comercial) == 120000              # hoje: 220000
          ObraServicoCusto.count(obra) == 1            # hoje: 2
          medicao_views: saldo == 0                    # hoje: -100000
```

E um segundo teste: item suprimido na v2 → IMC fica `SUPRIMIDO`, não some.
E um terceiro: aditivo que reduz item já medido em 60% → recusado.

- [ ] **Step 2: Rode e confirme a falha** — os números de hoje estão em §1.1; se seus números divergirem, **pare e reinvestigue** antes de escrever código: alguma fase anterior mudou o caminho.
- [ ] **Step 3: Implemente a reconciliação**
- [ ] **Step 4: Rode `tests/test_fase6_aditivo.py`, `tests/test_propagacao_proposta_obra.py` e `tests/test_ciclo_proposta_obra_medido_cr.py`**
- [ ] **Step 5: Commit** — `fix(fase6): aprovar aditivo reconcilia itens de medição em vez de duplicar`

---

### Task 8: Contabilidade do aditivo — só o delta

**Files:**
- Modify: `handlers/propostas_handlers.py:164-221`
- Test: `tests/test_fase6_aditivo.py`

Quando a aprovação é de um aditivo (existe contrato vigente antes — critério D2), o lançamento contábil usa `valor_delta`, `origem='ADITIVO'`, `origem_id = aditivo.id`. Delta negativo inverte débito (`1.1.02.001`) e crédito (`4.1.01.001`) — as contas usadas hoje em `handlers/propostas_handlers.py:200-209`. Delta zero (aditivo de prazo puro) não lança nada.

Preserve a propriedade de atomicidade: o handler continua sem `commit`/`rollback` (`handlers/propostas_handlers.py:87-91`).

Dependência da **Fase 4**: se o centro de custo virar obrigatório em `LancamentoContabil`/`PartidaContabil`, preencha-o aqui com o centro de custo da obra. Confira o nome da coluna antes.

- [ ] **Step 1: Teste que falha** — soma de `LancamentoContabil` com `origem in ('PROPOSTAS','ADITIVO')` para a obra == `valor_contrato` vigente. Hoje dá 220.000 contra 120.000.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Implemente**
- [ ] **Step 4: Rode o teste + `tests/test_ciclo_proposta_obra_medido_cr.py`**
- [ ] **Step 5: Commit** — `fix(fase6): aditivo lança o delta contábil, não o valor cheio`

---

### Task 9: Cronograma no aditivo — incremental, nunca destrutivo

**Files:**
- Modify: `services/cronograma_proposta.py` (materialização) e/ou `handlers/propostas_handlers.py:118-162`
- Test: `tests/test_fase6_aditivo.py`

Implementa D3. O caminho de materialização já é idempotente por `gerada_por_proposta_item_id` e por chave natural (`services/cronograma_proposta.py:479-505`) — o item **novo** já funciona. Falta:

- Item **suprimido**: a tarefa raiz gerada pelo `proposta_item_id` do ancestral recebe `ativa = False` (`models.py:4947`), em cascata nos filhos. Nenhum `DELETE`.
- Item **alterado**: no-op no cronograma, por decisão explícita (D3).
- Registrar o efeito em `CronogramaImportacaoEvento` se a API dele aceitar origem não-import; se não aceitar, registrar em `AditivoContrato.motivo`/log e **não** forçar.

Cuidado: `registrar_versao_inicial` (`handlers/propostas_handlers.py:142-148`) só deve rodar na primeira materialização. Aditivo não é versão inicial de cronograma.

- [ ] **Step 1: Teste que falha** — v1 com 2 serviços materializados; v2 suprime o segundo e acrescenta um terceiro. Esperado: tarefas do primeiro intactas, do segundo com `ativa=False`, do terceiro criadas; nenhuma tarefa apagada; apontamentos de RDO existentes preservados.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Implemente**
- [ ] **Step 4: Rode o teste + `tests/test_e2e_jornada_proposta_cronograma_playwright.py` (ou o gate correspondente, se browser estiver fora)**
- [ ] **Step 5: Commit** — `feat(fase6): aditivo ajusta cronograma sem destruir histórico`

---

### Task 10: Cadeia de revisões do Orçamento — migrations 274 e 275

**Files:**
- Modify: `models.py:6512-6620`
- Modify: `migrations.py`
- Create: `services/orcamento_versao.py`
- Modify: `views/orcamentos_views.py:527-588`
- Test: `tests/test_fase6_orcamento_revisao.py`

Colunas novas em `orcamento` (migration 274): `origem_id` (self-FK, SET NULL, nullable, index — aponta para a **raiz** da cadeia), `revisao_de_id` (self-FK — aponta para a revisão **imediatamente anterior**), `versao` Integer NOT NULL default 1, `motivo_revisao` Text nullable, `travado_em` DateTime nullable.

Coluna nova em `orcamento_item` (migration 275): `item_origem_id`, self-FK `orcamento_item.id` SET NULL, nullable, index.

`views/orcamentos_views.py:530` (`duplicar`) passa a delegar a `services/orcamento_versao.criar_revisao`, que faz o que `duplicar` já faz (`views/orcamentos_views.py:538-580` — copia todos os overrides, composição, dimensionais, template) **mais**: grava `origem_id`/`revisao_de_id`/`versao`/`motivo_revisao` no orçamento e `item_origem_id` em cada item. O título deixa de ser `"… (cópia)"` e passa a `"… (rev. N)"`.

Mantenha a rota `duplicar` no mesmo endpoint — dois templates a referenciam (`templates/orcamentos/listar.html:45`, `templates/orcamentos/editar.html:26`). Só o corpo muda.

- [ ] **Step 1: Teste que falha** — revisar um orçamento produz `versao=2`, `revisao_de_id` correto, `origem_id` igual à raiz, e todo item com `item_origem_id` preenchido; cadeia de 3 revisões converge para a mesma raiz.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Colunas, migrations 274/275, serviço, rota**
- [ ] **Step 4: Rode o teste + `tests/test_e2e_orcamento_proposta.py`**
- [ ] **Step 5: Commit** — `feat(fase6): cadeia de revisões do Orçamento (migrations 274, 275)`

---

### Task 11: Trava de edição do orçamento convertido

**Files:**
- Modify: `views/orcamentos_views.py:282` (`atualizar`), `:315` (`adicionar_item`), `:382` (`atualizar_item`), `:472` (`reset_composicao`), `:497` (`remover_item`), `:514` (`excluir`)
- Modify: `views/orcamentos_views.py:592` (`gerar_proposta` — passa a travar)
- Test: `tests/test_fase6_orcamento_revisao.py`

Hoje qualquer uma dessas seis rotas edita um orçamento já `convertido`, alterando o custo por baixo de uma proposta enviada. Regra nova: se `orcamento.travado_em is not None`, a rota recusa com flash apontando para "criar revisão". `gerar_proposta` (`views/orcamentos_views.py:786-787`, onde hoje só mexe no `status`) passa a setar `travado_em = utcnow()`.

Guarda de compatibilidade: orçamentos legados com `status='fechado'`/`'convertido'` e `travado_em IS NULL` **não** são travados retroativamente — travar o estoque existente quebraria fluxo em curso sem aviso. Só o que passar por `gerar_proposta` daqui em diante trava. Registre isso no docstring.

- [ ] **Step 1: Teste que falha** — POST em cada uma das seis rotas num orçamento travado não altera nada e devolve redirect com flash; num orçamento em rascunho continua funcionando.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Implemente a guarda (helper único, não seis cópias)**
- [ ] **Step 4: Rode o teste + `tests/test_orcamento_override_e2e.py`**
- [ ] **Step 5: Commit** — `feat(fase6): orçamento convertido em proposta fica travado para edição`

---

### Task 12: Diff e comparador de versões + migration 276 (backfill do elo)

**Files:**
- Create: `services/proposta_diff.py`, `templates/propostas/comparar.html`, `templates/orcamentos/comparar.html`
- Modify: `services/orcamento_versao.py` (função `diff_revisoes`)
- Modify: `propostas_consolidated.py` (rota `/propostas/<int:id>/comparar/<int:outra_id>`), `views/orcamentos_views.py` (rota análoga)
- Modify: `migrations.py` (276)
- Test: `tests/test_fase6_rastreabilidade_itens.py`

Contrato do diff (idêntico nos dois serviços, para que os templates sejam simétricos):

```
diff(origem, destino) -> list[dict]
# cada dict: {
#   'situacao': 'mantido'|'alterado'|'incluido'|'suprimido',
#   'origem': item | None,
#   'destino': item | None,
#   'delta_quantidade': Decimal | None,
#   'delta_valor': Decimal | None,
# }
```

Pareamento **só** por `item_origem_id`. Não caia na tentação de casar por `descricao` em runtime — isso é o que produz falso "mantido" quando o operador renomeia a linha.

Migration 276 faz o backfill retroativo do elo nas cadeias existentes, casando `(descricao, ordem)` dentro da mesma cadeia de proposta e dentro da mesma cadeia de orçamento. É **best-effort e explícito**: linha que não casar fica `NULL` e aparece no diff como `incluido`/`suprimido`. Loga a contagem de casados e não-casados. Não invente casamento aproximado.

As duas telas mostram: cabeçalho com as duas versões e o delta total, tabela de itens colorida por situação, e o total geral com o delta destacado.

- [ ] **Step 1: Teste que falha** — cadeia v1→v2 com um item mantido, um alterado, um incluído e um suprimido produz exatamente essas quatro classificações e o `delta_valor` total bate com `v2.valor_total − v1.valor_total`.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Serviços, rotas, templates, migration 276**
- [ ] **Step 4: Rode o teste**
- [ ] **Step 5: Commit** — `feat(fase6): comparador de versões de proposta e orçamento (migration 276)`

---

### Task 13: UI do aditivo e extrato de contrato

**Files:**
- Create: `views/aditivos_views.py`, `templates/aditivos/listar.html`, `templates/aditivos/form.html`
- Modify: `app.py` (registro do blueprint) ou `main.py`, conforme o padrão do módulo vizinho
- Modify: `templates/obras/detalhes_obra_profissional.html` (aba/atalho "Contrato e aditivos")
- Test: `tests/test_fase6_aditivo.py`

Rotas: `GET /obras/<id>/aditivos` (extrato: contrato original, cada aditivo com delta e motivo, valor vigente, cadeia de `ObraContratoVersao`), `GET|POST /obras/<id>/aditivos/novo`, `POST /obras/<id>/aditivos/<aid>/aprovar`, `POST /obras/<id>/aditivos/<aid>/cancelar`.

O formulário de aditivo mostra o **preview do diff** (Task 12) entre a proposta vigente e a nova versão, antes de aprovar. Aprovar sem ver o impacto é o que a fase existe para impedir.

**Autorização — dependência da Fase 1:** use o decorator de escopo por obra publicado por ela (o plano da Fase 1 o chama `obra_required`, em `utils/autorizacao.py`). Aprovar aditivo é ação sensível: exija o papel que a Fase 1 definir como equivalente a gestor da obra, **não** apenas `@admin_required`. Confira o nome real antes de importar.

⚠️ **Ordem de import em `app.py` é contrato não declarado** (`ESTADO-ATUAL.md`, armadilha 5): registre o blueprint junto dos vizinhos de obra, não no topo, e rode a suíte inteira depois.

- [ ] **Step 1: Teste que falha** — usuário sem papel de gestor da obra recebe 403 em `aprovar`; com papel, o aditivo aprova e o extrato mostra as duas versões.
- [ ] **Step 2: Rode e confirme a falha**
- [ ] **Step 3: Implemente blueprint, templates e registro**
- [ ] **Step 4: Rode o teste + smoke de rotas**
- [ ] **Step 5: Commit** — `feat(fase6): tela de aditivos e extrato de contrato da obra`

---

### Task 14: Fecho da fase

- [ ] **Step 1: Rode o gate** — `bash run_tests.sh --gate`. Compare o total com os 878 testes de referência do `ESTADO-ATUAL.md`. Qualquer teste que **passe a falhar** é regressão desta fase até prova em contrário.
- [ ] **Step 2: Confira as migrations** — 270 a 276 registradas em `migrations_to_run` (`migrations.py:3831-4014`), na ordem, e o boot da app aplicando-as sem erro. Rode duas vezes para provar idempotência.
- [ ] **Step 3: Rode `ruff check` nos arquivos tocados** — não herde violação nova (543 existentes são dívida anterior; não aumente a conta).
- [ ] **Step 4: Atualize `ESTADO-ATUAL.md`** — marque a Fase 6 e registre o que ficou em aberto (§8).
- [ ] **Step 5: Commit** — `chore(fase6): fecho — orçamento versionado e aditivo contratual`

---

## 7. Premissas a reconfirmar antes de executar

Esta fase é a 6ª de 9. Tudo abaixo foi verificado em `fb4147b`, mas as Fases 1–5 rodam antes dela. **Reconfirme cada item antes da Task 1** — 15 minutos de grep economizam meia fase.

| # | Premissa | Por que pode ter mudado | Como reconfirmar |
|---|---|---|---|
| 1 | `Obra.valor_contrato` continua `Float` e escrito só em `event_manager.py:1043`, `views/obras.py:391` e `:873` | A Fase 2 (máquina de estados) e a Fase 4 (centro de custo) mexem em `Obra`. Se alguém acrescentou outro escritor, D6 fura | `grep -rn "valor_contrato\s*=" --include=*.py . \| grep -v archive \| grep -v tests` |
| 2 | A duplicação de IMC/lançamento medida em §1.1 ainda acontece com os mesmos números | Se uma fase anterior "consertou" isso por outro caminho, a Task 7 muda de escopo | Rode o probe: reaproveite `tests/test_proposta_revisao_nao_duplica_obra.py` como módulo e conte `ItemMedicaoComercial` e `LancamentoContabil` após aprovar v1 e v2 |
| 3 | `handlers/propostas_handlers.py:15-70` continua sendo o único ponto que cria `ItemMedicaoComercial` a partir de proposta | O importador físico-financeiro cria IMC por outro caminho (`services/importacao_fisico_financeiro.py`) e pode ter sido unificado | `grep -rn "ItemMedicaoComercial(" --include=*.py . \| grep -v archive \| grep -v tests` |
| 4 | A maior migration continua abaixo de 270 | Fases 1–5 vão consumir números. O plano da Fase 1 reserva 214–216; as demais não estão escritas | `grep -n "migrations_to_run" -A 400 migrations.py \| tail -30` |
| 5 | `MedicaoContrato` continua sem UI de escrita | Se a Fase 8 (financeiro) antecipou uma tela, a Task 4 precisa cobri-la também | `grep -rn "MedicaoContrato" views/ *.py \| grep -v archive` |
| 6 | O nome real do decorator de autorização por obra da Fase 1 | O plano da Fase 1 diz `utils/autorizacao.obra_required`, mas é plano, não código | `ls utils/autorizacao.py && grep -n "^def \|^class " utils/autorizacao.py` |
| 7 | A Fase 4 não tornou `centro de custo` obrigatório em `LancamentoContabil`/`ObraServicoCusto` sem default | Se tornou, os inserts das Tasks 7 e 8 quebram com `IntegrityError` | Inspecione o modelo e as migrations da Fase 4 |
| 8 | `Obra.regime_medicao` continua `'fixa'\|'percentual'` (`models.py:292`) | Se a Fase 2 modelou regime como enum ou o moveu, D4 muda de forma | `grep -n "regime_medicao" models.py services/*.py` |
| 9 | `criar_nova_versao` continua sendo a única porta para revisar proposta enviada (`propostas_consolidated.py:1511-1518` é o gate) | Uma fase anterior pode ter aberto exceção | `grep -n "rascunho" propostas_consolidated.py \| head -20` |
| 10 | `TarefaCronograma.ativa` continua existindo e sem semântica de negócio conflitante (`models.py:4947`) | A Fase 7 (planejamento avançado) é depois, mas o M10 do cronograma pode ter usado | `grep -rn "\.ativa" services/cronograma*.py views/cronograma*.py` |

---

## 8. Decisões que precisam do Cássio

Todas já têm recomendação adotada — o plano roda sem resposta. A resposta pode **simplificar**, não desbloquear.

| # | Pergunta | Recomendação adotada |
|---|---|---|
| **1** | Dono da versão vigente: Orçamento ou Proposta? (pergunta 1 da DEVOLUTIVA, linha 281) | **Três donos separados** (D1): Orçamento versiona custo interno, Proposta versiona o compromisso com o cliente, `ObraContratoVersao` versiona o valor que fatura. A pergunta como posta assume que os dois competem pelo mesmo papel; eles não competem |
| **2** | O que caracteriza aditivo vs. revisão? | **Existência de contrato vigente** (D2), não o valor e não o estado da obra. Aditivo de prazo com delta zero continua sendo aditivo |
| **3** | Aditivo re-materializa cronograma? | **Sim, só incremental** (D3). Item novo materializa; item alterado não toca; item suprimido vira `ativa=False`. Nenhum `DELETE`, nunca |
| **4** | Medição já emitida muda de valor com o aditivo? | **Não** (D4). `MedicaoContrato` fica presa à versão em que nasceu; só marcos não recebidos podem ser repontados, e por escolha explícita no formulário |
| **5** | Como o aditivo entra na contabilidade? | **Só o delta** (D5), `origem='ADITIVO'`. Hoje lança o valor cheio e infla a receita — medido: 220k para um contrato de 120k |
| **6** | `Obra.valor_contrato` deixa de existir? | **Não** (D6). Vira cache derivado, read-only na UI, com escritor único |
| **7** | Aditivo exige aprovação de quem? | **Do papel de gestor da obra definido pela Fase 1**, não de qualquer `ADMIN`. Se você quiser dupla aprovação por valor (a pergunta 3 da DEVOLUTIVA, sobre alçada), isso encaixa em `AditivoContrato` sem mudar o schema — mas precisa do valor de X |
| **8** | Orçamentos legados já `convertido` devem travar retroativamente? | **Não** (Task 11). Travar o estoque existente quebra fluxo em curso sem aviso. Só trava o que passar por `gerar_proposta` daqui em diante |

---

## 9. Riscos

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **A Task 4 muda semântica de leitura em produção.** `MedicaoContrato.valor` é property calculada; trocar a base do cálculo altera número que já está em relatório | Média | Backfill aponta tudo para a versão nº1, cujo valor é exatamente o `valor_contrato` de hoje → no dia do deploy, nenhum número muda. Só muda quando alguém aprovar o primeiro aditivo. Teste dedicado a isso na Task 4 |
| **`ItemMedicaoComercial.proposta_item_id` é UNIQUE global** (`models.py:5448`) — reapontar na Task 7 pode dar `IntegrityError` dentro da transação atômica da aprovação, derrubando a aprovação inteira | Alta se ignorado | `flush()` entre o clear e o set; teste explícito que aprova três versões em cadeia |
| **Ordem de import em `app.py`** derruba metade do sistema se o blueprint novo entrar no lugar errado (`ESTADO-ATUAL.md`, armadilha 5) | Média | Registrar junto dos vizinhos de obra e rodar a suíte inteira na Task 13, não só o teste da task |
| **O backfill da migration 276 casa itens errados** por `(descricao, ordem)` | Média | Best-effort declarado: o que não casar fica `NULL` e aparece como incluído/suprimido no diff — visível e corrigível à mão. Loga contagem. Nunca casa por aproximação |
| **Conflito de numeração de migration** com as Fases 1–5 | Baixa | Faixa 270–279 reservada; premissa 4 do §7 reconfirma antes de começar |
| **Regressão nos 7 testes de `test_proposta_revisao_nao_duplica_obra.py`**, em especial `test_aprovar_revisao_atualiza_valor_de_contrato` | Alta durante as Tasks 2 e 7 | Rodar esse arquivo inteiro ao fim de **cada** uma das Tasks 2, 7 e 8, não só no fecho |
| **Obra sem baseline** criada por caminho que o plano não cobriu (importador físico-financeiro, seed, script) | Média | `contrato_vigente()` devolve `None` sem quebrar; a UI trata; e a Task 5 cria o baseline na primeira edição. Teste de invariante na Task 1 detecta o buraco cedo |

---

## 10. Critérios de pronto

A fase está pronta quando **todos** forem verdade, cada um com teste:

1. Aprovar um aditivo de R$ 100.000 → R$ 120.000 numa obra existente deixa: **1** `ItemMedicaoComercial` por linha de escopo (não 2), soma dos itens **= R$ 120.000** (não 220.000), `ObraServicoCusto` **não duplicado**, e receita contábil acumulada **= R$ 120.000** (não 220.000).
2. `MedicaoContrato` emitida antes do aditivo **não muda de valor** depois dele.
3. `Obra.valor_contrato` não é editável por formulário enquanto houver contrato vigente; toda mudança tem `AditivoContrato` com motivo, autor e data.
4. `contrato_vigente(obra.id, obra.admin_id).valor == Decimal(str(obra.valor_contrato))` para **toda** obra do banco, sempre — invariante testada.
5. Revisar uma proposta preserva `tipo_medicao_override` e os 5 campos `dim_*` (hoje perde os 6).
6. Toda linha de v2 sabe qual linha de v1 ela substitui (`item_origem_id`), e o comparador mostra mantido/alterado/incluído/suprimido com delta.
7. Orçamento convertido em proposta não pode mais ser editado; revisar cria uma revisão com FK de volta (hoje `duplicar` cria órfão).
8. Item suprimido por aditivo: tarefa de cronograma `ativa=False`, `ItemMedicaoComercial` `SUPRIMIDO`. **Zero `DELETE`** de tarefa ou de item de medição em todo o fluxo de aditivo.
9. Aditivo que reduza um item abaixo do já medido é recusado com mensagem clara.
10. `bash run_tests.sh --gate` verde, sem teste novo pulado por precondição de dado.

### O que esta fase deliberadamente NÃO entrega

- **PDF real da proposta.** A rota devolve HTML hoje (`propostas_consolidated.py:1165`) e continuará devolvendo. `reportlab` já está na stack e `services/medicao_service.py:389-470` é o modelo a copiar, mas isso é trabalho de apresentação e não pertence ao mesmo commit que o baseline de contrato. Fica registrado como pendência da Fase 8/9.
- **Modelo `Contrato` completo** (cláusulas, vigência, partes, alertas de vencimento) — é o módulo 4.10, Fase 9. Aqui só existe o **valor** contratado e sua história. `ObraContratoVersao` foi nomeada assim, e não `Contrato`, exatamente para não colidir com essa fase.
- **Alçada de aprovação por valor.** Depende do valor de X (pergunta 3 da DEVOLUTIVA), que não foi respondida. `AditivoContrato` já tem os campos para acomodá-la sem migration nova.
- **SINAPI** e **sugestão de preço a partir de cotações** — itens 4.4 da DEVOLUTIVA que não têm relação com versionamento.
