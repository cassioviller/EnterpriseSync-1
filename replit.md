### Overview
SIGE v9.0 (Sistema de Gestão Empresarial) is a multi-tenant business management system for SMBs, designed to automate and streamline critical operations. It provides end-to-end oversight from sales to project execution, covering commercial proposal generation, employee and payroll management, construction project control (Daily Work Reports - RDO), and comprehensive financial calculations. The system's main purpose is to enhance operational efficiency and improve overall business management for small and medium-sized businesses.

### User Preferences
- Priorizar soluções automáticas que funcionem no deploy
- Evitar intervenção manual no banco de produção
- Implementar logs detalhados para debugging
- Sistema deve ser resiliente a diferenças entre ambientes
- Interface moderna com cards elegantes em vez de listas simples
- Design limpo e profissional com gradientes e animações suaves
- Template unificado em todas as páginas do sistema
- Contraste adequado de texto (valores em preto) para melhor legibilidade
- Proteção robusta contra erros de transação de banco de dados
- Scripts automatizados para deploy de correções críticas em produção
- Código de produção limpo, separado de testes para performance otimizada
- Testes dedicados estruturados para validação contínua dos módulos consolidados
- Links RDO devem apontar para rota moderna `/funcionario/rdo/consolidado` com funcionalidades completas
- Ambiente de produção com 80 tabelas deve ser preservado durante migrações
- Operações destrutivas (exclusão) devem usar POST via formulários JavaScript
- Evitar auto-fill de campos que possam interferir em filtros de busca

### System Architecture
The system uses a Flask backend with SQLAlchemy ORM, a PostgreSQL database, and Jinja2 for server-side templating. Bootstrap handles frontend styling, and Docker is used for deployment. The codebase is organized with a `views/` Python package for domain-specific modules, all utilizing a unified `base_completo.html` template.

