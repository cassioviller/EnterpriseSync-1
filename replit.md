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
The system employs a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 for server-side templating and Bootstrap for a responsive frontend. Docker is used for deployment, leveraging a unified `base_completo.html` template for consistent UI/UX. The codebase has been refactored from a monolithic `views.py` into a `views/` Python package with domain-specific modules, while maintaining existing routes and function names.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation per `admin_id` and implements robust role-based access control.
-   **Security Hardening:** Includes CSRF protection, restricted CORS, rate limiting on login, and secure handling of sensitive keys.
-   **Event-Driven Integration:** Uses an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Modern, responsive layouts with modular components, a cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, featuring elegant cards, gradients, and smooth animations.
-   **Automated Database Migrations:** `migrations.py` manages schema updates, including critical migrations for multi-tenancy.
-   **Atomic Transactions:** Critical operations are protected by `safe_db_operation` to ensure data integrity.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category displays.
-   **Company Customization:** Allows dynamic branding via logo uploads and custom color schemes.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automated calculations, real-time recalculation, HTML-based PDF generation, and a client portal with token-based access. Includes CRUD for attachments with intelligent image optimization.
    -   **Employee Management & Payroll:** Handles registration, automated time clocking, flexible work schedules, and automated CLT-compliant payroll calculations with dynamic PDF holerite generation and accounting integration.
    -   **Construction Project Management (RDO):** Manages Daily Work Reports, dynamic service progress, consolidated routing, and a comprehensive mobile-first photo upload system with automatic WebP optimization. Integrated with Cronograma V2 for task linking and progress tracking.
    -   **Costs Management:** Provides CRUD for construction costs, real-time statistics, and KPI dashboards. Includes detailed labor cost dashboards per project.
    -   **Accounting:** Supports double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, and DRE.
    -   **Fleet Management System:** Manages vehicles, expenses, TCO dashboards, and critical alerts.
    -   **Food Management System (Alimentação v2.0):** Mobile-first redesigned interface for managing restaurant and food entries with dynamic multi-item launching, searchable employee selection, and automatic cost calculation.
    -   **Warehouse Management:** Manages materials, tools, and PPE with traceability, full CRUD for suppliers, material flow workflows, manual batch/lot selection, serialized item status transitions, optimistic locking, and employee consumable tracking.
    -   **Compras de Materiais V2:** Manages purchase orders with dynamic item tables, automatic cost registration via `GestaoCustoPai` as single source of truth (migration #92 adds `pedido_compra_id` FK to `AlmoxarifadoMovimento`). "Registrar Recebimento" route creates stock entries without duplicating cost. Dashboard `calcular_custo_material()` reads `GestaoCustoPai` (`tipo_categoria IN MATERIAL/COMPRA`) instead of legacy `CustoObra`.
    -   **Portal do Cliente por Obra:** Public client portal (token-based, no login) showing obra progress, cronograma tasks, purchase approvals, and measurement reports. Blueprint `portal_obras_views.py` at `/portal/obra/<token>`. Clients can approve/reject purchases and upload payment receipts. Admin integration in obra detail page with portal link, copy button, and medição generation. Migration #107 adds `Fornecedor.chave_pix`, `PedidoCompra.status_aprovacao_cliente`/`comprovante_pagamento_url`, and `MedicaoObra` table.
    -   **Mapa de Concorrência V2:** Multi-supplier comparison table with N items × N suppliers grid. Admin creates mapa via `GET/POST /obras/<obra_id>/mapa-v2/<mapa_id>/editar` with inline add/remove of suppliers (columns) and items (rows). Cotação table shows per-cell (item × supplier) value and deadline fields with auto-highlight of minimum values. Client portal (`/portal/obra/<token>`) shows interactive table with JS radio-button selection, column-header click to select all rows for a supplier, green highlighting of cheapest per-row, and "Confirmar Seleção" to persist choices. Migration #112 creates `mapa_concorrencia_v2`, `mapa_fornecedor`, `mapa_item_cotacao`, `mapa_cotacao` tables. Models: `MapaConcorrenciaV2`, `MapaFornecedor`, `MapaItemCotacao`, `MapaCotacao`. Routes: `criar_mapa_v2`, `editar_mapa_v2`, `deletar_mapa_v2` in `views/obras.py`; `selecionar_mapa_v2` in `portal_obras_views.py`.
    -   **Medição Quinzenal de Obra:** Biweekly measurement engine with commercial items (`ItemMedicaoComercial`), weighted task linking (`ItemMedicaoCronogramaTarefa`), automated percentage calculation from cronograma progress, PDF extrato generation (ReportLab), and `ContaReceber` integration on approval. Blueprint `medicao_views.py` at `/medicao/obra/<obra_id>`. Service layer `services/medicao_service.py` handles `gerar_medicao_quinzenal`, `fechar_medicao`, and `gerar_pdf_extrato_medicao`. Obra fields: `data_inicio_medicao`, `valor_entrada`, `data_entrada`. Migration #108. Portal shows detailed medicao info with PDF download links.
    -   **Cronograma V2:** MS-Project-style Gantt chart with task hierarchy, planned vs actual progress, and interactive drag-and-drop for task duration and reordering with chain recalculation.
    -   **Gestão de Custos V2:** Centralized cost management with a 4-step approval workflow and integration with other modules for automatic cost registration.
    -   **Reembolsos V2:** Full CRUD for reimbursements, integrated with Gestão de Custos V2.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking, enhanced facial recognition verification (DeepFace library), multiple photo support, stricter recognition thresholds, geofencing, and photo quality validation.
-   **Automated Database Error Diagnostics:** A `DatabaseDiagnostics` system analyzes SQLAlchemy errors, reports missing columns, and generates diagnostic reports.
-   **Híbrido Data Model Support:** For food management, aggregates data from legacy and new models for seamless coexistence.
-   **Transaction Isolation for Deletions:** Critical deletion operations use RAW connections with `isolation_level="AUTOCOMMIT"` and incorporate schema introspection for multi-tenant filtering.
-   **FluxoCaixa Enhancements:** Migration #105 adds optional `banco_id` FK to `fluxo_caixa`. Import preview (`/importacao/fluxo-caixa/upload`) has grouped category optgroups (Custo Direto/Indireto/Despesa Administrativa including Retirada de Sócios), inline-editable Data/Valor/Descrição fields, Reembolso checkbox, and Banco dropdown per row. "Apenas pgto." creates only FluxoCaixa (no GCP/GCF/ContaPagar). Fluxo de Caixa list (`/financeiro/fluxo-caixa`) has "Nova Movimentação" modal (grouped categories, banco, obra) and AJAX-based inline cell editing for direct FluxoCaixa entries.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** Object Relational Mapper (ORM).
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Python templating language.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** Date/time utilities.
-   **DeepFace:** Facial recognition library.
-   **Flask-WTF:** For CSRF protection.
-   **Flask-Limiter:** For rate limiting.