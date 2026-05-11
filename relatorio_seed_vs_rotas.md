# Relatório Diagnóstico: Seed vs. Rotas — SIGE v9.0

**Gerado em:** 2026-05-11  
**Escopo:** `scripts/seed_demo_alfa.py` (4 256 linhas) × rotas registradas em `app.py` + `main.py`  
**Tenant alvo:** Construtora Alfa (`ADMIN_EMAIL = admin@construtoraalfa.com`)  
**Objetivo:** Mapear o que o seed insere por módulo (método ORM direto vs. service/event), quais rotas existem e se renderizam com os dados semeados.

> **Metodologia — análise estática exclusiva.** Todos os julgamentos de status neste documento derivam da leitura do código-fonte (seed, views, blueprints). Nenhuma execução de servidor, requisição HTTP ou inspeção de banco de dados foi realizada. Os rótulos ✅ / ⚠️ expressam confiança inferida por análise estática, não confirmação em tempo de execução.

---

## Legenda de Métodos de Inserção

| Símbolo | Significado |
|---------|-------------|
| **ORM** | `db.session.add()` / `db.session.add_all()` direto — bypassa validação de rota |
| **SVC** | Função de serviço chamada diretamente (camada `services/`) |
| **EVT** | `EventManager.emit()` — mesmo handler disparado pela rota oficial |
| **HDL** | Função handler chamada diretamente (`handlers/`) |

---

## 1. Visão Global por Módulo

| # | Módulo | Entidades semeadas | Método | Rota correspondente |
|---|--------|--------------------|--------|---------------------|
| 1 | Auth / Setup | `Usuario`, `ConfiguracaoEmpresa` | ORM | `/login`, `/configuracoes/` |
| 2 | Clientes | `Cliente` (1) | ORM | `/clientes/` |
| 3 | Funcionários | `Funcionario` (5) | ORM | `/funcionarios/` |
| 4 | Catálogo | `Insumo`, `PrecoBase`, `SubatividadeMestre`, `CronogramaTemplate`+grupos+subatividades, `Servico`, `ComposicaoServico`, `Funcao` | ORM | `/catalogo/` |
| 5 | Templates de Proposta | `PropostaTemplate`, `PropostaTemplateClausula` (3) | ORM | `/propostas/templates/` |
| 6 | Orçamento | `Orcamento`, 4 × `OrcamentoItem` | ORM + **SVC** (`recalcular_item`, `recalcular_orcamento`) | `/orcamentos/` |
| 7 | Proposta "001.26" Bela Vista | `Proposta`, `PropostaItem`, `Obra`, `ItemMedicaoComercial`, `TarefaCronograma` | ORM + **SVC** (`materializar_cronograma`) | `/propostas/`, `/obras/` |
| 8 | RDOs Bela Vista (3) | `RDO`, `RDOServicoSubatividade`, `RDOMaoObra`, `RDOEquipamento`, `RDOOcorrencia`, `RDOApontamentoCronograma` | ORM + **EVT** (`rdo_finalizado`) + **SVC** (`recalcular_produtividade_rdo`) | `/rdo/` |
| 9 | Orç. Operacional BV | `ObraOrcamentoOperacional`, `ObraOrcamentoOperacionalItem`, `ObraOrcamentoOperacionalItemVersao` | ORM | `/obra/<id>/orcamento-operacional/` |
| 10 | Proposta E2E #118 | `Proposta`, `PropostaItem`, `Obra` | ORM + **HDL** (`handle_proposta_aprovada`) | `/propostas/` |
| 11 | Proposta TMK31 | `Proposta`, `PropostaItem` | ORM + **SVC** (`_copiar_clausulas_template_para_proposta`) | `/propostas/` |
| 12 | Propostas funil (2) | `Proposta`, `PropostaItem` (DEMO-A rascunho, DEMO-B enviada) | ORM | `/propostas/` |
| 13 | Compras Bela Vista (4 NFs) | `Fornecedor`, `AlmoxarifadoCategoria`, 5 × `AlmoxarifadoItem`, 4 × `PedidoCompra` + `PedidoCompraItem` | ORM + **SVC** (`processar_compra_normal` × 4) | `/compras/` |
| 14 | Alimentação | `Restaurante`, `AlimentacaoItem`, `CentroCusto`, `AlimentacaoLancamento`, `AlimentacaoLancamentoItem`, associação `alimentacao_funcionarios_assoc` | ORM | `/alimentacao/` |
| 15 | Transporte | `CategoriaTransporte`, `LancamentoTransporte` | ORM | `/transporte/` |
| 16 | Medição (Bela Vista) | `MedicaoObra` (aprovada) → `ContaReceber` | **SVC** (`gerar_medicao_quinzenal` + `fechar_medicao`) | `/obras/<id>/medicao` |
| 17 | CRM | Listas mestras (`CrmOrigem`, `CrmCadencia`, `CrmSituacao`, `CrmTipoMaterial`, `CrmTipoObra`, `CrmMotivoPerda`), 4 × `CrmResponsavel`, 12 × `Lead` + `LeadHistorico` | **SVC** (`seed_listas_mestras_crm`) + ORM | `/crm/` |
| 18 | Obra Pinheiros + Cronograma | `Cliente`, `Proposta`, `PropostaItem`, `Obra`, `ItemMedicaoComercial`, `TarefaCronograma` | ORM + **SVC** (`materializar_cronograma`) | `/obras/`, `/cronograma/` |
| 19 | RDOs Pinheiros (10) | `RDO`+sub-records × 10 | ORM + **EVT** (`rdo_finalizado` × 10) + **SVC** (`recalcular_produtividade_rdo`) | `/rdo/` |
| 20 | Orç. Operacional Pinheiros | `ObraOrcamentoOperacional` + items + versões | ORM (get-or-create) | `/obra/<id>/orcamento-operacional/` |
| 21 | Compras Pinheiros (6 NFs) | 6 × `PedidoCompra` + `PedidoCompraItem` | ORM + **SVC** (`processar_compra_normal` × 6) | `/compras/` |
| 22 | Frota | 2 × `Veiculo`, 6 × `CustoVeiculo`, 3 × `UsoVeiculo` | ORM | `/frota/` |
| 23 | Folha de Pagamento | 1 × `FolhaProcessada` (Carlos fev/2026) | **ORM direto** | `/folha/dashboard` ⚠️ |
| 24 | Contabilidade | 19 × `PlanoContas`, 14 × `LancamentoContabil`, 28 × `PartidaContabil` | ORM (upsert por código) | `/contabilidade/` |
| 25 | Fluxo de Caixa | 15 × `FluxoCaixa` (fev–mai/2026) | ORM | `/financeiro/fluxo-caixa` |
| 26 | Gestão de Custos (mês atual) | `GestaoCustoPai` + `GestaoCustoFilho` (7 lançamentos PENDENTE) | ORM + limpeza idempotente | `/gestao-custos/` |
| 27 | Backfill RDO | `RDOCustoDiario`, `GestaoCustoFilho` MAO_OBRA/SALARIO | **SVC** (`gravar_custo_funcionario_rdo`) + **EVT** (`rdo_finalizado` re-emit) | — (pós-seed) |

