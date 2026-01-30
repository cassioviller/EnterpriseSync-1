"""
Comando Flask para executar migração de geofencing em produção
Uso: flask migrate-geofencing
"""
from app import app, db
from flask.cli import with_appcontext
import click

@app.cli.command('migrate-geofencing')
@with_appcontext
def migrate_geofencing():
    """Executa a migração de geofencing adicionando colunas nas tabelas obra e registro_ponto"""
    
    print("=" * 60)
    print("INICIANDO MIGRAÇÃO DE GEOFENCING")
    print("=" * 60)
    
    try:
        # Obter conexão direta com o banco
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # ===== MIGRAÇÃO DA TABELA OBRA =====
        print("\n[1/2] Migrando tabela OBRA...")
        
        # Verificar se as colunas já existem
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='obra' AND column_name IN ('latitude', 'longitude', 'raio_geofence_metros')
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if 'latitude' not in existing_columns:
            print("  → Adicionando coluna 'latitude'...")
            cursor.execute('ALTER TABLE obra ADD COLUMN latitude DOUBLE PRECISION')
            print("  ✅ Coluna 'latitude' adicionada!")
        else:
            print("  ⚠️  Coluna 'latitude' já existe, pulando...")
        
        if 'longitude' not in existing_columns:
            print("  → Adicionando coluna 'longitude'...")
            cursor.execute('ALTER TABLE obra ADD COLUMN longitude DOUBLE PRECISION')
            print("  ✅ Coluna 'longitude' adicionada!")
        else:
            print("  ⚠️  Coluna 'longitude' já existe, pulando...")
        
        if 'raio_geofence_metros' not in existing_columns:
            print("  → Adicionando coluna 'raio_geofence_metros'...")
            cursor.execute('ALTER TABLE obra ADD COLUMN raio_geofence_metros INTEGER DEFAULT 100')
            print("  ✅ Coluna 'raio_geofence_metros' adicionada!")
        else:
            print("  ⚠️  Coluna 'raio_geofence_metros' já existe, pulando...")
        
        # ===== MIGRAÇÃO DA TABELA REGISTRO_PONTO =====
        print("\n[2/2] Migrando tabela REGISTRO_PONTO...")
        
        # Verificar se as colunas já existem
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='registro_ponto' AND column_name IN ('latitude', 'longitude', 'distancia_obra_metros')
        """)
        existing_columns_ponto = [row[0] for row in cursor.fetchall()]
        
        if 'latitude' not in existing_columns_ponto:
            print("  → Adicionando coluna 'latitude'...")
            cursor.execute('ALTER TABLE registro_ponto ADD COLUMN latitude DOUBLE PRECISION')
            print("  ✅ Coluna 'latitude' adicionada!")
        else:
            print("  ⚠️  Coluna 'latitude' já existe, pulando...")
        
        if 'longitude' not in existing_columns_ponto:
            print("  → Adicionando coluna 'longitude'...")
            cursor.execute('ALTER TABLE registro_ponto ADD COLUMN longitude DOUBLE PRECISION')
            print("  ✅ Coluna 'longitude' adicionada!")
        else:
            print("  ⚠️  Coluna 'longitude' já existe, pulando...")
        
        if 'distancia_obra_metros' not in existing_columns_ponto:
            print("  → Adicionando coluna 'distancia_obra_metros'...")
            cursor.execute('ALTER TABLE registro_ponto ADD COLUMN distancia_obra_metros DOUBLE PRECISION')
            print("  ✅ Coluna 'distancia_obra_metros' adicionada!")
        else:
            print("  ⚠️  Coluna 'distancia_obra_metros' já existe, pulando...")
        
        # Commit das mudanças
        connection.commit()
        
        print("\n" + "=" * 60)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print("\n📋 Resumo:")
        print("  • Tabela 'obra': 3 colunas de geofencing")
        print("  • Tabela 'registro_ponto': 3 colunas de localização")
        print("\n🚀 O sistema de geofencing está pronto para uso!")
        
    except Exception as e:
        connection.rollback()
        print("\n" + "=" * 60)
        print("❌ ERRO NA MIGRAÇÃO!")
        print("=" * 60)
        print(f"Erro: {str(e)}")
        print("\n⚠️  As mudanças foram revertidas (rollback)")
        raise
    
    finally:
        cursor.close()
        connection.close()


if __name__ == '__main__':
    with app.app_context():
        migrate_geofencing()
