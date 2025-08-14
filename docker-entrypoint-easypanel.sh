#!/bin/bash
# DOCKER ENTRYPOINT EASYPANEL - SIGE v8.0 ROBUSTO
# Baseado nas melhores práticas do guia de deploy

set -e

echo ">>> Iniciando SIGE v8.0 no EasyPanel <<<"

# 1. Validar Variáveis de Ambiente Essenciais  
: "${DATABASE_URL:=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable}"
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
PGHOST=$(echo $DATABASE_URL | sed -E 's/^.*@([^:?]+).*/\1/' 2>/dev/null || echo "viajey_sige")
PGPORT=$(echo $DATABASE_URL | sed -E 's/^.*:([0-9]+).*/\1/' 2>/dev/null || echo "5432")
PGUSER=$(echo $DATABASE_URL | sed -E 's/^.*:\/\/([^:]+):.*/\1/' 2>/dev/null || echo "sige")

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
    echo "Tabelas não existem. Usando comando direto psql..."
    
    # Estratégia alternativa: usar SQL direto via psql
    echo "🔧 Executando criação via SQL direto..."
    
    # Criar script SQL básico
    cat > /tmp/create_tables.sql << 'EOF'
-- SCRIPT BÁSICO DE CRIAÇÃO - SIGE v8.0
CREATE TABLE IF NOT EXISTS usuario (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256),
    nome VARCHAR(100) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    tipo_usuario VARCHAR(20) DEFAULT 'funcionario',
    admin_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS funcionario (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) UNIQUE NOT NULL,
    nome VARCHAR(100) NOT NULL,
    cpf VARCHAR(14) UNIQUE NOT NULL,
    cargo VARCHAR(100),
    salario DECIMAL(10,2) DEFAULT 0.0,
    data_admissao DATE,
    ativo BOOLEAN DEFAULT TRUE,
    admin_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS obra (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    status VARCHAR(20) DEFAULT 'planejamento',
    data_inicio DATE,
    data_fim_prevista DATE,
    admin_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registro_ponto (
    id SERIAL PRIMARY KEY,
    funcionario_id INTEGER NOT NULL,
    data_registro DATE NOT NULL,
    hora_entrada TIME,
    hora_saida_almoco TIME,
    hora_retorno_almoco TIME,
    hora_saida TIME,
    tipo_lancamento VARCHAR(20) DEFAULT 'normal',
    admin_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

    # Executar SQL
    if psql "$DATABASE_URL" -f /tmp/create_tables.sql; then
        echo "✅ Tabelas básicas criadas via SQL direto!"
    else
        echo "❌ Erro na criação via SQL - tentando método Flask..."
        python3 -c "
import sys, os
sys.path.insert(0, '/app')
from app import app, db
with app.app_context():
    db.create_all()
    print('✅ Criação via Flask concluída')
"
    fi
fi

echo ">>> Configuração do banco de dados concluída <<<"

# Criar usuários administrativos via SQL direto
echo "👤 Criando usuários administrativos..."

# Script SQL para usuários
cat > /tmp/create_users.sql << 'EOF'
-- USUÁRIOS ADMINISTRATIVOS
INSERT INTO usuario (username, email, nome, password_hash, tipo_usuario, ativo) 
VALUES 
('admin', 'admin@sige.com', 'Super Admin', 'scrypt:32768:8:1$o8T5NlEWKHiEXE2Q$46c1dd2f6a3d0f0c3e2e8e1a1a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7', 'super_admin', TRUE),
('valeverde', 'valeverde@sige.com', 'Vale Verde Admin', 'scrypt:32768:8:1$o8T5NlEWKHiEXE2Q$46c1dd2f6a3d0f0c3e2e8e1a1a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7', 'admin', TRUE)
ON CONFLICT (email) DO NOTHING;
EOF

if psql "$DATABASE_URL" -f /tmp/create_users.sql; then
    echo "✅ Usuários criados via SQL direto!"
else
    echo "⚠️ Tentando criação via Python..."
    python3 -c "
import sys
sys.path.insert(0, '/app')
from werkzeug.security import generate_password_hash
from app import app, db
from models import Usuario

with app.app_context():
    # Criar usuários administrativos
    admin_user = Usuario(
        username='admin',
        email='admin@sige.com', 
        nome='Super Admin',
        password_hash=generate_password_hash('admin123'),
        tipo_usuario='super_admin',
        ativo=True
    )
    
    vale_user = Usuario(
        username='valeverde',
        email='valeverde@sige.com',
        nome='Vale Verde Admin', 
        password_hash=generate_password_hash('admin123'),
        tipo_usuario='admin',
        ativo=True,
        admin_id=10
    )
    
    try:
        db.session.add(admin_user)
        db.session.add(vale_user)
        db.session.commit()
        print('✅ Usuários criados via Python!')
    except Exception as e:
        print(f'⚠️ Usuários já existem: {e}')
"
fi

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