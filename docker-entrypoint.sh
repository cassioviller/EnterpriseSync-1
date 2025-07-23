#!/bin/bash
# DOCKER ENTRYPOINT - SIGE v8.0
# Script de inicialização para container de produção

set -e

echo "🚀 Iniciando SIGE v8.0 em container Docker..."

# Aguardar banco de dados estar disponível
echo "⏳ Aguardando banco de dados PostgreSQL..."

# Extrair host e porta da DATABASE_URL
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')

# Usar valores padrão se não conseguir extrair
DB_HOST=${DB_HOST:-viajey_sige}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-sige}

echo "   Conectando em: $DB_HOST:$DB_PORT como $DB_USER"

until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
    echo "   Banco ainda não disponível, aguardando..."
    sleep 3
done
echo "✅ Banco de dados conectado!"

# Aplicar migrações e criar tabelas
echo "🗄️ Preparando banco de dados..."
cd /app
python -c "
from app import app, db
with app.app_context():
    try:
        import models
        db.create_all()
        print('✅ Tabelas criadas/verificadas com sucesso')
    except Exception as e:
        print(f'❌ Erro ao criar tabelas: {e}')
        exit(1)
"

# Verificar saúde da aplicação
echo "🔍 Verificando aplicação..."
python -c "
from app import app
try:
    with app.app_context():
        print('✅ Aplicação carregada com sucesso')
except Exception as e:
    print(f'❌ Erro na aplicação: {e}')
    exit(1)
"

# Iniciar aplicação com Gunicorn
echo "🌐 Iniciando servidor Gunicorn na porta ${PORT}..."
exec gunicorn \
    --bind 0.0.0.0:${PORT} \
    --workers 4 \
    --worker-class sync \
    --timeout 30 \
    --keepalive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    main:app