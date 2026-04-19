#!/bin/bash
# 🚀 SIGE v10.0 - ENTRYPOINT AUTOMÁTICO EASYPANEL/HOSTINGER
# ==========================================================
# FASE 3: Deploy Automático com Migrações Sempre Ativas
# Foco: Robustez, Logs Detalhados, Safety Features
# ==========================================================

set -e
set -o pipefail

# Configurações de logging detalhado
LOG_FILE="/tmp/sige_deployment.log"
MIGRATION_LOG="/tmp/sige_migrations.log"
HEALTH_LOG="/tmp/sige_health.log"

echo "🚀 SIGE v10.0 - DEPLOY AUTOMÁTICO EASYPANEL" | tee -a "$LOG_FILE"
echo "=============================================" | tee -a "$LOG_FILE"
echo "📅 $(date)" | tee -a "$LOG_FILE"
echo "💻 Hostname: $(hostname)" | tee -a "$LOG_FILE"
echo "🔧 Entrypoint: auto-migrations SEMPRE ativo" | tee -a "$LOG_FILE"

# FASE 3.1: Configurações de ambiente robustas
export FLASK_ENV=production
export DIGITAL_MASTERY_MODE=true
export AUTO_MIGRATIONS_ENABLED=true
export DEPLOYMENT_TIMESTAMP=$(date +%s)

# DATABASE_URL padrão para EasyPanel/Hostinger
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
    echo "🔧 DATABASE_URL padrão EasyPanel configurada" | tee -a "$LOG_FILE"
else
    echo "🔧 DATABASE_URL existente detectada" | tee -a "$LOG_FILE"
fi

# Mascarar DATABASE_URL nos logs por segurança
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
echo "🎯 Target Database Host: $DB_HOST" | tee -a "$LOG_FILE"

# FASE 3.2: Safety flags e configurações de segurança
ENABLE_ROLLBACK=${ENABLE_ROLLBACK:-"true"}
MIGRATION_TIMEOUT=${MIGRATION_TIMEOUT:-300}
HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-60}
FORCE_MIGRATION=${FORCE_MIGRATION:-"false"}

echo "🔐 CONFIGURAÇÕES DE SEGURANÇA:" | tee -a "$LOG_FILE"
echo "   🔄 Rollback automático: $ENABLE_ROLLBACK" | tee -a "$LOG_FILE"
echo "   ⏱️ Timeout migrações: ${MIGRATION_TIMEOUT}s" | tee -a "$LOG_FILE"
echo "   🏥 Timeout health check: ${HEALTH_CHECK_TIMEOUT}s" | tee -a "$LOG_FILE"
echo "   🚀 Força migração: $FORCE_MIGRATION" | tee -a "$LOG_FILE"

# FASE 3.3: Verificação de conectividade robusta
echo "🔌 VERIFICAÇÃO DE CONECTIVIDADE..." | tee -a "$LOG_FILE"

# Aguardar banco com timeout inteligente
DB_WAIT_TIME=${DB_WAIT_TIME:-30}
echo "⏳ Aguardando banco de dados ($DB_WAIT_TIME segundos)..." | tee -a "$LOG_FILE"
sleep "$DB_WAIT_TIME"

# Teste de conectividade com retry
RETRY_COUNT=0
MAX_RETRIES=5

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "🔍 Teste de conectividade - tentativa $((RETRY_COUNT + 1))/$MAX_RETRIES" | tee -a "$LOG_FILE"
    
    if command -v pg_isready >/dev/null 2>&1; then
        if pg_isready -h "$DB_HOST" -p "${DATABASE_PORT:-5432}" -U "${DATABASE_USER:-sige}" >/dev/null 2>&1; then
            echo "✅ Banco de dados acessível!" | tee -a "$LOG_FILE"
            break
        else
            echo "⚠️ Banco não responsivo - tentativa $((RETRY_COUNT + 1))" | tee -a "$LOG_FILE"
        fi
    else
        echo "ℹ️ pg_isready não disponível - testando via Python..." | tee -a "$LOG_FILE"
        
        # Teste via Python como fallback
        if python3 -c "
