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
    -   **Expandable Service Composition:** Services in budgets/proposals render as collapsible Bootstrap cards, displaying detailed cost breakdowns and included/excluded items.
    -   **Catalog Import via Excel:** Functionality to import and export catalog data for inputs and schedule templates using Excel files, with multi-tenant scoping and validation.
    -   **RDO Task Weighting:** Allows employees to assign weights to principal tasks within an RDO, influencing hour distribution when multiple activities are recorded.
    -   **CRM Leads - Kanban + Master Lists:** New CRM module with Kanban view, lead management, and configurable master lists for CRM entities like responsibles, origins, cadences, situations, material types, and project types. Features lead status tracking, historical logging, and controlled transitions (e.g., preventing 'Lost' status without a reason).
    -   **Proposta Sent Notification (Task #44):** When admin sends a proposal, the system emits the `proposta.enviada` event for n8n webhook delivery (e-mail to client) and renders a green WhatsApp button on the proposal detail page (pre-filled message + portal link, BR DDI normalization). Missing e-mail and/or phone produce non-blocking `flash` warnings; both the dispatch and the manual WhatsApp click are recorded in `PropostaHistorico` (`notificacao_disparada`, `whatsapp_aberto`).

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