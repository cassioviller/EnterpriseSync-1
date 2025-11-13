#!/bin/bash
# SIGE v10.0 - Entrypoint SIMPLIFICADO para EasyPanel
# Foco: Funcionar de forma confiável sem complexidade

set -e

echo "🚀 SIGE v10.0 - Deploy Simplificado"
echo "===================================="
echo "📅 $(date)"

# Configurações básicas
export FLASK_ENV=production

# Aguardar banco de dados (tempo fixo)
echo "⏳ Aguardando banco de dados (20 segundos)..."
sleep 20

# Executar migrações automáticas
echo "🔄 Executando migrações..."
if python3 /app/pre_start.py; then
    echo "✅ Migrações concluídas"
else
    echo "⚠️ Migrações com warning - continuando..."
fi

# Iniciar aplicação
echo "🚀 Iniciando aplicação..."
exec "$@"
