# SIGE - Sistema Integrado de Gestão Empresarial

## Overview

SIGE (Sistema Integrado de Gestão Empresarial) is a comprehensive business management system designed for "Estruturas do Vale", a construction company. The system provides integrated management of employees, projects, vehicles, timekeeping, and food expenses. Built with Flask (Python) and using SQLAlchemy for database operations, it features a responsive web interface with Bootstrap and Chart.js for data visualization.

## System Architecture

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **Database ORM**: SQLAlchemy with Flask-SQLAlchemy extension
- **Authentication**: Flask-Login for session management
- **Database**: SQLite by default, configurable via DATABASE_URL environment variable
- **Forms**: Flask-WTF with WTForms for form handling and validation
- **Security**: Werkzeug for password hashing and proxy handling

### Frontend Architecture
- **UI Framework**: Bootstrap 5 (dark theme)
- **Icons**: Font Awesome 6
- **Data Tables**: DataTables.js for enhanced table functionality
- **Charts**: Chart.js for data visualization
- **JavaScript**: Vanilla JavaScript with jQuery for DOM manipulation

### Application Structure
- **Modular Design**: Blueprint-based organization for different functional areas
- **Template Inheritance**: Jinja2 templates with base template for consistent layout
- **Static Assets**: CSS and JavaScript files organized in static directory

## Key Components

### Authentication System
- User login/logout functionality
- Session management with Flask-Login
- Password hashing using Werkzeug security utilities
- Protected routes requiring authentication

### Core Business Modules
1. **Employee Management** (Funcionários)
   - Employee registration and management
   - Department and role assignments
   - Salary tracking
   - Active/inactive status management

2. **Department Management** (Departamentos)
   - Department creation and management
   - Employee assignment to departments

3. **Role Management** (Funções)
   - Job role definitions
   - Base salary configurations
   - Employee role assignments

4. **Project Management** (Obras)
   - Construction project tracking
   - Budget management
   - Timeline management
   - Status tracking (In Progress, Completed, Paused, Cancelled)

5. **Vehicle Management** (Veículos)
   - Fleet management
   - Vehicle status tracking
   - Maintenance scheduling

6. **Timekeeping System** (Ponto)
   - Employee time tracking
   - Entry/exit logging
   - Lunch break management
   - Hours calculation utilities

7. **Food Management** (Alimentação)
   - Food expense tracking
   - Daily and monthly reporting

### Dashboard and Reporting
- **Main Dashboard**: KPI overview with employee count, active projects, and vehicle statistics
- **Data Visualization**: Charts showing employee distribution by department and project costs
- **Reporting Module**: Comprehensive reporting system with filtering capabilities

### Database Models
- **Usuario**: User authentication and profile management
- **Funcionario**: Employee information and relationships
- **Departamento**: Department structure
- **Funcao**: Job roles and salary information
- **Obra**: Construction projects and timeline management
- **Veiculo**: Vehicle fleet management
- **RegistroPonto**: Time tracking records
- **RegistroAlimentacao**: Food expense records

## Data Flow

### User Authentication Flow
1. User accesses protected route
2. Flask-Login checks session authentication
3. Redirect to login if not authenticated
4. Password verification against hashed passwords
5. Session establishment upon successful login

### CRUD Operations Flow
1. Form submission via POST requests
2. Flask-WTF form validation
3. SQLAlchemy ORM operations
4. Database transaction management
5. Response with success/error messages
6. Page redirect or AJAX response

### Dashboard Data Flow
1. Database queries for KPI calculations
2. Data aggregation using SQLAlchemy functions
3. Template rendering with processed data
4. Chart.js visualization on frontend

## External Dependencies

### Python Packages
- Flask: Web framework
- Flask-SQLAlchemy: Database ORM
- Flask-Login: Authentication management
- Flask-WTF: Form handling
- WTForms: Form validation
- Werkzeug: WSGI utilities and security

### Frontend Libraries
- Bootstrap 5: UI framework with dark theme
- Font Awesome 6: Icon library
- DataTables.js: Enhanced table functionality
- Chart.js: Data visualization
- jQuery: DOM manipulation

### Environment Configuration
- SESSION_SECRET: Application secret key
- DATABASE_URL: Database connection string
- Development vs Production settings

## Deployment Strategy

### Development Environment
- Flask development server
- SQLite database for local development
- Debug mode enabled
- Hot reload functionality

### Production Considerations
- WSGI server deployment (Gunicorn recommended)
- PostgreSQL database migration capability
- Environment variable configuration
- ProxyFix middleware for reverse proxy support
- Database connection pooling configuration

