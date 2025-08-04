# SIGE - Sistema Integrado de Gestão Empresarial

## Overview

SIGE (Sistema Integrado de Gestão Empresarial) is a comprehensive business management system designed for "Estruturas do Vale", a construction company. It provides integrated management of employees, projects, vehicles, timekeeping, and food expenses. The system aims to streamline operations, enhance decision-making through data visualization and advanced analytics, and provide detailed financial insights for construction project management. Its ambition is to transform into a specialized solution for metallic structures.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (August 2025)

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

### Saturday Worked Logic Final Implementation
- **Date**: August 4, 2025 (Final Solution)
- **Change**: Complete data cleanup, duplicate removal, and definitive Saturday worked logic implementation with template fixes
- **Impact**: Removed data inconsistencies, cleaned duplicates, applied correct Brazilian labor law calculation (all hours = extras at 50% rate, zero delay always), template updated to show correct values
- **Files**: `solucao_definitiva_sabado.py`, `aplicar_logica_sabado_urgente.py`, `templates/funcionario_perfil.html` (Saturday-specific display logic), server restarted, cache cleared
- **Result**: João Silva Santos 05/07/2025: 7.92h extras at 50% rate, 0min delay, sabado_horas_extras type, template shows "7.9h - 50%" for extras and "-" for delay, 53 Saturday records updated, 100% mathematical accuracy and display accuracy achieved

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