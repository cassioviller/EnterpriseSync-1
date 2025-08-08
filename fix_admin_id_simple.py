#!/usr/bin/env python3
"""
Script Simples: Corrigir admin_id em Produção
Execute este script diretamente no servidor após o deploy
"""

from app import app, db
from sqlalchemy import text

def fix_admin_id():
    with app.app_context():
        try:
            print("🔍 Verificando coluna admin_id...")
            
            # Verificar se admin_id existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'admin_id'
            """))
            
            if not result.fetchone():
                print("❌ Coluna admin_id não existe - adicionando...")
                
                # Adicionar coluna
                db.session.execute(text("ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER"))
                
                # Atualizar registros
                updated = db.session.execute(text("""
                    UPDATE outro_custo 
                    SET admin_id = (
                        SELECT admin_id 
                        FROM funcionario 
                        WHERE funcionario.id = outro_custo.funcionario_id
                        LIMIT 1
                    )
                    WHERE admin_id IS NULL
                """)).rowcount
                
                db.session.commit()
                print(f"✅ Correção aplicada - {updated} registros atualizados")
            else:
                print("✅ Coluna admin_id já existe")
                
            # Verificar resultado
            count = db.session.execute(text("SELECT COUNT(*) FROM outro_custo WHERE admin_id IS NOT NULL")).scalar()
            print(f"📊 Total de registros com admin_id: {count}")
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    fix_admin_id()