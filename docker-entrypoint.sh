#!/bin/bash
# DOCKER ENTRYPOINT - SIGE v8.0
# Script de inicialização para container de produção

set -e

echo "🚀 Iniciando SIGE v8.0 em container Docker..."

# Aguardar banco de dados estar disponível
echo "⏳ Aguardando banco de dados PostgreSQL..."
until pg_isready -h viajey_sige -p 5432 -U sige; do
    echo "   Banco ainda não disponível, aguardando..."
    sleep 2
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
    --worker-connections 1000 \
    --timeout 30 \
    --keepalive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    main:app