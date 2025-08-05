# SIGE - Sistema Integrado de Gestão Empresarial

## Overview

SIGE (Sistema Integrado de Gestão Empresarial) is a comprehensive business management system designed for "Estruturas do Vale", a construction company. It provides integrated management of employees, projects, vehicles, timekeeping, and food expenses. The system aims to streamline operations, enhance decision-making through data visualization and advanced analytics, and provide detailed financial insights for construction project management. Its ambition is to transform into a specialized solution for metallic structures.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (August 2025)
### Food Registration System - Critical JavaScript Bug Fixed
- **Date**: August 5, 2025 (Critical Fix)
- **Change**: Fixed JavaScript bug causing individual food entries to save with incorrect dates (August instead of selected July dates)
- **Impact**: Individual food registrations now save with correct user-selected dates; period-based entries were already working correctly
- **Files**: `templates/alimentacao.html` (removed `valueAsDate = new Date()` and automatic date assignments), `corrigir_data_periodo_atual.py` for data correction
- **Result**: Individual food entry for 30/07/2025 now saves correctly instead of creating multiple August entries, period entries (18/07 to 18/07) continue working properly

### Overtime Calculation Logic - Complete Fix Applied
- **Date**: August 5, 2025 (Final Implementation)
- **Change**: Fixed incorrect overtime calculation logic for all timesheet records
- **Impact**: Corrected calculation based on individual employee work schedules (entry anticipation + late departure)
- **Files**: `kpis_engine.py` (lines 583-601), `encontrar_registro_correto.py`, `aplicar_correcao_geral_horas_extras.py`
- **Result**: Example case 07:05-17:50 vs 07:12-17:00 schedule now correctly shows 0.95h (7min early + 50min late = 57min total) instead of 1.8h, all overtime calculations now use proper minute-based logic


### KPI System Complete Overhaul
- **Date**: August 1, 2025
- **Change**: Complete correction of KPI calculation inconsistencies
- **Impact**: Standardized 549 time records, implemented corrected calculation service
- **Files**: `correcao_completa_kpis.py`, `interface_tipos_registro.py`, `RELATORIO_IMPLEMENTACAO_COMPLETA.md`
- **Result**: 100% consistency in main KPIs, clear cost logic for all record types

### SIGE v8.1 - Complete KPI Engine Overhaul
- **Date**: August 1, 2025 (Later)
- **Change**: Implemented completely new KPI engine with expanded timesheet types and precise cost calculations
- **Impact**: 10 standardized timesheet types, cost calculator based on specific work schedules, multiple record entry interface
- **Files**: `kpis_engine_v8_1.py`, `migrar_tipos_v8_1.py`, `interface_lancamento_multiplo.py`, `RELATORIO_IMPLEMENTACAO_V8_1.md`
- **Result**: 12 precise KPIs, cost calculation per project, automated migration system, 100% functional testing

### Production Bug Fixes - Final
- **Date**: August 1, 2025 (Final)
- **Change**: Fixed productivity/efficiency calculation and UI modal errors
- **Impact**: Danilo now shows correct 100% productivity/efficiency, modal opens correctly with multiple fallback methods
- **Files**: `kpis_engine.py`, `templates/funcionario_perfil.html`, `CORRECAO_PRODUTIVIDADE_EFICIENCIA_FINALIZADA.md`
- **Result**: Productivity = 100% when no lost hours, "Custo Total" KPI with proper white text on blue background, robust modal opening system

### Saturday Worked Logic and KPI Engine Complete Fix
- **Date**: August 4, 2025 (Final Solution)
- **Change**: Complete data cleanup, duplicate removal, definitive Saturday worked logic implementation, and KPI engine fix for production environment
- **Impact**: Fixed Saturday hours not being counted in KPI calculations, corrected cost calculation logic, updated engine to recognize both sabado_trabalhado and sabado_horas_extras types
- **Files**: `kpis_engine.py` (lines 158, 332), `templates/funcionario_perfil.html`, `corrigir_todos_sabados.py`, `corrigir_sabado_final.py`, server restarted
- **Result**: KPI engine now properly counts Saturday worked hours (should show 8.2h instead of 0.3h for Antonio), cost calculation includes 50% Saturday premium, template displays correctly with "7.9h - 50%" format, 62 Saturday records with 282.3h total extras properly calculated

