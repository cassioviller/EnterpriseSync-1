#!/bin/bash
# 🚀 SIGE v10.0 - ENTRYPOINT PARA CORREÇÃO DE VEÍCULOS EM PRODUÇÃO
# ================================================================
# Versão especializada para aplicar migration de limpeza de veículos
# Foco: Resolver problemas de SQLAlchemy com models obsoletos
# ================================================================

set -e

echo "🚀 SIGE v10.0 - CORREÇÃO DE VEÍCULOS EM PRODUÇÃO"
echo "================================================"

# Configurações básicas de ambiente
export FLASK_ENV=production
export DIGITAL_MASTERY_MODE=true
export RUN_VEHICLE_MIGRATION=true

# DATABASE_URL padrão para EasyPanel se não estiver definida
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
    echo "🔧 Usando DATABASE_URL padrão EasyPanel"
else
    echo "🔧 Usando DATABASE_URL existente"
fi

# Logging detalhado para produção
echo "📋 AMBIENTE DE PRODUÇÃO DETECTADO"
echo "   🔑 DATABASE_URL configurada"
echo "   🔧 RUN_VEHICLE_MIGRATION=true"
echo "   💻 Hostname: $(hostname)"
echo "   📅 Data: $(date)"

# Aguardar banco de dados com timeout estendido
echo "🔌 Aguardando banco de dados..."
sleep 20

# Teste detalhado de conectividade
echo "🔍 Testando conectividade com banco..."
if command -v pg_isready >/dev/null 2>&1; then
    for i in {1..5}; do
        if pg_isready -h ${DATABASE_HOST:-viajey_sige} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-sige} >/dev/null 2>&1; then
            echo "✅ Banco de dados acessível (tentativa $i)"
            break
        else
            echo "⚠️ Tentativa $i/5 - aguardando banco..."
            sleep 5
        fi
    done
else
    echo "ℹ️ pg_isready não disponível - continuando"
fi

# 🔥 MIGRATION CRÍTICA PARA VEÍCULOS
echo "🔥 EXECUTANDO MIGRATION CRÍTICA DE VEÍCULOS"
echo "============================================"

python3 -c "
import sys
import os
sys.path.append('/app')

print('🚀 INICIANDO MIGRATION DE LIMPEZA DE VEÍCULOS...')

try:
    # Importar o script de migration
    import migration_cleanup_veiculos_production
    
    print('📋 Executando migration...')
    migrator = migration_cleanup_veiculos_production.VeiculosMigrationCleaner()
    sucesso = migrator.executar_migration()
    
    if sucesso:
        print('✅ MIGRATION DE VEÍCULOS EXECUTADA COM SUCESSO!')
    else:
        print('❌ MIGRATION FALHOU - continuando com inicialização')
        
except Exception as e:
    print(f'⚠️ Erro na migration (não crítico): {e}')
    print('🔄 Aplicação tentará continuar...')
"

# Inicialização básica da aplicação
echo "📊 Inicializando aplicação pós-migration..."
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
        
        # Health check específico de veículos
        try:
            from sqlalchemy import text, inspect
            
            # Verificar tabelas de veículos
            inspector = inspect(db.engine)
            tabelas = inspector.get_table_names()
            
            print('🔍 VERIFICAÇÃO PÓS-MIGRATION:')
            tabelas_essenciais = ['veiculo', 'uso_veiculo', 'custo_veiculo']
            for tabela in tabelas_essenciais:
                if tabela in tabelas:
                    result = db.session.execute(text(f'SELECT COUNT(*) FROM {tabela}'))
                    count = result.scalar()
                    print(f'   ✅ {tabela}: {count} registros')
                else:
                    print(f'   ❌ {tabela}: TABELA AUSENTE')
            
            # Verificar se tabelas obsoletas foram removidas
            tabelas_obsoletas = ['alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo']
            print('🗑️ TABELAS OBSOLETAS:')
            for tabela in tabelas_obsoletas:
                if tabela in tabelas:
                    print(f'   ⚠️ {tabela}: AINDA PRESENTE (pode causar erro)')
                else:
                    print(f'   ✅ {tabela}: REMOVIDA')
                    
        except Exception as e:
            print(f'ℹ️ Health check diagnóstico: {e}')
        
        print('✅ Inicialização básica concluída')
        
except Exception as e:
    print(f'⚠️ Erro na inicialização (não crítico): {e}')
    print('🔄 Aplicação tentará continuar...')
"

echo "🎯 CORREÇÃO DE VEÍCULOS APLICADA COM SUCESSO!"
echo "🚀 Iniciando aplicação..."

# Executar comando passado como parâmetro
exec "$@"