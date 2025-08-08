#!/usr/bin/env python3
"""
Migração: Adicionar coluna admin_id à tabela outro_custo
Para execução automática durante o deploy
"""

import os
import sys
from sqlalchemy import create_engine, text
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_and_add_admin_id():
    """
    Verifica se a coluna admin_id existe na tabela outro_custo
    Se não existir, adiciona a coluna e atualiza os registros
    """
    try:
        # Conectar ao banco
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL não encontrada")
            return False
            
        engine = create_engine(str(database_url))
        
        with engine.connect() as conn:
            # Verificar se a coluna admin_id existe
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'admin_id'
            """))
            
            if result.fetchone():
                logger.info("✅ Coluna admin_id já existe na tabela outro_custo")
                return True
            
            logger.info("🔧 Coluna admin_id não existe - adicionando...")
            
            # Adicionar coluna admin_id
            conn.execute(text("ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER"))
            logger.info("✅ Coluna admin_id adicionada")
            
            # Atualizar registros existentes com admin_id baseado no funcionário
            result = conn.execute(text("""
                UPDATE outro_custo 
                SET admin_id = (
                    SELECT admin_id 
                    FROM funcionario 
                    WHERE funcionario.id = outro_custo.funcionario_id
                    LIMIT 1
                )
                WHERE admin_id IS NULL
            """))
            
            updated_rows = result.rowcount
            logger.info(f"✅ {updated_rows} registros atualizados com admin_id")
            
            # Confirmar transação
            conn.commit()
            
            # Verificar resultado
            test_result = conn.execute(text("SELECT admin_id FROM outro_custo LIMIT 1"))
            test_value = test_result.scalar()
            logger.info(f"✅ Teste pós-migração: admin_id = {test_value}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro durante migração: {e}")
        return False

def verify_table_structure():
    """
    Verifica e exibe a estrutura final da tabela outro_custo
    """
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL não encontrada")
            return False
        engine = create_engine(str(database_url))
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, ordinal_position
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            logger.info(f"📊 Estrutura da tabela outro_custo ({len(columns)} colunas):")
            
            for col in columns:
                marker = "👉" if col[0] == 'admin_id' else "  "
                logger.info(f"{marker} {col[2]:2d}. {col[0]} ({col[1]})")
                
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar estrutura: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Iniciando migração: add_admin_id_to_outro_custo")
    
    # Executar migração
    if check_and_add_admin_id():
        logger.info("✅ Migração concluída com sucesso")
        
        # Verificar estrutura final
        verify_table_structure()
        
        sys.exit(0)
    else:
        logger.error("❌ Migração falhou")
        sys.exit(1)