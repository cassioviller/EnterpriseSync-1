## Overview
SIGE v9.0 (Sistema de Gestão Empresarial) is a production-ready, multi-tenant business management system designed for Small and Medium-sized Businesses (SMBs). Its core purpose is to automate and streamline critical business operations, including commercial proposal generation, employee and payroll management, construction project control (Daily Work Reports - RDO), and comprehensive financial calculations. The system aims to significantly enhance operational efficiency, provide end-to-end oversight from sales to project execution, and improve overall business management capabilities for SMBs.

## User Preferences
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

## System Architecture
The system employs a Flask backend, SQLAlchemy ORM, and PostgreSQL database. Jinja2 is used for server-side templating, and Bootstrap for the frontend. Docker facilitates deployment. The codebase is structured with a `views/` Python package for domain-specific modules, utilizing a unified `base_completo.html` template.

**Key Architectural Decisions & Features:**
-   **Multi-tenancy and Security:** Features data isolation, robust role-based access control, CSRF protection, restricted CORS, rate limiting, and secure key handling.
-   **Event-Driven Architecture:** Utilizes an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Emphasizes modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, incorporating elegant cards, gradients, and smooth animations.
-   **Data Integrity & Management:** Includes automated database migrations (`migrations.py`), atomic transactions via `safe_db_operation`, and automated error diagnostics for SQLAlchemy.
-   **Dynamic Content Generation:** Supports dynamic PDF generation with custom headers and company customization through logo uploads and color schemes.
-   **Core Modules:**
    -   **Commercial Management:** Proposal management with reusable templates, automated calculations, real-time recalculation, and client portal access; Service Catalog and Parametric Budgeting with input compositions and calculated selling prices.
    -   **Employee & Payroll Management:** Employee registration, automated time clocking (with GPS, facial recognition, geofencing), flexible schedules, automated CLT-compliant payroll, dynamic PDF holerite generation, and accounting integration.
    -   **Construction Project Management:** Daily Work Reports (RDO) with dynamic service progress, consolidated routing, mobile-first photo uploads, and integration with Cronograma V2; Biweekly Project Measurement with automated percentage calculation and `ContaReceber` integration.
    -   **Financial & Accounting:** Double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, DRE, and enhanced FluxoCaixa with optional `banco_id` and import previews.
    -   **Logistics & Inventory:** Warehouse management with traceability, full CRUD for suppliers, material flow, batch/lot selection, serialized item transitions, and optimistic locking; Material Purchase Management (Compras de Materiais V2) with dynamic item tables and automated cost registration.
    -   **Fleet Management:** Vehicle management, expense tracking, TCO dashboards, and critical alerts.
    -   **Food Management:** Mobile-first interface for restaurant and food entries with dynamic multi-item launching and automatic cost calculation.
    -   **Client Portal:** Token-based access for clients to view project progress, approve purchases, and upload payment receipts.
    -   **Competitive Bidding:** Multi-supplier comparison tool with N items × N suppliers grid, inline editing, and interactive client selection.
    -   **Automated Project Scheduling (Cronograma V2):** MS-Project-style Gantt chart with task hierarchy and drag-and-drop. Automatic schedule creation upon proposal approval from service templates.
    -   **Configurable Proposal Clauses:** Dynamic clause management per proposal and template, replacing fixed text fields with structured, orderable entries.
    -   **Responsible Engineer Management:** Dedicated `EngenheiroResponsavel` model for managing engineer details, supporting per-proposal overrides and fallback mechanisms.
    -   **Project-Client Linking:** `Obra.cliente_id` FK to `Cliente` for improved data integrity, with fallback to legacy text fields.
    -   **Employee Metrics:** A unified service for calculating employee KPIs and costs for salarists and day-workers, integrating various cost components (labor, benefits, food, reimbursements, inventory).
    -   **Configurable Theme System (Task #191):** Per-tenant visual theme stored in `ConfiguracaoEmpresa` (4 colors + preset id). Three presets ship out of the box (Azul Profundo SaaS — default, Verde Construção, Grafite Premium) and admins can also tweak the 4 colors freely (primary, secondary, header/nav, app background). The theme is delivered to every page via the `inject_company_config` context processor (`sige_theme`), which feeds CSS variables consumed by `static/css/sige-theme.css`. Bootstrap is preserved; the new stylesheet overrides `--bs-*` and key components (navbar, nav-tabs, buttons, dropdowns) so no template rewrites are needed.
    -   **Resilient Client Approval Flow (Task #195):** Two robustness fixes for `POST /propostas/cliente/<token>/aprovar`. (1) `templates/propostas/portal_cliente.html` now guards `proposta.titulo` (mapped to nullable `assunto` column) before calling `.lower()` — previously the public portal crashed with HTTP 500 for propostas without subject, blocking client approvals entirely. (2) `event_manager.propagar_proposta_para_obra` now creates a synthetic `Cliente` (named after the proposta number) when `cliente_resolver` returns `None` (whitespace-only `cliente_nome` + no email + no valid `cliente_id` — common in legacy data), so Obra creation never fails the FK constraint. The fallback runs in the same transaction and logs a warning so admins can fix the source data.
    -   **Initial Schedule Review on Obra (Task #200):** Two-state visit gate for obras created from proposal approval. New nullable column `Obra.cronograma_revisado_em` (Migration 140) records whether an admin reviewed the obra's initial schedule. Default flow: when proposal is approved without a pre-configured `cronograma_default_json` snapshot, the resulting obra is born with `cronograma_revisado_em=NULL` and zero `TarefaCronograma`. The very first GET `/obras/<id>` redirects to `/obras/<id>/cronograma-revisar-inicial` (gate in `views.obras.detalhes_obra`), where the admin sees the same checked tree from the proposal templates and unchecks/checks subatividades. POSTing materializes only the checked branches via `services.cronograma_proposta.materializar_cronograma`, runs `recalcular_cronograma`, and stamps `cronograma_revisado_em=utcnow()` — subsequent visits open the obra detail normally, even when the admin confirmed with everything unchecked (review is considered done once confirmed; the `cronograma_pendente` banner in `detalhes_obra` short-circuits to `False` whenever `cronograma_revisado_em IS NOT NULL`). If the admin pre-configured `cronograma_default_json` before approval, `handlers.propostas_handlers._materializar_cronograma_se_houver` already stamps the flag, so the obra is born "already reviewed" and never falls into the gate. A "Revisar de novo" button on the Cronograma tab POSTs to `/obras/<id>/cronograma-revisar-reset`, which deletes only TarefaCronograma rows where `gerada_por_proposta_item_id IS NOT NULL` (preserving manually-added tasks; `item_medicao_cronograma_tarefa` cascades, `tarefa_pai_id` uses `ON DELETE SET NULL`) and clears the flag, reopening the gate. Migration 140 backfills existing obras: any obra with at least one TarefaCronograma carrying `gerada_por_proposta_item_id IS NOT NULL` is marked as already reviewed (created_at copied to the new column) so production data does not retroactively block experienced users. Coverage: `tests/test_cronograma_revisao_obra_gate.py` (workflow `test-cronograma-revisao-obra-gate`) — 34 asserts across 5 scenarios (no pre-config, with pre-config snapshot, reset/regenerate, manual tasks survive reset, confirm review with everything unchecked still marks obra reviewed and silences the pending banner).

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** Object Relational Mapper (ORM).
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Python templating language.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** Date/time utilities.
-   **DeepFace:** Facial recognition library.
-   **Flask-WTF:** For CSRF protection.
-   **Flask-Limiter:** For rate limiting.