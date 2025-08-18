"""
Migrações automáticas do banco de dados
Executadas automaticamente na inicialização da aplicação
"""
import logging
from sqlalchemy import text
from models import db

logger = logging.getLogger(__name__)

def executar_migracoes():
    """
    Execute todas as migrações necessárias automaticamente
    """
    try:
        logger.info("🔄 Iniciando migrações automáticas do banco de dados...")
        
        # Migração 1: Adicionar coluna categoria na tabela proposta_templates
        migrar_categoria_proposta_templates()
        
        # Migração 2: Adicionar outras colunas faltantes se necessário
        migrar_colunas_faltantes_proposta_templates()
        
        logger.info("✅ Migrações automáticas concluídas com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro durante migrações automáticas: {e}")
        # Não interromper a aplicação, apenas logar o erro
        pass

def migrar_categoria_proposta_templates():
    """
    Adiciona a coluna categoria na tabela proposta_templates se não existir
    """
    try:
        # Verificar se a coluna já existe
        check_query = text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'proposta_templates' 
            AND column_name = 'categoria'
        """)
        
        result = db.session.execute(check_query).scalar()
        
        if result == 0:
            # Coluna não existe, criar
            logger.info("📝 Adicionando coluna 'categoria' na tabela proposta_templates...")
            
            migration_query = text("""
                ALTER TABLE proposta_templates 
                ADD COLUMN categoria character varying(50) NOT NULL DEFAULT 'Estrutura Metálica'
            """)
            
            db.session.execute(migration_query)
            db.session.commit()
            
            logger.info("✅ Coluna 'categoria' adicionada com sucesso!")
        else:
            logger.info("✅ Coluna 'categoria' já existe na tabela proposta_templates")
            
    except Exception as e:
        logger.error(f"❌ Erro ao migrar coluna categoria: {e}")
        db.session.rollback()

def migrar_colunas_faltantes_proposta_templates():
    """
    Adiciona outras colunas que podem estar faltantes na tabela proposta_templates
    """
    colunas_necessarias = [
        ('itens_inclusos', 'text'),
        ('itens_exclusos', 'text'), 
        ('condicoes', 'text')
    ]
    
    for nome_coluna, tipo_coluna in colunas_necessarias:
        try:
            # Verificar se a coluna já existe
            check_query = text(f"""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_templates' 
                AND column_name = '{nome_coluna}'
            """)
            
            result = db.session.execute(check_query).scalar()
            
            if result == 0:
                # Coluna não existe, criar
                logger.info(f"📝 Adicionando coluna '{nome_coluna}' na tabela proposta_templates...")
                
                migration_query = text(f"""
                    ALTER TABLE proposta_templates 
                    ADD COLUMN {nome_coluna} {tipo_coluna}
                """)
                
                db.session.execute(migration_query)
                db.session.commit()
                
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso!")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela proposta_templates")
                
        except Exception as e:
            logger.error(f"❌ Erro ao migrar coluna {nome_coluna}: {e}")
            db.session.rollback()

def verificar_estrutura_tabela():
    """
    Verifica e exibe a estrutura atual da tabela proposta_templates
    """
    try:
        query = text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'proposta_templates' 
            ORDER BY ordinal_position
        """)
        
        colunas = db.session.execute(query).fetchall()
        
        logger.info("📋 Estrutura atual da tabela proposta_templates:")
        for coluna in colunas:
            logger.info(f"  - {coluna.column_name} ({coluna.data_type})")
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar estrutura da tabela: {e}")