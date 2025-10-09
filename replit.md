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
-   **Fleet Management System (SIMPLIFICADO - Oct 2025):** Sistema de veículos com migração unificada inteligente.
    -   **ARQUITETURA ATUAL (Outubro 2025):**
        - **Modelos Backend:** `Vehicle`, `VehicleUsage`, `VehicleExpense` (models.py linhas 3229-3327)
        - **Aliases para Compatibilidade:** `FrotaVeiculo=Vehicle`, `FrotaUtilizacao=VehicleUsage`, `FrotaDespesa=VehicleExpense`
        - **Tabelas Atuais:** `frota_veiculo`, `frota_utilizacao`, `frota_despesa` (produção)
        - **Tabelas Alvo:** `vehicle`, `vehicle_usage`, `vehicle_expense` (criadas pela Migração 20)
        - **Blueprint:** `frota_bp` (frota_views.py) com rotas `/frota/*`
        - **Relacionamentos:** Mantidos `.usos` e `.custos` para compatibilidade total
        - **Campos Completos:** 18 campos incluindo manutenção (data_ultima_manutencao, data_proxima_manutencao, km_proxima_manutencao)
        - **Multi-tenant:** Todos os modelos incluem `admin_id NOT NULL` com isolamento completo
    -   **MIGRAÇÃO 20 UNIFICADA (Out 2025):** UMA ÚNICA migração inteligente que substitui 13 migrações fragmentadas (antigas 20-32).
        - **Detecção Inteligente:** Detecta estado atual do banco (frota_*, vehicle_*, ou vazio)
        - **Processo Adaptativo:**
            1. Se `frota_*` existem e `vehicle_*` não: CREATE → MIGRAR → DROP
            2. Se `vehicle_*` já existem: SKIP (idempotente)
            3. Se nenhuma existe: CREATE do zero
        - **Preservação de Dados:** 100% dos campos migrados (18 campos por tabela)
        - **Feature Flag:** `RECREATE_VEHICLE_SYSTEM=true` (bloqueada por padrão)
        - **Idempotente:** Pode executar múltiplas vezes com segurança
        - **Logging Detalhado:** Todas as operações são registradas
        - **Redução de Código:** 1.331 linhas removidas (38.5% mais limpo)
    -   **MIGRAÇÃO 33 (CORREÇÃO PRODUÇÃO - Out 2025):** Recria tabela frota_despesa com schema completo.
        - **Problema:** Produção sem coluna `obra_id`, causando erro ao registrar despesas
        - **Solução:** Backup → DROP → CREATE → RESTORE (7 passos seguros)
        - **Processo:**
            1. Verifica existência da tabela
            2. Backup em tabela temporária
            3. DROP CASCADE da tabela antiga
            4. CREATE com schema completo (17 colunas)
            5. RESTORE dos dados do backup
            6. Ajusta sequence com NULL safety
            7. Remove backup temporário
        - **Schema Completo:** 17 campos (id, veiculo_id, **obra_id**, data_custo, tipo_custo, valor, descricao, fornecedor, numero_nota_fiscal, data_vencimento, status_pagamento, forma_pagamento, km_veiculo, observacoes, admin_id, created_at, updated_at)
        - **Feature Flag:** `RECREATE_FROTA_DESPESA=true` (bloqueada por padrão)
        - **Testado:** ✅ Dev - 5 registros preservados 100%
        - **Status:** ✅ Pronta para produção
    -   **Status Atual (Out 2025):**
        - ✅ Sistema Frota funcionando (tabelas frota_* em produção)
        - ✅ Backend limpo com modelos Vehicle* + aliases para compatibilidade
        - ✅ Migração 20 unificada implementada e bloqueada por segurança
        - ✅ Migração 33 resolve divergência dev/prod na tabela frota_despesa
        - ✅ Código 38.5% mais simples (1 migração vs 13 fragmentadas)
        - ✅ Campos de manutenção preservados em todos os cenários
        - ✅ Relacionamentos compatíveis (.usos, .custos) funcionando perfeitamente
        - ✅ Health check passando: `{"database":"connected","status":"healthy"}`
        - 🎯 Próximo passo: Ativar `RECREATE_FROTA_DESPESA=true` em produção
        - ✅ Redirecionamentos: `/veiculos` → `/frota` (HTTP 307 preserva POST)
    -   **Deployment Strategy:** 100% automático, migrações inteligentes adaptam-se ao ambiente, feature flags garantem segurança total.
-   **Food Management System (REFORMULADO - Oct 2025):** Sistema de alimentação com interface card-based moderna.
    -   **ARQUITETURA (Outubro 2025):**
        - **Modelos Backend:** `Restaurante`, `AlimentacaoLancamento` (models.py)
        - **Tabelas:** `restaurante`, `alimentacao_lancamento`, `alimentacao_funcionarios_assoc`
        - **Blueprint:** `alimentacao_bp` (alimentacao_views.py) com rotas `/alimentacao/*`
        - **Campos de Pagamento (Migração 34):** razao_social, cnpj, pix, nome_conta
        - **Multi-tenant:** Todos os modelos incluem `admin_id NOT NULL` com isolamento completo
    -   **INTERFACE UX (Out 2025):**
        - **Página Principal (`/alimentacao/`):** Cards elegantes com gradiente verde, exibindo restaurantes cadastrados
        - **Página Detalhes (`/alimentacao/restaurante/<id>`):** Informações completas do restaurante + tabela de lançamentos
        - **Fluxo de Navegação:** Cards → Detalhes → Lançamentos (integração completa)
        - **Dados de Pagamento:** Razão social, CNPJ, PIX e nome da conta exibidos na página de detalhes
    -   **MIGRAÇÃO 27 (Sistema Base):** Criação das tabelas restaurante, alimentacao_lancamento, alimentacao_funcionarios_assoc
    -   **MIGRAÇÃO 34 (Campos Pagamento):** Adição de 4 campos de pagamento no modelo Restaurante
    -   **Status Atual (Out 2025):**
        - ✅ Interface reformulada com cards modernos (substituiu lista tradicional)
        - ✅ Página de detalhes dedicada com informações completas
        - ✅ Campos de pagamento implementados (razao_social, cnpj, pix, nome_conta)
        - ✅ Navegação fluida entre restaurantes e lançamentos
        - ✅ Multi-tenant funcionando perfeitamente
        - ✅ Templates modernos alinhados com design system do SIGE
-   **Deploy Optimization (Oct 2025):** Sistema de migrações otimizado para startup rápido.
    -   **Problema Resolvido:** Migrações antigas causavam lentidão no deploy (262+ linhas de log)
    -   **Solução Implementada:** Migrações 1-19 desativadas (já aplicadas em produção)
    -   **Migrações Ativas:** Apenas 20, 27, 33, 34 executam no startup
    -   **Resultado:** Redução de 94% nos logs de migração (262→15 linhas)
    -   **Performance:** Deploy significativamente mais rápido em produção
    -   **Histórico Preservado:** Funções antigas mantidas comentadas para referência
    -   **Rollback:** Para reativar migrações antigas, descomentar linhas 700-757 em migrations.py

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.