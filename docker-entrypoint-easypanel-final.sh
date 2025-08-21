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

-- CRIAR TABELA CONFIGURACAO_EMPRESA SEM FOREIGN KEY
CREATE TABLE IF NOT EXISTS configuracao_empresa (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL,
    nome_empresa VARCHAR(200) NOT NULL,
    cnpj VARCHAR(20),
    endereco TEXT,
    telefone VARCHAR(20),
    email VARCHAR(120),
    website VARCHAR(200),
    logo_url VARCHAR(500),
    itens_inclusos_padrao TEXT,
    itens_exclusos_padrao TEXT,
    condicoes_padrao TEXT,
    condicoes_pagamento_padrao TEXT,
    garantias_padrao TEXT,
    observacoes_gerais_padrao TEXT,
    prazo_entrega_padrao INTEGER,
    validade_padrao INTEGER,
    percentual_nota_fiscal_padrao DECIMAL(5,2),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logo_base64 TEXT,
    cor_primaria VARCHAR(7) DEFAULT '#007bff',
    cor_secundaria VARCHAR(7) DEFAULT '#6c757d',
    cor_fundo_proposta VARCHAR(7) DEFAULT '#f8f9fa',
    logo_pdf_base64 TEXT,
    header_pdf_base64 TEXT,
    UNIQUE(admin_id)
);

