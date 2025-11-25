#!/usr/bin/env python3
"""
CORREÇÃO IMEDIATA PARA PRODUÇÃO - BANCO DE DADOS
Executa diretamente via SQL para corrigir nomes das subatividades
Data: 08/09/2025 - 19:05
"""

import os
import sys
import psycopg2
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚨 CORREÇÃO IMEDIATA PRODUÇÃO - BANCO DIRETO")
    
    try:
        # URL do banco de produção (EasyPanel)
        # Substitua pela URL correta do seu banco de produção
        DATABASE_URL_PROD = "postgresql://viajey_sige:5432@sige-db/viajey_sige"
        
        logger.info("🔌 Conectando ao banco de produção...")
        conn = psycopg2.connect(DATABASE_URL_PROD)
        cursor = conn.cursor()
        
        logger.info("✅ Conectado ao banco de produção!")
        
        # === 1. IDENTIFICAR ADMIN_ID CORRETO ===
        cursor.execute("SELECT id, email FROM usuario WHERE ativo = true ORDER BY id")
        admins = cursor.fetchall()
        logger.info(f"👥 Admins encontrados: {admins}")
        
        # Admin_id de produção (geralmente 2)
        admin_id_prod = 2
        logger.info(f"🎯 Usando admin_id de produção: {admin_id_prod}")
        
        # === 2. DIAGNÓSTICO ATUAL ===
        cursor.execute("""
            SELECT COUNT(*) FROM rdo_servico_subatividade 
            WHERE nome_subatividade LIKE 'Subatividade %' 
            AND admin_id = %s
        """, (admin_id_prod,))
        
        total_erradas = cursor.fetchone()[0]
        logger.info(f"📊 Subatividades com nome errado: {total_erradas}")
        
        # === 3. APLICAR CORREÇÕES MASSIVAS ===
        logger.info("🔧 APLICANDO CORREÇÕES MASSIVAS...")
        
        # Mapeamento completo para produção (IDs 150-165)
        correcoes = {
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
        for nome_errado, nome_correto in correcoes.items():
            cursor.execute("""
                UPDATE rdo_servico_subatividade 
                SET nome_subatividade = %s
                WHERE nome_subatividade = %s 
                AND admin_id = %s
            """, (nome_correto, nome_errado, admin_id_prod))
            
            corrigidas = cursor.rowcount
            total_corrigidas += corrigidas
            if corrigidas > 0:
                logger.info(f"✅ {corrigidas} registros: '{nome_errado}' → '{nome_correto}'")
        
        logger.info(f"📊 TOTAL DE CORREÇÕES: {total_corrigidas} subatividades renomeadas")
        
        # === 4. VERIFICAÇÃO FINAL ===
        cursor.execute("""
            SELECT COUNT(*) FROM rdo_servico_subatividade 
            WHERE nome_subatividade LIKE 'Subatividade %' 
            AND admin_id = %s
        """, (admin_id_prod,))
        
        ainda_erradas = cursor.fetchone()[0]
        logger.info(f"📊 Subatividades ainda com nome errado: {ainda_erradas}")
        
        # === 5. MOSTRAR ESTATÍSTICAS ===
        cursor.execute("""
            SELECT nome_subatividade, COUNT(*) 
            FROM rdo_servico_subatividade 
            WHERE admin_id = %s 
            GROUP BY nome_subatividade 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """, (admin_id_prod,))
        
        estatisticas = cursor.fetchall()
        logger.info("📊 TOP 10 SUBATIVIDADES MAIS USADAS:")
        for nome, count in estatisticas:
            logger.info(f"  📝 {nome}: {count} registros")
        
        # Commit das mudanças
        conn.commit()
        logger.info("💾 CORREÇÕES COMMITADAS COM SUCESSO!")
        
        # Fechar conexões
        cursor.close()
        conn.close()
        
        logger.info("🎯 CORREÇÃO IMEDIATA FINALIZADA!")
        logger.info("📋 RESULTADO:")
        logger.info(f"  ✅ {total_corrigidas} subatividades corrigidas")
        logger.info(f"  ❌ {ainda_erradas} ainda precisam de correção")
        logger.info("  🚀 Teste agora no sistema de produção!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO NA CORREÇÃO: {str(e)}")
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)