# SIGE v9.0
A multi-tenant business management system for SMBs, designed to automate and streamline critical operations from sales to project execution and financial management.

## Run & Operate
_Populate as you build_

## Stack
- **Framework:** Flask
- **ORM:** SQLAlchemy
- **Database:** PostgreSQL
- **Frontend:** Bootstrap, Jinja2
- **Deployment:** Docker
- **Build Tool:** _Populate as you build_
- **Validation:** _Populate as you build_
- **Runtime:** Python (version implied by Flask/SQLAlchemy ecosystem)

## Where things live
- **Core application logic:** `views/` Python package (domain-specific modules)
- **Base HTML template:** `base_completo.html`
- **Database Schema:** Defined implicitly by SQLAlchemy models
- **API Contracts:** _Populate as you build_
- **Theme/Styling:** `static/css/styles.css` (with `.sige-*` namespace for shared partials)
- **Shared Jinja macros:** `templates/_partials/macros.html`

## Architecture decisions
-   **Multi-tenancy and Security:** Implemented with data isolation, RBAC, CSRF, restricted CORS, rate limiting, and secure key handling.
-   **Event-Driven Architecture:** Uses an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **Atomic DB Transactions:** Utilizes `safe_db_operation` for atomic transactions and automated error diagnostics.
-   **Operational Budget per Obra:** Each `Obra` maintains an editable, versioned copy of its `Orcamento` via `ObraOrcamentoOperacional`, cloning on the first RDO.
-   **Unified UI Theme:** All new and migrated screens (CRM, Métricas) extend `base_completo.html` and use shared Jinja macros for consistent design.

## Product
-   **Commercial Management:** Proposal generation, automated calculations, client portal, service catalog, parametric budgeting.
-   **Employee & Payroll:** Registration, automated time clocking, flexible schedules, CLT-compliant payroll, PDF payslips.
-   **Construction Project Management:** Daily Work Reports (RDO) with dynamic service progress, consolidated routing, mobile photo uploads, project measurement, intelligent hour normalization.
-   **Financial & Accounting:** Double-entry bookkeeping, automated journal entries, chart of accounts, DRE, cash flow management.
-   **Logistics & Inventory:** Warehouse management, supplier CRUD, material flow, batch/lot selection, serialized items, optimistic locking.
-   **Fleet Management:** Vehicle management, expense tracking, TCO dashboards, critical alerts.
-   **Food Management:** Mobile-first interface for restaurant entries with dynamic multi-item launching and auto-cost calculation.
-   **Client Portal:** Token-based access for project progress, purchase approval, payment receipt uploads.
-   **Competitive Bidding:** Multi-supplier comparison tool with inline editing.
-   **Automated Project Scheduling (Cronograma V2):** MS-Project-style Gantt chart with task hierarchy and drag-and-drop, automated schedule creation.
-   **CRM Leads:** Kanban view, lead management, configurable master lists, status tracking, historical logging.

## User preferences
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

## Gotchas
-   **Demo Refresh:** To reseed the 'Alfa' demo tenant, set `SIGE_FORCE_RESEED=1` in EasyPanel environment variables *before* deployment. **Crucially, remove this flag immediately after the deploy** to prevent subsequent deploys from wiping demo data.
-   **Cross-Tenant References:** The demo reseed process will abort if cross-tenant references are detected to safeguard production data.

## Pointers
-   **Flask Documentation:** [https://flask.palletsprojects.com/](https://flask.palletsprojects.com/)
-   **SQLAlchemy Documentation:** [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
-   **Bootstrap Documentation:** [https://getbootstrap.com/docs/](https://getbootstrap.com/docs/)
-   **Jinja2 Documentation:** [https://jinja.palletsprojects.com/](https://jinja.palletsprojects.com/)
-   **Sortable.js Documentation:** [https://sortablejs.github.io/Sortable/](https://sortablejs.github.io/Sortable/)