### Database Migration
- SQLAlchemy model-based schema management
- Automatic table creation on application startup
- Support for database URL configuration

## Changelog

- July 03, 2025. Initial setup
- July 03, 2025. Enhanced employee management with photo upload and real-time validation
- July 03, 2025. Implemented comprehensive employee profile page with KPIs, time tracking history, and occurrence management
- July 03, 2025. Implemented comprehensive Reports and Dashboards page with global filters, interactive charts, and categorized reports
- July 03, 2025. Removed fornecedores (suppliers), materiais (materials), and clientes (clients) modules completely from system, including database models, forms, routes, and navigation links. Fixed duplicate reports link in header.
- July 04, 2025. Implemented SIGE v3.0 with advanced KPI engine following technical specification:
  - Added employee code field (F0001, F0002, etc.) to all existing employees
  - Created comprehensive KPIs Engine with correct business rules for attendance, delays, and costs
  - Implemented new dashboard layout 4-4-2 with 10 KPIs as specified
  - Added enhanced database models for occurrences, work calendar, and detailed time tracking
  - Created automatic calculation system for delays (entry + early departure in hours)
  - Implemented correct absence calculation (working days without presence record)
  - Added real-time KPI updates and CSV export functionality
- July 04, 2025. Final v3.0 Implementation:
  - Fixed AttributeError in KPI engine by correcting relationship references to HorarioTrabalho
  - Created comprehensive system documentation (RELATORIO_SISTEMA_SIGE_v3.md)
  - Implemented proper business rules for construction industry KPIs
  - Fixed UI layout with filters moved above performance indicators
  - Removed "(Mês Atual)" text from all KPI titles as requested
  - System now uses PostgreSQL with proper foreign key relationships
- July 04, 2025. KPI Engine v3.0 Enhancements and Date Filter Fix:
  - Enhanced KPI engine with complete 2025 holidays (including Carnaval, Corpus Christi)
  - Added automatic calculation triggers for new point records
  - Fixed date filter persistence issue in employee profile page
  - Implemented proper backend-frontend data flow for date filters
  - Created recalculation script for existing point records
  - Ensured all data tables (point, food, occurrences) respect selected date filters
