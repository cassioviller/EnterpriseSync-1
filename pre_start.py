#!/usr/bin/env python3
"""
Pre-start script para produção - SIGE v9.0
Executa migrações antes do Gunicorn iniciar

OBJETIVO:
- Garantir que todas as migrações sejam aplicadas antes do app iniciar
- Fornecer feedback claro sobre o status das migrações
- Bloquear deploy se houver erros críticos (opcional via STRICT_MIGRATIONS)
"""

import os
import sys
import logging
from datetime import datetime

# Configurar logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_migrations():
    """Executa sistema de migrações v2.0 com rastreamento"""
    try:
        logger.info("=" * 80)
        logger.info("🚀 PRE-START SCRIPT - SIGE v9.0")
        logger.info(f"⏰ Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 80)
        
        # Importar app context e sistema de migrações
        logger.info("📦 Importando dependências...")
        from app import app, db
        from migrations import executar_migracoes
        
        logger.info("✅ Dependências carregadas")
        
        # Executar migrações dentro do app context
        with app.app_context():
            logger.info("🔄 Iniciando sistema de migrações...")
            
            # Executar migrações (já tem logs internos detalhados)
            executar_migracoes()
            
            logger.info("=" * 80)
            logger.info("✅ PRE-START CONCLUÍDO - Sistema pronto para iniciar")
            logger.info("=" * 80)
            
            return True
            
    except ImportError as e:
        logger.error(f"❌ Erro ao importar módulos: {e}")
        logger.error("Verifique se todas as dependências estão instaladas")
        return False
        
    except Exception as e:
        logger.error(f"❌ Erro crítico durante pre-start: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def check_strict_mode():
    """Verifica se modo estrito está ativado (bloqueia deploy em caso de erro)"""
    return os.environ.get('STRICT_MIGRATIONS', 'false').lower() == 'true'

def main():
    """Função principal do pre-start"""
    logger.info("🎬 Iniciando pre-start script...")
    
    # Executar migrações
    success = run_migrations()
    
    # Verificar modo estrito
    strict_mode = check_strict_mode()
    
    if not success:
        if strict_mode:
            logger.error("=" * 80)
            logger.error("🛑 MODO ESTRITO ATIVO - Deploy bloqueado por erro nas migrações")
            logger.error("=" * 80)
            logger.error("AÇÕES:")
            logger.error("1. Verificar logs acima para identificar o erro")
            logger.error("2. Corrigir o problema e fazer novo deploy")
            logger.error("3. Ou desativar modo estrito: STRICT_MIGRATIONS=false")
            sys.exit(1)  # Exit code 1 = erro (Dockerfile para aqui)
        else:
            logger.warning("=" * 80)
            logger.warning("⚠️  Migrações falharam mas modo estrito está DESATIVADO")
            logger.warning("⚠️  Aplicação continuará inicializando...")
            logger.warning("=" * 80)
            logger.warning("NOTA: Para bloquear deploy em caso de erro, use: STRICT_MIGRATIONS=true")
            sys.exit(0)  # Exit code 0 = sucesso (Dockerfile continua)
    
    logger.info("✅ Pre-start concluído com sucesso")
    sys.exit(0)  # Exit code 0 = sucesso

if __name__ == "__main__":
    main()
