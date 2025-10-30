#!/usr/bin/env python3
"""
Script mestre para executar todas as correções de admin_id
Executa os 3 scripts individuais em sequência
"""
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Executa todas as correções"""
    
    logger.info("=" * 80)
    logger.info("🚀 CORREÇÃO COMPLETA: admin_id em 3 tabelas")
    logger.info("=" * 80)
    print()
    
    resultados = []
    
    # 1. Funcao
    logger.info("📋 1/3: Corrigindo funcao...")
    try:
        from fix_funcao_admin_id import fix_funcao_admin_id
        success = fix_funcao_admin_id()
        resultados.append(("funcao", success))
    except Exception as e:
        logger.error(f"❌ Erro em funcao: {e}")
        resultados.append(("funcao", False))
    print()
    
    # 2. rdo_mao_obra
    logger.info("📋 2/3: Corrigindo rdo_mao_obra...")
    try:
        from fix_rdo_mao_obra_admin_id import fix_rdo_mao_obra_admin_id
        success = fix_rdo_mao_obra_admin_id()
        resultados.append(("rdo_mao_obra", success))
    except Exception as e:
        logger.error(f"❌ Erro em rdo_mao_obra: {e}")
        resultados.append(("rdo_mao_obra", False))
    print()
    
    # 3. registro_alimentacao
    logger.info("📋 3/3: Corrigindo registro_alimentacao...")
    try:
        from fix_registro_alimentacao_admin_id import fix_registro_alimentacao_admin_id
        success = fix_registro_alimentacao_admin_id()
        resultados.append(("registro_alimentacao", success))
    except Exception as e:
        logger.error(f"❌ Erro em registro_alimentacao: {e}")
        resultados.append(("registro_alimentacao", False))
    print()
    
    # Resumo
    logger.info("=" * 80)
    logger.info("📊 RESUMO DA CORREÇÃO")
    logger.info("=" * 80)
    
    sucesso = sum(1 for _, ok in resultados if ok)
    total = len(resultados)
    
    for tabela, ok in resultados:
        status = "✅" if ok else "❌"
        logger.info(f"{status} {tabela}")
    
    logger.info("-" * 80)
    logger.info(f"Total: {sucesso}/{total} tabelas corrigidas")
    
    if sucesso == total:
        logger.info("✅ TODAS as tabelas corrigidas com sucesso!")
        logger.info("")
        logger.info("🔄 Próximo passo: Reiniciar aplicação")
        logger.info("   supervisorctl restart all")
        return True
    else:
        logger.warning(f"⚠️  Apenas {sucesso}/{total} tabelas corrigidas")
        logger.warning("   Verifique os erros acima")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
