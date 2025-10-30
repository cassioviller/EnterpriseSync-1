#!/bin/bash
# ============================================================================
# SCRIPT DE EXECUÇÃO RÁPIDA - PRODUÇÃO EASYPANEL
# Execute este script dentro do container
# ============================================================================

set -e  # Parar se houver erro

echo "============================================================================"
echo "🚀 CORREÇÃO EMERGENCIAL - rdo_mao_obra.admin_id"
echo "============================================================================"
echo ""

# 1. Verificar DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERRO: DATABASE_URL não encontrada"
    exit 1
fi

echo "✅ DATABASE_URL encontrada"
echo ""

# 2. Verificar se admin_id existe
echo "📋 Verificando estado atual da tabela rdo_mao_obra..."
echo ""

COLUMN_EXISTS=$(psql $DATABASE_URL -t -c "
    SELECT COUNT(*) 
    FROM information_schema.columns 
    WHERE table_name = 'rdo_mao_obra' 
      AND column_name = 'admin_id'
")

if [ "$COLUMN_EXISTS" -gt 0 ]; then
    echo "✅ admin_id JÁ EXISTE em rdo_mao_obra"
    echo "   Problema pode ser outro. Execute:"
    echo "   python3 diagnostico_producao.py"
    exit 0
fi

echo "❌ admin_id NÃO EXISTE em rdo_mao_obra"
echo ""

# 3. Confirmar execução
echo "⚠️  Este script vai:"
echo "   1. Fazer backup do banco"
echo "   2. Adicionar coluna admin_id em rdo_mao_obra"
echo "   3. Preencher dados automaticamente"
echo "   4. Reiniciar aplicação"
echo ""

read -p "🔐 Digite 'SIM' para confirmar: " confirmacao

if [ "$confirmacao" != "SIM" ]; then
    echo "❌ Execução cancelada"
    exit 1
fi

echo ""
echo "============================================================================"

# 4. Fazer backup
echo "💾 Fazendo backup..."
BACKUP_FILE="/tmp/backup_rdo_mao_obra_$(date +%Y%m%d_%H%M%S).sql"
pg_dump $DATABASE_URL > $BACKUP_FILE

if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h $BACKUP_FILE | cut -f1)
    echo "✅ Backup criado: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "❌ ERRO ao criar backup"
    exit 1
fi

echo ""

# 5. Executar correção SQL
echo "🔧 Executando correção SQL..."
echo ""

psql $DATABASE_URL < fix_rdo_mao_obra_AGORA.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Correção SQL executada com sucesso"
else
    echo ""
    echo "❌ ERRO na execução SQL"
    echo "   Restaurar backup: psql $DATABASE_URL < $BACKUP_FILE"
    exit 1
fi

echo ""

# 6. Reiniciar aplicação
echo "🔄 Reiniciando aplicação..."

if command -v supervisorctl &> /dev/null; then
    supervisorctl restart all
    echo "✅ Aplicação reiniciada via supervisorctl"
else
    echo "⚠️  supervisorctl não encontrado"
    echo "   Reinicie manualmente via Easypanel UI"
fi

echo ""
echo "============================================================================"
echo "✅ CORREÇÃO CONCLUÍDA"
echo "============================================================================"
echo ""
echo "📋 Próximos passos:"
echo "   1. Aguarde 30 segundos"
echo "   2. Acesse: https://sige.cassiovillar.tech/funcionario/rdo/consolidado"
echo "   3. Verifique se RDOs mostram porcentagens e funcionários"
echo ""
echo "🔍 Se ainda houver erros:"
echo "   python3 diagnostico_producao.py"
echo ""
echo "💾 Backup salvo em: $BACKUP_FILE"
echo "============================================================================"
