## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system for Small and Medium-sized Businesses (SMBs). It aims to streamline operations across commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. The system covers the entire business workflow from sales to on-site management and financial calculations, enhancing efficiency and operational oversight.

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
The system is built on a Flask backend, utilizing SQLAlchemy ORM and a PostgreSQL database, with Jinja2 for templating and Bootstrap for frontend styling. Docker is used for deployment. A unified `base_completo.html` template ensures consistent UI/UX.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation per `admin_id` with role-based access control.
-   **Dynamic Dashboard KPIs:** Real-time metrics calculated from the database with robust error handling.
-   **Event-Driven Integration System:** Uses an `EventManager` (Observer Pattern) for automated cross-module integration (e.g., material movements impacting costs, payroll triggering accounting entries).
-   **UI/UX Design:** Modern, responsive layouts with modular components, cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design for modules like RDO.
-   **Automated Database Migrations:** `migrations.py` manages schema updates at application initialization.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automated calculations, PDF generation, history tracking.
    -   **Employee Management:** Registration, automated time clocking, overtime calculations.
    -   **Construction Project Management (RDO):** Control over projects with Daily Work Reports and dynamic service progress.
    -   **Payroll (Folha de Pagamento):** Automated calculation based on time clock records, competency selector (15 months range), legal parameters validation, and automatic accounting integration. **CLT-compliant overtime differentiation**: HE 50% for Saturdays/weekdays (1.5x pay), HE 100% for Sundays/holidays (2.0x pay) with triple detection (weekday, tipo_registro, CalendarioUtil). Optimized performance with pre-loaded holiday calendar (single query + O(1) lookups).
    -   **Costs Management (Custos):** CRUD for construction costs with multi-tenant security, filters, real-time statistics, and professional UI.
    -   **Accounting (Contabilidade):** Double-entry bookkeeping with automatic journal entries from payroll, chart of accounts, trial balance, and DRE with competency selector.
    -   **Fleet Management System:** Manages vehicles and expenses.
    -   **Food Management System:** Manages restaurant and food entries.
    -   **Warehouse Management (Almoxarifado):** Comprehensive system for materials, tools, and PPE with traceability and multi-tenant isolation.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking.
-   **Dynamic PDF Generation:** Custom headers, dynamic content, multi-category proposal display.
-   **Company Customization:** Dynamic branding with logo uploads and custom colors.
-   **Drag-and-Drop Organization:** Intuitive organization of proposals.
-   **Atomic Transactions:** Ensures data integrity for critical operations using `safe_db_operation`.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** For date and time calculations.