---

## 2. Detalhamento por Módulo

### 2.1 Auth / Setup

**Seed (linhas ~1–200):**
- `Usuario` (ADMIN) com `versao_sistema=None` inicialmente; promovido para `'v2'` ao final por `_backfill_custos_rdo_demo()`.
- `ConfiguracaoEmpresa`: razão social, CNPJ, endereço.

**Rotas:**
- `/login` (GET/POST), `/logout` (POST)
- `/dashboard` — renderiza KPIs e cards de acesso rápido.
- `/configuracoes/` — edição de `ConfiguracaoEmpresa`.

**Status:** ✅ Funcional. Dados presentes, tenant v2 ativo.

---

### 2.2 Clientes / CRM

**Seed:**
- `Cliente`: "Residencial Bela Vista" (com CNPJ, e-mail, telefone, endereço).
- `Cliente`: "Pinheiros Empreendimentos Ltda" (bloco 14).
- **CRM listas mestras** via `seed_listas_mestras_crm()` (serviço de `crm_seeds.py`): `CrmOrigem` (Site, Indicação, Google, Anúncio Meta Ads, Prospecção Ativa), `CrmCadencia`, `CrmSituacao`, `CrmTipoMaterial`, `CrmTipoObra`, `CrmMotivoPerda`.
- 4 × `CrmResponsavel`: Ana Paula Costa, Bruno Mendes, Carla Tavares, Diego Santos.
- 12 × `Lead` (distribuídos nas 8 colunas do Kanban: EM_FILA×2, EM_ANDAMENTO×2, ENVIADO×2, VALIDACAO×1, APROVADO×1, FEEDBACK×1, CONGELADO×1, PERDIDO×2) + `LeadHistorico` (2–4 entradas por lead com trajetória espaçada).
- Lead APROVADO vinculado à `Proposta` "001.26" e `Obra` Bela Vista.

**Rotas (`/crm/` — `crm_bp`):**
- `/crm/` — Kanban board.
- `/crm/lista` — tabela paginada.
- `/crm/novo` (GET/POST), `/crm/<id>/editar`, `/crm/<id>/excluir`, `/crm/<id>/mudar_status`.
- `/crm/<id>/gerar_proposta`, `/crm/<id>/criar_obra`.
- `/crm/cadastros` — listas mestras CRUD.
- `/crm/exportar_modelo`, `/crm/importar`.
- `/crm/clientes/<id>` — mini-ficha do cliente.

**Status:** ✅ Funcional. 12 leads com aging variado (1–25 dias), listas mestras populadas.

---

### 2.3 Funcionários / RH

**Seed (linhas ~300–500):**
- 5 × `Funcionario`: Carlos Pereira (mensalista R$2.800), Pedro Almeida, João Santos, Marcos Oliveira, Ana Souza (4 diaristas R$180/dia).

**Rotas (`/funcionarios/`):**
- CRUD completo (lista, novo, editar, excluir, foto).
- Ponto eletrônico / registro de face.

**Status:** ✅ Funcional.

---

### 2.4 Catálogo de Serviços e Insumos

