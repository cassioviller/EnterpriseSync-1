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
-   **Fleet Management System (RECRIADO - Oct 2025):** Sistema de veículos completamente recriado com backend limpo e migração 32.
    -   **ARQUITETURA ATUAL (Outubro 2025 - Migração 32):**
        - **Modelos Backend:** `Vehicle`, `VehicleUsage`, `VehicleExpense` (models.py linhas 3229-3327)
        - **Aliases para Compatibilidade:** `FrotaVeiculo=Vehicle`, `FrotaUtilizacao=VehicleUsage`, `FrotaDespesa=VehicleExpense`
        - **Tabelas Atuais:** `frota_veiculo`, `frota_utilizacao`, `frota_despesa` (produção)
        - **Tabelas Novas (Migração 32):** `vehicle`, `vehicle_usage`, `vehicle_expense`
        - **Blueprint:** `frota_bp` (frota_views.py) com rotas `/frota/*`
        - **Relacionamentos:** Mantidos `.usos` e `.custos` para compatibilidade total
        - **Campos Completos:** 18 campos incluindo manutenção (data_ultima_manutencao, data_proxima_manutencao, km_proxima_manutencao)
        - **Multi-tenant:** Todos os modelos incluem `admin_id NOT NULL` com isolamento completo
    -   **Migration 26 (LIMPEZA - Oct 2025):** DROP CASCADE de todas as tabelas antigas do sistema de veículos.
        - **Tabelas Removidas:** `veiculo`, `uso_veiculo`, `custo_veiculo`, `fleet_vehicle`, `fleet_vehicle_usage`, `fleet_vehicle_cost`
        - **Feature Flag:** Requer `DROP_OLD_VEHICLE_TABLES=true` para executar (bloqueada por padrão)
        - **Processo:** Verifica existência → DROP CASCADE → Commit → Logging detalhado
        - **Segurança:** Idempotente, não re-raise erros, aplicação continua mesmo se falhar
        - **Status:** ✅ Pronta para ativação após validação funcional
    -   **HISTÓRICO DE MIGRAÇÕES ANTIGAS (Outubro 2025):**
        - **Migrações 20-25:** Tentativas de adicionar colunas passageiros em `uso_veiculo` - TODAS FALHARAM em produção
        - **Problema Root:** Schema inconsistente entre dev/prod impossibilitou ALTER TABLE confiável
        - **Solução Final:** Reescrita completa do backend com novos nomes (Frota*) em vez de migrações
    -   **MIGRAÇÕES CRÍTICAS DE CORREÇÃO (Out 2025):**
        - **Migração 28:** Migração de dados `veiculo/uso_veiculo/custo_veiculo` → `frota_*` (✅ Aplicada)
        - **Migração 29:** Correção `data_id` → `data_custo` em `frota_despesa` (✅ Aplicada)
        - **Migração 30 (Out 2025):** Adiciona coluna `obra_id` em `frota_despesa` em produção
            - **Problema:** Tabela criada sem FK para obras em produção
            - **Solução:** `ALTER TABLE frota_despesa ADD COLUMN obra_id INTEGER REFERENCES obra(id)`
            - **Índice:** Cria `idx_frota_despesa_obra_id` para performance
            - **Status:** ✅ Implementada, idempotente, pronta para deploy
        - **Migração 31 (LIMPEZA COMPLETA - Out 2025):** Remove TODAS as tabelas antigas de veículos
            - **Problema:** Coexistência de 3 arquiteturas (veiculo, fleet_*, frota_*)
            - **Solução:** DROP CASCADE de tabelas legacy e fleet, mantém apenas frota_*
            - **Segurança:** Requer `DROP_OLD_VEHICLE_TABLES=true` (bloqueada por padrão)
            - **Status:** ✅ Implementada, aguardando ativação manual
        - **Migração 32 (RECREAÇÃO COMPLETA - Out 2025):** Recria sistema de veículos com backend limpo
            - **Problema:** Código legacy (FrotaVeiculo) misturado, dificultando manutenção
            - **Solução:** Novos modelos (Vehicle, VehicleUsage, VehicleExpense) + aliases para compatibilidade
            - **Processo:** CREATE vehicle_* → MIGRAR dados de frota_* → DROP frota_*
            - **Segurança:** Requer `RECREATE_VEHICLE_SYSTEM=true` (bloqueada por padrão)
            - **Campos Preservados:** Todos os 18 campos incluindo manutenção
            - **Relacionamentos:** `.usos` e `.custos` mantidos para compatibilidade total
            - **Status:** ✅ Implementada, aguardando ativação manual
    -   **Status Atual (Out 2025):**
        - ✅ Sistema Frota funcionando (tabelas frota_* em produção)
        - ✅ Backend recriado com modelos Vehicle* + aliases para compatibilidade
        - ✅ Migração 32 implementada e aguardando ativação (RECREATE_VEHICLE_SYSTEM=true)
        - ✅ Campos de manutenção preservados (data_ultima_manutencao, data_proxima_manutencao, km_proxima_manutencao)
        - ✅ Relacionamentos compatíveis (.usos, .custos) funcionando perfeitamente
        - ✅ Health check passando: `{"database":"connected","status":"healthy"}`
        - 🎯 Próximo passo: Ativar feature flag para migração de produção frota_* → vehicle_*
        - ✅ Redirecionamentos: `/veiculos` → `/frota` (HTTP 307 preserva POST)
    -   **Deployment Strategy:** 100% automático, zero intervenção manual, feature flag garante segurança.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.