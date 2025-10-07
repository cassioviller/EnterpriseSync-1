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
    -   **Schema Alignment (Oct 2025):** CRITICAL alignment with production schema ensuring consistent use of `funcionario_id` across all environments.
        - **Production Discovery:** Production database uses `funcionario_id` (NOT NULL) in `uso_veiculo` table, not `motorista_id`
        - **Code Updates:** All Python models (models.py, views.py) updated to use `funcionario_id` consistently
        - **Auto-Migration:** Migrations 20 and 21 automatically rename `motorista_id` → `funcionario_id` in development environments
        - **Safety:** Completely idempotent, production (already correct) unchanged, development auto-corrects
        - **Zero Downtime:** No manual intervention required, migrations handle cross-environment differences automatically
    -   **Migration 20 (FIXED - Oct 2025):** Complete Fleet tables created (`fleet_vehicle`, `fleet_vehicle_usage`, `fleet_vehicle_cost`) with 100% data migration from legacy tables verified.
        - **Critical Fix 1 (FK):** Foreign key creation moved to separate ALTER TABLE statements (Part 3.5) AFTER all tables exist, eliminating "vehicle_id constraint does not exist" production error
        - **Critical Fix 2 (funcionario_id):** Part 4.5 verifies/renames to `funcionario_id` (production schema standard)
        - **Architecture:** Tables created WITHOUT inline FKs → All tables exist → FKs added via ALTER TABLE → funcionario_id verified/renamed → Data migrated
        - **Safety:** Each FK wrapped in try/except for resilience; single commit at end preserves atomicity; idempotent column creation
        - **Monitoring:** Production should alert if any ALTER TABLE FK statement fails in logs
    -   **Migration 21 (Schema Confirmation):** Confirms `funcionario_id` structure in legacy `uso_veiculo` table, renames `motorista_id` if found (development compatibility).
    -   **Migration 22 (Passageiros - Oct 2025):** Adiciona colunas `passageiros_frente` e `passageiros_tras` (TEXT) na tabela `uso_veiculo` para registro de passageiros do veículo (IDs separados por vírgula).
    -   **Migration 23 (Emergencial - DROP TABLE - BLOQUEADA):** Recria tabela `uso_veiculo` com schema correto. **BLOQUEADA POR SEGURANÇA** - requer `ALLOW_DESTRUCTIVE_MIGRATION=true` para executar. Não usar em produção sem backup completo.
    -   **Migration 24 (Passageiros Robusto - Oct 2025):** Adiciona colunas `passageiros_frente` e `passageiros_tras` com estratégia robusta: tratamento individual por coluna, commits explícitos, logging detalhado do SQL, não interrompe aplicação em caso de falha. Fornece SQL manual se ALTER TABLE falhar.
        - **Resiliência:** Não re-raise erros - aplicação continua mesmo se falhar
        - **Diagnóstico:** Detecta ambiente (dev/prod), loga SQL exato executado
        - **Fallback:** Se falhar, loga comandos SQL para execução manual no banco
        - **Idempotência:** Verifica existência antes de adicionar cada coluna
    -   **Phase 1 (Complete):** All critical fixes deployed, 100% automatic deployment achieved, production stabilized, schema alignment complete, legacy system operational with enhanced compatibility.
    -   **Estratégia de Migração em 3 Camadas (Oct 2025):**
        1. **Camada 1 (Migração 22):** Tentativa simples e idempotente de ALTER TABLE
        2. **Camada 2 (Migração 23):** Solução destrutiva (DROP TABLE) - bloqueada por feature flag
        3. **Camada 3 (Migração 24):** Solução robusta com fallback manual e logging detalhado
        - **Resultado:** Zero downtime garantido, aplicação sempre inicia, logs guiam correção manual se necessário
    -   **Migration 25 (ULTRA-ROBUSTA - SQL Puro - Oct 2025):** Solução definitiva para garantir colunas passageiros em produção usando SQL nativo do PostgreSQL.
        - **Tecnologia:** Blocos DO com IF NOT EXISTS emulado (compatível PostgreSQL 9.0+)
        - **Vantagens:** Execução direta no banco (não passa por ORM), commits separados por coluna, absolutamente idempotente
        - **Logging:** Detecta ambiente (dev/prod), mostra SQL exato executado, confirma colunas criadas
        - **Segurança:** Não re-raise erros, aplicação continua mesmo se falhar, fornece SQL para execução manual
        - **Status:** ✅ Testado e aprovado em desenvolvimento, pronto para produção
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