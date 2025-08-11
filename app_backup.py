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

# Usar a instância do models
from models import db
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

# Importar e configurar models usando o padrão correto
from models import db as models_db
from models import *

# Conectar a instância do db
models_db.init_app(app)

# Import views após models estarem configurados
# from auth import auth_bp  # Removido temporariamente
from views import main_bp
from relatorios_funcionais import relatorios_bp
from almoxarifado_views import almoxarifado_bp

# Register blueprints
# app.register_blueprint(auth_bp, url_prefix='/auth')  # Removido temporariamente
app.register_blueprint(main_bp)
app.register_blueprint(relatorios_bp, url_prefix='/relatorios')
app.register_blueprint(almoxarifado_bp, url_prefix='/almoxarifado')
# Blueprint de folha de pagamento será registrado após inicialização

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Create tables if they don't exist
with app.app_context():
    models_db.create_all()
    logging.info("Database tables created/verified")
    
    # Registrar blueprint de folha de pagamento após inicialização
    try:
        from folha_pagamento_views import folha_bp
        app.register_blueprint(folha_bp, url_prefix='/folha-pagamento')
        logging.info("✅ Blueprint folha de pagamento registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint folha de pagamento: {e}")
    
    # Registrar blueprint de contabilidade após inicialização
    try:
        from contabilidade_views import contabilidade_bp
        app.register_blueprint(contabilidade_bp, url_prefix='/contabilidade')
        logging.info("✅ Blueprint contabilidade registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint contabilidade: {e}")
    
    # Migrar fotos se necessário
    try:
        import base64
        import os
        
        funcionarios_sem_base64 = Funcionario.query.filter(
            Funcionario.foto.isnot(None),
            Funcionario.foto_base64.is_(None)
        ).all()
        
        for funcionario in funcionarios_sem_base64:
            try:
                caminho_foto = os.path.join('static', funcionario.foto)
                if os.path.exists(caminho_foto) and caminho_foto.endswith('.svg'):
                    with open(caminho_foto, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                    funcionario.foto_base64 = f"data:image/svg+xml;base64,{svg_base64}"
            except Exception:
                pass
        
        if migrados > 0:
            models_db.session.commit()
            logging.info(f"✅ {migrados} fotos migradas para base64")
        else:
            logging.info("✅ Fotos já estão em base64")
            
    except Exception as e:
        logging.warning(f"⚠️ Aviso na migração foto_base64: {e}")

# Adicionar função para templates
@app.context_processor
def inject_foto_funcionario():
    from utils import obter_foto_funcionario
    return dict(obter_foto_funcionario=obter_foto_funcionario)
    

