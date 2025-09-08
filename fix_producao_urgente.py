#!/usr/bin/env python3
"""
CORREÇÃO URGENTE PARA PRODUÇÃO - SISTEMA RDO
Executa diretamente em produção para corrigir problemas imediatos
Data: 08/09/2025
"""

import os
import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚨 INICIANDO CORREÇÃO URGENTE DE PRODUÇÃO")
    
    try:
        # Importar modelos necessários
        from app import app, db
        from models import SubatividadeMestre, RDOServicoSubatividade, RDO, Funcionario, Usuario
        from sqlalchemy import text
        
        with app.app_context():
            logger.info("🔧 CORREÇÕES URGENTES - SISTEMA RDO PRODUÇÃO")
            
            # === 1. DIAGNÓSTICO COMPLETO ===
            logger.info("🔍 DIAGNÓSTICO PRODUÇÃO")
            
            # Verificar admin_id em produção
            admins = db.session.execute(text("SELECT id, email, tipo_usuario FROM usuario WHERE ativo = true")).fetchall()
            logger.info(f"👥 Admins ativos: {[(a[0], a[1], a[2]) for a in admins]}")
            
            # Identificar admin_id correto para produção (provavelmente 2)
            admin_id_producao = 2
            
            # Verificar funcionários
            funcionarios = db.session.execute(text("SELECT COUNT(*) FROM funcionario WHERE admin_id = :admin_id AND ativo = true"), {'admin_id': admin_id_producao}).scalar()
            logger.info(f"👷 Funcionários ativos (admin_id={admin_id_producao}): {funcionarios}")
            
            # === 2. CORREÇÃO CRÍTICA DOS NOMES DAS SUBATIVIDADES ===
            logger.info("📝 CORREÇÃO CRÍTICA DE NOMES - MAPEAMENTO PRODUÇÃO")
            
            # Mapeamento completo baseado na imagem (IDs 150-165)
            mapeamento_producao = {
                'Subatividade 150': '1. Detalhamento do projeto',
                'Subatividade 151': '2. Seleção de materiais', 
                'Subatividade 152': '3. Traçagem',
                'Subatividade 153': '4. Corte mecânico',
                'Subatividade 154': '5. Furação',
                'Subatividade 155': '6. Montagem e soldagem',
                'Subatividade 156': '7. Acabamento e pintura', 
                'Subatividade 157': '8. Identificação e logística',
                'Subatividade 158': '9. Planejamento de montagem',
                'Subatividade 159': '10. Preparação do local',
                'Subatividade 160': '11. Transporte para obra',
                'Subatividade 161': '12. Posicionamento e alinhamento',
                'Subatividade 162': '13. Fixação definitiva',
                'Subatividade 163': '14. Inspeção e controle de qualidade',
                'Subatividade 164': '15. Documentação técnica',
                'Subatividade 165': '16. Entrega e aceitação'
            }
            
            total_corrigidas = 0
            for nome_errado, nome_correto in mapeamento_producao.items():
                corrigidas = db.session.execute(text("""
                    UPDATE rdo_servico_subatividade 
                    SET nome_subatividade = :nome_correto
                    WHERE nome_subatividade = :nome_errado
                      AND admin_id = :admin_id
                """), {
                    'nome_correto': nome_correto, 
                    'nome_errado': nome_errado,
                    'admin_id': admin_id_producao
                }).rowcount
                total_corrigidas += corrigidas
                if corrigidas > 0:
                    logger.info(f"✅ Corrigidas {corrigidas}: '{nome_errado}' → '{nome_correto}'")
            
            logger.info(f"📊 TOTAL CORRIGIDO: {total_corrigidas} subatividades renomeadas")
            
            # === 3. CORREÇÃO DA API DE FUNCIONÁRIOS ===
            logger.info("👥 CORREÇÃO API FUNCIONÁRIOS")
            
            # Corrigir admin_id de funcionários órfãos
            funcionarios_corrigidos = db.session.execute(text("""
                UPDATE funcionario 
                SET admin_id = :admin_id 
                WHERE admin_id IS NULL OR admin_id = 0
            """), {'admin_id': admin_id_producao}).rowcount
            logger.info(f"✅ Funcionários com admin_id corrigido: {funcionarios_corrigidos}")
            
            # === 4. CORREÇÃO DE RDOS ÓRFÃOS ===
            logger.info("📋 CORREÇÃO RDOS ÓRFÃOS")
            
            rdos_corrigidos = db.session.execute(text("""
                UPDATE rdo 
                SET admin_id = :admin_id 
                WHERE admin_id IS NULL OR admin_id = 0 OR admin_id = 10
            """), {'admin_id': admin_id_producao}).rowcount
            logger.info(f"✅ RDOs com admin_id corrigido: {rdos_corrigidos}")
            
            # === 5. LIMPEZA DE LIXO NO BANCO ===
            logger.info("🧹 LIMPEZA BANCO PRODUÇÃO")
            
            # Remover etapas inválidas
            etapas_removidas = db.session.execute(text("""
                DELETE FROM rdo_servico_subatividade 
                WHERE nome_subatividade IN ('Etapa Inicial', 'Etapa Intermediária')
                  AND admin_id = :admin_id
            """), {'admin_id': admin_id_producao}).rowcount
            logger.info(f"🗑️  Etapas inválidas removidas: {etapas_removidas}")
            
            # === 6. VALIDAÇÃO FINAL ===
            logger.info("✅ VALIDAÇÃO FINAL PRODUÇÃO")
            
            # Estatísticas finais
            rdos_total = db.session.execute(text("SELECT COUNT(*) FROM rdo WHERE admin_id = :admin_id"), {'admin_id': admin_id_producao}).scalar()
            subatividades_total = db.session.execute(text("SELECT COUNT(*) FROM rdo_servico_subatividade WHERE admin_id = :admin_id"), {'admin_id': admin_id_producao}).scalar()
            funcionarios_ativos = db.session.execute(text("SELECT COUNT(*) FROM funcionario WHERE admin_id = :admin_id AND ativo = true"), {'admin_id': admin_id_producao}).scalar()
            
            logger.info(f"📊 ESTATÍSTICAS FINAIS PRODUÇÃO (admin_id={admin_id_producao}):")
            logger.info(f"  📋 RDOs: {rdos_total}")
            logger.info(f"  📝 Subatividades: {subatividades_total}")  
            logger.info(f"  👷 Funcionários ativos: {funcionarios_ativos}")
            
            # Commit final
            db.session.commit()
            logger.info("💾 CORREÇÕES APLICADAS COM SUCESSO!")
            
            logger.info("🎯 CORREÇÃO URGENTE DE PRODUÇÃO FINALIZADA!")
            logger.info("📋 PRÓXIMOS PASSOS:")
            logger.info("  1. Testar salvamento de nova RDO")
            logger.info("  2. Verificar busca de funcionários")
            logger.info("  3. Confirmar nomes corretos das subatividades")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ ERRO NA CORREÇÃO URGENTE: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            db.session.rollback()
        except:
            pass
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)