#!/usr/bin/env python3
"""
🚀 SISTEMA DE MIGRAÇÕES FORÇADAS PARA VEÍCULOS
==============================================
Executa ALTER TABLE para adicionar colunas faltantes
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VeiculoMigrationForcer:
    def __init__(self, database_url):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        
    def check_column_exists(self, table_name, column_name):
        """Verifica se coluna existe na tabela"""
        try:
            inspector = inspect(self.engine)
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception as e:
            logger.error(f"Erro ao verificar coluna {column_name} em {table_name}: {e}")
            return False
    
    def execute_migration(self, sql_command, description):
        """Executa comando SQL de migração com tratamento de erro"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(sql_command))
                conn.commit()
                logger.info(f"✅ {description}")
                return True
        except (OperationalError, ProgrammingError) as e:
            if "already exists" in str(e) or "duplicate column" in str(e):
                logger.info(f"⚠️  {description} - Já existe")
                return True
            else:
                logger.error(f"❌ {description} - ERRO: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ {description} - ERRO INESPERADO: {e}")
            return False
    
    def migrate_uso_veiculo_table(self):
        """Migra tabela uso_veiculo com todas as colunas necessárias"""
        logger.info("🔄 Iniciando migração da tabela uso_veiculo...")
        
        # Lista de colunas que devem existir - COMPLETA baseada na verificação
        required_columns = [
            {
                'name': 'hora_saida',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN hora_saida TIME;',
                'description': 'Adicionar coluna hora_saida'
            },
            {
                'name': 'hora_retorno',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN hora_retorno TIME;',
                'description': 'Adicionar coluna hora_retorno'
            },
            {
                'name': 'destino',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN destino VARCHAR(255);',
                'description': 'Adicionar coluna destino'
            },
            {
                'name': 'motivo',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN motivo TEXT;',
                'description': 'Adicionar coluna motivo'
            },
            {
                'name': 'porcentagem_combustivel',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN porcentagem_combustivel INTEGER;',
                'description': 'Adicionar coluna porcentagem_combustivel'
            },
            {
                'name': 'km_percorrido',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN km_percorrido INTEGER DEFAULT 0;',
                'description': 'Adicionar coluna km_percorrido'
            },
            {
                'name': 'horas_uso',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN horas_uso FLOAT DEFAULT 0.0;',
                'description': 'Adicionar coluna horas_uso'
            },
            {
                'name': 'custo_estimado',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN custo_estimado FLOAT DEFAULT 0.0;',
                'description': 'Adicionar coluna custo_estimado'
            },
            {
                'name': 'aprovado',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN aprovado BOOLEAN DEFAULT FALSE;',
                'description': 'Adicionar coluna aprovado'
            },
            {
                'name': 'aprovado_por_id',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN aprovado_por_id INTEGER;',
                'description': 'Adicionar coluna aprovado_por_id'
            },
            {
                'name': 'data_aprovacao',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN data_aprovacao TIMESTAMP;',
                'description': 'Adicionar coluna data_aprovacao'
            },
            {
                'name': 'created_at',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;',
                'description': 'Adicionar coluna created_at'
            },
            {
                'name': 'updated_at',
                'sql': 'ALTER TABLE uso_veiculo ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;',
                'description': 'Adicionar coluna updated_at'
            }
        ]
        
        success_count = 0
        for column in required_columns:
            if not self.check_column_exists('uso_veiculo', column['name']):
                logger.info(f"🔄 Coluna {column['name']} não existe, adicionando...")
                if self.execute_migration(column['sql'], column['description']):
                    success_count += 1
            else:
                logger.info(f"✅ Coluna {column['name']} já existe")
                success_count += 1
        
        logger.info(f"📊 Migração uso_veiculo: {success_count}/{len(required_columns)} colunas OK")
        return success_count == len(required_columns)
    
    def migrate_custo_veiculo_table(self):
        """Migra tabela custo_veiculo com colunas necessárias"""
        logger.info("🔄 Iniciando migração da tabela custo_veiculo...")
        
        required_columns = [
            {
                'name': 'data',
                'sql': 'ALTER TABLE custo_veiculo ADD COLUMN data DATE;',
                'description': 'Adicionar coluna data'
            },
            {
                'name': 'litros_combustivel',
                'sql': 'ALTER TABLE custo_veiculo ADD COLUMN litros_combustivel FLOAT;',
                'description': 'Adicionar coluna litros_combustivel'
            },
            {
                'name': 'preco_por_litro',
                'sql': 'ALTER TABLE custo_veiculo ADD COLUMN preco_por_litro FLOAT;',
                'description': 'Adicionar coluna preco_por_litro'
            },
            {
                'name': 'km_atual',
                'sql': 'ALTER TABLE custo_veiculo ADD COLUMN km_atual INTEGER;',
                'description': 'Adicionar coluna km_atual'
            },
            {
                'name': 'created_at',
                'sql': 'ALTER TABLE custo_veiculo ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;',
                'description': 'Adicionar coluna created_at'
            },
            {
                'name': 'updated_at',
                'sql': 'ALTER TABLE custo_veiculo ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;',
                'description': 'Adicionar coluna updated_at'
            }
        ]
        
        success_count = 0
        for column in required_columns:
            if not self.check_column_exists('custo_veiculo', column['name']):
                if self.execute_migration(column['sql'], column['description']):
                    success_count += 1
            else:
                logger.info(f"✅ Coluna {column['name']} já existe")
                success_count += 1
        
        return success_count == len(required_columns)
    
    def run_all_migrations(self):
        """Executa todas as migrações necessárias"""
        logger.info("🚀 INICIANDO MIGRAÇÕES FORÇADAS DE VEÍCULOS")
        logger.info("=" * 60)
        
        results = []
        
        # Migrar uso_veiculo
        results.append(self.migrate_uso_veiculo_table())
        
        # Migrar custo_veiculo
        results.append(self.migrate_custo_veiculo_table())
        
        # Resultado final
        if all(results):
            logger.info("🎉 TODAS AS MIGRAÇÕES EXECUTADAS COM SUCESSO!")
            return True
        else:
            logger.error("❌ ALGUMAS MIGRAÇÕES FALHARAM")
            return False

def main():
    """Função principal para execução das migrações"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não definida")
        sys.exit(1)
    
    logger.info(f"🎯 Target Database: {database_url.split('@')[1] if '@' in database_url else 'LOCAL'}")
    
    migrator = VeiculoMigrationForcer(database_url)
    success = migrator.run_all_migrations()
    
    if success:
        logger.info("✅ MIGRAÇÕES CONCLUÍDAS - Sistema pronto para uso")
        sys.exit(0)
    else:
        logger.error("❌ MIGRAÇÕES FALHARAM - Verificar logs")
        sys.exit(1)

if __name__ == "__main__":
    main()