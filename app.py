import os
import logging
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create app instance
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///sige.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config['WTF_CSRF_ENABLED'] = False

# Initialize extensions
from models import db  # Import the db instance from models
db.init_app(app)

migrate = Migrate()
migrate.init_app(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

csrf = CSRFProtect()
csrf.init_app(app)

# Import models after db initialization
from models import *

# Import models de serviços
try:
    from models_servicos import *
    logging.info("✅ Modelos de serviços importados")
except Exception as e:
    logging.error(f"❌ Erro ao importar modelos de serviços: {e}")

# Import views
from views import main_bp
try:
    from relatorios_funcionais import relatorios_bp
    app.register_blueprint(relatorios_bp, url_prefix='/relatorios')
except ImportError:
    logging.warning("Relatórios funcionais não disponível")

try:
    from almoxarifado_views import almoxarifado_bp
    app.register_blueprint(almoxarifado_bp, url_prefix='/almoxarifado')
except ImportError:
    logging.warning("Almoxarifado views não disponível")

# Register main blueprint
app.register_blueprint(main_bp)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Create tables and initialize
with app.app_context():
    db.create_all()
    logging.info("Database tables created/verified")
    
    # Register additional blueprints
    try:
        from folha_pagamento_views import folha_bp
        app.register_blueprint(folha_bp, url_prefix='/folha-pagamento')
        logging.info("✅ Blueprint folha de pagamento registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint folha de pagamento: {e}")
    
    try:
        from contabilidade_views import contabilidade_bp
        app.register_blueprint(contabilidade_bp, url_prefix='/contabilidade')
        logging.info("✅ Blueprint contabilidade registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint contabilidade: {e}")
    
    # Registrar blueprint de serviços
    try:
        from servicos_views import servicos_bp
        app.register_blueprint(servicos_bp, url_prefix='/servicos')
        logging.info("✅ Blueprint serviços registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint serviços: {e}")
    
    # Importar modelos de propostas
    try:
        from models_propostas import PropostaComercialSIGE, PropostaItem, PropostaArquivo, PropostaTemplate
        logging.info("✅ Modelos de propostas importados")
    except ImportError as e:
        logging.warning(f"⚠️ Erro ao importar modelos de propostas: {e}")
    
    # Registrar blueprint de propostas
    try:
        from propostas_views import propostas_bp
        app.register_blueprint(propostas_bp, url_prefix='/propostas')
        logging.info("✅ Blueprint propostas registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint propostas: {e}")
    
    # Migrate photos if necessary
    try:
        import base64
        funcionarios_sem_base64 = Funcionario.query.filter(
            Funcionario.foto.isnot(None),
            Funcionario.foto_base64.is_(None)
        ).all()
        
        migrados = 0
        for funcionario in funcionarios_sem_base64:
            try:
                caminho_foto = os.path.join('static', funcionario.foto)
                if os.path.exists(caminho_foto) and caminho_foto.endswith('.svg'):
                    with open(caminho_foto, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                    funcionario.foto_base64 = f"data:image/svg+xml;base64,{svg_base64}"
                    migrados += 1
            except Exception:
                pass
        
        if migrados > 0:
            db.session.commit()
            logging.info(f"✅ {migrados} fotos migradas para base64")
        else:
            logging.info("✅ Fotos já estão em base64")
            
    except Exception as e:
        logging.error(f"Erro na migração de fotos: {e}")

    # Importar bypass de autenticação para desenvolvimento
    try:
        import simple_bypass
        logging.info("🔓 Sistema de bypass simples carregado")
    except Exception as e:
        logging.error(f"Erro ao carregar bypass: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)