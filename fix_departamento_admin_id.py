#!/usr/bin/env python3
"""
Script para adicionar admin_id na tabela departamento
Executa de forma independente e idempotente
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_departamento_admin_id():
    """Adiciona admin_id na tabela departamento"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada")
        return False
    
    logger.info("=" * 80)
    logger.info("🔧 CORREÇÃO: departamento.admin_id")
    logger.info("=" * 80)
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Verificar se coluna já existe
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'departamento' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ departamento.admin_id JÁ EXISTE - skip")
                return True
            
            logger.warning("⚠️  departamento.admin_id NÃO EXISTE - corrigindo...")
            
            # Executar correção
            connection.execute(text("""
                BEGIN;
                
                -- 1. Adicionar coluna
                ALTER TABLE departamento ADD COLUMN admin_id INTEGER;
                
                -- 2. Backfill usando funcionario.departamento_id
                UPDATE departamento d
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.departamento_id = d.id
                  AND d.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- 3. Usar admin_id mais comum para NULLs restantes
                UPDATE departamento
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
                ALTER TABLE departamento ALTER COLUMN admin_id SET NOT NULL;
                
                -- 5. Adicionar foreign key
                ALTER TABLE departamento
                ADD CONSTRAINT fk_departamento_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                -- 6. Criar índice
                CREATE INDEX IF NOT EXISTS idx_departamento_admin_id 
                ON departamento(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            
            # Validar
            result = connection.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(admin_id) as com_admin_id
                FROM departamento
            """))
            
            row = result.fetchone()
            logger.info(f"✅ departamento.admin_id adicionado com sucesso")
            logger.info(f"   Total de registros: {row[0]}")
            logger.info(f"   Com admin_id: {row[1]}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir departamento: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = fix_departamento_admin_id()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)
