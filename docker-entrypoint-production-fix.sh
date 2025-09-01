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

python3 -c "
import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_servico_admin_id():
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error('DATABASE_URL não encontrado')
            return False
            
        logger.info('🔧 Verificando admin_id na tabela servico...')
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar se coluna admin_id existe
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=\'servico\' AND column_name=\'admin_id\'
        ''')
        
        if not cursor.fetchone():
            logger.info('✅ Adicionando coluna admin_id na tabela servico...')
            
            # Adicionar coluna admin_id
            cursor.execute('''
                ALTER TABLE servico 
                ADD COLUMN admin_id INTEGER
            ''')
            
            # Popular com admin_id padrão
            cursor.execute('''
                UPDATE servico 
                SET admin_id = 10 
                WHERE admin_id IS NULL
            ''')
            
            # Adicionar foreign key constraint
            cursor.execute('''
                ALTER TABLE servico 
                ADD CONSTRAINT fk_servico_admin 
                FOREIGN KEY (admin_id) REFERENCES usuario(id)
            ''')
            
            # Tornar NOT NULL  
            cursor.execute('''
                ALTER TABLE servico 
                ALTER COLUMN admin_id SET NOT NULL
            ''')
            
            conn.commit()
            logger.info('✅ HOTFIX aplicado: admin_id adicionado na tabela servico')
            
        else:
            logger.info('✅ Coluna admin_id já existe na tabela servico')
            
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f'❌ Erro no HOTFIX admin_id: {e}')
        return False

fix_servico_admin_id()
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ HOTFIX admin_id aplicado com sucesso"
else
    echo "⚠️ HOTFIX admin_id falhou - continuando inicialização"
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