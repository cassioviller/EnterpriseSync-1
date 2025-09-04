#!/bin/bash
# Script de entrada unificado para SIGE v8.2
# Sistema "Serviços da Obra" baseado em RDO + Subatividades

set -e

echo "🚀 Iniciando SIGE v8.2 (Serviços da Obra Corrigido)"

# Detectar ambiente
if [[ "${FLASK_ENV:-production}" == "development" ]]; then
    echo "🔧 Modo: DESENVOLVIMENTO"
    ENABLE_DEBUG=true
else
    echo "🏭 Modo: PRODUÇÃO"
    ENABLE_DEBUG=false
fi

# Verificar e configurar DATABASE_URL
if [[ -z "${DATABASE_URL}" ]]; then
    echo "⚠️  DATABASE_URL não definida, usando padrão EasyPanel"
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige"
fi

# Adicionar sslmode=disable se não estiver presente (para EasyPanel)
if [[ "${DATABASE_URL}" != *"sslmode="* ]]; then
    if [[ "${DATABASE_URL}" == *"?"* ]]; then
        export DATABASE_URL="${DATABASE_URL}&sslmode=disable"
    else
        export DATABASE_URL="${DATABASE_URL}?sslmode=disable"
    fi
    echo "🔒 SSL desabilitado para compatibilidade EasyPanel"
fi

# Aguardar conexão com PostgreSQL
echo "⏳ Verificando conexão com PostgreSQL..."

# Extrair componentes da DATABASE_URL de forma mais robusta
if [[ $DATABASE_URL =~ postgres(ql)?://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
    DB_USER="${BASH_REMATCH[2]}"
    DB_PASS="${BASH_REMATCH[3]}" 
    DB_HOST="${BASH_REMATCH[4]}"
    DB_PORT="${BASH_REMATCH[5]}"
    DB_NAME="${BASH_REMATCH[6]}"
else
    # Valores padrão para EasyPanel
    DB_HOST="viajey_sige"
    DB_PORT="5432"
    DB_USER="sige"
    DB_NAME="sige"
fi

echo "🔍 Conectando em: ${DB_HOST}:${DB_PORT} (usuário: ${DB_USER})"

# Aguardar banco com timeout
TIMEOUT=60
COUNTER=0

until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout: PostgreSQL não respondeu em ${TIMEOUT}s"
        echo "🔍 Debug: DATABASE_URL=${DATABASE_URL}"
        echo "🔍 Debug: Host=${DB_HOST}, Port=${DB_PORT}, User=${DB_USER}"
        exit 1
    fi
    
    echo "⏳ PostgreSQL não disponível, tentativa $((COUNTER + 1))/${TIMEOUT}..."
    sleep 2
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# Executar migrações automáticas
echo "🔄 Executando migrações automáticas..."
python -c "
import sys
import traceback
from app import app, db

with app.app_context():
    try:
        print('🔄 Testando conexão com banco...')
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        print('✅ Conexão com banco OK')
        
        # Importar e executar migrações
        import migrations
        print('✅ Migrações executadas com sucesso')
        
    except Exception as e:
        print(f'❌ Erro nas migrações: {e}')
        print('📋 Traceback:')
        traceback.print_exc()
        
        # Em produção, falhar se migrações não funcionarem
        if '${FLASK_ENV}' == 'production':
            sys.exit(1)
        else:
            print('⚠️  Continuando em modo desenvolvimento...')
"

if [[ $? -ne 0 && "${FLASK_ENV}" == "production" ]]; then
    echo "❌ Falha crítica nas migrações em produção"
    exit 1
fi

# Verificar integridade dos templates críticos
echo "🔍 Verificando templates críticos..."
TEMPLATES_ESSENCIAIS=(
    "templates/rdo/novo.html"
    "templates/funcionarios.html" 
    "templates/dashboard.html"
    "templates/base_completo.html"
)

for template in "${TEMPLATES_ESSENCIAIS[@]}"; do
    if [[ ! -f "/app/${template}" ]]; then
        echo "❌ Template crítico não encontrado: ${template}"
        exit 1
    fi
done

echo "✅ Todos os templates críticos encontrados"

# Verificar estrutura de rotas essenciais
echo "🔍 Verificando estrutura de rotas..."
python -c "
from app import app
from flask import url_for

with app.app_context():
    try:
        # Testar rotas críticas (incluindo novas APIs v8.2)
        rotas_criticas = [
            'main.dashboard',
            'main.funcionarios', 
            'main.funcionario_rdo_consolidado',
            'main.funcionario_rdo_novo',
            'main.health_check',
            'main.adicionar_servico_rdo_obra',
            'main.api_servicos_disponiveis_obra'
        ]
        
        for rota in rotas_criticas:
            try:
                url_for(rota)
                print(f'✅ Rota OK: {rota}')
            except Exception as e:
                print(f'❌ Rota falhou: {rota} - {e}')
                
        print('✅ Verificação de rotas concluída')
        
    except Exception as e:
        print(f'❌ Erro na verificação de rotas: {e}')
"

# Mostrar estatísticas finais
echo "📊 Estatísticas do sistema:"
echo "   - Python: $(python --version)"
echo "   - Diretório: $(pwd)"
echo "   - Usuário: $(whoami)"
echo "   - Templates: $(find /app/templates -name '*.html' | wc -l) arquivos"
echo "   - Arquivos estáticos: $(find /app/static -type f | wc -l) arquivos"

if [[ "${ENABLE_DEBUG}" == "true" ]]; then
    echo "🔧 Informações de debug ativadas"
    echo "   - Blueprints registrados:"
    python -c "
from app import app
for blueprint in app.blueprints:
    print(f'     - {blueprint}')
"
fi

echo "🎯 Sistema pronto! Iniciando aplicação..."
exec "$@"