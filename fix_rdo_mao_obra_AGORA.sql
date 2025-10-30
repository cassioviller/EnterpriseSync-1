-- ============================================================================
-- CORREÇÃO EMERGENCIAL: Adicionar admin_id em rdo_mao_obra
-- Execute AGORA no banco de produção
-- ============================================================================

-- VERIFICAR ANTES: psql $DATABASE_URL -c "\d rdo_mao_obra"
-- Se admin_id NÃO aparecer, execute este script

BEGIN;

DO $$
BEGIN
    -- Verificar se coluna admin_id já existe
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'rdo_mao_obra' 
          AND column_name = 'admin_id'
    ) THEN
        
        RAISE NOTICE '🔧 Adicionando coluna admin_id em rdo_mao_obra...';
        
        -- 1. Adicionar coluna (nullable primeiro)
        ALTER TABLE rdo_mao_obra 
        ADD COLUMN admin_id INTEGER;
        
        RAISE NOTICE '✅ Coluna criada';
        
        -- 2. Backfill: Pegar admin_id da obra via rdo
        UPDATE rdo_mao_obra rm
        SET admin_id = o.admin_id
        FROM rdo r
        JOIN obra o ON r.obra_id = o.id
        WHERE rm.rdo_id = r.id
          AND rm.admin_id IS NULL
          AND o.admin_id IS NOT NULL;
        
        RAISE NOTICE '✅ Dados preenchidos via obra';
        
        -- 3. Verificar se sobraram NULLs
        DECLARE
            count_nulls INTEGER;
        BEGIN
            SELECT COUNT(*) INTO count_nulls
            FROM rdo_mao_obra
            WHERE admin_id IS NULL;
            
            IF count_nulls > 0 THEN
                RAISE NOTICE '⚠️  % registros ainda com admin_id NULL', count_nulls;
                
                -- Tentar via funcionario
                UPDATE rdo_mao_obra rm
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE rm.funcionario_id = f.id
                  AND rm.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                RAISE NOTICE '✅ Preenchimento adicional via funcionario';
            END IF;
        END;
        
        -- 4. Aplicar NOT NULL (só se não houver NULLs)
        DECLARE
            count_nulls_final INTEGER;
        BEGIN
            SELECT COUNT(*) INTO count_nulls_final
            FROM rdo_mao_obra
            WHERE admin_id IS NULL;
            
            IF count_nulls_final = 0 THEN
                ALTER TABLE rdo_mao_obra 
                ALTER COLUMN admin_id SET NOT NULL;
                
                RAISE NOTICE '✅ Constraint NOT NULL aplicada';
            ELSE
                RAISE WARNING '⚠️  % registros ainda NULL - NOT NULL não aplicado', count_nulls_final;
            END IF;
        END;
        
        -- 5. Adicionar foreign key
        ALTER TABLE rdo_mao_obra
        ADD CONSTRAINT fk_rdo_mao_obra_admin_id
        FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
        
        RAISE NOTICE '✅ Foreign key criada';
        
        -- 6. Criar índice para performance
        CREATE INDEX idx_rdo_mao_obra_admin_id 
        ON rdo_mao_obra(admin_id);
        
        RAISE NOTICE '✅ Índice criado';
        
        RAISE NOTICE '';
        RAISE NOTICE '====================================================================';
        RAISE NOTICE '✅ SUCESSO: admin_id adicionado em rdo_mao_obra';
        RAISE NOTICE '====================================================================';
        
    ELSE
        RAISE NOTICE '';
        RAISE NOTICE '====================================================================';
        RAISE NOTICE '⏭️  SKIP: admin_id JÁ EXISTE em rdo_mao_obra';
        RAISE NOTICE '====================================================================';
    END IF;
END $$;

-- Validar resultado
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'rdo_mao_obra'
  AND column_name = 'admin_id';

-- Verificar distribuição de dados
SELECT 
    admin_id,
    COUNT(*) as total_registros
FROM rdo_mao_obra
GROUP BY admin_id
ORDER BY admin_id;

COMMIT;

-- ============================================================================
-- INSTRUÇÕES DE USO:
-- ============================================================================
-- 
-- 1. Fazer backup ANTES:
--    pg_dump $DATABASE_URL > /tmp/backup_rdo_mao_obra.sql
--
-- 2. Executar este script:
--    psql $DATABASE_URL < fix_rdo_mao_obra_AGORA.sql
--
-- 3. Reiniciar aplicação:
--    supervisorctl restart all
--
-- 4. Testar:
--    Acessar: /funcionario/rdo/consolidado
--    Deve mostrar porcentagens e funcionários
-- ============================================================================
