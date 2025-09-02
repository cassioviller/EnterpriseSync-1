#!/bin/bash
set -e

echo "🚀 SIGE v8.0 - Inicialização de Produção"
echo "========================================"

# Aguardar PostgreSQL estar disponível
echo "⏳ Aguardando PostgreSQL..."
until pg_isready -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-postgres}"; do
  echo "PostgreSQL ainda não está pronto - aguardando..."
  sleep 2
done
echo "✅ PostgreSQL disponível!"

# Aplicar correções críticas de produção
echo "🔧 Aplicando correções de produção..."
python3 deploy_fix_producao.py

if [ $? -eq 0 ]; then
    echo "✅ Correções aplicadas com sucesso!"
else
    echo "❌ Falha nas correções de produção!"
    exit 1
fi

# Executar migrações automáticas do sistema
echo "🔄 Executando migrações do sistema..."
python3 -c "
import sys
sys.path.append('.')
from app import app, db
with app.app_context():
    db.create_all()
    print('✅ Migrações do sistema concluídas!')
"

# Verificar integridade do sistema
echo "🔍 Verificando integridade do sistema..."
python3 -c "
import sys
sys.path.append('.')
from app import app, db
from models import Obra, Usuario
with app.app_context():
    try:
        # Testar queries críticas
        obras_count = Obra.query.count()
        users_count = Usuario.query.count()
        print(f'✅ Sistema íntegro: {obras_count} obras, {users_count} usuários')
    except Exception as e:
        print(f'❌ Erro de integridade: {e}')
        exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Sistema íntegro e pronto!"
else
    echo "❌ Falha na verificação de integridade!"
    exit 1
fi

echo "========================================"
echo "🎉 SIGE v8.0 - Pronto para Produção"
echo "========================================"

# Iniciar aplicação
echo "🚀 Iniciando aplicação..."
exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WORKERS:-2} --timeout ${TIMEOUT:-120} --reuse-port main:app