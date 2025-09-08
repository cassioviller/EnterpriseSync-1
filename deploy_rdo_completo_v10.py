#!/usr/bin/env python3
"""
DEPLOY RDO COMPLETO v10.0 - Sistema SIGE
Correção completa de todo o sistema RDO
Data: 08/09/2025
Autor: Arquitetura Joris Kuypers
"""

import os
import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 INICIANDO DEPLOY RDO COMPLETO v10.0")
    
    try:
        # Importar modelos necessários
        from app import app, db
        from models import (
            SubatividadeMestre, RDOServicoSubatividade, RDO, Servico, 
            ServicoObraReal, Obra, Usuario, Funcionario
        )
        from sqlalchemy import text
        
        with app.app_context():
            logger.info("🔧 CORREÇÕES COMPLETAS DO SISTEMA RDO")
            
            # === FASE 1: LIMPEZA GERAL ===
            logger.info("🧹 FASE 1: LIMPEZA GERAL DO BANCO")
            
            # 1.1 Remover subatividades duplicadas
            duplicadas_removidas = db.session.execute(text("""
                DELETE FROM subatividade_mestre 
                WHERE nome IN ('Etapa Inicial', 'Etapa Intermediária')
                  AND id NOT IN (
                    SELECT DISTINCT sm.id FROM subatividade_mestre sm
                    INNER JOIN servico s ON sm.servico_id = s.id
                    WHERE sm.nome NOT IN ('Etapa Inicial', 'Etapa Intermediária')
                      AND s.ativo = true
                    ORDER BY sm.id
                  )
            """)).rowcount
            logger.info(f"✅ Removidas {duplicadas_removidas} subatividades duplicadas")
            
            # 1.2 Limpar RDOs órfãos
            rdos_orfaos = db.session.execute(text("""
                DELETE FROM rdo_servico_subatividade 
                WHERE rdo_id NOT IN (SELECT id FROM rdo)
            """)).rowcount
            logger.info(f"✅ Removidas {rdos_orfaos} subatividades RDO órfãs")
            
            # === FASE 2: CORREÇÕES DE INTEGRIDADE ===
            logger.info("🔗 FASE 2: CORREÇÕES DE INTEGRIDADE")
            
            # 2.1 Corrigir admin_id em RDOs
            rdos_corrigidos = db.session.execute(text("""
                UPDATE rdo SET admin_id = (
                    SELECT o.admin_id FROM obra o WHERE o.id = rdo.obra_id
                ) WHERE admin_id IS NULL OR admin_id = 0
            """)).rowcount
            logger.info(f"✅ Corrigidos {rdos_corrigidos} RDOs com admin_id inválido")
            
            # 2.2 Corrigir servico_id em subatividades RDO
            subatividades_servico_corrigidas = db.session.execute(text("""
                UPDATE rdo_servico_subatividade rss
                SET servico_id = sor.servico_id
                FROM servico_obra_real sor
                INNER JOIN rdo r ON r.obra_id = sor.obra_id
                WHERE rss.rdo_id = r.id 
                  AND (rss.servico_id IS NULL OR rss.servico_id = 0)
                  AND sor.ativo = true
            """)).rowcount
            logger.info(f"✅ Corrigidas {subatividades_servico_corrigidas} subatividades com servico_id inválido")
            
            # === FASE 3: CORREÇÃO DE NOMES ===
            logger.info("📝 FASE 3: CORREÇÃO DE NOMES DAS SUBATIVIDADES")
            
            # 3.1 Mapeamento completo de nomes incorretos
            mapeamento_nomes = {
                'Subatividade 440': 'Preparação da Estrutura',
                'Subatividade 441': 'Instalação de Terças', 
                'Subatividade 442': 'Colocação das Telhas',
                'Subatividade 443': 'Vedação e Calhas',
                'Subatividade 15236': 'Preparação da Estrutura',
                'Subatividade 15237': 'Instalação de Terças',
                'Subatividade 15238': 'Colocação das Telhas', 
                'Subatividade 15239': 'Vedação e Calhas',
                'Etapa Inicial': None,  # Remover completamente
                'Etapa Intermediária': None,  # Remover completamente
            }
            
            total_corrigidas = 0
            total_removidas = 0
            
            for nome_errado, nome_correto in mapeamento_nomes.items():
                if nome_correto is None:
                    # Remover subatividades inválidas
                    removidas = db.session.execute(text("""
                        DELETE FROM rdo_servico_subatividade 
                        WHERE nome_subatividade = :nome_errado
                    """), {'nome_errado': nome_errado}).rowcount
                    total_removidas += removidas
                    logger.info(f"🗑️  Removidas {removidas} subatividades '{nome_errado}'")
                else:
                    # Corrigir nomes
                    corrigidas = db.session.execute(text("""
                        UPDATE rdo_servico_subatividade 
                        SET nome_subatividade = :nome_correto
                        WHERE nome_subatividade = :nome_errado
                    """), {'nome_correto': nome_correto, 'nome_errado': nome_errado}).rowcount
                    total_corrigidas += corrigidas
                    if corrigidas > 0:
                        logger.info(f"✅ Corrigidas {corrigidas}: '{nome_errado}' → '{nome_correto}'")
            
            logger.info(f"📊 TOTAL: {total_corrigidas} nomes corrigidos, {total_removidas} subatividades removidas")
            
            # === FASE 4: OTIMIZAÇÕES E VALIDAÇÕES ===
            logger.info("🔍 FASE 4: OTIMIZAÇÕES E VALIDAÇÕES")
            
            # 4.1 Atualizar percentuais inconsistentes
            percentuais_corrigidos = db.session.execute(text("""
                UPDATE rdo_servico_subatividade 
                SET percentual_conclusao = 0 
                WHERE percentual_conclusao < 0 OR percentual_conclusao > 100
            """)).rowcount
            logger.info(f"✅ Corrigidos {percentuais_corrigidos} percentuais inválidos")
            
            # 4.2 Remover registros duplicados
            duplicadas_rdo_removidas = db.session.execute(text("""
                DELETE FROM rdo_servico_subatividade rss1
                WHERE EXISTS (
                    SELECT 1 FROM rdo_servico_subatividade rss2
                    WHERE rss2.rdo_id = rss1.rdo_id 
                      AND rss2.nome_subatividade = rss1.nome_subatividade
                      AND rss2.servico_id = rss1.servico_id
                      AND rss2.id > rss1.id
                )
            """)).rowcount
            logger.info(f"✅ Removidas {duplicadas_rdo_removidas} subatividades RDO duplicadas")
            
            # === FASE 5: RELATÓRIO FINAL ===
            logger.info("📊 FASE 5: RELATÓRIO FINAL DO SISTEMA")
            
            # Estatísticas gerais
            stats = {}
            stats['total_rdos'] = db.session.execute(text("SELECT COUNT(*) FROM rdo")).scalar()
            stats['total_subatividades_rdo'] = db.session.execute(text("SELECT COUNT(*) FROM rdo_servico_subatividade")).scalar()
            stats['total_subatividades_mestre'] = db.session.execute(text("SELECT COUNT(*) FROM subatividade_mestre")).scalar()
            stats['rdos_por_admin'] = db.session.execute(text("""
                SELECT admin_id, COUNT(*) FROM rdo GROUP BY admin_id ORDER BY admin_id
            """)).fetchall()
            
            logger.info("📈 ESTATÍSTICAS FINAIS:")
            logger.info(f"  📋 RDOs totais: {stats['total_rdos']}")
            logger.info(f"  📝 Subatividades RDO: {stats['total_subatividades_rdo']}")
            logger.info(f"  🎯 Subatividades Mestre: {stats['total_subatividades_mestre']}")
            
            logger.info("👥 RDOs por Admin:")
            for admin_id, count in stats['rdos_por_admin']:
                logger.info(f"  Admin {admin_id}: {count} RDOs")
            
            # Validação de integridade final
            problemas = []
            
            # RDOs sem subatividades
            rdos_vazios = db.session.execute(text("""
                SELECT COUNT(*) FROM rdo r 
                LEFT JOIN rdo_servico_subatividade rss ON r.id = rss.rdo_id 
                WHERE rss.id IS NULL
            """)).scalar()
            if rdos_vazios > 0:
                problemas.append(f"{rdos_vazios} RDOs sem subatividades")
            
            # Subatividades com nomes genéricos restantes
            nomes_genericos = db.session.execute(text("""
                SELECT COUNT(*) FROM rdo_servico_subatividade 
                WHERE nome_subatividade LIKE 'Subatividade %'
            """)).scalar()
            if nomes_genericos > 0:
                problemas.append(f"{nomes_genericos} subatividades com nomes genéricos")
            
            if problemas:
                logger.warning("⚠️  PROBLEMAS DETECTADOS:")
                for problema in problemas:
                    logger.warning(f"  - {problema}")
            else:
                logger.info("✅ Nenhum problema de integridade detectado")
            
            # Commit final
            db.session.commit()
            logger.info("💾 Todas as correções foram aplicadas com sucesso!")
            
            logger.info("🎯 DEPLOY RDO COMPLETO v10.0 FINALIZADO COM SUCESSO!")
            return True
            
    except Exception as e:
        logger.error(f"❌ ERRO NO DEPLOY RDO COMPLETO: {str(e)}")
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