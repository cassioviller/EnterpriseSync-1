# CONFIGURAÇÃO DE PRODUÇÃO - SIGE v8.0
# Gerado automaticamente pelo build.sh

import os

# Configurações da aplicação
FLASK_ENV = 'production'
DEBUG = False
TESTING = False

# Configurações de banco
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0
}

# Configurações de segurança
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Configurações de aplicação
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

print("✅ Configuração de produção carregada")
