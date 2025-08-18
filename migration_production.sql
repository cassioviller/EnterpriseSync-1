-- Script para executar no banco de produção
-- Este script adiciona a coluna 'categoria' que está faltando na tabela proposta_templates

-- Primeiro, verificar se a coluna já existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'proposta_templates' 
        AND column_name = 'categoria'
    ) THEN
        -- Adicionar a coluna categoria
        ALTER TABLE proposta_templates 
        ADD COLUMN categoria character varying(50) NOT NULL DEFAULT 'Estrutura Metálica';
        
        RAISE NOTICE 'Coluna categoria adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna categoria já existe!';
    END IF;
END
$$;

-- Verificar outras colunas que podem estar faltando
DO $$
BEGIN
    -- Verificar e adicionar itens_inclusos se não existir
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'proposta_templates' 
        AND column_name = 'itens_inclusos'
    ) THEN
        ALTER TABLE proposta_templates 
        ADD COLUMN itens_inclusos text;
        RAISE NOTICE 'Coluna itens_inclusos adicionada!';
    END IF;

    -- Verificar e adicionar itens_exclusos se não existir
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'proposta_templates' 
        AND column_name = 'itens_exclusos'
    ) THEN
        ALTER TABLE proposta_templates 
        ADD COLUMN itens_exclusos text;
        RAISE NOTICE 'Coluna itens_exclusos adicionada!';
    END IF;

    -- Verificar e adicionar condicoes se não existir
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'proposta_templates' 
        AND column_name = 'condicoes'
    ) THEN
        ALTER TABLE proposta_templates 
        ADD COLUMN condicoes text;
        RAISE NOTICE 'Coluna condicoes adicionada!';
    END IF;
END
$$;

-- Verificar a estrutura final da tabela
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'proposta_templates' 
ORDER BY ordinal_position;