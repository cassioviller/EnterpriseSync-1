#!/usr/bin/env python3
"""
🔧 CORREÇÃO AUTOMÁTICA PRODUÇÃO - PORCENTAGEM_COMBUSTIVEL
================================================================
Script específico para corrigir coluna porcentagem_combustivel na produção
Executado automaticamente durante o deploy via Dockerfile

AMBIENTE ALVO: EasyPanel/Hostinger Production
CONNECTION STRING: postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
================================================================
"""

import os
import sys
import logging
import time
from datetime import datetime

def setup_production_logging():
    """Configurar logging específico para produção"""
    log_format = '%(asctime)s [PROD-FIX] %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('/app/logs/porcentagem_combustivel_fix.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def detect_production_environment():
    """Detectar se estamos no ambiente de produção EasyPanel"""
    hostname = os.uname().nodename
    database_url = os.environ.get('DATABASE_URL', '')
    
    # Indicadores de produção EasyPanel
    is_easypanel = any([
        'viajey_sige' in hostname,
        'easypanel' in hostname.lower(),
        'viajey_sige' in database_url,
        'sige:sige@' in database_url
    ])
    
    return is_easypanel, hostname, database_url

def get_production_connection():
    """Obter conexão específica para produção"""
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        # Tentar DATABASE_URL primeiro
        database_url = os.environ.get("DATABASE_URL")
        
        # Se não tiver, usar URL padrão EasyPanel
        if not database_url:
            database_url = "postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
            os.environ['DATABASE_URL'] = database_url
        
        # Parse da URL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        url = urlparse(database_url)
        
        # Conectar com timeout específico para produção
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            database=url.path[1:] if url.path else 'sige',
            sslmode='disable' if 'sslmode=disable' in database_url else 'prefer',
            connect_timeout=30
        )
        
        return conn, database_url
        
    except Exception as e:
        raise Exception(f"Falha na conexão produção: {e}")

def verify_production_database(conn, logger):
    """Verificar se estamos no banco de produção correto"""
    try:
        cursor = conn.cursor()
        
        # Verificar nome do banco
        cursor.execute("SELECT current_database(), current_user;")
        db_name, db_user = cursor.fetchone()
        
        # Verificar quantidade de tabelas (produção deve ter ~80 tabelas)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        table_count = cursor.fetchone()[0]
        
        logger.info(f"🔍 Banco detectado: {db_name}")
        logger.info(f"👤 Usuário: {db_user}")
        logger.info(f"📊 Total tabelas: {table_count}")
        
        # Verificar se é ambiente de produção (>= 50 tabelas)
        if table_count >= 50:
            logger.info("✅ Ambiente de PRODUÇÃO confirmado")
            return True
        else:
            logger.warning(f"⚠️ Ambiente pode ser desenvolvimento (apenas {table_count} tabelas)")
            return False
            
        cursor.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar banco: {e}")
        return False

