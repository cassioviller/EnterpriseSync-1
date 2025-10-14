# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system for SMBs, streamlining core operations such as commercial proposals, employee management, construction project control (Daily Work Reports - RDO), and automated payroll. It aims to enhance efficiency from sales to construction site management and complex payroll calculations.

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
The system uses a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 templates and Bootstrap for the frontend. Docker manages deployment. A unified modern template (`base_completo.html`) ensures consistent UI/UX. Critical database transaction protection is implemented via a `safe_db_operation` function.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with role-based access control and dynamic `admin_id` handling.
-   **Event-Driven Integration System (v9.0):** `EventManager` (event_manager.py) implements Observer Pattern for automated cross-module integration. Active integrations:
    -   Almoxarifado → Custos: Material withdrawals emit `material_saida` events with cost tracking
    -   Frota → Custos: Vehicle usage emits `veiculo_usado` events calculating fuel/wear costs (R$0.80/km)
    -   Handlers use structured logging for audit trail until full Cost Management module is implemented
    -   4 events registered at startup: material_saida, veiculo_usado, ponto_registrado, proposta_aprovada
-   **UI/UX Design:** Professional design system following modern UX/UI guidelines, including responsive grid layouts, modular components, a cohesive color palette (primary green #198754), hierarchical typography, consistent spacing, advanced visual states, real-time validation, and WCAG accessibility. Mobile-First Design is applied for modules like RDO, optimizing for touch and including PWA meta tags.
-   **Automated Database Migrations:** `migrations.py` handles schema updates automatically at application initialization, logging all operations and optimized for quick startup.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automatic calculations, categorization, filtering, custom numbering, professional PDF generation, and history tracking.
    -   **Employee Management:** Full registration with photo support, automated time clocking, and overtime/lateness calculation.
    -   **Construction Project Management (RDO):** Control of projects with Daily Work Reports, employee and equipment allocation, featuring a modernized card-based interface and dynamic service progress calculation.
    -   **Payroll:** Automatic calculation based on time clock records and configurable salaries.
    -   **Fleet Management System:** Manages vehicles, usage, and expenses.
    -   **Food Management System:** Card-based interface for managing restaurants and food entries.
    -   **Almoxarifado v3.0 (Warehouse Management):** Complete system for materials, tools, and PPE with full traceability, multi-tenant isolation, serialized and consumable control types, CRUD, movement tracking (ENTRADA/SAIDA/DEVOLUCAO), dashboards, reports, and employee profile integration.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock system allowing multiple employees to punch in/out from a single device per construction site, with GPS tracking, real-time status updates, and configurable schedules.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content pagination, and multi-category proposal display.
-   **Company Customization:** Allows dynamic branding with logo uploads and custom colors.
-   **Drag-and-Drop Organization:** System for organizing proposals by dragging and dropping multiple templates.
-   **Atomic Transactions:** Ensures data integrity for critical operations.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.