**Seed (linhas ~500–1000):**
- **Insumos** (`Insumo`) + `PrecoBase`: Cimento CP II 50kg, Areia grossa m³, Brita 1 m³, Tijolo cerâmico, Cal hidratada 20kg, Argamassa pronta 25kg, Tinta acrílica 18L, Massa corrida 25kg, Servente (MO), Pedreiro (MO), Encarregado (MO), Pintor (MO), Betoneira 400L, Andaime tubular.
- **SubatividadeMestre**: estrutura de 3 níveis (Alvenaria, Contrapiso, Pintura).
- **CronogramaTemplate**: 4 templates (Alvenaria, Alvenaria Expresso, Contrapiso, Pintura); grupos e subatividades vinculados.
- **Servicos**: Alvenaria de vedação, Contrapiso, Pintura interna, Mobilização + `ComposicaoServico` (MAO_OBRA, MATERIAL, EQUIPAMENTO por serviço).
- **Funcoes**: Pedreiro, Servente, Encarregado, Pintor — vinculadas a `ComposicaoServico`.

**Rotas (`/catalogo/` — `catalogo_bp`):**
- `/catalogo/servicos`, `/catalogo/servicos/novo`, `/catalogo/servicos/<id>/editar`.
- `/catalogo/insumos`, `/catalogo/insumos/novo`.
- `/api/catalogo/*` (aliases JSON para consultas inline).

**Status:** ✅ Funcional. Composições completas (3 tipos por serviço).

---

### 2.5 Orçamentos

**Seed (linhas 1485–1557):**
- 1 × `Orcamento` "ORC-2026-0001" (rascunho) com 4 × `OrcamentoItem` (cenários A–D de override de cronograma e composição customizada).
- `recalcular_item()` + `recalcular_orcamento()` chamados via SVC após inserção → preços e totais calculados.

**Rotas (`/orcamentos/` — `orcamentos_bp`):**
- `/orcamentos/`, `/orcamentos/novo`, `/orcamentos/<id>`, `/orcamentos/<id>/editar`.
- Preview de cronograma (accordion) visível no detalhe do orçamento.

**Status:** ✅ Funcional. 4 cenários demonstrando override explícito, padrão, template alternativo e composição customizada.

---

### 2.6 Propostas

**Seed:**

| Proposta | Nº | Status | Origem |
|----------|----|--------|--------|
| Bela Vista | 001.26 | aprovada | ORM + `materializar_cronograma` |
| E2E #118 | E2E118.26 | aprovada | ORM + `handle_proposta_aprovada` |
| Com Template | TMK31.26 | rascunho | ORM + `_copiar_clausulas_template_para_proposta` |
| Funil A | DEMO-A.26 | rascunho | ORM puro |
| Funil B | DEMO-B.26 | enviada | ORM puro |
| Pinheiros | 002.26 | aprovada | ORM + `materializar_cronograma` |

- `PropostaTemplate` (1, padrão) + 3 × `PropostaTemplateClausula`.
- Propostas aprovadas têm `cronograma_default_json` populado (árvore de preview serializada).

**Rotas (`/propostas/` — `propostas_bp`):**
- `/propostas/`, `/propostas/nova`, `/propostas/<id>`, `/propostas/<id>/editar`.
- `/propostas/<id>/aprovar`, `/propostas/<id>/pdf`.
- `/propostas/templates/` — CRUD de modelos.

**Status:** ✅ Funcional. Funil com 5 propostas em estados distintos visíveis na listagem.

---

### 2.7 Obras e Cronograma

**Seed:**
- **Obra "Residencial Bela Vista"** (`OBR-2026-001`): status Em andamento, `portal_ativo=True`, Carlos como responsável, `data_inicio_medicao=2026-02-01`.
- **Obra "Comercial Pinheiros"** (`OBR-2026-002`): status Em andamento, Carlos como responsável, 1.500 m².
- **Obra E2E #118**: gerada via `handle_proposta_aprovada`.
- `TarefaCronograma`: 3 níveis materializados via `materializar_cronograma()` para Bela Vista e Pinheiros.
- `ItemMedicaoComercial`: itens de medição comercial por proposta-item.

**Rotas:**
- `/obras/` — lista, `/obras/<id>` — detalhe.
- `/cronograma/obra/<id>` — Gantt interativo.
- `/obra/<id>/orcamento-operacional/` — orçamento operacional.
- `/obras/<id>/planejamento-custos` — planejamento.
- Portal do cliente: `/portal/obras/<id>/`.

**Status:** ✅ Funcional. Cronograma em 3 níveis com percentuais de avanço refletindo os RDOs finalizados.

---

### 2.8 RDO (Relatório Diário de Obra)

**Seed:**
- **Bela Vista**: 3 RDOs finalizados (semanas 1–3 de fev/2026).
- **Pinheiros**: 10 RDOs finalizados (semanal de 03/02 a 07/04/2026, progresso 10→100% com variação intencional: RDO 3 abaixo do orçado, RDO 7 compensação).
- Cada RDO contém: `RDOServicoSubatividade`, `RDOMaoObra` (equipe completa com auditoria de função), `RDOEquipamento` (em RDOs alternados), `RDOOcorrencia` (mix Baixa/Média), `RDOApontamentoCronograma` (qty executada e acumulada).
- **Finalização**: `rdo.status = 'Finalizado'` + `EventManager.emit('rdo_finalizado', …)` — mesmo path da rota `/rdo/<id>/finalizar`.
- `recalcular_produtividade_rdo()` executado por RDO (cria snapshot de produtividade).