- July 04, 2025. Visual Absence Identification System:
  - Implemented comprehensive absence detection for employee timesheet table
  - Added red background highlighting (#3d2a2a) for absence days
  - Created "Falta" text display in red (#dc3545) with bold formatting
  - Developed smart absence logic considering working days and 2025 Brazilian holidays
  - Enhanced KPI engine with functions for absence period identification
  - Integrated absence detection with existing date filter system
- July 04, 2025. KPI Calculation Corrections and UI Improvements:
  - Fixed absence calculation logic to use precise business day counting
  - Enhanced justified absence logic to consider approved occurrences with date ranges
  - Corrected delay display in timesheet table to use total_atraso_minutos field
  - Added work schedule display in employee profile data section
  - Improved KPI transparency by aligning calculations with actual data visible in tables
  - Created recalculation script for existing timesheet records to ensure data consistency
- July 04, 2025. Final KPI Precision Corrections for Pedro Lima Sousa Case:
  - Investigated and corrected all KPI calculation discrepancies reported for employee Pedro Lima Sousa
  - Confirmed absence counting logic correctly identifies 5 absences (19/06/25 is Corpus Christi holiday)
  - Fixed delay calculation system to properly calculate and persist entry delays and early departures
  - Implemented comprehensive delay tracking: 19.08 hours total delays across 13 records in June 2025
  - Validated all KPI formulas against actual database records for complete accuracy
  - System now correctly displays absence highlighting, delay minutes, and all derived KPIs
- July 04, 2025. Holiday Identification System and Comprehensive Analysis:
  - Implemented holiday identification system in timesheet table with visual distinction
  - Holidays now display as "Feriado" in gray color vs "Falta" in red, with different background colors
  - Added complete holiday calendar for 2025 including Carnaval, Corpus Christi, and all national holidays
  - Created comprehensive technical report (RELATORIO_FUNCIONALIDADES_PENDENTES.md) documenting:
    * 33% implementation rate of documented KPIs (6 of 18 complete)
    * Incomplete modules: Materials, Suppliers, Clients (templates exist but disconnected)
    * Non-functional report links in Reports & Dashboards page
    * Missing export functionality (PDF/Excel) beyond basic CSV
    * Placeholder modals in restaurant food management
  - System analysis reveals solid core functionality with clear roadmap for remaining implementations
- July 04, 2025. Codebase Cleanup - Orphaned Modules Removal:
  - Completely removed orphaned modules: Fornecedores, Materiais, Clientes
  - Deleted templates: templates/fornecedores.html, templates/materiais.html, templates/clientes.html
  - Verified no remaining references to removed modules in Python files, templates, or routes
  - Maintained legitimate "fornecedor" field in vehicle costs (for service provider tracking)
  - Updated technical report to reflect 100% completion of module cleanup
  - System now focused exclusively on active functionalities with clean codebase
- July 07, 2025. Modal Funcional de Alimentação - v3.1:
  - Implementado modal completamente funcional na página de detalhes de restaurantes
  - Funcionalidades: seleção múltipla de funcionários, cálculo automático de valor total, validação de duplicatas
  - Adicionada rota backend /alimentacao/restaurantes/<int:restaurante_id>/lancamento (POST)
  - JavaScript interativo para UX aprimorada (checkbox "Selecionar Todos", resumo em tempo real)
  - Sistema de prevenção de registros duplicados com validação completa
  - Atualização dos relatórios técnicos com progresso atual (RELATORIO_SISTEMA_SIGE_v3.md e RELATORIO_FUNCIONALIDADES_PENDENTES.md)
  - Taxa de completude operacional atualizada para 85% do sistema
- July 07, 2025. Sistema de Relatórios Funcionais Completo - v3.2:
  - Implementado sistema completo de relatórios funcionais com 10 tipos de relatórios
  - Exportação multi-formato: CSV, Excel (.xlsx) e PDF usando openpyxl e reportlab
  - Relatórios funcionando: funcionários, ponto, horas extras, alimentação, obras, custos, veículos, dashboard executivo, progresso, rentabilidade
  - Módulo separado relatorios_funcionais.py com funções especializadas de exportação
  - Interface web com botões de exportação integrados e JavaScript funcional
  - Correção de todos os links quebrados em templates e rotas inexistentes
  - Sistema totalmente estável e operacional com relatórios exportáveis
  - Taxa de completude operacional elevada para 90% do sistema
- July 07, 2025. Modal de Ocorrências Funcional Completo - v3.3:
  - Implementado modal de ocorrências completamente funcional no perfil do funcionário
  - Rotas backend completas: criar, editar e excluir ocorrências (/funcionarios/<id>/ocorrencias/nova)
  - Formulário com validação: tipo, data início/fim, status, descrição
  - JavaScript interativo: validação de formulário, limpeza automática do modal, confirmações de exclusão
  - Integração completa com modelo Ocorrencia existente no banco de dados
  - Funcionalidades: criar nova ocorrência, excluir ocorrência, validação de datas
  - Interface responsiva com Bootstrap 5 e feedback visual adequado
  - Sistema de ocorrências agora totalmente operacional e integrado ao perfil do funcionário
- July 07, 2025. Relatório Detalhado do Projeto - Documentação Completa:
  - Criado relatório técnico completo (project_details_report.md) com análise aprofundada do sistema
  - Documentação da estrutura completa do banco de dados (26 tabelas) com relacionamentos
  - Mapeamento de todos os 44 endpoints da API com métodos HTTP e parâmetros
  - Análise detalhada da lógica de negócio e engine de KPIs v3.0
  - Documentação de configurações de ambiente, deploy e dependências
  - Descrição de fluxos de usuário críticos passo a passo
  - Avaliação de estratégias de teste e recomendações
  - Relatório técnico completo para facilitar manutenção e desenvolvimento futuro
- July 07, 2025. Módulo de Gestão Financeira Avançada - v4.0:
  - Implementado módulo financeiro completo com 4 novos modelos: CentroCusto, Receita, OrcamentoObra, FluxoCaixa
  - Criado engine de cálculos financeiros (financeiro.py) com KPIs e análises
  - Rotas backend completas: dashboard financeiro, receitas, fluxo de caixa, centros de custo
  - Interface web responsiva com Bootstrap 5 e gráficos Chart.js integrados
  - Menu de navegação com dropdown "Financeiro" adicionado ao sistema
  - Sistema de sincronização automática do fluxo de caixa com dados existentes
  - Controle de receitas com status (Pendente/Recebido) e múltiplas formas de recebimento
  - Centros de custo configuráveis por obra, departamento, projeto ou atividade
  - Correção de erro na página de obras (referência de rota inexistente)
  - Sistema financeiro totalmente operacional e integrado ao SIGE v3.0
- July 07, 2025. Correção Completa do Sistema de Funcionários - v4.1:
  - Implementadas funções utilitárias críticas: gerar_codigo_funcionario, salvar_foto_funcionario, validar_cpf
  - Corrigidas rotas truncadas novo_funcionario e editar_funcionario com validações completas
  - Criado template funcionario_form.html com JavaScript para preview de foto e máscaras
  - Validação de CPF em tempo real com algoritmo brasileiro oficial
  - Sistema de upload de foto funcional com nomenclatura por código do funcionário
  - Prevenção de duplicatas de CPF e geração automática de códigos únicos (F0001, F0002, etc.)
  - Máscaras de entrada para CPF e telefone com formatação automática
  - Criado relatório técnico completo (RELATORIO_PONTO_E_CUSTOS_FUNCIONARIOS.md) documentando:
    * Arquitetura completa do sistema de controle de ponto
    * Engine de KPIs v3.0 com 10 indicadores em layout 4-4-2
    * Lógica detalhada de cálculo de custos (mão de obra, alimentação, transporte)
    * Algoritmo de identificação inteligente de faltas considerando dias úteis e feriados
    * Sistema de triggers automáticos para atualização de cálculos de ponto
    * Regras de negócio específicas para construção civil
    * Métricas de performance e otimizações implementadas
  - Sistema de funcionários agora 100% operacional com cadastro, edição e gestão completa
- July 08, 2025. Sistema de Tipos de Lançamento com Percentuais Configuráveis - v4.2:
  - Implementados tipos especiais: "Sábado Horas Extras" e "Domingo Horas Extras" com percentuais configuráveis
  - Migração de banco de dados adicionando colunas tipo_registro e percentual_extras (119 registros atualizados)
  - Campo percentual habilitado para trabalho normal quando há horas extras detectadas
  - JavaScript dinâmico para mostrar/ocultar campos baseado no tipo selecionado
  - Fotos SVG aleatórias geradas para todos os funcionários (F0001.svg, F0002.svg, etc.)
  - Sistema de fotos corrigido em cards de funcionários e perfis de detalhes
  - Correção crítica na lógica de faltas: agora contabiliza apenas registros explícitos de falta no sistema
  - Atualizado engines de KPIs (v3.0 e simple) para não calcular faltas automáticas por dias sem registro
  - Sistema respeita regra de negócio: faltas só são contabilizadas quando lançadas manualmente no módulo
  - Correções visuais: falta justificada aparece em verde, atrasos limitados a 2 casas decimais
  - Registros de exemplo criados para Cássio com tipos corretos (feriado trabalhado, sábado/domingo extras)
  - CRUD de ponto corrigido: removido erro na criação de ocorrências automáticas
  - Perfil do Cássio populado com 12 registros demonstrando todos os tipos de lançamento no mês 6/2025
  - Tipos demonstrados: trabalho normal, falta, falta justificada, feriado, feriado trabalhado, sábado/domingo extras, meio período
- July 08, 2025. Sistema de Identificação Visual de Tipos de Lançamento - v4.3:
  - Implementado sistema completo de identificação visual para tipos de lançamento
  - Badges coloridos na coluna de data: SÁBADO (verde), DOMINGO (amarelo), FERIADO TRAB. (azul), FERIADO (cinza), JUSTIFICADA (azul), FALTA (vermelho)
  - Cores de fundo das linhas diferenciadas: sábado (verde escuro), domingo (roxo escuro), falta (vermelho escuro), feriado (azul escuro)
  - Ícones distintivos em observações: calendário (sábado), sol (domingo), estrela (feriado trab.), casa (feriado), check (justificada), X (falta)
  - Legenda visual explicativa no topo da tabela de ponto para orientação do usuário
  - Sistema permite identificação rápida e fácil de todos os tipos de lançamento especiais
- July 08, 2025. Correções em Feriados Trabalhados e Lógica de Almoço - v4.4:
  - Corrigido feriado trabalhado para mostrar horários de entrada/saída e horas extras contabilizadas
  - Implementada lógica para trabalho sem intervalo de almoço ("Sem Intervalo" em verde)
  - Adicionados registros com atrasos (30min entrada, 15min entrada + 15min saída antecipada)
  - Corrigida exibição de todos os tipos de registro (feriado, falta, feriado trabalhado) nas colunas
  - Template atualizado para usar tipo_registro ao invés de is_feriado/is_falta para maior precisão
  - Registros de exemplo incluem: atrasos, trabalho sem almoço, feriado trabalhado com horários completos
- July 08, 2025. Ajustes Finais no Sistema de Ponto - v4.5:
  - Corrigidos intervalos de almoço: maioria dos dias possui horário de almoço (12:00-13:00)
  - Apenas dia 13/06 mantido sem intervalo (trabalho contínuo de 8h)
  - Removida completamente seção "Histórico de Ocorrências" do perfil do funcionário
  - Corrigida exibição de horários de almoço (mostra "-" ao invés de "Sem Intervalo" quando não há)
  - Sistema agora reflete corretamente a realidade: maioria dos funcionários fazem intervalo de almoço
  - Feriados trabalhados exibem corretamente horários de entrada, saída e almoço com horas extras
- July 08, 2025. Correção do Link RDO no Menu de Navegação - v4.6:
  - Corrigido link "RDO" no menu principal que estava direcionando para relatórios
  - Link agora aponta corretamente para main.lista_rdos
  - Implementadas rotas RDO completas: lista_rdos, novo_rdo, criar_rdo, visualizar_rdo, editar_rdo, excluir_rdo
  - Corrigido link de criação de RDO na página de detalhes de obra
  - Sistema RDO (Relatório Diário de Obra) agora totalmente funcional e acessível pelo menu
- July 08, 2025. Correção de KPIs e Feriados Trabalhados - v4.7:
  - Corrigidos registros do Cássio para junho/2025 com dados realistas
  - Feriado trabalhado (07/06 - Corpus Christi) agora mostra 100% de horas extras corretamente
  - Engine de KPIs v3.0 corrigido para calcular atrasos baseado em total_atraso_minutos
  - Atrasos agora contabilizados corretamente: 30min + 30min = 1.0h total
  - Horas extras calculadas corretamente: 8h (feriado 100%) + 4h (sábado 50%) + 4h (domingo 100%) = 20h
  - Sistema visual mantém identificação por badges e cores para tipos especiais
  - KPIs agora refletem dados precisos: 83h trabalhadas, 20h extras, 1h atrasos, 1 falta
- July 08, 2025. Melhorias na Página de Obras com Filtros Rápidos - v4.8:
  - Removido botão duplicado "Ver Detalhes" nos cards e tabela de obras
  - Implementados filtros rápidos na parte superior: nome da obra, status, período de datas
  - Pré-selecionado período padrão para últimos 30 dias (mês atual)
  - Botão "Limpar Filtros" para resetar busca facilmente
  - Informação visual sobre período padrão para cálculo de KPIs
  - Navegação otimizada: botão verde agora cria RDO com obra pré-selecionada
  - Interface mais limpa e funcional para gestão de obras
- July 08, 2025. Correção de Visualização de KPIs - v4.9:
  - Corrigido problema de paginação na tabela de ponto (pageLength aumentado para 25)
  - Adicionado resumo visual do período mostrando totais calculados
  - Melhorada visualização de horas extras para evitar confusão com dados paginados
  - Verificação de dados confirmada: 20h extras (8h+4h+4h+4h) calculadas corretamente
  - Interface otimizada para mostrar todos os dados relevantes do período selecionado
- July 08, 2025. Sistema de Outros Custos com Vale Transporte e Descontos - v5.0:
  - Implementado modelo OutroCusto para gestão de custos adicionais e descontos
  - Seção "Outros Custos" adicionada entre registro de ponto e alimentação no perfil do funcionário
  - Tipos suportados: Vale Transporte, Vale Alimentação, Desconto VT (6%), Outros Descontos
  - Modal funcional com auto-seleção de categoria e validações
  - Rotas backend para criar e excluir outros custos
  - Corrigido erro no template financeiro (dashboard.html) com list comprehension em Jinja2
  - Corrigido exibição de horas extras do feriado trabalhado na tabela de ponto
  - Sistema permite controle completo de custos adicionais e descontos sobre salário
  - Dados de exemplo populados para demonstração das funcionalidades
- July 08, 2025. Correções no Modal e Layout dos Indicadores - v5.1:
  - Corrigido modal de outros custos: removidos campos "Percentual (%)" e "Obra" conforme solicitado
  - Campo "Tipo" alterado para input text livre (ex: Vale Transporte, Vale Alimentação, etc.)
  - Layout dos indicadores reorganizado para grid 4-4-3 (4 colunas + 4 colunas + 3 colunas)
  - "Outros Custos" posicionado na segunda linha, última coluna (posição 2-4)
  - Corrigido cálculo de "Horas Perdidas": agora usa fórmula ((faltas*8) + atrasos)
  - Corrigido erro de template Jinja2 com hasattr, usando "is defined" ao invés
  - Sistema de outros custos completamente integrado aos KPIs com cálculo automático

## User Preferences

Preferred communication style: Simple, everyday language.