"""
SIGE v10.0 - Pre-Start: Execução de migrações antes do Gunicorn
Chamado por docker-entrypoint-easypanel-auto.sh antes de iniciar a aplicação.
"""
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger('pre_start')

sys.path.append('/app')

logger.info("=== SIGE pre_start.py iniciando ===")

try:
    from app import app, db
except Exception as e:
    logger.error(f"ERRO ao importar app: {e}")
    sys.exit(1)

with app.app_context():
    logger.info("Criando/verificando tabelas (db.create_all)...")
    try:
        db.create_all()
        logger.info("db.create_all concluido.")
    except Exception as e:
        logger.error(f"ERRO em db.create_all: {e}")
        sys.exit(1)

    logger.info("Executando migracoes de schema (executar_migracoes)...")
    try:
        from migrations import executar_migracoes
        executar_migracoes()
        logger.info("executar_migracoes concluido.")
    except Exception as e:
        logger.error(f"ERRO em executar_migracoes: {e}")
        sys.exit(1)

    logger.info("Executando migracoes GestaoCustoPai (migrate_gestao_custos)...")
    try:
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        migrate_script = os.path.join(script_dir, 'migrate_gestao_custos.py')
        result = subprocess.run(
            [sys.executable, migrate_script],
            capture_output=True, text=True, timeout=120
        )
        if result.stdout:
            logger.info(f"migrate_gestao_custos stdout: {result.stdout.strip()}")
        if result.stderr:
            logger.info(f"migrate_gestao_custos stderr: {result.stderr.strip()}")
        if result.returncode != 0:
            logger.error(f"migrate_gestao_custos falhou com codigo {result.returncode}")
            sys.exit(1)
        logger.info("migrate_gestao_custos concluido.")
    except Exception as e:
        logger.error(f"ERRO ao executar migrate_gestao_custos: {e}")
        sys.exit(1)

logger.info("=== pre_start.py concluido com sucesso ===")
sys.exit(0)