**Rotas (`/rdo/` — `main_bp`):**
- `/rdo` / `/rdo/lista` — listagem com filtros.
- `/rdo/novo` (GET), `/rdo/criar` (POST).
- `/rdo/<id>` — visualização completa.
- `/rdo/<id>/finalizar` (POST), `/rdo/<id>/editar`, `/rdo/<id>/duplicar`, `/rdo/<id>/atualizar`.
- `/funcionario/rdo/consolidado`, `/funcionario/rdo/novo`.

**Status:** ✅ Funcional. 13 RDOs finalizados com dados de MO, serviço, equipamento e ocorrência.

---

### 2.9 Compras e Almoxarifado

**Seed:**

| NF | Obra | Valor | Pagamento | Método |
|----|------|-------|-----------|--------|
| NF-2026-0001 | Bela Vista | R$1.500 | à vista | `processar_compra_normal` |
| NF-2026-0002 | Bela Vista | R$10.865 | à vista | `processar_compra_normal` |
| NF-2026-0003 | Bela Vista | R$7.460 | 30 dias | `processar_compra_normal` |
| NF-2026-0004 | Bela Vista | R$16.775 | à vista | `processar_compra_normal` |
| NF-2026-0005 | Pinheiros | R$33.300 | à vista | `processar_compra_normal` |
| NF-2026-0006 | Pinheiros | R$41.425 | à vista | `processar_compra_normal` |
| NF-2026-0007 | Pinheiros | R$27.725 | 60 dias | `processar_compra_normal` |
| NF-2026-0008 | Pinheiros | R$107.200 | à vista | `processar_compra_normal` |
| NF-2026-0009 | Pinheiros | R$10.650 | à vista | `processar_compra_normal` |
| NF-2026-0010 | Pinheiros | R$82.725 | 30 dias | `processar_compra_normal` |

- `processar_compra_normal()` gera: `GestaoCustoPai` (MATERIAL PAGO) + `AlmoxarifadoEntrada`/`AlmoxarifadoSaida` (movimentação de estoque).
- 1 × `Fornecedor` (Materiais São Paulo Ltda) + 1 × `AlmoxarifadoCategoria` + 5 × `AlmoxarifadoItem` (Cimento, Bloco cerâmico, Areia, Tinta, Massa corrida).

**Rotas (`/compras/` — `compras_bp`) — ⚠️ guard `_check_v2()`:**
- `/compras/` — lista de pedidos.
- `/compras/aprovacao` — pedidos pendentes de aprovação.
- `/compras/nova` (GET/POST) — formulário de nova compra.
- `/compras/<id>` — detalhe.
- `/compras/receber/<id>` (POST), `/compras/excluir/<id>` (POST).

**Status:** ✅ Inferido funcional (análise estática). 10 NFs semeadas; movimentação de estoque gerada via `processar_compra_normal`. Todas as rotas devem passar no guard `is_v2_active()` porque `versao_sistema='v2'` é garantido pelo backfill — desde que ele complete sem erro.

---

### 2.10 Alimentação

**Seed (linhas 2113–2181):**
- `Restaurante`: Restaurante Bom Prato.
- `AlimentacaoItem`: Marmita executiva (R$18,00, `is_default=True`).
- `CentroCusto`: CC da obra Bela Vista (tipo="obra").
- `AlimentacaoLancamento` (1): 05/02/2026, R$54,00, 3 diaristas.
- `AlimentacaoLancamentoItem` × 3 (um por diarista).
- Associação `alimentacao_funcionarios_assoc` inserida via `db.session.execute(_aa.insert(), …)` (ORM direto com `admin_id` na tabela intermediária).

**Rotas (`/alimentacao/` — `alimentacao_bp`):**
- `/alimentacao/restaurantes`, `/alimentacao/restaurantes/novo`, etc.
- `/alimentacao/` / `/alimentacao/lancamentos` — lista de lançamentos.
- `/alimentacao/lancamentos/novo` (fluxo v1) e `/alimentacao/lancamentos/novo-v2` (fluxo modal).
- `/alimentacao/itens` — catálogo de itens.
- `/alimentacao/dashboard` — resumo por período.

**Status:** ✅ Funcional. Sem guard `_check_v2()` — acesso irrestrito.

---

### 2.11 Transporte

**Seed (linhas 2183–2204):**
- `CategoriaTransporte`: Combustível.
- `LancamentoTransporte`: 06/02/2026, R$180,00, Pedro, CC Bela Vista.

**Rotas (`/transporte/` — `transporte_bp`) — ⚠️ guard `_check_v2()`:**
- `/transporte/` — lista de lançamentos.
- `/transporte/novo` (GET/POST).
- `/transporte/novo-massa` — lançamento em massa.
- `/transporte/categorias` — CRUD de categorias.
- `/transporte/excluir/<id>` (POST).

