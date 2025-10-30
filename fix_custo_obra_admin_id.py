#!/usr/bin/env python3
"""
Script para adicionar admin_id na tabela custo_obra
Executa de forma independente e idempotente
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_custo_obra_admin_id():
    """Adiciona admin_id na tabela custo_obra"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada")
        return False
    
    logger.info("=" * 80)
    logger.info("🔧 CORREÇÃO: custo_obra.admin_id")
    logger.info("=" * 80)
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Verificar se coluna já existe
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'custo_obra' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ custo_obra.admin_id JÁ EXISTE - skip")
                return True
            
            logger.warning("⚠️  custo_obra.admin_id NÃO EXISTE - corrigindo...")
            
            # Executar correção
            connection.execute(text("""
                BEGIN;
                
                -- 1. Adicionar coluna
                ALTER TABLE custo_obra ADD COLUMN admin_id INTEGER;
                
                -- 2. Backfill usando obra.admin_id
                UPDATE custo_obra co
                SET admin_id = o.admin_id
                FROM obra o
                WHERE co.obra_id = o.id
                  AND co.admin_id IS NULL
                  AND o.admin_id IS NOT NULL;
                
                -- 3. Usar admin_id mais comum para NULLs restantes
                UPDATE custo_obra
                SET admin_id = (
                    SELECT admin_id 
                    FROM obra 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                )
                WHERE admin_id IS NULL;
                
                -- 4. Aplicar NOT NULL
                ALTER TABLE custo_obra ALTER COLUMN admin_id SET NOT NULL;
                
                -- 5. Adicionar foreign key
                ALTER TABLE custo_obra
                ADD CONSTRAINT fk_custo_obra_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                -- 6. Criar índice
                CREATE INDEX IF NOT EXISTS idx_custo_obra_admin_id 
                ON custo_obra(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            
            # Validar
            result = connection.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(admin_id) as com_admin_id
                FROM custo_obra
            """))
            
            row = result.fetchone()
            logger.info(f"✅ custo_obra.admin_id adicionado com sucesso")
            logger.info(f"   Total de registros: {row[0]}")
            logger.info(f"   Com admin_id: {row[1]}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir custo_obra: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = fix_custo_obra_admin_id()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)