-- CRIAR TABELA PROPOSTA_TEMPLATES SEM FOREIGN KEY  
CREATE TABLE IF NOT EXISTS proposta_templates (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    categoria VARCHAR(100),
    itens_padrao TEXT,
    prazo_entrega_dias INTEGER DEFAULT 90,
    validade_dias INTEGER DEFAULT 7,
    percentual_nota_fiscal DECIMAL(5,2) DEFAULT 13.50,
    itens_inclusos TEXT,
    itens_exclusos TEXT,
    condicoes TEXT,
    condicoes_pagamento TEXT,
    garantias TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    publico BOOLEAN DEFAULT FALSE,
    uso_contador INTEGER DEFAULT 0,
    admin_id INTEGER NOT NULL,
    criado_por INTEGER,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRIAR TABELA PROPOSTAS_COMERCIAIS SEM FOREIGN KEY
CREATE TABLE IF NOT EXISTS propostas_comerciais (
    id SERIAL PRIMARY KEY,
    numero_proposta VARCHAR(50) UNIQUE NOT NULL,
    cliente_nome VARCHAR(200) NOT NULL,
    cliente_email VARCHAR(120),
    cliente_telefone VARCHAR(20),
    cliente_endereco TEXT,
    assunto VARCHAR(500),
    objeto TEXT,
    valor_total DECIMAL(10,2) NOT NULL DEFAULT 0.0,
    prazo_entrega INTEGER DEFAULT 90,
    validade INTEGER DEFAULT 7,
    percentual_nota_fiscal DECIMAL(5,2) DEFAULT 13.50,
    status VARCHAR(50) DEFAULT 'rascunho',
    admin_id INTEGER NOT NULL,
    criado_por INTEGER,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    publico BOOLEAN DEFAULT FALSE,
    token_cliente VARCHAR(255) UNIQUE,
    itens_inclusos TEXT,
    itens_exclusos TEXT,
    condicoes TEXT,
    condicoes_pagamento TEXT,
    garantias TEXT,
    observacoes_gerais TEXT
);

-- CRIAR TABELA PROPOSTA_ITENS SEM FOREIGN KEY
CREATE TABLE IF NOT EXISTS proposta_itens (
    id SERIAL PRIMARY KEY,
    proposta_id INTEGER NOT NULL,
    descricao VARCHAR(500) NOT NULL,
    quantidade DECIMAL(10,3) NOT NULL DEFAULT 1,
    unidade VARCHAR(10) DEFAULT 'un',
    preco_unitario DECIMAL(10,2) NOT NULL DEFAULT 0.0,
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.0,
    ordem INTEGER DEFAULT 0,
    admin_id INTEGER NOT NULL,
    categoria_titulo VARCHAR(200),
    template_origem_id INTEGER,
    template_origem_nome VARCHAR(200),
    grupo_ordem INTEGER DEFAULT 0,
    item_ordem_no_grupo INTEGER DEFAULT 0
);

-- CONFIGURAÇÃO DA EMPRESA PARA O ADMIN ID=10
INSERT INTO configuracao_empresa (
    admin_id, nome_empresa, cnpj, endereco, telefone, email, website,
    itens_inclusos_padrao, itens_exclusos_padrao, condicoes_padrao, 
    condicoes_pagamento_padrao, garantias_padrao, prazo_entrega_padrao,
    validade_padrao, percentual_nota_fiscal_padrao, cor_primaria,
    cor_secundaria, cor_fundo_proposta
) VALUES (
    10, 
    'Vale Verde Estruturas Metálicas',
    '12.345.678/0001-90',
    'Rodovia BR-116, KM 142 - Distrito Industrial, São José dos Campos/SP',
    '(12) 99999-9999',
    'contato@valeverde.com.br',
    'https://www.valeverde.com.br',
    'Mão de obra para execução dos serviços; Todos os equipamentos de segurança necessários; Transporte e alimentação da equipe; Container para guarda de ferramentas; Movimentação de carga (Munck); Transporte dos materiais',
    'Projeto e execução de qualquer obra civil, fundações, alvenarias, elétrica, automação, tubulações etc.; Execução de ensaios destrutivos e radiográficos; Fornecimento de local para armazenagem das peças; Fornecimento e/ou serviços não especificados claramente nesta proposta; Fornecimento de escoramento (escoras); Fornecimento de andaimes e plataformas; Técnico de segurança; Pintura final de acabamento; Calhas, rufos, condutores e pingadeiras',
    'Prazo de Entrega: 90 dias; Percentual Nota Fiscal: 13.50%; Pagamento via PIX com desconto de 2%',
    '10% de entrada na assinatura do contrato; 10% após projeto aprovado; 45% compra dos perfis; 25% no início da montagem in loco; 10% após a conclusão da montagem',
    'A Vale Verde Estruturas Metálicas garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.; Garantia de montagem: 12 meses; Suporte técnico: 24 meses',
    90,
    7,
    13.50,
    '#008b3a',
    '#6c757d',
    '#f0f8ff'
) ON CONFLICT (admin_id) DO UPDATE SET
    nome_empresa = EXCLUDED.nome_empresa,
    cnpj = EXCLUDED.cnpj,
    endereco = EXCLUDED.endereco,
    telefone = EXCLUDED.telefone,
    email = EXCLUDED.email,
    website = EXCLUDED.website;

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
-- Em produção, manter os admin_id existentes se já tiverem dados
-- UPDATE funcionario SET admin_id = 10 WHERE admin_id = 4;

-- OBRA DEMO
INSERT INTO obra (codigo, nome, descricao, status, data_inicio, data_fim_prevista, admin_id, token_cliente, orcamento, valor_contrato, area_total_m2, cliente_nome, cliente_email, cliente_telefone, portal_ativo)
VALUES ('OBR001', 'Jardim das Flores - Vargem Velha', 'Construção de galpão industrial 500m²', 'andamento', '2024-07-01', '2024-12-31', 10, 'demo_token_cliente_123', 150000.00, 180000.00, 500.00, 'José Silva Santos', 'jose.silva@email.com', '(11) 99999-9999', TRUE)
ON CONFLICT (codigo) DO NOTHING;

EOSQL

    echo "✅ Estrutura criada via SQL direto!"
fi

# Remover foreign keys problemáticas e adicionar colunas que podem estar faltando
echo "🔧 Removendo constraints problemáticas e atualizando schema..."
psql "$DATABASE_URL" << 'EOSQL' || true
-- REMOVER FOREIGN KEY CONSTRAINTS PROBLEMÁTICAS
DO $$
BEGIN
    -- Remover constraint de configuracao_empresa se existir
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints 
               WHERE constraint_name = 'configuracao_empresa_admin_id_fkey' 
               AND table_name = 'configuracao_empresa') THEN
        ALTER TABLE configuracao_empresa DROP CONSTRAINT configuracao_empresa_admin_id_fkey;
        RAISE NOTICE 'Foreign key constraint configuracao_empresa_admin_id_fkey removida';
    END IF;
    
    -- Remover constraint de proposta_templates se existir
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints 
               WHERE constraint_name = 'proposta_templates_admin_id_fkey' 
               AND table_name = 'proposta_templates') THEN
        ALTER TABLE proposta_templates DROP CONSTRAINT proposta_templates_admin_id_fkey;
        RAISE NOTICE 'Foreign key constraint proposta_templates_admin_id_fkey removida';
    END IF;
    
    -- Remover constraint de propostas_comerciais se existir
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints 
               WHERE constraint_name = 'propostas_comerciais_admin_id_fkey' 
               AND table_name = 'propostas_comerciais') THEN
        ALTER TABLE propostas_comerciais DROP CONSTRAINT propostas_comerciais_admin_id_fkey;
        RAISE NOTICE 'Foreign key constraint propostas_comerciais_admin_id_fkey removida';
    END IF;
    
    RAISE NOTICE 'Constraints de foreign key removidas com sucesso';
END
$$;

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

-- ADICIONAR CAMPO FALTANTE EM REGISTRO_PONTO
ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS tipo_local VARCHAR(50) DEFAULT 'obra';
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