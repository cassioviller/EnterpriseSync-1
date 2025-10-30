#!/usr/bin/env python3
"""
Script para adicionar admin_id na tabela horario_trabalho
Executa de forma independente e idempotente
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_horario_trabalho_admin_id():
    """Adiciona admin_id na tabela horario_trabalho"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada")
        return False
    
    logger.info("=" * 80)
    logger.info("🔧 CORREÇÃO: horario_trabalho.admin_id")
    logger.info("=" * 80)
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Verificar se coluna já existe
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'horario_trabalho' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ horario_trabalho.admin_id JÁ EXISTE - skip")
                return True
            
            logger.warning("⚠️  horario_trabalho.admin_id NÃO EXISTE - corrigindo...")
            
            # Executar correção
            connection.execute(text("""
                BEGIN;
                
                -- 1. Adicionar coluna
                ALTER TABLE horario_trabalho ADD COLUMN admin_id INTEGER;
                
                -- 2. Backfill usando funcionario.horario_id
                UPDATE horario_trabalho ht
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.horario_id = ht.id
                  AND ht.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- 3. Usar admin_id mais comum para NULLs restantes
                UPDATE horario_trabalho
                SET admin_id = (
                    SELECT admin_id 
                    FROM funcionario 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                )
                WHERE admin_id IS NULL;
                
                -- 4. Aplicar NOT NULL
                ALTER TABLE horario_trabalho ALTER COLUMN admin_id SET NOT NULL;
                
                -- 5. Adicionar foreign key
                ALTER TABLE horario_trabalho
                ADD CONSTRAINT fk_horario_trabalho_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                -- 6. Criar índice
                CREATE INDEX IF NOT EXISTS idx_horario_trabalho_admin_id 
                ON horario_trabalho(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            
            # Validar
            result = connection.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(admin_id) as com_admin_id
                FROM horario_trabalho
            """))
            
            row = result.fetchone()
            logger.info(f"✅ horario_trabalho.admin_id adicionado com sucesso")
            logger.info(f"   Total de registros: {row[0]}")
            logger.info(f"   Com admin_id: {row[1]}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir horario_trabalho: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = fix_horario_trabalho_admin_id()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)
