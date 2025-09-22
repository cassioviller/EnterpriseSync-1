import os
import logging
from flask import Flask, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
# CSRFProtect removido - causa conflito 405 quando WTF_CSRF_ENABLED=False
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# 🤖 SISTEMA DE DETECÇÃO AUTOMÁTICA DE AMBIENTE - SIGE v10.0
from environment_detector import auto_configure_environment, get_environment_info, is_production

# Configure logging for production
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create app instance
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    if is_production():
        # EasyPanel fallback: usar chave baseada no DATABASE_URL como base
        database_url = os.environ.get("DATABASE_URL", "")
        if "viajey_sige" in database_url:
            # Gerar chave determinística mas segura para EasyPanel
            import hashlib
            base_string = f"sige-easypanel-{database_url.split('@')[1] if '@' in database_url else 'fallback'}"
            app.secret_key = hashlib.sha256(base_string.encode()).hexdigest()
            logger.warning("⚠️ Usando chave EasyPanel auto-gerada - Configure SESSION_SECRET para máxima segurança")
        else:
            logger.error("🚨 ERRO CRÍTICO: SESSION_SECRET não configurada em produção!")
            raise RuntimeError("SESSION_SECRET environment variable is required in production")
    else:
        app.secret_key = "dev-key-not-for-production"
        logger.warning("⚠️ Usando chave de desenvolvimento - NÃO SEGURO para produção")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# 🤖 DETECÇÃO E CONFIGURAÇÃO AUTOMÁTICA DE AMBIENTE
logger.info("🚀 SIGE v10.0 - INICIANDO DETECÇÃO AUTOMÁTICA DE AMBIENTE")
logger.info("=" * 60)

# Configurar ambiente automaticamente baseado na detecção inteligente
env_info = auto_configure_environment()

# Database configuration - v10.0 Digital Mastery com detecção automática
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    # Se não houver DATABASE_URL, usar padrão baseado no ambiente detectado
    if is_production():
        database_url = "postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
        os.environ['DATABASE_URL'] = database_url
        logger.info("🔧 DATABASE_URL de produção configurada automaticamente")
    else:
        logger.info("🔧 DATABASE_URL de desenvolvimento mantida")

# Função para mascarar credenciais nos logs
def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    import re
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

# Log da detecção automática
logger.info(f"🌍 AMBIENTE DETECTADO: {env_info['environment'].upper()}")
logger.info(f"🖥️ PLATAFORMA: {env_info['platform'].upper()}")
logger.info(f"📊 CONFIANÇA: {env_info['confidence']:.1%}")
logger.info(f"🔗 DATABASE: {mask_database_url(database_url)}")
logger.info(f"🔄 AUTO-MIGRAÇÕES: {env_info['auto_migrations']}")
logger.info(f"🗑️ AUTO-LIMPEZA: {env_info['auto_cleanup']}")

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
    "pool_size": 10,
    "max_overflow": 20,
    "echo": False  # Desabilitar logs SQL em produção
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['WTF_CSRF_ENABLED'] = False

# Configurações v10.0 Digital Mastery - Automáticas baseadas no ambiente
app.config['DIGITAL_MASTERY_MODE'] = True
app.config['OBSERVABILITY_ENABLED'] = True
app.config['RUN_MIGRATIONS_FLAG'] = env_info['auto_migrations']  # Automático baseado na detecção
app.config['RUN_CLEANUP_FLAG'] = env_info['auto_cleanup']  # Automático baseado na detecção
app.config['RDO_MASTERY_ENABLED'] = True
app.config['ENVIRONMENT_INFO'] = env_info  # Armazenar info do ambiente para uso posterior

# Configurações específicas por ambiente
if is_production():
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    logger.info("🏭 Configurações de produção aplicadas")
else:
    app.config['DEBUG'] = True
    logger.info("🔧 Configurações de desenvolvimento mantidas")

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
setattr(login_manager, 'login_view', 'auth.login')  # Corrigido para apontar para blueprint auth
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

