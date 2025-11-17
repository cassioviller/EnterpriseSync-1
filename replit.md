## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system for SMBs, designed to automate and streamline core operations. It covers commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. The system aims to boost efficiency and provide comprehensive operational oversight from sales to project management and financial calculations.

## Recent Changes (November 2025)
**v9.1.0 - Proposal Items CRUD System (CRITICAL)**
- **BREAKTHROUGH**: Implemented complete CRUD workflow for proposal items (PropostaItem)
- Added item processing to POST `/criar` route: creates items + calculates valor_total automatically
- Added item processing to POST `/editar/<id>` route: updates/creates/deletes items + recalculates total
- Robust currency parser (`parse_currency()`): handles Brazilian formats ("2.500,50", "R$ 1.234,56")
- Transactional integrity: Proposta + PropostaItem rows committed atomically
- History tracking: "criada com X itens" / "editada - X itens processados"
- **Validated end-to-end**: Created proposal FINAL-001 with 3 items → DB shows 3 proposta_itens rows + valor_total R$ 5.800,00 → Portal/PDF render correctly
- **Impact**: Proposals can now have items! Previously only test data (TEST-PDF.25) had items via manual SQL

**v9.0.3 - Total Calculation & Rendering Overhaul (Critical)**
- Fixed total_geral calculation logic: now prioritizes manual valor_total over calculated sum
- Updated all templates (portal and PDF) to use total_geral instead of proposta.valor_total
- Fixed strftime None-type error in template listing with defensive rendering
- Allows proposals to have manual totals (discounts/adjustments) different from item sums
- Validated: Proposta with 12 items (R$ 120.700 calculated) correctly shows R$ 48.500 manual total

**v9.0.2 - Proposal Items Rendering Fix (Critical)**
- Fixed critical bug: Items table not rendering in client portal and PDF
- Added item organization logic to `portal_cliente()` function (was missing)
- Both portal and PDF now correctly display all proposal items with totals
- Validated with 12-item proposal showing R$ 48.500,00 correctly

**v9.0.1 - Proposal Portal Visibility & Copy Button Fix**
- Fixed portal link visibility: Card now appears immediately upon proposal creation (even for drafts)
- Added contextual warning banner for draft proposals to set client expectations
- Fixed JavaScript TypeError in copy button: Changed `event.target` to explicit `this` parameter passing
- Improved UX with instant link availability and visual feedback on copy action

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
The system is built with a Flask backend, SQLAlchemy ORM, and PostgreSQL. Jinja2 handles server-side templating, Bootstrap provides responsive frontend styling, and Docker is used for deployment. A unified `base_completo.html` template ensures consistent UI/UX.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Features data isolation per `admin_id` and robust role-based access control.
-   **Event-Driven Integration:** Uses an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles.
-   **Automated Database Migrations:** `migrations.py` manages schema updates, including critical migrations for multi-tenancy (`Migration 48`), vehicle tracking (`Migration 49`), schema synchronization for `uso_veiculo` (`Migration 50`) and `custo_veiculo` (`Migration 51`), RDO photo optimization (`Migration 52`), and RDO photo base64 persistence (`Migration 53`).
-   **Atomic Transactions:** Critical operations are protected by `safe_db_operation`.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category displays.
-   **Company Customization:** Allows dynamic branding via logo uploads and custom color schemes.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates with **multi-template loading system** (allows loading multiple template tables simultaneously in proposals), automated calculations with inline editing, real-time total recalculation, **HTML-based PDF generation** with 9-section structure (objeto, preços, inclusos, exclusos, pagamento, entrega, garantias, considerações, validade), and history tracking. Template system supports structured JSON data with editable quantity/pricing fields. **Client portal** with token-based access for public proposal viewing, approval, and rejection without login. **Portal link visibility:** Link to client portal now appears immediately upon proposal creation (even for drafts), with contextual warning banner for draft status. Templates protected against None-type errors with defensive rendering patterns. **PDF item rendering:** Tables render when proposal contains items (PropostaItem records); empty proposals show section headers only.
    -   **Employee Management:** Registration, automated time clocking, and overtime calculations.
    -   **Construction Project Management (RDO):** Daily Work Reports, dynamic service progress, consolidated routing, and a comprehensive mobile-first photo upload system with automatic WebP optimization, thumbnail generation, custom full-screen lightbox, inline captioning, and **database-based base64 storage** for production-grade photo persistence (prevents photo loss on container restarts). **Advanced filtering system** with obra, status, funcionário (via JOIN on RDOMaoObra), date range filters, and dynamic ordering (date desc/asc, obra alphabetical, status).
    -   **Payroll:** Automated CLT-compliant calculations, late deduction processing, and dynamic PDF holerite generation with automated accounting integration.
    -   **Costs Management:** CRUD for construction costs, real-time statistics, and KPI dashboards.
    -   **Accounting:** Double-entry bookkeeping, automated journal entries from payroll, chart of accounts, trial balance, and DRE.
    -   **Fleet Management System:** Manages vehicles, expenses, TCO dashboards, and critical alert notifications, including an interactive mobile-friendly passenger selection modal.
    -   **Food Management System:** Manages restaurant and food entries, integrating with the financial module, supporting hybrid data models.
    -   **Warehouse Management:** Manages materials, tools, and PPE with traceability.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking and an advanced Excel import system for batch point records, including model generation, robust validation, and KPIs.
-   **Automated Database Error Diagnostics:** A `DatabaseDiagnostics` system analyzes SQLAlchemy errors, reports missing columns, generates diagnostic reports, and is integrated with `@capture_db_errors` decorators for user-friendly error handling.
-   **Híbrido Data Model Support:** For food management, the system aggregates data from legacy and new models (`RegistroAlimentacao` and `AlimentacaoLancamento`) for seamless coexistence.
-   **Transaction Isolation for Deletions:** Critical deletion operations use RAW connections with `isolation_level="AUTOCOMMIT"` to prevent transaction errors, incorporating schema introspection for multi-tenant filtering.
-   **RDO Photo Persistence System (v9.0.4):** Implements database-based base64 storage for RDO photos to ensure persistence across container restarts and deployments. Each photo is stored in 3 optimized versions: original WebP base64, optimized 1200px for viewing, and thumbnail 300px for gallery display. Backward compatible with legacy file-based photos through intelligent fallback rendering.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** Object Relational Mapper (ORM).
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Python templating language.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** Date/time utilities.