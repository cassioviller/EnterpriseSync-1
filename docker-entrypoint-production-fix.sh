#!/bin/bash
# DOCKER ENTRYPOINT PRODUCTION FIX - SIGE v8.0 
# Script final simplificado para corrigir admin_id

set -e

echo "🚀 SIGE v8.0 - Iniciando (Production Fix - 02/09/2025)"
echo "📍 Modo: ${FLASK_ENV:-production}"

# Configuração do ambiente
export PYTHONPATH=/app
export FLASK_APP=main.py
export FLASK_ENV=production

# Verificar/detectar DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️ DATABASE_URL não definida - tentando detectar automaticamente..."
    
    # Tentar variáveis alternativas do EasyPanel
    if [ -n "$POSTGRES_URL" ]; then
        export DATABASE_URL="$POSTGRES_URL"
        echo "✅ DATABASE_URL detectada via POSTGRES_URL"
    elif [ -n "$DB_HOST" ] && [ -n "$DB_USER" ]; then
        export DATABASE_URL="postgres://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}?sslmode=disable"
        echo "✅ DATABASE_URL construída via DB_* variables"
    else
        # Fallback para configuração conhecida do projeto
        export DATABASE_URL="postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"
        echo "⚠️ Usando DATABASE_URL fallback do projeto"
    fi
fi

echo "📍 DATABASE_URL: $(echo $DATABASE_URL | sed 's/:\/\/[^:]*:[^@]*@/:\/\/****:****@/')"

# Aguardar PostgreSQL
echo "⏳ Verificando PostgreSQL..."
TIMEOUT=20
COUNTER=0

until psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout PostgreSQL (${TIMEOUT}s)"
        exit 1
    fi
    echo "⏳ Tentativa $COUNTER/$TIMEOUT - aguardando PostgreSQL..."
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# HOTFIX CRÍTICO - COMANDOS SQL DIRETOS
echo "🔧 HOTFIX: Aplicando correção admin_id na tabela servico..."

echo "1️⃣ Verificando se coluna admin_id existe..."
COLUMN_EXISTS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='servico' AND column_name='admin_id';" 2>/dev/null | xargs)

if [ "$COLUMN_EXISTS" = "0" ]; then
    echo "🚨 COLUNA admin_id NÃO EXISTE - APLICANDO CORREÇÃO..."
    
    echo "2️⃣ Adicionando coluna admin_id..."
    psql "$DATABASE_URL" -c "ALTER TABLE servico ADD COLUMN admin_id INTEGER;" || echo "⚠️ Erro ao adicionar coluna"
    
    echo "3️⃣ Verificando usuário admin..."
    USER_EXISTS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM usuario WHERE id=10;" 2>/dev/null | xargs)
    if [ "$USER_EXISTS" = "0" ]; then
        echo "🔧 Criando usuário admin_id=10..."
        psql "$DATABASE_URL" -c "INSERT INTO usuario (id, username, email, nome, password_hash, ativo, created_at) VALUES (10, 'admin_sistema', 'admin@sistema.local', 'Admin Sistema', 'pbkdf2:sha256:260000\$salt\$hash', TRUE, NOW());" || echo "⚠️ Erro ao criar usuário"
    fi
    
    echo "4️⃣ Populando serviços..."
    psql "$DATABASE_URL" -c "UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;" || echo "⚠️ Erro ao popular"
    
    echo "5️⃣ Definindo NOT NULL..."
    psql "$DATABASE_URL" -c "ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;" || echo "⚠️ Erro NOT NULL"
    
    echo "✅ HOTFIX EXECUTADO"
    
    # Verificar resultado
    FINAL_CHECK=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='servico' AND column_name='admin_id';" 2>/dev/null | xargs)
    if [ "$FINAL_CHECK" = "1" ]; then
        echo "✅ SUCESSO: Coluna admin_id criada!"
    else
        echo "❌ FALHA: Coluna ainda não existe"
    fi
else
    echo "✅ Coluna admin_id já existe"
fi

# Inicialização da aplicação
echo "🔧 Inicializando aplicação..."
python -c "
import sys
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

# Executar comando
exec "$@"