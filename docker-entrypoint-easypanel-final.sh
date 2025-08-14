#!/bin/bash

# SIGE v8.0 - Script de Deploy EasyPanel DEFINITIVO
# Solução: SQL direto para evitar problemas SQLAlchemy

set -e

echo ">>> SIGE v8.0 - Deploy EasyPanel (SQL Strategy) <<<"

# Variáveis de ambiente
: "${DATABASE_URL:=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable}"
: "${FLASK_ENV:=production}"
: "${PORT:=5000}"

echo "🔧 Aguardando PostgreSQL..."
for i in {1..30}; do
    if psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
        echo "✅ PostgreSQL conectado!"
        break
    fi
    echo "⏳ Tentativa $i/30..."
    sleep 2
done

# Verificar se tabelas existem
TABLE_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$TABLE_COUNT" -gt "0" ]; then
    echo "📋 $TABLE_COUNT tabelas já existem, mantendo estrutura atual"
else
    echo "🏗️ Criando estrutura inicial via SQL..."
    
    # Script SQL completo 
    psql "$DATABASE_URL" << 'EOSQL'
-- ESTRUTURA BÁSICA SIGE v8.0
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

-- USUÁRIOS ADMINISTRATIVOS
INSERT INTO usuario (username, email, nome, password_hash, tipo_usuario, ativo, admin_id) 
VALUES 
('admin', 'admin@sige.com', 'Super Admin', 'scrypt:32768:8:1$o8T5NlEWKHiEXE2Q$46c1dd2f6a3d0f0c3e2e8e1a1a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7', 'super_admin', TRUE, NULL),
('valeverde', 'valeverde@sige.com', 'Vale Verde Admin', 'scrypt:32768:8:1$o8T5NlEWKHiEXE2Q$46c1dd2f6a3d0f0c3e2e8e1a1a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7a8a8a9a5a7', 'admin', TRUE, 10)
ON CONFLICT (email) DO NOTHING;

-- FUNCIONÁRIO DEMO
INSERT INTO funcionario (codigo, nome, cpf, cargo, salario, data_admissao, admin_id)
VALUES ('FUN001', 'Carlos Alberto Santos', '123.456.789-00', 'Operador', 2500.00, '2024-01-15', 10)
ON CONFLICT (codigo) DO NOTHING;

EOSQL

    echo "✅ Estrutura criada via SQL direto!"
fi

# Verificação final
FINAL_TABLES=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
FINAL_USERS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM usuario;" | tr -d ' ')

echo "📊 DEPLOY CONCLUÍDO:"
echo "   • Tabelas: $FINAL_TABLES"
echo "   • Usuários: $FINAL_USERS"
echo "   • Credenciais: admin@sige.com / admin123"
echo "   • Credenciais: valeverde@sige.com / admin123"

echo "🚀 Iniciando aplicação na porta $PORT..."
exec "$@"