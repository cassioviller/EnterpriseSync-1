#!/usr/bin/env python3
"""
Script para corrigir tabela restaurante em produção
Adiciona colunas faltantes e configura dados necessários
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def main():
    print("🔧 CORREÇÃO DA TABELA RESTAURANTE - PRODUÇÃO")
    print("=" * 50)
    
    # URL do banco de dados
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL não encontrada!")
        return False
    
    print(f"📡 Conectando ao banco: {database_url[:30]}...")
    
    try:
        # Criar engine e sessão
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print("✅ Conectado ao banco de dados!")
        
        # 1. Verificar colunas existentes
        print("\n🔍 Verificando estrutura atual da tabela restaurante...")
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'restaurante'
            ORDER BY column_name;
        """))
        
        colunas_existentes = [row[0] for row in result.fetchall()]
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
                    session.execute(text(sql))
                    print(f"✅ Adicionada: {coluna} ({tipo})")
                    colunas_adicionadas += 1
                except Exception as e:
                    print(f"⚠️ Erro ao adicionar {coluna}: {e}")
            else:
                print(f"ℹ️ Já existe: {coluna}")
        
        # 4. Verificar se temos usuários admin
        print("\n👤 Verificando usuários admin...")
        result = session.execute(text("""
            SELECT id, nome, email 
            FROM usuario 
            WHERE tipo_usuario = 'ADMIN' 
            LIMIT 1;
        """))
        
        admin = result.fetchone()
        if admin:
            admin_id, admin_nome, admin_email = admin
            print(f"✅ Admin encontrado: {admin_nome} ({admin_email})")
            
            # 5. Atualizar restaurantes sem admin_id
            if 'admin_id' in [col for col, _ in colunas_necessarias.items() if col not in colunas_existentes]:
                print("\n🔗 Configurando admin_id para restaurantes existentes...")
                result = session.execute(text("""
                    UPDATE restaurante 
                    SET admin_id = :admin_id 
                    WHERE admin_id IS NULL OR admin_id = 0;
                """), {'admin_id': admin_id})
                
                print(f"✅ {result.rowcount} restaurantes associados ao admin")
        else:
            print("⚠️ Nenhum usuário admin encontrado!")
        
        # 6. Commit das alterações
        session.commit()
        print(f"\n🎉 CORREÇÃO FINALIZADA!")
        print(f"📊 Colunas adicionadas: {colunas_adicionadas}")
        
        # 7. Verificação final
        print("\n🔍 Verificação final...")
        result = session.execute(text("SELECT COUNT(*) FROM restaurante;"))
        total_restaurantes = result.scalar()
        print(f"📈 Total de restaurantes: {total_restaurantes}")
        
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'restaurante'
            ORDER BY column_name;
        """))
        
        colunas_finais = [row[0] for row in result.fetchall()]
        print(f"📋 Estrutura final: {sorted(colunas_finais)}")
        
        session.close()
        print("\n✅ SCRIPT EXECUTADO COM SUCESSO!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)