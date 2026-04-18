## Overview
SIGE v9.0 (Sistema de Gestão Empresarial) is a production-ready, multi-tenant business management system for Small and Medium-sized Businesses (SMBs). It automates and streamlines critical operations such as commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. The system aims to boost operational efficiency, provide comprehensive oversight from sales to project management and financial calculations, and enhance overall business management.

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
The system uses a Flask backend, SQLAlchemy ORM, PostgreSQL database, Jinja2 for server-side templating, and Bootstrap for the frontend. Docker is used for deployment, leveraging a unified `base_completo.html` template. The codebase is refactored into a `views/` Python package with domain-specific modules.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation and robust role-based access control.
-   **Security Hardening:** Includes CSRF protection, restricted CORS, rate limiting, and secure key handling.
-   **Event-Driven Integration:** Uses an `EventManager` (Observer Pattern) for automated cross-module data flow.
-   **UI/UX Design:** Modern, responsive layouts with modular components, cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design principles, featuring elegant cards, gradients, and smooth animations.
-   **Automated Database Migrations:** `migrations.py` manages schema updates.
-   **Atomic Transactions:** Critical operations are protected by `safe_db_operation` for data integrity.
-   **Dynamic PDF Generation:** Supports custom headers and dynamic content.
-   **Company Customization:** Allows dynamic branding via logo uploads and custom color schemes.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automated calculations, real-time recalculation, HTML-based PDF generation, client portal with token-based access, and attachment CRUD with image optimization.
    -   **Employee Management & Payroll:** Handles registration, automated time clocking, flexible schedules, automated CLT-compliant payroll, dynamic PDF holerite generation, and accounting integration.
    -   **Construction Project Management (RDO):** Manages Daily Work Reports, dynamic service progress, consolidated routing, mobile-first photo upload with WebP optimization, and integration with Cronograma V2.
    -   **Costs Management:** CRUD for construction costs, real-time statistics, KPI dashboards, and labor cost dashboards.
    -   **Accounting:** Supports double-entry bookkeeping, automated journal entries, chart of accounts, trial balance, and DRE.
    -   **Fleet Management System:** Manages vehicles, expenses, TCO dashboards, and critical alerts.
    -   **Food Management System (Alimentação v2.0):** Mobile-first interface for managing restaurant and food entries with dynamic multi-item launching, searchable employee selection, and automatic cost calculation.
    -   **Warehouse Management:** Manages materials, tools, and PPE with traceability, full CRUD for suppliers, material flow workflows, batch/lot selection, serialized item status transitions, optimistic locking, and employee consumable tracking.
    -   **Compras de Materiais V2:** Manages purchase orders with dynamic item tables and automatic cost registration. Features a "Registrar Recebimento" route for stock entries and a dashboard for material cost calculation.
    -   **Portal do Cliente por Obra:** Public client portal (token-based) showing project progress, cronograma tasks, purchase approvals, and measurement reports. Clients can approve/reject purchases and upload payment receipts.
    -   **Mapa de Concorrência V2:** Multi-supplier comparison table with N items × N suppliers grid. Supports admin creation, inline editing, minimum value highlighting, and interactive client selection via a portal.
    -   **Medição Quinzenal de Obra:** Biweekly measurement engine with commercial items, weighted task linking, automated percentage calculation from cronograma progress, PDF extrato generation, and `ContaReceber` integration on approval. Manages a single, cumulative `ContaReceber` per project.
    -   **Ciclo Proposta → Obra → Medido → ContaReceber:** Automates the lifecycle from proposal approval to project creation, commercial item linking, and cumulative `ContaReceber` generation based on measured progress.
    -   **Cronograma V2:** MS-Project-style Gantt chart with task hierarchy, planned vs actual progress, and interactive drag-and-drop for task management.
    -   **Cronograma Automático na Aprovação da Proposta (Task #102):** Cada Servico pode ter um `template_padrao_id` (CronogramaTemplate). Ao clicar "Aprovar" em uma proposta com itens vinculados a serviços com template, o admin é levado à tela `/propostas/<id>/cronograma-revisar` onde vê a árvore consolidada Serviço→Grupo→Subatividade e marca/desmarca nós antes de confirmar. Ao submeter, o snapshot é persistido em `Proposta.cronograma_default_json` e o handler `handle_proposta_aprovada` chama `services.cronograma_proposta.materializar_cronograma()` (idempotente via `TarefaCronograma.gerada_por_proposta_item_id`) que cria a hierarquia de 3 níveis em `TarefaCronograma` + `ItemMedicaoCronogramaTarefa` com peso por horas (fallback divisão igual). Tudo na mesma transação atômica de Obra/IMC/contábil.
    -   **Gestão de Custos V2:** Centralized cost management with a 4-step approval workflow and integration with other modules for automatic cost registration. Supports per-line CRUD for cost items.
    -   **Reembolsos V2:** Full CRUD for reimbursements, integrated with Gestão de Custos V2.
    -   **Catálogo de Serviços + Orçamento Paramétrico:** Cross-project catalog of inputs (`Insumo`) with versioned price history. Services have compositions (input × coefficient) and calculated selling prices. Integrates with proposals and commercial measurements.
    -   **Cálculo Paramétrico — Explosão de Insumos:** Persists a snapshot of service cost breakdown by input (material, labor, equipment) when saving `PropostaItem` and `ItemMedicaoComercial`. Provides an API endpoint for real-time explosion and server-side recalculation.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking, enhanced facial recognition verification, multiple photo support, stricter recognition thresholds, geofencing, and photo quality validation.
    -   **Métricas de Funcionários (v1+v2):** Serviço único `services/funcionario_metrics.py` calcula KPIs/custos suportando salaristas (v1: salário fixo, fórmula horas × valor_hora + extras × 1.5) e diaristas (v2: valor_diaria × dias_pagos + equivalente para extras). Decisão de modo respeita override por funcionário (`Funcionario.tipo_remuneracao`) sobre tenant (`is_v2_active()`). Custo total agrega MO + VA + VT (× dias_pagos) + Alimentação real híbrida (RegistroAlimentacao + AlimentacaoLancamento + rateio M2M) + Reembolsos + Almoxarifado em posse (consumível e serializado). Consumido por `views/employees.py` (lista, perfil, PDF), `views/dashboard.py` (loop por funcionário usa apenas `custo_mao_obra` para evitar double-count com agregações de tenant), `api_funcionarios.py` (valor/hora) e `relatorios_funcionais.py` (relatório de horas extras).
-   **Automated Database Error Diagnostics:** A system to analyze SQLAlchemy errors, report missing columns, and generate diagnostic reports.
-   **Híbrido Data Model Support:** For food management, aggregates data from legacy and new models.
-   **Transaction Isolation for Deletions:** Critical deletion operations use RAW connections with `isolation_level="AUTOCOMMIT"` and schema introspection for multi-tenant filtering.
-   **FluxoCaixa Enhancements:** Adds optional `banco_id` FK. Features import preview with grouped categories, inline-editable fields, and a modal for new movements with AJAX-based inline editing.

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