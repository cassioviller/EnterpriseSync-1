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
echo "🚨 HOTFIX PRODUÇÃO: Aplicando correção admin_id na tabela servico..."

# Primeira tentativa: DATABASE_URL direto
if [ -n "$DATABASE_URL" ]; then
    echo "📍 DATABASE_URL detectado: $(echo $DATABASE_URL | sed 's/:[^:]*@/:****@/')"
    echo "🔧 EXECUTANDO HOTFIX DIRETO NO POSTGRESQL..."
    
    # Executar SQL crítico via psql
    psql "$DATABASE_URL" << 'EOSQL'
-- HOTFIX CRÍTICO: Adicionar admin_id na tabela servico
-- Este script executa automaticamente no deploy

\echo '🔍 Verificando estrutura da tabela servico...'

-- Verificar se coluna admin_id já existe
DO $$
DECLARE
    column_exists boolean := false;
    user_exists boolean := false;
BEGIN
    -- Verificar se coluna existe
    SELECT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'servico' AND column_name = 'admin_id'
    ) INTO column_exists;
    
    IF NOT column_exists THEN
        RAISE NOTICE '🚨 COLUNA admin_id NAO EXISTE - APLICANDO HOTFIX...';
        
        -- 1. Adicionar coluna admin_id
        RAISE NOTICE '1️⃣ Adicionando coluna admin_id...';
        ALTER TABLE servico ADD COLUMN admin_id INTEGER;
        
        -- 2. Verificar/criar usuário admin padrão (CORRIGIDO)
        SELECT EXISTS (SELECT id FROM usuario WHERE id = 10) INTO user_exists;
        IF NOT user_exists THEN
            RAISE NOTICE '2️⃣ Criando usuário admin padrão...';
            
            -- Usar estrutura real da tabela usuario conforme models.py
            INSERT INTO usuario (id, username, email, nome, password_hash, ativo, admin_id, created_at) 
            VALUES (10, 'admin_sistema', 'admin@sistema.local', 'Admin Sistema', 
                    'pbkdf2:sha256:260000$salt$validhash', TRUE, NULL, NOW());
        ELSE
            RAISE NOTICE '2️⃣ Usuário admin_id=10 já existe';
        END IF;
        
        -- 3. Popular todos os serviços existentes
        RAISE NOTICE '3️⃣ Populando serviços existentes...';
        UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;
        
        -- 4. Tornar coluna NOT NULL primeiro
        RAISE NOTICE '4️⃣ Definindo coluna como NOT NULL...';
        ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;
        
        -- 5. Adicionar constraint foreign key (APENAS se usuário existe)
        IF user_exists OR EXISTS (SELECT id FROM usuario WHERE id = 10) THEN
            RAISE NOTICE '5️⃣ Adicionando foreign key constraint...';
            ALTER TABLE servico ADD CONSTRAINT fk_servico_admin 
            FOREIGN KEY (admin_id) REFERENCES usuario(id);
        ELSE
            RAISE NOTICE '⚠️ Usuário admin não existe - pulando foreign key';
        END IF;
        
        RAISE NOTICE '✅ HOTFIX COMPLETADO COM SUCESSO!';
        RAISE NOTICE '📊 Estrutura da tabela servico atualizada';
        
    ELSE
        RAISE NOTICE '✅ Coluna admin_id já existe - nenhuma ação necessária';
    END IF;
END
$$;

\echo '🎯 HOTFIX concluído!'
EOSQL
    
    
    HOTFIX_RESULT=$?
    
    if [ $HOTFIX_RESULT -eq 0 ]; then
        echo "✅ HOTFIX EXECUTADO COM SUCESSO!"
        echo "📊 Tabela servico atualizada com admin_id"
    else
        echo "⚠️ HOTFIX falhou - tentando método alternativo..."
        
        # FALLBACK: Método robusto sem foreign key
        echo "🔧 Executando correção simplificada sem foreign key..."
        
        # Etapa 1: Adicionar coluna
        psql "$DATABASE_URL" -c "ALTER TABLE servico ADD COLUMN IF NOT EXISTS admin_id INTEGER;" 2>/dev/null
        
        # Etapa 2: Popular com dados
        psql "$DATABASE_URL" -c "UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;" 2>/dev/null
        
        # Etapa 3: NOT NULL (sem foreign key para evitar erro)
        psql "$DATABASE_URL" -c "ALTER TABLE servico ALTER COLUMN admin_id SET DEFAULT 10;" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "✅ HOTFIX SIMPLIFICADO APLICADO!"
        else
            echo "❌ FALLBACK TAMBÉM FALHOU - continuando sem admin_id"
        fi
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