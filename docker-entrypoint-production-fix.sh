#!/bin/bash
# DOCKER ENTRYPOINT PRODUCTION FIX - SIGE v8.0
# Script otimizado para resolver loops infinitos em produção

set -e

echo "🚀 SIGE v8.0 - Iniciando (Production Fix v2.0 - 01/09/2025)"
echo "📍 Modo: ${FLASK_ENV:-production}"

# Configuração silenciosa do ambiente
export PYTHONPATH=/app
export FLASK_APP=main.py
export FLASK_ENV=production

# Aguardar PostgreSQL com timeout reduzido
echo "⏳ Verificando PostgreSQL..."

# Configuração padrão EasyPanel
DB_HOST="${DATABASE_HOST:-viajey_sige}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_USER="${DATABASE_USER:-sige}"

TIMEOUT=20
COUNTER=0

until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout PostgreSQL (${TIMEOUT}s)"
        exit 1
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# Inicialização mínima da aplicação (sem loops)
echo "🔧 Inicializando aplicação..."
python -c "
import os
import sys
import warnings

# Suprimir warnings para evitar logs excessivos
warnings.filterwarnings('ignore')
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

sys.path.append('/app')

try:
    from app import app
    print('✅ App carregado')
except Exception as e:
    print(f'❌ Erro: {e}')
    sys.exit(1)
" 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo "❌ Falha na inicialização"
    exit 1
fi

echo "🎯 Aplicação pronta!"

# Executar comando com configurações otimizadas
exec "$@"