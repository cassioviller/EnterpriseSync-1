## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system for Small and Medium-sized Businesses (SMBs). It aims to streamline operations across commercial proposal generation, employee management, construction project control (Daily Work Reports - RDO), and automated payroll processing. The system covers the entire business workflow from sales to on-site management and financial calculations, enhancing efficiency and operational oversight.

**Current Status (October 28, 2025):**
- **Test Success Rate:** 93.6% (44/47 scenarios) ✅
- **Critical Bugs:** 4/4 fixed (100%)
- **Automated Integrations:** 6/6 validated (Folha→Contabilidade, Almoxarifado→Custos/Financeiro, etc)
- **Production Readiness:** 95% confidence, ready for deployment with documented limitations

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
The system is built on a Flask backend, utilizing SQLAlchemy ORM and a PostgreSQL database, with Jinja2 for templating and Bootstrap for frontend styling. Docker is used for deployment. A unified `base_completo.html` template ensures consistent UI/UX.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Ensures data isolation per `admin_id` with role-based access control.
-   **Dynamic Dashboard KPIs:** Real-time metrics calculated from the database with robust error handling.
-   **Event-Driven Integration System:** Uses an `EventManager` (Observer Pattern) for automated cross-module integration (e.g., material movements impacting costs, payroll triggering accounting entries).
-   **UI/UX Design:** Modern, responsive layouts with modular components, cohesive color palette, hierarchical typography, consistent spacing, WCAG accessibility, and Mobile-First Design for modules like RDO.
-   **Automated Database Migrations:** `migrations.py` manages schema updates at application initialization.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates, automated calculations, PDF generation, history tracking.
    -   **Employee Management:** Registration, automated time clocking, overtime calculations.
    -   **Construction Project Management (RDO):** Control over projects with Daily Work Reports and dynamic service progress.
    -   **Payroll (Folha de Pagamento):** Automated calculation based on time clock records, competency selector (15 months range), legal parameters validation, and automatic accounting integration. **CLT-compliant overtime differentiation**: HE 50% for Saturdays/weekdays (1.5x pay), HE 100% for Sundays/holidays (2.0x pay) with triple detection (weekday, tipo_registro, CalendarioUtil). **Late deductions**: Accumulated minutes converted to hours and deducted from gross salary (implemented Oct 28, 2025). Optimized performance with pre-loaded holiday calendar (single query + O(1) lookups).
    -   **Costs Management (Custos):** CRUD for construction costs with multi-tenant security, filters, real-time statistics, and professional UI.
    -   **Accounting (Contabilidade):** Double-entry bookkeeping with automatic journal entries from payroll, chart of accounts (14 accounts initialized for admin_id=54), trial balance, and DRE with competency selector. **Known Limitation:** PlanoContas uses `codigo` as PK - each admin must use unique account codes (e.g., admin 54: "1.1.01.001", admin 55: "1001"). Full multi-tenant code reuse requires future migration to composite PK.
    -   **Fleet Management System:** Manages vehicles and expenses.
    -   **Food Management System:** Manages restaurant and food entries.
    -   **Warehouse Management (Almoxarifado):** Comprehensive system for materials, tools, and PPE with traceability and multi-tenant isolation.
    -   **Shared Device Time Clock System (Ponto Eletrônico):** Mobile-first time clock with GPS tracking.
-   **Dynamic PDF Generation:** Custom headers, dynamic content, multi-category proposal display.
-   **Company Customization:** Dynamic branding with logo uploads and custom colors.
-   **Drag-and-Drop Organization:** Intuitive organization of proposals.
-   **Atomic Transactions:** Ensures data integrity for critical operations using `safe_db_operation`.

