#!/usr/bin/env python3
"""
Script de deploy - Executa todas as migrações necessárias
Para ser executado automaticamente durante o deploy
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration_script(script_path):
    """
    Executa um script de migração específico
    """
    try:
        logger.info(f"🔧 Executando migração: {script_path}")
        
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            logger.info(f"✅ Migração {script_path} concluída com sucesso")
            if result.stdout:
                logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"❌ Migração {script_path} falhou")
            if result.stderr:
                logger.error(f"Erro: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao executar {script_path}: {e}")
        return False

def main():
    """
    Executa todas as migrações de deploy
    """
    logger.info("🚀 Iniciando deploy - Executando migrações")
    
    # Lista de migrações a serem executadas (em ordem)
    migrations = [
        "migrations/add_admin_id_to_outro_custo.py"
    ]
    
    failed_migrations = []
    
    for migration in migrations:
        migration_path = Path(migration)
        
        if not migration_path.exists():
            logger.warning(f"⚠️  Migração não encontrada: {migration}")
            continue
            
        if not run_migration_script(migration):
            failed_migrations.append(migration)
    
    # Relatório final
    if failed_migrations:
        logger.error(f"❌ {len(failed_migrations)} migrações falharam:")
        for failed in failed_migrations:
            logger.error(f"  - {failed}")
        sys.exit(1)
    else:
        logger.info("✅ Todas as migrações executadas com sucesso")
        logger.info("🎯 Deploy concluído - Sistema pronto para uso")
        sys.exit(0)

if __name__ == "__main__":
    main()