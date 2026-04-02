## Overview
SIGE v9.0 (Sistema de Gestão Empresarial) is a production-ready, multi-tenant business management system designed for Small and Medium-sized Businesses (SMBs). Its core purpose is to automate and streamline critical operations, including commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. The system aims to significantly boost operational efficiency, provide comprehensive oversight from sales to project management and financial calculations, and ultimately enhance overall business management for SMBs.

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
The system employs a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 for server-side templating and Bootstrap for a responsive frontend. Docker is used for deployment, leveraging a unified `base_completo.html` template for consistent UI/UX.

**Views Package Structure (Refactored 2026-02-10):**
The monolithic `views.py` (11,042 lines) was refactored into a `views/` Python package with domain-specific modules. All routes remain on the same `main_bp` Blueprint with identical function names. The original file is preserved as `views_old_backup.py`.
-   `views/__init__.py` - Blueprint definition and module imports
-   `views/helpers.py` - Shared utilities (safe_db_operation, get_admin_id_robusta, get_admin_id_dinamico, circuit_breaker fallbacks)
-   `views/auth.py` - Authentication (login, logout, index)
-   `views/dashboard.py` - Dashboard and health checks
-   `views/users.py` - User management (CRUD)
-   `views/employees.py` - Employee management and profiles
-   `views/obras.py` - Construction project management
-   `views/vehicles.py` - Vehicle/fleet management
-   `views/rdo.py` - Daily Work Reports (RDO) system
-   `views/api.py` - API endpoints for frontend
-   `views/admin.py` - Super admin, diagnostics, novo_ponto

**Security Hardening (2026-02-10):**
-   CSRF Protection enabled via Flask-WTF CSRFProtect with auto-injection JS in base templates
-   CORS restricted to sige.cassioviller.tech + Replit dev domains (no more origins="*")
-   Rate limiting on login route (5 per minute) via flask-limiter
-   Secret key moved from hardcoded to SESSION_SECRET environment variable
-   API blueprints exempted from CSRF: api_organizer, api_servicos_obra_limpa, ponto, landing

**Code Quality (2026-02-10):**
-   All debug print() statements replaced with structured logging (logging module)
-   Emojis removed from log messages, replaced with text tags [OK], [ERROR], [WARN], etc.