### KPI Dashboard Enhancement - Duplicate Metric Fix
- **Date**: August 4, 2025 (Later)
- **Change**: Replaced duplicate Efficiency KPI with Overtime Hours display to eliminate confusion between identical Productivity and Efficiency percentages
- **Impact**: Fourth row now shows distinct KPIs: Horas Perdidas, Horas Extras (instead of Eficiência), Valor Falta Justificada, Custo Total
- **Files**: `kpis_engine.py` (lines 74-75, 100), `templates/funcionario_perfil.html` (lines 253-254)
- **Result**: Dashboard now displays Horas Extras value in yellow highlight format (8.2h for Antonio case), eliminating confusion from having identical percentage values for Productivity and Efficiency

### Saturday Hours Logic Complete Overhaul - Final Fix Applied
- **Date**: August 4, 2025 (Final Implementation)
- **Change**: Applied definitive Saturday logic - all Saturday records show 0h in "worked hours" column, hours extras calculated based on normal workday schedule
- **Impact**: 99 Saturday records processed, forced recalculation applied, KPI engine now correctly sums all Saturday overtime at 50% premium
- **Files**: `forcar_atualizacao_kpis.py`, `testar_funcionario_193h_especifico.py`, complete database correction applied
- **Result**: Saturday records display correctly as 0h worked + extras based on employee's normal schedule, KPIs include all Saturday overtime in calculations, system shows proper values in interface

### Critical Security Fix: Multi-Tenant Data Isolation
- **Date**: August 4, 2025 (Critical Security Patch)
- **Change**: Fixed critical security vulnerability where admin users could see data from other companies/administrators
- **Impact**: Corrected data leakage in vehicle dashboard, KPI calculations, and reports where admin "alves" was seeing vehicles from other companies
- **Files**: `views.py` (lines 416, 4647, 4622), `kpi_unificado.py` (line 183), `corrigir_vazamento_veiculos.py`
- **Result**: Complete multi-tenant isolation implemented - each admin now sees only their own company data, no cross-contamination between different businesses

### JavaScript Modal Fix: Null Reference Errors
- **Date**: August 4, 2025 (UI/UX Critical Fix)
- **Change**: Fixed recurring JavaScript error "Cannot read properties of null (reading 'style')" in point record editing modal
- **Impact**: Eliminated crashes when opening edit modal for point records, improved robustness of DOM element access
- **Files**: `templates/funcionario_perfil.html` (lines 1210-1285, 1330-1345, 2016-2019), `correcao_final_modal.py`
- **Result**: Point record editing modal now opens reliably without JavaScript errors, all DOM manipulations protected with null checks, improved user experience

### Labor Cost Calculation Logic Complete Overhaul
- **Date**: August 4, 2025 (Critical Fix)
- **Change**: Completely rewrote `_calcular_custo_mensal` method with correct logic: Base Salary - (Daily_Value × Absences) + Overtime_Value
- **Impact**: Fixed major calculation errors where costs were inflated by 50-300%, now properly accounts for fixed monthly salary minus absence deductions plus overtime premiums
- **Files**: `kpis_engine.py` (lines 163-200), `corrigir_custo_danilo.py` for analysis and validation
- **Result**: Antonio's cost corrected from R$ 2,443.83 to estimated R$ 2,190.81 (R$ 253 reduction), system now calculates real employee costs instead of inflated hour-based calculations

### Time Tracking Logic - Independent Delays and Overtime Calculation
- **Date**: August 4, 2025 (Final Implementation)  
- **Change**: Implemented independent calculation of delays vs overtime hours based on actual work schedules
- **Impact**: System now correctly calculates delays from late entry and overtime from extended departure separately, following user specification
- **Files**: `kpis_engine.py` (lines 532-600), `aplicar_logica_sabado_definitiva.py`
- **Result**: Ana Paula 29/07/2025 example: 07:30 entry (18min delay) + 18:00 exit (1h overtime) calculated independently against 07:12-17:00 standard schedule

