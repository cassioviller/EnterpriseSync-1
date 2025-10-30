#!/usr/bin/env python3
"""
Script para forçar execução da Migration 48 em produção
USO: python3 force_migration_48.py
"""
import os
import sys
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def force_migration_48():
    """Força execução da Migration 48"""
    
    # Importar após configurar logging
    from app import app, db
    from migrations import _migration_48_adicionar_admin_id_modelos_faltantes
    
    with app.app_context():
        try:
            logger.info("=" * 80)
            logger.info("🚀 FORÇANDO EXECUÇÃO DA MIGRATION 48")
            logger.info("=" * 80)
            logger.info("")
            logger.info("⚠️  ATENÇÃO: Este script irá modificar o banco de dados")
            logger.info("⚠️  Certifique-se de ter um BACKUP antes de continuar")
            logger.info("")
            
            # Confirmar execução
            if '--force' not in sys.argv:
                resposta = input("🔐 Digite 'EXECUTAR' para confirmar: ")
                if resposta != 'EXECUTAR':
                    logger.info("❌ Execução cancelada pelo usuário")
                    return False
            
            logger.info("🔄 Executando Migration 48...")
            logger.info("")
            
            # Executar migration
            _migration_48_adicionar_admin_id_modelos_faltantes()
            
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ MIGRATION 48 EXECUTADA COM SUCESSO")
            logger.info("=" * 80)
            logger.info("")
            logger.info("📋 Próximos passos:")
            logger.info("1. Execute: python3 validate_migration_48.py")
            logger.info("2. Teste a aplicação")
            logger.info("3. Verifique logs de erros")
            
            return True
            
        except Exception as e:
            logger.error("")
            logger.error("=" * 80)
            logger.error("❌ ERRO AO EXECUTAR MIGRATION 48")
            logger.error("=" * 80)
            logger.error(f"Erro: {e}")
            logger.error("")
            logger.error("🔄 ROLLBACK NECESSÁRIO:")
            logger.error("Execute: python3 rollback_migration_48.py")
            
            import traceback
            traceback.print_exc()
            
            return False

if __name__ == "__main__":
    try:
        if '--help' in sys.argv:
            print("""
USO: python3 force_migration_48.py [--force]

Força a execução da Migration 48 que adiciona admin_id em:
- rdo_mao_obra
- funcao
- registro_alimentacao
- E outras 17 tabelas

OPÇÕES:
  --force    Executa sem confirmação interativa
  --help     Mostra esta ajuda

IMPORTANTE:
  Faça backup do banco ANTES de executar!
  
EXEMPLO:
  # Com confirmação
  python3 force_migration_48.py
  
  # Sem confirmação (automatizado)
  python3 force_migration_48.py --force
""")
            sys.exit(0)
        
        success = force_migration_48()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n❌ Execução cancelada pelo usuário (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