**Commercial Landing Page (2026-02-10):**
-   `/site` route serves standalone marketing page (landing_views.py + templates/landing.html)
-   4 pricing tiers: Starter R$499, Professional R$899, Enterprise R$1.599, Corporate (sob consulta)
-   18 modules showcased, feature highlights, differentials section
-   Fully responsive, standalone HTML (not extending base templates)

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation per `admin_id` and implements robust role-based access control.
-   **Event-Driven Integration:** Uses an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, featuring elegant cards, gradients, and smooth animations.
-   **Automated Database Migrations:** `migrations.py` manages schema updates, including critical migrations for multi-tenancy.
-   **Atomic Transactions:** Critical operations are protected by `safe_db_operation` to ensure data integrity.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category displays.
-   **Company Customization:** Allows dynamic branding via logo uploads and custom color schemes.
-   **Core Modules:**
    -   **Proposal Management:** Features reusable templates, automated calculations, real-time recalculation, HTML-based PDF generation, and a client portal with token-based access. Includes CRUD for attachments with intelligent image optimization.
    -   **Employee Management & Payroll:** Handles registration, automated time clocking, flexible work schedules with configurable tolerances, and automated CLT-compliant payroll calculations with dynamic PDF holerite generation and accounting integration.
    -   **Construction Project Management (RDO):** Manages Daily Work Reports, dynamic service progress, consolidated routing, and a comprehensive mobile-first photo upload system with automatic WebP optimization.
    -   **Costs Management:** Provides CRUD for construction costs, real-time statistics, and KPI dashboards. Includes detailed labor cost dashboards per project.
    -   **Accounting:** Supports double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, and DRE.
    -   **Fleet Management System:** Manages vehicles, expenses, TCO dashboards, and critical alerts.
    -   **Food Management System (Alimentação v2.0):** Mobile-first redesigned interface for managing restaurant and food entries with dynamic multi-item launching, searchable employee selection, and automatic cost calculation. V2 tenants get per-item employee + cost-center assignment, CustoObra grouping by cost center, Gestão de Custos integration, and a navbar dropdown with direct "Novo Lançamento" link (badge V2). Bug fixed: `UnboundLocalError` on `is_v2_active` caused by redundant local import inside function removed.
    -   **Warehouse Management:** Manages materials, tools, and PPE with traceability, full CRUD for suppliers, material flow workflows (entrada/saída/devolução), manual batch/lot selection for strategic cost optimization, serialized item status transitions, optimistic locking, and employee consumable tracking.
    -   **Transporte V2 Melhorias (Migration 78):** Centro de custo removido do formulário (era duplicidade da Obra); `centro_custo_id` tornado nullable via M78; novo formulário `/transporte/novo-massa` para lançamento em lote (múltiplos funcionários × múltiplos dias via seleção de período e dias da semana); preview interativo mostra X funcionários × Y dias = Z lançamentos + valor total; integração automática com Gestão de Custos por funcionário no lote; navbar atualizado com link direto "Lançamento em Lote"; filtro de lista trocado de Centro de Custo para Obra.
    -   **Compras de Materiais V2 (Migration 74):** `pedido_compra` + `pedido_compra_item` tables; `compras_views.py` blueprint at `/compras`; dynamic JS item table with per-row subtotal and grand total; auto-creates `CustoObra` (if obra selected) and `ContaPagar` records (status PAGO if à vista, PENDENTE if term/parcelado); file attachment support; V2-only menu link inside Almoxarifado dropdown.
    -   **Cronograma V2 (Migration 75):** MS-Project-style Gantt chart with `CalendarioEmpresa` + `TarefaCronograma` models; task hierarchy (pai/filho); planned vs actual progress; `cronograma_views.py` blueprint at `/cronograma`; `utils/cronograma_engine.py` for progress calculations.
    -   **RDO Integrado ao Cronograma V2 (Migration 76):** `RDOApontamentoCronograma` model links RDOs to cronograma tasks; `novo.html` shows V2-only card `#cardCronogramaV2` with AJAX task tree + production quantity inputs; `salvar_rdo_flexivel` processes `cronograma_tarefa_<id>=<qty>` form fields; `visualizar_rdo_moderno.html` shows "Produção do Dia — Cronograma V2" section with dual progress bars (planned vs actual); admin users can create RDOs without employee session (criado_por_id falls back to current_user.id).
    -   **Gestão de Custos V2 (Migration 77):** Centralized cost management module with 4-step approval workflow. `GestaoCustoPai` + `GestaoCustoFilho` models (hierarchy); `gestao_custos_views.py` blueprint at `/gestao-custos`; status flow PENDENTE → SOLICITADO → AUTORIZADO → PAGO (two-phase: autorizar route marks AUTORIZADO, pagar route marks PAGO and creates FluxoCaixa); AJAX accordion to expand child items; manual cost entry form; `utils/financeiro_integration.py` with `registrar_custo_automatico()` for automatic integration from other modules; V2 navbar: dropdown "Gestão Financeira" with links to Gestão de Custos + Reembolsos.
    -   **Financeiro V2 Integration (2026-04-02):** `financeiro_service.py` includes `GestaoCustoPai` (SOLICITADO+AUTORIZADO status) in `calcular_fluxo_caixa()` saídas previstas and `obter_kpis_financeiros()` total_pagar. `financeiro_views.py` passes `custos_v2` to contas_pagar template. `contas_pagar.html` shows "Gestão de Custos V2" section with badges for pending/authorized costs.
    -   **Reembolsos V2 (Migration 79 + 2026-04-02 CRUD):** `reembolso_views.py` blueprint at `/reembolso`; full CRUD (listar, novo, editar, excluir); auto-creates linked `GestaoCustoPai` (tipo REEMBOLSO) on create; templates at `templates/reembolsos/`; V2-only navbar link under "Gestão Financeira" dropdown.
    -   **Diaristas Ponto (2026-04-02):** `ponto_service.py` `bater_ponto_obra` now emits `ponto_registrado` event after commit. `event_manager.py` `calcular_horas_folha` detects `tipo_remuneracao == 'diaria'` and creates `CustoObra` with `valor_diaria` + `categoria='PONTO_ELETRONICO_DIARIA'` on first clock-in (entrada), with idempotency guard to avoid duplicate daily costs.
    -   **Cronograma Predecessora Inline + Recálculo em Cadeia (2026-04-02):** `cronograma_views.py` `atualizar_tarefa` now calls `recalcular_cronograma()` after each update (chain propagation). Gantt template inline predecessora editing upgraded from number input to a `<select>` dropdown listing all tasks by name with cycle-safe commit/blur logic.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking, advanced Excel import, and enhanced facial recognition verification using DeepFace library (offline, no cloud AI). Features include:
        - **Multiple Photos per Employee:** Employees can register multiple facial photos (with/without glasses, different angles, lighting) to improve recognition accuracy (model: `FotoFacialFuncionario`, migration 68)
        - **Stricter Recognition Threshold:** Reduced from 0.55 to 0.40 for more rigorous matching (fewer false positives)
        - **60% Minimum Confidence:** Requires at least 60% confidence for positive identification
        - **Geofencing:** GPS-based location validation when works (obras) have coordinates configured (100m default radius)
        - **Photo Quality Validation:** Validates brightness (30-230), minimum size (150x150px) before accepting photos
        - **UI for Photo Management:** `/ponto/funcionario/<id>/fotos-faciais` for managing employee facial photos
-   **Automated Database Error Diagnostics:** A `DatabaseDiagnostics` system analyzes SQLAlchemy errors, reports missing columns, and generates diagnostic reports.
-   **Híbrido Data Model Support:** For food management, aggregates data from legacy and new models for seamless coexistence.
-   **Transaction Isolation for Deletions:** Critical deletion operations use RAW connections with `isolation_level="AUTOCOMMIT"` and incorporate schema introspection for multi-tenant filtering.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** Object Relational Mapper (ORM).
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Python templating language.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** Date/time utilities.