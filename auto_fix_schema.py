#!/usr/bin/env python3
"""
Correção Automática de Schema - Integrada ao Deploy
Executa durante inicialização do container Docker
"""

import os
import sys
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def corrigir_schema_automatico():
    """Correção automática do schema durante deploy"""
    
    # URL do banco de dados
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada!")
        return False
    
    try:
        # Conectar ao banco
        logger.info("🔗 Conectando ao banco de dados...")
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Verificar se tabela restaurante existe
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if 'restaurante' not in tables:
                logger.info("📋 Tabela restaurante não existe ainda - será criada pela migração")
                return True
            
            # Verificar colunas atuais
            logger.info("🔍 Verificando schema da tabela restaurante...")
            columns = inspector.get_columns('restaurante')
            column_names = [col['name'] for col in columns]
            
            # Colunas que devem existir
            required_columns = {
                'responsavel': 'VARCHAR(100)',
                'preco_almoco': 'DECIMAL(10,2) DEFAULT 0.00',
                'preco_jantar': 'DECIMAL(10,2) DEFAULT 0.00', 
                'preco_lanche': 'DECIMAL(10,2) DEFAULT 0.00',
                'admin_id': 'INTEGER'
            }
            
            # Identificar colunas faltantes
            missing_columns = []
            for col_name, col_type in required_columns.items():
                if col_name not in column_names:
                    missing_columns.append((col_name, col_type))
            
            # Adicionar colunas faltantes
            if missing_columns:
                logger.info(f"🔧 Adicionando {len(missing_columns)} colunas faltantes...")
                
                for col_name, col_type in missing_columns:
                    sql = f"ALTER TABLE restaurante ADD COLUMN {col_name} {col_type}"
                    logger.info(f"   ⚙️ {sql}")
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"   ✅ Coluna {col_name} adicionada")
            else:
                logger.info("✅ Todas as colunas necessárias já existem")
            
            # Remover coluna duplicada se existir
            if 'contato_responsavel' in column_names:
                logger.info("🗑️ Removendo coluna duplicada 'contato_responsavel'...")
                conn.execute(text("ALTER TABLE restaurante DROP COLUMN contato_responsavel"))
                conn.commit()
                logger.info("   ✅ Coluna duplicada removida")
            
            # Configurar admin_id para restaurantes existentes
            result = conn.execute(text("SELECT COUNT(*) FROM restaurante WHERE admin_id IS NULL OR admin_id = 0"))
            count = result.scalar()
            
            if count > 0:
                logger.info(f"🔧 Configurando admin_id para {count} restaurantes...")
                conn.execute(text("UPDATE restaurante SET admin_id = 1 WHERE admin_id IS NULL OR admin_id = 0"))
                conn.commit()
                logger.info(f"   ✅ {count} restaurantes atualizados")
            
            # Verificar resultado final
            total_result = conn.execute(text("SELECT COUNT(*) FROM restaurante"))
            total = total_result.scalar()
            logger.info(f"🏪 Total de restaurantes: {total}")
            
            logger.info("🎉 CORREÇÃO AUTOMÁTICA DO SCHEMA CONCLUÍDA!")
            return True
            
    except OperationalError as e:
        if "does not exist" in str(e):
            logger.info("📋 Tabela restaurante ainda não existe - será criada pela migração")
            return True
        else:
            logger.error(f"❌ Erro de conexão: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Erro na correção automática: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔧 CORREÇÃO AUTOMÁTICA DE SCHEMA - DEPLOY")
    logger.info("=" * 50)
    
    sucesso = corrigir_schema_automatico()
    
    if sucesso:
        logger.info("✅ CORREÇÃO AUTOMÁTICA EXECUTADA COM SUCESSO!")
        sys.exit(0)
    else:
        logger.info("⚠️ CORREÇÃO AUTOMÁTICA FALHOU (não crítico)")
        sys.exit(0)  # Não falhar o deploy por causa disso