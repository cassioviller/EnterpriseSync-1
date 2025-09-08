#!/usr/bin/env python3
"""
DEPLOY FIX SUBATIVIDADES v10.0 - Sistema SIGE
Correção crítica para nomes incorretos de subatividades
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
    logger.info("🚀 INICIANDO DEPLOY FIX SUBATIVIDADES v10.0")
    
    try:
        # Importar modelos necessários
        from app import app, db
        from models import SubatividadeMestre
        from sqlalchemy import text
        
        with app.app_context():
            logger.info("🔧 1. LIMPEZA DE SUBATIVIDADES DUPLICADAS")
            
            # Remover subatividades duplicadas incorretas
            duplicadas_removidas = db.session.execute(text("""
                DELETE FROM subatividade_mestre 
                WHERE servico_id = 121 
                  AND nome IN ('Etapa Inicial', 'Etapa Intermediária')
                  AND id NOT IN (15236, 15237, 15238, 15239)
            """)).rowcount
            
            logger.info(f"✅ Removidas {duplicadas_removidas} subatividades duplicadas")
            
            logger.info("🔧 2. VALIDAÇÃO DAS SUBATIVIDADES CORRETAS")
            
            # Verificar se as subatividades corretas existem
            subatividades_corretas = db.session.execute(text("""
                SELECT id, nome FROM subatividade_mestre 
                WHERE servico_id = 121 
                  AND id IN (15236, 15237, 15238, 15239)
                ORDER BY id
            """)).fetchall()
            
            for sub in subatividades_corretas:
                logger.info(f"✅ Subatividade {sub[0]}: {sub[1]}")
            
            logger.info("🔧 3. APLICAÇÃO DE COMMIT")
            db.session.commit()
            
            logger.info("🔧 4. VERIFICAÇÃO FINAL")
            total_subatividades = db.session.execute(text("""
                SELECT COUNT(*) FROM subatividade_mestre WHERE servico_id = 121
            """)).scalar()
            
            logger.info(f"✅ Total de subatividades para serviço 121: {total_subatividades}")
            
            if total_subatividades == 4:
                logger.info("🎯 DEPLOY FIX CONCLUÍDO COM SUCESSO!")
                return True
            else:
                logger.error(f"❌ ERRO: Esperado 4 subatividades, encontradas {total_subatividades}")
                return False
                
    except Exception as e:
        logger.error(f"❌ ERRO NO DEPLOY FIX: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)