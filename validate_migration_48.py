#!/usr/bin/env python3
"""
Script para validar que Migration 48 foi executada corretamente
"""
import os
import sys
from sqlalchemy import create_engine, text

def validate_migration_48():
    """Valida execução completa da Migration 48"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL não encontrada")
        sys.exit(1)
    
    engine = create_engine(database_url)
    
    print("=" * 80)
    print("🔍 VALIDAÇÃO PÓS-MIGRATION 48")
    print("=" * 80)
    print()
    
    tabelas = ['rdo_mao_obra', 'funcao', 'registro_alimentacao']
    
    todas_ok = True
    resultados = []
    
    with engine.connect() as connection:
        for tabela in tabelas:
            print(f"📋 Tabela: {tabela}")
            print("-" * 80)
            
            status = {"tabela": tabela}
            
            # 1. Verificar coluna
            result = connection.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = :tabela AND column_name = 'admin_id'
            """), {"tabela": tabela})
            
            col_info = result.fetchone()
            
            if col_info:
                print(f"✅ Coluna admin_id existe")
                print(f"   Tipo: {col_info[1]}")
                print(f"   Nullable: {col_info[2]}")
                status["coluna"] = "✅"
                status["tipo"] = col_info[1]
                status["nullable"] = col_info[2]
            else:
                print(f"❌ Coluna admin_id NÃO existe")
                status["coluna"] = "❌"
                status["tipo"] = "N/A"
                status["nullable"] = "N/A"
                todas_ok = False
            
            # 2. Verificar foreign key
            result = connection.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = :tabela 
                  AND constraint_type = 'FOREIGN KEY'
                  AND constraint_name LIKE '%admin_id%'
            """), {"tabela": tabela})
            
            fk = result.fetchone()
            if fk:
                print(f"✅ Foreign key: {fk[0]}")
                status["fk"] = "✅"
            else:
                print(f"⚠️  Foreign key não encontrada")
                status["fk"] = "⚠️"
            
            # 3. Verificar índice
            result = connection.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = :tabela 
                  AND indexname LIKE '%admin_id%'
            """), {"tabela": tabela})
            
            idx = result.fetchone()
            if idx:
                print(f"✅ Índice: {idx[0]}")
                status["indice"] = "✅"
            else:
                print(f"⚠️  Índice não encontrado")
                status["indice"] = "⚠️"
            
            # 4. Verificar distribuição de dados
            result = connection.execute(text(f"""
                SELECT admin_id, COUNT(*) 
                FROM {tabela} 
                GROUP BY admin_id 
                ORDER BY admin_id
            """))
            
            distribuicao = result.fetchall()
            print(f"📊 Distribuição de admin_id:")
            total_registros = 0
            for admin_id, count in distribuicao:
                print(f"   Admin {admin_id}: {count} registros")
                total_registros += count
            
            status["total_registros"] = total_registros
            
            # 5. Verificar registros NULL
            result = connection.execute(text(f"SELECT COUNT(*) FROM {tabela} WHERE admin_id IS NULL"))
            nulls = result.scalar()
            
            if nulls > 0:
                print(f"❌ {nulls} registros com admin_id NULL")
                status["nulls"] = f"❌ {nulls}"
                todas_ok = False
            else:
                print(f"✅ Nenhum registro com admin_id NULL")
                status["nulls"] = "✅ 0"
            
            resultados.append(status)
            print()
        
        # Resumo em tabela
        print("=" * 80)
        print("📊 RESUMO DA VALIDAÇÃO")
        print("=" * 80)
        print()
        
        # Cabeçalho
        print(f"{'Tabela':<25} {'Coluna':<8} {'FK':<6} {'Índice':<8} {'Registros':<12} {'NULLs':<10}")
        print("-" * 80)
        
        # Linhas
        for r in resultados:
            print(f"{r['tabela']:<25} {r['coluna']:<8} {r.get('fk', 'N/A'):<6} {r.get('indice', 'N/A'):<8} {r.get('total_registros', 0):<12} {r.get('nulls', 'N/A'):<10}")
        
        print()
        
        if todas_ok:
            print("✅ VALIDAÇÃO COMPLETA - MIGRATION 48 EXECUTADA COM SUCESSO")
            print()
            print("🎉 Sistema está pronto para uso!")
            return True
        else:
            print("❌ VALIDAÇÃO FALHOU - PROBLEMAS DETECTADOS")
            print()
            print("🔧 Ações necessárias:")
            print("   1. Verifique os erros acima")
            print("   2. Execute novamente: python3 force_migration_48.py")
            print("   3. Ou faça rollback: python3 rollback_migration_48.py")
            return False

if __name__ == "__main__":
    try:
        success = validate_migration_48()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
