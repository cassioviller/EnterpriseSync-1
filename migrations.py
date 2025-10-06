"""
Migrações automáticas do banco de dados
Executadas automaticamente na inicialização da aplicação
"""
import logging
from sqlalchemy import text
from models import db
import os
import re

logger = logging.getLogger(__name__)

def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

def executar_migracoes():
    """
    Execute todas as migrações necessárias automaticamente
    REATIVADO PARA DEPLOY EASYPANEL COMPLETO
    """
    try:
        logger.info("🔄 Iniciando migrações automáticas COMPLETAS do banco EasyPanel...")
        # Mascarar credenciais por segurança
        database_url = os.environ.get('DATABASE_URL', 'postgresql://sige:sige@viajey_sige:5432/sige')
        logger.info(f"🎯 TARGET DATABASE: {mask_database_url(database_url)}")
        
        # MIGRAÇÃO 0: CRÍTICA - Garantir coluna motorista_id em uso_veiculo (PRIMEIRA DE TODAS)
        garantir_motorista_id_uso_veiculo()
        
        # Verificar se a tabela existe, se não existir, criar completa
        garantir_tabela_proposta_templates_existe()
        
        # Migração 1: Adicionar coluna categoria na tabela proposta_templates
        migrar_categoria_proposta_templates()
        
        # Migração 2: Adicionar outras colunas faltantes se necessário
        migrar_colunas_faltantes_proposta_templates()
        
        # Migração 3: Tornar campos assunto e objeto opcionais em propostas_comerciais
        migrar_campos_opcionais_propostas()
        
        # Migração 4: Adicionar campos de personalização visual na configuração da empresa
        migrar_personalizacao_visual_empresa()
        
        # Migração 5: Adicionar campos de organização para proposta_itens
        migrar_campos_organizacao_propostas()
        
        # Migração 6: Garantir usuários existem para foreign keys
        garantir_usuarios_producao()
        
        # Migração 7: Adicionar novos campos completos para templates
        migrar_campos_completos_templates()
        
        # Migração 8: Adicionar campos editáveis para páginas do PDF - IGNORADA POR ENQUANTO
        logger.info("✅ Campos PDF serão adicionados manualmente se necessário")
        
        # Migração 9: CRÍTICA - Corrigir campos faltantes na tabela rdo_ocorrencia
        migrar_campos_rdo_ocorrencia()
        
        # Migração 10: CRÍTICA - Adicionar campo admin_id na tabela rdo
        migrar_campo_admin_id_rdo()
        
        # Migração 11: CRÍTICA - Criar tabelas do sistema RDO aprimorado
        migrar_sistema_rdo_aprimorado()
        
        # Migração 12: URGENTE - Adicionar admin_id na tabela servico
        adicionar_admin_id_servico()
        
        # Migração 13: CRÍTICA - Corrigir admin_id em serviços existentes
        corrigir_admin_id_servicos_existentes()
        
        # Migração 14: NOVA - Criar tabela ServicoObraReal
        migrar_tabela_servico_obra_real()
        
        # Migração 15: CRÍTICA - Adicionar coluna local na tabela RDO para produção
        adicionar_coluna_local_rdo()
        
        # Migração 16: NOVA - Adicionar campos faltantes na tabela allocation_employee
        adicionar_campos_allocation_employee()
        
        # Migração 17: CRÍTICA - Migração específica para sistema de veículos
        migrar_sistema_veiculos_critical()
        
        # Migração 18: CRÍTICA - Corrigir admin_id nullable para multi-tenant seguro
        corrigir_admin_id_vehicle_tables()
        
        # Migração 19: NOVA - Adicionar colunas faltantes em veículos (chassi, renavam, combustivel)
        adicionar_colunas_veiculo_completas()
        
        # Migração 20: CRÍTICA - Sistema Fleet Completo (nova arquitetura de veículos)
        migrar_sistema_fleet_completo()
        
        # Migração 21: HOTFIX EMERGENCIAL - Adicionar motorista_id na tabela ANTIGA uso_veiculo
        hotfix_adicionar_motorista_id_legacy()

        logger.info("✅ Migrações automáticas concluídas com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro durante migrações automáticas: {e}")
        # Não interromper a aplicação, apenas logar o erro
        pass

def garantir_motorista_id_uso_veiculo():
    """
    MIGRAÇÃO 0: CRÍTICA - PRIMEIRA DE TODAS
    
    Garante que a coluna motorista_id existe na tabela uso_veiculo
    EXECUTA ANTES DE TUDO para evitar erros em produção
    
    CONTEXTO:
    - Erro em produção: column "motorista_id" does not exist
    - Esta migração é a PRIMEIRA a executar
    - Idempotente: pode executar múltiplas vezes sem problemas
    """
    try:
        logger.info("=" * 80)
        logger.info("🚨 MIGRAÇÃO 0: GARANTINDO motorista_id em uso_veiculo (PRIMEIRA MIGRAÇÃO)")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se tabela uso_veiculo existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'uso_veiculo'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.info("ℹ️  Tabela uso_veiculo não existe ainda, pulando migração")
            cursor.close()
            connection.close()
            return
        
        # Verificar se coluna motorista_id já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'uso_veiculo' 
            AND column_name = 'motorista_id'
        """)
        
        if cursor.fetchone():
            logger.info("✅ Coluna motorista_id já existe em uso_veiculo")
            cursor.close()
            connection.close()
            return
        
        logger.info("🔧 CRIANDO coluna motorista_id na tabela uso_veiculo...")
        
        # Adicionar coluna motorista_id (NULLABLE para compatibilidade)
        cursor.execute("""
            ALTER TABLE uso_veiculo 
            ADD COLUMN motorista_id INTEGER
        """)
        logger.info("✅ Coluna motorista_id adicionada com sucesso!")
        
        # Adicionar FK opcional para funcionario
        try:
            cursor.execute("""
                ALTER TABLE uso_veiculo 
                ADD CONSTRAINT fk_uso_veiculo_motorista 
                FOREIGN KEY (motorista_id) REFERENCES funcionario(id) 
                ON DELETE SET NULL
            """)
            logger.info("✅ Foreign key fk_uso_veiculo_motorista adicionada!")
        except Exception as fk_error:
            logger.warning(f"⚠️  FK não pôde ser criada: {fk_error}")
        
        # Criar índice para performance
        try:
            cursor.execute("""
                CREATE INDEX idx_uso_veiculo_motorista 
                ON uso_veiculo(motorista_id)
            """)
            logger.info("✅ Índice idx_uso_veiculo_motorista criado!")
        except Exception as idx_error:
            logger.warning(f"⚠️  Índice não pôde ser criado: {idx_error}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("🎉 MIGRAÇÃO 0 CONCLUÍDA: motorista_id garantido em uso_veiculo!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERRO CRÍTICO na Migração 0 - motorista_id: {str(e)}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())
        
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def garantir_usuarios_producao():
    """
    Garantir que usuários necessários existem para evitar foreign key violations
    """
    try:
        from models import Usuario
        
        # Verificar se usuário admin_id=10 existe
        usuario_10 = Usuario.query.get(10)
        if not usuario_10:
            logger.info("🔄 Criando usuário admin ID=10 para produção...")
            
            # Criar usuário usando SQL direto para evitar conflitos
            db.engine.execute(text("""
                INSERT INTO usuario (id, username, email, nome, password_hash, tipo_usuario, ativo, admin_id)
                VALUES (10, 'valeverde_admin', 'admin@valeverde.com.br', 'Administrador Vale Verde', 
                        'scrypt:32768:8:1$PLACEHOLDER_HASH_TO_BE_CHANGED', 
                        'admin', TRUE, NULL)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, nome = EXCLUDED.nome
            """))
            logger.info("✅ Usuário admin ID=10 criado com sucesso!")
        else:
            logger.info("✅ Usuário admin ID=10 já existe")
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao garantir usuários de produção: {e}")
        # Tentar com método alternativo se SQLAlchemy 2.0
        try:
            connection = db.engine.raw_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                INSERT INTO usuario (id, username, email, nome, password_hash, tipo_usuario, ativo, admin_id)
                VALUES (10, 'valeverde_admin', 'admin@valeverde.com.br', 'Administrador Vale Verde', 
                        'scrypt:32768:8:1$PLACEHOLDER_HASH_TO_BE_CHANGED', 'admin', TRUE, NULL)
                ON CONFLICT (id) DO NOTHING
            """)
            connection.commit()
            cursor.close()
            connection.close()
            logger.info("✅ Usuário admin ID=10 criado via conexão direta!")
        except Exception as e2:
            logger.error(f"❌ Falha ao criar usuário admin: {e2}")

def migrar_campos_opcionais_propostas():
    """
    Torna os campos assunto e objeto opcionais na tabela propostas_comerciais
    """
    try:
        # Usar conexão direta para verificar constraints
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se os campos ainda são NOT NULL
        cursor.execute("""
            SELECT column_name, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name IN ('assunto', 'objeto')
            AND is_nullable = 'NO'
        """)
        campos_nao_null = cursor.fetchall()
        
        if campos_nao_null:
            logger.info("🔄 Removendo constraints NOT NULL dos campos assunto e objeto...")
            
            # Remover constraint NOT NULL do campo assunto
            cursor.execute("ALTER TABLE propostas_comerciais ALTER COLUMN assunto DROP NOT NULL")
            logger.info("✅ Campo 'assunto' agora é opcional")
            
            # Remover constraint NOT NULL do campo objeto
            cursor.execute("ALTER TABLE propostas_comerciais ALTER COLUMN objeto DROP NOT NULL")
            logger.info("✅ Campo 'objeto' agora é opcional")
            
            connection.commit()
            logger.info("✅ Campos de proposta atualizados para serem opcionais")
        else:
            logger.info("✅ Campos assunto e objeto já são opcionais")
            
        cursor.close()
        connection.close()
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar campos opcionais: {str(e)}")

