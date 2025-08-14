#!/bin/bash
# DOCKER ENTRYPOINT EASYPANEL - SIGE v8.0 ROBUSTO
# Baseado nas melhores práticas do guia de deploy

set -e

echo ">>> Iniciando SIGE v8.0 no EasyPanel <<<"

# 1. Validar Variáveis de Ambiente Essenciais
: "${DATABASE_URL:?Variável DATABASE_URL não está configurada. Verifique as configurações do EasyPanel.}"
: "${FLASK_ENV:=production}"
: "${PORT:=5000}"
: "${PYTHONPATH:=/app}"

echo "Configurações validadas:"
echo "- DATABASE_URL: ${DATABASE_URL}"
echo "- FLASK_ENV: ${FLASK_ENV}"
echo "- PORT: ${PORT}"

# 2. Limpar variáveis conflitantes (seguindo o guia)
# Isso garante que apenas DATABASE_URL seja usada
unset PGDATABASE PGUSER PGPASSWORD PGHOST PGPORT
unset POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT

# 3. Extrair informações de conexão da DATABASE_URL
PGHOST=$(echo $DATABASE_URL | sed -E 's/^.*@([^:]+):.*/\1/' 2>/dev/null || echo "localhost")
PGPORT=$(echo $DATABASE_URL | sed -E 's/^.*:([0-9]+).*/\1/' 2>/dev/null || echo "5432")
PGUSER=$(echo $DATABASE_URL | sed -E 's/^.*:\/\/([^:]+):.*/\1/' 2>/dev/null || echo "postgres")

echo "Conectando ao PostgreSQL: $PGUSER@$PGHOST:$PGPORT"

# 4. Aguardar PostgreSQL estar pronto (robusto)
echo "Aguardando inicialização do PostgreSQL..."
MAX_ATTEMPTS=30
ATTEMPTS=0

check_db_connection() {
    pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" > /dev/null 2>&1
    return $?
}

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    if check_db_connection; then
        echo "PostgreSQL está pronto!"
        break
    fi
    ATTEMPTS=$((ATTEMPTS+1))
    echo "PostgreSQL não está pronto - tentativa $ATTEMPTS de $MAX_ATTEMPTS - aguardando..."
    sleep 2
done

if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
    echo "ERRO: Não foi possível conectar ao PostgreSQL após $MAX_ATTEMPTS tentativas."
    echo "Verifique a DATABASE_URL e a conectividade de rede."
    exit 1
fi

echo "Banco de dados conectado com sucesso!"

cd /app

# 5. Verificar se tabelas já existem (como no guia Node.js)
echo "Verificando se as tabelas do banco de dados existem..."
TABLE_EXISTS=$(python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from app import app, db
    from sqlalchemy import text
    with app.app_context():
        result = db.session.execute(text('SELECT to_regclass(\\'public.usuario\\');')).scalar()
        print('exists' if result else 'not_exists')
except:
    print('not_exists')
" 2>/dev/null || echo "not_exists")

if [ "$TABLE_EXISTS" = "exists" ]; then
    echo "Tabelas já existem, pulando migração."
else
    echo "Tabelas não existem. Executando migração inicial..."
    python3 -c "
import os
import sys
sys.path.insert(0, '/app')

try:
    from app import app, db
    print('✅ App importado com sucesso')
    
    with app.app_context():
        # Dropar e recriar todas as tabelas
        db.drop_all()
        print('🗑️ Tabelas antigas removidas')
        
        db.create_all()
        print('✅ Tabelas criadas com sucesso')
        
        # Verificar tabelas criadas
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f'📊 {len(tables)} tabelas criadas: {tables[:5]}...')
        
except Exception as e:
    print(f'❌ Erro na criação de tabelas: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"
fi

echo ">>> Configuração do banco de dados concluída <<<"

# Criar usuários administrativos
echo "👤 Criando usuários administrativos..."
python3 -c "
import sys
sys.path.insert(0, '/app')

try:
    from app import app, db
    from models import Usuario, TipoUsuario
    from werkzeug.security import generate_password_hash
    
    with app.app_context():
        # Super Admin
        if not Usuario.query.filter_by(email='admin@sige.com').first():
            admin = Usuario(
                username='admin',
                email='admin@sige.com',
                nome='Super Admin',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.SUPER_ADMIN,
                ativo=True
            )
            db.session.add(admin)
            print('✅ Super Admin criado')
        
        # Admin Demo
        if not Usuario.query.filter_by(username='valeverde').first():
            admin_demo = Usuario(
                username='valeverde',
                email='valeverde@sige.com',
                nome='Vale Verde Admin',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True
            )
            db.session.add(admin_demo)
            print('✅ Admin Demo criado')
        
        db.session.commit()
        
        # Relatório final
        total = Usuario.query.count()
        print(f'📊 Total de usuários: {total}')
        
except Exception as e:
    print(f'❌ Erro na criação de usuários: {e}')
    import traceback
    traceback.print_exc()
"

echo "✅ SIGE v8.0 PRONTO PARA PRODUÇÃO!"
echo "🔐 CREDENCIAIS:"
echo "   • Super Admin: admin@sige.com / admin123"
echo "   • Admin Demo: valeverde / admin123"

# 7. Iniciar a aplicação (seguindo padrão exec "$@")
echo "Iniciando aplicação na porta $PORT..."
exec "$@"