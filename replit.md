# SIGE - Sistema Integrado de Gestão Empresarial

## Overview

SIGE (Sistema Integrado de Gestão Empresarial) is a comprehensive business management system tailored for construction companies, specifically "Estruturas do Vale". Its core purpose is to provide integrated management of employees, projects, vehicles, timekeeping, and food expenses. The system aims to streamline operations, enhance decision-making through advanced analytics and data visualization, and offer detailed financial insights. The long-term ambition for SIGE is to evolve into a specialized solution for metallic structures.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

**Latest Update - August 12, 2025 (12:25 BRT) - HEADER DASHBOARD PROFISSIONAL FINALIZADO:**
- 🎨 **HEADER DASHBOARD PROFISSIONAL FINALIZADO**: Layout moderno e funcional implementado
  - **Internal Server Error Resolvido**: URLs corrigidas para caminhos diretos (/funcionarios, /obras, etc.)
  - **Design Profissional**: Ícone circular azul 56px com gradiente, tipografia H2 em negrito
  - **Layout Responsivo**: Container flexbox com alinhamento perfeito e espaçamento consistente
  - **Navegação Organizada**: 6 módulos em 3 grupos de botões temáticos
  - **Sistema de Cores**: Cada módulo com cor específica (primary, success, info, warning, secondary)
  - **UX/UI Melhorado**: Interface limpa, intuitiva e profissional
- 🎯 **MÓDULO DE SERVIÇOS 100% FUNCIONAL**: Sistema completo para propostas comerciais
  - **5 Modelos Integrados**: ServicoMestre, SubServico, TabelaComposicao, ItemTabelaComposicao, ItemServicoPropostaDinamica
  - **Sistema CRUD Completo**: Dashboard, listagem, criação, edição, visualização para serviços e tabelas
  - **8+ Endpoints Funcionais**: /servicos/dashboard, /servicos/servicos, /servicos/tabelas, APIs de integração
  - **3+ Templates Criados**: Dashboard principal, formulários com preview, listagens com filtros
  - **Códigos Automáticos**: Sistema hierárquico SRV001, SRV001.001, SRV002.001...
  - **Preview de Preços**: Cálculo dinâmico de margem de lucro em tempo real
  - **Tabelas de Composição**: Sistema avançado por tipo de estrutura (galpão, edifício, ponte)
  - **Parâmetros Técnicos**: Área mínima/máxima, altura, fatores multiplicadores
  - **Multi-tenant**: Isolamento completo de dados por administrador
  - **APIs de Integração**: Endpoints para aplicar serviços completos em propostas
  - **Sistema de Subserviços**: Componentes hierárquicos com preços independentes
  - **Blueprint Registrado**: /servicos/* totalmente operacional no app.py
  - **Correções SQLAlchemy**: Relacionamentos entre Proposta e ItemServicoPropostaDinamica funcionando
  - **Templates Responsivos**: Interface profissional com Bootstrap e JavaScript interativo

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
    - Overtime calculation based on each employee's registered standard work schedule, compliant with Brazilian labor legislation (CLT).
    - Automatic pre-filling of RDO activities with percentages from previous entries for the same project.
    - Period-based food registration.
    - Comprehensive labor cost calculation logic, including DSR (weekly paid rest) calculation compliant with Lei 605/49.

### Frontend
- **UI Framework**: Bootstrap 5 (dark theme by default, with toggle for light mode).
- **Interactivity**: DataTables.js for enhanced tables, Chart.js for data visualization, and jQuery/Vanilla JavaScript for dynamic elements.
- **Visuals**: Font Awesome 6 for icons, SVG avatars for employees.

### Key Modules & Features
- **Employee Management**: Comprehensive profiles, time tracking (Ponto), KPI dashboard, food expense tracking (Alimentação), and other costs management. Includes custom work schedules, detailed labor cost calculations, and employee activation/deactivation.
- **Project Management (Obras)**: Tracking construction projects, budget management, timeline, status, and integrated financial KPIs (e.g., Cost/m², Profit Margin, Budget Deviation). Includes Daily Work Report (RDO) system.
- **Commercial Management**: Complete proposal system with client portal integration, automatic conversion to projects, and professional proposal generation.
- **Client Portal**: Dedicated client dashboard for project progress tracking, RDO viewing, photo galleries, and automatic notifications.
- **Team Management**: Advanced allocation system with Kanban/Calendar interface, automatic RDO generation, conflict prevention, and comprehensive reporting.
- **Warehouse Management**: Complete inventory control with material tracking, movement history, RDO integration, stock level monitoring, barcode scanning, and XML NFe import processing.
- **Vehicle Management**: Fleet tracking, status, and maintenance.
- **Financial Management**: Includes `CentroCusto`, `Receita`, `OrcamentoObra`, `FluxoCaixa` models, and a dedicated financial calculation engine with strategic KPIs. Integrates a complete accounting system with Brazilian chart of accounts.
- **Multi-Tenant System**: Differentiated dashboards and functionalities based on user roles (Super Admin, Admin, Employee).
- **Reporting & Dashboards**: Functional reporting system with multi-format export (CSV, Excel, PDF). Interactive dashboards with drill-down and filtering.
- **Smart Features**: AI-powered predictions and anomaly detection, intelligent alerts, persistent photo management, and automated error diagnostics.

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