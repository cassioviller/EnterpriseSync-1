# SIGE v9.0
A multi-tenant business management system for SMBs, designed to automate and streamline critical operations from sales to project execution and financial management.

## Run & Operate
- **Start:** `.pythonlibs/bin/gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`
- **Entry point:** `main:app` (imports `app` from `app.py`, registers extra blueprints)
- **Required env vars:** `DATABASE_URL`, `SESSION_SECRET`
- **Optional env vars:** `N8N_WEBHOOK_URL`, `SIGE_ENABLE_DEMO_SEED`, `SIGE_ALLOW_PROD_SEED`, `SIGE_FORCE_RESEED`, `UPLOADS_PATH`

## Stack
- **Framework:** Flask 3.x with Flask-Login, Flask-SQLAlchemy, Flask-Migrate, Flask-WTF, Flask-CORS, Flask-Limiter
- **Runtime:** Python 3.11
- **ORM:** SQLAlchemy 2.x
- **Database:** PostgreSQL (via Replit's built-in PostgreSQL integration)
- **Frontend:** Bootstrap + Jinja2 templates
- **Server:** Gunicorn

## Where things live
- **Core app setup:** `app.py` (extensions, blueprints, context processors)
- **Blueprint registration (extras):** `main.py`
- **Models:** `models.py` (consolidated SQLAlchemy models)
- **Migrations:** `migrations.py` (auto-run on startup)
- **Views/blueprints:** `views/` package + many `*_views.py` files at root
- **Base HTML template:** `templates/base_completo.html`
- **Shared Jinja macros:** `templates/_partials/macros.html`
- **Theme/Styling:** `static/css/styles.css` + `static/css/sige-mobile.css`
- **Manual do Usuário:** `manual/*.md` rendered by `views/manual_views.py`
- **Services/business logic:** `services/`
- **Event handlers:** `handlers/`
- **Utilities:** `utils/`

## Architecture decisions
- **Multi-tenancy:** Data isolation via `admin_id` on every table; RBAC with `TipoUsuario` enum (SUPER_ADMIN, ADMIN, FUNCIONARIO)
- **Auth:** Flask-Login + internal `Usuario` model + Werkzeug password hashing (no external provider)
- **Event-driven:** `EventManager` (Observer pattern) for cross-module automation (payroll, costs, webhooks)
- **Auto-migrations:** `migrations.py` runs on every startup; `fix_all_admin_id_universal` ensures schema consistency
- **Resilience patterns:** Circuit breakers (`utils/circuit_breaker`), SAGA (`utils/saga`), idempotency (`utils/idempotency`)
- **Mobile shell:** `base_completo.html` renders drawer offcanvas + bottom nav on screens ≤991px; CSS in `sige-mobile.css`

## Product
- **Commercial:** Proposal generation, service catalog, parametric budgeting, client portal
- **HR & Payroll:** Employee registration, time clocking (with facial recognition via DeepFace), CLT payroll, PDF payslips
- **Construction:** Daily Work Reports (RDO), Gantt scheduling, project measurement, material tracking
- **Financial:** Double-entry bookkeeping, DRE, cash flow, chart of accounts
- **Logistics:** Warehouse management, supplier CRUD, material flow, serialized items
- **Fleet:** Vehicle management, expense tracking, TCO dashboards
- **Food:** Mobile-first restaurant entry management
- **CRM:** Kanban leads, status tracking, configurable master lists

## User preferences
- Priorizar soluções automáticas que funcionem no deploy
- Evitar intervenção manual no banco de produção
- Implementar logs detalhados para debugging
- Interface moderna com cards elegantes, gradientes e animações suaves
- Template unificado em todas as páginas do sistema
- Operações destrutivas (exclusão) devem usar POST via formulários JavaScript
- Evitar auto-fill de campos que possam interferir em filtros de busca

## Gotchas
- **Gunicorn path:** Must use `.pythonlibs/bin/gunicorn` (not `python -m gunicorn`) in Replit
- **Demo reseed:** Set `SIGE_FORCE_RESEED=1` before deploy to reseed Alfa tenant; remove immediately after
- **Cross-tenant safety:** Demo reseed aborts if cross-tenant references detected
- **APScheduler:** Not installed — scheduled jobs are disabled (non-critical)
- **DeepFace model:** Downloads ~38MB SFace model on first boot; cached at `~/.deepface/weights/`
- **RDOs legados em Rascunho:** A MIGRAÇÃO 154 foi aposentada do boot porque travava o deploy ao processar o pipeline de custos a cada inicialização. Para migrar RDOs em Rascunho legados, rodar sob demanda: `python scripts/migrar_rdos_rascunho_legados.py` (use `--dry-run` para listar antes; `--only 66,204` para escopo). RDOs que falharem aparecem em relatório claro para revisão humana, sem derrubar nada.

## Pointers
- Flask: https://flask.palletsprojects.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Bootstrap: https://getbootstrap.com/docs/
- Jinja2: https://jinja.palletsprojects.com/
