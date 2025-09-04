#!/bin/bash
# Script de entrada EasyPanel - CORREÇÃO 405 Method Not Allowed
set -e

echo "🚀 Iniciando SIGE v8.1 (EasyPanel - Correção 405)"

# Configurações específicas EasyPanel para resolver erro 405
export WTF_CSRF_ENABLED=false
export FLASK_ENV=production
export FLASK_DEBUG=false

# Verificar DATABASE_URL
if [[ -z "${DATABASE_URL}" ]]; then
    echo "⚠️  DATABASE_URL não definida, usando padrão EasyPanel"
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige"
fi

# Adicionar sslmode=disable
if [[ "${DATABASE_URL}" != *"sslmode="* ]]; then
    if [[ "${DATABASE_URL}" == *"?"* ]]; then
        export DATABASE_URL="${DATABASE_URL}&sslmode=disable"
    else
        export DATABASE_URL="${DATABASE_URL}?sslmode=disable"
    fi
    echo "🔒 SSL desabilitado para EasyPanel"
fi

# Aguardar PostgreSQL
echo "⏳ Verificando conexão com PostgreSQL..."
if [[ $DATABASE_URL =~ postgres(ql)?://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
    DB_HOST="${BASH_REMATCH[4]}"
    DB_PORT="${BASH_REMATCH[5]}"
    DB_USER="${BASH_REMATCH[2]}"
else
    DB_HOST="viajey_sige"
    DB_PORT="5432"
    DB_USER="sige"
fi

echo "🔍 Conectando em: ${DB_HOST}:${DB_PORT}"

# Aguardar banco
TIMEOUT=60
COUNTER=0
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout: PostgreSQL não disponível"
        exit 1
    fi
    echo "⏳ PostgreSQL não disponível, tentativa $((COUNTER + 1))/${TIMEOUT}..."
    sleep 2
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# Executar migrações
echo "🔄 Executando migrações automáticas..."
python -c "
import sys, traceback
from app import app, db

with app.app_context():
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        print('✅ Conexão com banco OK')
        
        import migrations
        print('✅ Migrações executadas com sucesso')
        
    except Exception as e:
        print(f'❌ Erro nas migrações: {e}')
        traceback.print_exc()
        sys.exit(1)
"

# Verificar rotas críticas
echo "🔍 Verificando rotas críticas..."
python -c "
from app import app
with app.app_context():
    print('✅ Flask app carregado')
    print(f'   - Blueprints: {len(app.blueprints)}')
    print(f'   - Rotas: {len(app.url_map.iter_rules())}')
"

echo "🎯 Sistema EasyPanel pronto! Iniciando aplicação..."
exec "$@"
