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
- **2025-10-21:** UI ENHANCEMENT - Templates de Propostas - Aplicadas melhorias visuais modernas na interface de itens dos templates (novo.html e editar.html). Mudanças: (1) Header do card de itens com fundo azul (bg-primary) e texto branco, (2) Badge dinâmico no header mostrando total em tempo real, (3) Contador de itens integrado ao título, (4) Botão "Adicionar Item" atualizado para btn-light no editar.html. JavaScript atualizado: função atualizarTotal() agora sincroniza badge do header, rodapé e contador de itens simultaneamente. E2E validado: Template com 3 itens (R$ 208.000,00) criado e editado com sucesso, totais corretos em ambas as páginas. Architect-reviewed: PASS. Regra aprendida: Headers azuis com badges brancos seguem padrão visual do SIGE - aplicar consistentemente em cards de listagens dinâmicas.
- **2025-10-21:** CRITICAL API FIX - Templates de Propostas - Corrigido erro `'PropostaTemplate' object has no attribute 'valor_base'` que impedia carregamento de templates. Problema: API `/api/template/<id>` tentava acessar campo inexistente valor_base (linha 417 propostas_consolidated.py). Causa: Campo valor_base não existe no modelo PropostaTemplate. Solução: Removida referência a valor_base, adicionados campos corretos (descricao, itens_padrao, prazo_entrega_dias, validade_dias, percentual_nota_fiscal). E2E validado: Template "Galpão Industrial Básico" carrega corretamente, botão "Pré-carregar Template" funciona, sem erros JavaScript. Regra aprendida: Sempre validar campos do modelo antes de usar em APIs - usar search_codebase para confirmar estrutura.
- **2025-10-20:** CRITICAL FALLBACK FIX - Dashboard e Funcionários - Removido fallback incorreto que estimava custos quando não há registros de ponto. Problema: Dashboard mostrava R$ 47.855,54 e página Funcionários R$ 69.528,44 baseado em estimativas de salário × meses, mesmo sem lançamentos de ponto. Causa: Fallback em 2 locais (linhas 866-888 e 1508-1529) ativava para TODOS os funcionários sem registros, calculando custo = salário × meses. Solução: Removido fallback completo em ambos os locais - sem registros = R$ 0,00. E2E validado: Dashboard R$ 13.258,61 (-72%), Funcionários R$ 13.258,61 e 360,8h (-81% e -94%). Regra aprendida: Fallback NUNCA deve estimar custos para períodos vazios - férias/afastamentos devem ser registrados explicitamente via tipo_registro no sistema de ponto.
- **2025-10-17:** CRITICAL SCOPE FIX - Faltas Justificadas Dashboard - Resolvido erro `cannot access free variable 'calendar' where it is not associated with a value in enclosing scope` que causava KPI "Faltas Justificadas" mostrar R$ 0.00 em produção. Causa: reimportações locais de `calendar` nas linhas 520 e 5282 conflitavam com uso em funções aninhadas. Solução: Removidas reimportações locais, mantido apenas import global (linha 11). E2E validado: Dashboard agora mostra corretamente 12 dias, R$ 4.630,43. Regra aprendida: NUNCA reimportar módulos dentro de funções - Python em produção (Gunicorn) faz análise de escopo rigorosa.
- **2025-10-17:** CRITICAL SCHEMA FIX - Migração 45 para Propostas Comerciais - Implementada correção de schema para resolver erro `psycopg2.errors.UndefinedColumn: column propostas_comerciais.numero_proposta does not exist` em produção PostgreSQL. Problema: modelo Python usa mapeamento de colunas (`numero = db.Column('numero_proposta', ...)`) mas banco não tinha nomes corretos. Solução: Migração 45 renomeia colunas automaticamente: (1) `numero` → `numero_proposta`, (2) `titulo` → `assunto`, (3) `descricao` → `objeto`. Migração é idempotente (verifica existência antes de renomear), segura (não perde dados), e executará automaticamente em deploy. Fixes dashboard quebrado em produção devido a queries SQLAlchemy incompatíveis com schema PostgreSQL real.
- **2025-10-17:** PRODUCTION DEPLOYMENT FIX - Chart.js Local + UnboundLocalError - Resolvidos 2 problemas críticos: (1) Chart.js v4.4.0 hospedado localmente em /static/js/vendor/ - CDN bloqueado em produção, (2) UnboundLocalError corrigido adicionando variáveis de fallback ao except block (total_custo_real, custo_alimentacao_real, custo_transporte_real, custo_outros_real, total_horas_real). Dashboard validado com KPIs corretos (Mão de Obra R$193.273,61, Alimentação R$1.107,36, Total R$195.630,97). Architect-reviewed: PASS.

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
    -   **Payroll:** Automated calculation based on time clock records.
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