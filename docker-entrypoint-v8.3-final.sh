#!/bin/bash
# DOCKER ENTRYPOINT PRODUÇÃO v9.0 - OTIMIZADO E LIMPO
set -e

echo "🚀 SIGE v9.0 - Sistema de Gestão Empresarial"

# Configuração do ambiente
export PYTHONPATH=/app
export FLASK_APP=main.py
export FLASK_ENV=production

# Configurar DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    if [ -n "$POSTGRES_URL" ]; then
        export DATABASE_URL="$POSTGRES_URL"
    else
        export DATABASE_URL="postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"
    fi
fi

# Aguardar PostgreSQL
echo "⏳ Conectando ao PostgreSQL..."
TIMEOUT=30
COUNTER=0

until psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout PostgreSQL"
        exit 1
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# Aplicar correções mínimas no banco
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 << 'EOSQL' >/dev/null 2>&1
DO $$
BEGIN
    -- Garantir campo admin_id na tabela servico_obra
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'servico_obra' AND column_name = 'admin_id'
    ) THEN
        ALTER TABLE servico_obra ADD COLUMN admin_id INTEGER DEFAULT 2;
    END IF;
    
    -- Atualizar registros sem admin_id
    UPDATE servico_obra SET admin_id = 2 WHERE admin_id IS NULL;
    
    -- Garantir funcionário para admin_id=2 em produção
    IF NOT EXISTS (SELECT 1 FROM funcionarios WHERE admin_id = 2 LIMIT 1) THEN
        INSERT INTO funcionarios (nome, admin_id, ativo, created_at) VALUES 
        ('Admin Sistema', 2, TRUE, NOW())
        ON CONFLICT DO NOTHING;
    END IF;
END
$$;
EOSQL

echo "✅ Banco corrigido"

# Validar aplicação
python3 -c "
import sys
sys.path.append('/app')
try:
    from app import app
    print('✅ Flask validado')
except Exception as e:
    print(f'❌ Erro: {e}')
    sys.exit(1)
" 2>/dev/null

echo "🚀 Iniciando servidor..."

# Executar comando principal
exec "$@"