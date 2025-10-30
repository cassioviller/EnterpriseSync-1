-- ============================================================================
-- CORREÇÃO DIRETA EM PRODUÇÃO - Migration 48
-- Execute este SQL se os scripts Python não funcionarem
-- ============================================================================

-- IMPORTANTE: Faça backup ANTES de executar!
-- pg_dump $DATABASE_URL > /tmp/backup_$(date +%Y%m%d_%H%M%S).sql

BEGIN;

-- ============================================================================
-- 1. TABELA: rdo_mao_obra
-- ============================================================================

DO $$
DECLARE
    admin_id_padrao INTEGER;
BEGIN
    -- Encontrar admin_id mais comum nas tabelas relacionadas
    SELECT admin_id INTO admin_id_padrao
    FROM obra
    WHERE admin_id IS NOT NULL
    GROUP BY admin_id
    ORDER BY COUNT(*) DESC
    LIMIT 1;
    
    RAISE NOTICE 'Admin ID padrão detectado: %', admin_id_padrao;
    
    -- Verificar se coluna já existe
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'rdo_mao_obra' AND column_name = 'admin_id'
    ) THEN
        RAISE NOTICE '🔧 Adicionando admin_id em rdo_mao_obra...';
        
        -- Adicionar coluna
        ALTER TABLE rdo_mao_obra ADD COLUMN admin_id INTEGER;
        
        -- Backfill usando relacionamento com obra via rdo
        UPDATE rdo_mao_obra rm
        SET admin_id = o.admin_id
        FROM rdo r
        JOIN obra o ON r.obra_id = o.id
        WHERE rm.rdo_id = r.id
          AND rm.admin_id IS NULL
          AND o.admin_id IS NOT NULL;
        
        -- Aplicar NOT NULL
        ALTER TABLE rdo_mao_obra ALTER COLUMN admin_id SET NOT NULL;
        
        -- Adicionar foreign key
        ALTER TABLE rdo_mao_obra
        ADD CONSTRAINT fk_rdo_mao_obra_admin_id
        FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
        
        -- Criar índice
        CREATE INDEX idx_rdo_mao_obra_admin_id ON rdo_mao_obra(admin_id);
        
        RAISE NOTICE '✅ rdo_mao_obra.admin_id criada';
    ELSE
        RAISE NOTICE '⏭️  rdo_mao_obra.admin_id já existe';
    END IF;
END $$;

-- ============================================================================
-- 2. TABELA: funcao
-- ============================================================================

DO $$
DECLARE
    admin_id_padrao INTEGER;
BEGIN
    -- Encontrar admin_id mais comum
    SELECT admin_id INTO admin_id_padrao
    FROM funcionario
    WHERE admin_id IS NOT NULL
    GROUP BY admin_id
    ORDER BY COUNT(*) DESC
    LIMIT 1;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'funcao' AND column_name = 'admin_id'
    ) THEN
        RAISE NOTICE '🔧 Adicionando admin_id em funcao...';
        
        ALTER TABLE funcao ADD COLUMN admin_id INTEGER;
        
        -- Backfill usando funcionario.funcao_id
        UPDATE funcao fu
        SET admin_id = f.admin_id
        FROM funcionario f
        WHERE f.funcao_id = fu.id
          AND fu.admin_id IS NULL
          AND f.admin_id IS NOT NULL;
        
        -- Se ainda houver NULLs, usar admin_id padrão
        UPDATE funcao
        SET admin_id = admin_id_padrao
        WHERE admin_id IS NULL;
        
        ALTER TABLE funcao ALTER COLUMN admin_id SET NOT NULL;
        
        ALTER TABLE funcao
        ADD CONSTRAINT fk_funcao_admin_id
        FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
        
        CREATE INDEX idx_funcao_admin_id ON funcao(admin_id);
        
        RAISE NOTICE '✅ funcao.admin_id criada';
    ELSE
        RAISE NOTICE '⏭️  funcao.admin_id já existe';
    END IF;
END $$;

-- ============================================================================
-- 3. TABELA: registro_alimentacao
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'registro_alimentacao' AND column_name = 'admin_id'
    ) THEN
        RAISE NOTICE '🔧 Adicionando admin_id em registro_alimentacao...';
        
        ALTER TABLE registro_alimentacao ADD COLUMN admin_id INTEGER;
        
        -- Backfill usando funcionario_id
        UPDATE registro_alimentacao ra
        SET admin_id = f.admin_id
        FROM funcionario f
        WHERE ra.funcionario_id = f.id
          AND ra.admin_id IS NULL
          AND f.admin_id IS NOT NULL;
        
        ALTER TABLE registro_alimentacao ALTER COLUMN admin_id SET NOT NULL;
        
        ALTER TABLE registro_alimentacao
        ADD CONSTRAINT fk_registro_alimentacao_admin_id
        FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
        
        CREATE INDEX idx_registro_alimentacao_admin_id ON registro_alimentacao(admin_id);
        
        RAISE NOTICE '✅ registro_alimentacao.admin_id criada';
    ELSE
        RAISE NOTICE '⏭️  registro_alimentacao.admin_id já existe';
    END IF;
END $$;

-- ============================================================================
-- COMMIT e VALIDAÇÃO
-- ============================================================================

-- Se chegou aqui sem erros, fazer commit
COMMIT;

-- Validar resultado
DO $$
DECLARE
    count_rdo_mao_obra INTEGER;
    count_funcao INTEGER;
    count_registro_alimentacao INTEGER;
BEGIN
    SELECT COUNT(*) INTO count_rdo_mao_obra
    FROM information_schema.columns 
    WHERE table_name = 'rdo_mao_obra' AND column_name = 'admin_id';
    
    SELECT COUNT(*) INTO count_funcao
    FROM information_schema.columns 
    WHERE table_name = 'funcao' AND column_name = 'admin_id';
    
    SELECT COUNT(*) INTO count_registro_alimentacao
    FROM information_schema.columns 
    WHERE table_name = 'registro_alimentacao' AND column_name = 'admin_id';
    
    RAISE NOTICE '';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ CORREÇÃO CONCLUÍDA';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'rdo_mao_obra.admin_id: %', CASE WHEN count_rdo_mao_obra > 0 THEN '✅' ELSE '❌' END;
    RAISE NOTICE 'funcao.admin_id: %', CASE WHEN count_funcao > 0 THEN '✅' ELSE '❌' END;
    RAISE NOTICE 'registro_alimentacao.admin_id: %', CASE WHEN count_registro_alimentacao > 0 THEN '✅' ELSE '❌' END;
    RAISE NOTICE '';
    RAISE NOTICE '🔄 Próximo passo: Reinicie a aplicação';
    RAISE NOTICE 'supervisorctl restart all';
    RAISE NOTICE '====================================================================';
END $$;

-- Instruções de uso:
-- 1. Conectar ao banco: psql $DATABASE_URL
-- 2. Executar este arquivo: \i correcao_direta_producao.sql
-- 3. OU via comando: psql $DATABASE_URL < correcao_direta_producao.sql
