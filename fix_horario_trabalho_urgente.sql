-- ============================================================================
-- FIX URGENTE: horario_trabalho.admin_id
-- Adiciona coluna admin_id na tabela horario_trabalho
-- Script idempotente - pode ser executado múltiplas vezes
-- ============================================================================

BEGIN;

DO $$
BEGIN
    -- Verificar se coluna já existe
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'horario_trabalho' AND column_name = 'admin_id'
    ) THEN
        RAISE NOTICE '⏭️  horario_trabalho.admin_id já existe - nada a fazer';
        RETURN;
    END IF;
    
    RAISE NOTICE '🔄 Corrigindo tabela horario_trabalho...';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- PASSO 1: Adicionar coluna
    -- ========================================================================
    RAISE NOTICE '📝 PASSO 1: Adicionando coluna admin_id...';
    ALTER TABLE horario_trabalho ADD COLUMN admin_id INTEGER;
    RAISE NOTICE '   ✅ Coluna adicionada';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- PASSO 2: Backfill via funcionario.horario_trabalho_id
    -- ========================================================================
    RAISE NOTICE '🔄 PASSO 2: Backfill via funcionario.horario_trabalho_id...';
    
    UPDATE horario_trabalho ht
    SET admin_id = f.admin_id
    FROM funcionario f
    WHERE f.horario_trabalho_id = ht.id
      AND ht.admin_id IS NULL
      AND f.admin_id IS NOT NULL;
    
    RAISE NOTICE '   ✅ Backfill via funcionario concluído';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- PASSO 3: Aplicar admin_id padrão (2) para registros órfãos
    -- ========================================================================
    RAISE NOTICE '🔧 PASSO 3: Corrigindo registros órfãos...';
    
    UPDATE horario_trabalho 
    SET admin_id = 2 
    WHERE admin_id IS NULL;
    
    RAISE NOTICE '   ✅ Registros órfãos corrigidos (admin_id = 2)';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- PASSO 4: Aplicar NOT NULL
    -- ========================================================================
    RAISE NOTICE '🔒 PASSO 4: Aplicando constraint NOT NULL...';
    ALTER TABLE horario_trabalho ALTER COLUMN admin_id SET NOT NULL;
    RAISE NOTICE '   ✅ Constraint NOT NULL aplicada';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- PASSO 5: Adicionar foreign key
    -- ========================================================================
    RAISE NOTICE '🔗 PASSO 5: Adicionando foreign key...';
    ALTER TABLE horario_trabalho
    ADD CONSTRAINT fk_horario_trabalho_admin_id
    FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
    RAISE NOTICE '   ✅ Foreign key criada: fk_horario_trabalho_admin_id';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- PASSO 6: Criar índice
    -- ========================================================================
    RAISE NOTICE '⚡ PASSO 6: Criando índice...';
    CREATE INDEX idx_horario_trabalho_admin_id ON horario_trabalho(admin_id);
    RAISE NOTICE '   ✅ Índice criado: idx_horario_trabalho_admin_id';
    RAISE NOTICE '';
    
    -- ========================================================================
    -- RESUMO FINAL
    -- ========================================================================
    RAISE NOTICE '═══════════════════════════════════════════════════════════════';
    RAISE NOTICE '✅ TABELA horario_trabalho CORRIGIDA COM SUCESSO!';
    RAISE NOTICE '═══════════════════════════════════════════════════════════════';
    
END $$;

COMMIT;

-- ============================================================================
-- VALIDAÇÃO
-- ============================================================================

SELECT 
    'horario_trabalho' as tabela,
    COUNT(*) as total_registros,
    COUNT(admin_id) as com_admin_id,
    COUNT(*) - COUNT(admin_id) as sem_admin_id,
    COUNT(DISTINCT admin_id) as admins_distintos
FROM horario_trabalho;

-- Mostrar dados
SELECT id, nome, admin_id, created_at 
FROM horario_trabalho 
ORDER BY id;
