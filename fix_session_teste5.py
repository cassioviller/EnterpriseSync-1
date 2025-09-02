#!/usr/bin/env python3
"""
Script para forçar login correto do usuário teste5
"""

from models import db, Usuario
from werkzeug.security import generate_password_hash

def fix_user_session():
    # Buscar usuário teste5
    user = Usuario.query.filter_by(username='teste5').first()
    
    if user:
        print(f"✅ Usuário encontrado: {user.username} (ID: {user.id})")
        print(f"   - Admin ID: {user.admin_id}")
        print(f"   - Tipo: {user.tipo_usuario}")
        print(f"   - Email: {user.email}")
        
        # Recriar senha para garantir
        user.password_hash = generate_password_hash('123456')
        db.session.commit()
        
        print("✅ Senha reconfigurada: 123456")
        print("🔄 Faça logout e login novamente")
        
        return True
    else:
        print("❌ Usuário teste5 não encontrado")
        return False

if __name__ == "__main__":
    fix_user_session()