"""
SIGE v10.0 - Pre-Start: Execução de migrações antes do Gunicorn
Chamado por docker-entrypoint-easypanel-auto.sh antes de iniciar a aplicação.
"""
import sys
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

    # NOTA: o passo legado que tentava executar 'migrate_gestao_custos.py'
    # foi removido — o arquivo nunca existiu na raiz e o subprocess
    # retornava código 2, derrubando o deploy. A correção pontual de
    # GestaoCustoPai do seed V2 vive em scripts/fix_gestao_custos_seed.py
    # e roda sob demanda quando necessário (não pertence ao boot).

logger.info("=== pre_start.py concluido com sucesso ===")
sys.exit(0)
