# CONFIGURAÇÕES PRODUÇÃO - SIGE v8.0

import os
from datetime import timedelta

class ConfigProducao:
    # Segurança
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sua-chave-super-secreta-producao-128-chars')
    WTF_CSRF_ENABLED = True
    
    # Banco de dados otimizado
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
        'max_overflow': 30
    }
    
    # Sessões seguras
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(hours=12)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
