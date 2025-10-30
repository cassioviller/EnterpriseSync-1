#!/usr/bin/env python3
"""
Script para adicionar admin_id na tabela rdo_mao_obra
Executa de forma independente e idempotente
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_rdo_mao_obra_admin_id():
    """Adiciona admin_id na tabela rdo_mao_obra"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada")
        return False
    
    logger.info("=" * 80)
    logger.info("🔧 CORREÇÃO: rdo_mao_obra.admin_id")
    logger.info("=" * 80)
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Verificar se coluna já existe
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_mao_obra' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ rdo_mao_obra.admin_id JÁ EXISTE - skip")
                return True
            
            logger.warning("⚠️  rdo_mao_obra.admin_id NÃO EXISTE - corrigindo...")
            
            # Executar correção
            connection.execute(text("""
                BEGIN;
                
                -- 1. Adicionar coluna
                ALTER TABLE rdo_mao_obra ADD COLUMN admin_id INTEGER;
                
                -- 2. Backfill usando rdo → obra
                UPDATE rdo_mao_obra rm
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE rm.rdo_id = r.id
                  AND rm.admin_id IS NULL
                  AND o.admin_id IS NOT NULL;
                
                -- 3. Backfill usando funcionario (fallback)
                UPDATE rdo_mao_obra rm
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE rm.funcionario_id = f.id
                  AND rm.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- 4. Aplicar NOT NULL (só se não houver NULLs)
                DO $$
                DECLARE
                    count_nulls INTEGER;
                BEGIN
                    SELECT COUNT(*) INTO count_nulls
                    FROM rdo_mao_obra
                    WHERE admin_id IS NULL;
                    
                    IF count_nulls = 0 THEN
                        ALTER TABLE rdo_mao_obra ALTER COLUMN admin_id SET NOT NULL;
                    ELSE
                        RAISE WARNING '⚠️  % registros ainda com admin_id NULL', count_nulls;
                    END IF;
                END $$;
                
                -- 5. Adicionar foreign key
                ALTER TABLE rdo_mao_obra
                ADD CONSTRAINT fk_rdo_mao_obra_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                -- 6. Criar índice
                CREATE INDEX IF NOT EXISTS idx_rdo_mao_obra_admin_id 
                ON rdo_mao_obra(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            
            # Validar
            result = connection.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(admin_id) as com_admin_id,
                    COUNT(*) - COUNT(admin_id) as nulls
                FROM rdo_mao_obra
            """))
            
            row = result.fetchone()
            logger.info(f"✅ rdo_mao_obra.admin_id adicionado com sucesso")
            logger.info(f"   Total de registros: {row[0]}")
            logger.info(f"   Com admin_id: {row[1]}")
            if row[2] > 0:
                logger.warning(f"   ⚠️  Registros NULL: {row[2]}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir rdo_mao_obra: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = fix_rdo_mao_obra_admin_id()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)
