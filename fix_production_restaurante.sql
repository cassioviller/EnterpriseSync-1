-- CORREÇÃO MANUAL PARA PRODUÇÃO - TABELA RESTAURANTE
-- Execute no terminal do EasyPanel ou cliente PostgreSQL

-- 1. VERIFICAR ESTADO ATUAL
SELECT 'COLUNAS ATUAIS:' as status;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'restaurante' 
ORDER BY ordinal_position;

-- 2. REMOVER COLUNA DUPLICADA (se existir)
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'restaurante' AND column_name = 'contato_responsavel') THEN
        ALTER TABLE restaurante DROP COLUMN contato_responsavel;
        RAISE NOTICE 'Coluna contato_responsavel removida';
    ELSE
        RAISE NOTICE 'Coluna contato_responsavel já não existe';
    END IF;
END $$;

-- 3. ADICIONAR COLUNAS FALTANTES (se não existirem)
DO $$ 
BEGIN
    -- Responsavel
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'restaurante' AND column_name = 'responsavel') THEN
        ALTER TABLE restaurante ADD COLUMN responsavel VARCHAR(100);
        RAISE NOTICE 'Coluna responsavel adicionada';
    END IF;
    
    -- Preços
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'restaurante' AND column_name = 'preco_almoco') THEN
        ALTER TABLE restaurante ADD COLUMN preco_almoco DOUBLE PRECISION DEFAULT 0.0;
        RAISE NOTICE 'Coluna preco_almoco adicionada';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'restaurante' AND column_name = 'preco_jantar') THEN
        ALTER TABLE restaurante ADD COLUMN preco_jantar DOUBLE PRECISION DEFAULT 0.0;
        RAISE NOTICE 'Coluna preco_jantar adicionada';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'restaurante' AND column_name = 'preco_lanche') THEN
        ALTER TABLE restaurante ADD COLUMN preco_lanche DOUBLE PRECISION DEFAULT 0.0;
        RAISE NOTICE 'Coluna preco_lanche adicionada';
    END IF;
    
    -- Observações
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'restaurante' AND column_name = 'observacoes') THEN
        ALTER TABLE restaurante ADD COLUMN observacoes TEXT;
        RAISE NOTICE 'Coluna observacoes adicionada';
    END IF;
    
    -- Admin ID para multi-tenant
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'restaurante' AND column_name = 'admin_id') THEN
        ALTER TABLE restaurante ADD COLUMN admin_id INTEGER;
        RAISE NOTICE 'Coluna admin_id adicionada';
    END IF;
END $$;

-- 4. ATUALIZAR VALORES PADRÃO PARA REGISTROS EXISTENTES
UPDATE restaurante SET 
    preco_almoco = COALESCE(preco_almoco, 0.0),
    preco_jantar = COALESCE(preco_jantar, 0.0),
    preco_lanche = COALESCE(preco_lanche, 0.0),
    admin_id = COALESCE(admin_id, 10)  -- ID do admin Vale Verde
WHERE preco_almoco IS NULL OR preco_jantar IS NULL OR preco_lanche IS NULL OR admin_id IS NULL;

-- 5. VERIFICAR RESULTADO FINAL
SELECT 'COLUNAS APÓS CORREÇÃO:' as status;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'restaurante' 
ORDER BY ordinal_position;

-- 6. CONTAR REGISTROS
SELECT 'TOTAL DE RESTAURANTES:' as status, COUNT(*) as total FROM restaurante;

SELECT 'CORREÇÃO COMPLETA!' as status;