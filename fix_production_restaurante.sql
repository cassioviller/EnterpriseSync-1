-- Script SQL para Correção do Schema da Tabela Restaurante em Produção
-- Baseado no diagnóstico: colunas faltantes identificadas

-- Verificar schema atual
\echo '🔍 Schema atual da tabela restaurante:'
\d restaurante

-- Adicionar colunas faltantes identificadas pelo diagnóstico
\echo '🔧 Adicionando colunas faltantes...'

-- Coluna responsavel (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'restaurante' AND column_name = 'responsavel'
    ) THEN
        ALTER TABLE restaurante ADD COLUMN responsavel VARCHAR(100);
        RAISE NOTICE '✅ Coluna responsavel adicionada';
    ELSE
        RAISE NOTICE '✅ Coluna responsavel já existe';
    END IF;
END $$;

-- Coluna preco_almoco (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'restaurante' AND column_name = 'preco_almoco'
    ) THEN
        ALTER TABLE restaurante ADD COLUMN preco_almoco DECIMAL(10,2) DEFAULT 0.00;
        RAISE NOTICE '✅ Coluna preco_almoco adicionada';
    ELSE
        RAISE NOTICE '✅ Coluna preco_almoco já existe';
    END IF;
END $$;

-- Coluna preco_jantar (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'restaurante' AND column_name = 'preco_jantar'
    ) THEN
        ALTER TABLE restaurante ADD COLUMN preco_jantar DECIMAL(10,2) DEFAULT 0.00;
        RAISE NOTICE '✅ Coluna preco_jantar adicionada';
    ELSE
        RAISE NOTICE '✅ Coluna preco_jantar já existe';
    END IF;
END $$;

-- Coluna preco_lanche (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'restaurante' AND column_name = 'preco_lanche'
    ) THEN
        ALTER TABLE restaurante ADD COLUMN preco_lanche DECIMAL(10,2) DEFAULT 0.00;
        RAISE NOTICE '✅ Coluna preco_lanche adicionada';
    ELSE
        RAISE NOTICE '✅ Coluna preco_lanche já existe';
    END IF;
END $$;

-- Coluna admin_id (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'restaurante' AND column_name = 'admin_id'
    ) THEN
        ALTER TABLE restaurante ADD COLUMN admin_id INTEGER;
        RAISE NOTICE '✅ Coluna admin_id adicionada';
    ELSE
        RAISE NOTICE '✅ Coluna admin_id já existe';
    END IF;
END $$;

-- Remover coluna duplicada se existir
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'restaurante' AND column_name = 'contato_responsavel'
    ) THEN
        ALTER TABLE restaurante DROP COLUMN contato_responsavel;
        RAISE NOTICE '🗑️ Coluna duplicada contato_responsavel removida';
    ELSE
        RAISE NOTICE '✅ Coluna contato_responsavel não existe (correto)';
    END IF;
END $$;

-- Configurar admin_id para restaurantes existentes
\echo '🔧 Configurando admin_id para restaurantes existentes...'
UPDATE restaurante 
SET admin_id = 1 
WHERE admin_id IS NULL OR admin_id = 0;

\echo '✅ Schema corrigido! Verificando resultado final:'

-- Mostrar schema final
\d restaurante

-- Contar restaurantes
SELECT COUNT(*) as total_restaurantes FROM restaurante;

\echo '🎉 CORREÇÃO CONCLUÍDA! Acesse /restaurantes para verificar.'