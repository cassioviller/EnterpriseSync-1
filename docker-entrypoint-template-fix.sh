#!/bin/bash
set -e

echo "🚀 SIGE v8.0 - Correção de Template RDO"

# Aguardar PostgreSQL
echo "⏳ Aguardando PostgreSQL..."
until pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres} 2>/dev/null; do
    sleep 2
done
echo "✅ PostgreSQL conectado!"

# Executar correção de templates
echo "🔧 Aplicando correção de templates..."
python corrigir_template_rdo_producao.py

# Verificar se template novo.html existe
if [ ! -f "templates/rdo/novo.html" ]; then
    echo "❌ ERRO: Template templates/rdo/novo.html não encontrado!"
    exit 1
fi

echo "✅ Template novo.html confirmado"

# Executar migrações
echo "🔄 Executando migrações..."
python -c "
from app import app, db
with app.app_context():
    try:
        import migrations
        print('✅ Migrações concluídas')
    except Exception as e:
        print(f'⚠️ Aviso: {e}')
"

# Verificar saúde da aplicação antes de iniciar
echo "🔍 Verificação final..."
python -c "
from app import app
with app.app_context():
    print('✅ Aplicação inicializada corretamente')
"

echo "🎯 Iniciando servidor..."
exec "$@"
