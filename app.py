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
