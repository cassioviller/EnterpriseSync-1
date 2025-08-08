#!/usr/bin/env python3
"""
Script para corrigir problemas de metadata da coluna foto_base64
"""

from app import app, db
from models import Funcionario
from sqlalchemy import text

def fix_metadata_foto_base64():
    """Corrige problemas de metadata da coluna foto_base64"""
    
    with app.app_context():
        try:
            print("🔧 Verificando e corrigindo metadata da coluna foto_base64...")
            
            # Verificar se a coluna existe no banco
            result = db.session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'funcionario' 
                AND column_name = 'foto_base64'
            """)).fetchone()
            
            if not result:
                print("❌ Coluna foto_base64 não existe no banco!")
                print("🔧 Criando coluna...")
                db.session.execute(text("ALTER TABLE funcionario ADD COLUMN foto_base64 TEXT"))
                db.session.commit()
                print("✅ Coluna foto_base64 criada!")
            else:
                print(f"✅ Coluna foto_base64 existe: {result[1]}")
            
            # Limpar cache de metadata do SQLAlchemy
            print("🔄 Limpando cache de metadata...")
            db.metadata.clear()
            
            # Refletir tabelas do banco
            print("🔄 Refletindo estrutura do banco...")
            db.metadata.reflect(bind=db.engine)
            
            # Testar acesso à coluna
            print("🧪 Testando acesso à coluna...")
            funcionario_teste = Funcionario.query.first()
            if funcionario_teste:
                # Tentar acessar a coluna foto_base64
                foto_base64 = funcionario_teste.foto_base64
                print(f"✅ Acesso à coluna funcionou! Valor: {'Existe' if foto_base64 else 'NULL'}")
            else:
                print("⚠️ Nenhum funcionário encontrado para teste")
            
            print("🎉 Metadata corrigida com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao corrigir metadata: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    fix_metadata_foto_base64()