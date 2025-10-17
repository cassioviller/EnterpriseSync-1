#!/usr/bin/env python3
"""
Script para resetar senha de admin para testes
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Usuario
from werkzeug.security import generate_password_hash

def resetar_senha():
    """Reseta a senha do admin Vale Verde (ID 10)"""
    
    print("\n" + "="*60)
    print("🔑 RESETAR SENHA - ADMIN VALE VERDE")
    print("="*60 + "\n")
    
    try:
        with app.app_context():
            # Buscar admin
            admin = Usuario.query.filter_by(id=10).first()
            
            if not admin:
                print("❌ Admin com ID 10 não encontrado!")
                return 1
            
            # Nova senha
            nova_senha = "admin123"
            
            # Gerar hash
            admin.password_hash = generate_password_hash(nova_senha)
            
            # Salvar
            db.session.commit()
            
            print("✅ Senha resetada com sucesso!")
            print(f"\n📋 Credenciais de acesso:")
            print(f"   👤 Username: {admin.username}")
            print(f"   📧 Email: {admin.email}")
            print(f"   🔑 Senha: {nova_senha}")
            print(f"   🏢 Empresa: {admin.nome}")
            print(f"   🎭 Tipo: {admin.tipo_usuario.value}")
            print(f"\n🌐 Acesse: http://localhost:5000/login")
            print("="*60 + "\n")
            
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(resetar_senha())
