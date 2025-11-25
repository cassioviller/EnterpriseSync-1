#!/usr/bin/env python3
"""
Migração para adicionar campo 'cliente' na tabela Obra
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def adicionar_campo_cliente():
    """Adiciona campo cliente na tabela obra se não existir"""
    
    with app.app_context():
        try:
            # Verificar se coluna já existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'obra' AND column_name = 'cliente'
            """)).fetchone()
            
            if not result:
                print("🔄 Adicionando campo 'cliente' na tabela obra...")
                db.session.execute(text("ALTER TABLE obra ADD COLUMN cliente VARCHAR(200)"))
                db.session.commit()
                print("✅ Campo 'cliente' adicionado com sucesso!")
            else:
                print("✅ Campo 'cliente' já existe na tabela obra")
                
        except Exception as e:
            print(f"❌ Erro na migração: {e}")
            db.session.rollback()

if __name__ == "__main__":
    adicionar_campo_cliente()