# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed to streamline business operations for SMBs. It provides a comprehensive solution for managing commercial proposals, employee administration, construction project control (Daily Work Reports - RDO), and automated payroll. The system aims to enhance efficiency across core business activities, from sales proposal generation to complex payroll calculations and construction site management.

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
The system is built with a Flask backend, SQLAlchemy ORM, and PostgreSQL database, utilizing Jinja2 templates and Bootstrap for the frontend. Deployment is managed via Docker. A core architectural principle is the implementation of automatic database migrations to ensure schema consistency.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with role-based access control and dynamic `admin_id` handling for development and production.
-   **UI/UX Design:** A professional design system with modern UX/UI guidelines, including a responsive grid, modular components (cards, stylized inputs), a cohesive color palette (primary green #198754), hierarchical typography (Inter font), consistent spacing, advanced visual states, real-time validation, and WCAG accessibility. All 110+ pages use a unified modern template (`base_completo.html`) with proper text contrast.
-   **Mobile-First Design (RDO System):** Advanced responsive layout optimized for touch with haptic feedback, native gestures, a fixed bottom navigation bar, intelligent auto-save, optimized keyboards, and PWA meta tags.
-   **Automated Database Migrations:** `migrations.py` handles schema updates automatically at app initialization, ensuring production readiness.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automatic calculations, categorization, filtering, custom numbering, and professional PDF generation with dynamic A4 pagination.
    -   **Employee Management:** Full registration with photo support, automated time clocking, and overtime/lateness calculation.
    -   **Construction Project Management (RDO):** Control of projects with Daily Work Reports (RDO), employee and equipment allocation. Features a modernized card-based interface (`rdo_lista_unificada.html`) accessible via `/rdo` with a statistics dashboard and advanced filtering.
    -   **Payroll:** Automatic calculation based on time clock records and configurable salaries.
-   **Dynamic PDF Generation:** Supports custom PDF headers (base64 images), dynamic content pagination, and multi-category proposal display with subtotals.
-   **Company Customization:** Allows dynamic branding with logo uploads, custom colors (primary, secondary, background) for public proposal portals and PDF outputs.
-   **Drag-and-Drop Organization:** System for organizing proposals by dragging and dropping multiple templates, dynamically updating PDF output.
-   **Critical Database Transaction Protection:** Implemented via `safe_db_operation` function to prevent production errors and ensure resilience.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM for database interaction.
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop functionality.