-- HOTFIX CRÍTICO - Adicionar coluna obra.cliente ausente em produção
-- Script para executar diretamente no PostgreSQL de produção

DO $$
DECLARE
    column_exists boolean := false;
BEGIN
    -- Verificar se coluna obra.cliente existe
    SELECT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'cliente'
    ) INTO column_exists;
    
    -- Adicionar coluna se não existir
    IF NOT column_exists THEN
        ALTER TABLE obra ADD COLUMN cliente VARCHAR(200);
        RAISE NOTICE '✅ Coluna obra.cliente adicionada com sucesso';
    ELSE
        RAISE NOTICE '✅ Coluna obra.cliente já existe';
    END IF;
    
    -- Verificar outras colunas essenciais da obra
    PERFORM 1;
    
    -- Garantir que cliente_nome existe
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'cliente_nome'
    ) THEN
        ALTER TABLE obra ADD COLUMN cliente_nome VARCHAR(100);
        RAISE NOTICE '✅ Coluna obra.cliente_nome adicionada';
    END IF;
    
    -- Garantir que cliente_email existe
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'cliente_email'
    ) THEN
        ALTER TABLE obra ADD COLUMN cliente_email VARCHAR(120);
        RAISE NOTICE '✅ Coluna obra.cliente_email adicionada';
    END IF;
    
    -- Garantir que cliente_telefone existe
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'cliente_telefone'
    ) THEN
        ALTER TABLE obra ADD COLUMN cliente_telefone VARCHAR(20);
        RAISE NOTICE '✅ Coluna obra.cliente_telefone adicionada';
    END IF;
    
    -- Garantir que token_cliente existe
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'token_cliente'
    ) THEN
        ALTER TABLE obra ADD COLUMN token_cliente VARCHAR(255);
        RAISE NOTICE '✅ Coluna obra.token_cliente adicionada';
    END IF;
    
    -- Garantir que portal_ativo existe
    IF NOT EXISTS (
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'obra' AND column_name = 'portal_ativo'
    ) THEN
        ALTER TABLE obra ADD COLUMN portal_ativo BOOLEAN DEFAULT TRUE;
        RAISE NOTICE '✅ Coluna obra.portal_ativo adicionada';
    END IF;
    
    -- Verificar estrutura final
    RAISE NOTICE '🔍 Verificando estrutura final da tabela obra...';
    
    -- Teste da query que estava falhando
    PERFORM obra.id, obra.nome, obra.cliente 
    FROM obra 
    WHERE obra.admin_id IS NOT NULL 
    LIMIT 1;
    
    RAISE NOTICE '✅ HOTFIX CONCLUÍDO - Tabela obra corrigida com sucesso!';
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '❌ Erro durante hotfix: %', SQLERRM;
        RAISE;
END
$$;