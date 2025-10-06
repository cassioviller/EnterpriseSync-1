-- ============================================================================
-- SCRIPT PARA ADICIONAR motorista_id NA TABELA uso_veiculo (PRODUÇÃO)
-- ============================================================================
-- 
-- OBJETIVO: Corrigir erro "column motorista_id does not exist"
-- QUANDO EXECUTAR: Uma única vez no banco de produção
-- 
-- INSTRUÇÕES:
-- 1. Conecte-se ao banco de produção
-- 2. Execute este script completo
-- 3. Verifique que o comando retornou sucesso
-- ============================================================================

-- Adicionar coluna motorista_id (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'uso_veiculo' 
        AND column_name = 'motorista_id'
    ) THEN
        -- Adicionar coluna
        ALTER TABLE uso_veiculo 
        ADD COLUMN motorista_id INTEGER;
        
        RAISE NOTICE 'Coluna motorista_id adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna motorista_id já existe, nada a fazer.';
    END IF;
END $$;

-- Adicionar Foreign Key (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_uso_veiculo_motorista'
    ) THEN
        ALTER TABLE uso_veiculo 
        ADD CONSTRAINT fk_uso_veiculo_motorista 
        FOREIGN KEY (motorista_id) 
        REFERENCES funcionario(id) 
        ON DELETE SET NULL;
        
        RAISE NOTICE 'Foreign key fk_uso_veiculo_motorista adicionada!';
    ELSE
        RAISE NOTICE 'Foreign key fk_uso_veiculo_motorista já existe.';
    END IF;
END $$;

-- Criar índice para performance (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_indexes 
        WHERE indexname = 'idx_uso_veiculo_motorista'
    ) THEN
        CREATE INDEX idx_uso_veiculo_motorista 
        ON uso_veiculo(motorista_id);
        
        RAISE NOTICE 'Índice idx_uso_veiculo_motorista criado!';
    ELSE
        RAISE NOTICE 'Índice idx_uso_veiculo_motorista já existe.';
    END IF;
END $$;

-- Verificar resultado
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'uso_veiculo' 
AND column_name = 'motorista_id';

-- ============================================================================
-- RESULTADO ESPERADO:
-- column_name   | data_type | is_nullable
-- motorista_id  | integer   | YES
-- ============================================================================
