#!/usr/bin/env python3
"""
SIGE v10.0 - Script de Migração Avançado
Sistema de migração com logs detalhados e validação robusta
Autor: Joris Kuypers Architecture
Data: 2025-09-08
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/migration.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)

class SIGEMigrationManager:
    """Gerenciador de migrações do SIGE v10.0"""
    
    def __init__(self, database_url):
        self.database_url = database_url
        self.engine = None
        self.inspector = None
        
    def connect(self):
        """Estabelecer conexão com banco"""
        try:
            logger.info("🔌 Conectando ao banco de dados...")
            self.engine = create_engine(self.database_url)
            self.inspector = inspect(self.engine)
            
            # Testar conexão
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("✅ Conexão estabelecida com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar: {str(e)}")
            return False
    
    def get_existing_tables(self):
        """Obter lista de tabelas existentes"""
        try:
            tables = self.inspector.get_table_names()
            logger.info(f"📊 Tabelas encontradas: {len(tables)}")
            for table in sorted(tables):
                logger.info(f"  ✅ {table}")
            return tables
        except Exception as e:
            logger.error(f"❌ Erro ao listar tabelas: {str(e)}")
            return []
    
    def check_table_structure(self, table_name):
        """Verificar estrutura de uma tabela"""
        try:
            columns = self.inspector.get_columns(table_name)
            logger.info(f"🔍 Tabela '{table_name}' - {len(columns)} colunas:")
            
            for col in columns:
                logger.info(f"  📄 {col['name']} ({col['type']})")
                
            return columns
        except Exception as e:
            logger.error(f"❌ Erro ao verificar tabela {table_name}: {str(e)}")
            return []
    
    def ensure_admin_id_columns(self):
        """Garantir que todas as tabelas tenham coluna admin_id"""
        logger.info("🔧 Verificando colunas admin_id...")
        
        tables_need_admin_id = [
            'usuario', 'obra', 'servico', 'rdo', 'funcionario',
            'proposta_templates', 'servico_obra_real', 'almoxarifado',
            'alimentacao', 'equipe', 'veiculo'
        ]
        
        with self.engine.connect() as conn:
            for table in tables_need_admin_id:
                try:
                    # Verificar se tabela existe
                    if table not in self.inspector.get_table_names():
                        logger.warning(f"⚠️  Tabela '{table}' não existe, pulando...")
                        continue
                    
                    # Verificar se coluna admin_id existe
                    columns = [col['name'] for col in self.inspector.get_columns(table)]
                    
                    if 'admin_id' not in columns:
                        logger.info(f"🔨 Adicionando coluna admin_id à tabela '{table}'...")
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN admin_id INTEGER"))
                        conn.commit()
                        logger.info(f"✅ Coluna admin_id adicionada à tabela '{table}'")
                    else:
                        logger.info(f"✅ Tabela '{table}' já possui coluna admin_id")
                        
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao processar tabela '{table}': {str(e)}")
                    continue
    
    def create_missing_tables(self):
        """Criar tabelas ausentes usando SQLAlchemy"""
        logger.info("🔨 Verificando e criando tabelas ausentes...")
        
        try:
            # Importar models para criar tabelas
            sys.path.append('/app')
            from app import app, db
            
            with app.app_context():
                logger.info("📊 Criando todas as tabelas definidas nos models...")
                db.create_all()
                logger.info("✅ Tabelas criadas com sucesso")
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabelas: {str(e)}")
            logger.error(traceback.format_exc())
    
    def validate_critical_data(self):
        """Validar dados críticos do sistema"""
        logger.info("🔍 Validando dados críticos...")
        
        validations = [
            ("SELECT COUNT(*) FROM usuario", "usuários"),
            ("SELECT COUNT(*) FROM obra", "obras"),
            ("SELECT COUNT(*) FROM servico", "serviços"),
            ("SELECT COUNT(*) FROM rdo", "RDOs"),
        ]
        
        with self.engine.connect() as conn:
            for query, description in validations:
                try:
                    result = conn.execute(text(query)).scalar()
                    logger.info(f"📊 {description.capitalize()}: {result}")
                    
                    if result == 0:
                        logger.warning(f"⚠️  Nenhum registro encontrado para {description}")
                        
                except Exception as e:
                    logger.warning(f"⚠️  Não foi possível verificar {description}: {str(e)}")
    
    def setup_rdo_mastery_features(self):
        """Configurar recursos específicos do RDO Digital Mastery"""
        logger.info("🎯 Configurando recursos RDO Digital Mastery...")
        
        with self.engine.connect() as conn:
            try:
                # Verificar se tabela RDO tem colunas necessárias
                rdo_columns = [col['name'] for col in self.inspector.get_columns('rdo')]
                
                required_columns = [
                    ('observacoes_gerais', 'TEXT'),
                    ('local', 'VARCHAR(255)'),
                    ('condicoes_climaticas', 'VARCHAR(100)'),
                    ('admin_id', 'INTEGER')
                ]
                
                for col_name, col_type in required_columns:
                    if col_name not in rdo_columns:
                        logger.info(f"🔨 Adicionando coluna '{col_name}' à tabela RDO...")
                        conn.execute(text(f"ALTER TABLE rdo ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        logger.info(f"✅ Coluna '{col_name}' adicionada")
                    else:
                        logger.info(f"✅ Coluna '{col_name}' já existe na tabela RDO")
                
                logger.info("✅ Recursos RDO Digital Mastery configurados")
                
            except Exception as e:
                logger.error(f"❌ Erro ao configurar RDO Mastery: {str(e)}")
    
    def run_full_migration(self):
        """Executar migração completa"""
        logger.info("🚀 Iniciando migração completa SIGE v10.0...")
        
        start_time = datetime.now()
        
        try:
            # 1. Conectar ao banco
            if not self.connect():
                return False
            
            # 2. Listar tabelas existentes
            existing_tables = self.get_existing_tables()
            
            # 3. Criar tabelas ausentes
            self.create_missing_tables()
            
            # 4. Garantir colunas admin_id
            self.ensure_admin_id_columns()
            
            # 5. Configurar recursos RDO Mastery
            self.setup_rdo_mastery_features()
            
            # 6. Validar dados críticos
            self.validate_critical_data()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"✅ Migração concluída com sucesso em {duration:.2f} segundos")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro durante migração: {str(e)}")
            logger.error(traceback.format_exc())
            return False

def main():
    """Função principal"""
    logger.info("=" * 60)
    logger.info("🚀 SIGE v10.0 - Sistema de Migração Digital Mastery")
    logger.info("=" * 60)
    
    # Obter URL do banco
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não definida")
        sys.exit(1)
    
    logger.info(f"🔗 Conectando em: {database_url.split('@')[1] if '@' in database_url else 'banco local'}")
    
    # Executar migração
    migration_manager = SIGEMigrationManager(database_url)
    
    if migration_manager.run_full_migration():
        logger.info("🎉 Migração concluída com sucesso!")
        sys.exit(0)
    else:
        logger.error("💥 Migração falhou!")
        sys.exit(1)

if __name__ == "__main__":
    main()