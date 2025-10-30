## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed for Small and Medium-sized Businesses (SMBs). Its primary purpose is to streamline and automate core business operations including commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. SIGE aims to enhance efficiency and provide comprehensive operational oversight across the entire business workflow, from sales to on-site project management and financial calculations.

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

## System Architecture
The system employs a Flask backend, SQLAlchemy ORM, and a PostgreSQL database. Jinja2 is used for server-side templating and Bootstrap for responsive frontend styling. Docker facilitates deployment. A unified `base_completo.html` template ensures UI/UX consistency.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with robust role-based access control.
-   **Event-Driven Integration System:** Utilizes an `EventManager` (Observer Pattern) for automated cross-module data flow (e.g., material movements impacting costs, payroll triggering accounting).
-   **UI/UX Design:** Modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, particularly for modules like RDO.
-   **Automated Database Migrations:** `migrations.py` manages schema updates during application initialization, including a critical multi-tenancy migration (Migration 48) that backfills `admin_id` into 20 core models with tenant-aware strategies and comprehensive post-backfill validations to prevent data leakage and ensure isolation.
-   **Atomic Transactions:** Critical operations are protected by `safe_db_operation` to ensure data integrity.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category proposal displays.
-   **Company Customization:** Allows dynamic branding via logo uploads and custom color schemes.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automated calculations, PDF generation, and history tracking.
    -   **Employee Management:** Registration, automated time clocking, and overtime calculations.
    -   **Construction Project Management (RDO):** Daily Work Reports and dynamic service progress.
    -   **Payroll (Folha de Pagamento):** Automated calculations including CLT-compliant overtime differentiation (50% and 100% rates) and late deduction processing. Integrates with accounting.
    -   **Costs Management (Custos):** CRUD for construction costs with multi-tenant security, real-time statistics, and a dashboard with KPIs.
    -   **Accounting (Contabilidade):** Double-entry bookkeeping, automatic journal entries from payroll, a chart of accounts, trial balance, and DRE with competency selection.
    -   **Fleet Management System:** Manages vehicles, expenses, and provides TCO dashboards with critical alert notifications.
    -   **Food Management System:** Manages restaurant and food entries, integrates with the financial module to generate accounts payable.
    -   **Warehouse Management (Almoxarifado):** Manages materials, tools, and PPE with traceability.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking.
-   **Automated Database Error Diagnostics:** Includes a `DatabaseDiagnostics` system (`utils/database_diagnostics.py`) to analyze SQLAlchemy errors, report missing columns, and generate diagnostic reports. This system is integrated into views with `@capture_db_errors` decorators to provide user-friendly error messages and fallback mechanisms, particularly crucial for ensuring system functionality even when core migrations (like Migration 48) are pending in production. This diagnostic system includes a dedicated admin panel and pre/post-migration scripts for robust deployment.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** Object Relational Mapper (ORM).
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework for responsive design.
-   **Jinja2:** Python templating language.
-   **Docker:** Platform for developing, shipping, and running applications in containers.
-   **Sortable.js:** JavaScript library for drag-and-drop functionality.
-   **python-dateutil:** Provides extensions to the standard datetime module.