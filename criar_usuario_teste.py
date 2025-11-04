#!/usr/bin/env python3
"""
Script para criar usuário administrador de teste
"""
from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

def criar_usuario_admin():
    """Cria um usuário administrador de teste"""
    
    with app.app_context():
        # Credenciais do usuário de teste
        username = "admin_teste"
        email = "admin.teste@sige.com"
        senha = "Teste@2024"
        nome = "Administrador Teste"
        
        # Verificar se já existe
        usuario_existente = Usuario.query.filter(
            (Usuario.username == username) | (Usuario.email == email)
        ).first()
        
        if usuario_existente:
            print(f"⚠️  Usuário já existe!")
            print(f"   ID: {usuario_existente.id}")
            print(f"   Username: {usuario_existente.username}")
            print(f"   Email: {usuario_existente.email}")
            print(f"   Nome: {usuario_existente.nome}")
            print(f"   Tipo: {usuario_existente.tipo_usuario.value}")
            print("\n✅ USE ESTAS CREDENCIAIS:")
            print(f"   Username: {usuario_existente.username}")
            print(f"   Senha: Teste@2024")
            return usuario_existente.id
        
        # Criar novo usuário
        novo_usuario = Usuario(
            username=username,
            email=email,
            password_hash=generate_password_hash(senha),
            nome=nome,
            ativo=True,
            tipo_usuario=TipoUsuario.ADMIN,
            admin_id=None  # Admin não tem admin_id
        )
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        print("="*80)
        print("✅ USUÁRIO ADMINISTRADOR CRIADO COM SUCESSO!")
        print("="*80)
        print(f"\n📋 CREDENCIAIS DE ACESSO:")
        print(f"   Username: {username}")
        print(f"   Senha: {senha}")
        print(f"   Email: {email}")
        print(f"   Nome: {nome}")
        print(f"   ID: {novo_usuario.id}")
        print(f"   Tipo: ADMINISTRADOR")
        print("\n🔐 GUARDE ESTAS CREDENCIAIS!")
        print("="*80)
        
        return novo_usuario.id

if __name__ == "__main__":
    admin_id = criar_usuario_admin()
    print(f"\n✅ Admin ID para usar no script de população: {admin_id}")
