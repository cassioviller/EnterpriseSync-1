#!/bin/bash
set -e

echo "🚀 Iniciando SIGE v8.0 em produção..."

# Aguardar banco de dados
echo "⏳ Aguardando conexão com PostgreSQL..."
until pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres}; do
    echo "⏳ PostgreSQL não disponível, aguardando..."
    sleep 2
done

echo "✅ PostgreSQL conectado!"

# Executar migrações automáticas
echo "🔄 Executando migrações automáticas..."
python -c "
from app import app, db
with app.app_context():
    try:
        # Importar migrations para executar automaticamente
        import migrations
        print('✅ Migrações executadas com sucesso')
    except Exception as e:
        print(f'⚠️ Aviso nas migrações: {e}')
"

echo "🎯 Iniciando aplicação..."
exec "$@"
