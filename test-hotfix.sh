#!/bin/bash
# Teste do HOTFIX admin_id para validar antes do deploy

echo "🧪 TESTANDO HOTFIX ADMIN_ID..."

# Simular DATABASE_URL de produção
export DATABASE_URL="postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"

echo "📍 DATABASE_URL: $DATABASE_URL"

# Testar conexão direta
echo "🔧 Testando conexão com psql..."
psql "$DATABASE_URL" -c "SELECT version();" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Conexão bem-sucedida!"
    
    # Testar comando de verificação
    echo "🔍 Testando verificação da coluna admin_id..."
    psql "$DATABASE_URL" -c "
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='servico' AND column_name='admin_id';
    " 2>&1
    
else
    echo "❌ Falha na conexão - verificar DATABASE_URL"
fi

echo "🎯 Teste concluído!"