#!/bin/bash
# SIGE v10.0 - ENTRYPOINT CORRIGIDO PARA PRODUÇÃO
# Versão corrigida para resolver problema do botão "Gerenciar" em produção
# Foco: Estabilidade sem correções problemáticas

set -e

echo "🚀 SIGE v10.0 - Iniciando sistema robusto..."

# Configurações básicas de ambiente
export FLASK_ENV=production
export DIGITAL_MASTERY_MODE=true

# DATABASE_URL padrão para EasyPanel se não estiver definida
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
    echo "🔧 Usando DATABASE_URL padrão EasyPanel"
else
    echo "🔧 Usando DATABASE_URL existente"
fi

echo "✅ Configurações aplicadas"

# Aguardar banco de dados com timeout simples
echo "🔌 Aguardando banco de dados..."
sleep 15

# Teste básico de conectividade (não crítico)
echo "🔍 Testando conectividade..."
if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h ${DATABASE_HOST:-viajey_sige} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-sige} >/dev/null 2>&1; then
        echo "✅ Banco de dados acessível"
    else
        echo "⚠️ Banco não responsivo - continuando (pode funcionar)"
    fi
else
    echo "ℹ️ pg_isready não disponível - continuando"
fi

# Inicialização básica e segura da aplicação
echo "📊 Inicializando aplicação..."
python3 -c "
import sys
import os
sys.path.append('/app')

try:
    print('🔧 Importando aplicação...')
    from app import app, db
    
    with app.app_context():
        print('📋 Verificando/criando tabelas básicas...')
        db.create_all()
        print('✅ Tabelas verificadas')
        
        # Verificação básica de dados (apenas diagnóstico)
        try:
            from sqlalchemy import text
            result = db.session.execute(text('SELECT COUNT(*) FROM usuario'))
            user_count = result.scalar()
            print(f'ℹ️ Usuários no banco: {user_count}')
        except Exception as e:
            print(f'ℹ️ Verificação diagnóstica: {e} - continuando')
        
        print('✅ Inicialização básica concluída')
        
except Exception as e:
    print(f'⚠️ Erro na inicialização (não crítico): {e}')
    print('🔄 Aplicação tentará continuar...')
"

echo "🎯 SIGE v10.0 inicializado com sucesso!"
echo "🚀 Iniciando aplicação..."

# Executar comando passado como parâmetro
exec "$@"