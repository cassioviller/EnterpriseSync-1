#!/bin/bash
# DOCKER ENTRYPOINT PRODUCTION FIX - SIGE v8.0
# Script otimizado para resolver loops infinitos em produção

set -e

echo "🚀 SIGE v8.0 - Iniciando (Production Fix v2.0 - 01/09/2025)"
echo "📍 Modo: ${FLASK_ENV:-production}"

# Configuração silenciosa do ambiente
export PYTHONPATH=/app
export FLASK_APP=main.py
export FLASK_ENV=production

# Aguardar PostgreSQL com timeout reduzido
echo "⏳ Verificando PostgreSQL..."

# Configuração padrão EasyPanel
DB_HOST="${DATABASE_HOST:-viajey_sige}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_USER="${DATABASE_USER:-sige}"

TIMEOUT=20
COUNTER=0

until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout PostgreSQL (${TIMEOUT}s)"
        exit 1
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# HOTFIX CRÍTICO: Corrigir admin_id na tabela servico ANTES da aplicação iniciar
echo "🔧 HOTFIX: Aplicando correção admin_id na tabela servico..."

# Executar SQL direto sem Python para máxima confiabilidade
if [ -n "$DATABASE_URL" ]; then
    echo "📍 DATABASE_URL encontrado, executando HOTFIX..."
    
    # Extrair componentes da URL para psql
    DB_USER=$(echo $DATABASE_URL | sed 's/.*:\/\/\([^:]*\):.*/\1/')
    DB_PASS=$(echo $DATABASE_URL | sed 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/')
    DB_HOST=$(echo $DATABASE_URL | sed 's/.*@\([^:]*\):.*/\1/')
    DB_PORT=$(echo $DATABASE_URL | sed 's/.*:\([0-9]*\)\/.*/\1/')
    DB_NAME=$(echo $DATABASE_URL | sed 's/.*\/\([^?]*\).*/\1/')
    
    export PGPASSWORD="$DB_PASS"
    
    echo "🔧 Conectando em $DB_HOST:$DB_PORT/$DB_NAME como $DB_USER..."
    
    # Executar comandos SQL via psql
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
    DO \$\$
    BEGIN
        -- Verificar se coluna admin_id existe
        IF NOT EXISTS (
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='servico' AND column_name='admin_id'
        ) THEN
            RAISE NOTICE '✅ Adicionando coluna admin_id na tabela servico...';
            
            -- Adicionar coluna admin_id
            ALTER TABLE servico ADD COLUMN admin_id INTEGER;
            
            -- Popular com admin_id padrão para todos os registros
            UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;
            
            -- Verificar se usuário admin_id=10 existe, se não criar
            IF NOT EXISTS (SELECT id FROM usuario WHERE id = 10) THEN
                INSERT INTO usuario (id, username, email, nome, password_hash, tipo_usuario, ativo, admin_id)
                VALUES (10, 'admin_producao', 'admin@producao.com', 'Admin Produção', 
                        'scrypt:32768:8:1\$password_hash', 'admin', TRUE, NULL)
                ON CONFLICT (id) DO NOTHING;
            END IF;
            
            -- Adicionar foreign key constraint
            ALTER TABLE servico ADD CONSTRAINT fk_servico_admin 
            FOREIGN KEY (admin_id) REFERENCES usuario(id);
            
            -- Tornar NOT NULL
            ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;
            
            RAISE NOTICE '✅ HOTFIX aplicado: admin_id adicionado na tabela servico';
        ELSE
            RAISE NOTICE '✅ Coluna admin_id já existe na tabela servico';
        END IF;
    END
    \$\$;
    " 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ HOTFIX admin_id aplicado com sucesso via psql"
    else
        echo "⚠️ HOTFIX admin_id falhou via psql - continuando inicialização"
    fi
else
    echo "❌ DATABASE_URL não encontrado - pulando HOTFIX"
fi

# Inicialização mínima da aplicação (sem loops)
echo "🔧 Inicializando aplicação..."
python -c "
import os
import sys
import warnings

# Suprimir warnings para evitar logs excessivos
warnings.filterwarnings('ignore')
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

sys.path.append('/app')

try:
    from app import app
    print('✅ App carregado')
except Exception as e:
    print(f'❌ Erro: {e}')
    sys.exit(1)
" 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo "❌ Falha na inicialização"
    exit 1
fi

echo "🎯 Aplicação pronta!"

# Executar comando com configurações otimizadas
exec "$@"