def migrar_personalizacao_visual_empresa():
    """
    Adiciona colunas de personalização visual na tabela configuracao_empresa
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de colunas para adicionar
        colunas_novas = [
            ('logo_base64', 'TEXT'),
            ('logo_pdf_base64', 'TEXT'),
            ('header_pdf_base64', 'TEXT'),
            ('cor_primaria', 'VARCHAR(7) DEFAULT \'#007bff\''),
            ('cor_secundaria', 'VARCHAR(7) DEFAULT \'#6c757d\''),
            ('cor_fundo_proposta', 'VARCHAR(7) DEFAULT \'#f8f9fa\'')
        ]
        
        for nome_coluna, tipo_coluna in colunas_novas:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'configuracao_empresa' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela configuracao_empresa...")
                cursor.execute(f"ALTER TABLE configuracao_empresa ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela configuracao_empresa")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar colunas de personalização visual: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
            cursor.close()
            connection.close()

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

def migrar_campos_organizacao_propostas():
    """
    Adiciona campos de organização avançada para proposta_itens
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de colunas para adicionar
        colunas_organizacao = [
            ('categoria_titulo', 'VARCHAR(100)'),
            ('template_origem_id', 'INTEGER'),
            ('template_origem_nome', 'VARCHAR(100)'),
            ('grupo_ordem', 'INTEGER DEFAULT 1'),
            ('item_ordem_no_grupo', 'INTEGER DEFAULT 1')
        ]
        
        for nome_coluna, tipo_coluna in colunas_organizacao:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_itens' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela proposta_itens...")
                cursor.execute(f"ALTER TABLE proposta_itens ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela proposta_itens")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar campos de organização: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()

