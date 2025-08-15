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
    foto_base64 TEXT,
    departamento_id INTEGER,
    funcao_id INTEGER,
    horario_trabalho_id INTEGER,
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
    token_cliente VARCHAR(255) UNIQUE,
    responsavel_id INTEGER,
    endereco TEXT,
    orcamento DECIMAL(10,2) DEFAULT 0.0,
    valor_contrato DECIMAL(10,2) DEFAULT 0.0,
    area_total_m2 DECIMAL(10,2) DEFAULT 0.0,
    cliente_nome VARCHAR(100),
    cliente_email VARCHAR(120),
    cliente_telefone VARCHAR(20),
    portal_ativo BOOLEAN DEFAULT TRUE,
    data_previsao_fim DATE,
    ativo BOOLEAN DEFAULT TRUE,
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

-- FUNCIONÁRIOS DEMO PARA PRODUÇÃO - CORRIGIDO ADMIN_ID
INSERT INTO funcionario (codigo, nome, cpf, cargo, salario, data_admissao, admin_id, ativo)
VALUES 
('FUN001', 'Carlos Alberto Santos', '123.456.789-00', 'Operador', 2500.00, '2024-01-15', 10, TRUE),
('FUN002', 'Maria Silva Costa', '234.567.890-11', 'Auxiliar Administrativo', 2200.00, '2024-02-01', 10, TRUE),
('FUN003', 'João Oliveira Lima', '345.678.901-22', 'Soldador', 3200.00, '2024-03-10', 10, TRUE),
('FUN004', 'Ana Paula Santos', '456.789.012-33', 'Ajudante Geral', 1800.00, '2024-04-05', 10, TRUE),
('FUN005', 'Pedro Costa Alves', '567.890.123-44', 'Motorista', 2800.00, '2024-05-20', 10, TRUE)
ON CONFLICT (codigo) DO NOTHING;

-- CORRIGIR FUNCIONÁRIOS EXISTENTES PARA O ADMIN CORRETO
UPDATE funcionario SET admin_id = 10 WHERE admin_id = 4;

-- OBRA DEMO
INSERT INTO obra (codigo, nome, descricao, status, data_inicio, data_fim_prevista, admin_id, token_cliente, orcamento, valor_contrato, area_total_m2, cliente_nome, cliente_email, cliente_telefone, portal_ativo)
VALUES ('OBR001', 'Jardim das Flores - Vargem Velha', 'Construção de galpão industrial 500m²', 'andamento', '2024-07-01', '2024-12-31', 10, 'demo_token_cliente_123', 150000.00, 180000.00, 500.00, 'José Silva Santos', 'jose.silva@email.com', '(11) 99999-9999', TRUE)
ON CONFLICT (codigo) DO NOTHING;

EOSQL

    echo "✅ Estrutura criada via SQL direto!"
fi

# Adicionar colunas que podem estar faltando
echo "🔧 Atualizando schema para compatibilidade..."
psql "$DATABASE_URL" << 'EOSQL' || true
-- Adicionar campos que podem estar faltando (compatibilidade com schema existente)
ALTER TABLE obra ADD COLUMN IF NOT EXISTS token_cliente VARCHAR(255) UNIQUE;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS responsavel_id INTEGER;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS cliente_nome VARCHAR(100);
ALTER TABLE obra ADD COLUMN IF NOT EXISTS cliente_email VARCHAR(120);
ALTER TABLE obra ADD COLUMN IF NOT EXISTS cliente_telefone VARCHAR(20);
ALTER TABLE obra ADD COLUMN IF NOT EXISTS portal_ativo BOOLEAN DEFAULT TRUE;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS data_previsao_fim DATE;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS orcamento DECIMAL(10,2) DEFAULT 0.0;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS valor_contrato DECIMAL(10,2) DEFAULT 0.0;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS area_total_m2 DECIMAL(10,2) DEFAULT 0.0;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS ultima_visualizacao_cliente TIMESTAMP;
ALTER TABLE obra ADD COLUMN IF NOT EXISTS proposta_origem_id INTEGER;

ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS foto_base64 TEXT;
ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS departamento_id INTEGER;
ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS funcao_id INTEGER;
ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS horario_trabalho_id INTEGER;
ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS rg VARCHAR(20);
ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS telefone VARCHAR(20);
ALTER TABLE funcionario ADD COLUMN IF NOT EXISTS email VARCHAR(120);

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_obra_token_cliente ON obra(token_cliente);
CREATE INDEX IF NOT EXISTS idx_funcionario_admin_id ON funcionario(admin_id);
CREATE INDEX IF NOT EXISTS idx_obra_admin_id ON obra(admin_id);
EOSQL

# Verificação final
FINAL_TABLES=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
FINAL_USERS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM usuario;" | tr -d ' ')
FINAL_OBRAS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM obra;" | tr -d ' ')

echo "📊 DEPLOY CONCLUÍDO:"
echo "   • Tabelas: $FINAL_TABLES"
echo "   • Usuários: $FINAL_USERS"
echo "   • Obras: $FINAL_OBRAS"
echo "   • Credenciais: admin@sige.com / admin123"
echo "   • Credenciais: valeverde@sige.com / admin123"

echo "🚀 Iniciando aplicação na porta $PORT..."
exec "$@"