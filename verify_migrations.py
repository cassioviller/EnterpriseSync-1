#!/usr/bin/env python3
"""
🔍 VERIFICADOR DE INTEGRIDADE DAS MIGRAÇÕES DE VEÍCULOS
=====================================================
Verifica se todas as colunas necessárias existem nas tabelas de veículos
Ideal para auditoria e confirmação pós-migração
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

class MigrationVerifier:
    def __init__(self, database_url):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        
    def check_table_exists(self, table_name):
        """Verifica se tabela existe no banco"""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            return table_name in tables
        except Exception as e:
            logger.error(f"Erro ao verificar tabela {table_name}: {e}")
            return False
    
    def get_table_columns(self, table_name):
        """Obtém lista de colunas de uma tabela"""
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            return [col['name'] for col in columns]
        except Exception as e:
            logger.error(f"Erro ao obter colunas da tabela {table_name}: {e}")
            return []
    
    def verify_uso_veiculo_table(self):
        """Verifica integridade da tabela uso_veiculo"""
        logger.info("🔍 Verificando tabela uso_veiculo...")
        
        if not self.check_table_exists('uso_veiculo'):
            logger.error("❌ Tabela uso_veiculo não existe!")
            return False
        
        expected_columns = [
            'id',
            'veiculo_id',
            'funcionario_id',
            'data_uso',
            'hora_saida',
            'hora_retorno',
            'km_inicial',
            'km_final',
            'destino',
            'motivo',
            'porcentagem_combustivel',  # CRÍTICA
            'km_percorrido',
            'horas_uso',
            'custo_estimado',
            'aprovado',
            'aprovado_por_id',
            'data_aprovacao',
            'admin_id',
            'created_at',
            'updated_at'
        ]
        
        existing_columns = self.get_table_columns('uso_veiculo')
        missing_columns = []
        
        for column in expected_columns:
            if column in existing_columns:
                logger.info(f"  ✅ Coluna {column} existe")
            else:
                logger.error(f"  ❌ Coluna {column} NÃO EXISTE")
                missing_columns.append(column)
        
        if missing_columns:
            logger.error(f"❌ FALHA: {len(missing_columns)} colunas faltantes em uso_veiculo")
            logger.error(f"📋 Colunas faltantes: {', '.join(missing_columns)}")
            return False
        else:
            logger.info(f"✅ SUCESSO: Todas as {len(expected_columns)} colunas existem em uso_veiculo")
            return True
    
    def verify_custo_veiculo_table(self):
        """Verifica integridade da tabela custo_veiculo"""
        logger.info("🔍 Verificando tabela custo_veiculo...")
        
        if not self.check_table_exists('custo_veiculo'):
            logger.error("❌ Tabela custo_veiculo não existe!")
            return False
        
        expected_columns = [
            'id',
            'veiculo_id',
            'data',
            'tipo_custo',
            'valor',
            'descricao',
            'litros_combustivel',
            'preco_por_litro',
            'km_atual',
            'admin_id',
            'created_at',
            'updated_at'
        ]
        
        existing_columns = self.get_table_columns('custo_veiculo')
        missing_columns = []
        
        for column in expected_columns:
            if column in existing_columns:
                logger.info(f"  ✅ Coluna {column} existe")
            else:
                logger.error(f"  ❌ Coluna {column} NÃO EXISTE")
                missing_columns.append(column)
        
        if missing_columns:
            logger.error(f"❌ FALHA: {len(missing_columns)} colunas faltantes em custo_veiculo")
            logger.error(f"📋 Colunas faltantes: {', '.join(missing_columns)}")
            return False
        else:
            logger.info(f"✅ SUCESSO: Todas as {len(expected_columns)} colunas existem em custo_veiculo")
            return True
    
    def verify_veiculo_table(self):
        """Verifica integridade da tabela veiculo"""
        logger.info("🔍 Verificando tabela veiculo...")
        
        if not self.check_table_exists('veiculo'):
            logger.error("❌ Tabela veiculo não existe!")
            return False
        
        expected_columns = [
            'id',
            'placa',
            'marca',
            'modelo',
            'ano',
            'tipo',
            'status',
            'km_atual',
            'data_ultima_manutencao',
            'data_proxima_manutencao',
            'ativo',
            'admin_id',
            'created_at'
        ]
        
        existing_columns = self.get_table_columns('veiculo')
        missing_columns = []
        
        for column in expected_columns:
            if column in existing_columns:
                logger.info(f"  ✅ Coluna {column} existe")
            else:
                logger.error(f"  ❌ Coluna {column} NÃO EXISTE")
                missing_columns.append(column)
        
        if missing_columns:
            logger.error(f"❌ FALHA: {len(missing_columns)} colunas faltantes em veiculo")
            logger.error(f"📋 Colunas faltantes: {', '.join(missing_columns)}")
            return False
        else:
            logger.info(f"✅ SUCESSO: Todas as {len(expected_columns)} colunas existem em veiculo")
            return True
    
    def get_database_info(self):
        """Obtém informações gerais do banco"""
        try:
            with self.engine.connect() as conn:
                # Versão do PostgreSQL
                result = conn.execute(text("SELECT version();"))
                version = result.fetchone()[0]
                
                # Informações do banco atual
                result = conn.execute(text("SELECT current_database(), current_user;"))
                db_info = result.fetchone()
                
                return {
                    'version': version,
                    'database': db_info[0],
                    'user': db_info[1]
                }
        except Exception as e:
            logger.error(f"Erro ao obter informações do banco: {e}")
            return None
    
    def run_full_verification(self):
        """Executa verificação completa do sistema"""
        logger.info("🔍 VERIFICADOR DE INTEGRIDADE DAS MIGRAÇÕES")
        logger.info("=" * 60)
        
        # Informações do banco
        db_info = self.get_database_info()
        if db_info:
            logger.info(f"🎯 Banco: {db_info['database']}")
            logger.info(f"👤 Usuário: {db_info['user']}")
            logger.info(f"🗄️ Versão: {db_info['version'].split(' ')[1]}")
        
        logger.info("-" * 60)
        
        # Verificar tabelas
        results = []
        
        results.append(self.verify_veiculo_table())
        results.append(self.verify_uso_veiculo_table())
        results.append(self.verify_custo_veiculo_table())
        
        logger.info("=" * 60)
        
        # Resultado final
        if all(results):
            logger.info("🎉 VERIFICAÇÃO COMPLETA: TODAS AS TABELAS ESTÃO ÍNTEGRAS!")
            logger.info("✅ Sistema de veículos pronto para uso")
            return True
        else:
            logger.error("❌ VERIFICAÇÃO FALHOU: PROBLEMAS DE INTEGRIDADE DETECTADOS")
            logger.error("🔧 Execute as migrações forçadas para corrigir")
            return False

def main():
    """Função principal para verificação"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não definida")
        sys.exit(1)
    
    # Mascarar credenciais para logs seguros
    database_url_masked = database_url
    import re
    database_url_masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', database_url_masked)
    
    logger.info(f"🎯 Target Database: {database_url_masked}")
    
    verifier = MigrationVerifier(database_url)
    success = verifier.run_full_verification()
    
    if success:
        logger.info(f"✅ VERIFICAÇÃO CONCLUÍDA - {datetime.now()}")
        sys.exit(0)
    else:
        logger.error(f"❌ VERIFICAÇÃO FALHOU - {datetime.now()}")
        sys.exit(1)

if __name__ == "__main__":
    main()