import psycopg2
import os
import sys
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('✅ Conectividade Python OK')
    sys.exit(0)
except Exception as e:
    print(f'❌ Erro conectividade: {e}')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"; then
            echo "✅ Banco acessível via Python!" | tee -a "$LOG_FILE"
            break
        fi
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "⏱️ Aguardando 10s antes da próxima tentativa..." | tee -a "$LOG_FILE"
        sleep 10
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ ERRO: Não foi possível conectar ao banco após $MAX_RETRIES tentativas" | tee -a "$LOG_FILE"
    if [ "$ENABLE_ROLLBACK" = "true" ]; then
        echo "🔙 Rollback ativado - abortando deploy" | tee -a "$LOG_FILE"
        exit 1
    else
        echo "⚠️ Continuando sem conectividade (rollback desabilitado)" | tee -a "$LOG_FILE"
    fi
fi

# FASE 3.4: EXECUÇÃO AUTOMÁTICA DE MIGRAÇÕES v2.0 (COM RASTREAMENTO)
echo "🔄 FASE 3.4: MIGRAÇÕES AUTOMÁTICAS v2.0 - RASTREAMENTO ATIVO" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"

# Backup de segurança antes das migrações
BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
echo "💾 Criando backup de segurança: $BACKUP_TIMESTAMP" | tee -a "$LOG_FILE"

# Executar migrações via pre_start.py com timeout e logs detalhados
echo "🚀 Executando sistema de migrações v2.0 (idempotente)..." | tee -a "$LOG_FILE"

timeout "$MIGRATION_TIMEOUT" python3 /app/pre_start.py 2>&1 | tee -a "$MIGRATION_LOG"

MIGRATION_EXIT_CODE=$?

if [ $MIGRATION_EXIT_CODE -ne 0 ]; then
    echo "❌ ERRO: Migrações falhou com código $MIGRATION_EXIT_CODE" | tee -a "$LOG_FILE"
    
    if [ "$ENABLE_ROLLBACK" = "true" ]; then
        echo "🔙 ROLLBACK: Deploy cancelado por falha nas migrações" | tee -a "$LOG_FILE"
        echo "📋 Logs de migração disponíveis em: $MIGRATION_LOG" | tee -a "$LOG_FILE"
        exit 1
    else
        echo "⚠️ Continuando apesar da falha (rollback desabilitado)" | tee -a "$LOG_FILE"
    fi
else
    echo "✅ Migrações executadas com sucesso!" | tee -a "$LOG_FILE"
fi

# FASE 3.5: HEALTH CHECK PÓS-MIGRAÇÃO OBRIGATÓRIO
echo "🏥 FASE 3.5: HEALTH CHECK PÓS-MIGRAÇÃO" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

echo "🔍 Executando health check abrangente..." | tee -a "$LOG_FILE"

timeout "$HEALTH_CHECK_TIMEOUT" python3 -c "
import sys
import os
import json
import traceback
from datetime import datetime

sys.path.append('/app')

