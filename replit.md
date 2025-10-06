# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed to streamline core business operations. It focuses on commercial proposals, employee management, construction project control (Daily Work Reports - RDO), and automated payroll. The system aims to provide a comprehensive solution for companies to efficiently manage their activities, from sales proposal generation and complex payroll calculations to construction site management, targeting the SMB sector.

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
The system utilizes a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 templates and Bootstrap for the frontend. Docker manages deployment. A unified modern template (`base_completo.html`) ensures consistent UI/UX across all pages. Critical database transaction protection is implemented via a `safe_db_operation` function.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with role-based access control and dynamic `admin_id` handling.
-   **UI/UX Design:** Professional design system with modern UX/UI guidelines, including responsive grid layouts, modular components (cards, stylized inputs), a cohesive color palette (primary green #198754), hierarchical typography (Inter font), consistent spacing, advanced visual states, real-time validation, and WCAG accessibility.
-   **Mobile-First Design (RDO System):** Optimized for touch with haptic feedback, native gestures, a fixed bottom navigation bar, intelligent auto-save, optimized keyboards, and PWA meta tags.
-   **Automated Database Migrations:** `migrations.py` handles schema updates automatically at application initialization, logging all operations.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automatic calculations, categorization, filtering, custom numbering, and professional PDF generation with dynamic A4 pagination.
    -   **Employee Management:** Full registration with photo support, automated time clocking, and overtime/lateness calculation.
    -   **Construction Project Management (RDO):** Control of projects with Daily Work Reports (RDO), employee and equipment allocation, featuring a modernized card-based interface accessible via `/rdo` with gradient headers, statistics dashboard, and advanced filtering.
    -   **Payroll:** Automatic calculation based on time clock records and configurable salaries.
-   **Dynamic PDF Generation:** Supports custom PDF headers, dynamic content pagination, and multi-category proposal display with subtotals.
-   **Company Customization:** Allows dynamic branding with logo uploads and custom colors (primary, secondary, background) affecting public proposal portals and PDF outputs.
-   **Drag-and-Drop Organization:** System for organizing proposals by dragging and dropping multiple templates, dynamically updating PDF output.
-   **Fleet Management System (Phase 1):** New vehicle management architecture with dual-phase rollout:
    -   **Migration 0 (FIRST - Oct 2025):** CRITICAL automatic migration that executes BEFORE all others to guarantee `motorista_id` column exists in `uso_veiculo` table.
        - **Execution Order:** Runs as FIRST migration (line 36 in executar_migracoes())
        - **Functionality:** Verifies table existence → checks column existence → creates column/FK/index if missing
        - **Safety:** Completely idempotent, safe to run multiple times, detailed logging for production monitoring
        - **Production Fix:** Automatically resolves "column motorista_id does not exist" error without manual intervention
        - **Triple Redundancy:** Migration 0 (primary) + Migration 20 Part 4.5 (secondary) + Migration 21 (tertiary)
    -   **Migration 20 (FIXED - Oct 2025):** Complete Fleet tables created (`fleet_vehicle`, `fleet_vehicle_usage`, `fleet_vehicle_cost`) with 100% data migration from legacy tables verified.
        - **Critical Fix 1 (FK):** Foreign key creation moved to separate ALTER TABLE statements (Part 3.5) AFTER all tables exist, eliminating "vehicle_id constraint does not exist" production error
        - **Critical Fix 2 (motorista_id):** Part 4.5 verifies `motorista_id` column exists before Part 5 uses it (now redundant with Migration 0, kept for safety)
        - **Architecture:** Tables created WITHOUT inline FKs → All tables exist → FKs added via ALTER TABLE → motorista_id verified → Data migrated
        - **Safety:** Each FK wrapped in try/except for resilience; single commit at end preserves atomicity; idempotent column creation
        - **Monitoring:** Production should alert if any ALTER TABLE FK statement fails in logs
    -   **Migration 21 (Hotfix):** Emergency fix verifying `motorista_id` in legacy `uso_veiculo` table (now redundant with Migration 0, but kept for triple-redundancy safety).
    -   **Phase 1 (Complete):** All critical fixes deployed, 100% automatic deployment achieved, production stabilized, legacy system operational with enhanced compatibility.
    -   **Phase 2 (Pending):** Gradual migration of 27+ routes in views.py from legacy models to FleetService using feature flag system.
    -   **Idempotent Migration:** All migrations prevent data duplication using NOT EXISTS guards; verified counts: 1 vehicle, 3 usage records, 5 cost records all successfully migrated.
    -   **Deployment Strategy:** Zero manual intervention required - all migrations run automatically on application startup in both development and production environments.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.