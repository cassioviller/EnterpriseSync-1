# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed to streamline core business operations for the SMB sector. It offers comprehensive solutions for commercial proposals, employee management, construction project control (Daily Work Reports - RDO), and automated payroll. The system aims to enhance efficiency from sales proposal generation and complex payroll calculations to construction site management.

## Recent Changes
**October 13, 2025:**
- Fixed construction site details page to show only employees who clocked in (based on ponto records)
- Implemented dynamic service progress calculation from RDO data using `calcular_progresso_real_servico` function
- Fixed critical bug where service progress regressed to 0% when newer RDOs omitted subactivities - now aggregates latest value per subactivity across all RDOs using MAX(id) grouped by subactivity name
- Architect approved service progress fix with recommendations for future improvements (temporal fields, duplicate validation, performance monitoring)

**October 10, 2025:**
- Added Almoxarifado v3.0 (Warehouse Management Module) - Complete system for managing materials, tools, and PPE with full traceability and multi-tenant isolation

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
    -   **Almoxarifado v3.0 (Warehouse Management):** Complete warehouse management system for materials, tools, and PPE control with full traceability and multi-tenant isolation. Features serialized (individual tracking) and consumable (quantity-based FIFO) control types, comprehensive CRUD operations, movement tracking (ENTRADA/SAIDA/DEVOLUCAO), dashboard with KPIs and alerts, advanced reports, and integration with employee profiles. Includes 4 models (AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento) managed by feature-flagged Migration 39.
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

---

### Módulo Almoxarifado v3.0 (SIGE v8.0)
Sistema completo de gestão de almoxarifado para controle de materiais, ferramentas e EPIs com rastreabilidade total e isolamento multi-tenant.

**Arquitetura:**
- **4 Modelos:** AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento
- **Migração 39:** Feature-flagged (CREATE_ALMOXARIFADO_SYSTEM=true), cria 4 tabelas com índices de performance
- **Blueprint:** almoxarifado_bp (prefixo /almoxarifado) registrado em views.py

**Tipos de Controle:**
1. **SERIALIZADO:** Controle unitário por número de série (martelos, furadeiras, EPIs)
   - Rastreabilidade individual
   - Devolução obrigatória (permite_devolucao=True automático)
   - Status: DISPONIVEL, EM_USO, EM_MANUTENCAO

2. **CONSUMIVEL:** Controle por quantidade com FIFO (cimento, parafusos, tintas)
   - Controle quantitativo
   - Consumo sem devolução ou devolução configurável
   - Baixa automática por saída

**Funcionalidades Principais:**

1. **CRUD Completo:**
   - Categorias (nome, tipo padrão, ativo)
   - Itens (código, nome, tipo_controle, estoque_minimo, permite_devolucao)
   - Validação automática: SERIALIZADO força permite_devolucao=True

2. **Sistema de Movimentações:**
   - **ENTRADA:** Registro de compras/recebimentos (obra_id=NULL, fornecedor)
   - **SAIDA:** Vinculação funcionário+obra, baixa FIFO para consumíveis
   - **DEVOLUCAO:** Registro de condição (BOM, DANIFICADO, PERDIDO), volta ao estoque

3. **Dashboard (/almoxarifado/):**
   - 4 KPIs: Total Itens, Estoque Baixo, Movimentos Hoje, Valor Total
   - 3 Alertas: Estoque Baixo, Vencendo, Em Manutenção
   - Últimas 10 Movimentações com badges coloridos

4. **Relatórios (/almoxarifado/relatorios):**
   - Posição de Estoque (por categoria, subtotais)
   - Movimentações por Período (filtros avançados)
   - Itens por Funcionário (em posse, valor total)
   - Consumo por Obra (saídas não devolvidas)
   - Alertas e Pendências (estoque baixo, manutenção, >30 dias)

5. **Integração Funcionários:**
   - Seção Almoxarifado no perfil (funcionario_perfil.html)
   - Mostra itens EM_USO com valor total
   - Link direto para detalhes no almoxarifado

**APIs Internas:**
- GET /api/item/<id>: Detalhes item (tipo_controle, permite_devolucao)
- GET /api/estoque-disponivel/<item_id>: Estoque disponível para saída
- GET /api/itens-funcionario/<id>: Itens em posse do funcionário

**Segurança Multi-Tenant:**
- TODAS as queries filtradas por admin_id
- Isolamento total entre tenants em categorias/itens/estoque/movimentos
- obra_id nullable=True (ENTRADAs não têm obra associada)

**Validação End-to-End (Task 16):**
✅ 7 fluxos testados com sucesso
✅ Bugs corrigidos na Migração 39 (obra_id nullable + colunas adicionadas)
✅ Sistema pronto para produção