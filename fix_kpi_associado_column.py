#!/usr/bin/env python3
"""
CORREÇÃO DE EMERGÊNCIA: Erro UndefinedColumn outro_custo.kpi_associado

Problema identificado:
- A coluna kpi_associado existe na tabela outro_custo
- Mas há um erro SQLAlchemy UndefinedColumn ao tentar acessar essa coluna
- Possível causa: cache de metadados ou inconsistência de schema

Soluções aplicadas:
1. Verificar e recriar a estrutura da tabela se necessário
2. Atualizar metadados do SQLAlchemy
3. Corrigir queries que possam estar causando o problema
"""

import os
import sys
import logging
from datetime import datetime, date

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_kpi_associado_issue():
    """Corrige o problema da coluna kpi_associado"""
    try:
        # Importar dependências
        from app import app, db
        from sqlalchemy import text, inspect
        from models import OutroCusto
        
        with app.app_context():
            logger.info("🔧 Iniciando correção do erro kpi_associado...")
            
            # 1. Verificar se a coluna existe
            inspector = inspect(db.engine)
            columns = inspector.get_columns('outro_custo')
            column_names = [col['name'] for col in columns]
            
            logger.info(f"📋 Colunas existentes em outro_custo: {column_names}")
            
            if 'kpi_associado' not in column_names:
                logger.info("❌ Coluna kpi_associado não encontrada. Adicionando...")
                
                # Adicionar a coluna
                db.session.execute(text("""
                    ALTER TABLE outro_custo 
                    ADD COLUMN kpi_associado VARCHAR(30) DEFAULT 'outros_custos'
                """))
                
                # Atualizar registros existentes
                db.session.execute(text("""
                    UPDATE outro_custo 
                    SET kpi_associado = 'outros_custos' 
                    WHERE kpi_associado IS NULL
                """))
                
                db.session.commit()
                logger.info("✅ Coluna kpi_associado adicionada com sucesso")
            else:
                logger.info("✅ Coluna kpi_associado já existe")
            
            # 2. Forçar atualização dos metadados do SQLAlchemy
            logger.info("🔄 Atualizando metadados do SQLAlchemy...")
            db.metadata.clear()
            db.metadata.reflect(db.engine)
            
            # 3. Testar uma query simples
            logger.info("🧪 Testando query com kpi_associado...")
            test_query = db.session.query(OutroCusto.id, OutroCusto.kpi_associado).limit(1)
            result = test_query.first()
            logger.info(f"✅ Query teste bem-sucedida: {result}")
            
            # 4. Verificar registros sem kpi_associado e corrigir
            registros_sem_kpi = db.session.query(OutroCusto).filter(
                OutroCusto.kpi_associado.is_(None)
            ).count()
            
            if registros_sem_kpi > 0:
                logger.info(f"🔧 Corrigindo {registros_sem_kpi} registros sem kpi_associado...")
                db.session.query(OutroCusto).filter(
                    OutroCusto.kpi_associado.is_(None)
                ).update({'kpi_associado': 'outros_custos'})
                db.session.commit()
                logger.info("✅ Registros corrigidos")
            
            logger.info("🎉 Correção concluída com sucesso!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro durante a correção: {str(e)}")
        if 'db' in locals():
            db.session.rollback()
        return False

def clear_sqlalchemy_cache():
    """Limpa o cache do SQLAlchemy"""
    try:
        from app import app, db
        
        with app.app_context():
            logger.info("🧹 Limpando cache do SQLAlchemy...")
            
            # Limpar registry de classes
            db.metadata.clear()
            
            # Fechar todas as conexões
            db.session.close()
            db.engine.dispose()
            
            logger.info("✅ Cache limpo com sucesso")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao limpar cache: {str(e)}")
        return False

if __name__ == '__main__':
    logger.info("🚀 Iniciando correção de emergência...")
    
    # Executar correções
    if clear_sqlalchemy_cache():
        if fix_kpi_associado_issue():
            logger.info("✅ Todas as correções aplicadas com sucesso!")
            sys.exit(0)
        else:
            logger.error("❌ Falha na correção principal")
            sys.exit(1)
    else:
        logger.error("❌ Falha na limpeza do cache")
        sys.exit(1)