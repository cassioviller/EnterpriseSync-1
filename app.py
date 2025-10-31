import os
import logging
from flask import Flask, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
# CSRFProtect removido - causa conflito 405 quando WTF_CSRF_ENABLED=False
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging for production
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create app instance
app = Flask(__name__)

# 🔒 CRITICAL SECURITY: SESSION_SECRET handling
# SESSION_SECRET fixo no código (pode ser sobrescrito por variável de ambiente)
secret_key = os.environ.get("SESSION_SECRET", "Oqv_zfDLhygGT5AF8t3llIIC_qnryXzGWXxgM0jCvC4")

if secret_key == "Oqv_zfDLhygGT5AF8t3llIIC_qnryXzGWXxgM0jCvC4":
    logger.info("✅ Usando SESSION_SECRET padrão do código")
else:
    logger.info("✅ Usando SESSION_SECRET da variável de ambiente")

app.secret_key = secret_key
app.config["SECRET_KEY"] = secret_key
logger.info(f"✅ Secret key configurado (length: {len(secret_key)})")

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration - v10.0 Digital Mastery
database_url = os.environ.get("DATABASE_URL", "postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable")

# Auto-detectar ambiente - CREDENTIALS MASCARADAS POR SEGURANÇA
def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    import re
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

if "neon" in database_url or "localhost" in database_url:
    # DESENVOLVIMENTO
    logger.info(f"🔧 DESENVOLVIMENTO DATABASE: {mask_database_url(database_url)}")
else:
    # PRODUÇÃO - EasyPanel
    logger.info(f"🔧 PRODUÇÃO DATABASE: {mask_database_url(database_url)}")

# Convert postgres:// to postgresql:// for SQLAlchemy compatibility
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Garantir que sslmode=disable está presente para EasyPanel
if database_url and "sslmode=" not in database_url:
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}sslmode=disable"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "pool_size": 20,        # ✅ OTIMIZAÇÃO: Dobrado de 10→20 para suportar mais concorrência
    "max_overflow": 40,     # ✅ OTIMIZAÇÃO: Dobrado de 20→40 (total 60 conexões vs 30 anterior)
    "pool_timeout": 30,     # ✅ OTIMIZAÇÃO: Timeout explícito para evitar deadlocks
    "echo": False  # Desabilitar logs SQL em produção
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['WTF_CSRF_ENABLED'] = False

# Configurações v10.0 Digital Mastery
app.config['DIGITAL_MASTERY_MODE'] = True
app.config['OBSERVABILITY_ENABLED'] = True
app.config['RUN_MIGRATIONS_FLAG'] = os.environ.get('RUN_MIGRATIONS', '').lower() in ['1', 'true', 'yes']
app.config['RDO_MASTERY_ENABLED'] = True

# Configurações específicas para resolver erro SERVER_NAME  
app.config['SERVER_NAME'] = None  # Permite qualquer host
app.config['APPLICATION_ROOT'] = '/'  # Raiz da aplicação  
app.config['PREFERRED_URL_SCHEME'] = 'http'  # Esquema padrão

