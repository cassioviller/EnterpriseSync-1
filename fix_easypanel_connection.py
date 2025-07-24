#!/usr/bin/env python3
"""
Script para resolver problemas de conexão no EasyPanel
Baseado nos logs da imagem fornecida
"""

import os
import sys
import time
from datetime import datetime

def check_database_connection():
    """Verifica e corrige conexão com banco"""
    print("🔍 DIAGNÓSTICO EASYPANEL - SIGE v8.0")
    print("=" * 50)
    print(f"⏰ Executado em: {datetime.now()}")
    
    # Variáveis de ambiente
    print("\n📋 VARIÁVEIS DE AMBIENTE:")
    db_url = os.environ.get('DATABASE_URL', 'NÃO DEFINIDA')
    print(f"   DATABASE_URL: {db_url[:50]}..." if len(db_url) > 50 else f"   DATABASE_URL: {db_url}")
    print(f"   PORT: {os.environ.get('PORT', 'NÃO DEFINIDA')}")
    print(f"   FLASK_APP: {os.environ.get('FLASK_APP', 'NÃO DEFINIDA')}")
    
    if db_url == 'NÃO DEFINIDA':
        print("❌ DATABASE_URL não está definida!")
        return False
    
    # Tentar importar aplicação
    print("\n🐍 TESTE DE IMPORTAÇÃO:")
    try:
        from app import app, db
        print("   ✅ App importado com sucesso")
        
        # Testar contexto da aplicação
        with app.app_context():
            print("   ✅ Contexto da aplicação ativo")
            
            # Testar conexão direta
            try:
                result = db.engine.execute(db.text("SELECT 1")).fetchone()
                print("   ✅ Conexão com PostgreSQL funcionando")
                
                # Importar modelos
                import models
                print("   ✅ Modelos importados")
                
                # Criar tabelas
                db.create_all()
                print("   ✅ Comando db.create_all() executado")
                
                # Verificar tabelas criadas
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                print(f"   📊 Total de tabelas: {len(tables)}")
                
                if len(tables) > 0:
                    print("   📋 Primeiras 10 tabelas:")
                    for i, table in enumerate(sorted(tables)[:10]):
                        print(f"      {i+1:2d}. {table}")
                    
                    if len(tables) > 10:
                        print(f"      ... e mais {len(tables) - 10} tabelas")
                    
                    # Criar usuário administrativo
                    create_admin_user()
                    
                    print("\n🎯 BANCO DE DADOS CONFIGURADO COM SUCESSO!")
                    return True
                else:
                    print("   ⚠️ Nenhuma tabela foi criada")
                    return False
                    
            except Exception as e:
                print(f"   ❌ Erro na conexão com banco: {e}")
                return False
                
    except Exception as e:
        print(f"   ❌ Erro na importação: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_admin_user():
    """Cria usuário administrativo"""
    print("\n👤 CRIANDO USUÁRIO ADMINISTRATIVO:")
    
    try:
        from models import Usuario, TipoUsuario
        from werkzeug.security import generate_password_hash
        from app import db
        
        # Verificar se já existe
        existing_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
        
        if existing_admin:
            print(f"   ✅ Super Admin já existe: {existing_admin.email}")
        else:
            # Criar novo super admin
            admin = Usuario(
                nome='Super Administrador',
                username='admin',
                email='admin@sige.com',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.SUPER_ADMIN,
                ativo=True
            )
            db.session.add(admin)
            
            # Criar admin demo
            demo = Usuario(
                nome='Vale Verde Construções',
                username='valeverde',
                email='admin@valeverde.com',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True
            )
            db.session.add(demo)
            
            db.session.commit()
            print("   ✅ Super Admin criado: admin@sige.com / admin123")
            print("   ✅ Admin Demo criado: valeverde / admin123")
        
        # Contar usuários
        total_users = Usuario.query.count()
        print(f"   📊 Total de usuários no sistema: {total_users}")
        
    except Exception as e:
        print(f"   ❌ Erro ao criar usuário: {e}")

def main():
    """Função principal"""
    success = check_database_connection()
    
    if success:
        print("\n" + "="*50)
        print("🎉 SISTEMA SIGE v8.0 ATIVADO COM SUCESSO!")
        print("="*50)
        print("🔐 CREDENCIAIS DE ACESSO:")
        print("   Super Admin: admin@sige.com / admin123")
        print("   Admin Demo:  valeverde / admin123")
        print("\n🌐 Acesse sua URL do EasyPanel e faça login!")
    else:
        print("\n" + "="*50)
        print("❌ FALHA NA CONFIGURAÇÃO")
        print("="*50)
        print("📧 Envie os logs acima para o desenvolvedor")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)