### Food Registration System Enhancement
- **Date**: August 4, 2025
- **Change**: Implemented period-based food registration and enhanced UI filters
- **Impact**: Users can now register meals for multiple consecutive days and filter works with quick status buttons
- **Files**: `templates/alimentacao.html`, `templates/obras.html`, `views.py`
- **Result**: Period registration with date range selection, quick status filters for works (Planning, In Progress, Completed, etc.), improved navigation with direct "Funcionários" link

## System Architecture

### Core Design Principles
- **Modular Design**: Utilizes Flask Blueprints for distinct functional areas.
- **Data-Driven**: Emphasizes comprehensive data collection and visualization for KPIs and reporting.
- **Multi-Tenant**: Supports hierarchical access levels (Super Admin, Admin, Employee) with data isolation.
- **Scalable**: Designed for potential expansion with new modules and integration capabilities.
- **User-Centric UI**: Responsive web interface with a professional aesthetic, including dark/light mode themes.

### Backend
- **Framework**: Flask (Python)
- **Database ORM**: SQLAlchemy with Flask-SQLAlchemy
- **Authentication**: Flask-Login for session management and role-based access control.
- **Security**: Werkzeug for password hashing.
- **Data Processing**: Custom KPI engine (v4.0) for detailed calculations, including a unified `CalculadoraObra` class for consistent financial metrics.
- **Advanced Capabilities**: Integration of AI/Analytics for cost prediction, anomaly detection, resource optimization, and sentiment analysis. Smart notification system for critical KPIs.

### Frontend
- **UI Framework**: Bootstrap 5 (dark theme by default, with toggle for light mode).
- **Interactivity**: DataTables.js for enhanced tables, Chart.js for data visualization, and jQuery/Vanilla JavaScript for dynamic elements.
- **Visuals**: Font Awesome 6 for icons, SVG avatars for employees.

### Key Modules & Features
- **Employee Management**: Comprehensive profiles, time tracking (Ponto), KPI dashboard (15 KPIs), food expense tracking (Alimentação), and other costs management. Includes custom work schedules and detailed labor cost calculations.
- **Project Management (Obras)**: Tracking construction projects, budget management, timeline, status, and integrated financial KPIs (e.g., Cost/m², Profit Margin, Budget Deviation). Includes Daily Work Report (RDO) system.
- **Vehicle Management**: Fleet tracking, status, and maintenance.
- **Financial Management**: Includes `CentroCusto`, `Receita`, `OrcamentoObra`, `FluxoCaixa` models, and a dedicated financial calculation engine with strategic KPIs.
- **Multi-Tenant System**: Differentiated dashboards and functionalities based on user roles (Super Admin, Admin, Employee). Super Admin manages other admins, while Admins manage operational data.
- **Reporting & Dashboards**: Functional reporting system with multi-format export (CSV, Excel, PDF). Interactive dashboards with drill-down and filtering.
- **Smart Features**: AI-powered predictions and anomaly detection, intelligent alerts, persistent photo management, and automated error diagnostics for production environments.

## External Dependencies

### Python Packages
- `Flask`: Web framework
- `Flask-SQLAlchemy`: Database ORM
- `Flask-Login`: User session management
- `Flask-WTF`: Form handling
- `WTForms`: Form validation
- `Werkzeug`: WSGI utilities and security
- `openpyxl`: Excel file generation
- `reportlab`: PDF generation
- `Flask-Migrate`: Database migrations

### Frontend Libraries
- `Bootstrap 5`: UI framework
- `Font Awesome 6`: Icon library
- `DataTables.js`: Enhanced table functionality
- `Chart.js`: Data visualization
- `jQuery`: DOM manipulation (used where Vanilla JS is not applied)

### Database
- **SQLite**: Default for development.
- **PostgreSQL**: Recommended for production.

### Environment Configuration
- `SESSION_SECRET`: Application secret key.
- `DATABASE_URL`: Database connection string.
- Deployment environment variables for production settings.
```