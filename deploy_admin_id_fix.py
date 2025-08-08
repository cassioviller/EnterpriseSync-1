#!/usr/bin/env python3
"""
Script de Deploy: Correção admin_id em Produção
Adiciona coluna admin_id à tabela outro_custo se ela não existir
Para uso direto em produção
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_admin_id_fix():
    """
    Aplica correção da coluna admin_id em produção
    """
    try:
        # Verificar DATABASE_URL
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("❌ DATABASE_URL não encontrada nas variáveis de ambiente")
            return False
            
        logger.info(f"🔗 Conectando ao banco: {database_url[:30]}...")
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Verificar se admin_id existe
            logger.info("🔍 Verificando existência da coluna admin_id...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'admin_id'
            """))
            
            if result.fetchone():
                logger.info("✅ Coluna admin_id já existe - nenhuma ação necessária")
                return True
            
            logger.info("❌ Coluna admin_id não encontrada")
            logger.info("🔧 Adicionando coluna admin_id...")
            
            # Adicionar coluna
            conn.execute(text("ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER"))
            logger.info("✅ Coluna admin_id adicionada")
            
            # Atualizar registros existentes
            logger.info("🔄 Atualizando registros existentes...")
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
            
            updated_count = result.rowcount
            logger.info(f"✅ {updated_count} registros atualizados com admin_id")
            
            # Commit das mudanças
            conn.commit()
            logger.info("💾 Mudanças salvas no banco")
            
            # Verificação final
            logger.info("🔍 Verificação final...")
            test_result = conn.execute(text("SELECT admin_id FROM outro_custo LIMIT 1"))
            test_value = test_result.scalar()
            
            if test_value:
                logger.info(f"✅ Teste bem-sucedido: admin_id = {test_value}")
                
                # Contar registros com admin_id
                count_result = conn.execute(text("SELECT COUNT(*) FROM outro_custo WHERE admin_id IS NOT NULL"))
                count = count_result.scalar()
                logger.info(f"📊 {count} registros com admin_id preenchido")
                
                return True
            else:
                logger.error("❌ Falha no teste - admin_id não foi preenchido")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erro durante correção: {e}")
        return False

def verify_deployment():
    """
    Verifica se o deploy foi bem-sucedido
    """
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            return False
            
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Verificar estrutura final
            result = conn.execute(text("""
                SELECT column_name, ordinal_position
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            logger.info(f"📋 Estrutura final da tabela outro_custo ({len(columns)} colunas):")
            
            admin_id_found = False
            for col in columns:
                marker = "👉" if col[0] == 'admin_id' else "  "
                logger.info(f"{marker} {col[1]:2d}. {col[0]}")
                if col[0] == 'admin_id':
                    admin_id_found = True
            
            if admin_id_found and len(columns) >= 12:
                logger.info("✅ Estrutura da tabela correta")
                return True
            else:
                logger.error("❌ Estrutura da tabela incompleta")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erro na verificação: {e}")
        return False

def main():
    """
    Função principal do deploy
    """
    logger.info("🚀 INICIANDO DEPLOY - Correção admin_id")
    logger.info("=" * 50)
    
    # Aplicar correção
    if not apply_admin_id_fix():
        logger.error("❌ Falha na aplicação da correção")
        sys.exit(1)
    
    # Verificar deploy
    if not verify_deployment():
        logger.error("❌ Falha na verificação do deploy")
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info("🎯 DEPLOY CONCLUÍDO COM SUCESSO")
    logger.info("✅ Sistema SIGE pronto para uso em produção")
    
    return True

if __name__ == "__main__":
    main()