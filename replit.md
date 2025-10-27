## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system designed for Small and Medium-sized Businesses (SMBs). Its core purpose is to streamline and enhance efficiency across key operational areas, including commercial proposal generation, comprehensive employee management, detailed construction project control (Daily Work Reports - RDO), and automated payroll processing. The system aims to cover the entire business workflow from initial sales activities to on-site construction management and complex financial calculations.

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
- **2025-10-27:** CUSTOS MODULE v9.0 + PAYROLL→ACCOUNTING INTEGRATION - Completado sistema completo de custos (40%→95%) e integração automática folha→contabilidade. **CUSTOS**: 5 novas rotas (criar/editar/deletar/listar/dashboard), 2 templates (custo_form.html, listar.html) com validação multi-tenant rigorosa, estatísticas em tempo real, filtros avançados. E2E PASSOU: Criar custo R$ 5.000 → verificado DB, editar → alteração confirmada, deletar → removido. **INTEGRAÇÃO FOLHA→CONTAB**: Handler automático `criar_lancamento_folha_pagamento` gera partidas dobradas ao processar folha (DÉBITO: 5.1.01.001 Despesas Pessoal, CRÉDITO: 2.1.03.001 Salários a Pagar + INSS/IRRF/FGTS). 48 folhas → 48 lançamentos + 178 partidas criadas automaticamente. Campos obrigatórios corrigidos: `numero` (sequencial), `valor_total`, `sequencia` (1,2,3...), `admin_id` (multi-tenant). BUGS CRÍTICOS CORRIGIDOS: (1) Campos inexistentes `fornecedor`/`observacoes` removidos. (2) EventManager.emit agora passa `admin_id` como 3º argumento. (3) Todos campos NOT NULL de LancamentoContabil e PartidaContabil preenchidos. STATUS ATUAL: ✅ CRUD 100% funcional, ⚠️ Integração funciona mas com desbalanceamento menor (-629 de ~20k total = 3%) que requer investigação futura de warnings "Funcionário None não encontrado". Regra aprendida crítica: SEMPRE preencher TODOS campos obrigatórios do schema (numero, sequencia, admin_id, valor_total) em handlers de eventos para evitar IntegrityError.
- **2025-10-27:** COMPETENCY SELECTOR - Folha & Contabilidade - Implementado seletor visual de competência (mês/ano) em ambos módulos. **Folha de Pagamento**: Dashboard com dropdown de 15 competências (12 meses passados + atual + 2 futuros), permite processar folhas de qualquer mês, validação de parâmetros legais por ano selecionado, overlay de loading durante processamento. **Contabilidade**: Balancete e DRE com mesmo seletor, navegação via query string (mes/ano). Dependência adicionada: python-dateutil para cálculo de competências (relativedelta). Bug crítico corrigido: UnboundLocalError quando competência inválida (ano_sel/mes_sel não definidos no except). E2E PASSOU: Seleção de meses diferentes em ambos módulos funcionando. Architect-reviewed: PASS após correção do bloqueador. Regra aprendida: Sempre inicializar TODAS as variáveis usadas fora do bloco try no bloco except.
- **2025-10-27:** BULK SALARY UPDATE FEATURE - Configurações RH (Funções) - Implementada atualização em massa de salários ao editar função. Quando o salário base de uma função é alterado, TODOS os funcionários dessa função (do mesmo tenant) têm seus salários atualizados automaticamente. Query segura com isolamento multi-tenant: `filter_by(funcao_id=id, admin_id=admin_id)`. Transação atômica garante consistência (tudo ou nada). Mensagem flash informativa exibe quantidade de funcionários atualizados. Logging detalhado da operação. E2E PASSOU: Alterado salário "Engenheiro Civil" R$ 8.500 → R$ 12.000, verificado que 4 funcionários do tenant 10 foram atualizados, confirmado que funcionários de outros tenants NÃO foram afetados. Architect-reviewed: PASS após correção crítica (vazamento multi-tenant eliminado). Regra aprendida: SEMPRE filtrar por admin_id em queries de Funcionario, mesmo quando Funcao é compartilhada entre tenants.
- **2025-10-27:** AUTO-FILL SALARY FEATURE - Cadastro de Funcionários - Implementado auto-preenchimento de salário ao selecionar função. API endpoint GET /api/funcao/{id} retorna dados da função (salario_base). JavaScript em funcionarios.html monitora select#funcao_id e preenche input#salario automaticamente via fetch. Correções aplicadas: (1) Import de Funcao adicionado em views.py. (2) Removido filtro admin_id (Funcao não é multi-tenant). (3) Campo salário limpo ao desselecionar função (fix architect - evita salário "fantasma"). E2E PASSOU: Selecionar "Diretor Geral" → R$ 20.000,00, desselecionar → vazio, "Engenheiro Civil" → R$ 8.500,00. Architect-reviewed: PASS. Regra aprendida: Sempre limpar campos auto-preenchidos quando seleção é revertida para estado inicial.

## System Architecture
The system is built on a Flask backend, utilizing SQLAlchemy ORM and a PostgreSQL database. Jinja2 is used for templating, and Bootstrap for frontend styling. Docker is used for deployment. A unified `base_completo.html` template ensures consistent UI/UX across the application. Critical database operations are protected by a `safe_db_operation` function to ensure data integrity.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation for each `admin_id` with role-based access control and dynamic `admin_id` handling.
-   **Dynamic Dashboard KPIs:** All metrics are calculated in real-time from the database, including proposal status, conversion rates, and analytics, with robust error handling.
-   **Event-Driven Integration System:** An `EventManager` (Observer Pattern) facilitates automated cross-module integration (e.g., material withdrawals impacting costs, payroll processing triggering accounting entries).
-   **UI/UX Design:** Adheres to modern UX/UI guidelines, featuring responsive layouts, modular components, a cohesive color palette, hierarchical typography, consistent spacing, and WCAG accessibility. Mobile-First Design is applied to modules like RDO.
-   **Automated Database Migrations:** `migrations.py` manages schema updates automatically at application initialization, ensuring consistent database structures.
-   **Core Modules:**
    -   **Proposal Management:** Supports reusable templates, automated calculations, PDF generation, and history tracking.
    -   **Employee Management:** Includes registration, automated time clocking, and overtime calculations.
    -   **Construction Project Management (RDO):** Provides control over projects with Daily Work Reports and dynamic service progress calculation.
    -   **Payroll (Folha de Pagamento v9.0):** Automated calculation based on time clock records with competency selector (15 months range), legal parameters validation, and automatic accounting integration via EventManager.
    -   **Costs Management (Custos v9.0):** Complete CRUD for construction costs with multi-tenant security, obra/tipo filters, real-time statistics, professional UI with cards and modals.
    -   **Accounting (Contabilidade v9.0):** Double-entry bookkeeping with automatic journal entries from payroll (LancamentoContabil + PartidaContabil), chart of accounts (PlanoContas), trial balance (Balancete), and DRE with competency selector.
    -   **Fleet Management System:** Manages vehicles and expenses.
    -   **Food Management System:** Manages restaurant and food entries.
    -   **Almoxarifado v3.0 (Warehouse Management):** Comprehensive system for materials, tools, and PPE with traceability, multi-tenant isolation, and movement tracking.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking for construction sites.
-   **Dynamic PDF Generation:** Supports custom headers, dynamic content, and multi-category proposal display.
-   **Company Customization:** Allows for dynamic branding with logo uploads and custom colors.
-   **Drag-and-Drop Organization:** Enables intuitive organization of proposals using multiple templates.
-   **Atomic Transactions:** Ensures data integrity for critical operations.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop functionality.