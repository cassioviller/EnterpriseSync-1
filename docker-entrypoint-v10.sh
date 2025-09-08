#!/bin/bash
# SIGE v10.0 - DIGITAL MASTERY ENTRYPOINT
# Entrypoint robusto para produção EasyPanel/Hostinger
# Autor: Joris Kuypers Architecture
# Data: 2025-09-08 - Versão: 10.0.1

set -e  # Parar em caso de erro

# Cores para logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Função de log com timestamp
log() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  $1${NC}"
}

# Banner de inicialização
echo -e "${PURPLE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    SIGE v10.0 - DIGITAL MASTERY             ║"
echo "║              Sistema Integrado de Gestão Empresarial        ║"
echo "║                     Joris Kuypers Architecture              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

log "🚀 Iniciando SIGE v10.0 Digital Mastery..."
log_info "Ambiente: PRODUÇÃO"
log_info "Plataforma: EasyPanel/Hostinger"
log_info "Arquitetura: Microsserviços com Observabilidade"

# Verificar variáveis de ambiente
log "🔍 Verificando configurações de ambiente..."

if [ -z "$DATABASE_URL" ]; then
    log_warning "DATABASE_URL não definida, usando configuração padrão do EasyPanel"
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
fi

log_info "DATABASE_URL configurada: ${DATABASE_URL}"

# Configurações adicionais
export DIGITAL_MASTERY_MODE=true
export OBSERVABILITY_ENABLED=true
export RDO_MASTERY_ENABLED=true
export FLASK_ENV=production

log_success "Variáveis de ambiente configuradas"

# Função para testar conexão com banco
test_database_connection() {
    log "🔌 Testando conexão com banco de dados..."
    
    for i in {1..30}; do
        if pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; then
            log_success "Conexão com banco estabelecida"
            return 0
        fi
        
        log_warning "Tentativa $i/30: Aguardando banco de dados..."
        sleep 2
    done
    
    log_error "Falha ao conectar com banco após 30 tentativas"
    return 1
}

# Função para executar migrações com logs detalhados
run_migrations() {
    log "📊 Iniciando migrações do banco de dados..."
    
    # Backup antes das migrações (se necessário)
    if [ "$BACKUP_BEFORE_MIGRATION" = "true" ]; then
        log_info "Criando backup antes das migrações..."
        pg_dump "$DATABASE_URL" > "/app/backups/backup_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null || log_warning "Backup falhou, continuando..."
    fi
    
    # Executar migrações Python
    log "🔄 Executando migrações automáticas..."
    
    python3 << 'EOF'
import sys
import os
sys.path.append('/app')

try:
    from app import app, db
    from sqlalchemy import text
    import logging
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    with app.app_context():
        logger.info("🔍 Verificando estrutura do banco...")
        
        # Verificar se as tabelas principais existem
        tables_to_check = [
            'usuario', 'obra', 'servico', 'rdo', 'funcionario',
            'proposta_templates', 'servico_obra_real'
        ]
        
        existing_tables = []
        missing_tables = []
        
        for table in tables_to_check:
            try:
                result = db.session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                existing_tables.append(table)
                logger.info(f"✅ Tabela '{table}' existe e está acessível")
            except Exception as e:
                missing_tables.append(table)
                logger.warning(f"⚠️  Tabela '{table}' não encontrada ou inaccessível: {str(e)}")
        
        logger.info(f"📊 Resumo: {len(existing_tables)} tabelas OK, {len(missing_tables)} tabelas ausentes")
        
        # Criar tabelas ausentes se necessário
        if missing_tables:
            logger.info("🔨 Criando tabelas ausentes...")
            try:
                db.create_all()
                logger.info("✅ Tabelas criadas com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao criar tabelas: {str(e)}")
                sys.exit(1)
        
        # Verificar colunas críticas
        logger.info("🔍 Verificando colunas críticas...")
        
        critical_columns = [
            ('usuario', 'admin_id'),
            ('obra', 'admin_id'),
            ('servico', 'admin_id'),
            ('rdo', 'admin_id'),
            ('proposta_templates', 'admin_id')
        ]
        
        for table, column in critical_columns:
            try:
                result = db.session.execute(text(f"SELECT {column} FROM {table} LIMIT 1"))
                logger.info(f"✅ Coluna '{column}' existe na tabela '{table}'")
            except Exception as e:
                logger.warning(f"⚠️  Coluna '{column}' ausente na tabela '{table}': {str(e)}")
                
                # Tentar adicionar coluna admin_id se não existir
                if column == 'admin_id':
                    try:
                        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN admin_id INTEGER"))
                        db.session.commit()
                        logger.info(f"✅ Coluna 'admin_id' adicionada à tabela '{table}'")
                    except Exception as add_error:
                        logger.warning(f"⚠️  Não foi possível adicionar coluna admin_id: {str(add_error)}")
        
        # Verificar dados de teste
        logger.info("🔍 Verificando dados básicos...")
        
        try:
            user_count = db.session.execute(text("SELECT COUNT(*) FROM usuario")).scalar()
            obra_count = db.session.execute(text("SELECT COUNT(*) FROM obra")).scalar()
            servico_count = db.session.execute(text("SELECT COUNT(*) FROM servico")).scalar()
            
            logger.info(f"📊 Dados encontrados: {user_count} usuários, {obra_count} obras, {servico_count} serviços")
            
            if user_count == 0:
                logger.warning("⚠️  Nenhum usuário encontrado - sistema pode precisar de dados iniciais")
            
        except Exception as e:
            logger.warning(f"⚠️  Não foi possível verificar dados: {str(e)}")
        
        logger.info("✅ Migrações concluídas com sucesso")
        
except Exception as e:
    logger.error(f"❌ Erro durante migrações: {str(e)}")
    sys.exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        log_success "Migrações executadas com sucesso"
    else
        log_error "Falha nas migrações"
        exit 1
    fi
}

