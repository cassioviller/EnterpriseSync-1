#!/bin/bash
# DEPLOY PRODUÇÃO - SIGE v8.0

echo "🚀 Iniciando deploy SIGE v8.0..."

# Backup do banco
echo "📦 Fazendo backup..."
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Aplicar otimizações
echo "⚡ Aplicando otimizações..."
psql $DATABASE_URL < otimizacoes_producao.sql

# Reiniciar aplicação
echo "🔄 Reiniciando aplicação..."
# Comando específico do ambiente (PM2, systemd, etc.)

# Verificar saúde
echo "🏥 Verificando saúde..."
sleep 5
curl -f http://localhost/api/monitoring/health || exit 1

echo "✅ Deploy concluído!"
