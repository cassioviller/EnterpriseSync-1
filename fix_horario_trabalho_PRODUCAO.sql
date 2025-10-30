-- ============================================================================
-- SCRIPT DE PRODUÇÃO: Adiciona admin_id na tabela horario_trabalho
-- Execute via psql: psql $DATABASE_URL -f fix_horario_trabalho_PRODUCAO.sql
-- ============================================================================

BEGIN;

-- Verificar se coluna já existe
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'horario_trabalho' AND column_name = 'admin_id'
    ) THEN
        RAISE NOTICE '⏭️  admin_id já existe - nada a fazer';
        RETURN;
    END IF;
    
    RAISE NOTICE '🔧 Iniciando correção de horario_trabalho...';
    RAISE NOTICE '';
    
    -- PASSO 1: Adicionar coluna
    RAISE NOTICE '📝 PASSO 1: Adicionando coluna admin_id...';
    ALTER TABLE horario_trabalho ADD COLUMN admin_id INTEGER;
    RAISE NOTICE '   ✅ Coluna adicionada';
    RAISE NOTICE '';
    
    -- PASSO 2: Backfill via funcionario
    RAISE NOTICE '🔄 PASSO 2: Preenchendo admin_id via funcionario...';
    UPDATE horario_trabalho ht
    SET admin_id = f.admin_id
    FROM funcionario f
    WHERE f.horario_trabalho_id = ht.id
      AND ht.admin_id IS NULL
      AND f.admin_id IS NOT NULL;
    RAISE NOTICE '   ✅ Backfill concluído';
    RAISE NOTICE '';
    
    -- PASSO 3: Preencher NULLs com admin_id = 2
    RAISE NOTICE '🔧 PASSO 3: Preenchendo órfãos com admin_id = 2...';
    UPDATE horario_trabalho 
    SET admin_id = 2 
    WHERE admin_id IS NULL;
    RAISE NOTICE '   ✅ Órfãos corrigidos';
    RAISE NOTICE '';
    
    -- PASSO 4: Aplicar NOT NULL
    RAISE NOTICE '🔒 PASSO 4: Aplicando NOT NULL...';
    ALTER TABLE horario_trabalho ALTER COLUMN admin_id SET NOT NULL;
    RAISE NOTICE '   ✅ Constraint aplicada';
    RAISE NOTICE '';
    
    -- PASSO 5: Adicionar foreign key
    RAISE NOTICE '🔗 PASSO 5: Criando foreign key...';
    ALTER TABLE horario_trabalho
    ADD CONSTRAINT fk_horario_trabalho_admin_id
    FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
    RAISE NOTICE '   ✅ Foreign key criada';
    RAISE NOTICE '';
    
    -- PASSO 6: Criar índice
    RAISE NOTICE '⚡ PASSO 6: Criando índice...';
    CREATE INDEX idx_horario_trabalho_admin_id ON horario_trabalho(admin_id);
    RAISE NOTICE '   ✅ Índice criado';
    RAISE NOTICE '';
    
    RAISE NOTICE '✅ CORREÇÃO CONCLUÍDA COM SUCESSO!';
END $$;

COMMIT;

-- Validação
SELECT 
    'horario_trabalho' as tabela,
    COUNT(*) as total,
    COUNT(admin_id) as com_admin_id,
    COUNT(DISTINCT admin_id) as admins
FROM horario_trabalho;

-- Mostrar dados
SELECT id, nome, admin_id 
FROM horario_trabalho 
ORDER BY id;