def fix_porcentagem_combustivel_column(conn, logger):
    """Corrigir coluna porcentagem_combustivel especificamente"""
    try:
        cursor = conn.cursor()
        
        # 1. Verificar se tabela uso_veiculo existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'uso_veiculo'
            );
        """)
        
        if not cursor.fetchone()[0]:
            logger.error("❌ Tabela uso_veiculo não existe!")
            return False
            
        # 2. Verificar se coluna porcentagem_combustivel existe
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'uso_veiculo' 
            AND column_name = 'porcentagem_combustivel';
        """)
        
        column_info = cursor.fetchone()
        
        if column_info:
            logger.info(f"✅ Coluna 'porcentagem_combustivel' já existe: {column_info}")
        else:
            logger.info("🔧 Adicionando coluna 'porcentagem_combustivel'...")
            
            # Adicionar coluna
            cursor.execute("""
                ALTER TABLE uso_veiculo 
                ADD COLUMN porcentagem_combustivel INTEGER DEFAULT NULL;
            """)
            
            logger.info("✅ Coluna 'porcentagem_combustivel' adicionada")
        
        # 3. Verificar dados existentes
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(porcentagem_combustivel) as com_combustivel
            FROM uso_veiculo;
        """)
        
        total, com_combustivel = cursor.fetchone()
        logger.info(f"📊 Registros: {total} total, {com_combustivel} com combustível")
        
        # 4. Testar query que estava falhando
        cursor.execute("""
            SELECT 
                uv.id,
                uv.veiculo_id,
                uv.porcentagem_combustivel,
                v.placa
            FROM uso_veiculo uv
            LEFT JOIN veiculo v ON uv.veiculo_id = v.id
            LIMIT 3;
        """)
        
        test_results = cursor.fetchall()
        logger.info(f"✅ Query JOIN testada com sucesso: {len(test_results)} resultados")
        
        # Commit das alterações
        conn.commit()
        cursor.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir coluna: {e}")
        conn.rollback()
        return False

def create_production_migration_log(conn, logger):
    """Criar log de migração na produção"""
    try:
        cursor = conn.cursor()
        
        # Criar tabela de logs se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_logs (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'SUCCESS',
                details TEXT,
                environment VARCHAR(50) DEFAULT 'production'
            );
        """)
        
        # Registrar esta migração
        cursor.execute("""
            INSERT INTO migration_logs (migration_name, details, status) 
            VALUES (%s, %s, %s)
        """, [
            'fix_porcentagem_combustivel_production',
            'Correção automática da coluna porcentagem_combustivel na tabela uso_veiculo',
            'SUCCESS'
        ])
        
        conn.commit()
        cursor.close()
        
        logger.info("✅ Log de migração registrado")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível criar log de migração: {e}")
        return False

def main():
    """Função principal - Execução automática na produção"""
    logger = setup_production_logging()
    
    logger.info("🚀 INICIANDO CORREÇÃO AUTOMÁTICA - PRODUÇÃO")
    logger.info("=" * 60)
    logger.info(f"📅 Timestamp: {datetime.now()}")
    
    # 1. Detectar ambiente
    is_production, hostname, db_url = detect_production_environment()
    
    logger.info(f"🖥️ Hostname: {hostname}")
    logger.info(f"🔗 Database: {db_url.replace(':sige@', ':****@') if db_url else 'não definida'}")
    
    if not is_production:
        logger.info("ℹ️ Ambiente não é produção EasyPanel - saindo")
        sys.exit(0)
    
    logger.info("🎯 AMBIENTE DE PRODUÇÃO EASYPANEL DETECTADO")
    
    # 2. Conectar ao banco
    try:
        conn, final_db_url = get_production_connection()
        logger.info("✅ Conexão com banco de produção estabelecida")
    except Exception as e:
        logger.error(f"❌ Falha na conexão: {e}")
        sys.exit(1)
    
    try:
        # 3. Verificar banco de produção
        if not verify_production_database(conn, logger):
            logger.error("❌ Não foi possível confirmar ambiente de produção")
            sys.exit(1)
        
        # 4. Aguardar estabilização
        logger.info("⏳ Aguardando estabilização do banco...")
        time.sleep(5)
        
        # 5. Corrigir coluna porcentagem_combustivel
        logger.info("🔧 Iniciando correção da coluna...")
        if fix_porcentagem_combustivel_column(conn, logger):
            logger.info("✅ Correção da coluna concluída com sucesso")
        else:
            logger.error("❌ Falha na correção da coluna")
            sys.exit(1)
        
        # 6. Registrar migração
        create_production_migration_log(conn, logger)
        
        logger.info("=" * 60)
        logger.info("🎉 CORREÇÃO AUTOMÁTICA CONCLUÍDA COM SUCESSO!")
        logger.info("✅ Coluna porcentagem_combustivel disponível na produção")
        logger.info("🚀 Sistema pronto para deploy!")
        
    except Exception as e:
        logger.error(f"❌ ERRO GERAL: {e}")
        sys.exit(1)
        
    finally:
        # Fechar conexão
        if conn:
            conn.close()
            logger.info("🔒 Conexão fechada")

if __name__ == "__main__":
    main()