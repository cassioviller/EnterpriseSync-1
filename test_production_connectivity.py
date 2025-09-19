#!/usr/bin/env python3
"""
🔌 SCRIPT DE TESTE DE CONECTIVIDADE COM PRODUÇÃO EASYPANEL
==========================================================
Testa a conectividade com a base de dados de produção EasyPanel
e lista tabelas relacionadas ao sistema de veículos.
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
import psycopg2
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [CONNECTIVITY_TEST] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/connectivity_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Connection string de produção fornecida pelo usuário
PRODUCTION_DATABASE_URL = "postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"

# Tabelas relacionadas ao sistema de veículos
VEHICLE_RELATED_TABLES = [
    # Tabelas essenciais (devem existir)
    'veiculo',
    'uso_veiculo', 
    'custo_veiculo',
    'passageiro_veiculo',
    
    # Tabelas obsoletas (devem ser removidas)
    'alerta_veiculo',
    'manutencao_veiculo', 
    'transferencia_veiculo',
    'equipe_veiculo',
    'alocacao_veiculo'
]

def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    import re
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

def test_psycopg2_connectivity():
    """Testa conectividade básica com psycopg2"""
    logger.info("🔌 Testando conectividade básica com psycopg2...")
    
    try:
        # Testar conexão direta
        conn = psycopg2.connect(PRODUCTION_DATABASE_URL)
        
        # Verificar versão do PostgreSQL
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        pg_version = cursor.fetchone()[0]
        logger.info(f"✅ PostgreSQL Version: {pg_version}")
        
        # Verificar usuário atual
        cursor.execute("SELECT current_user")
        current_user = cursor.fetchone()[0]
        logger.info(f"✅ Current User: {current_user}")
        
        # Verificar database atual
        cursor.execute("SELECT current_database()")
        current_db = cursor.fetchone()[0]
        logger.info(f"✅ Current Database: {current_db}")
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Conectividade psycopg2: SUCESSO")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro conectividade psycopg2: {e}")
        return False

def test_sqlalchemy_connectivity():
    """Testa conectividade com SQLAlchemy"""
    logger.info("🔌 Testando conectividade com SQLAlchemy...")
    
    try:
        # Converter postgres:// para postgresql:// se necessário
        database_url = PRODUCTION_DATABASE_URL
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            
        engine = create_engine(database_url)
        
        # Testar conexão
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            test_result = result.scalar()
            logger.info(f"✅ SQLAlchemy test query result: {test_result}")
            
        logger.info("✅ Conectividade SQLAlchemy: SUCESSO")
        return engine
        
    except Exception as e:
        logger.error(f"❌ Erro conectividade SQLAlchemy: {e}")
        return None

def list_all_tables(engine):
    """Lista todas as tabelas no banco de dados"""
    logger.info("📋 Listando todas as tabelas do banco...")
    
    try:
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        
        logger.info(f"📊 Total de tabelas no banco: {len(all_tables)}")
        
        # Salvar lista completa em arquivo
        tables_info = {
            'timestamp': datetime.now().isoformat(),
            'total_tables': len(all_tables),
            'all_tables': sorted(all_tables)
        }
        
        with open('/tmp/production_tables_list.json', 'w') as f:
            json.dump(tables_info, f, indent=2)
            
        logger.info("💾 Lista completa salva em: /tmp/production_tables_list.json")
        
        return all_tables
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar tabelas: {e}")
        return []

def analyze_vehicle_tables(engine):
    """Analisa especificamente as tabelas relacionadas a veículos"""
    logger.info("🚗 Analisando tabelas relacionadas ao sistema de veículos...")
    
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        vehicle_analysis = {
            'timestamp': datetime.now().isoformat(),
            'essential_tables': {},
            'obsolete_tables': {},
            'summary': {}
        }
        
        # Verificar tabelas essenciais
        essential_tables = ['veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo']
        logger.info("🔍 Verificando tabelas essenciais...")
        
        for table in essential_tables:
            if table in existing_tables:
                # Contar registros
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        vehicle_analysis['essential_tables'][table] = {
                            'exists': True,
                            'record_count': count
                        }
                        logger.info(f"✅ Tabela essencial {table}: {count} registros")
                except Exception as e:
                    vehicle_analysis['essential_tables'][table] = {
                        'exists': True,
                        'record_count': 'ERROR',
                        'error': str(e)
                    }
                    logger.warning(f"⚠️ Erro ao contar registros em {table}: {e}")
            else:
                vehicle_analysis['essential_tables'][table] = {
                    'exists': False,
                    'record_count': 0
                }
                logger.warning(f"⚠️ Tabela essencial AUSENTE: {table}")
        
        # Verificar tabelas obsoletas
        obsolete_tables = ['alerta_veiculo', 'manutencao_veiculo', 'transferencia_veiculo', 'equipe_veiculo', 'alocacao_veiculo']
        logger.info("🔍 Verificando tabelas obsoletas...")
        
        obsolete_found = []
        for table in obsolete_tables:
            if table in existing_tables:
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        vehicle_analysis['obsolete_tables'][table] = {
                            'exists': True,
                            'record_count': count
                        }
                        obsolete_found.append(table)
                        logger.warning(f"🗑️ Tabela obsoleta PRESENTE: {table} ({count} registros)")
                except Exception as e:
                    vehicle_analysis['obsolete_tables'][table] = {
                        'exists': True,
                        'record_count': 'ERROR',
                        'error': str(e)
                    }
                    logger.warning(f"⚠️ Erro ao contar registros em {table}: {e}")
            else:
                vehicle_analysis['obsolete_tables'][table] = {
                    'exists': False
                }
                logger.info(f"✅ Tabela obsoleta já removida: {table}")
        
        # Resumo
        essential_present = sum(1 for t in vehicle_analysis['essential_tables'].values() if t['exists'])
        obsolete_present = len(obsolete_found)
        
        vehicle_analysis['summary'] = {
            'essential_tables_present': essential_present,
            'essential_tables_total': len(essential_tables),
            'obsolete_tables_present': obsolete_present,
            'obsolete_tables_total': len(obsolete_tables),
            'migration_needed': obsolete_present > 0,
            'tables_to_remove': obsolete_found
        }
        
        logger.info(f"📊 RESUMO VEÍCULOS:")
        logger.info(f"   ✅ Tabelas essenciais presentes: {essential_present}/{len(essential_tables)}")
        logger.info(f"   🗑️ Tabelas obsoletas presentes: {obsolete_present}/{len(obsolete_tables)}")
        logger.info(f"   🔄 Migração necessária: {'SIM' if obsolete_present > 0 else 'NÃO'}")
        
        # Salvar análise completa
        with open('/tmp/vehicle_tables_analysis.json', 'w') as f:
            json.dump(vehicle_analysis, f, indent=2)
            
        logger.info("💾 Análise completa salva em: /tmp/vehicle_tables_analysis.json")
        
        return vehicle_analysis
        
    except Exception as e:
        logger.error(f"❌ Erro na análise de tabelas de veículos: {e}")
        return None

def main():
    """Função principal do teste de conectividade"""
    logger.info("🚀 TESTE DE CONECTIVIDADE COM PRODUÇÃO EASYPANEL")
    logger.info("=" * 60)
    logger.info(f"🎯 Target Database: {mask_database_url(PRODUCTION_DATABASE_URL)}")
    logger.info(f"📅 Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Teste 1: Conectividade psycopg2
        logger.info("\n🔍 TESTE 1: Conectividade psycopg2")
        logger.info("-" * 40)
        psycopg2_success = test_psycopg2_connectivity()
        
        if not psycopg2_success:
            logger.error("❌ Falha na conectividade psycopg2 - abortando testes")
            return False
        
        # Teste 2: Conectividade SQLAlchemy
        logger.info("\n🔍 TESTE 2: Conectividade SQLAlchemy")
        logger.info("-" * 40)
        engine = test_sqlalchemy_connectivity()
        
        if engine is None:
            logger.error("❌ Falha na conectividade SQLAlchemy - abortando testes")
            return False
        
        # Teste 3: Listagem de tabelas
        logger.info("\n🔍 TESTE 3: Listagem de todas as tabelas")
        logger.info("-" * 40)
        all_tables = list_all_tables(engine)
        
        # Teste 4: Análise específica de veículos
        logger.info("\n🔍 TESTE 4: Análise de tabelas de veículos")
        logger.info("-" * 40)
        vehicle_analysis = analyze_vehicle_tables(engine)
        
        # Resultado final
        logger.info("\n✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
        logger.info("=" * 60)
        logger.info("📁 ARQUIVOS GERADOS:")
        logger.info("   📋 /tmp/connectivity_test.log")
        logger.info("   📊 /tmp/production_tables_list.json")
        logger.info("   🚗 /tmp/vehicle_tables_analysis.json")
        
        if vehicle_analysis and vehicle_analysis['summary']['migration_needed']:
            logger.info("\n🔄 MIGRAÇÃO NECESSÁRIA:")
            for table in vehicle_analysis['summary']['tables_to_remove']:
                logger.info(f"   🗑️ Remover: {table}")
        else:
            logger.info("\n✅ Nenhuma migração necessária - sistema já está limpo")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO: {e}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)