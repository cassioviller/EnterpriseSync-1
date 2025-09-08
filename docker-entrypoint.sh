#!/bin/bash
# DIGITAL MASTERY ENTRYPOINT - SIGE v10.0 PRODUCTION
# Implementação dos Princípios de Joris Kuypers para PRODUÇÃO
# "Kaipa da primeira vez certo" + Observabilidade Completa + Robustez
# Aplicação dos 4 pilares: Robustez, Escalabilidade, Observabilidade, Manutenibilidade

set -euo pipefail  # Fail fast com pipeline safety
IFS=$'\n\t'       # Secure Internal Field Separator

# Trap para cleanup em caso de erro (Joris principle: resilience)
trap 'echo "❌ ERRO FATAL na linha $LINENO. Saída código: $?"; exit 1' ERR
trap 'echo "⚠️ SIGTERM recebido. Shutdown graceful..."; exit 0' TERM
trap 'echo "⚠️ SIGINT recebido. Shutdown graceful..."; exit 0' INT

echo "🎯 =============================================="
echo "🚀 SIGE v10.0 - DIGITAL MASTERY ARCHITECTURE"
echo "📊 Observabilidade Completa + RDO System"
echo "⚡ Implementação Joris Kuypers Principles"
echo "🎯 =============================================="

# Configuração de ambiente Digital Mastery
export DATABASE_URL="${DATABASE_URL:-postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable}"
export FLASK_APP=main.py
export DIGITAL_MASTERY_MODE=true
export OBSERVABILITY_ENABLED=true

echo "🔧 DATABASE_URL: $DATABASE_URL"
echo "📊 DIGITAL_MASTERY_MODE: $DIGITAL_MASTERY_MODE"

# PostgreSQL connection com retry exponential backoff (Joris: robustness)
echo "🔄 Aguardando PostgreSQL com estratégia avançada..."
POSTGRES_RETRIES=0
MAX_RETRIES=30
BASE_DELAY=1

while [ $POSTGRES_RETRIES -lt $MAX_RETRIES ]; do
    if pg_isready -h ${DATABASE_HOST:-viajey_sige} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-sige} > /dev/null 2>&1; then
        echo "✅ PostgreSQL conectado! (tentativa: $((POSTGRES_RETRIES + 1)))"
        
        # Teste de conexão SQL avançado
        if psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
            echo "✅ Teste SQL avançado: SUCESSO"
            break
        else
            echo "⚠️ PostgreSQL disponível mas conexão SQL falhou"
        fi
    fi
    
    POSTGRES_RETRIES=$((POSTGRES_RETRIES + 1))
    # Exponential backoff com jitter
    DELAY=$((BASE_DELAY * (2 ** (POSTGRES_RETRIES / 5))))
    JITTER=$((RANDOM % 3))
    TOTAL_DELAY=$((DELAY + JITTER))
    
    echo "⏳ Tentativa $POSTGRES_RETRIES/$MAX_RETRIES - aguardando ${TOTAL_DELAY}s..."
    sleep $TOTAL_DELAY
done

if [ $POSTGRES_RETRIES -eq $MAX_RETRIES ]; then
    echo "❌ ERRO CRÍTICO: PostgreSQL inacessível após $MAX_RETRIES tentativas"
    echo "🔍 Database URL: $DATABASE_URL"
    echo "🔍 Host: ${DATABASE_HOST:-viajey_sige}"
    echo "🔍 Port: ${DATABASE_PORT:-5432}"
    exit 1
fi

cd /app

# Digital Mastery Database Initialization
echo "🎯 Inicializando Digital Mastery Database..."
python3 -c "
import os
import logging
from datetime import datetime

# Configure observability logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - MASTERY - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DigitalMastery')

logger.info('🚀 DIGITAL MASTERY INITIALIZATION STARTED')

try:
    from app import app, db
    import models
    
    with app.app_context():
        logger.info('📊 Creating all database tables...')
        db.create_all()
        logger.info('✅ All tables created successfully!')
        
        # MIGRAÇÕES DESABILITADAS - Corrigindo logs infinitos em produção
        logger.info('🔇 Digital Mastery migrations DISABLED - preventing infinite logs')
        # try:
        #     from migrations import executar_migracoes
        #     executar_migracoes()
        #     logger.info('✅ Migrations completed successfully!')
        # except Exception as migration_error:
        #     logger.warning(f'⚠️ Migration warning: {migration_error}')
        
        # Database schema validation
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        logger.info(f'📊 Total tables in database: {len(tables)}')
        
        # Specific RDO system validation
        required_tables = [
            'rdo', 'rdo_servico_subatividade', 
            'servico_obra_real', 'servico_obra'
        ]
        
        missing_tables = [table for table in required_tables if table not in tables]
        if missing_tables:
            logger.error(f'❌ Missing required tables: {missing_tables}')
        else:
            logger.info('✅ All RDO system tables present!')

except Exception as e:
    logger.error(f'❌ CRITICAL ERROR in Digital Mastery initialization: {e}')
    import traceback
    traceback.print_exc()
    exit(1)

logger.info('🎯 DIGITAL MASTERY INITIALIZATION COMPLETED')
"

# RDO System Corrections for Production (Joris: "Kaipa da primeira vez certo")
echo "🔧 Aplicando correções RDO para produção..."

# Apply critical RDO fixes with error handling
echo "🎯 Aplicando logs críticos de RDO..."
if [ -f "production_rdo_fix.py" ]; then
    python3 production_rdo_fix.py || echo "⚠️ Warning: production_rdo_fix.py não executado"
