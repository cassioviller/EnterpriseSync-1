#!/usr/bin/env python3
"""
Script de Deploy - Correção Crítica de Produção
Fix para coluna obra.cliente ausente em produção
"""

import sys
import os
import logging
from sqlalchemy import text, inspect
from sqlalchemy.exc import ProgrammingError

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_and_add_missing_columns():
    """Verifica e adiciona colunas ausentes na tabela obra"""
    
    try:
        # Importar app e db
        sys.path.append('.')
        from app import app, db
        
        with app.app_context():
            logger.info("🔍 Verificando estrutura da tabela obra...")
            
            # Obter inspetor do banco
            inspector = inspect(db.engine)
            
            # Verificar colunas existentes
            existing_columns = [col['name'] for col in inspector.get_columns('obra')]
            logger.info(f"✅ Colunas existentes: {existing_columns}")
            
            # Colunas que devem existir
            required_columns = {
                'cliente': 'VARCHAR(200)',
                'cliente_nome': 'VARCHAR(100)',
                'cliente_email': 'VARCHAR(120)',
                'cliente_telefone': 'VARCHAR(20)',
                'token_cliente': 'VARCHAR(255)',
                'portal_ativo': 'BOOLEAN DEFAULT TRUE',
                'ultima_visualizacao_cliente': 'TIMESTAMP',
                'proposta_origem_id': 'INTEGER REFERENCES propostas_comerciais(id)'
            }
            
            # Verificar e adicionar colunas ausentes
            missing_columns = []
            for col_name, col_definition in required_columns.items():
                if col_name not in existing_columns:
                    missing_columns.append((col_name, col_definition))
                    logger.warning(f"⚠️ Coluna ausente: {col_name}")
            
            if not missing_columns:
                logger.info("✅ Todas as colunas já existem!")
                return True
            
            # Adicionar colunas ausentes
            logger.info(f"🔧 Adicionando {len(missing_columns)} colunas ausentes...")
            
            for col_name, col_definition in missing_columns:
                try:
                    sql = f"ALTER TABLE obra ADD COLUMN {col_name} {col_definition};"
                    logger.info(f"📝 Executando: {sql}")
                    db.session.execute(text(sql))
                    db.session.commit()
                    logger.info(f"✅ Coluna {col_name} adicionada com sucesso!")
                    
                except ProgrammingError as e:
                    if "already exists" in str(e):
                        logger.info(f"ℹ️ Coluna {col_name} já existe (ignorando)")
                        db.session.rollback()
                    else:
                        logger.error(f"❌ Erro ao adicionar coluna {col_name}: {e}")
                        db.session.rollback()
                        return False
                except Exception as e:
                    logger.error(f"❌ Erro inesperado ao adicionar coluna {col_name}: {e}")
                    db.session.rollback()
                    return False
            
            # Verificar se todas as colunas foram adicionadas
            updated_columns = [col['name'] for col in inspector.get_columns('obra')]
            logger.info(f"✅ Colunas após migração: {updated_columns}")
            
            # Verificar se há tokens únicos ausentes
            logger.info("🔧 Verificando tokens únicos...")
            try:
                obras_sem_token = db.session.execute(text(
                    "SELECT id, nome FROM obra WHERE token_cliente IS NULL OR token_cliente = ''"
                )).fetchall()
                
                if obras_sem_token:
                    logger.info(f"🔧 Gerando tokens para {len(obras_sem_token)} obras...")
                    import uuid
                    
                    for obra in obras_sem_token:
                        token = str(uuid.uuid4())
                        db.session.execute(text(
                            "UPDATE obra SET token_cliente = :token WHERE id = :id"
                        ), {'token': token, 'id': obra.id})
                        logger.info(f"  ✅ Token gerado para obra {obra.nome}")
                    
                    db.session.commit()
                    logger.info("✅ Tokens únicos gerados com sucesso!")
                else:
                    logger.info("✅ Todas as obras já possuem tokens únicos!")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar tokens: {e}")
                db.session.rollback()
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro crítico durante migração: {e}")
        return False

def verify_fix():
    """Verifica se o fix foi aplicado corretamente"""
    
    try:
        sys.path.append('.')
        from app import app, db
        from models import Obra
        
        with app.app_context():
            logger.info("🔍 Verificando fix aplicado...")
            
            # Testar query que estava falhando
            try:
                obras = Obra.query.filter_by(admin_id=2).limit(1).all()
                logger.info("✅ Query de obras funcionando corretamente!")
                return True
                
            except Exception as e:
                logger.error(f"❌ Query ainda falhando: {e}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erro na verificação: {e}")
        return False

def main():
    """Função principal do script de deploy"""
    
    logger.info("🚀 INICIANDO DEPLOY - CORREÇÃO CRÍTICA DE PRODUÇÃO")
    logger.info("=" * 60)
    
    # Verificar ambiente
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não configurado!")
        sys.exit(1)
    
    logger.info(f"🔗 Conectando ao banco: {database_url[:50]}...")
    
    # Executar correções
    if not check_and_add_missing_columns():
        logger.error("❌ Falha na adição de colunas!")
        sys.exit(1)
    
    # Verificar se funcionou
    if not verify_fix():
        logger.error("❌ Verificação falhou!")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("🎉 DEPLOY CONCLUÍDO COM SUCESSO!")
    logger.info("✅ Problema da coluna obra.cliente resolvido")
    logger.info("✅ Sistema pronto para produção")

if __name__ == '__main__':
    main()