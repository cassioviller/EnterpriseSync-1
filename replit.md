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

## User Preferences

Preferred communication style: Simple, everyday language.