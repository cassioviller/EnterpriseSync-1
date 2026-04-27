## Overview
SIGE v9.0 (Sistema de Gestão Empresarial) is a multi-tenant business management system for SMBs, designed to automate and streamline critical operations. It covers commercial proposal generation, employee and payroll management, construction project control (Daily Work Reports - RDO), and comprehensive financial calculations. The system aims to enhance operational efficiency, provide end-to-end oversight from sales to project execution, and improve overall business management.

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
The system utilizes a Flask backend with SQLAlchemy ORM, a PostgreSQL database, and Jinja2 for server-side templating. Bootstrap is used for the frontend, and Docker for deployment. The codebase is structured with a `views/` Python package for domain-specific modules, all using a unified `base_completo.html` template.

**Key Architectural Decisions & Features:**
-   **Multi-tenancy and Security:** Features data isolation, role-based access control, CSRF protection, restricted CORS, rate limiting, and secure key handling.
-   **Event-Driven Architecture:** Employs an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Focuses on modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, including elegant cards, gradients, and smooth animations.
-   **Data Integrity & Management:** Includes automated database migrations, atomic transactions via `safe_db_operation`, and automated error diagnostics for SQLAlchemy.
-   **Dynamic Content Generation:** Supports dynamic PDF generation with custom headers and company customization through logo uploads and configurable color schemes.
-   **Core Modules:**
    -   **Commercial Management:** Proposal management with templates, automated calculations, real-time recalculation, client portal access, service catalog, and parametric budgeting.
    -   **Employee & Payroll Management:** Employee registration, automated time clocking (GPS, facial recognition, geofencing), flexible schedules, automated CLT-compliant payroll, dynamic PDF holerite generation, and accounting integration.
    -   **Construction Project Management:** Daily Work Reports (RDO) with dynamic service progress, consolidated routing, mobile photo uploads, and integration with Cronograma V2; Biweekly Project Measurement.
    -   **Financial & Accounting:** Double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, DRE, and enhanced FluxoCaixa.
    -   **Logistics & Inventory:** Warehouse management with traceability, full CRUD for suppliers, material flow, batch/lot selection, serialized item transitions, and optimistic locking; Material Purchase Management with dynamic item tables and automated cost registration.
    -   **Fleet Management:** Vehicle management, expense tracking, TCO dashboards, and critical alerts.
    -   **Food Management:** Mobile-first interface for restaurant and food entries with dynamic multi-item launching and automatic cost calculation.
    -   **Client Portal:** Token-based access for clients to view project progress, approve purchases, and upload payment receipts.
    -   **Competitive Bidding:** Multi-supplier comparison tool with an N items × N suppliers grid, inline editing, and interactive client selection.
    -   **Automated Project Scheduling (Cronograma V2):** MS-Project-style Gantt chart with task hierarchy and drag-and-drop. Automatic schedule creation from service templates upon proposal approval.
    -   **Configurable Proposal Clauses:** Dynamic clause management per proposal and template, allowing structured, orderable entries.
    -   **Responsible Engineer Management:** Dedicated `EngenheiroResponsavel` model supporting per-proposal overrides and fallback mechanisms.
    -   **Project-Client Linking:** `Obra.cliente_id` FK to `Cliente` for improved data integrity, with fallback to legacy text fields.
    -   **Employee Metrics:** Unified service for calculating employee KPIs and costs for salarists and day-workers.
    -   **Configurable Theme System:** Per-tenant visual themes stored in `ConfiguracaoEmpresa`, allowing selection from presets or custom color adjustments (primary, secondary, header/nav, app background) overriding Bootstrap via CSS variables.
    -   **Resilient Client Approval Flow:** Robustness fixes for proposal approval, handling null proposal subjects and creating synthetic `Cliente` records for legacy data to prevent failures in `Obra` creation.
    -   **Searchable Supplier Dropdown on /compras/nova:** Implemented Select2 for supplier and project search, providing typeahead functionality. Includes multi-tenant validation to prevent cross-tenant data leakage.
    -   **Single Proposta Model:** Consolidated proposal data into a single `Proposta` model, dropping several legacy tables after data backup.
    -   **Initial Schedule Review on Obra:** Implemented a two-state visit gate for newly created `Obra` instances, requiring administrative review of the initial schedule before full project access. Includes a reset mechanism and backfill for existing production data.

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