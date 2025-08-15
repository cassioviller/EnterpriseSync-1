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

# Database configuration - Optimized for EasyPanel deployment
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    # EasyPanel default PostgreSQL URL pattern
    database_url = "postgresql://sige:sige@viajey_sige:5432/sige"

# Convert postgres:// to postgresql:// for SQLAlchemy compatibility
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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

# Import all models (now consolidated)
from models import *
logging.info("✅ Todos os modelos importados do arquivo consolidado")

# Import views
from views import main_bp
from production_routes import production_bp
from error_handlers import register_error_handlers
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
app.register_blueprint(production_bp, url_prefix='/prod')

# Register error handlers
register_error_handlers(app)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Função para templates
@app.template_global()
def obter_foto_funcionario(funcionario):
    """Obter foto do funcionário (base64 ou padrão)"""
    if funcionario.foto_base64:
        return funcionario.foto_base64
    elif funcionario.foto:
        return url_for('static', filename=funcionario.foto)
    else:
        # SVG padrão baseado no nome
        iniciais = ''.join([nome[0].upper() for nome in funcionario.nome.split()[:2]])
        cores = ['#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8', '#6f42c1']
        cor_fundo = cores[hash(funcionario.nome) % len(cores)]
        
        svg_avatar = f'''data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80">
            <rect width="80" height="80" fill="{cor_fundo}"/>
            <text x="40" y="45" font-family="Arial, sans-serif" font-size="24" font-weight="bold" 
                  text-anchor="middle" fill="white">{iniciais}</text>
        </svg>'''
        return svg_avatar

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
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint serviços não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint serviços: {e}")
    
    # Modelos de propostas já estão consolidados em models.py
    logging.info("✅ Modelos de propostas importados do arquivo consolidado")
    
    # Registrar blueprint de propostas
    try:
        from propostas_views import propostas_bp
        app.register_blueprint(propostas_bp, url_prefix='/propostas')
        logging.info("✅ Blueprint propostas registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint propostas não encontrado: {e}")
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
        import bypass_auth
        logging.info("🔓 Sistema de bypass de autenticação carregado")
    except Exception as e:
        logging.error(f"Erro ao carregar bypass: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)