**Key Architectural Decisions & Features:**
-   **Multi-tenancy and Security:** Includes data isolation, role-based access control, CSRF protection, restricted CORS, rate limiting, and secure key handling.
-   **Event-Driven Architecture:** Utilizes an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Emphasizes modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, featuring cards, gradients, and animations.
-   **Data Integrity & Management:** Supports automated database migrations, atomic transactions via `safe_db_operation`, and automated error diagnostics for SQLAlchemy.
-   **Dynamic Content Generation:** Enables dynamic PDF generation with custom headers and company-specific branding (logos, color schemes).
-   **Core Modules:**
    -   **Commercial Management:** Manages proposals with templates, automated calculations, real-time recalculation, client portal access, service catalog, and parametric budgeting.
    -   **Employee & Payroll Management:** Handles employee registration, automated time clocking (GPS, facial recognition, geofencing), flexible schedules, CLT-compliant payroll, dynamic PDF payslip generation, and accounting integration.
    -   **Construction Project Management:** Provides Daily Work Reports (RDO) with dynamic service progress, consolidated routing, mobile photo uploads, and integration with Cronograma V2. Features biweekly project measurement and intelligent hour normalization for employees across multiple activities within an RDO.
    -   **Financial & Accounting:** Implements double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, DRE, and enhanced cash flow management.
    -   **Logistics & Inventory:** Offers warehouse management with traceability, full CRUD for suppliers, material flow, batch/lot selection, serialized item transitions, optimistic locking, and automated cost registration for material purchases.
    -   **Fleet Management:** Manages vehicles, tracks expenses, provides TCO dashboards, and issues critical alerts.
    -   **Food Management:** Mobile-first interface for restaurant and food entries with dynamic multi-item launching and automatic cost calculation.
    -   **Client Portal:** Token-based access for clients to view project progress, approve purchases, and upload payment receipts, built on a shared layout with dynamic theming.
    -   **Competitive Bidding:** Multi-supplier comparison tool with an N items × N suppliers grid, inline editing, and interactive client selection.
    -   **Automated Project Scheduling (Cronograma V2):** MS-Project-style Gantt chart with task hierarchy and drag-and-drop, allowing automatic schedule creation from service templates.
    -   **Configurable Proposal Clauses:** Dynamic management of clauses per proposal and template.
    -   **Responsible Engineer Management:** Dedicated model supporting per-proposal overrides and fallback mechanisms.
    -   **Project-Client Linking:** Uses `Obra.cliente_id` FK for improved data integrity, with fallback for legacy data.
    -   **Employee Metrics:** Unified service for calculating employee KPIs and costs.
    -   **Configurable Theme System:** Per-tenant visual themes customizable via presets or custom color adjustments.
    -   **Resilient Client Approval Flow:** Robustness fixes for proposal approval, including handling null subjects and creating synthetic client records.
    -   **Searchable Supplier Dropdown:** Implemented Select2 for supplier and project search with multi-tenant validation.
    -   **Single Proposta Model:** Consolidated proposal data into a single model, replacing several legacy tables.
    -   **Initial Schedule Review on Obra:** Implemented a two-state visit gate for new `Obra` instances requiring administrative schedule review.
    -   **Operational Budget per Obra (Task #63):** Each `Obra` keeps an editable copy of its source `Orcamento` (1:1 via `ObraOrcamentoOperacional`) with per-item temporal versioning (`vigente_de`/`vigente_ate` + `modo_aplicacao`). Auto-clone fires on the 1st RDO via SQLAlchemy `after_insert` listener (deferred via `Timer` thread to escape the after-commit session state). Edits support `a_partir_de_hoje` (closes current window + opens new) and `retroativo` (in-place + audit row). Service exposes `garantir_operacional`, `obter_operacional_vigente(data_referencia)`, `editar_item`, `diff_com_original`, `atualizar_do_original` (only diffed items), `listar_versoes`. UI at `/obra/<id>/orcamento-operacional/` with tabs Itens/Histórico/Atualizar do original. Commercial `editar.html` shows a banner when sibling obras already have a separate operational budget so users know commercial edits no longer affect those obras.
    -   **Expandable Service Composition:** Services in budgets/proposals render as collapsible Bootstrap cards, displaying detailed cost breakdowns and included/excluded items.
    -   **Catalog Import via Excel:** Functionality to import and export catalog data for inputs and schedule templates using Excel files, with multi-tenant scoping and validation.
    -   **RDO Task Weighting:** Allows employees to assign weights to principal tasks within an RDO, influencing hour distribution when multiple activities are recorded.
    -   **Cronograma↔Subatividade↔Serviço↔MO Linkage (Task #62):** Adds clean linkage between schedule tasks, subactivities, services, and labor composition. New `Funcao.insumo_id` (Funcao→Insumo MAO_OBRA equivalence), `SubatividadeMaoObra` N:N junction (SubatividadeMestre × ComposicaoServico), `SubatividadeMestre.criada_via_cronograma`/`precisa_revisao` flags, `TarefaCronograma.servico_id` (required for new tasks; nullable in DB for legacy), `RDOMaoObra.composicao_servico_id`+`vinculo_status` columns. A SQLAlchemy `before_flush` listener auto-fills `composicao_servico_id`/`vinculo_status` for every new RDOMaoObra row across all save paths (V1/V2/edit/duplicate); `vinculo_status='manual'` is preserved. Cronograma POST validates `servico_id` and auto-creates SubatividadeMestre by name (case-insensitive trim). Catálogo edit page lets gestor mark which composições belong to each subatividade; values flow into the auto-link as a filter. New `vinculos_audit_bp` blueprint exposes `/vinculos/auditoria` with 4 tabs (subactivities pending review, tasks without service, RDO labor with problematic vinculo_status, functions without insumo). Migration 150 adds all schema and backfills `tarefa_cronograma.servico_id` by name.
    -   **CRM Leads - Kanban + Master Lists:** New CRM module with Kanban view, lead management, and configurable master lists for CRM entities like responsibles, origins, cadences, situations, material types, and project types. Features lead status tracking, historical logging, and controlled transitions (e.g., preventing 'Lost' status without a reason).
    -   **Unified Visual Design — CRM + Métricas (Task #15):** All 4 CRM screens (kanban, lista, lead_form, cadastros) and all 5 Métricas screens (funcionarios, empresa_servico, detalhe_funcionario, ranking, divergencia_servico) now extend the single light theme `base_completo.html`. The 5 Métricas screens were migrated off the legacy dark `base.html`. A shared partials file `templates/_partials/macros.html` provides 7 reusable Jinja macros (`page_header`, `filter_card`, `data_table_card`, `status_badge`, `kpi_card`, `empty_state`, `back_link`); paired styles live under the `.sige-*` namespace at the bottom of `static/css/styles.css`. The `status_badge` macro normalizes the 8 CRM funnel stages (Em fila / Em andamento / Enviado / Validação / Aprovado / Feedback / Congelado / Perdido) to consistent colored pills across kanban and list views. The Ranking screen got a podium for the top 3 above the full ranking table. Existing routes, business rules, permissions, AJAX endpoints (kanban drag-and-drop, status change, motivo-perda modal, exportar CSV, aplicar referência), and data shapes were preserved unchanged.
    -   **Proposta Sent Notification (Task #44):** When admin sends a proposal, the system emits the `proposta.enviada` event for n8n webhook delivery (e-mail to client) and renders a green WhatsApp button on the proposal detail page (pre-filled message + portal link, BR DDI normalization). Missing e-mail and/or phone produce non-blocking `flash` warnings; both the dispatch and the manual WhatsApp click are recorded in `PropostaHistorico` (`notificacao_disparada`, `whatsapp_aberto`).
    -   **Demo Refresh Gate (Task #59):** EasyPanel deploys auto-run `seed_demo_alfa.py`, which is idempotent (no-op when admin Alfa already exists). To replant the Alfa demo with the latest dataset, set `SIGE_FORCE_RESEED=1` (also accepts `true`/`yes`/`on`) in the EasyPanel panel before the deploy — the entrypoint then passes `--reset` to the seed, wiping and replanting **only** the Alfa tenant (multi-tenant safeguard from Task #55 aborts if cross-tenant references exist). **Always remove the flag after the refresh deploy** to prevent every subsequent deploy from destroying manual data on top of the Alfa tenant. Demo dataset (Task #20 expansion) covers two simultaneous obras: `OBR-2026-001` Residencial Bela Vista (3 RDOs Finalizados + medição APROVADA + ContaReceber OBR-MED) and `OBR-2026-002` Comercial Pinheiros (R$ 462.500 em 4 itens — 1500m² alvenaria + 1500m² contrapiso + 1500m² pintura interna acrílica + verba mobilização — três serviços com template materializam folhas no cronograma para que `/metricas/servico` (Empresa por Serviço) exiba ≥3 serviços com dados; 10 RDOs Finalizados, progresso monotônico 10→100% e variação intencional dos incrementos semanais (1 RDO a +5% para sinalizar produtividade abaixo do orçado, 1 RDO a +15% como compensação) + 2 RDOs com 1 diarista omitido para variação em Métricas; horas trabalhadas variam 6-10h com horas extras 0-2h e ocorrências em mix Baixa/Média). CRM populado com 4 responsáveis (Ana Paula, Bruno, Carla, Diego), listas mestras semeadas (origem/cadência/situação/tipo material/tipo obra/motivo perda) e 12 leads distribuídos nas 8 colunas do Kanban — incluindo 1 Aprovado linkado à proposta+obra Bela Vista e 2 Perdidos com motivo cadastrado. `status_changed_at` espalhado entre 1 e 25 dias atrás para que o badge "parado há X dias" apareça em verde/amarelo/vermelho. `_reset_dataset()` cobre todas as novas tabelas (`lead_historico`, `lead`, `crm_responsavel`, `crm_origem`, `crm_cadencia`, `crm_situacao`, `crm_tipo_material`, `crm_tipo_obra`, `crm_motivo_perda`); `_backfill_custos_rdo_demo()` itera todas as obras do admin (não só Bela Vista) para gerar GestaoCustoFilho SALARIO/VA/VT dos diaristas em ambas obras. **Métricas (follow-up Task #20):** o seed agora cria 3 `Funcao` (Pedreiro/Servente/Encarregado) com `insumo_id` apontando para os insumos MAO_OBRA, vincula `Funcionario.funcao_id` e popula `SubatividadeMaoObra` (N:N sub_mestre↔composicao MAO_OBRA por serviço) — pré-requisitos do listener `services.vinculo_mao_obra.before_flush` que preenche `RDOMaoObra.composicao_servico_id` automaticamente. Os loops RDO Bela Vista/Pinheiros invertem a ordem para criar `RDOServicoSubatividade` primeiro com `quantidade_produzida` calculado, flush, e depois `RDOMaoObra` referenciando `subatividade_id=rss.id`. `_backfill_custos_rdo_demo` chama `gravar_custo_funcionario_rdo` antes de `gerar_custos_mao_obra_rdo` para popular `RDOCustoDiario` (consumido pelas métricas de produtividade/lucratividade). `_reset_dataset` adiciona DELETE de `rdo_custo_diario`, `subatividade_mao_obra` e `funcao`. Resultado: `/metricas/servico`, `/metricas/funcionarios` e `/metricas/divergencia` exibem dados reais (3 serviços com `total_produzido`/`total_hh`/`indice_pct`/`papel_gargalo`, 4 funcionários com `custo_total`, totais de divergência) imediatamente após `--reset`.

### Operating the Demo Refresh in Production

To force a refresh of the `Construtora Alfa` demo tenant on the next EasyPanel deploy:
1. EasyPanel → **Environment** → add `SIGE_FORCE_RESEED=1`.
2. Trigger the deploy. In the deploy log expect: `⚠️  SIGE_FORCE_RESEED ativo — seed vai REPLANTAR (--reset) o tenant Alfa.` followed by `✅ seed demo Alfa concluído com sucesso (exit 0)`.
3. **Remove `SIGE_FORCE_RESEED` from the panel** (or set it to `0`). Otherwise every future deploy will wipe and replant the Alfa demo.

### External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** Object Relational Mapper (ORM).
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Python templating language.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** Date/time utilities.
-   **DeepFace:** Facial recognition library.
-   **Flask-WTF:** For CSRF protection.
-   **Flask-Limiter:** For rate limiting.