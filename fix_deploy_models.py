#!/usr/bin/env python3
"""
SCRIPT DE CORREÇÃO PARA DEPLOY EASYPANEL
Corrige problemas de dependências circulares e foreign keys
"""

import os
import sys
import traceback

# Adicionar caminho do app
sys.path.insert(0, '/app')

def main():
    print("🔧 SCRIPT DE CORREÇÃO PARA DEPLOY - SIGE v8.0")
    
    try:
        # Import básico
        from app import app, db
        
        print("✅ App importado com sucesso")
        
        with app.app_context():
            # 1. Dropar todas as tabelas (estratégia limpa)
            print("🗑️ Dropando todas as tabelas...")
            db.drop_all()
            
            # 2. Criar tabelas em ordem específica para evitar dependências
            print("🏗️ Criando tabelas em ordem correta...")
            
            # Import específico dos models para forçar ordem
            from models import (
                Usuario, TipoUsuario, Departamento, Funcao, HorarioTrabalho,
                Funcionario, Obra, RegistroPonto, TipoLancamento,
                RDO, AtividadeRDO, TipoAtividade
            )
            
            # Criar apenas as tabelas essenciais primeiro
            essencial_tables = [
                Usuario.__table__,
                Departamento.__table__,
                Funcao.__table__,
                HorarioTrabalho.__table__,
            ]
            
            for table in essencial_tables:
                table.create(db.engine, checkfirst=True)
                print(f"✅ Tabela {table.name} criada")
            
            # Criar tabelas dependentes
            dependent_tables = [
                Funcionario.__table__,
                Obra.__table__,
            ]
            
            for table in dependent_tables:
                table.create(db.engine, checkfirst=True)
                print(f"✅ Tabela {table.name} criada")
            
            # Criar resto das tabelas
            print("🏗️ Criando tabelas restantes...")
            db.create_all()
            
            # 3. Verificar tabelas criadas
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📊 Total de {len(tables)} tabelas criadas")
            
            # 4. Criar usuários administrativos
            print("👤 Criando usuários administrativos...")
            from werkzeug.security import generate_password_hash
            
            # Super Admin
            if not Usuario.query.filter_by(email='admin@sige.com').first():
                admin = Usuario(
                    username='admin',
                    email='admin@sige.com',
                    nome='Super Admin',
                    password_hash=generate_password_hash('admin123'),
                    tipo_usuario=TipoUsuario.SUPER_ADMIN,
                    ativo=True
                )
                db.session.add(admin)
                print("✅ Super Admin criado")
            
            # Admin Demo
            if not Usuario.query.filter_by(username='valeverde').first():
                admin_demo = Usuario(
                    username='valeverde',
                    email='valeverde@sige.com',
                    nome='Vale Verde Admin',
                    password_hash=generate_password_hash('admin123'),
                    tipo_usuario=TipoUsuario.ADMIN,
                    ativo=True
                )
                db.session.add(admin_demo)
                print("✅ Admin Demo criado")
            
            db.session.commit()
            
            # 5. Relatório final
            total_usuarios = Usuario.query.count()
            print(f"📊 Total de usuários: {total_usuarios}")
            
            print("✅ SCRIPT DE CORREÇÃO CONCLUÍDO COM SUCESSO!")
            return True
            
    except Exception as e:
        print(f"❌ ERRO no script de correção: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)