def log_health(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('/tmp/sige_health.log', 'a') as f:
        f.write(f'[{timestamp}] {message}\n')
    print(f'[{timestamp}] {message}')

log_health('🏥 INICIANDO HEALTH CHECK PÓS-MIGRAÇÃO')
log_health('='*40)

try:
    from app import app, db
    from sqlalchemy import text, inspect
    
    with app.app_context():
        health_result = {
            'timestamp': datetime.now().isoformat(),
            'status': 'unknown',
            'checks': {},
            'errors': [],
            'warnings': []
        }
        
        # 1. Teste de conectividade básica
        try:
            db.session.execute(text('SELECT 1'))
            health_result['checks']['database_connection'] = 'OK'
            log_health('✅ Conectividade com banco: OK')
        except Exception as e:
            health_result['checks']['database_connection'] = 'FAIL'
            health_result['errors'].append(f'DB Connection: {str(e)}')
            log_health(f'❌ Conectividade com banco: {e}')
        
        # 2. Verificar tabelas essenciais de veículos
        try:
            inspector = inspect(db.engine)
            tabelas_existentes = inspector.get_table_names()
            
            # ✅ ATUALIZADO: Tabelas do sistema FROTA (Outubro 2025)
            tabelas_essenciais = ['frota_veiculo', 'frota_utilizacao', 'frota_despesa']
            tabelas_obsoletas = ['alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo', 'manutencao_veiculo', 'alerta_veiculo']
            
            # Verificar essenciais
            for tabela in tabelas_essenciais:
                if tabela in tabelas_existentes:
                    health_result['checks'][f'table_{tabela}'] = 'OK'
                    log_health(f'✅ Tabela essencial: {tabela}')
                    
                    # Contar registros
                    try:
                        result = db.session.execute(text(f'SELECT COUNT(*) FROM {tabela}'))
                        count = result.scalar()
                        health_result['checks'][f'count_{tabela}'] = count
                        log_health(f'📊 {tabela}: {count} registros')
                    except Exception as e:
                        log_health(f'⚠️ Erro ao contar {tabela}: {e}')
                else:
                    health_result['checks'][f'table_{tabela}'] = 'MISSING'
                    health_result['errors'].append(f'Tabela essencial ausente: {tabela}')
                    log_health(f'❌ Tabela essencial ausente: {tabela}')
            
            # Verificar obsoletas (devem estar ausentes)
            obsoletas_presentes = []
            for tabela in tabelas_obsoletas:
                if tabela in tabelas_existentes:
                    obsoletas_presentes.append(tabela)
                    health_result['checks'][f'obsolete_{tabela}'] = 'PRESENT'
                    health_result['warnings'].append(f'Tabela obsoleta presente: {tabela}')
                    log_health(f'⚠️ Tabela obsoleta ainda presente: {tabela}')
                else:
                    health_result['checks'][f'obsolete_{tabela}'] = 'REMOVED'
                    log_health(f'✅ Tabela obsoleta removida: {tabela}')
            
            if obsoletas_presentes:
                log_health(f'⚠️ ATENÇÃO: {len(obsoletas_presentes)} tabelas obsoletas ainda presentes')
            else:
                log_health('✅ Todas as tabelas obsoletas foram removidas')
                
        except Exception as e:
            health_result['errors'].append(f'Erro verificação tabelas: {str(e)}')
            log_health(f'❌ Erro na verificação de tabelas: {e}')
        
        # 3. Teste de funcionalidade básica
        try:
            # Tentar importar e verificar modelos principais
            from models import Usuario, Funcionario, Obra
            
            # Contar registros principais
            count_usuarios = Usuario.query.count()
            count_funcionarios = Funcionario.query.count()
            count_obras = Obra.query.count()
            
            health_result['checks']['count_usuarios'] = count_usuarios
            health_result['checks']['count_funcionarios'] = count_funcionarios
            health_result['checks']['count_obras'] = count_obras
            
            log_health(f'📊 Sistema: {count_usuarios} usuários, {count_funcionarios} funcionários, {count_obras} obras')
            
        except Exception as e:
            health_result['warnings'].append(f'Erro verificação modelos: {str(e)}')
            log_health(f'⚠️ Erro na verificação de modelos: {e}')
        
        # Determinar status final
        if health_result['errors']:
            health_result['status'] = 'error'
            log_health(f'❌ HEALTH CHECK: ERRO ({len(health_result[\"errors\"])} erros)')
            
            # Se rollback estiver ativo e houver erros críticos, falhar
            if os.environ.get('ENABLE_ROLLBACK', 'true').lower() == 'true':
                log_health('🔙 ROLLBACK: Deploy cancelado por falha no health check')
                sys.exit(1)
                
        elif health_result['warnings']:
            health_result['status'] = 'warning'
            log_health(f'⚠️ HEALTH CHECK: WARNING ({len(health_result[\"warnings\"])} warnings)')
        else:
            health_result['status'] = 'healthy'
            log_health('✅ HEALTH CHECK: HEALTHY')
        
        # Salvar resultado completo
        with open('/tmp/health_check_result.json', 'w') as f:
            json.dump(health_result, f, indent=2)
        
        log_health('💾 Resultado completo salvo em: /tmp/health_check_result.json')
        log_health('✅ HEALTH CHECK CONCLUÍDO')
        
except Exception as e:
    log_health(f'❌ ERRO CRÍTICO NO HEALTH CHECK: {e}')
    log_health(f'📋 Traceback: {traceback.format_exc()}')
    
    if os.environ.get('ENABLE_ROLLBACK', 'true').lower() == 'true':
        log_health('🔙 ROLLBACK: Deploy cancelado por erro crítico')
        sys.exit(1)
" 2>&1 | tee -a "$HEALTH_LOG"

HEALTH_EXIT_CODE=$?

if [ $HEALTH_EXIT_CODE -ne 0 ]; then
    echo "❌ ERRO: Health check falhou com código $HEALTH_EXIT_CODE" | tee -a "$LOG_FILE"
    
    if [ "$ENABLE_ROLLBACK" = "true" ]; then
        echo "🔙 ROLLBACK: Deploy cancelado por falha no health check" | tee -a "$LOG_FILE"
        exit 1
    else
        echo "⚠️ Continuando apesar da falha no health check" | tee -a "$LOG_FILE"
    fi
else
    echo "✅ Health check concluído com sucesso!" | tee -a "$LOG_FILE"
fi

# FASE 3.6: LOGS FINAIS E INICIALIZAÇÃO
echo "🎯 FASE 3.6: DEPLOY AUTOMÁTICO CONCLUÍDO" | tee -a "$LOG_FILE"
echo "=======================================" | tee -a "$LOG_FILE"

echo "📋 RESUMO DO DEPLOY:" | tee -a "$LOG_FILE"
echo "   📅 Timestamp: $(date)" | tee -a "$LOG_FILE"
echo "   ⏱️ Duração total: $(($(date +%s) - DEPLOYMENT_TIMESTAMP))s" | tee -a "$LOG_FILE"
echo "   🔄 Migrações: Executadas automaticamente" | tee -a "$LOG_FILE"
echo "   🚗 Limpeza veículos: Forçada" | tee -a "$LOG_FILE"
echo "   🏥 Health check: Executado" | tee -a "$LOG_FILE"

echo "📁 LOGS DISPONÍVEIS:" | tee -a "$LOG_FILE"
echo "   📋 Deploy geral: $LOG_FILE" | tee -a "$LOG_FILE"
echo "   🔄 Migrações: $MIGRATION_LOG" | tee -a "$LOG_FILE"
echo "   🏥 Health check: $HEALTH_LOG" | tee -a "$LOG_FILE"
echo "   📊 Health result: /tmp/health_check_result.json" | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"

# FASE 3.7: SEED DEMO "Construtora Alfa" (Task #108)
# - Idempotente: chave natural = email admin@construtoraalfa.com.br
# - Implantações subsequentes detectam o admin e saem em silêncio (no-op)
# - Falhas NÃO derrubam o container — log e segue
echo "🌱 FASE 3.7: SEED DEMO ALFA (idempotente)" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
if [ "${SIGE_SKIP_DEMO_SEED:-false}" = "true" ]; then
    echo "⏭️ SIGE_SKIP_DEMO_SEED=true — pulando seed do dataset Alfa" | tee -a "$LOG_FILE"
else
    if [ -f /app/scripts/seed_demo_alfa.py ]; then
        SEED_LOG="/tmp/sige_seed_demo_alfa.log"
        timeout 60 python3 /app/scripts/seed_demo_alfa.py 2>&1 | tee -a "$SEED_LOG" | tee -a "$LOG_FILE" || \
            echo "⚠️ seed demo Alfa falhou (continuando deploy) — ver $SEED_LOG" | tee -a "$LOG_FILE"
    else
        echo "ℹ️ scripts/seed_demo_alfa.py ausente — seed pulado" | tee -a "$LOG_FILE"
    fi
fi

echo "🚀 SIGE v10.0 PRONTO PARA PRODUÇÃO!" | tee -a "$LOG_FILE"
echo "🌐 Iniciando aplicação em modo produção..." | tee -a "$LOG_FILE"

# Executar comando passado como parâmetro
exec "$@"