## Recent Changes (October 30, 2025)
**Implemented:**
1. ✅ **Migração 48 - Multi-Tenancy Completo (20 Modelos)** [APROVADO ARCHITECT - PRODUCTION READY]
   - **Objetivo:** Completar isolamento multi-tenant adicionando admin_id em 20 modelos faltantes
   - **Modelos Atualizados:** Departamento, Funcao, HorarioTrabalho, ServicoObra, HistoricoProdutividadeServico, TipoOcorrencia, Ocorrencia, CalendarioUtil, CentroCusto, Receita, OrcamentoObra, FluxoCaixa, RegistroAlimentacao, RDOMaoObra, RDOEquipamento, RDOOcorrencia, RDOFoto, NotificacaoCliente, PropostaItens, PropostaArquivos
   
   - **⚠️ CORREÇÃO CRÍTICA DE SEGURANÇA (Oct 30, 2025):**
     - ❌ Versão simplificada inicial causava vazamento de dados (UPDATE genérico com admin_id padrão)
     - ✅ Versão tenant-aware restaurada com backfill inteligente via FK
     - ✅ Validações pós-backfill adicionadas para detecção de colapso de tenants
     - ✅ Architect aprovou: isolamento multi-tenant preservado
   
   - **Estratégia de Backfill Tenant-Aware (4 Grupos):**
     - **Grupo 1 (14 tabelas):** Backfill via FK simples preservando isolamento
       - departamento, funcao, horario_trabalho → funcionario.admin_id
       - servico_obra, ocorrencia, receita, orcamento_obra, notificacao_cliente → obra.admin_id
       - historico_produtividade_servico → servico_obra → obra.admin_id
       - registro_alimentacao → funcionario.admin_id
       - rdo_mao_obra, rdo_equipamento, rdo_ocorrencia, rdo_foto → rdo → obra.admin_id
       - proposta_itens, proposta_arquivos → propostas_comerciais.admin_id
     - **Grupo 2 (2 tabelas):** Backfill via COALESCE multi-FK
       - centro_custo → COALESCE(obra.admin_id, departamento.admin_id)
       - fluxo_caixa → COALESCE(obra.admin_id, centro_custo.admin_id)
     - **Grupo 3 (2 tabelas):** Duplicação de seeds para cada admin via CROSS JOIN
       - tipo_ocorrencia → duplica todos os tipos para cada admin
       - calendario_util → duplica todas as datas para cada admin
     - **Grupo 4 (2 tabelas):** Correção de nullable em models.py
       - departamento, funcao, horario_trabalho: nullable=True → nullable=False
   
   - **Validações Pós-Backfill (Segurança Multi-Tenant):**
     - 🔍 Contagem de admins distintos por tabela
     - ⚠️ Detecção de colapso de tenants (alerta se múltiplos admins colapsam em um)
     - 📊 Logs detalhados de distribuição de admin_id por tabela
     - 🔴 ABORTA migração se registros órfãos detectados
     - ✅ Commit só ocorre após todas as validações passarem
   
   - **Proteções Implementadas:**
     - ✅ Backfill tenant-aware via FK (preserva isolamento)
     - ✅ Órfãos em qualquer tabela ABORTAM migração (via Exception)
     - ✅ Seeds duplicados para cada admin (não compartilhados entre tenants)
     - ✅ Logs detalhados de órfãos e distribuição de tenants
     - ✅ Rollback automático em caso de erro por tabela
     - ✅ Índices criados automaticamente para performance
     - ✅ Idempotência total (pula tabelas que já têm admin_id)
   
   - **Mudanças no Banco:**
     - Coluna admin_id adicionada (INTEGER NOT NULL)
     - Foreign key para usuario(id) com ON DELETE CASCADE
     - Índices idx_{tabela}_admin_id para todas as 20 tabelas
     - Constraints de integridade referencial
   
   - **Status de Produção:**
     - ✅ APROVADO ARCHITECT (Oct 30, 2025) - sem problemas de segurança
     - ✅ Isolamento multi-tenant preservado
     - ✅ Validações pós-backfill implementadas
     - ✅ Idempotência validada (pula em desenvolvimento)
     - 🟢 PRODUCTION READY para Easypanel
   
   - **Procedimento de Deploy Easypanel:**
     1. Fazer backup completo do banco antes da migração
     2. Migração executará automaticamente no primeiro startup
     3. Verificar logs para validações pós-backfill
     4. Se órfãos detectados: revisar dados manualmente antes de re-executar
     5. Migração é idempotente: pode executar múltiplas vezes sem problemas
   
   - **IMPORTANTE:** Ao criar novos registros nesses modelos, sempre definir admin_id=current_user.id