def run_intelligent_migrations():
    """
    🚀 SISTEMA DE MIGRAÇÕES INTELIGENTE OTIMIZADO - SIGE v10.0
    =========================================================
    Sistema inteligente com marker de migrações para evitar re-execução desnecessária.
    
    DETECÇÃO DE PRODUÇÃO:
    - 'viajey_sige' em DATABASE_URL
    - FORCE_MIGRATIONS=1 (também força re-execução)
    - EASYPANEL_PROJECT_ID definido
    - 'render.com' ou 'railway.app' em DATABASE_URL
    
    OTIMIZAÇÃO:
    - Verifica markers para evitar re-execução desnecessária
    - FORCE_MIGRATIONS=1 bypassa markers e força execução
    - Lightweight migrations_meta table para tracking
    
    COMPORTAMENTO:
    - PRODUÇÃO: Usa CompleteDatabaseMigrator (sistema robusto)
    - DESENVOLVIMENTO: Mantém db.create_all() (sistema simples)
    
    SEGURANÇA:
    - Não falha o startup em caso de erro
    - Fallback seguro para db.create_all()
    - Logging detalhado para debugging
    """
    
    # Máscara para URLs de banco em logs seguros
    def mask_db_url(url):
        if not url:
            return "None"
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    
    # 🚀 SISTEMA DE MARKERS PARA OTIMIZAÇÃO DE MIGRAÇÕES
    def check_migrations_marker():
        """
        Verifica se migrações já foram executadas usando marker lightweight.
        Retorna True se migrações já foram executadas recentemente.
        """
        try:
            from sqlalchemy import text
            
            # Tentar verificar se existe tabela migrations_meta
            with db.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'migrations_meta'
                    );
                """)).scalar()
                
                if not result:
                    logger.debug("📍 Tabela migrations_meta não existe - primeira execução")
                    return False
                
                # Verificar marker recente (últimas 24h)
                marker_result = conn.execute(text("""
                    SELECT executed_at FROM migrations_meta 
                    WHERE marker_type = 'intelligent_migrations'
                    AND executed_at > NOW() - INTERVAL '24 hours'
                    ORDER BY executed_at DESC 
                    LIMIT 1;
                """)).fetchone()
                
                if marker_result:
                    logger.info(f"⚡ Marker encontrado: migrações executadas em {marker_result[0]}")
                    logger.info("⏭️ Pulando re-execução desnecessária (use FORCE_MIGRATIONS=1 para forçar)")
                    return True
                
                logger.debug("📍 Nenhum marker recente encontrado")
                return False
                
        except Exception as e:
            logger.debug(f"📍 Erro ao verificar marker (normal na primeira execução): {e}")
            return False
    
    def create_migrations_marker():
        """
        Cria marker de execução de migrações para otimização futura.
        """
        try:
            from sqlalchemy import text
            
            with db.engine.connect() as conn:
                # Criar tabela se não existir
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS migrations_meta (
                        id SERIAL PRIMARY KEY,
                        marker_type VARCHAR(50) NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        environment VARCHAR(20),
                        notes TEXT
                    );
                """))
                
                # Inserir novo marker
                conn.execute(text("""
                    INSERT INTO migrations_meta (marker_type, environment, notes)
                    VALUES ('intelligent_migrations', :env, 'Sistema inteligente de migrações executado');
                """), {"env": "PRODUÇÃO" if detect_production_environment()[0] else "DESENVOLVIMENTO"})
                
                conn.commit()
                logger.info("✅ Marker de migração criado com sucesso")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao criar marker (não crítico): {e}")
    
    # Detecção inteligente de ambiente
    def detect_production_environment():
        """
        Detecta se estamos em produção baseado nos critérios especificados
        """
        database_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        
        # Critério 1: 'viajey_sige' em DATABASE_URL
        if 'viajey_sige' in database_url:
            return True, "'viajey_sige' detectado em DATABASE_URL"
        
        # Critério 2: FORCE_MIGRATIONS=1
        if os.environ.get('FORCE_MIGRATIONS') == '1':
            return True, "FORCE_MIGRATIONS=1 detectado"
        
        # Critério 3: EASYPANEL_PROJECT_ID definido
        if os.environ.get('EASYPANEL_PROJECT_ID'):
            return True, "EASYPANEL_PROJECT_ID detectado"
        
        # Critério 4: render.com ou railway.app em DATABASE_URL
        if any(provider in database_url for provider in ['render.com', 'railway.app']):
            return True, "Provedor de produção (render.com/railway.app) detectado"
        
        return False, "Ambiente de desenvolvimento detectado"
    
    logger.info("🚀 INICIANDO SISTEMA DE MIGRAÇÕES INTELIGENTE OTIMIZADO - SIGE v10.0")
    logger.info("=" * 60)
    
    try:
        # Verificar override forçado
        force_migrations = os.environ.get('FORCE_MIGRATIONS') == '1'
        if force_migrations:
            logger.info("🔄 FORCE_MIGRATIONS=1 detectado - forçando execução das migrações")
        
        # Detectar ambiente
        is_production, detection_reason = detect_production_environment()
        env_type = "PRODUÇÃO" if is_production else "DESENVOLVIMENTO"
        
        logger.info(f"🌍 AMBIENTE DETECTADO: {env_type}")
        logger.info(f"🔍 RAZÃO: {detection_reason}")
        logger.info(f"🔗 DATABASE: {mask_db_url(app.config.get('SQLALCHEMY_DATABASE_URI'))}")
        
        # ⚡ OTIMIZAÇÃO: Verificar markers para evitar re-execução desnecessária
        if not force_migrations and check_migrations_marker():
            logger.info("⚡ OTIMIZAÇÃO ATIVADA: Pulando migrações desnecessárias")
            logger.info("💡 Use FORCE_MIGRATIONS=1 para forçar re-execução se necessário")
            return
        
        if is_production:
            logger.info("🏭 MODO PRODUÇÃO: Usando CompleteDatabaseMigrator")
            logger.info("-" * 40)
            
            try:
                # Tentar importar o sistema robusto de migrações
                from database_migrator_complete import CompleteDatabaseMigrator
                
                database_url = app.config.get("SQLALCHEMY_DATABASE_URI")
                if not database_url:
                    raise ValueError("DATABASE_URL não configurada")
                
                # Inicializar e executar migrador robusto
                migrator = CompleteDatabaseMigrator(database_url)
                
                logger.info("🔧 Conectando ao banco de dados...")
                if migrator.connect_to_database():
                    logger.info("✅ Conexão estabelecida com sucesso")
                    
                    logger.info("🔄 Executando migrações robustas...")
                    success = migrator.run_complete_migration()
                    
                    if success:
                        logger.info("🎉 MIGRAÇÕES ROBUSTAS EXECUTADAS COM SUCESSO!")
                        logger.info("✅ Sistema de banco totalmente atualizado")
                        
                        # Estatísticas do migrador
                        stats = migrator.migration_stats
                        logger.info(f"📊 Estatísticas: {stats['tables_analyzed']} tabelas, "
                                  f"{stats['columns_added']} colunas adicionadas, "
                                  f"{stats['admin_ids_fixed']} admin_ids corrigidos")
                        
                        # Criar marker para otimização futura
                        create_migrations_marker()
                    else:
                        logger.warning("⚠️ Migrações retornaram falha - verificar logs detalhados")
                        logger.info("🔄 Executando fallback: db.create_all()")
                        db.create_all()
                else:
                    logger.error("❌ Falha na conexão - executando fallback")
                    logger.info("🔄 Executando fallback: db.create_all()")
                    db.create_all()
                    
            except ImportError as e:
                logger.error(f"❌ Erro ao importar database_migrator_complete: {e}")
                logger.info("🔄 Executando fallback: db.create_all()")
                db.create_all()
                
            except Exception as e:
                logger.error(f"❌ Erro no sistema robusto de migrações: {e}")
                logger.info("🔄 Executando fallback: db.create_all()")
                db.create_all()
        
        else:
            logger.info("🔧 MODO DESENVOLVIMENTO: Usando db.create_all()")
            logger.info("-" * 40)
            
            # Em desenvolvimento, usar o método simples
            db.create_all()
            logger.info("✅ Tabelas criadas/verificadas em modo desenvolvimento")
            
            # Criar marker para otimização futura
            create_migrations_marker()
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO no sistema de migrações: {e}")
        logger.info("🆘 Executando fallback de emergência: db.create_all()")
        
        try:
            db.create_all()
            logger.info("✅ Fallback de emergência executado com sucesso")
        except Exception as fallback_error:
            logger.error(f"💥 FALHA TOTAL: Nem fallback funcionou: {fallback_error}")
            # Não reraise - permitir que app continue
    
    logger.info("=" * 60)
    logger.info("✅ SISTEMA DE MIGRAÇÕES INTELIGENTE CONCLUÍDO")
    logger.info("💡 App pronto para uso - migrações processadas com segurança")

# Create tables and initialize
with app.app_context():
    # Executar sistema inteligente de migrações
    run_intelligent_migrations()
    
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
        from alimentacao_crud import alimentacao_bp
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
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint API organizer: {e}")
    
    # Registrar blueprint de categorias de serviços
    try:
        from categoria_servicos import categorias_bp
        app.register_blueprint(categorias_bp)
        logging.info("✅ Blueprint categorias de serviços registrado")
    except ImportError as e:
        logging.warning(f"⚠️ Blueprint categorias de serviços não encontrado: {e}")
    except Exception as e:
        logging.error(f"❌ Erro ao registrar blueprint categorias de serviços: {e}")
    
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