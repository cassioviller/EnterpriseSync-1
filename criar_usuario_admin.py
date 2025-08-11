"""
Script para criar usuário administrador padrão
"""

from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

def criar_admin():
    with app.app_context():
        # Verificar se já existe admin
        admin_existe = Usuario.query.filter_by(email='admin@sige.com').first()
        
        if not admin_existe:
            # Criar usuário admin
            admin = Usuario(
                nome='Administrador SIGE',
                email='admin@sige.com',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.SUPER_ADMIN,
                ativo=True
            )
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Usuário administrador criado com sucesso!")
            print("📧 Email: admin@sige.com")
            print("🔑 Senha: admin123")
        else:
            print("ℹ️ Usuário administrador já existe")

if __name__ == '__main__':
    criar_admin()