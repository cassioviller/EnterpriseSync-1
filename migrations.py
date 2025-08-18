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
        
        # Verificar se a tabela existe, se não existir, criar completa
        garantir_tabela_proposta_templates_existe()
        
        # Migração 1: Adicionar coluna categoria na tabela proposta_templates
        migrar_categoria_proposta_templates()
        
        # Migração 2: Adicionar outras colunas faltantes se necessário
        migrar_colunas_faltantes_proposta_templates()
        
        logger.info("✅ Migrações automáticas concluídas com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro durante migrações automáticas: {e}")
        # Não interromper a aplicação, apenas logar o erro
        pass

def garantir_tabela_proposta_templates_existe():
    """
    Verifica se a tabela proposta_templates existe, se não existir, cria completa
    """
    try:
        # Verificar se a tabela existe
        table_check = text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'proposta_templates'
        """)
        
        result = db.session.execute(table_check).scalar()
        
        if result == 0:
            logger.info("📝 Tabela proposta_templates não existe, criando...")
            
            # Criar tabela completa
            create_table_query = text("""
                CREATE TABLE proposta_templates (
                    id serial PRIMARY KEY,
                    nome character varying(100) NOT NULL,
                    descricao text,
                    categoria character varying(50) NOT NULL DEFAULT 'Estrutura Metálica',
                    itens_padrao json DEFAULT '[]'::json,
                    prazo_entrega_dias integer DEFAULT 90,
                    validade_dias integer DEFAULT 7,
                    percentual_nota_fiscal numeric(5,2) DEFAULT 13.5,
                    itens_inclusos text,
                    itens_exclusos text,
                    condicoes text,
                    condicoes_pagamento text DEFAULT '10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem',
                    garantias text DEFAULT 'A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.',
                    ativo boolean DEFAULT true,
                    publico boolean DEFAULT false,
                    uso_contador integer DEFAULT 0,
                    admin_id integer,
                    criado_por integer,
                    criado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            db.session.execute(create_table_query)
            db.session.commit()
            
            logger.info("✅ Tabela proposta_templates criada com sucesso!")
        else:
            logger.info("✅ Tabela proposta_templates já existe")
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar/criar tabela proposta_templates: {e}")
        db.session.rollback()

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
    Adiciona todas as colunas que podem estar faltantes na tabela proposta_templates
    """
    colunas_necessarias = [
        ('itens_padrao', 'json DEFAULT \'[]\'::json'),
        ('prazo_entrega_dias', 'integer DEFAULT 90'),
        ('validade_dias', 'integer DEFAULT 7'), 
        ('percentual_nota_fiscal', 'numeric(5,2) DEFAULT 13.5'),
        ('itens_inclusos', 'text'),
        ('itens_exclusos', 'text'), 
        ('condicoes', 'text'),
        ('condicoes_pagamento', 'text DEFAULT \'10% de entrada na assinatura do contrato\n10% após projeto aprovado\n45% compra dos perfis\n25% no início da montagem in loco\n10% após a conclusão da montagem\''),
        ('garantias', 'text DEFAULT \'A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.\''),
        ('ativo', 'boolean DEFAULT true'),
        ('publico', 'boolean DEFAULT false'),
        ('uso_contador', 'integer DEFAULT 0'),
        ('admin_id', 'integer'),
        ('criado_por', 'integer'),
        ('criado_em', 'timestamp without time zone DEFAULT CURRENT_TIMESTAMP'),
        ('atualizado_em', 'timestamp without time zone DEFAULT CURRENT_TIMESTAMP')
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
            
    # Adicionar foreign keys se necessário
    try:
        add_foreign_keys_if_needed()
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar foreign keys: {e}")

def add_foreign_keys_if_needed():
    """
    Adiciona foreign keys que podem estar faltando
    """
    try:
        # Verificar se FK admin_id existe
        fk_check = text("""
            SELECT COUNT(*) FROM information_schema.table_constraints 
            WHERE constraint_type = 'FOREIGN KEY' 
            AND table_name = 'proposta_templates' 
            AND constraint_name LIKE '%admin_id%'
        """)
        
        result = db.session.execute(fk_check).scalar()
        
        if result == 0:
            logger.info("📝 Adicionando foreign key para admin_id...")
            
            # Primeiro verificar se a tabela usuario existe
            table_check = text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'usuario'")
            if db.session.execute(table_check).scalar() > 0:
                fk_query = text("""
                    ALTER TABLE proposta_templates 
                    ADD CONSTRAINT fk_proposta_templates_admin_id 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                """)
                
                db.session.execute(fk_query)
                db.session.commit()
                logger.info("✅ Foreign key admin_id adicionada!")
            
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível adicionar foreign keys: {e}")
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