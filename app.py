import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configurações para URLs funcionarem corretamente
app.config['SERVER_NAME'] = None  # Allow localhost and other hosts
app.config['APPLICATION_ROOT'] = '/'
app.config['PREFERRED_URL_SCHEME'] = 'http'

# configure the database - usar DATABASE_URL do ambiente ou SQLite local
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///sige.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
# Desabilitar CSRF temporariamente para produção
app.config['WTF_CSRF_ENABLED'] = False
csrf.init_app(app)
login_manager.login_view = 'main.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

# Import models and views
from models import *
# from auth import auth_bp  # Removido temporariamente
from views import main_bp
from relatorios_funcionais import relatorios_bp

# Register blueprints
# app.register_blueprint(auth_bp, url_prefix='/auth')  # Removido temporariamente
app.register_blueprint(main_bp)
app.register_blueprint(relatorios_bp, url_prefix='/relatorios')

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    logging.info("Database tables created/verified")
    
    # Corrigir fotos dos funcionários automaticamente no startup
    try:
        from fix_fotos_startup import fix_fotos_startup
        if fix_fotos_startup():
            logging.info("✅ Fotos dos funcionários verificadas e corrigidas automaticamente")
        else:
            logging.warning("⚠️ Algumas fotos podem não ter sido corrigidas")
    except Exception as e:
        logging.warning(f"⚠️ Aviso: Não foi possível corrigir fotos automaticamente: {e}")
    
    # Verificar e adicionar coluna kpi_associado se necessário
    try:
        from sqlalchemy import text, inspect
        
        # Verificar se a coluna kpi_associado existe
        inspector = inspect(db.engine)
        columns = inspector.get_columns('outro_custo')
        column_names = [col['name'] for col in columns]
        
        if 'kpi_associado' not in column_names:
            logging.info("🔧 Adicionando coluna kpi_associado...")
            db.session.execute(text("ALTER TABLE outro_custo ADD COLUMN kpi_associado VARCHAR(30) DEFAULT 'outros_custos'"))
            db.session.execute(text("UPDATE outro_custo SET kpi_associado = 'outros_custos' WHERE kpi_associado IS NULL"))
            db.session.commit()
            logging.info("✅ Coluna kpi_associado adicionada com sucesso")
        else:
            logging.info("✅ Coluna kpi_associado já existe")
            
    except Exception as e:
        logging.warning(f"⚠️ Aviso: Não foi possível verificar/adicionar coluna kpi_associado: {e}")
        db.session.rollback()
