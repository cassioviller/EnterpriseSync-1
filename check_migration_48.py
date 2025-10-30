#!/usr/bin/env python3
"""
Script para verificar status da Migration 48 em produção
"""
import os
import sys
from sqlalchemy import create_engine, text

def check_migration_48():
    """Verifica se Migration 48 foi executada e se colunas existem"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL não encontrada")
        sys.exit(1)
    
    engine = create_engine(database_url)
    
    print("=" * 80)
    print("🔍 VERIFICAÇÃO DE STATUS DA MIGRATION 48")
    print("=" * 80)
    print(f"📊 Database: {database_url.split('@')[1] if '@' in database_url else 'N/A'}")
    print()
    
    with engine.connect() as connection:
        # 1. Verificar histórico de migrations
        print("📋 Verificando histórico de migrations...")
        try:
            result = connection.execute(text("""
                SELECT migration_number, migration_name, executed_at, status 
                FROM migration_history 
                WHERE migration_number = 48
            """))
            
            row = result.fetchone()
            
            if row:
                print(f"✅ Migration 48 encontrada no histórico:")
                print(f"   Número: {row[0]}")
                print(f"   Nome: {row[1]}")
                print(f"   Executada em: {row[2]}")
                print(f"   Status: {row[3]}")
            else:
                print("❌ Migration 48 NÃO encontrada no histórico")
        except Exception as e:
            print(f"⚠️  Erro ao consultar migration_history: {e}")
        
        print()
        
        # 2. Verificar se colunas admin_id existem
        print("📋 Verificando colunas admin_id nas tabelas...")
        print()
        
        tabelas = ['rdo_mao_obra', 'funcao', 'registro_alimentacao']
        tabelas_ok = 0
        tabelas_faltando = []
        
        for tabela in tabelas:
            result = connection.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = :tabela AND column_name = 'admin_id'
            """), {"tabela": tabela})
            
            col_info = result.fetchone()
            
            if col_info:
                print(f"✅ {tabela}.admin_id EXISTE")
                print(f"   Tipo: {col_info[1]}")
                print(f"   Nullable: {col_info[2]}")
                tabelas_ok += 1
                
                # Contar registros
                result_count = connection.execute(text(f"SELECT COUNT(*) FROM {tabela}"))
                total = result_count.scalar()
                
                result_null = connection.execute(text(f"SELECT COUNT(*) FROM {tabela} WHERE admin_id IS NULL"))
                nulls = result_null.scalar()
                
                print(f"   Total de registros: {total}")
                print(f"   Registros NULL: {nulls}")
            else:
                print(f"❌ {tabela}.admin_id NÃO EXISTE")
                tabelas_faltando.append(tabela)
            
            print()
        
        # 3. Resumo
        print("=" * 80)
        print("📊 RESUMO")
        print("=" * 80)
        print(f"Tabelas com admin_id: {tabelas_ok}/3")
        print(f"Tabelas faltando admin_id: {len(tabelas_faltando)}/3")
        
        if tabelas_faltando:
            print(f"\n❌ Tabelas que precisam da Migration 48:")
            for tabela in tabelas_faltando:
                print(f"   - {tabela}")
            print("\n🔧 AÇÃO NECESSÁRIA: Executar Migration 48")
            return False
        else:
            print("\n✅ TODAS as tabelas têm admin_id")
            print("✅ Migration 48 completada com sucesso")
            return True

if __name__ == "__main__":
    try:
        success = check_migration_48()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