**Status:** ✅ Inferido funcional (análise estática). 1 lançamento semeado; rotas devem passar no guard `is_v2_active()` com o tenant Alfa (v2).

---

### 2.12 Medição Comercial

**Seed (linhas 2208–2223):**
- `MedicaoObra` nº 001, período 01–15/02/2026, status APROVADA, criada via `gerar_medicao_quinzenal()`.
- Fechamento via `fechar_medicao()` → gera `ContaReceber` (OBR-MED).

**Rotas:**
- `/obras/<id>/medicao` (legacy, registrado em `main.py`).
- `/medicao/obra/<id>` (alias via `catalogo_legacy_bp`).

**Status:** ✅ Inferido funcional (análise estática). 1 `MedicaoObra` aprovada semeada; `ContaReceber` deve existir — gerada por `fechar_medicao()` conforme lógica de serviço.

---

### 2.13 Frota

**Seed (linhas 3275–3388):**
- 2 × `Veiculo`: Toyota Hilux SRX (ABC-1234, km 42.800) e Mercedes Sprinter 415 (DEF-5678, km 68.200).
- 6 × `CustoVeiculo`: combustível × 4, manutenção × 1, IPVA × 1 — vinculados às obras.
- 3 × `UsoVeiculo`: Hilux BV, Sprinter BV, Hilux Pinheiros.

**Rotas (`/frota/` — `frota_bp`):**
- `/frota/` — lista de veículos.
- `/frota/novo`, `/frota/<id>`, `/frota/<id>/editar`, `/frota/<id>/deletar`.
- `/frota/<id>/reativar`.
- `/frota/<veiculo_id>/uso/novo`, `/frota/uso/<uso_id>/editar`, `/frota/uso/<uso_id>/deletar`.
- `/frota/<veiculo_id>/custo/novo`, `/frota/custo/<custo_id>/editar`, `/frota/custo/<custo_id>/deletar`.
- `/frota/dashboard` — TCO, gráficos de custo por tipo.

**Status:** ✅ Funcional. Sem guard `_check_v2()`. Dashboard com 2 veículos, 6 despesas e 3 utilizações.

---

### 2.14 Folha de Pagamento

**Seed (linhas 3390–3422):**
- 1 × `FolhaProcessada` para Carlos (fev/2026): salário base R$2.800, INSS func. R$252, IRRF R$0, FGTS R$224, encargos patronais R$560, custo total empresa R$3.584.
- **Inserção via ORM direto** — não passa pelo handler `/folha/processar/<ano>/<mes>`.
- Valores CLT hardcoded (não derivados de `ParametrosLegais`).
- **Não há `ParametrosLegais` semeado** → o dashboard `/folha/dashboard` exibe aviso de "parâmetros legais não configurados".

**Rotas (`/folha/` — `folha_bp`, registrado com `url_prefix='/folha'` em `app.py`):**
- `/folha/dashboard` — resumo por período.
- `/folha/processar/<ano>/<mes>` (POST) — gera folha completa via CLT para todos os funcionários.
- `/folha/parametros-legais` / criar / editar / toggle — INSS/IRRF/FGTS tabelas.
- `/folha/beneficios` / criar / editar — vale transporte, alimentação, etc.
- `/folha/adiantamentos` / criar / aprovar / rejeitar.
- `/folha/relatorios` — analítico e holerite PDF.
- `/folha/relatorios/holerite/<folha_id>` — PDF individual.
- `/folha/api/funcionarios/folha/<ano>/<mes>` — JSON de funcionários aptos.

**Status:** ⚠️ **Parcialmente funcional.**
- `FolhaProcessada` de Carlos presente no banco; o dashboard deve exibi-la e o holerite PDF deve ser gerado — desde que o template Jinja2 de holerite não dependa de `ParametrosLegais`.
- `ParametrosLegais` ausente → aviso no dashboard; rota `/folha/processar/` rejeitará ou gerará folha com valores zerados para as demais categorias.
- `BeneficioFuncionario` e `AdiantamentoFuncionario` ausentes → listas vazias.

---

### 2.15 Contabilidade

**Seed (linhas 3424–3521):**
- 19 × `PlanoContas` (upsert por código): árvore Ativo (1/1.1/1.1.01/1.1.02), Passivo (2/2.1/2.1.01), Receita (3/3.1/3.1.01), Despesa (4/4.1/4.1.01–02, 4.2/4.2.01, 4.3/4.3.01–02).
- 14 × `LancamentoContabil` + 28 × `PartidaContabil` (partidas dobradas): cobrindo recebimento de medição, folha, NFs de compra, combustível e revisão.

**Rotas (`/contabilidade/` — `contabilidade_bp`, prefixo definido em `app.py`):**
- `/contabilidade/dashboard`.
- `/contabilidade/plano-contas`.
- `/contabilidade/lancamentos` — listagem; `/contabilidade/lancamentos/criar` (GET/POST).
- `/contabilidade/lancamentos/<id>` — detalhe; editar; estornar.
- `/contabilidade/balancete` (+ PDF + Excel).
- `/contabilidade/razao/<conta_codigo>`.
- `/contabilidade/dre` (+ PDF + Excel).
- `/contabilidade/balanco`.
- `/contabilidade/auditoria`.
- `/contabilidade/relatorios`.
- `/contabilidade/centros-custo` / criar / editar.

