"""
Migração para adicionar campos de organização avançada ao sistema de propostas
"""

import logging
from sqlalchemy import text
from app import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def executar_migracao_organizer():
    """Executa migração para adicionar campos de organização"""
    try:
        logger.info("🔄 Iniciando migração para organização avançada...")
        
        # Adicionar novos campos à tabela proposta_itens
        campos_organizer = [
            "ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS categoria_titulo VARCHAR(100)",
            "ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS template_origem_id INTEGER REFERENCES proposta_templates(id)",
            "ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS template_origem_nome VARCHAR(100)",
            "ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS grupo_ordem INTEGER DEFAULT 1",
            "ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS item_ordem_no_grupo INTEGER DEFAULT 1"
        ]
        
        for sql in campos_organizer:
            try:
                db.session.execute(text(sql))
                logger.info(f"✅ Executado: {sql}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"✅ Campo já existe: {sql}")
                else:
                    logger.error(f"❌ Erro ao executar: {sql} - {e}")
        
        db.session.commit()
        logger.info("✅ Migração de organização concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro na migração de organização: {e}")
        db.session.rollback()
        raise

if __name__ == "__main__":
    executar_migracao_organizer()