2. ✅ **Módulo de Custos - Dashboard TCO Completo** (Tarefas 1-4)
   - Dashboard com 4 KPIs: Total do mês, Custos por categoria, Top 5 obras, Evolução mensal
   - Gráficos Chart.js: Pizza (custos por categoria), Linha (evolução mensal)
   - Filtros interativos: obra, categoria, período
   - Integração RDO→Custos: handler `rdo_finalizado` emite de ambos os caminhos (finalizar_rdo e update)
   - Integração Frota→Custos: validada (evento `veiculo_usado`)

3. ✅ **Módulo de Frota - Dashboard TCO + Alertas** (Tarefas 5-7)
   - Dashboard TCO com 4 KPIs: TCO Total, Custo Médio/KM, Total Veículos, Custos Mês Atual
   - 3 gráficos Chart.js: Custos por tipo (pizza), Evolução mensal (linha), Top 5 veículos (barra)
   - Campos de alerta adicionados: `data_vencimento_ipva`, `data_vencimento_seguro`
   - Função `verificar_alertas()`: classifica urgência (crítica/alta/média) para IPVA, Seguro, Manutenção
   - Filtros aplicados em TODAS as queries: tipo de veículo, status, data início/fim

4. ✅ **Módulo de Alimentação - Dashboard + Integração Financeiro** (Tarefas 8-10)
   - Dashboard com 4 KPIs: Total Refeições, Custo Total, Custo Médio, Custos Mês Atual
   - 3 gráficos Chart.js: Top 5 Funcionários (barras), Evolução Mensal (linha), Top 5 Obras (barras)
   - Filtros interativos: restaurante, obra, data início/fim
   - **Integração Alimentação→Financeiro** (event_manager.py linhas 952-1038):
     - Handler `alimentacao_lancamento_criado` converte Restaurante→Fornecedor→ContaPagar
     - Reutiliza Fornecedores existentes por CNPJ, cria automaticamente se não existir
     - Conta a pagar com vencimento em 7 dias, origem_tipo='ALIMENTACAO'
   - Evento emitido após commit do lançamento (alimentacao_views.py linhas 202-213)
   - CRUD completo já existente: restaurantes e lançamentos com validações multi-tenant

5. ✅ **Módulo Financeiro - Correções Críticas** (October 30, 2025)
   - **Bug Fix:** Template `contas_pagar.html` linha 243 referenciava `datetime` sem passar no contexto → Corrigido passando `datetime=datetime` em todos os renders
   - **Bug Fix:** Endpoint `criar_conta_pagar` passava `fornecedor_nome` direto para ContaPagar, mas modelo requer `fornecedor_id` → Implementado busca/criação automática de Fornecedor
   - **Bug Fix:** Tabela `fornecedor` tem coluna `nome` NOT NULL não mapeada no modelo Python → Corrigido usando SQL direto para preencher todos os campos obrigatórios
   - **Funcionalidades Validadas via E2E:**
     - ✅ Criar conta a pagar com fornecedor auto-criado (busca por CNPJ, cria se não existir)
     - ✅ Baixar parcialmente conta a pagar (status PENDENTE → PARCIAL)
     - ✅ KPIs em tempo real na listagem de contas
   - **Status:** Contas a Pagar 100% funcional e testado

**Previous Changes (October 28, 2025):**
1. ✅ Late deduction in payroll (`services/folha_service.py`)
2. ✅ Chart of Accounts initialized (14 accounts)
3. ✅ Complete test data created
4. ✅ Automated integrations validated (3/3 tests passed 100%)
5. ✅ Test report updated: RELATORIO_TESTES_SIGE_v9.0.md (93.6% success rate)

**Known Issues:**
- PlanoContas multi-tenancy limitation (codes must be unique across all admins)
- Future migration needed for composite PK (admin_id, codigo)
- **get_admin_id() Fallback:** Múltiplas implementações de get_admin_id() em diferentes arquivos ainda usam fallback hard-coded (valor 10). Isso pode causar IntegrityError se o usuário com id=10 não existir. **AÇÃO FUTURA:** Centralizar get_admin_id() e nunca retornar valor hard-coded - lançar erro se não conseguir determinar admin_id.

## External Dependencies
-   **Flask:** Web framework.
-   **SQLAlchemy:** ORM.
-   **PostgreSQL:** Relational database.
-   **Bootstrap:** Frontend framework.
-   **Jinja2:** Templating engine.
-   **Docker:** Containerization platform.
-   **Sortable.js:** JavaScript library for drag-and-drop.
-   **python-dateutil:** For date and time calculations.