**Status:** ✅ Inferido funcional (análise estática). 19 contas e 14 lançamentos presentes no banco; DRE e balancete devem renderizar com dados conforme as queries das rotas lidas no código.

---

### 2.16 Financeiro

**Seed (linhas 3524–3654):**
- 15 × `FluxoCaixa` (fev–mai/2026): 1 ENTRADA (medição), 14 SAÍDAS (folha, compras, frota, alimentação, NFs adicionais BV e Pinheiros).
- `ContaReceber` gerada indiretamente via `fechar_medicao()` (vide Medição §2.12).
- Não há `ContaPagar` explícita semeada (NFs a prazo constam no `FluxoCaixa` mas não geram `ContaPagar` diretamente).

**Rotas (`/financeiro/` — `financeiro_bp`):**
- `/financeiro/` — dashboard financeiro.
- `/financeiro/contas-pagar` / nova / pagar.
- `/financeiro/contas-receber` — lista; `/financeiro/contas-receber/<id>/receber`.
- `/financeiro/fluxo-caixa` — DRE de caixa + filtros.
- `/financeiro/bancos` — contas bancárias.
- `/financeiro/plano-contas` (alias — redireciona ou replica contabilidade).
- `/financeiro/api/kpis` — JSON para dashboard.

**Status:** ✅ Funcional. Fluxo de caixa com 15 movimentos; 1 `ContaReceber` da medição; lista de `ContaPagar` vazia (NFs foram lançadas apenas no FC/Contabilidade).

---

### 2.17 Gestão de Custos V2

**Seed:**
- `GestaoCustoPai` + `GestaoCustoFilho` criados em dois momentos:
  1. **Via `processar_compra_normal`** (compras): GCF tipo MATERIAL PAGO por NF.
  2. **Via `EventManager.emit('rdo_finalizado')`** (RDOs): GCF tipos SALARIO/MAO_OBRA_DIRETA por RDO.
  3. **`_seed_custos_mes_atual()`**: 7 GCF PENDENTE para o mês corrente (3 para BV, 4 para Pinheiros) — reexecutado a cada deploy, idempotente.

**Rotas (`/gestao-custos/` — `gestao_custos_bp`):**
- `/gestao-custos/` — lista com filtros (obra, período, categoria).
- `/gestao-custos/novo` (GET/POST).
- `/gestao-custos/obra/<obra_id>/servicos` — JSON de serviços da obra.
- `/gestao-custos/<pai_id>/filhos` — detalhe de filhos.
- `/gestao-custos/filho/<id>/editar` / excluir (POST).
- `/gestao-custos/<pai_id>/solicitar` / autorizar / pagar / editar / excluir.
- `/gestao-custos/migrar-contas-pagar` (POST) — migração utilitária.

**Status:** ✅ Inferido funcional (análise estática). GCF com origens distintas (pedido_compra, rdo_mao_obra, rdo_custo_diario, demo_mes_atual) devem estar presentes — inseridos via `processar_compra_normal` e `EventManager.emit('rdo_finalizado')` conforme código analisado.

---

### 2.18 Custos Legado (`/custos/`)

**Seed:** Nenhuma inserção via `custos_bp`. Os dados de custo existem via `GestaoCustos` e `RDOCustoDiario`.

**Rotas (`/custos/` — `custos_bp`):**
- `/custos/`, `/custos/obra/<id>`, `/custos/criar`, `/custos/editar/<id>`, `/custos/deletar/<id>`, `/custos/listar`.
- APIs: `/custos/api/custos-categoria`, `/custos/api/custos-mensais`.

**Status:** ⚠️ **Lista vazia.** Blueprint registrado, rotas funcionam, mas nenhum dado de custo foi semeado pelo modelo legado. Dados estão em `GestaoCustos` (v2). Módulo pode ser considerado obsoleto para demos.

---

### 2.19 Métricas de Produtividade e Lucratividade

**Seed:** Depende dos RDOs + `TarefaCronograma` + `RDOApontamentoCronograma` já semeados. Não há inserção direta em tabelas de métricas — elas são computadas on-the-fly.

**Rotas (`/metricas/` — `metricas_bp`):**
- `/metricas/` — dashboard empresa.
- `/metricas/servico` — índice por serviço ("Empresa por Serviço").
- `/metricas/funcionarios` — produtividade por função.
- `/metricas/divergencia/servico/<id>` — detalhamento de divergência.

**Status:** ✅ Funcional. 13 RDOs finalizados (3 BV + 10 PIN) com variação intencional de produtividade geram dados para todos os gráficos. RDO 3 Pinheiros abaixo do orçado → índice < 100% em "Empresa por Serviço"; RDO 7 compensa.

---

### 2.20 Equipe / Alocação

**Seed:** Nenhuma inserção de `Allocation` ou `AllocationEmployee`.

