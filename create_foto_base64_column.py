#!/usr/bin/env python3
"""
Script para criar a coluna foto_base64 se ela não existir
Para ser executado em produção via migration
"""

import os
import sys
from app import app, db
from sqlalchemy import text

def create_foto_base64_column():
    """Cria a coluna foto_base64 se ela não existir"""
    
    with app.app_context():
        try:
            # Verificar se a coluna já existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'funcionario' 
                AND column_name = 'foto_base64'
            """)).fetchone()
            
            if result:
                print("✅ Coluna foto_base64 já existe!")
                return True
            
            # Criar a coluna se não existir
            print("🔧 Criando coluna foto_base64...")
            db.session.execute(text("ALTER TABLE funcionario ADD COLUMN foto_base64 TEXT"))
            db.session.commit()
            print("✅ Coluna foto_base64 criada com sucesso!")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao criar coluna: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = create_foto_base64_column()
    sys.exit(0 if success else 1)