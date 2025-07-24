#!/usr/bin/env python3
"""
Script para criar usuário superadmin automaticamente
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

import os
from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

def criar_superadmin():
    """Cria usuário superadmin se não existir"""
    
    with app.app_context():
        try:
            # Configurações do superadmin via variáveis de ambiente
            admin_email = os.environ.get("SUPERADMIN_EMAIL", "admin@sige.com")
            admin_password = os.environ.get("SUPERADMIN_PASSWORD", "admin123")
            admin_nome = os.environ.get("SUPERADMIN_NAME", "Super Admin")
            admin_username = os.environ.get("SUPERADMIN_USERNAME", "admin")
            
            # Verificar se já existe um superadmin
            existing_admin = Usuario.query.filter_by(email=admin_email).first()
            
            if not existing_admin:
                # Verificar se já existe algum superadmin
                existing_superadmin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
                
                if existing_superadmin:
                    print(f'☑️ Já existe um usuário superadmin: {existing_superadmin.email}')
                    return True
                
                # Criar hash da senha
                password_hash = generate_password_hash(admin_password)
                
                # Criar novo superadmin
                new_admin = Usuario(
                    username=admin_username,
                    email=admin_email,
                    nome=admin_nome,
                    password_hash=password_hash,
                    tipo_usuario=TipoUsuario.SUPER_ADMIN,
                    ativo=True,
                    admin_id=None  # Superadmin não tem admin pai
                )
                
                db.session.add(new_admin)
                db.session.commit()
                
                print(f'✅ Usuário superadmin criado com sucesso!')
                print(f'   Email: {admin_email}')
                print(f'   Username: {admin_username}')
                print(f'   Nome: {admin_nome}')
                print(f'   Senha: {admin_password}')
                return True
                
            else:
                print(f'☑️ Usuário superadmin já existe: {admin_email}')
                # Atualizar tipo se necessário
                if existing_admin.tipo_usuario != TipoUsuario.SUPER_ADMIN:
                    existing_admin.tipo_usuario = TipoUsuario.SUPER_ADMIN
                    existing_admin.ativo = True
                    db.session.commit()
                    print(f'✅ Tipo de usuário atualizado para SUPER_ADMIN')
                return True
                
        except Exception as e:
            print(f'❌ Erro ao criar/verificar superadmin: {e}')
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("👤 CRIAÇÃO DE USUÁRIO SUPERADMIN - SIGE v8.0")
    print("=" * 50)
    
    resultado = criar_superadmin()
    
    if resultado:
        print("\n🎯 Superadmin configurado com sucesso!")
        print("\nCredenciais de acesso:")
        print(f"   Email: {os.environ.get('SUPERADMIN_EMAIL', 'admin@sige.com')}")
        print(f"   Senha: {os.environ.get('SUPERADMIN_PASSWORD', 'admin123')}")
    else:
        print("\n❌ Falha na configuração do superadmin")
        exit(1)