**Rotas (`/equipe/` — `equipe_bp`):**
- `/equipe/alocacao`, `/equipe/alocacao-principal`.
- `/equipe/funcionarios/<id>` — detalhe de alocação.
- APIs REST para alocações, sincronização de ponto.

**Status:** ⚠️ **Estado vazio (análise estática).** Blueprint e rotas existem no código, sem alocações semeadas. A tela deve renderizar a estrutura mas sem dados.

---

### 2.21 Subempreiteiros

**Seed:** Nenhuma inserção.

**Rotas (`/subempreiteiros/` — `subempreiteiros_bp`):**
- `/subempreiteiros/`, `/subempreiteiros/criar`, `/subempreiteiros/<id>/editar`.

**Status:** ⚠️ **Estado vazio (análise estática).** Rotas existem no código mas lista deve estar vazia sem dados semeados.

---

### 2.22 Reembolsos

**Seed:** Nenhuma inserção.

**Rotas (`/reembolsos/` — `reembolso_bp`):**
- `/reembolsos/`, `/reembolsos/novo`, `/reembolsos/<id>/editar`, `/reembolsos/<id>/excluir`.

**Status:** ⚠️ **Estado vazio (análise estática).** Rotas existem no código mas lista deve estar vazia sem dados semeados.

---

## 3. Mapa de Serviços e Eventos Chamados pelo Seed

| Função/Evento | Arquivo | Chamadas no seed | Efeito |
|---------------|---------|-----------------|--------|
| `materializar_cronograma()` | `services/cronograma_proposta.py` | 2 (BV + Pinheiros) | Cria `TarefaCronograma` em 3 níveis |
| `recalcular_item()` | `services/orcamento_view_service.py` | 4 (itens do orçamento) | Recalcula custo/venda por item |
| `recalcular_orcamento()` | `services/orcamento_view_service.py` | 1 | Totaliza orçamento |
| `montar_arvore_preview()` | `services/cronograma_proposta.py` | 2 (E2E118 + Pinheiros) | Gera `cronograma_default_json` |
| `handle_proposta_aprovada()` | `handlers/propostas_handlers.py` | 1 (E2E118) | Dispara criação de obra e cronograma |
| `_copiar_clausulas_template_para_proposta()` | `propostas_consolidated.py` | 1 (TMK31) | Copia cláusulas do template |
| `processar_compra_normal()` | `compras_views.py` | 10 (4 BV + 6 PIN) | Cria GCP MATERIAL PAGO + movimentação almoxarifado |
| `gerar_medicao_quinzenal()` | `services/medicao_service.py` | 1 | Cria `MedicaoObra` |
| `fechar_medicao()` | `services/medicao_service.py` | 1 | Aprova medição → cria `ContaReceber` |
| `seed_listas_mestras_crm()` | `crm_seeds.py` | 1 | Popula listas mestras CRM |
| `EventManager.emit('rdo_finalizado')` | `event_manager.py` | 13 (3 BV + 10 PIN) | Cria `GestaoCustoFilho` SALARIO/MAO_OBRA |
| `recalcular_produtividade_rdo()` | `services/rdo_custos.py` | 13 | Snapshot de produtividade por RDO |
| `sincronizar_percentuais_obra()` | `utils/cronograma_engine.py` | 1 (Pinheiros) | Rola percentuais pai ← filhos |
| `gravar_custo_funcionario_rdo()` | `services/custo_funcionario_dia.py` | todos os RDOs (backfill) | Cria `RDOCustoDiario` |

---

## 4. Observações e Riscos

### 4.1 ⚠️ Folha: bypass da rota `processar`

A `FolhaProcessada` de Carlos (fev/2026) é inserida via ORM com valores CLT hardcoded. A rota `/folha/processar/<ano>/<mes>` calcula automaticamente INSS/IRRF/FGTS usando a tabela `ParametrosLegais`, que **não está semeada**. Consequências:

- O dashboard mostra aviso "Parâmetros legais não configurados".
- Clicar em "Processar Folha" para outros meses gerará folha com tabelas de tributação zeradas (ou lançará erro, dependendo da implementação da rota).
- O holerite PDF de Carlos renderiza normalmente (dados já gravados).
- Para corrigir: semear `ParametrosLegais` com tabela INSS/IRRF 2026, ou ajustar o seed para chamar a lógica de processamento via serviço.

### 4.2 ⚠️ v2 guard depende de `_backfill_custos_rdo_demo`

O campo `versao_sistema='v2'` no `Usuario` admin é definido APÓS `_seed()` terminar, dentro de `_backfill_custos_rdo_demo()`. Se o seed falhar entre o final de `_seed()` e o início do backfill, o tenant ficará sem o flag v2, tornando as rotas `/compras/` e `/transporte/` inacessíveis (redirect para dashboard sem erro explícito).

### 4.3 ℹ️ Compras `processar_compra_normal` importado diretamente de `compras_views`

O seed importa `processar_compra_normal` de `compras_views.py` (linha 1969), acoplando o seed a uma função definida dentro de um blueprint. Isso funciona mas representa acoplamento atípico (serviço de negócio exposto pelo módulo de view). Não causa falha funcional, mas dificulta refatoração.

