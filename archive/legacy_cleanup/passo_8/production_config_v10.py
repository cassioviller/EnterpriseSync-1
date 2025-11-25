#!/usr/bin/env python3
"""
SIGE v10.0 - Configuração de Produção
Configurações otimizadas para EasyPanel/Hostinger
Autor: Joris Kuypers Architecture
Data: 2025-09-08
"""

import os
import logging
import re
from urllib.parse import urlparse

def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

class ProductionConfig:
    """Configurações específicas para produção"""
    
    # Configurações básicas
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sige-v10-digital-mastery-production-key-2025')
    DEBUG = False
    TESTING = False
    
    # Configurações de banco de dados
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 20,
        'echo': False  # Desabilitar logs SQL em produção
    }
    
    # Configurações de sessão
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'sige_v10:'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hora
    
    # Configurações de segurança
    WTF_CSRF_ENABLED = False  # Desabilitado para compatibilidade
    WTF_CSRF_TIME_LIMIT = None
    
    # Configurações de upload
    UPLOAD_FOLDER = '/app/static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Configurações específicas do SIGE
    DIGITAL_MASTERY_MODE = True
    OBSERVABILITY_ENABLED = True
    RDO_MASTERY_ENABLED = True
    
    # Configurações de logging
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configurações de cache (se necessário)
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    @staticmethod
    def init_app(app):
        """Inicializar configurações específicas da aplicação"""
        
        # Configurar logging para produção
        if not app.debug:
            import logging
            from logging.handlers import RotatingFileHandler
            
            # Criar diretório de logs se não existir
            os.makedirs('/app/logs', exist_ok=True)
            
            # Configurar handler de arquivo com rotação
            file_handler = RotatingFileHandler(
                '/app/logs/sige.log',
                maxBytes=10240000,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(ProductionConfig.LOG_FORMAT))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('🚀 SIGE v10.0 Digital Mastery iniciado em produção')
        
        # Configurar diretórios necessários
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs('/app/backups', exist_ok=True)
        
        # Validar configurações críticas
        ProductionConfig._validate_config(app)
    
    @staticmethod
    def _validate_config(app):
        """Validar configurações críticas"""
        
        # Validar URL do banco
        db_url = app.config.get('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL não configurada")
        
        # Validar se é PostgreSQL
        parsed = urlparse(db_url)
        if parsed.scheme not in ['postgresql', 'postgres']:
            raise ValueError(f"Banco não suportado: {parsed.scheme}. Use PostgreSQL.")
        
        # Validar host do banco (deve ser EasyPanel)
        if 'viajey_sige' not in parsed.hostname:
            app.logger.warning(f"⚠️  Host do banco pode estar incorreto: {parsed.hostname}")
        
        app.logger.info(f"✅ Configurações validadas - Banco: {parsed.hostname}:{parsed.port}")

class DevelopmentConfig:
    """Configurações para desenvolvimento (fallback)"""
    
    SECRET_KEY = 'dev-key'
    DEBUG = True
    TESTING = False
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///sige_dev.db')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False

# Configuração baseada no ambiente
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig  # Usar produção como padrão
}

def get_config():
    """Obter configuração baseada no ambiente"""
    env = os.environ.get('FLASK_ENV', 'production')
    return config.get(env, config['default'])

# Configurações específicas para RDO Digital Mastery
RDO_MASTERY_CONFIG = {
    'EXTRACTION_ENABLED': True,
    'VALIDATION_ENABLED': True,
    'OBSERVABILITY_ENABLED': True,
    'AUTO_DISCOVERY_ENABLED': True,
    'SUBACTIVITIES_PROCESSING': True,
    'ROBUST_EXTRACTION': True,
    'FALLBACK_STRATEGIES': True,
    'DETAILED_LOGGING': True
}

# Configurações de observabilidade
OBSERVABILITY_CONFIG = {
    'METRICS_ENABLED': True,
    'TRACING_ENABLED': True,
    'HEALTH_CHECK_ENABLED': True,
    'PERFORMANCE_MONITORING': True,
    'ERROR_TRACKING': True
}

def setup_production_environment():
    """Configurar ambiente de produção"""
    
    # Definir variáveis de ambiente para produção
    production_env = {
        'FLASK_ENV': 'production',
        'DIGITAL_MASTERY_MODE': 'true',
        'OBSERVABILITY_ENABLED': 'true',
        'RDO_MASTERY_ENABLED': 'true',
        'LOG_LEVEL': 'INFO'
    }
    
    for key, value in production_env.items():
        if key not in os.environ:
            os.environ[key] = value
    
    # Configurar timezone
    os.environ['TZ'] = 'America/Sao_Paulo'
    
    print("✅ Ambiente de produção configurado")

if __name__ == "__main__":
    setup_production_environment()
    config_class = get_config()
    print(f"📊 Configuração ativa: {config_class.__name__}")
    print(f"🔗 Banco de dados: {mask_database_url(config_class.DATABASE_URL)}")
    print(f"🎯 Digital Mastery: {config_class.DIGITAL_MASTERY_MODE}")