# SIGE - Sistema Integrado de Gestão Empresarial

## Overview

SIGE (Sistema Integrado de Gestão Empresarial) is a comprehensive business management system for construction companies, specifically designed for "Estruturas do Vale". It provides integrated management of employees, projects, vehicles, timekeeping, and food expenses. The system aims to streamline operations, enhance decision-making through data visualization and advanced analytics, and provide detailed financial insights. Its ambition is to transform into a specialized solution for metallic structures.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

**Latest Update - August 8, 2025:**
- ✅ Resolved critical `UndefinedColumn` error for `admin_id` in production environments
- ✅ Created robust deployment script (`fix_admin_id_production.py`) for production fixes
- ✅ Fixed template dependencies in `funcionario_perfil.html` to use available KPI fields
- ✅ Implemented comprehensive SQLAlchemy cache clearing and metadata reflection
- ✅ Validated complete functionality: 58 outro_custo records with proper admin_id assignment
- ✅ Documented complete solution in `SOLUCAO_ADMIN_ID_PRODUCAO.md` for future deployments

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
- **Data Processing**: Custom KPI engine for detailed calculations, including a unified `CalculadoraObra` class for consistent financial metrics.
- **Advanced Capabilities**: Integration of AI/Analytics for cost prediction, anomaly detection, resource optimization, and sentiment analysis. Smart notification system for critical KPIs.
- **Key Technical Implementations**:
    - Overtime calculation based on each employee's registered standard work schedule.
    - Automatic pre-filling of RDO activities with percentages from previous entries for the same project.
    - Period-based food registration.
    - Complete overhaul of labor cost calculation logic.

### Frontend
- **UI Framework**: Bootstrap 5 (dark theme by default, with toggle for light mode).
- **Interactivity**: DataTables.js for enhanced tables, Chart.js for data visualization, and jQuery/Vanilla JavaScript for dynamic elements.
- **Visuals**: Font Awesome 6 for icons, SVG avatars for employees.

### Key Modules & Features
- **Employee Management**: Comprehensive profiles, time tracking (Ponto), KPI dashboard (15 KPIs), food expense tracking (Alimentação), and other costs management. Includes custom work schedules, detailed labor cost calculations, and employee activation/deactivation system with proper filtering.
- **Project Management (Obras)**: Tracking construction projects, budget management, timeline, status, and integrated financial KPIs (e.g., Cost/m², Profit Margin, Budget Deviation). Includes Daily Work Report (RDO) system.
- **Vehicle Management**: Fleet tracking, status, and maintenance.
- **Financial Management**: Includes `CentroCusto`, `Receita`, `OrcamentoObra`, `FluxoCaixa` models, and a dedicated financial calculation engine with strategic KPIs.
- **Multi-Tenant System**: Differentiated dashboards and functionalities based on user roles (Super Admin, Admin, Employee). Super Admin manages other admins, while Admins manage operational data. Data integrity protected against inactive employee leakage.
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
- `jQuery`: DOM manipulation

### Database
- **SQLite**: Default for development.
- **PostgreSQL**: Recommended for production.