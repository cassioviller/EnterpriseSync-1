# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed to streamline core business operations for the SMB sector. It offers comprehensive solutions for commercial proposals, employee management, construction project control (Daily Work Reports - RDO), and automated payroll. The system aims to enhance efficiency from sales proposal generation and complex payroll calculations to construction site management.

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
The system utilizes a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 templates and Bootstrap for the frontend. Docker manages deployment. A unified modern template (`base_completo.html`) ensures consistent UI/UX. Critical database transaction protection is implemented via a `safe_db_operation` function.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with role-based access control and dynamic `admin_id` handling.
-   **UI/UX Design:** Professional design system with modern UX/UI guidelines, including responsive grid layouts, modular components, a cohesive color palette (primary green #198754), hierarchical typography, consistent spacing, advanced visual states, real-time validation, and WCAG accessibility.
    -   **Mobile-First Design (RDO System):** Optimized for touch with haptic feedback, native gestures, a fixed bottom navigation bar, intelligent auto-save, optimized keyboards, and PWA meta tags.
-   **Automated Database Migrations:** `migrations.py` handles schema updates automatically at application initialization, logging all operations. Optimized for quick startup by deactivating older, already applied migrations.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automatic calculations, categorization, filtering, custom numbering, professional PDF generation with dynamic A4 pagination, and complete history tracking.
    -   **Employee Management:** Full registration with photo support, automated time clocking, and overtime/lateness calculation.
    -   **Construction Project Management (RDO):** Control of projects with Daily Work Reports, employee and equipment allocation, featuring a modernized card-based interface.
    -   **Payroll:** Automatic calculation based on time clock records and configurable salaries.
    -   **Fleet Management System:** Manages vehicles, usage, and expenses with a unified intelligent migration process that ensures data preservation and compatibility.
    -   **Food Management System:** Modern card-based interface for managing restaurants and food entries, including payment details.
-   **Dynamic PDF Generation:** Supports custom PDF headers, dynamic content pagination, and multi-category proposal display with subtotals.
-   **Company Customization:** Allows dynamic branding with logo uploads and custom colors affecting public proposal portals and PDF outputs.
-   **Drag-and-Drop Organization:** System for organizing proposals by dragging and dropping multiple templates.
-   **Atomic Transactions:** Ensures data integrity for critical operations (e.g., proposal editing, deletion, approval) by committing changes to both the main record and its history simultaneously.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.