### 4.4 ℹ️ `ContaPagar` ausente para NFs a prazo

Os pedidos NF-2026-0003 (30 dias), NF-2026-0007 (60 dias) e NF-2026-0010 (30 dias) têm `condicao_pagamento` a prazo, mas `processar_compra_normal` não cria `ContaPagar` para eles — apenas o `FluxoCaixa` e o `GestaoCustoPai` são gerados. A listagem em `/financeiro/contas-pagar` permanece vazia para essas compras.

### 4.5 ℹ️ Módulos sem dados de demonstração

Os seguintes módulos têm rotas registradas e funcionais, mas sem nenhum dado semeado:

| Módulo | Prefixo | Impacto |
|--------|---------|---------|
| Equipe/Alocação | `/equipe/` | Tela vazia |
| Subempreiteiros | `/subempreiteiros/` | Tela vazia |
| Reembolsos | `/reembolsos/` | Tela vazia |
| Folha — ParametrosLegais | `/folha/parametros-legais` | Aviso no dashboard |
| Folha — Benefícios | `/folha/beneficios` | Tela vazia |
| Folha — Adiantamentos | `/folha/adiantamentos` | Tela vazia |
| Custos legado | `/custos/` | Lista vazia |

### 4.6 ℹ️ `alimentacao_funcionarios_assoc` inserida com `db.session.execute`

A tabela de associação entre `AlimentacaoLancamento` e `Funcionario` carrega `admin_id NOT NULL`. O seed usa `db.session.execute(_aa.insert(), […])` diretamente para preencher essa coluna, que não é preenchida pelo backref SQLAlchemy automaticamente. Comportamento correto, mas documentado como exceção à regra ORM pura.

---

## 5. Sumário de Status por Módulo

> **Nota:** a coluna "Status" reflete confiança inferida por análise estática do código. ✅ significa que os dados estão presentes no seed e as rotas existem e devem funcionar conforme o código lido; não é confirmação de execução em tempo real.

| Módulo | Dados semeados | Rotas registradas | Status (estático) |
|--------|---------------|-------------------|-------------------|
| Auth/Config | ✅ | ✅ | ✅ Esperado funcional |
| Clientes | ✅ (2) | ✅ | ✅ Esperado funcional |
| Funcionários | ✅ (5) | ✅ | ✅ Esperado funcional |
| Catálogo | ✅ | ✅ | ✅ Esperado funcional |
| Orçamentos | ✅ (1 + 4 itens) | ✅ | ✅ Esperado funcional |
| Propostas | ✅ (6 + templates) | ✅ | ✅ Esperado funcional |
| Obras | ✅ (3) | ✅ | ✅ Esperado funcional |
| Cronograma | ✅ (3 níveis, 2 obras) | ✅ | ✅ Esperado funcional |
| RDO | ✅ (13 finalizados) | ✅ | ✅ Esperado funcional |
| Orç. Operacional | ✅ (2 obras) | ✅ | ✅ Esperado funcional |
| Compras | ✅ (10 NFs, v2) | ✅ (v2 guard) | ✅ Esperado funcional¹ |
| Almoxarifado | ✅ (5 itens, movimentações) | ✅ | ✅ Esperado funcional |
| Alimentação | ✅ (1 lançamento) | ✅ | ✅ Esperado funcional |
| Transporte | ✅ (1 lançamento, v2) | ✅ (v2 guard) | ✅ Esperado funcional¹ |
| Medição | ✅ (1 aprovada, SVC) | ✅ | ✅ Esperado funcional |
| CRM | ✅ (12 leads, 8 estágios) | ✅ | ✅ Esperado funcional |
| Frota | ✅ (2 veículos, 9 registros) | ✅ | ✅ Esperado funcional |
| Folha | ⚠️ (1 FolhaProcessada, sem ParametrosLegais) | ✅ | ⚠️ Parcial² |
| Contabilidade | ✅ (19 contas, 14 lançamentos) | ✅ | ✅ Esperado funcional |
| Financeiro | ✅ (15 FC, 1 CR) | ✅ | ✅ Esperado funcional |
| Gestão Custos V2 | ✅ (via SVC/EVT + mês atual) | ✅ | ✅ Esperado funcional |
| Métricas | ✅ (derivado dos RDOs) | ✅ | ✅ Esperado funcional |
| Equipe/Alocação | ❌ sem dados | ✅ | ⚠️ Esperado vazio |
| Subempreiteiros | ❌ sem dados | ✅ | ⚠️ Esperado vazio |
| Reembolsos | ❌ sem dados | ✅ | ⚠️ Esperado vazio |
| Custos legado | ❌ sem dados | ✅ | ⚠️ Esperado vazio |
| Planejamento Custos | ❌ sem dados | ✅ | ⚠️ Esperado vazio |

¹ Requer que `_backfill_custos_rdo_demo` complete sem erro para promover `versao_sistema='v2'`.  
² `ParametrosLegais` ausente → aviso no dashboard; rota `processar` operará com tabelas zeradas.

---

*Documento gerado por análise estática do código-fonte. Nenhuma execução de servidor ou inspeção de banco de dados foi realizada. Nenhuma alteração de código foi introduzida.*