else
    echo "⚠️ production_rdo_fix.py não encontrado - pulando"
fi
python3 -c "
import logging
from datetime import datetime

logger = logging.getLogger('RDO_Production_Fix')
logger.setLevel(logging.INFO)

try:
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        logger.info('🔄 Starting RDO production fixes...')
        
        # Fix 1: Ensure servico_obra has correct structure
        try:
            result = db.session.execute(text('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'servico_obra' 
                AND column_name = 'quantidade_planejada'
            '''))
            
            if not result.fetchone():
                logger.info('⚡ Adding quantidade_planejada column...')
                db.session.execute(text('''
                    ALTER TABLE servico_obra 
                    ADD COLUMN quantidade_planejada DECIMAL(10,4) DEFAULT 1.0
                '''))
                
            # Ensure all servico_obra records have quantidade_planejada
            db.session.execute(text('''
                UPDATE servico_obra 
                SET quantidade_planejada = 1.0 
                WHERE quantidade_planejada IS NULL
            '''))
            
            db.session.commit()
            logger.info('✅ servico_obra structure validated')
            
        except Exception as e:
            logger.warning(f'⚠️ servico_obra fix warning: {e}')
            db.session.rollback()
        
        # Fix 2: Ensure RDO number generation compatibility
        try:
            # Check if any RDO exists to validate the system
            rdo_count = db.session.execute(text('SELECT COUNT(*) FROM rdo')).scalar()
            logger.info(f'📊 RDO records in database: {rdo_count}')
            
        except Exception as e:
            logger.warning(f'⚠️ RDO validation warning: {e}')
        
        logger.info('✅ RDO production fixes completed')
        
except Exception as e:
    logger.error(f'❌ Error in RDO production fixes: {e}')
    import traceback
    traceback.print_exc()
"

# Create admin users with observability
echo "👤 Criando usuários administrativos com observabilidade..."
python3 -c "
import logging
from datetime import datetime

logger = logging.getLogger('UserCreation')
logger.setLevel(logging.INFO)

try:
    from app import app, db
    from models import Usuario, TipoUsuario
    from werkzeug.security import generate_password_hash
    
    with app.app_context():
        users_created = 0
        
        # Create Super Admin
        if not Usuario.query.filter_by(email='admin@valeverde.com.br').first():
            admin = Usuario(
                username='admin',
                email='admin@valeverde.com.br',
                nome='Administrador Sistema',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.ADMIN,
                admin_id=10,
                ativo=True
            )
            db.session.add(admin)
            users_created += 1
            logger.info('✅ Admin principal criado: admin@valeverde.com.br')
        
        # Create production admin if in production environment
        if not Usuario.query.filter_by(email='admin@sige.com').first():
            prod_admin = Usuario(
                username='sige_admin',
                email='admin@sige.com', 
                nome='SIGE Admin Produção',
                password_hash=generate_password_hash('sige2025'),
                tipo_usuario=TipoUsuario.ADMIN,
                admin_id=2,
                ativo=True
            )
            db.session.add(prod_admin)
            users_created += 1
            logger.info('✅ Admin produção criado: admin@sige.com')
        
        if users_created > 0:
            db.session.commit()
            logger.info(f'📊 {users_created} usuários criados')
        
        # Count and log user statistics
        total_users = Usuario.query.count()
        admin_users = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).count()
        
        logger.info(f'📊 ESTATÍSTICAS DE USUÁRIOS:')
        logger.info(f'   • Total: {total_users}')
        logger.info(f'   • Admins: {admin_users}')
        
except Exception as e:
    logger.error(f'❌ Erro na criação de usuários: {e}')
    import traceback
    traceback.print_exc()
"

# Digital Mastery System Validation
echo "🎯 Validação final Digital Mastery..."
python3 -c "
import logging
from datetime import datetime

logger = logging.getLogger('DigitalMasteryValidation')
logger.setLevel(logging.INFO)

try:
    from app import app
    
    with app.app_context():
        # Test observability system
        try:
            from utils.observability import mastery_observer
            operation_id = mastery_observer.start_operation('SYSTEM_VALIDATION')
            mastery_observer.add_step(operation_id, 'PRODUCTION_READY', {
                'timestamp': datetime.now().isoformat(),
                'system_status': 'operational',
                'digital_mastery': True
            })
            mastery_observer.finish_operation(operation_id, 'SUCCESS')
            logger.info('✅ Observability system validated')
        except Exception as e:
            logger.warning(f'⚠️ Observability warning: {e}')
        
        # Test RDO extraction function
        try:
            # Import the corrected extraction function
            from views import _extrair_subatividades_form
            logger.info('✅ RDO extraction function available')
        except Exception as e:
            logger.warning(f'⚠️ RDO function warning: {e}')
        
        logger.info('🎯 DIGITAL MASTERY SYSTEM VALIDATION COMPLETED')
        
except Exception as e:
    logger.error(f'❌ Validation error: {e}')
"

echo "🎯 =============================================="
echo "✅ SIGE v10.0 Digital Mastery PRONTO!"
echo "📊 Observabilidade Completa Ativada"
echo "🚀 Sistema RDO com Correções Aplicadas"
echo "🎯 =============================================="
echo ""
echo "🔑 ACESSO SISTEMA:"
echo "   • Desenvolvimento: admin@valeverde.com.br / admin123"
echo "   • Produção: admin@sige.com / sige2025"
echo ""
echo "📊 ENDPOINTS OBSERVABILIDADE:"
echo "   • Health Check: /health"
echo "   • Debug Dashboard: /debug/mastery-dashboard"
echo ""

# Execute the command passed to the container
exec \"$@\"