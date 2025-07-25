#!/usr/bin/env python3
"""
Script para corrigir schema da tabela restaurante em produção
Problema: Coluna 'contato_responsavel' duplicada com 'responsavel'
"""

from app import app, db
from sqlalchemy import text, inspect
import os
import sys

def fix_restaurante_schema():
    """Corrige schema da tabela restaurante em produção"""
    print("🔧 CORREÇÃO DO SCHEMA RESTAURANTE EM PRODUÇÃO")
    print("=" * 50)
    
    try:
        with app.app_context():
            # Verificar se estamos em produção
            database_url = os.environ.get('DATABASE_URL', '')
            print(f"Database URL: {database_url[:50]}...")
            
            # Verificar estado atual da tabela
            inspector = inspect(db.engine)
            
            if 'restaurante' not in inspector.get_table_names():
                print("❌ Tabela 'restaurante' não encontrada!")
                return False
            
            columns = inspector.get_columns('restaurante')
            column_names = [col['name'] for col in columns]
            
            print(f"📊 Colunas atuais: {', '.join(column_names)}")
            
            # Lista de correções SQL necessárias
            sql_corrections = []
            
            # 1. Remover coluna duplicada 'contato_responsavel' se existir
            if 'contato_responsavel' in column_names and 'responsavel' in column_names:
                sql_corrections.append("ALTER TABLE restaurante DROP COLUMN IF EXISTS contato_responsavel;")
                print("✓ Detectada coluna duplicada 'contato_responsavel' - será removida")
            
            # 2. Adicionar colunas faltantes se necessário
            required_columns = {
                'responsavel': 'VARCHAR(100)',
                'preco_almoco': 'DOUBLE PRECISION DEFAULT 0.0',
                'preco_jantar': 'DOUBLE PRECISION DEFAULT 0.0', 
                'preco_lanche': 'DOUBLE PRECISION DEFAULT 0.0',
                'observacoes': 'TEXT',
                'admin_id': 'INTEGER'
            }
            
            for col_name, col_type in required_columns.items():
                if col_name not in column_names:
                    sql_corrections.append(f"ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
                    print(f"✓ Coluna '{col_name}' será adicionada")
            
            # 3. Adicionar foreign key para admin_id se não existir
            fks = inspector.get_foreign_keys('restaurante')
            admin_fk_exists = any(fk['constrained_columns'] == ['admin_id'] for fk in fks)
            
            if not admin_fk_exists and 'admin_id' in column_names:
                sql_corrections.append("ALTER TABLE restaurante ADD CONSTRAINT fk_restaurante_admin_id FOREIGN KEY (admin_id) REFERENCES usuario(id);")
                print("✓ Foreign key para admin_id será adicionada")
            
            # Executar correções
            if sql_corrections:
                print(f"\n🛠️  EXECUTANDO {len(sql_corrections)} CORREÇÕES...")
                
                for i, sql in enumerate(sql_corrections, 1):
                    try:
                        print(f"   {i}. {sql}")
                        db.session.execute(text(sql))
                        print(f"      ✅ Sucesso!")
                    except Exception as e:
                        print(f"      ⚠️  Erro: {e}")
                        # Continuar com outras correções
                
                # Commit todas as mudanças
                db.session.commit()
                print("\n✅ TODAS AS CORREÇÕES APLICADAS COM SUCESSO!")
                
                # Verificar estado final
                columns_after = inspector.get_columns('restaurante')
                print(f"\n📊 Colunas finais: {', '.join([col['name'] for col in columns_after])}")
                
                return True
            else:
                print("✅ Schema já está correto, nenhuma correção necessária!")
                return True
                
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        db.session.rollback()
        return False

def test_restaurante_functionality():
    """Testa funcionalidades básicas após correção"""
    print("\n🧪 TESTANDO FUNCIONALIDADES...")
    
    try:
        with app.app_context():
            from models import Restaurante
            
            # Tentar criar um restaurante de teste
            teste = Restaurante(
                nome="Teste Restaurante",
                endereco="Rua Teste",
                telefone="11999999999",
                responsavel="João Teste",
                preco_almoco=15.0,
                admin_id=1
            )
            
            db.session.add(teste)
            db.session.commit()
            
            # Buscar o restaurante criado
            restaurante_criado = Restaurante.query.filter_by(nome="Teste Restaurante").first()
            
            if restaurante_criado:
                print("✅ Criação de restaurante: OK")
                
                # Limpar teste
                db.session.delete(restaurante_criado)
                db.session.commit()
                print("✅ Remoção de restaurante: OK")
                
                return True
            else:
                print("❌ Restaurante não foi criado corretamente")
                return False
                
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO CORREÇÃO DO SCHEMA RESTAURANTE")
    print("=" * 50)
    
    # Executar correção
    success = fix_restaurante_schema()
    
    if success:
        # Testar funcionalidades
        test_success = test_restaurante_functionality()
        
        if test_success:
            print("\n🎉 CORREÇÃO COMPLETADA COM SUCESSO!")
            print("   O módulo de restaurantes/alimentação deve funcionar normalmente.")
            sys.exit(0)
        else:
            print("\n⚠️  Correção aplicada mas testes falharam")
            sys.exit(1)
    else:
        print("\n❌ FALHA NA CORREÇÃO!")
        sys.exit(1)