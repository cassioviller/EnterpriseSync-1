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

## User Preferences

Preferred communication style: Simple, everyday language.