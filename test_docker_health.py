#!/usr/bin/env python3
"""
Script para testar saúde do container Docker e banco de dados
"""

import os
import sys
from datetime import datetime

def test_environment():
    """Testa ambiente e configurações"""
    print("🔍 TESTE DE AMBIENTE - SIGE v8.0")
    print("=" * 50)
    
    # Variáveis de ambiente
    print("📋 Variáveis de Ambiente:")
    env_vars = ['DATABASE_URL', 'FLASK_APP', 'PORT', 'PGHOST', 'PGPORT', 'PGUSER', 'PGDATABASE']
    for var in env_vars:
        value = os.environ.get(var, 'NÃO DEFINIDA')
        if 'PASSWORD' in var or 'SECRET' in var:
            value = '*' * len(value) if value else 'NÃO DEFINIDA'
        print(f"   {var}: {value}")
    
    # Diretório atual
    print(f"\n📁 Diretório atual: {os.getcwd()}")
    
    # Arquivos importantes
    print("\n📄 Arquivos importantes:")
    important_files = ['app.py', 'models.py', 'views.py', 'main.py', 'requirements.txt', 'Dockerfile']
    for file in important_files:
        exists = "✅" if os.path.exists(file) else "❌"
        print(f"   {exists} {file}")
    
    # Testar importação
    print("\n🐍 Teste de Importação:")
    try:
        from app import app, db
        print("   ✅ app e db importados com sucesso")
        
        with app.app_context():
            # Testar conexão com banco
            try:
                result = db.engine.execute(db.text("SELECT 1")).fetchone()
                print("   ✅ Conexão com banco funcionando")
            except Exception as e:
                print(f"   ❌ Erro na conexão: {e}")
            
            # Testar criação de tabelas
            try:
                import models
                print("   ✅ Modelos importados")
                
                db.create_all()
                print("   ✅ db.create_all() executado")
                
                # Listar tabelas
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                print(f"   📊 Total de tabelas criadas: {len(tables)}")
                
                if len(tables) > 0:
                    print("   📋 Tabelas encontradas:")
                    for table in sorted(tables):
                        print(f"      • {table}")
                else:
                    print("   ⚠️ Nenhuma tabela encontrada")
                
            except Exception as e:
                print(f"   ❌ Erro ao criar tabelas: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        print(f"   ❌ Erro na importação: {e}")
        import traceback
        traceback.print_exc()

def test_database_direct():
    """Teste direto no banco PostgreSQL"""
    print("\n🗄️ TESTE DIRETO NO BANCO:")
    print("=" * 50)
    
    try:
        import psycopg2
        
        # Pegar URL do banco
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("   ❌ DATABASE_URL não definida")
            return
        
        # Conectar diretamente
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Testar conexão
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"   ✅ PostgreSQL conectado: {version[0][:50]}...")
        
        # Listar tabelas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"   📊 Tabelas no banco: {len(tables)}")
        
        if tables:
            for table in tables:
                print(f"      • {table[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Erro no teste direto: {e}")

if __name__ == "__main__":
    print(f"⏰ Executado em: {datetime.now()}")
    test_environment()
    test_database_direct()
    print("\n🏁 Teste concluído!")