# Configure CORS for AJAX requests
CORS(app, origins="*", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Initialize extensions
from models import db  # Import the db instance from models
db.init_app(app)

migrate = Migrate()
migrate.init_app(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

# Context processor para configurações da empresa
@app.context_processor
def inject_company_config():
    """Injeta configurações da empresa em todos os templates"""
    try:
        from flask_login import current_user
        from models import ConfiguracaoEmpresa
        
        if current_user and current_user.is_authenticated:
            admin_id = getattr(current_user, 'admin_id', None) or current_user.id
            config_empresa = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
            
            if config_empresa:
                return {
                    'config_empresa': config_empresa,
                    'empresa_cores': {
                        'primaria': config_empresa.cor_primaria or '#007bff',
                        'secundaria': config_empresa.cor_secundaria or '#6c757d',
                        'fundo_proposta': config_empresa.cor_fundo_proposta or '#f8f9fa'
                    }
                }
        
        # Valores padrão se não houver configuração
        return {
            'config_empresa': None,
            'empresa_cores': {
                'primaria': '#007bff',
                'secundaria': '#6c757d', 
                'fundo_proposta': '#f8f9fa'
            }
        }
    except Exception:
        # Fallback em caso de erro
        return {
            'config_empresa': None,
            'empresa_cores': {
                'primaria': '#007bff',
                'secundaria': '#6c757d',
                'fundo_proposta': '#f8f9fa'
            }
        }

# CORREÇÃO CRÍTICA: CSRF removido completamente para evitar conflito 405
# CSRFProtect estava sendo inicializado mesmo com WTF_CSRF_ENABLED = False
# Esta é a causa principal dos erros 405 Method Not Allowed

# Configurar CORS para requisições AJAX das APIs
CORS(app, origins="*", methods=["GET", "POST", "PUT", "DELETE"], 
     allow_headers=["Content-Type", "Authorization"])

# Import all models (now consolidated)
from models import *
logging.info("✅ Todos os modelos importados do arquivo consolidado")

# Import Event Manager to register integration handlers
try:
    import event_manager
    logging.info(f"✅ Event Manager inicializado - {len(event_manager.EventManager.list_events())} eventos registrados")
except Exception as e:
    logging.warning(f"⚠️ Event Manager não carregado: {e}")

# Import event handlers to auto-register
try:
    import handlers.folha_handlers
    logging.info("✅ Handler de folha de pagamento registrado")
except Exception as e:
    logging.warning(f"⚠️ Handler de folha não carregado: {e}")

try:
    import handlers.propostas_handlers
    logging.info("✅ Handler de propostas comerciais registrado")
except Exception as e:
    logging.warning(f"⚠️ Handler de propostas não carregado: {e}")

try:
    import handlers.financeiro_handlers
    logging.info("✅ Handler de financeiro registrado")
except Exception as e:
    logging.warning(f"⚠️ Handler de financeiro não carregado: {e}")

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
    app.register_blueprint(almoxarifado_bp)
    logging.info("✅ Blueprint almoxarifado registrado")
except ImportError:
    logging.warning("Almoxarifado views não disponível")

try:
    from ponto_views import ponto_bp
    app.register_blueprint(ponto_bp)
    logging.info("✅ Blueprint ponto eletrônico registrado")
except ImportError:
    logging.warning("Ponto views não disponível")

# Register main blueprint
app.register_blueprint(main_bp)
app.register_blueprint(production_bp, url_prefix='/prod')

# Register ServicoObraReal blueprint
try:
    from crud_servico_obra_real import servico_obra_real_bp
    app.register_blueprint(servico_obra_real_bp)
    logging.info("✅ Blueprint ServicoObraReal registrado")
except ImportError as e:
    logging.warning(f"ServicosObraReal não disponível: {e}")

# Test routes removed for production cleanliness

# Register error handlers
register_error_handlers(app)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Função para templates
@app.template_global()
def obter_foto_funcionario(funcionario):
    """Obter foto do funcionário (base64 ou padrão)"""
    from flask import url_for  # Import necessário para template_global
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
    # Import models
    import models  # noqa: F401
    
    db.create_all()
    logging.info("Database tables created/verified")
    
    # ✅ MIGRAÇÕES AUTOMÁTICAS SEMPRE ATIVAS - SIMPLICIDADE MÁXIMA
    logger.info("🔄 Executando migrações automáticas do banco de dados...")
    try:
        from migrations import executar_migracoes
        executar_migracoes()
        logger.info("✅ Migrações executadas com sucesso!")
    except Exception as e:
        logger.error(f"❌ Erro ao executar migrações: {e}")
        logger.warning("⚠️ Aplicação continuará mesmo com erro nas migrações")
    
    # 🔧 AUTO-FIX UNIVERSAL - Correção automática de admin_id em TODAS as tabelas
    # Executa SEMPRE no startup para garantir que TODAS as tabelas tenham admin_id
    try:
        from fix_all_admin_id_universal import auto_fix_all_admin_id
        auto_fix_all_admin_id()
    except Exception as e:
        logger.error(f"❌ Erro no auto-fix universal: {e}")
    
    # 🗑️ SISTEMA DE LIMPEZA DE VEÍCULOS - CRITICAL INTEGRATION
    # Executa limpeza de tabelas obsoletas de veículos quando RUN_CLEANUP_VEICULOS=1
    try:
        from migration_cleanup_veiculos_production import run_migration_if_needed
        cleanup_success = run_migration_if_needed()
        if cleanup_success:
            logger.info("✅ Migration de limpeza de veículos processada com sucesso")
        else:
            logger.warning("⚠️ Migration de limpeza de veículos falhou ou não foi necessária")
    except ImportError:
        logger.warning("⚠️ Migration de limpeza de veículos não disponível")
    except Exception as e:
        logger.error(f"❌ Erro na migration de limpeza de veículos: {e}")
        # Não interromper o app, apenas logar erro
        logger.info("📝 Para executar migrações: RUN_MIGRATIONS=1 gunicorn --bind 0.0.0.0:5000 main:app")
    
    # Register additional blueprints
    try:
        from folha_pagamento_views import folha_bp
        app.register_blueprint(folha_bp, url_prefix='/folha')
        logging.info("✅ Blueprint folha de pagamento registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint folha de pagamento: {e}")
    
    try:
        from contabilidade_views import contabilidade_bp
        app.register_blueprint(contabilidade_bp, url_prefix='/contabilidade')
        logging.info("✅ Blueprint contabilidade registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint contabilidade: {e}")
    
    # Blueprint financeiro v9.0
    try:
        from financeiro_views import financeiro_bp
        app.register_blueprint(financeiro_bp)
        logging.info("✅ Blueprint financeiro v9.0 registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint financeiro: {e}")
    
    # Blueprint custos v9.0
    try:
        from custos_views import custos_bp
        app.register_blueprint(custos_bp)
        logging.info("✅ Blueprint custos v9.0 registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint custos: {e}")
    
    # Blueprint templates de propostas
    try:
        from templates_views import templates_bp
        app.register_blueprint(templates_bp, url_prefix='/templates')
        logging.info("✅ Blueprint templates registrado")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint templates: {e}")
    
    # Blueprint de serviços será registrado em main.py para evitar conflitos
    
    # Registrar blueprint de alimentação
    try:
        from alimentacao_views import alimentacao_bp
        app.register_blueprint(alimentacao_bp)
        logging.info("✅ Blueprint alimentação registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint alimentação não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint alimentação: {e}")
    
    # Modelos de propostas já estão consolidados em models.py
    logging.info("✅ Modelos de propostas importados do arquivo consolidado")
    
    # Registrar blueprint de propostas consolidado
    try:
        from propostas_consolidated import propostas_bp
        app.register_blueprint(propostas_bp, url_prefix='/propostas')
        logging.info("✅ Blueprint propostas consolidado registrado")
    except ImportError as e:
        # Fallback para blueprint antigo
        try:
            from propostas_views import propostas_bp
            app.register_blueprint(propostas_bp, url_prefix='/propostas')
            logging.info("✅ Blueprint propostas (fallback) registrado")
        except ImportError as e2:
            logging.warning(f"⚠️ Blueprint propostas não encontrado: {e} | {e2}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint propostas: {e}")
    
    # Registrar API de organização
    try:
        from api_organizer import api_organizer
        app.register_blueprint(api_organizer)
        logging.info("✅ Blueprint API organizer registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint API organizer não encontrado: {e}")
    
    # Registrar blueprint de categorias de serviços
    try:
        from categoria_servicos import categorias_bp
        app.register_blueprint(categorias_bp)
        logging.info("✅ Blueprint categorias de serviços registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint categorias de serviços não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint categorias de serviços: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint API organizer: {e}")
    
    # Registrar blueprint de configurações
    try:
        from configuracoes_views import configuracoes_bp
        app.register_blueprint(configuracoes_bp)
        logging.info("✅ Blueprint configurações registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint configurações não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint configurações: {e}")
    
    # Registrar API limpa de serviços da obra
    try:
        from api_servicos_obra_limpa import api_servicos_obra_bp
        app.register_blueprint(api_servicos_obra_bp)
        logging.info("✅ Blueprint API serviços obra LIMPA registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint API serviços obra limpa não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint API serviços obra limpa: {e}")
    
    # Registrar blueprint EQUIPE - Sistema de Gestão Lean
    try:
        from equipe_views import equipe_bp
        app.register_blueprint(equipe_bp)
        logging.info("✅ Blueprint EQUIPE (gestão lean) registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint EQUIPE não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint EQUIPE: {e}")
    
    # Registrar blueprint FROTA - Novo sistema de gestão de veículos
    try:
        from frota_views import frota_bp
        app.register_blueprint(frota_bp)
        logging.info("✅ Blueprint FROTA registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint FROTA não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint FROTA: {e}")
    
    # Sistema avançado de veículos removido (código obsoleto limpo)
    
    # Photo migration moved to migrations.py for cleaner app initialization
    
    # Development authentication bypass (PERMANENTEMENTE DESABILITADO)
    # Causa conflitos de admin_id entre sessões
    # if os.environ.get('FLASK_ENV') != 'production':
    #     try:
    #         bypass_auth removido
    #         logging.info("🔓 Sistema de bypass de autenticação carregado")
    #     except Exception as e:
    #         logging.error(f"Erro ao carregar bypass: {e}")
    
    logging.info("🔒 Sistema de bypass PERMANENTEMENTE desabilitado - admin_id consistente")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)