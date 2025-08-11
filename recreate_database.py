"""
Script para recriar completamente o banco de dados do SIGE v8.0
Remove conflitos de estrutura e garante schema limpo
"""

import os
import sys

def recreate_database():
    """Recria o banco de dados do zero"""
    print("🔧 RECRIANDO BANCO DE DADOS SIGE v8.0")
    print("=" * 50)
    
    # Remover arquivo SQLite se existir
    db_files = ['sige.db', 'instance/sige.db', 'database.db']
    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"✅ Removido: {db_file}")
    
    # Remover migrations se existirem
    if os.path.exists('migrations'):
        import shutil
        shutil.rmtree('migrations')
        print("✅ Pasta migrations removida")
    
    # Criar novo banco com estrutura limpa
    try:
        from app import app, db
        
        with app.app_context():
            # Criar todas as tabelas
            db.create_all()
            print("✅ Banco de dados recriado com sucesso!")
            
            # Contar tabelas criadas
            from sqlalchemy import text
            result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            print(f"✅ {len(result)} tabelas criadas")
            
            # Listar algumas tabelas principais
            tables = [row[0] for row in result if not row[0].startswith('sqlite_')]
            print(f"📋 Tabelas: {', '.join(tables[:5])}...")
            
            # Criar usuário admin padrão se não existir
            from models import Usuario, TipoUsuario
            from werkzeug.security import generate_password_hash
            
            admin_exists = Usuario.query.filter_by(username='admin').first()
            if not admin_exists:
                admin = Usuario(
                    username='admin',
                    email='admin@sige.com',
                    password_hash=generate_password_hash('admin123'),
                    nome='Administrador',
                    tipo_usuario=TipoUsuario.ADMIN
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Usuário admin padrão criado (admin/admin123)")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro ao recriar banco: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = recreate_database()
    if success:
        print("\n🎉 BANCO RECRIADO COM SUCESSO!")
        print("🚀 Reinicie o servidor para aplicar as mudanças")
    else:
        print("\n❌ FALHA NA RECRIAÇÃO DO BANCO")
        sys.exit(1)