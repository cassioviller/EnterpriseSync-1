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
    -   **Food Management System (Alimentação v2.0):** Mobile-first redesigned interface for managing restaurant and food entries with dynamic multi-item launching, searchable employee selection, and automatic cost calculation.
    -   **Warehouse Management:** Manages materials, tools, and PPE with traceability, full CRUD for suppliers, material flow workflows (entrada/saída/devolução), manual batch/lot selection for strategic cost optimization, serialized item status transitions, optimistic locking, and employee consumable tracking.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking and advanced Excel import.
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