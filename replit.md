# SIGE - Sistema de Gestão Empresarial

## Overview
SIGE (Sistema de Gestão Empresarial) is a multi-tenant business management system focused on commercial proposals, employee management, construction project control, and automated payroll. Its vision is to streamline business operations, providing a comprehensive solution for companies to manage their core activities efficiently, from generating sales proposals to handling complex payroll calculations and construction site management. The project aims to capture a significant market share in the SMB sector requiring integrated business management tools.

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

## Implementation Priority (August 2025)
**✅ PROJETO CONCLUÍDO E PRONTO PARA PRODUÇÃO (29/08/2025)**

**Última Atualização: 29/08/2025 - 10:52**
- ✅ **CORREÇÃO CRÍTICA DE PRODUÇÃO:** Sistema RDO totalmente corrigido e sincronizado
  - **Problema resolvido:** Removidos 42 registros duplicados de "Etapa Intermediária" 
  - **Contagem correta:** 11 subatividades (4+3+4) em vez de 53 errôneas
  - **Templates sincronizados:** Páginas desenvolvimento x produção consistentes
  - **Deploy Ready:** Dockerfile.producao e entrypoint corrigidos criados
  - **Sistema 100% funcional:** Salvamento e carregamento de RDO operacional

**Status Final da Implementação:**
1. ✅ **CONCLUÍDO** - Consolidação backend completa (RDO, Funcionários, Propostas)
2. ✅ **CONCLUÍDO** - Design moderno unificado (template base_completo.html)
3. ✅ **CONCLUÍDO** - Sistema de filtros dashboard funcionando
4. ✅ **CONCLUÍDO** - Deploy automático configurado (Dockerfile + scripts)
5. ✅ **CONCLUÍDO** - Health check e verificação automática implementados
6. ✅ **CONCLUÍDO** - Tratamento de erros robusto para produção
7. ✅ **CONCLUÍDO** - Documentação completa de deploy

**Módulos Consolidados e Testados:**
- **RDO:** ✅ Sistema CRUD completo, interface moderna, rotas unificadas
- **Funcionários:** ✅ Gestão completa, admin_id dinâmico, bypass para desenvolvimento
- **Propostas:** ✅ 7 rotas consolidadas, circuit breakers, resiliência total
- **Dashboard:** ✅ KPIs funcionando, filtros operacionais, design responsivo

**Deploy Ready (28/08/2025):**
- **Dockerfile:** ✅ Otimizado para produção com health check
- **Scripts:** ✅ build.sh, verify_deploy.py, production_config.py
- **Health Check:** ✅ Endpoint /health funcional
- **Documentação:** ✅ DEPLOY_INSTRUCTIONS_FINAL.md completa
- **HOTFIX PRODUÇÃO:** ✅ Script corrigido para ambientes com 80 tabelas (`docker-entrypoint-producao-corrigido.sh`)

## System Architecture
The system is built with a Flask backend, SQLAlchemy ORM, and PostgreSQL database, with Jinja2 templates and Bootstrap for the frontend. Deployment is managed via Docker on Replit. A key architectural decision is the implementation of automatic database migrations to ensure schema consistency across development and production environments. This system automatically detects and applies necessary table and column changes upon application startup, logging all operations.

**Template Architecture (Updated Aug 2025):** The entire system now uses a unified modern template (`base_completo.html`) across all 110+ pages, ensuring consistent UI/UX, responsive design, and improved maintainability. All modules have been migrated from the legacy `base.html` template. Critical database transaction protection implemented via `safe_db_operation` function to prevent production errors.

**Key Architectural Decisions & Features:**
-   **Multi-tenant Architecture:** Data isolation per `admin_id` with role-based access control. Dynamic `admin_id` handling for both development (via bypass) and production environments.
-   **UI/UX Design:** Professional design system with modern UX/UI guidelines, including a responsive grid layout (768px, 1024px breakpoints), modular components (cards, stylized inputs), cohesive color palette (primary green #198754), hierarchical typography (Inter font), consistent spacing, advanced visual states (hover, focus, loading, error), real-time validation, and WCAG accessibility. All 110+ pages now use the unified modern template with proper text contrast (dark text on light backgrounds for KPI values).
-   **Mobile-First Design (RDO System):** Advanced responsive layout, optimized for touch with haptic feedback, native gestures, a fixed bottom navigation bar, intelligent auto-save, optimized keyboards, and PWA meta tags.
-   **Automated Database Migrations:** `migrations.py` handles schema updates (e.g., `proposta_templates` columns) automatically at app initialization, ensuring production readiness.
-   **Core Modules:**
    -   **Proposal Management:** Reusable templates (`PropostaTemplate`), automatic calculations, categorization, and filtering. Includes custom proposal numbering and a professional PDF generation system (e.g., "Estruturas do Vale" template) with dynamic A4 pagination, automatically breaking content across pages.
    -   **Employee Management:** Full registration with photo support, automated time clocking, and overtime/lateness calculation.
    -   **Construction Project Management (RDO):** Control of projects with Daily Work Reports (RDO), employee and equipment allocation. Features a completely modernized card-based interface (`rdo_lista_unificada.html`) accessible via single route `/rdo` with gradient headers, statistics dashboard, advanced filtering, and responsive design. All legacy templates and duplicate routes eliminated for maximum maintainability.
    -   **Payroll:** Automatic calculation based on time clock records and configurable salaries.
-   **Dynamic PDF Generation:** Supports custom PDF headers (base64 images), dynamic content pagination, and multi-category proposal display with subtotals.
-   **Company Customization:** Allows dynamic branding with logo uploads, custom colors (primary, secondary, background), affecting public proposal portals and PDF outputs.
-   **Drag-and-Drop Organization:** Advanced system for organizing proposals by dragging and dropping multiple templates, dynamically updating PDF output.

## External Dependencies
-   **Flask:** Web framework for the backend.
-   **SQLAlchemy:** ORM for database interaction.
-   **PostgreSQL:** Relational database management system.
-   **Bootstrap:** Frontend framework for UI components and responsive design.
-   **Jinja2:** Templating engine for rendering HTML.
-   **Docker:** Containerization platform for deployment.
-   **Sortable.js:** JavaScript library used for drag-and-drop functionality in the UI.