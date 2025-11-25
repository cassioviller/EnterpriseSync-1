#!/usr/bin/env python3
"""
Script de diagnóstico para produção
Execute este script no container do Easypanel para entender o problema
"""
import os
import sys
from sqlalchemy import create_engine, text

def diagnostico_completo():
    """Diagnóstico completo do ambiente de produção"""
    
    print("=" * 80)
    print("🔍 DIAGNÓSTICO DE PRODUÇÃO - MIGRATION 48")
    print("=" * 80)
    print()
    
    # 1. Verificar DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ ERRO CRÍTICO: DATABASE_URL não encontrada")
        print("   Verifique variáveis de ambiente")
        return False
    
    print(f"✅ DATABASE_URL encontrada")
    print(f"   Host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'N/A'}")
    print()
    
    # 2. Conectar ao banco
    try:
        engine = create_engine(database_url)
        connection = engine.connect()
        print("✅ Conexão com banco estabelecida")
        print()
    except Exception as e:
        print(f"❌ ERRO ao conectar ao banco: {e}")
        return False
    
    # 3. Verificar tabela migration_history
    print("📋 Verificando histórico de migrations...")
    try:
        result = connection.execute(text("""
            SELECT COUNT(*) FROM migration_history WHERE migration_number = 48
        """))
        count = result.scalar()
        
        if count > 0:
            print("✅ Migration 48 ENCONTRADA no histórico")
            
            result = connection.execute(text("""
                SELECT migration_number, migration_name, executed_at, status 
                FROM migration_history 
                WHERE migration_number = 48
            """))
            row = result.fetchone()
            print(f"   Executada em: {row[2]}")
            print(f"   Status: {row[3]}")
        else:
            print("❌ Migration 48 NÃO ENCONTRADA no histórico")
            print("   CAUSA: Migração nunca foi executada")
    except Exception as e:
        print(f"⚠️  Erro ao consultar migration_history: {e}")
        print("   Tabela migration_history pode não existir")
    
    print()
    
    # 4. Verificar colunas admin_id (AS 3 CRÍTICAS)
    print("📋 Verificando colunas admin_id nas 3 tabelas CRÍTICAS...")
    print()
    
    tabelas_criticas = [
        ('rdo_mao_obra', 'RDO - Mão de Obra'),
        ('funcao', 'Funções'),
        ('registro_alimentacao', 'Alimentação')
    ]
    
    tabelas_ok = 0
    tabelas_problema = []
    
    for tabela, descricao in tabelas_criticas:
        try:
            result = connection.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = :tabela AND column_name = 'admin_id'
            """), {"tabela": tabela})
            
            col_info = result.fetchone()
            
            if col_info:
                print(f"✅ {tabela}.admin_id EXISTE ({descricao})")
                print(f"   Tipo: {col_info[1]}, Nullable: {col_info[2]}")
                
                # Contar registros
                result_count = connection.execute(text(f"SELECT COUNT(*) FROM {tabela}"))
                total = result_count.scalar()
                
                result_null = connection.execute(text(f"SELECT COUNT(*) FROM {tabela} WHERE admin_id IS NULL"))
                nulls = result_null.scalar()
                
                print(f"   Registros: {total} total, {nulls} NULL")
                tabelas_ok += 1
            else:
                print(f"❌ {tabela}.admin_id NÃO EXISTE ({descricao})")
                tabelas_problema.append(tabela)
        except Exception as e:
            print(f"❌ {tabela}: ERRO ao verificar - {e}")
            tabelas_problema.append(tabela)
        
        print()
    
    # 5. Testar query problemática
    print("🧪 Testando query que está falhando em produção...")
    try:
        result = connection.execute(text("""
            SELECT COUNT(*) 
            FROM rdo_mao_obra 
            WHERE rdo_id = 1
        """))
        count = result.scalar()
        print(f"✅ Query em rdo_mao_obra funcionou (encontrou {count} registros)")
    except Exception as e:
        print(f"❌ Query em rdo_mao_obra FALHOU: {e}")
        print("   Esta é a causa do erro InFailedSqlTransaction")
    
    print()
    
    # 6. Resumo e diagnóstico
    print("=" * 80)
    print("📊 RESUMO DO DIAGNÓSTICO")
    print("=" * 80)
    print()
    
    if tabelas_ok == 3:
        print("✅ DIAGNÓSTICO: Sistema OK")
        print("   Todas as 3 tabelas críticas têm admin_id")
        print("   Migration 48 foi executada com sucesso")
        print()
        print("🤔 Se ainda há erros, verifique:")
        print("   1. Reinicie a aplicação: supervisorctl restart all")
        print("   2. Verifique logs: tail -100 /var/log/app.log")
        return True
    else:
        print("❌ DIAGNÓSTICO: Migration 48 NÃO executada")
        print(f"   Tabelas OK: {tabelas_ok}/3")
        print(f"   Tabelas com problema: {len(tabelas_problema)}/3")
        print()
        
        if tabelas_problema:
            print("🔴 TABELAS QUE PRECISAM DE CORREÇÃO:")
            for tabela in tabelas_problema:
                print(f"   - {tabela}")
        
        print()
        print("🔧 SOLUÇÃO:")
        print("   1. Execute: python3 force_migration_48.py")
        print("   2. OU reinicie aplicação: supervisorctl restart all")
        print("   3. Aguarde 30s e execute este script novamente")
        return False
    
    connection.close()

if __name__ == "__main__":
    try:
        success = diagnostico_completo()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