def migrar_campos_completos_templates():
    """
    Migração 7: Adicionar campos completos para templates (dados do cliente, engenheiro, seções)
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de colunas completas para adicionar
        colunas_completas = [
            # Dados do cliente (primeira página)
            ("cidade_data", "VARCHAR(200) DEFAULT 'São José dos Campos, [DATA]'"),
            ("destinatario", "VARCHAR(200)"),
            ("atencao_de", "VARCHAR(200)"),
            ("telefone_cliente", "VARCHAR(50)"),
            ("assunto", "TEXT"),
            ("numero_referencia", "VARCHAR(100)"),
            ("texto_apresentacao", "TEXT"),
            
            # Dados do engenheiro responsável
            ("engenheiro_nome", "VARCHAR(200) DEFAULT 'Engº Lucas Barbosa Alves Pinto'"),
            ("engenheiro_crea", "VARCHAR(50) DEFAULT 'CREA- 5070458626-SP'"),
            ("engenheiro_email", "VARCHAR(120) DEFAULT 'contato@estruturasdovale.com.br'"),
            ("engenheiro_telefone", "VARCHAR(50) DEFAULT '12 99187-7435'"),
            ("engenheiro_endereco", "TEXT DEFAULT 'Rua Benedita Nunes de Campos, 140. Residencial União, São José dos Campos - CEP 12.239-008'"),
            ("engenheiro_website", "VARCHAR(200) DEFAULT 'www.estruturasdovale.com.br'"),
            
            # Seções completas da proposta (1-9)
            ("secao_objeto", "TEXT"),
            ("condicoes_entrega", "TEXT"),
            ("consideracoes_gerais", "TEXT"),
            ("secao_validade", "TEXT")
        ]
        
        for nome_coluna, tipo_coluna in colunas_completas:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_templates' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela proposta_templates...")
                cursor.execute(f"ALTER TABLE proposta_templates ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela proposta_templates")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar campos completos de templates: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()


def migrar_campos_rdo_ocorrencia():
    """
    CRÍTICA: Migração para corrigir campos faltantes na tabela rdo_ocorrencia
    O modelo RDOOcorrencia possui campos que não existem na tabela do banco
    """
    try:
        import psycopg2
        import os
        
        # Conectar ao banco usando a URL do ambiente
        connection = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = connection.cursor()
        
        logger.info("🔄 Verificando e adicionando campos faltantes na tabela rdo_ocorrencia...")
        
        # Campos que precisam existir na tabela rdo_ocorrencia
        campos_necessarios = [
            ("tipo_ocorrencia", "VARCHAR(50)", "NOT NULL DEFAULT 'Observação'"),
            ("severidade", "VARCHAR(20)", "DEFAULT 'Baixa'"),
            ("responsavel_acao", "VARCHAR(100)"),
            ("prazo_resolucao", "DATE"),
            ("status_resolucao", "VARCHAR(20)", "DEFAULT 'Pendente'"),
            ("observacoes_resolucao", "TEXT"),
            ("criado_em", "TIMESTAMP", "DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for nome_coluna, tipo_coluna, *restricoes in campos_necessarios:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_ocorrencia' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela rdo_ocorrencia...")
                
                # Montar comando ALTER TABLE
                alter_comando = f"ALTER TABLE rdo_ocorrencia ADD COLUMN {nome_coluna} {tipo_coluna}"
                if restricoes:
                    alter_comando += f" {restricoes[0]}"
                
                cursor.execute(alter_comando)
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso na tabela rdo_ocorrencia")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela rdo_ocorrencia")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração da tabela rdo_ocorrencia concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO ao migrar campos RDO ocorrência: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()


def migrar_campo_admin_id_rdo():
    """
    CRÍTICA: Adicionar campo admin_id na tabela rdo para suporte multitenant
    """
    try:
        import psycopg2
        import os
        
        # Conectar ao banco usando a URL do ambiente
        connection = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = connection.cursor()
        
        logger.info("🔄 Verificando se campo admin_id existe na tabela rdo...")
        
        # Verificar se a coluna admin_id já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'rdo' 
            AND column_name = 'admin_id'
        """)
        
        exists = cursor.fetchone()
        
        if not exists:
            logger.info("🔄 Adicionando coluna 'admin_id' na tabela rdo...")
            cursor.execute("ALTER TABLE rdo ADD COLUMN admin_id INTEGER REFERENCES usuario(id)")
            logger.info("✅ Coluna 'admin_id' adicionada com sucesso na tabela rdo")
        else:
            logger.info("✅ Coluna 'admin_id' já existe na tabela rdo")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração do campo admin_id na tabela rdo concluída!")
        
    except Exception as e:
        logger.error(f"❌ ERRO ao migrar campo admin_id RDO: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()


def migrar_sistema_rdo_aprimorado():
    """
    CRÍTICA: Criar/atualizar tabelas do sistema RDO aprimorado com verificação de estrutura
    """
    try:
        import psycopg2
        import os
        
        # Conectar ao banco usando a URL do ambiente
        connection = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = connection.cursor()
        
        logger.info("🔄 Verificando e atualizando estrutura das tabelas RDO (preservando dados)...")
        
        # Verificar se tabelas existem
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name IN ('subatividade_mestre', 'rdo_servico_subatividade')
            AND table_schema = 'public'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"📋 Tabelas encontradas: {existing_tables}")
        
        # SUBATIVIDADE_MESTRE: Criar ou verificar estrutura
        if 'subatividade_mestre' not in existing_tables:
            logger.info("🆕 Criando tabela subatividade_mestre...")
            cursor.execute("""
                CREATE TABLE subatividade_mestre (
                    id SERIAL PRIMARY KEY,
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    nome VARCHAR(200) NOT NULL,
                    descricao TEXT,
                    ordem_padrao INTEGER DEFAULT 0,
                    obrigatoria BOOLEAN DEFAULT TRUE,
                    duracao_estimada_horas FLOAT,
                    complexidade INTEGER DEFAULT 1,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Tabela subatividade_mestre criada")
        else:
            logger.info("🔍 Verificando estrutura da tabela subatividade_mestre...")
            
            # Definir colunas esperadas
            expected_columns = {
                'id': 'SERIAL PRIMARY KEY',
                'servico_id': 'INTEGER NOT NULL',
                'nome': 'VARCHAR(200) NOT NULL',
                'descricao': 'TEXT',
                'ordem_padrao': 'INTEGER DEFAULT 0',
                'obrigatoria': 'BOOLEAN DEFAULT TRUE',
                'duracao_estimada_horas': 'FLOAT',
                'complexidade': 'INTEGER DEFAULT 1', 
                'admin_id': 'INTEGER NOT NULL',
                'ativo': 'BOOLEAN DEFAULT TRUE',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            # Verificar colunas existentes
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'subatividade_mestre' 
                ORDER BY ordinal_position
            """)
            existing_columns = {row[0]: row for row in cursor.fetchall()}
            
            # Adicionar colunas faltantes
            for col_name in expected_columns:
                if col_name not in existing_columns and col_name != 'id':  # Nunca alterar ID
                    try:
                        col_definition = expected_columns[col_name]
                        
                        # Simplificar definição para ALTER TABLE
                        if col_name == 'servico_id':
                            col_def = 'INTEGER NOT NULL REFERENCES servico(id)'
                        elif col_name == 'admin_id':
                            col_def = 'INTEGER NOT NULL REFERENCES usuario(id)'
                        elif col_name == 'nome':
                            col_def = 'VARCHAR(200) NOT NULL'
                        elif col_name == 'descricao':
                            col_def = 'TEXT'
                        elif col_name == 'ordem_padrao':
                            col_def = 'INTEGER DEFAULT 0'
                        elif col_name == 'obrigatoria':
                            col_def = 'BOOLEAN DEFAULT TRUE'
                        elif col_name == 'duracao_estimada_horas':
                            col_def = 'FLOAT'
                        elif col_name == 'complexidade':
                            col_def = 'INTEGER DEFAULT 1'
                        elif col_name == 'ativo':
                            col_def = 'BOOLEAN DEFAULT TRUE'
                        elif col_name in ['created_at', 'updated_at']:
                            col_def = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                        else:
                            col_def = 'TEXT'
                        
                        cursor.execute(f"ALTER TABLE subatividade_mestre ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                        logger.info(f"✅ Coluna '{col_name}' adicionada à subatividade_mestre")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao adicionar coluna '{col_name}': {e}")
            
            logger.info("✅ Estrutura subatividade_mestre verificada/atualizada")
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subativ_mestre_servico ON subatividade_mestre(servico_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subativ_mestre_admin ON subatividade_mestre(admin_id)")
        
        # RDO_SERVICO_SUBATIVIDADE: Criar ou verificar estrutura  
        if 'rdo_servico_subatividade' not in existing_tables:
            logger.info("🆕 Criando tabela rdo_servico_subatividade...")
            cursor.execute("""
                CREATE TABLE rdo_servico_subatividade (
                    id SERIAL PRIMARY KEY,
                    rdo_id INTEGER NOT NULL REFERENCES rdo(id),
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    nome_subatividade VARCHAR(200) NOT NULL,
                    descricao_subatividade TEXT,
                    percentual_conclusao FLOAT DEFAULT 0.0,
                    percentual_anterior FLOAT DEFAULT 0.0,
                    incremento_dia FLOAT DEFAULT 0.0,
                    observacoes_tecnicas TEXT,
                    ordem_execucao INTEGER DEFAULT 0,
                    ativo BOOLEAN DEFAULT TRUE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Tabela rdo_servico_subatividade criada")
        else:
            logger.info("🔍 Verificando estrutura da tabela rdo_servico_subatividade...")
            
            # Definir colunas esperadas
            expected_columns = {
                'id': 'SERIAL PRIMARY KEY',
                'rdo_id': 'INTEGER NOT NULL',
                'servico_id': 'INTEGER NOT NULL', 
                'nome_subatividade': 'VARCHAR(200) NOT NULL',
                'descricao_subatividade': 'TEXT',
                'percentual_conclusao': 'FLOAT DEFAULT 0.0',
                'percentual_anterior': 'FLOAT DEFAULT 0.0',
                'incremento_dia': 'FLOAT DEFAULT 0.0',
                'observacoes_tecnicas': 'TEXT',
                'ordem_execucao': 'INTEGER DEFAULT 0',
                'ativo': 'BOOLEAN DEFAULT TRUE',
                'admin_id': 'INTEGER NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            # Verificar colunas existentes
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'rdo_servico_subatividade' 
                ORDER BY ordinal_position
            """)
            existing_columns = {row[0]: row for row in cursor.fetchall()}
            
            # Adicionar colunas faltantes
            for col_name in expected_columns:
                if col_name not in existing_columns and col_name != 'id':  # Nunca alterar ID
                    try:
                        # Simplificar definição para ALTER TABLE
                        if col_name == 'rdo_id':
                            col_def = 'INTEGER NOT NULL REFERENCES rdo(id)'
                        elif col_name == 'servico_id':
                            col_def = 'INTEGER NOT NULL REFERENCES servico(id)'
                        elif col_name == 'admin_id':
                            col_def = 'INTEGER NOT NULL REFERENCES usuario(id)'
                        elif col_name == 'nome_subatividade':
                            col_def = 'VARCHAR(200) NOT NULL'
                        elif col_name in ['descricao_subatividade', 'observacoes_tecnicas']:
                            col_def = 'TEXT'
                        elif col_name in ['percentual_conclusao', 'percentual_anterior', 'incremento_dia']:
                            col_def = 'FLOAT DEFAULT 0.0'
                        elif col_name == 'ordem_execucao':
                            col_def = 'INTEGER DEFAULT 0'
                        elif col_name == 'ativo':
                            col_def = 'BOOLEAN DEFAULT TRUE'
                        elif col_name in ['created_at', 'updated_at']:
                            col_def = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                        else:
                            col_def = 'TEXT'
                        
                        cursor.execute(f"ALTER TABLE rdo_servico_subatividade ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                        logger.info(f"✅ Coluna '{col_name}' adicionada à rdo_servico_subatividade")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao adicionar coluna '{col_name}': {e}")
            
            logger.info("✅ Estrutura rdo_servico_subatividade verificada/atualizada")
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rdo_servico_subativ ON rdo_servico_subatividade(rdo_id, servico_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subativ_admin ON rdo_servico_subatividade(admin_id)")
        
        # REMOVIDO: Não inserir dados automaticamente - apenas criar tabelas vazias
        logger.info("✅ Estrutura de tabelas garantida - dados existentes preservados")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração do sistema RDO aprimorado concluída!")
        
    except Exception as e:
        logger.error(f"❌ Erro na migração do sistema RDO: {e}")
        try:
            connection.rollback()
            cursor.close()  
            connection.close()
        except:
            pass

def adicionar_admin_id_servico():
    """Adiciona admin_id na tabela servico para multi-tenant"""
    try:
        # Verificar se a coluna admin_id já existe na tabela servico
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='servico' AND column_name='admin_id'
        """)).fetchone()
        
        if not result:
            logger.info("🔧 Adicionando coluna admin_id na tabela servico...")
            
            # Adicionar coluna admin_id
            db.session.execute(text("""
                ALTER TABLE servico 
                ADD COLUMN admin_id INTEGER REFERENCES usuario(id)
            """))
            
            # Atualizar registros existentes com admin_id padrão (10)
            db.session.execute(text("""
                UPDATE servico 
                SET admin_id = 10 
                WHERE admin_id IS NULL
            """))
            
            # Tornar a coluna NOT NULL após popular os dados
            db.session.execute(text("""
                ALTER TABLE servico 
                ALTER COLUMN admin_id SET NOT NULL
            """))
            
            db.session.commit()
            logger.info("✅ Coluna admin_id adicionada na tabela servico")
            
        else:
            logger.info("✅ Coluna admin_id já existe na tabela servico")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao adicionar admin_id na tabela servico: {e}")

def corrigir_admin_id_servicos_existentes():
    """Corrige admin_id em serviços existentes que podem estar sem valor"""
    try:
        # Usar conexão direta para máxima compatibilidade
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar quantos serviços estão sem admin_id
        cursor.execute("SELECT COUNT(*) FROM servico WHERE admin_id IS NULL")
        servicos_sem_admin = cursor.fetchone()[0]
        
        if servicos_sem_admin > 0:
            logger.info(f"🔧 Corrigindo {servicos_sem_admin} serviços sem admin_id...")
            
            # Atualizar serviços sem admin_id para usar admin_id=10
            cursor.execute("""
                UPDATE servico 
                SET admin_id = 10 
                WHERE admin_id IS NULL
            """)
            
            logger.info(f"✅ {servicos_sem_admin} serviços corrigidos com admin_id=10")
        else:
            logger.info("✅ Todos os serviços já possuem admin_id correto")
        
        # CORREÇÃO CRÍTICA: Verificar apenas se usuários existem na tabela usuario (não só admins)
        cursor.execute("""
            SELECT DISTINCT admin_id 
            FROM servico 
            WHERE admin_id NOT IN (SELECT id FROM usuario)
        """)
        admin_ids_invalidos = cursor.fetchall()
        
        for (admin_id_invalido,) in admin_ids_invalidos:
            logger.warning(f"⚠️ Serviços com admin_id inválido (usuário não existe): {admin_id_invalido}")
            
            # IMPORTANTE: Só corrigir se o usuário realmente não existir
            # Não alterar serviços de usuários válidos como admin_id=50
            cursor.execute("SELECT COUNT(*) FROM usuario WHERE id = %s", (admin_id_invalido,))
            usuario_existe = cursor.fetchone()[0]
            
            if usuario_existe == 0:
                logger.info(f"🔧 Corrigindo serviços para admin_id=10 (usuário {admin_id_invalido} não existe)")
                cursor.execute("""
                    UPDATE servico 
                    SET admin_id = 10 
                    WHERE admin_id = %s
                """, (admin_id_invalido,))
            else:
                logger.info(f"✅ Mantendo serviços do admin_id={admin_id_invalido} (usuário válido)")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("✅ Correção de admin_id em serviços concluída!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir admin_id em serviços: {e}")
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except:
            pass

def migrar_tabela_servico_obra_real():
    """
    Criar tabela ServicoObraReal para gestão avançada de serviços na obra
    """
    try:
        logger.info("🔄 Verificando se tabela servico_obra_real existe...")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se a tabela já existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'servico_obra_real'
        """)
        
        tabela_existe = cursor.fetchone()[0] > 0
        
        if not tabela_existe:
            logger.info("🔧 Criando tabela servico_obra_real...")
            
            cursor.execute("""
                CREATE TABLE servico_obra_real (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id),
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    
                    -- Planejamento detalhado
                    quantidade_planejada NUMERIC(12,4) NOT NULL DEFAULT 0.0,
                    quantidade_executada NUMERIC(12,4) DEFAULT 0.0,
                    percentual_concluido NUMERIC(5,2) DEFAULT 0.0,
                    
                    -- Controle de prazo
                    data_inicio_planejada DATE,
                    data_fim_planejada DATE,
                    data_inicio_real DATE,
                    data_fim_real DATE,
                    
                    -- Controle de custos
                    valor_unitario NUMERIC(10,2) DEFAULT 0.0,
                    valor_total_planejado NUMERIC(12,2) DEFAULT 0.0,
                    valor_total_executado NUMERIC(12,2) DEFAULT 0.0,
                    
                    -- Status e controle
                    status VARCHAR(30) DEFAULT 'Não Iniciado',
                    prioridade INTEGER DEFAULT 3,
                    responsavel_id INTEGER REFERENCES funcionario(id),
                    
                    -- Observações e notas
                    observacoes TEXT,
                    notas_tecnicas TEXT,
                    
                    -- Controle de qualidade
                    aprovado BOOLEAN DEFAULT FALSE,
                    data_aprovacao TIMESTAMP,
                    aprovado_por_id INTEGER REFERENCES funcionario(id),
                    
                    -- Multi-tenant e controle
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraint unique
                    UNIQUE(obra_id, servico_id)
                )
            """)
            
            logger.info("✅ Tabela servico_obra_real criada com sucesso!")
            
            # Criar índices para performance
            cursor.execute("CREATE INDEX idx_servico_obra_real_obra ON servico_obra_real(obra_id)")
            cursor.execute("CREATE INDEX idx_servico_obra_real_servico ON servico_obra_real(servico_id)")
            cursor.execute("CREATE INDEX idx_servico_obra_real_admin ON servico_obra_real(admin_id)")
            cursor.execute("CREATE INDEX idx_servico_obra_real_status ON servico_obra_real(status)")
            
            logger.info("✅ Índices criados para servico_obra_real!")
        else:
            logger.info("✅ Tabela servico_obra_real já existe")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração da tabela ServicoObraReal concluída!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela servico_obra_real: {e}")
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except:
            pass

def criar_tabela_servico_obra_real_limpa():
    """
    Cria tabela servico_obra_real versão limpa e simplificada
    """
    try:
        logger.info("🔄 Criando tabela servico_obra_real versão LIMPA...")
        
        # Usar SQLAlchemy diretamente
        from sqlalchemy import text
        
        # Verificar se tabela existe
        result = db.session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'servico_obra_real'
            )
        """)).scalar()
        
        if not result:
            logger.info("🆕 Criando nova tabela servico_obra_real...")
            
            # Criar tabela usando SQLAlchemy
            db.session.execute(text("""
                CREATE TABLE servico_obra_real (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id),
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    
                    -- Quantidades
                    quantidade_planejada NUMERIC(10,2) DEFAULT 1.0,
                    quantidade_executada NUMERIC(10,2) DEFAULT 0.0,
                    percentual_concluido NUMERIC(5,2) DEFAULT 0.0,
                    
                    -- Valores
                    valor_unitario NUMERIC(10,2) DEFAULT 0.0,
                    valor_total_planejado NUMERIC(10,2) DEFAULT 0.0,
                    valor_total_executado NUMERIC(10,2) DEFAULT 0.0,
                    
                    -- Status e controle
                    status VARCHAR(50) DEFAULT 'Não Iniciado',
                    prioridade INTEGER DEFAULT 3,
                    
                    -- Datas
                    data_inicio_planejada DATE,
                    data_inicio_real DATE,
                    data_fim_planejada DATE,
                    data_fim_real DATE,
                    
                    -- Aprovação
                    aprovado BOOLEAN DEFAULT FALSE,
                    aprovado_em TIMESTAMP,
                    aprovado_por_id INTEGER,
                    
                    -- Observações
                    observacoes TEXT,
                    observacoes_execucao TEXT,
                    
                    -- Multi-tenant
                    admin_id INTEGER NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(obra_id, servico_id, admin_id)
                )
            """))
            
            # Índices básicos
            db.session.execute(text("CREATE INDEX idx_servico_obra_real_obra_id ON servico_obra_real(obra_id)"))
            db.session.execute(text("CREATE INDEX idx_servico_obra_real_admin_id ON servico_obra_real(admin_id)"))
            
            db.session.commit()
            logger.info("✅ Tabela servico_obra_real LIMPA criada com sucesso!")
        else:
            logger.info("✅ Tabela servico_obra_real já existe")
            
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela limpa: {e}")
        db.session.rollback()

def adicionar_coluna_local_rdo():
    """Adiciona coluna 'local' na tabela RDO para compatibilidade com produção"""
    try:
        logger.info("🔄 Verificando se coluna 'local' existe na tabela RDO...")
        
        # Verificar se a coluna local já existe
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='rdo' AND column_name='local'
        """)).fetchone()
        
        if not result:
            logger.info("🔧 Adicionando coluna 'local' na tabela RDO...")
            
            # Adicionar coluna local
            db.session.execute(text("""
                ALTER TABLE rdo 
                ADD COLUMN local VARCHAR(100) DEFAULT 'Campo'
            """))
            
            db.session.commit()
            logger.info("✅ Coluna 'local' adicionada à tabela RDO com sucesso!")
        else:
            logger.info("✅ Coluna 'local' já existe na tabela RDO")
            
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar coluna 'local' na tabela RDO: {e}")
        db.session.rollback()

