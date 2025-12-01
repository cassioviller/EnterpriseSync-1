## Overview
SIGE v9.0 (Sistema de Gestão Empresarial) is a production-ready multi-tenant business management system for SMBs, validated through comprehensive E2E testing. Its purpose is to automate and streamline core operations, covering commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. The system aims to boost efficiency and provide comprehensive operational oversight from sales to project management and financial calculations, ultimately enhancing business management for SMBs.

## Recent Changes (December 2025)
- **Ponto Eletrônico Fix**: Refactored ponto_service.py to use FuncionarioObrasPonto association table instead of non-existent Funcionario.obra_atual_id field
- **E2E Testing Complete**: 13/13 modules tested and validated for production deployment
- **Mobile Responsiveness**: Verified mobile-first design on 375x667 viewport across all major modules

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
The system is built with a Flask backend, SQLAlchemy ORM, and PostgreSQL, utilizing Jinja2 for server-side templating and Bootstrap for responsive frontend styling. Docker is used for deployment, with a unified `base_completo.html` template for consistent UI/UX.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation per `admin_id` and implements robust role-based access control.
-   **Event-Driven Integration:** Uses an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles.
-   **Automated Database Migrations:** `migrations.py` manages schema updates, including critical migrations for multi-tenancy, vehicle tracking, schema synchronization, RDO photo optimization, and RDO photo base64 persistence.
-   **Atomic Transactions:** Critical operations are protected by `safe_db_operation` to ensure data integrity.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category displays.
-   **Company Customization:** Allows dynamic branding via logo uploads and custom color schemes.
-   **Core Modules:**
    -   **Proposal Management:** Features reusable templates with a multi-template loading system, automated calculations with inline editing, real-time total recalculation, HTML-based PDF generation, and history tracking. Includes a client portal with token-based access for viewing, approval, and rejection. Implements a complete CRUD for proposal attachments with intelligent image optimization (WebP conversion) and database-based Base64 storage for persistence.
    -   **Employee Management:** Handles registration, automated time clocking, and overtime calculations.
    -   **Construction Project Management (RDO):** Manages Daily Work Reports, dynamic service progress, consolidated routing, and a comprehensive mobile-first photo upload system with automatic WebP optimization, thumbnail generation, and database-based Base64 storage for photo persistence. Features an advanced filtering system.
    -   **Payroll:** Automates CLT-compliant calculations, late deduction processing, and dynamic PDF holerite generation with automated accounting integration.
    -   **Costs Management:** Provides CRUD for construction costs, real-time statistics, and KPI dashboards.
    -   **Accounting:** Supports double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, and DRE.
    -   **Fleet Management System:** Manages vehicles, expenses, TCO dashboards, and critical alert notifications.
    -   **Food Management System (Alimentação v2.0):** Manages restaurant and food entries with a **mobile-first redesigned interface**. Features a dynamic multi-item lancamento system with pre-registered items (AlimentacaoItem), searchable employee chips selector for quick multi-selection, automatic cost calculation per employee, and flexible item pricing. New database models: `alimentacao_item` (pre-registered food items with default prices), `alimentacao_lancamento_item` (items per lancamento). Routes: `/alimentacao/lancamentos/novo-v2` for new mobile-first form, `/alimentacao/itens` for item management CRUD. Default "Marmita" item auto-created if no items exist. Integrates with financial module via EventManager.
    -   **Warehouse Management:** Manages materials, tools, and PPE with traceability, including a complete CRUD system for supplier management with multi-tenant isolation, soft delete, and robust validation. Features comprehensive material flow workflows (entrada/saída/devolução) with correct `funcionario_atual_id` tracking in AlmoxarifadoEstoque, and an enhanced API endpoint that returns all consumable items with `permite_devolucao` flag for frontend decision-making. Implements full CRUD for manual movements with advanced features: multi-lot support with **Manual Batch/Lot Selection** (users explicitly choose which batches to consume instead of automatic FIFO, allowing strategic cost optimization), serialized item status transitions (DISPONIVEL ↔ EM_USO), optimistic locking with `updated_at` timestamps to prevent concurrent edit conflicts, stock validation preventing negative balances, and rollback mechanisms for safe edits/deletions. Manual movements are flagged with `origem_manual=True` and can be edited/deleted via UI, while system-generated movements remain read-only. **Manual Batch Selection System:** During saída operations, consumable items display all available batches with checkboxes and quantity inputs; real-time JavaScript validation ensures allocated quantities match the total saída; backend validates batch ownership, availability, and quantity constraints before processing; system supports both manual selection mode (when lote_allocations provided) and legacy FIFO fallback (when not provided). **Employee Consumable Tracking:** Tracks employee possession of both serialized AND consumable items with new 'CONSUMIDO' movement type. Net possession calculated as: SAIDA - DEVOLUCAO - CONSUMIDO. Devolução page features dual-action buttons ('Devolver' for returns, 'Consumido' for consumed materials). Employee profiles display comprehensive possession tracking with automatic aggregation across all movement types. Route `/almoxarifado/processar-consumo` handles consumption processing with quantity validation.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking and an advanced Excel import system for batch point records.
-   **Automated Database Error Diagnostics:** A `DatabaseDiagnostics` system analyzes SQLAlchemy errors, reports missing columns, and generates diagnostic reports, integrated with `@capture_db_errors` decorators.
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