# Função para validar sistema
validate_system() {
    log "🔍 Validando sistema..."
    
    # Verificar arquivos críticos
    critical_files=(
        "/app/app.py"
        "/app/models.py"
        "/app/views.py"
        "/app/templates/base_completo.html"
        "/app/templates/rdo/novo.html"
    )
    
    for file in "${critical_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "Arquivo crítico encontrado: $file"
        else
            log_error "Arquivo crítico ausente: $file"
            exit 1
        fi
    done
    
    # Verificar blueprints
    log_info "Verificando blueprints registrados..."
    python3 -c "
import sys
sys.path.append('/app')
from app import app
print(f'📊 Blueprints registrados: {len(app.blueprints)}')
for name in app.blueprints.keys():
    print(f'  ✅ {name}')
" || log_warning "Não foi possível verificar blueprints"
    
    log_success "Sistema validado"
}

# Função para inicializar logs
setup_logging() {
    log "📝 Configurando sistema de logs..."
    
    mkdir -p /app/logs
    
    # Configurar rotação de logs
    cat > /app/logs/logrotate.conf << 'EOF'
/app/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 sige sige
}
EOF
    
    log_success "Sistema de logs configurado"
}

# Função principal
main() {
    # Configurar logs
    setup_logging
    
    # Testar conexão com banco
    if ! test_database_connection; then
        log_error "Falha na conexão com banco de dados"
        exit 1
    fi
    
    # Executar migrações
    run_migrations
    
    # Validar sistema
    validate_system
    
    log "🎯 Configurações específicas do RDO Digital Mastery..."
    export RDO_MASTERY_EXTRACTION_ENABLED=true
    export RDO_MASTERY_VALIDATION_ENABLED=true
    export RDO_MASTERY_OBSERVABILITY_ENABLED=true
    
    log_success "Sistema SIGE v10.0 Digital Mastery pronto para produção!"
    log_info "Iniciando aplicação Flask..."
    
    # Executar comando passado como argumento
    exec "$@"
}

# Trap para cleanup
cleanup() {
    log_warning "Recebido sinal de parada, finalizando graciosamente..."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Executar função principal
main "$@"