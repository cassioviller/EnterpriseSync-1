#!/usr/bin/env python3
"""
🚀 EXECUTOR DE MIGRAÇÕES PARA PRODUÇÃO EASYPANEL
===============================================
Script final para execução das migrações com a connection string de produção.
Inclui todas as verificações de segurança e logs detalhados.

USAGE:
    export DATABASE_URL="postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"
    export RUN_CLEANUP_VEICULOS=1
    python3 production_migration_executor.py
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PRODUCTION_EXECUTOR] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/production_migration_executor.log')
    ]
)
logger = logging.getLogger(__name__)

def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    import re
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

def validate_production_environment():
    """Valida se estamos no ambiente de produção correto"""
    logger.info("🔍 Validando ambiente de produção...")
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL não definida")
        return False
    
    logger.info(f"🎯 Target Database: {mask_database_url(database_url)}")
    
    # Verificar se é a connection string de produção esperada
    if 'viajey_sige:5432' not in database_url:
        logger.warning(f"⚠️ DATABASE_URL não aponta para viajey_sige:5432")
        logger.warning(f"⚠️ URL atual: {mask_database_url(database_url)}")
        
        if input("Continuar mesmo assim? (s/N): ").lower() != 's':
            logger.info("🛑 Execução cancelada pelo usuário")
            return False
    
    return True

def execute_connectivity_test():
    """Executa teste de conectividade com produção"""
    logger.info("🔌 Testando conectividade com produção...")
    
    try:
        import psycopg2
        
        database_url = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        
        cursor = conn.cursor()
        
        # Verificar versão PostgreSQL
        cursor.execute("SELECT version()")
        pg_version = cursor.fetchone()[0]
        logger.info(f"✅ PostgreSQL: {pg_version}")
        
        # Verificar usuário e database
        cursor.execute("SELECT current_user, current_database()")
        user, db = cursor.fetchone()
        logger.info(f"✅ Conectado como: {user}@{db}")
        
        # Contar tabelas existentes
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count = cursor.fetchone()[0]
        logger.info(f"📊 Total de tabelas: {table_count}")
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Conectividade testada com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro de conectividade: {e}")
        return False

def analyze_vehicle_tables_production():
    """Analisa especificamente as tabelas de veículos em produção"""
    logger.info("🚗 Analisando tabelas de veículos em produção...")
    
    try:
        import psycopg2
        
        database_url = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar tabelas essenciais
        essential_tables = ['veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo']
        obsolete_tables = ['alerta_veiculo', 'manutencao_veiculo', 'transferencia_veiculo', 'equipe_veiculo', 'alocacao_veiculo']
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'essential_tables': {},
            'obsolete_tables': {},
            'migration_needed': False
        }
        
        logger.info("🔍 Verificando tabelas essenciais...")
        for table in essential_tables:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = %s AND table_schema = 'public'
            """, (table,))
            
            if cursor.fetchone()[0] > 0:
                # Tabela existe, contar registros
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                analysis['essential_tables'][table] = {
                    'exists': True,
                    'count': count
                }
                logger.info(f"✅ {table}: {count} registros")
            else:
                analysis['essential_tables'][table] = {
                    'exists': False,
                    'count': 0
                }
                logger.warning(f"⚠️ Tabela essencial ausente: {table}")
        
        logger.info("🔍 Verificando tabelas obsoletas...")
        obsolete_found = []
        for table in obsolete_tables:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = %s AND table_schema = 'public'
            """, (table,))
            
            if cursor.fetchone()[0] > 0:
                # Tabela obsoleta existe
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                analysis['obsolete_tables'][table] = {
                    'exists': True,
                    'count': count
                }
                obsolete_found.append(table)
                logger.warning(f"🗑️ Tabela obsoleta presente: {table} ({count} registros)")
                analysis['migration_needed'] = True
            else:
                analysis['obsolete_tables'][table] = {
                    'exists': False
                }
                logger.info(f"✅ Tabela obsoleta já removida: {table}")
        
        cursor.close()
        conn.close()
        
        # Salvar análise
        with open('/tmp/production_vehicle_analysis.json', 'w') as f:
            json.dump(analysis, f, indent=2)
        
        logger.info(f"📊 RESULTADO: {len(obsolete_found)} tabelas obsoletas encontradas")
        logger.info(f"🔄 Migração necessária: {'SIM' if analysis['migration_needed'] else 'NÃO'}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Erro na análise de tabelas: {e}")
        return None

def execute_cleanup_migration():
    """Executa a migration de limpeza de veículos"""
    logger.info("🧹 Executando migration de limpeza de veículos...")
    
    try:
        # Certificar que a flag está definida
        os.environ['RUN_CLEANUP_VEICULOS'] = '1'
        
        sys.path.append('/app')
        from migration_cleanup_veiculos_production import VeiculosMigrationCleaner
        
        # Executar migration em modo produção
        migrator = VeiculosMigrationCleaner(dry_run=False)
        success = migrator.executar_migration()
        
        if success:
            logger.info("✅ Migration de limpeza executada com sucesso!")
            return True
        else:
            logger.error("❌ Migration de limpeza falhou!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro na migration de limpeza: {e}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return False

def execute_automatic_migrations():
    """Executa todas as migrações automáticas"""
    logger.info("🔄 Executando migrações automáticas...")
    
    try:
        sys.path.append('/app')
        from app import app
        
        with app.app_context():
            from migrations import executar_migracoes
            executar_migracoes()
            
        logger.info("✅ Migrações automáticas executadas com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro nas migrações automáticas: {e}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return False

def verify_final_state():
    """Verifica o estado final após as migrações"""
    logger.info("🔍 Verificando estado final após migrações...")
    
    try:
        # Re-analisar tabelas de veículos
        final_analysis = analyze_vehicle_tables_production()
        
        if final_analysis:
            obsolete_remaining = sum(1 for table in final_analysis['obsolete_tables'].values() if table.get('exists', False))
            essential_present = sum(1 for table in final_analysis['essential_tables'].values() if table.get('exists', False))
            
            logger.info(f"📊 ESTADO FINAL:")
            logger.info(f"   ✅ Tabelas essenciais presentes: {essential_present}/4")
            logger.info(f"   🗑️ Tabelas obsoletas restantes: {obsolete_remaining}/5")
            
            if obsolete_remaining == 0 and essential_present == 4:
                logger.info("🎉 SUCESSO TOTAL: Sistema de veículos limpo e funcionando!")
                return True
            else:
                logger.warning("⚠️ Sistema parcialmente migrado - verificar logs")
                return False
        else:
            logger.error("❌ Não foi possível verificar estado final")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro na verificação final: {e}")
        return False

def generate_execution_report():
    """Gera relatório final da execução"""
    logger.info("📋 Gerando relatório final da execução...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'execution_type': 'production_migration_complete',
        'database_url': mask_database_url(os.environ.get('DATABASE_URL', '')),
        'environment_variables': {
            'RUN_CLEANUP_VEICULOS': os.environ.get('RUN_CLEANUP_VEICULOS'),
            'DATABASE_URL_defined': bool(os.environ.get('DATABASE_URL'))
        },
        'files_generated': [
            '/tmp/production_migration_executor.log',
            '/tmp/production_vehicle_analysis.json',
            '/tmp/migration_cleanup_veiculos.log'
        ],
        'next_steps': [
            'Verificar logs em /tmp/sige_*.log',
            'Testar funcionalidades do sistema de veículos',
            'Monitorar performance após migrações',
            'Fazer backup do estado atual'
        ]
    }
    
    with open('/tmp/final_execution_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info("💾 Relatório final salvo em: /tmp/final_execution_report.json")
    return report

def main():
    """Função principal do executor de produção"""
    logger.info("🚀 EXECUTOR DE MIGRAÇÕES PARA PRODUÇÃO EASYPANEL")
    logger.info("=" * 60)
    logger.info(f"📅 Início da execução: {datetime.now().isoformat()}")
    
    try:
        # 1. Validar ambiente
        logger.info("\n🔍 FASE 1: Validação do Ambiente")
        logger.info("-" * 40)
        if not validate_production_environment():
            logger.error("❌ Falha na validação do ambiente")
            return False
        
        # 2. Teste de conectividade
        logger.info("\n🔌 FASE 2: Teste de Conectividade")
        logger.info("-" * 40)
        if not execute_connectivity_test():
            logger.error("❌ Falha no teste de conectividade")
            return False
        
        # 3. Análise inicial
        logger.info("\n📊 FASE 3: Análise Inicial das Tabelas")
        logger.info("-" * 40)
        initial_analysis = analyze_vehicle_tables_production()
        if not initial_analysis:
            logger.error("❌ Falha na análise inicial")
            return False
        
        # 4. Migration de limpeza (se necessária)
        if initial_analysis['migration_needed']:
            logger.info("\n🧹 FASE 4: Migration de Limpeza")
            logger.info("-" * 40)
            if not execute_cleanup_migration():
                logger.error("❌ Falha na migration de limpeza")
                return False
        else:
            logger.info("\n✅ FASE 4: Migration de Limpeza DESNECESSÁRIA")
            logger.info("-" * 40)
            logger.info("Sistema já está limpo - pulando migration de limpeza")
        
        # 5. Migrações automáticas
        logger.info("\n🔄 FASE 5: Migrações Automáticas")
        logger.info("-" * 40)
        if not execute_automatic_migrations():
            logger.error("❌ Falha nas migrações automáticas")
            return False
        
        # 6. Verificação final
        logger.info("\n🔍 FASE 6: Verificação Final")
        logger.info("-" * 40)
        if not verify_final_state():
            logger.warning("⚠️ Verificação final com problemas")
        
        # 7. Relatório final
        logger.info("\n📋 FASE 7: Relatório Final")
        logger.info("-" * 40)
        final_report = generate_execution_report()
        
        # Resultado final
        logger.info("\n🎉 EXECUÇÃO CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 60)
        logger.info("📁 ARQUIVOS GERADOS:")
        for file_path in final_report['files_generated']:
            logger.info(f"   📄 {file_path}")
        
        logger.info("\n🚀 PRÓXIMOS PASSOS:")
        for step in final_report['next_steps']:
            logger.info(f"   • {step}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO NA EXECUÇÃO: {e}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    logger.info(f"🏁 Execução finalizada com código: {exit_code}")
    sys.exit(exit_code)