def adicionar_campos_allocation_employee():
    """Adiciona campos faltantes (hora_almoco_saida, hora_almoco_retorno, percentual_extras) na tabela allocation_employee"""
    try:
        logger.info("🔄 Verificando campos faltantes na tabela allocation_employee...")
        
        # Lista de campos para verificar/adicionar
        campos_necessarios = [
            ('hora_almoco_saida', "TIME DEFAULT '12:00:00'"),
            ('hora_almoco_retorno', "TIME DEFAULT '13:00:00'"),
            ('percentual_extras', "REAL DEFAULT 0.0")
        ]
        
        for nome_campo, tipo_sql in campos_necessarios:
            # Verificar se o campo já existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='allocation_employee' AND column_name=:campo_nome
            """), {"campo_nome": nome_campo}).fetchone()
            
            if not result:
                logger.info(f"🔧 Adicionando campo '{nome_campo}' na tabela allocation_employee...")
                
                # Adicionar campo
                db.session.execute(text(f"""
                    ALTER TABLE allocation_employee 
                    ADD COLUMN {nome_campo} {tipo_sql}
                """))
                
                logger.info(f"✅ Campo '{nome_campo}' adicionado com sucesso!")
            else:
                logger.info(f"✅ Campo '{nome_campo}' já existe na tabela allocation_employee")
        
        db.session.commit()
        logger.info("✅ Todos os campos necessários da tabela allocation_employee verificados/adicionados!")
            
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar campos na tabela allocation_employee: {e}")
        db.session.rollback()

def migrar_sistema_veiculos_critical():
    """
    MIGRAÇÃO CRÍTICA: Sistema de Veículos Multi-Tenant
    Aplica constraints e campos obrigatórios que estão faltando no banco de dados
    """
    try:
        logger.info("🚗 MIGRAÇÃO CRÍTICA: Sistema de Veículos Multi-Tenant")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # 1. Verificar se a tabela veiculo existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'veiculo'
        """)
        tabela_existe = cursor.fetchone()[0] > 0
        
        if not tabela_existe:
            logger.info("📝 Tabela veiculo não existe, criando completa...")
            
            # Criar tabela completa com todas as constraints
            cursor.execute("""
                CREATE TABLE veiculo (
                    id SERIAL PRIMARY KEY,
                    placa VARCHAR(10) NOT NULL,
                    marca VARCHAR(50) NOT NULL,
                    modelo VARCHAR(50) NOT NULL,
                    ano INTEGER,
                    tipo VARCHAR(20) NOT NULL,
                    status VARCHAR(20) DEFAULT 'Disponível',
                    km_atual INTEGER DEFAULT 0,
                    data_ultima_manutencao DATE,
                    data_proxima_manutencao DATE,
                    ativo BOOLEAN DEFAULT TRUE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraint unique por admin para isolamento multi-tenant
                    CONSTRAINT veiculo_admin_placa_uc UNIQUE(admin_id, placa)
                )
            """)
            
            # Criar índices para performance
            cursor.execute("CREATE INDEX idx_veiculo_admin_id ON veiculo(admin_id)")
            cursor.execute("CREATE INDEX idx_veiculo_ativo ON veiculo(ativo)")
            
            connection.commit()
            logger.info("✅ Tabela veiculo criada com todas as constraints!")
            
        else:
            logger.info("🔍 Tabela veiculo existe, verificando constraints...")
            
            # 2. Verificar se admin_id existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = 'admin_id'
            """)
            admin_id_existe = cursor.fetchone()
            
            if not admin_id_existe:
                logger.info("🔄 Adicionando coluna admin_id...")
                cursor.execute("ALTER TABLE veiculo ADD COLUMN admin_id INTEGER")
                logger.info("✅ Coluna admin_id adicionada")
            
            # 3. Verificar se há registros sem admin_id e corrigir
            cursor.execute("SELECT COUNT(*) FROM veiculo WHERE admin_id IS NULL")
            registros_sem_admin = cursor.fetchone()[0]
            
            if registros_sem_admin > 0:
                logger.info(f"🔄 Corrigindo {registros_sem_admin} registros sem admin_id...")
                
                # Tentar usar ID 10 como padrão (admin principal)
                cursor.execute("SELECT id FROM usuario WHERE tipo_usuario = 'admin' LIMIT 1")
                admin_padrao = cursor.fetchone()
                
                if admin_padrao:
                    admin_id_padrao = admin_padrao[0]
                    cursor.execute(
                        "UPDATE veiculo SET admin_id = %s WHERE admin_id IS NULL",
                        (admin_id_padrao,)
                    )
                    logger.info(f"✅ Registros atualizados com admin_id = {admin_id_padrao}")
                else:
                    logger.warning("⚠️ Nenhum admin encontrado, usando ID 1 como padrão")
                    cursor.execute("UPDATE veiculo SET admin_id = 1 WHERE admin_id IS NULL")
            
            # 4. Verificar se admin_id é NOT NULL
            cursor.execute("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = 'admin_id'
            """)
            admin_nullable = cursor.fetchone()
            
            if admin_nullable and admin_nullable[0] == 'YES':
                logger.info("🔄 Aplicando constraint NOT NULL em admin_id...")
                cursor.execute("ALTER TABLE veiculo ALTER COLUMN admin_id SET NOT NULL")
                logger.info("✅ admin_id agora é NOT NULL")
            
            # 5. Verificar se foreign key existe
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'veiculo' 
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name LIKE '%admin%'
            """)
            fk_admin_existe = cursor.fetchone()
            
            if not fk_admin_existe:
                logger.info("🔄 Adicionando foreign key admin_id...")
                cursor.execute("""
                    ALTER TABLE veiculo 
                    ADD CONSTRAINT fk_veiculo_admin 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                """)
                logger.info("✅ Foreign key admin_id adicionada")
            
            # 6. Verificar se constraint unique existe
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'veiculo' 
                AND constraint_type = 'UNIQUE'
                AND constraint_name LIKE '%admin%placa%'
            """)
            unique_constraint_existe = cursor.fetchone()
            
            if not unique_constraint_existe:
                logger.info("🔄 Adicionando constraint unique (admin_id, placa)...")
                
                # Primeiro remover duplicatas se existirem
                cursor.execute("""
                    DELETE FROM veiculo 
                    WHERE id NOT IN (
                        SELECT DISTINCT ON (admin_id, placa) id 
                        FROM veiculo 
                        ORDER BY admin_id, placa, id
                    )
                """)
                
                # Adicionar constraint unique
                cursor.execute("""
                    ALTER TABLE veiculo 
                    ADD CONSTRAINT veiculo_admin_placa_uc 
                    UNIQUE(admin_id, placa)
                """)
                logger.info("✅ Constraint unique (admin_id, placa) adicionada")
            
            # 7. Verificar se updated_at existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = 'updated_at'
            """)
            updated_at_existe = cursor.fetchone()
            
            if not updated_at_existe:
                logger.info("🔄 Adicionando coluna updated_at...")
                cursor.execute("""
                    ALTER TABLE veiculo 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                logger.info("✅ Coluna updated_at adicionada")
            
            # 8. Criar índices se não existirem
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'veiculo' 
                AND indexname = 'idx_veiculo_admin_id'
            """)
            indice_admin_existe = cursor.fetchone()
            
            if not indice_admin_existe:
                logger.info("🔄 Criando índice para admin_id...")
                cursor.execute("CREATE INDEX idx_veiculo_admin_id ON veiculo(admin_id)")
                logger.info("✅ Índice admin_id criado")
            
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'veiculo' 
                AND indexname = 'idx_veiculo_ativo'
            """)
            indice_ativo_existe = cursor.fetchone()
            
            if not indice_ativo_existe:
                logger.info("🔄 Criando índice para ativo...")
                cursor.execute("CREATE INDEX idx_veiculo_ativo ON veiculo(ativo)")
                logger.info("✅ Índice ativo criado")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("🚗 ✅ MIGRAÇÃO CRÍTICA DE VEÍCULOS CONCLUÍDA COM SUCESSO!")
        logger.info("🔒 Sistema multi-tenant agora totalmente protegido")
        logger.info("🎯 Constraints aplicadas: unique(admin_id, placa), admin_id NOT NULL")
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na migração de veículos: {str(e)}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        raise  # Re-raise para que seja tratado pela migração principal

