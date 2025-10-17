## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed for Small and Medium-sized Businesses (SMBs). Its core purpose is to streamline and enhance efficiency across key operational areas, including commercial proposal generation, comprehensive employee management, detailed construction project control (Daily Work Reports - RDO), and automated payroll processing. The system aims to cover the entire business workflow from initial sales activities to on-site construction management and complex financial calculations.

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
The system is built on a Flask backend, utilizing SQLAlchemy ORM and a PostgreSQL database. Jinja2 is used for templating, and Bootstrap for frontend styling. Docker is used for deployment. A unified `base_completo.html` template ensures consistent UI/UX across the application. Critical database operations are protected by a `safe_db_operation` function to ensure data integrity.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation for each `admin_id` with role-based access control and dynamic `admin_id` handling.
-   **Dynamic Dashboard KPIs:** All metrics are calculated in real-time from the database, including proposal status, conversion rates, and analytics, with robust error handling.
-   **Event-Driven Integration System:** An `EventManager` (Observer Pattern) facilitates automated cross-module integration (e.g., material withdrawals impacting costs, payroll processing triggering accounting entries).
-   **UI/UX Design:** Adheres to modern UX/UI guidelines, featuring responsive layouts, modular components, a cohesive color palette, hierarchical typography, consistent spacing, and WCAG accessibility. Mobile-First Design is applied to modules like RDO.
-   **Automated Database Migrations:** `migrations.py` manages schema updates automatically at application initialization, ensuring consistent database structures.
-   **Core Modules:**
    -   **Proposal Management:** Supports reusable templates, automated calculations, PDF generation, and history tracking.
    -   **Employee Management:** Includes registration, automated time clocking, and overtime calculations.
    -   **Construction Project Management (RDO):** Provides control over projects with Daily Work Reports and dynamic service progress calculation.
    -   **Payroll:** Automated calculation based on time clock records.
    -   **Fleet Management System:** Manages vehicles and expenses.
    -   **Food Management System:** Manages restaurant and food entries.
    -   **Almoxarifado v3.0 (Warehouse Management):** Comprehensive system for materials, tools, and PPE with traceability, multi-tenant isolation, and movement tracking.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking for construction sites.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category proposal display.
-   **Company Customization:** Allows for dynamic branding with logo uploads and custom colors.
-   **Drag-and-Drop Organization:** Enables intuitive organization of proposals using multiple templates.
-   **Atomic Transactions:** Ensures data integrity for critical operations.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop functionality.