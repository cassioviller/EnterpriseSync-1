#!/usr/bin/env python3
"""
SCRIPT DE PRODUÇÃO: Adiciona admin_id na tabela horario_trabalho
Execute via SSH no Easypanel: python3 fix_horario_trabalho_PRODUCAO.py
"""
import os
import sys

def fix_horario_trabalho():
    """Corrige horario_trabalho.admin_id de forma SIMPLES e DIRETA"""
    
    print("=" * 80)
    print("🔧 CORREÇÃO PRODUÇÃO: horario_trabalho.admin_id")
    print("=" * 80)
    print()
    
    # Pegar DATABASE_URL do ambiente
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ ERRO: DATABASE_URL não encontrada no ambiente")
        print("   Certifique-se de estar no container correto")
        return False
    
    print(f"📊 Database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
    print()
    
    try:
        # Importar psycopg2 (já instalado no container)
        import psycopg2
        
        # Conectar
        print("🔌 Conectando ao banco...")
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cursor = conn.cursor()
        print("   ✅ Conectado")
        print()
        
        # Verificar se coluna já existe
        print("🔍 Verificando se admin_id já existe...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'horario_trabalho' 
              AND column_name = 'admin_id'
        """)
        
        if cursor.fetchone()[0] > 0:
            print("   ⏭️  Coluna admin_id JÁ EXISTE - nada a fazer")
            cursor.close()
            conn.close()
            return True
        
        print("   ⚠️  Coluna admin_id NÃO EXISTE - vamos criar!")
        print()
        
        # PASSO 1: Adicionar coluna
        print("📝 PASSO 1: Adicionando coluna admin_id...")
        cursor.execute("ALTER TABLE horario_trabalho ADD COLUMN admin_id INTEGER")
        print("   ✅ Coluna adicionada")
        print()
        
        # PASSO 2: Backfill via funcionario
        print("🔄 PASSO 2: Preenchendo admin_id via funcionario...")
        cursor.execute("""
            UPDATE horario_trabalho ht
            SET admin_id = f.admin_id
            FROM funcionario f
            WHERE f.horario_trabalho_id = ht.id
              AND ht.admin_id IS NULL
              AND f.admin_id IS NOT NULL
        """)
        rows = cursor.rowcount
        print(f"   ✅ {rows} registros preenchidos via relacionamento")
        print()
        
        # PASSO 3: Preencher NULLs com admin_id padrão (2)
        print("🔧 PASSO 3: Preenchendo registros órfãos com admin_id = 2...")
        cursor.execute("""
            UPDATE horario_trabalho 
            SET admin_id = 2 
            WHERE admin_id IS NULL
        """)
        orphans = cursor.rowcount
        print(f"   ✅ {orphans} registros órfãos corrigidos")
        print()
        
        # PASSO 4: Aplicar NOT NULL
        print("🔒 PASSO 4: Aplicando constraint NOT NULL...")
        cursor.execute("ALTER TABLE horario_trabalho ALTER COLUMN admin_id SET NOT NULL")
        print("   ✅ Constraint aplicada")
        print()
        
        # PASSO 5: Adicionar foreign key
        print("🔗 PASSO 5: Criando foreign key...")
        cursor.execute("""
            ALTER TABLE horario_trabalho
            ADD CONSTRAINT fk_horario_trabalho_admin_id
            FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE
        """)
        print("   ✅ Foreign key criada")
        print()
        
        # PASSO 6: Criar índice
        print("⚡ PASSO 6: Criando índice...")
        cursor.execute("""
            CREATE INDEX idx_horario_trabalho_admin_id 
            ON horario_trabalho(admin_id)
        """)
        print("   ✅ Índice criado")
        print()
        
        # COMMIT
        print("💾 Salvando alterações...")
        conn.commit()
        print("   ✅ COMMIT realizado")
        print()
        
        # VALIDAÇÃO
        print("🔍 Validando resultado...")
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(admin_id) as com_admin_id,
                COUNT(DISTINCT admin_id) as admins_distintos
            FROM horario_trabalho
        """)
        total, com_admin, distintos = cursor.fetchone()
        print(f"   📊 Total de registros: {total}")
        print(f"   ✅ Com admin_id: {com_admin}")
        print(f"   👥 Admins distintos: {distintos}")
        print()
        
        # Mostrar dados
        print("📋 Registros:")
        cursor.execute("SELECT id, nome, admin_id FROM horario_trabalho ORDER BY id")
        for row in cursor.fetchall():
            print(f"   ID {row[0]}: {row[1]} (admin_id={row[2]})")
        print()
        
        # Fechar
        cursor.close()
        conn.close()
        
        print("=" * 80)
        print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 80)
        print()
        print("🔄 Próximo passo: Reiniciar a aplicação")
        print("   supervisorctl restart all")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ ERRO DURANTE A CORREÇÃO")
        print("=" * 80)
        print(f"Erro: {e}")
        print()
        
        # Tentar rollback
        try:
            conn.rollback()
            print("↩️  Rollback executado - banco permanece inalterado")
        except:
            pass
        
        return False

if __name__ == "__main__":
    try:
        success = fix_horario_trabalho()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