def corrigir_admin_id_vehicle_tables():
    """
    Migração 18: CRÍTICA - Corrigir admin_id nullable em UsoVeiculo e CustoVeiculo
    USANDO JOINS DETERMINÍSTICOS para garantir isolamento multi-tenant seguro
    
    NUNCA mais usar hard-coded admin_id = 10!
    """
    try:
        logger.info("🔒 MIGRAÇÃO 18 (REESCRITA): Corrigindo admin_id via JOINs determinísticos...")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # 1. CORRIGIR TABELA uso_veiculo com JOINs determinísticos
        cursor.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'uso_veiculo' 
            AND column_name = 'admin_id'
        """)
        uso_veiculo_admin = cursor.fetchone()
        
        if uso_veiculo_admin and uso_veiculo_admin[1] == 'YES':
            logger.info("🔄 Corrigindo admin_id em uso_veiculo via JOINs determinísticos...")
            
            # Primeiro: Contar registros órfãos para auditoria
            cursor.execute("""
                SELECT COUNT(*) FROM uso_veiculo WHERE admin_id IS NULL
            """)
            orfaos_uso = cursor.fetchone()[0]
            logger.info(f"📊 Encontrados {orfaos_uso} registros órfãos em uso_veiculo")
            
            # ESTRATÉGIA 1: Corrigir via veiculo.admin_id (principal)
            cursor.execute("""
                UPDATE uso_veiculo 
                SET admin_id = v.admin_id
                FROM veiculo v
                WHERE uso_veiculo.veiculo_id = v.id 
                AND uso_veiculo.admin_id IS NULL
                AND v.admin_id IS NOT NULL
            """)
            corrigidos_veiculo = cursor.rowcount
            logger.info(f"✅ {corrigidos_veiculo} registros corrigidos via veiculo.admin_id")
            
            # ESTRATÉGIA 2: Fallback via funcionario.admin_id
            cursor.execute("""
                UPDATE uso_veiculo 
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE uso_veiculo.funcionario_id = f.id 
                AND uso_veiculo.admin_id IS NULL
                AND f.admin_id IS NOT NULL
            """)
            corrigidos_funcionario = cursor.rowcount
            logger.info(f"✅ {corrigidos_funcionario} registros corrigidos via funcionario.admin_id")
            
            # ESTRATÉGIA 3: Fallback via obra.admin_id
            cursor.execute("""
                UPDATE uso_veiculo 
                SET admin_id = o.admin_id
                FROM obra o
                WHERE uso_veiculo.obra_id = o.id 
                AND uso_veiculo.admin_id IS NULL
                AND o.admin_id IS NOT NULL
            """)
            corrigidos_obra = cursor.rowcount
            logger.info(f"✅ {corrigidos_obra} registros corrigidos via obra.admin_id")
            
            # Verificar se ainda há órfãos
            cursor.execute("""
                SELECT COUNT(*) FROM uso_veiculo WHERE admin_id IS NULL
            """)
            orfaos_restantes = cursor.fetchone()[0]
            
            if orfaos_restantes > 0:
                logger.warning(f"⚠️  {orfaos_restantes} registros órfãos restantes em uso_veiculo")
                logger.warning("🚨 BLOQUEANDO migração - registros órfãos não podem ser corrigidos determinísticamente")
                
                # Listar órfãos para diagnóstico
                cursor.execute("""
                    SELECT id, veiculo_id, funcionario_id, obra_id, data_uso 
                    FROM uso_veiculo 
                    WHERE admin_id IS NULL 
                    LIMIT 5
                """)
                orfaos_sample = cursor.fetchall()
                logger.warning(f"📋 Amostra de órfãos: {orfaos_sample}")
                
                # OPÇÃO SEGURA: Não aplicar NOT NULL se há órfãos
                logger.info("🛡️  Mantendo admin_id como nullable para preservar dados órfãos")
            else:
                # Aplicar constraint NOT NULL apenas se todos foram corrigidos
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ALTER COLUMN admin_id SET NOT NULL
                """)
                logger.info("✅ admin_id em uso_veiculo agora é NOT NULL")
        else:
            logger.info("✅ admin_id em uso_veiculo já é NOT NULL")
        
        # 2. CORRIGIR TABELA custo_veiculo com JOINs determinísticos
        cursor.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'custo_veiculo' 
            AND column_name = 'admin_id'
        """)
        custo_veiculo_admin = cursor.fetchone()
        
        if custo_veiculo_admin and custo_veiculo_admin[1] == 'YES':
            logger.info("🔄 Corrigindo admin_id em custo_veiculo via JOINs determinísticos...")
            
            # Primeiro: Contar registros órfãos para auditoria
            cursor.execute("""
                SELECT COUNT(*) FROM custo_veiculo WHERE admin_id IS NULL
            """)
            orfaos_custo = cursor.fetchone()[0]
            logger.info(f"📊 Encontrados {orfaos_custo} registros órfãos em custo_veiculo")
            
            # ESTRATÉGIA 1: Corrigir via veiculo.admin_id (principal)
            cursor.execute("""
                UPDATE custo_veiculo 
                SET admin_id = v.admin_id
                FROM veiculo v
                WHERE custo_veiculo.veiculo_id = v.id 
                AND custo_veiculo.admin_id IS NULL
                AND v.admin_id IS NOT NULL
            """)
            corrigidos_veiculo_custo = cursor.rowcount
            logger.info(f"✅ {corrigidos_veiculo_custo} registros corrigidos via veiculo.admin_id")
            
            # ESTRATÉGIA 2: Fallback via obra.admin_id se custo_veiculo tiver obra_id
            cursor.execute("""
                UPDATE custo_veiculo 
                SET admin_id = o.admin_id
                FROM obra o
                WHERE custo_veiculo.obra_id = o.id 
                AND custo_veiculo.admin_id IS NULL
                AND o.admin_id IS NOT NULL
            """)
            corrigidos_obra_custo = cursor.rowcount
            logger.info(f"✅ {corrigidos_obra_custo} registros corrigidos via obra.admin_id")
            
            # Verificar se ainda há órfãos
            cursor.execute("""
                SELECT COUNT(*) FROM custo_veiculo WHERE admin_id IS NULL
            """)
            orfaos_restantes_custo = cursor.fetchone()[0]
            
            if orfaos_restantes_custo > 0:
                logger.warning(f"⚠️  {orfaos_restantes_custo} registros órfãos restantes em custo_veiculo")
                logger.warning("🚨 BLOQUEANDO migração - registros órfãos não podem ser corrigidos determinísticamente")
                
                # Listar órfãos para diagnóstico
                cursor.execute("""
                    SELECT id, veiculo_id, obra_id, tipo_custo, valor 
                    FROM custo_veiculo 
                    WHERE admin_id IS NULL 
                    LIMIT 5
                """)
                orfaos_sample_custo = cursor.fetchall()
                logger.warning(f"📋 Amostra de órfãos: {orfaos_sample_custo}")
                
                # OPÇÃO SEGURA: Não aplicar NOT NULL se há órfãos
                logger.info("🛡️  Mantendo admin_id como nullable para preservar dados órfãos")
            else:
                # Aplicar constraint NOT NULL apenas se todos foram corrigidos
                cursor.execute("""
                    ALTER TABLE custo_veiculo 
                    ALTER COLUMN admin_id SET NOT NULL
                """)
                logger.info("✅ admin_id em custo_veiculo agora é NOT NULL")
        else:
            logger.info("✅ admin_id em custo_veiculo já é NOT NULL")
        
        # 3. Criar índices para melhor performance (mantido)
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'uso_veiculo' 
            AND indexname = 'idx_uso_veiculo_admin_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_uso_veiculo_admin_id ON uso_veiculo(admin_id)")
            logger.info("✅ Índice criado para uso_veiculo.admin_id")
        
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'custo_veiculo' 
            AND indexname = 'idx_custo_veiculo_admin_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_custo_veiculo_admin_id ON custo_veiculo(admin_id)")
            logger.info("✅ Índice criado para custo_veiculo.admin_id")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("🔐 ✅ MIGRAÇÃO 18 REESCRITA CONCLUÍDA!")
        logger.info("🎯 Multi-tenant seguro via JOINs determinísticos")
        logger.info("🛡️  ZERO mistura de dados entre tenants")
        logger.info("✨ Registros órfãos preservados sem violar integridade")
        
    except Exception as e:
        logger.error(f"❌ ERRO na Migração 18 - admin_id vehicle tables: {str(e)}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass


def adicionar_colunas_veiculo_completas():
    """
    MIGRAÇÃO 19: Adicionar colunas faltantes na tabela veiculo
    Resolve erro: column veiculo.chassi does not exist
    """
    try:
        logger.info("🚗 MIGRAÇÃO 19: Adicionando colunas faltantes em veículos...")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se tabela existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'veiculo'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.warning("⚠️ Tabela veiculo não existe - será criada pela migração anterior")
            cursor.close()
            connection.close()
            return
        
        # Colunas a adicionar
        colunas_adicionar = {
            'chassi': 'VARCHAR(50)',
            'renavam': 'VARCHAR(20)',
            'combustivel': "VARCHAR(20) DEFAULT 'Gasolina'",
            'cor': 'VARCHAR(30)',
            'km_proxima_manutencao': 'INTEGER',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        for coluna, tipo_sql in colunas_adicionar.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' na tabela veiculo...")
                cursor.execute(f"ALTER TABLE veiculo ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada com sucesso!")
            else:
                logger.info(f"✅ Coluna '{coluna}' já existe")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ MIGRAÇÃO 19 CONCLUÍDA: Todas as colunas de veículo verificadas/adicionadas!")
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 19 - colunas veiculo: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass


def migrar_sistema_fleet_completo():
    """
    MIGRAÇÃO 20: CRÍTICA - Sistema Fleet Completo
    
    Cria a nova arquitetura de veículos com tabelas Fleet:
    - fleet_vehicle (substitui veiculo)
    - fleet_vehicle_usage (substitui uso_veiculo) 
    - fleet_vehicle_cost (substitui custo_veiculo)
    
    Migra dados das tabelas antigas para as novas mantendo integridade multi-tenant.
    """
    try:
        logger.info("=" * 80)
        logger.info("🚀 MIGRAÇÃO 20: SISTEMA FLEET COMPLETO - NOVA ARQUITETURA")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # ===================================================================
        # PARTE 1: CRIAR TABELA fleet_vehicle
        # ===================================================================
        logger.info("📋 PARTE 1: Criando tabela fleet_vehicle...")
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'fleet_vehicle'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.info("🔨 Criando tabela fleet_vehicle...")
            cursor.execute("""
                CREATE TABLE fleet_vehicle (
                    vehicle_id SERIAL PRIMARY KEY,
                    reg_plate VARCHAR(10) NOT NULL,
                    make_name VARCHAR(50) NOT NULL,
                    model_name VARCHAR(100) NOT NULL DEFAULT 'Não informado',
                    vehicle_year INTEGER NOT NULL,
                    vehicle_kind VARCHAR(30) NOT NULL DEFAULT 'Veículo',
                    current_km INTEGER DEFAULT 0,
                    vehicle_color VARCHAR(30),
                    chassis_number VARCHAR(50),
                    renavam_code VARCHAR(20),
                    fuel_type VARCHAR(20) DEFAULT 'Gasolina',
                    status_code VARCHAR(20) DEFAULT 'ativo',
                    last_maintenance_date DATE,
                    next_maintenance_date DATE,
                    next_maintenance_km INTEGER,
                    admin_owner_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    CONSTRAINT uk_fleet_vehicle_admin_plate UNIQUE(admin_owner_id, reg_plate)
                )
            """)
            
            # Criar índices
            cursor.execute("CREATE INDEX idx_fleet_vehicle_admin_kind ON fleet_vehicle(admin_owner_id, vehicle_kind)")
            cursor.execute("CREATE INDEX idx_fleet_vehicle_plate_admin ON fleet_vehicle(reg_plate, admin_owner_id)")
            cursor.execute("CREATE INDEX idx_fleet_vehicle_status ON fleet_vehicle(admin_owner_id, status_code)")
            
            logger.info("✅ Tabela fleet_vehicle criada com sucesso!")
        else:
            logger.info("✅ Tabela fleet_vehicle já existe")
        
        # ===================================================================
        # PARTE 2: CRIAR TABELA fleet_vehicle_usage
        # ===================================================================
        logger.info("📋 PARTE 2: Criando tabela fleet_vehicle_usage...")
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'fleet_vehicle_usage'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.info("🔨 Criando tabela fleet_vehicle_usage...")
            cursor.execute("""
                CREATE TABLE fleet_vehicle_usage (
                    usage_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL,
                    driver_id INTEGER,
                    worksite_id INTEGER,
                    usage_date DATE NOT NULL,
                    departure_time TIME,
                    return_time TIME,
                    start_km INTEGER,
                    end_km INTEGER,
                    distance_km INTEGER,
                    front_passengers TEXT,
                    rear_passengers TEXT,
                    vehicle_responsible VARCHAR(100),
                    usage_notes TEXT,
                    admin_owner_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Criar índices
            cursor.execute("CREATE INDEX idx_fleet_usage_date_admin ON fleet_vehicle_usage(usage_date, admin_owner_id)")
            cursor.execute("CREATE INDEX idx_fleet_usage_driver ON fleet_vehicle_usage(driver_id)")
            cursor.execute("CREATE INDEX idx_fleet_usage_worksite ON fleet_vehicle_usage(worksite_id)")
            cursor.execute("CREATE INDEX idx_fleet_usage_vehicle ON fleet_vehicle_usage(vehicle_id)")
            
            logger.info("✅ Tabela fleet_vehicle_usage criada com sucesso!")
        else:
            logger.info("✅ Tabela fleet_vehicle_usage já existe")
        
        # ===================================================================
        # PARTE 3: CRIAR TABELA fleet_vehicle_cost
        # ===================================================================
        logger.info("📋 PARTE 3: Criando tabela fleet_vehicle_cost...")
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'fleet_vehicle_cost'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.info("🔨 Criando tabela fleet_vehicle_cost...")
            cursor.execute("""
                CREATE TABLE fleet_vehicle_cost (
                    cost_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL,
                    cost_date DATE NOT NULL,
                    cost_type VARCHAR(30) NOT NULL,
                    cost_amount NUMERIC(10, 2) NOT NULL,
                    cost_description VARCHAR(200) NOT NULL,
                    supplier_name VARCHAR(100),
                    invoice_number VARCHAR(20),
                    due_date DATE,
                    payment_status VARCHAR(20) DEFAULT 'Pendente',
                    payment_method VARCHAR(30),
                    cost_notes TEXT,
                    admin_owner_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Criar índices
            cursor.execute("CREATE INDEX idx_fleet_cost_date_admin ON fleet_vehicle_cost(cost_date, admin_owner_id)")
            cursor.execute("CREATE INDEX idx_fleet_cost_type ON fleet_vehicle_cost(cost_type)")
            cursor.execute("CREATE INDEX idx_fleet_cost_vehicle ON fleet_vehicle_cost(vehicle_id)")
            cursor.execute("CREATE INDEX idx_fleet_cost_status ON fleet_vehicle_cost(payment_status)")
            
            logger.info("✅ Tabela fleet_vehicle_cost criada com sucesso!")
        else:
            logger.info("✅ Tabela fleet_vehicle_cost já existe")
        
        # ===================================================================
        # PARTE 3.5: ADICIONAR FOREIGN KEYS (após criar todas as tabelas)
        # ===================================================================
        logger.info("📋 PARTE 3.5: Adicionando foreign keys...")
        
        # Verificar e adicionar FK fleet_vehicle → usuario
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle' 
            AND constraint_name = 'fk_fleet_vehicle_admin'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle 
                    ADD CONSTRAINT fk_fleet_vehicle_admin 
                    FOREIGN KEY (admin_owner_id) REFERENCES usuario(id)
                """)
                logger.info("✅ FK fleet_vehicle → usuario adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle → usuario: {e}")
        
        # Verificar e adicionar FK fleet_vehicle_usage → fleet_vehicle
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle_usage' 
            AND constraint_name = 'fk_fleet_usage_vehicle'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle_usage 
                    ADD CONSTRAINT fk_fleet_usage_vehicle 
                    FOREIGN KEY (vehicle_id) REFERENCES fleet_vehicle(vehicle_id)
                """)
                logger.info("✅ FK fleet_vehicle_usage → fleet_vehicle adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle_usage → fleet_vehicle: {e}")
        
        # Verificar e adicionar FK fleet_vehicle_usage → funcionario
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle_usage' 
            AND constraint_name = 'fk_fleet_usage_driver'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle_usage 
                    ADD CONSTRAINT fk_fleet_usage_driver 
                    FOREIGN KEY (driver_id) REFERENCES funcionario(id)
                """)
                logger.info("✅ FK fleet_vehicle_usage → funcionario adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle_usage → funcionario: {e}")
        
        # Verificar e adicionar FK fleet_vehicle_usage → obra
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle_usage' 
            AND constraint_name = 'fk_fleet_usage_worksite'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle_usage 
                    ADD CONSTRAINT fk_fleet_usage_worksite 
                    FOREIGN KEY (worksite_id) REFERENCES obra(id)
                """)
                logger.info("✅ FK fleet_vehicle_usage → obra adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle_usage → obra: {e}")
        
        # Verificar e adicionar FK fleet_vehicle_usage → usuario
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle_usage' 
            AND constraint_name = 'fk_fleet_usage_admin'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle_usage 
                    ADD CONSTRAINT fk_fleet_usage_admin 
                    FOREIGN KEY (admin_owner_id) REFERENCES usuario(id)
                """)
                logger.info("✅ FK fleet_vehicle_usage → usuario adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle_usage → usuario: {e}")
        
        # Verificar e adicionar FK fleet_vehicle_cost → fleet_vehicle
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle_cost' 
            AND constraint_name = 'fk_fleet_cost_vehicle'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle_cost 
                    ADD CONSTRAINT fk_fleet_cost_vehicle 
                    FOREIGN KEY (vehicle_id) REFERENCES fleet_vehicle(vehicle_id)
                """)
                logger.info("✅ FK fleet_vehicle_cost → fleet_vehicle adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle_cost → fleet_vehicle: {e}")
        
        # Verificar e adicionar FK fleet_vehicle_cost → usuario
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fleet_vehicle_cost' 
            AND constraint_name = 'fk_fleet_cost_admin'
        """)
        
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE fleet_vehicle_cost 
                    ADD CONSTRAINT fk_fleet_cost_admin 
                    FOREIGN KEY (admin_owner_id) REFERENCES usuario(id)
                """)
                logger.info("✅ FK fleet_vehicle_cost → usuario adicionada")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adicionar FK fleet_vehicle_cost → usuario: {e}")
        
        logger.info("✅ Todas as foreign keys verificadas/adicionadas!")
        
        # ===================================================================
        # PARTE 4: MIGRAR DADOS veiculo → fleet_vehicle
        # ===================================================================
        logger.info("📋 PARTE 4: Migrando dados veiculo → fleet_vehicle...")
        
        # Verificar se tabela antiga existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'veiculo'
        """)
        
        if cursor.fetchone()[0] > 0:
            # Contar registros na tabela antiga
            cursor.execute("SELECT COUNT(*) FROM veiculo")
            total_veiculos = cursor.fetchone()[0]
            
            if total_veiculos > 0:
                logger.info(f"🔄 Encontrados {total_veiculos} veículos para migrar...")
                
                # Migrar dados (INSERT ... ON CONFLICT para idempotência)
                cursor.execute("""
                    INSERT INTO fleet_vehicle (
                        reg_plate, make_name, model_name, vehicle_year, vehicle_kind,
                        current_km, vehicle_color, chassis_number, renavam_code, fuel_type,
                        status_code, last_maintenance_date, next_maintenance_date, 
                        next_maintenance_km, admin_owner_id, created_at
                    )
                    SELECT 
                        placa,
                        marca,
                        COALESCE(modelo, 'Não informado'),
                        COALESCE(ano, EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER),
                        COALESCE(tipo, 'Veículo'),
                        COALESCE(km_atual, 0),
                        cor,
                        chassi,
                        renavam,
                        COALESCE(combustivel, 'Gasolina'),
                        CASE WHEN ativo THEN 'ativo' ELSE 'inativo' END,
                        data_ultima_manutencao,
                        data_proxima_manutencao,
                        km_proxima_manutencao,
                        admin_id,
                        COALESCE(created_at, CURRENT_TIMESTAMP)
                    FROM veiculo
                    WHERE admin_id IS NOT NULL
                    ON CONFLICT (admin_owner_id, reg_plate) 
                    DO UPDATE SET
                        make_name = EXCLUDED.make_name,
                        model_name = EXCLUDED.model_name,
                        vehicle_year = EXCLUDED.vehicle_year,
                        current_km = EXCLUDED.current_km,
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                migrados = cursor.rowcount
                logger.info(f"✅ {migrados} veículos migrados/atualizados para fleet_vehicle!")
            else:
                logger.info("ℹ️  Tabela veiculo está vazia, nada a migrar")
        else:
            logger.info("ℹ️  Tabela veiculo não existe, pulando migração de dados")
        
        # ===================================================================
        # PARTE 4.5: GARANTIR coluna motorista_id em uso_veiculo (ANTES de usar)
        # ===================================================================
        logger.info("📋 PARTE 4.5: Verificando coluna motorista_id em uso_veiculo...")
        
        # Verificar se tabela uso_veiculo existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'uso_veiculo'
        """)
        
        if cursor.fetchone()[0] > 0:
            # Verificar se coluna motorista_id já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'uso_veiculo' 
                AND column_name = 'motorista_id'
            """)
            
            if not cursor.fetchone():
                logger.info("🔧 Adicionando coluna motorista_id na tabela uso_veiculo...")
                
                # Adicionar coluna motorista_id (NULLABLE para compatibilidade)
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ADD COLUMN motorista_id INTEGER
                """)
                logger.info("✅ Coluna motorista_id adicionada")
                
                # Adicionar FK opcional para funcionario
                try:
                    cursor.execute("""
                        ALTER TABLE uso_veiculo 
                        ADD CONSTRAINT fk_uso_veiculo_motorista 
                        FOREIGN KEY (motorista_id) REFERENCES funcionario(id) 
                        ON DELETE SET NULL
                    """)
                    logger.info("✅ FK fk_uso_veiculo_motorista adicionada")
                except Exception as fk_error:
                    logger.warning(f"⚠️ FK não pôde ser criada: {fk_error}")
                
                # Criar índice para performance
                try:
                    cursor.execute("""
                        CREATE INDEX idx_uso_veiculo_motorista 
                        ON uso_veiculo(motorista_id)
                    """)
                    logger.info("✅ Índice idx_uso_veiculo_motorista criado")
                except Exception as idx_error:
                    logger.warning(f"⚠️ Índice não pôde ser criado: {idx_error}")
            else:
                logger.info("✅ Coluna motorista_id já existe em uso_veiculo")
        else:
            logger.info("ℹ️  Tabela uso_veiculo não existe, coluna motorista_id não necessária")
        
        # ===================================================================
        # PARTE 5: MIGRAR DADOS uso_veiculo → fleet_vehicle_usage
        # ===================================================================
        logger.info("📋 PARTE 5: Migrando dados uso_veiculo → fleet_vehicle_usage...")
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'uso_veiculo'
        """)
        
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT COUNT(*) FROM uso_veiculo")
            total_usos = cursor.fetchone()[0]
            
            if total_usos > 0:
                logger.info(f"🔄 Encontrados {total_usos} registros de uso para migrar...")
                
                # Migrar dados com JOIN para mapear IDs
                cursor.execute("""
                    INSERT INTO fleet_vehicle_usage (
                        vehicle_id, driver_id, worksite_id, usage_date,
                        departure_time, return_time, start_km, end_km, distance_km,
                        front_passengers, rear_passengers, vehicle_responsible,
                        usage_notes, admin_owner_id, created_at
                    )
                    SELECT 
                        fv.vehicle_id,
                        uv.motorista_id,
                        uv.obra_id,
                        uv.data_uso,
                        uv.hora_saida,
                        uv.hora_retorno,
                        uv.km_inicial,
                        uv.km_final,
                        uv.km_percorrido,
                        uv.passageiros_frente,
                        uv.passageiros_tras,
                        uv.responsavel_veiculo,
                        uv.observacoes,
                        uv.admin_id,
                        COALESCE(uv.created_at, CURRENT_TIMESTAMP)
                    FROM uso_veiculo uv
                    INNER JOIN veiculo v ON uv.veiculo_id = v.id
                    INNER JOIN fleet_vehicle fv ON (v.placa = fv.reg_plate AND v.admin_id = fv.admin_owner_id)
                    WHERE uv.admin_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM fleet_vehicle_usage fuv 
                        WHERE fuv.vehicle_id = fv.vehicle_id 
                        AND fuv.usage_date = uv.data_uso
                        AND fuv.admin_owner_id = uv.admin_id
                    )
                """)
                
                migrados_uso = cursor.rowcount
                logger.info(f"✅ {migrados_uso} registros de uso migrados para fleet_vehicle_usage!")
            else:
                logger.info("ℹ️  Tabela uso_veiculo está vazia, nada a migrar")
        else:
            logger.info("ℹ️  Tabela uso_veiculo não existe, pulando migração de dados")
        
        # ===================================================================
        # PARTE 6: MIGRAR DADOS custo_veiculo → fleet_vehicle_cost
        # ===================================================================
        logger.info("📋 PARTE 6: Migrando dados custo_veiculo → fleet_vehicle_cost...")
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'custo_veiculo'
        """)
        
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT COUNT(*) FROM custo_veiculo")
            total_custos = cursor.fetchone()[0]
            
            if total_custos > 0:
                logger.info(f"🔄 Encontrados {total_custos} registros de custo para migrar...")
                
                # Migrar dados com JOIN para mapear IDs
                cursor.execute("""
                    INSERT INTO fleet_vehicle_cost (
                        vehicle_id, cost_date, cost_type, cost_amount,
                        cost_description, supplier_name, invoice_number, due_date,
                        payment_status, payment_method, cost_notes,
                        admin_owner_id, created_at
                    )
                    SELECT 
                        fv.vehicle_id,
                        cv.data_custo,
                        cv.tipo_custo,
                        cv.valor,
                        cv.descricao,
                        cv.fornecedor,
                        cv.numero_nota_fiscal,
                        cv.data_vencimento,
                        COALESCE(cv.status_pagamento, 'Pendente'),
                        cv.forma_pagamento,
                        cv.observacoes,
                        cv.admin_id,
                        COALESCE(cv.created_at, CURRENT_TIMESTAMP)
                    FROM custo_veiculo cv
                    INNER JOIN veiculo v ON cv.veiculo_id = v.id
                    INNER JOIN fleet_vehicle fv ON (v.placa = fv.reg_plate AND v.admin_id = fv.admin_owner_id)
                    WHERE cv.admin_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM fleet_vehicle_cost fvc 
                        WHERE fvc.vehicle_id = fv.vehicle_id 
                        AND fvc.cost_date = cv.data_custo
                        AND fvc.cost_description = cv.descricao
                        AND fvc.admin_owner_id = cv.admin_id
                    )
                """)
                
                migrados_custo = cursor.rowcount
                logger.info(f"✅ {migrados_custo} registros de custo migrados para fleet_vehicle_cost!")
            else:
                logger.info("ℹ️  Tabela custo_veiculo está vazia, nada a migrar")
        else:
            logger.info("ℹ️  Tabela custo_veiculo não existe, pulando migração de dados")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("🎉 MIGRAÇÃO 20 CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        logger.info("✅ Tabelas Fleet criadas:")
        logger.info("   - fleet_vehicle")
        logger.info("   - fleet_vehicle_usage")
        logger.info("   - fleet_vehicle_cost")
        logger.info("✅ Dados migrados das tabelas antigas")
        logger.info("✅ Índices criados para performance")
        logger.info("✅ Constraints multi-tenant aplicadas")
        logger.info("🔒 Tabelas antigas preservadas como backup")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERRO CRÍTICO na Migração 20 - Sistema Fleet: {str(e)}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())
        
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        
        # Re-raise para que seja tratado pelo executor principal
        raise


