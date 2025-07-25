#!/usr/bin/env python3
"""
Script de Correção para Schema da Tabela Restaurante em Produção
Baseado no diagnóstico automático: colunas faltantes identificadas
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def corrigir_schema_restaurante():
    """Corrige schema da tabela restaurante baseado no diagnóstico"""
    
    # URL do banco de dados
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL não encontrada!")
        return False
    
    try:
        # Conectar ao banco
        print("🔗 Conectando ao banco de dados...")
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Verificar colunas atuais
        print("🔍 Verificando schema atual...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'restaurante'
            ORDER BY ordinal_position;
        """)
        colunas_atuais = cursor.fetchall()
        
        print("📋 Colunas existentes:")
        for col in colunas_atuais:
            print(f"   ✅ {col[0]} ({col[1]})")
        
        # Colunas que devem existir
        colunas_necessarias = {
            'responsavel': 'VARCHAR(100)',
            'preco_almoco': 'DECIMAL(10,2) DEFAULT 0.00', 
            'preco_jantar': 'DECIMAL(10,2) DEFAULT 0.00',
            'preco_lanche': 'DECIMAL(10,2) DEFAULT 0.00',
            'admin_id': 'INTEGER'
        }
        
        # Identificar colunas faltantes
        colunas_existentes = [col[0] for col in colunas_atuais]
        colunas_faltantes = []
        
        for col_nome, col_tipo in colunas_necessarias.items():
            if col_nome not in colunas_existentes:
                colunas_faltantes.append((col_nome, col_tipo))
        
        if not colunas_faltantes:
            print("✅ Todas as colunas necessárias já existem!")
            return True
            
        # Adicionar colunas faltantes
        print(f"🔧 Adicionando {len(colunas_faltantes)} colunas faltantes...")
        
        for col_nome, col_tipo in colunas_faltantes:
            sql = f"ALTER TABLE restaurante ADD COLUMN {col_nome} {col_tipo};"
            print(f"   ⚙️ {sql}")
            cursor.execute(sql)
            print(f"   ✅ Coluna {col_nome} adicionada")
        
        # Verificar se coluna duplicada existe e remover
        print("🔍 Verificando coluna duplicada 'contato_responsavel'...")
        if 'contato_responsavel' in colunas_existentes:
            print("🗑️ Removendo coluna duplicada 'contato_responsavel'...")
            cursor.execute("ALTER TABLE restaurante DROP COLUMN contato_responsavel;")
            print("   ✅ Coluna 'contato_responsavel' removida")
        
        # Atualizar admin_id para restaurantes sem admin
        print("🔧 Configurando admin_id para restaurantes existentes...")
        cursor.execute("""
            UPDATE restaurante 
            SET admin_id = 1 
            WHERE admin_id IS NULL OR admin_id = 0;
        """)
        affected = cursor.rowcount
        print(f"   ✅ {affected} restaurantes atualizados com admin_id")
        
        # Verificar schema final
        print("✅ Verificação final do schema...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'restaurante'
            ORDER BY ordinal_position;
        """)
        schema_final = cursor.fetchall()
        
        print("📋 Schema final da tabela restaurante:")
        for col in schema_final:
            print(f"   ✅ {col[0]} ({col[1]})")
        
        # Contar restaurantes
        cursor.execute("SELECT COUNT(*) FROM restaurante;")
        total = cursor.fetchone()[0]
        print(f"🏪 Total de restaurantes: {total}")
        
        print("\n🎉 CORREÇÃO DO SCHEMA CONCLUÍDA COM SUCESSO!")
        print("   Agora acesse /restaurantes novamente para verificar")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na correção: {e}")
        return False

if __name__ == "__main__":
    print("🔧 CORREÇÃO DO SCHEMA RESTAURANTE - PRODUÇÃO")
    print("=" * 50)
    
    sucesso = corrigir_schema_restaurante()
    
    if sucesso:
        print("\n✅ SCRIPT EXECUTADO COM SUCESSO!")
        print("   Acesse /restaurantes para verificar se o erro foi resolvido")
        sys.exit(0)
    else:
        print("\n❌ FALHA NA EXECUÇÃO DO SCRIPT")
        sys.exit(1)