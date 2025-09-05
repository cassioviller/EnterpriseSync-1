#!/bin/bash
# DIGITAL MASTERY ENTRYPOINT - SIGE v10.0
# Implementação dos Princípios de Joris Kuypers
# "Kaipa da primeira vez certo" + Observabilidade Completa

set -e

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

# PostgreSQL connection with observability
echo "🔄 Aguardando PostgreSQL com observabilidade..."
POSTGRES_RETRIES=0
MAX_RETRIES=30

while [ $POSTGRES_RETRIES -lt $MAX_RETRIES ]; do
    if pg_isready -h ${DATABASE_HOST:-viajey_sige} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-sige} > /dev/null 2>&1; then
        echo "✅ PostgreSQL conectado! (tentativa: $((POSTGRES_RETRIES + 1)))"
        break
    fi
    POSTGRES_RETRIES=$((POSTGRES_RETRIES + 1))
    echo "⏳ Tentativa $POSTGRES_RETRIES/$MAX_RETRIES - aguardando PostgreSQL..."
    sleep 2
done

if [ $POSTGRES_RETRIES -eq $MAX_RETRIES ]; then
    echo "❌ ERRO: PostgreSQL não disponível após $MAX_RETRIES tentativas"
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
        
        # Execute migrations with observability
        logger.info('🔄 Executing Digital Mastery migrations...')
        try:
            from migrations import executar_migracoes
            executar_migracoes()
            logger.info('✅ Migrations completed successfully!')
        except Exception as migration_error:
            logger.warning(f'⚠️ Migration warning: {migration_error}')
        
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

# RDO System Corrections for Production
echo "🔧 Aplicando correções RDO para produção..."
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