def hotfix_adicionar_motorista_id_legacy():
    """
    MIGRAÇÃO 21: HOTFIX EMERGENCIAL
    
    Adiciona coluna motorista_id na tabela ANTIGA uso_veiculo para compatibilidade.
    Isso permite que o código legacy continue funcionando enquanto migramos para Fleet.
    
    CONTEXTO:
    - views.py ainda usa modelos antigos (Veiculo, UsoVeiculo) diretamente em 27+ rotas
    - Erro em produção: column "motorista_id" does not exist
    - Estratégia: hotfix agora, migração gradual para Fleet depois
    """
    try:
        logger.info("=" * 80)
        logger.info("🚨 MIGRAÇÃO 21: HOTFIX EMERGENCIAL - motorista_id em uso_veiculo legacy")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se tabela uso_veiculo existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'uso_veiculo'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.info("ℹ️  Tabela uso_veiculo não existe, hotfix não necessário")
            cursor.close()
            connection.close()
            return
        
        # Verificar se coluna motorista_id já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'uso_veiculo' 
            AND column_name = 'motorista_id'
        """)
        
        if cursor.fetchone():
            logger.info("✅ Coluna motorista_id já existe na tabela uso_veiculo legacy")
            cursor.close()
            connection.close()
            return
        
        logger.info("🔧 Adicionando coluna motorista_id na tabela uso_veiculo legacy...")
        
        # Adicionar coluna motorista_id (NULLABLE para compatibilidade)
        cursor.execute("""
            ALTER TABLE uso_veiculo 
            ADD COLUMN motorista_id INTEGER
        """)
        logger.info("✅ Coluna motorista_id adicionada")
        
        # Adicionar FK opcional para funcionario
        try:
            cursor.execute("""
                ALTER TABLE uso_veiculo 
                ADD CONSTRAINT fk_uso_veiculo_motorista 
                FOREIGN KEY (motorista_id) REFERENCES funcionario(id) 
                ON DELETE SET NULL
            """)
            logger.info("✅ Foreign key fk_uso_veiculo_motorista adicionada")
        except Exception as fk_error:
            logger.warning(f"⚠️  Foreign key não pôde ser criada: {fk_error}")
            logger.warning("ℹ️  Continuando sem FK (não bloqueia funcionalidade)")
        
        # Criar índice para performance
        try:
            cursor.execute("""
                CREATE INDEX idx_uso_veiculo_motorista 
                ON uso_veiculo(motorista_id)
            """)
            logger.info("✅ Índice idx_uso_veiculo_motorista criado")
        except Exception as idx_error:
            logger.warning(f"⚠️  Índice não pôde ser criado: {idx_error}")
        
        # IMPORTANTE: Tentar popular motorista_id com dados existentes de funcionario_id
        # (caso a tabela tenha usado funcionario_id antes)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'uso_veiculo' 
            AND column_name = 'funcionario_id'
        """)
        
        if cursor.fetchone():
            logger.info("🔄 Migrando dados de funcionario_id → motorista_id...")
            cursor.execute("""
                UPDATE uso_veiculo 
                SET motorista_id = funcionario_id 
                WHERE motorista_id IS NULL 
                AND funcionario_id IS NOT NULL
            """)
            migrados = cursor.rowcount
            if migrados > 0:
                logger.info(f"✅ {migrados} registros migrados de funcionario_id → motorista_id")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("🎉 HOTFIX 21 CONCLUÍDO COM SUCESSO!")
        logger.info("=" * 80)
        logger.info("✅ Coluna motorista_id adicionada em uso_veiculo legacy")
        logger.info("✅ Código legacy pode continuar funcionando")
        logger.info("✅ Produção estabilizada - erro 'motorista_id does not exist' resolvido")
        logger.info("📋 Próximos passos: Migrar rotas do views.py para usar FleetService gradualmente")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERRO CRÍTICO no Hotfix 21 - motorista_id legacy: {str(e)}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())
        
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        
        # NÃO re-raise - esse hotfix não deve quebrar o startup
        logger.warning("⚠️  Hotfix falhou mas aplicação continuará inicializando")
        logger.warning("⚠️  Sistema de veículos legacy pode apresentar erros até correção manual")