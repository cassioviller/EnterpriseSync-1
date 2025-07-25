#!/usr/bin/env python3
"""
Script para corrigir tabela restaurante em produção
Adiciona colunas faltantes e configura dados necessários
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse

def main():
    print("🔧 CORREÇÃO DA TABELA RESTAURANTE - PRODUÇÃO")
    print("=" * 50)
    
    # URL do banco de dados
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL não encontrada!")
        return False
    
    print(f"📡 Conectando ao banco: {database_url[:50]}...")
    
    # Parse da URL para psycopg2
    parsed = urlparse(database_url)
    
    try:
        # Conectar diretamente com psycopg2
        conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 5432
        )
        
        cursor = conn.cursor()
        print("✅ Conectado ao banco de dados!")
        
        # 1. Verificar colunas existentes
        print("\n🔍 Verificando estrutura atual da tabela restaurante...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'restaurante'
            ORDER BY column_name;
        """)
        
        colunas_existentes = [row[0] for row in cursor.fetchall()]
        print(f"📋 Colunas existentes: {colunas_existentes}")
        
        # 2. Colunas necessárias
        colunas_necessarias = {
            'responsavel': 'VARCHAR(100)',
            'preco_almoco': 'FLOAT DEFAULT 0.0',
            'preco_jantar': 'FLOAT DEFAULT 0.0', 
            'preco_lanche': 'FLOAT DEFAULT 0.0',
            'observacoes': 'TEXT',
            'admin_id': 'INTEGER'
        }
        
        # 3. Adicionar colunas faltantes
        print("\n🔧 Adicionando colunas faltantes...")
        colunas_adicionadas = 0
        
        for coluna, tipo in colunas_necessarias.items():
            if coluna not in colunas_existentes:
                try:
                    sql = f"ALTER TABLE restaurante ADD COLUMN {coluna} {tipo};"
                    cursor.execute(sql)
                    print(f"✅ Adicionada: {coluna} ({tipo})")
                    colunas_adicionadas += 1
                except Exception as e:
                    print(f"⚠️ Erro ao adicionar {coluna}: {e}")
            else:
                print(f"ℹ️ Já existe: {coluna}")
        
        # 4. Verificar se temos usuários admin
        print("\n👤 Verificando usuários admin...")
        cursor.execute("""
            SELECT id, nome, email 
            FROM usuario 
            WHERE tipo_usuario = 'ADMIN' 
            LIMIT 1;
        """)
        
        admin = cursor.fetchone()
        if admin:
            admin_id, admin_nome, admin_email = admin
            print(f"✅ Admin encontrado: {admin_nome} ({admin_email})")
            
            # 5. Atualizar restaurantes sem admin_id
            if 'admin_id' not in colunas_existentes or colunas_adicionadas > 0:
                print("\n🔗 Configurando admin_id para restaurantes existentes...")
                cursor.execute("""
                    UPDATE restaurante 
                    SET admin_id = %s 
                    WHERE admin_id IS NULL OR admin_id = 0;
                """, (admin_id,))
                
                print(f"✅ {cursor.rowcount} restaurantes associados ao admin")
        else:
            print("⚠️ Nenhum usuário admin encontrado!")
        
        # 6. Commit das alterações
        conn.commit()
        print(f"\n🎉 CORREÇÃO FINALIZADA!")
        print(f"📊 Colunas adicionadas: {colunas_adicionadas}")
        
        # 7. Verificação final
        print("\n🔍 Verificação final...")
        cursor.execute("SELECT COUNT(*) FROM restaurante;")
        total_restaurantes = cursor.fetchone()[0]
        print(f"📈 Total de restaurantes: {total_restaurantes}")
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'restaurante'
            ORDER BY column_name;
        """)
        
        colunas_finais = [row[0] for row in cursor.fetchall()]
        print(f"📋 Estrutura final: {sorted(colunas_finais)}")
        
        cursor.close()
        conn.close()
        print("\n✅ SCRIPT EXECUTADO COM SUCESSO!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)