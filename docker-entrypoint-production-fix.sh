#!/bin/bash
# DOCKER ENTRYPOINT PRODUCTION FIX - SIGE v8.0 FINAL
set -e

echo "🚀 SIGE v8.0.1 - Iniciando (Full Sync Dev-Prod - 03/09/2025)"

# Configuração do ambiente
export PYTHONPATH=/app
export FLASK_APP=main.py
export FLASK_ENV=production

# Detectar DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    if [ -n "$POSTGRES_URL" ]; then
        export DATABASE_URL="$POSTGRES_URL"
    else
        export DATABASE_URL="postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"
    fi
fi

echo "📍 DATABASE_URL: $(echo $DATABASE_URL | sed 's/:\/\/[^:]*:[^@]*@/:\/\/****:****@/')"

# Aguardar PostgreSQL
echo "⏳ Verificando PostgreSQL..."
TIMEOUT=30
COUNTER=0

until psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout PostgreSQL (${TIMEOUT}s)"
        exit 1
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# CORREÇÕES ATUALIZADAS - DESENVOLVIMENTO SINCRONIZADO
echo "🔧 CORREÇÕES ATUALIZADAS: Sincronizando dev-prod e aplicando fixes RDO..."

# Executar correção em bloco único
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 << 'EOSQL'
DO $$
DECLARE
    column_exists boolean := false;
    user_exists boolean := false;
    servico_count integer := 0;
BEGIN
    -- CORREÇÃO CRÍTICA: Adicionar coluna obra.cliente se não existir
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'cliente'
    ) THEN
        ALTER TABLE obra ADD COLUMN cliente VARCHAR(200);
        RAISE NOTICE '✅ Coluna obra.cliente adicionada';
    ELSE
        RAISE NOTICE '✅ Coluna obra.cliente já existe';
    END IF;

    -- 1. Verificar se coluna admin_id existe na tabela servico
    SELECT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'servico' AND column_name = 'admin_id'
    ) INTO column_exists;
    
    -- 2. Verificar se usuário admin existe
    SELECT EXISTS (
        SELECT id FROM usuario WHERE id = 10
    ) INTO user_exists;
    
    -- 3. Contar serviços existentes
    SELECT COUNT(*) FROM servico INTO servico_count;
    
    RAISE NOTICE '🔍 STATUS INICIAL:';
    RAISE NOTICE '   - Coluna admin_id existe: %', column_exists;
    RAISE NOTICE '   - Usuário admin existe: %', user_exists;
    RAISE NOTICE '   - Total de serviços: %', servico_count;
    
    -- 4. Criar usuário admin se não existir
    IF NOT user_exists THEN
        RAISE NOTICE '1️⃣ Criando usuário admin (ID: 10)...';
        INSERT INTO usuario (
            id, 
            username, 
            email, 
            password_hash, 
            nome, 
            ativo, 
            tipo_usuario, 
            admin_id, 
            created_at
        ) VALUES (
            10,
            'admin_sistema',
            'admin@sistema.local',
            'pbkdf2:sha256:260000$salt$hash_placeholder',
            'Admin Sistema',
            TRUE,
            'admin',
            10,
            NOW()
        );
        RAISE NOTICE '✅ Usuário admin criado com sucesso';
    ELSE
        RAISE NOTICE '✅ Usuário admin já existe';
    END IF;
    
    -- 5. Adicionar coluna admin_id se não existir
    IF NOT column_exists THEN
        RAISE NOTICE '2️⃣ Adicionando coluna admin_id na tabela servico...';
        ALTER TABLE servico ADD COLUMN admin_id INTEGER;
        
        RAISE NOTICE '3️⃣ Populando % serviços com admin_id = 10...', servico_count;
        UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;
        
        RAISE NOTICE '4️⃣ Definindo coluna como NOT NULL...';
        ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;
        
        RAISE NOTICE '5️⃣ Adicionando foreign key constraint...';
        ALTER TABLE servico ADD CONSTRAINT fk_servico_admin 
        FOREIGN KEY (admin_id) REFERENCES usuario(id);
        
        RAISE NOTICE '✅ HOTFIX COMPLETADO COM SUCESSO!';
        RAISE NOTICE '📊 Estrutura da tabela servico atualizada';
    ELSE
        RAISE NOTICE '✅ Coluna admin_id já existe - sistema OK';
    END IF;
    
    -- 6. Verificação final
    SELECT COUNT(*) FROM servico WHERE admin_id = 10 INTO servico_count;
    RAISE NOTICE '🎯 VERIFICAÇÃO FINAL: % serviços com admin_id = 10', servico_count;
    
END
$$;
EOSQL

HOTFIX_RESULT=$?

if [ $HOTFIX_RESULT -eq 0 ]; then
    echo "✅ HOTFIX DEFINITIVO EXECUTADO COM SUCESSO!"
    
    # Verificação adicional
    echo "🔍 Verificação pós-hotfix..."
    FINAL_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='servico' AND column_name='admin_id';" 2>/dev/null | xargs)
    
    if [ "$FINAL_COUNT" = "1" ]; then
        echo "✅ SUCESSO CONFIRMADO: Coluna admin_id existe!"
        
        # Testar query que estava falhando
        echo "🧪 Testando query original..."
        psql "$DATABASE_URL" -c "SELECT COUNT(*) as total FROM servico;" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "✅ QUERY ORIGINAL FUNCIONANDO!"
        else
            echo "⚠️ Query ainda com problemas"
        fi
    else
        echo "❌ FALHA: Coluna ainda não existe"
        exit 1
    fi
else
    echo "❌ HOTFIX FALHOU - Código de saída: $HOTFIX_RESULT"
    exit 1
fi

# Criar diretório de logs para produção
echo "📁 Criando sistema de logs para produção..."
mkdir -p /app/logs
mkdir -p /app/templates/debug
mkdir -p /app/templates/errors
touch /app/logs/production_errors.log
touch /app/logs/production_debug.log
chmod 755 /app/logs
chmod 644 /app/logs/*.log

# Inicialização da aplicação
echo "🔧 Inicializando aplicação SIGE v8.0.1 com sistema de logs..."
python -c "
import sys
sys.path.append('/app')
try:
    from app import app
    print('✅ App Flask carregado com sucesso')
except Exception as e:
    print(f'❌ Erro ao carregar app: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
" 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo "❌ Falha na inicialização da aplicação"
    exit 1
fi

echo "🎯 Sistema SIGE v8.0.1 pronto para uso - SINCRONIZADO!"
echo "📍 URLs de teste: /servicos | /rdo | /dashboard | /funcionarios"
echo "🔧 Correções incluídas: RDO continuação, mapping IDs, salvamento de subatividades"

# Executar comando principal
exec "$@"