# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system for SMBs, streamlining core operations such as commercial proposals, employee management, construction project control (Daily Work Reports - RDO), and automated payroll. It aims to enhance efficiency from sales to construction site management and complex payroll calculations.

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

## Recent Changes
- **2025-10-16:** CRITICAL ACCURACY & SECURITY FIX - Correção Completa de Cálculos Financeiros e Isolamento Multi-Tenant - (1) Eliminados 9 cálculos incorretos que usavam valores fixos (salario/220, salario/22) causando erros de 8-15% em TODOS os KPIs financeiros. Substituídos por funções dinâmicas de utils.py: calcular_valor_hora_periodo() calcula horas baseadas no período real + calendar.monthrange() para dias úteis reais. Funções corrigidas: _calcular_custos_obra, dashboard mão de obra, calcular_faltas_justificadas, funcionarios KPIs, funcionario_perfil, funcionario_perfil_pdf, obras, detalhes_obra. (2) Adicionados 14 filtros admin_id em kpis_engine.py (12 queries) e kpis_engine_v8_1.py (2 queries) para garantir isolamento completo de dados entre empresas em todas as consultas de RegistroPonto. (3) Corrigido erro float + Decimal no dashboard que causava crash em produção. Architect-reviewed: Todas correções validadas sem regressões ou problemas de segurança.
- **2025-10-16:** CRITICAL SECURITY FIX - Multi-Tenant Isolation nos KPIs Financeiros - Corrigidas 5 queries do dashboard que permitiam vazamento de dados entre empresas: (1) VehicleExpense adicionou filtro admin_id, (2) RegistroAlimentacao implementou JOIN com Funcionario.admin_id (tabela não tem admin_id direto), (3) OutroCusto (alimentação) adicionou filtro admin_id, (4) Faltas Justificadas filtram RegistroPonto.admin_id, (5) Outros Custos filtram OutroCusto.admin_id. Verificado em produção: KPIs agora isolados por tenant sem cross-contamination.
- **2025-10-16:** CRITICAL FIX - UnboundLocalError em Produção Resolvido - Removidas 12 reimportações locais de `datetime` em views.py que causavam UnboundLocalError apenas em ambiente Docker/Gunicorn (produção). Python analisa escopo durante compilação e marcava datetime como variável local devido aos imports internos. Sistema agora usa apenas import global (linha 9). Margem de Lucro adicionada ao dashboard com cálculo correto (100% quando custos=0, suporte a margens negativas), card com cores condicionais (verde/vermelho).
- **2025-10-15:** Folha de Pagamento v2.0 - Processamento real com cálculos automáticos (INSS progressivo, IRRF com deduções, FGTS 8%, horas extras, DSR). Integração completa com Ponto Eletrônico para cálculo automático de horas trabalhadas, extras e faltas. Event-driven integration para lançamentos contábeis automáticos.
- **2025-10-15:** Contabilidade Automática - Sistema de lançamentos contábeis com partidas dobradas automáticas a partir da folha de pagamento. Handler de eventos `folha_processada` cria lançamentos (débito em despesas, crédito em salários a pagar/INSS/IRRF) e aloca custos às obras automaticamente.
- **2025-10-15:** DRE Automática - Demonstração do Resultado do Exercício calculada automaticamente a partir dos lançamentos contábeis. Agrupa contas por prefixo (Receitas 4.x, Custos 3.1.x, Despesas 3.2.x) e calcula lucro bruto e líquido mensalmente.
- **2025-10-15:** Toggle Ativo/Finalizado em Obras - Botão fácil na página de detalhes permite alternar status da obra entre ATIVO (verde) e FINALIZADO (cinza). Obras finalizadas são automaticamente removidas de todos os dropdowns do sistema (RDO, Almoxarifado, Financeiro, etc).
- **2025-10-15:** Dashboard fully dynamized - All proposal KPIs now calculated from live database (status counts, conversion rate, average value, template usage, portal analytics). Replaced all hardcoded values with real-time queries scoped by tenant admin_id.
- **2025-10-15:** Dashboard reorganized by module - KPIs now grouped in clear sections with Financeiro e Custos as first priority, followed by Visão Geral, Recursos Humanos, Obras e RDO, and Propostas Comerciais as last. Green gradient section headers (#10b981 to #059669) for improved scannability and brand alignment.

## System Architecture
The system uses a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 templates and Bootstrap for the frontend. Docker manages deployment. A unified modern template (`base_completo.html`) ensures consistent UI/UX. Critical database transaction protection is implemented via a `safe_db_operation` function.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with role-based access control and dynamic `admin_id` handling.
-   **Dynamic Dashboard KPIs:** All metrics calculated in real-time from database with zero-division guards and error handling. Proposal metrics include status distribution, conversion rates, average values, and template usage analytics.
-   **Event-Driven Integration System (v9.0):** `EventManager` (event_manager.py) implements Observer Pattern for automated cross-module integration. Active integrations:
    -   Almoxarifado → Custos: Material withdrawals emit `material_saida` events with cost tracking
    -   Frota → Custos: Vehicle usage emits `veiculo_usado` events calculating fuel/wear costs (R$0.80/km)
    -   Folha de Pagamento → Contabilidade → Custos: Payroll processing emits `folha_processada` events creating double-entry accounting records and obra cost allocation
    -   Handlers use structured logging for audit trail and maintain transactional integrity
    -   5 events registered at startup: material_saida, veiculo_usado, ponto_registrado, proposta_aprovada, folha_processada
-   **UI/UX Design:** Professional design system following modern UX/UI guidelines, including responsive grid layouts, modular components, a cohesive color palette (primary green #198754), hierarchical typography, consistent spacing, advanced visual states, real-time validation, and WCAG accessibility. Mobile-First Design is applied for modules like RDO, optimizing for touch and including PWA meta tags.
-   **Automated Database Migrations:** `migrations.py` handles schema updates automatically at application initialization, logging all operations and optimized for quick startup.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automatic calculations, categorization, filtering, custom numbering, professional PDF generation, and history tracking.
    -   **Employee Management:** Full registration with photo support, automated time clocking, and overtime/lateness calculation.
    -   **Construction Project Management (RDO):** Control of projects with Daily Work Reports, employee and equipment allocation, featuring a modernized card-based interface and dynamic service progress calculation.
    -   **Payroll:** Automatic calculation based on time clock records and configurable salaries.
    -   **Fleet Management System:** Manages vehicles, usage, and expenses.
    -   **Food Management System:** Card-based interface for managing restaurants and food entries.
    -   **Almoxarifado v3.0 (Warehouse Management):** Complete system for materials, tools, and PPE with full traceability, multi-tenant isolation, serialized and consumable control types, CRUD, movement tracking (ENTRADA/SAIDA/DEVOLUCAO), dashboards, reports, and employee profile integration.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock system allowing multiple employees to punch in/out from a single device per construction site, with GPS tracking, real-time status updates, and configurable schedules.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content pagination, and multi-category proposal display.
-   **Company Customization:** Allows dynamic branding with logo uploads and custom colors.
-   **Drag-and-Drop Organization:** System for organizing proposals by dragging and dropping multiple templates.
-   **Atomic Transactions:** Ensures data integrity for critical operations.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.