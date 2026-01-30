"""
Migração: Adicionar campos de geofencing na tabela obra e registro_ponto
"""
from app import app, db
from sqlalchemy import text

def upgrade():
    """Adiciona os campos de geofencing na tabela obra"""
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('obra')]
            
            with db.engine.connect() as conn:
                if 'latitude' not in columns:
                    print("Adicionando coluna latitude em obra...")
                    conn.execute(text('ALTER TABLE obra ADD COLUMN latitude DOUBLE PRECISION'))
                
                if 'longitude' not in columns:
                    print("Adicionando coluna longitude em obra...")
                    conn.execute(text('ALTER TABLE obra ADD COLUMN longitude DOUBLE PRECISION'))
                
                if 'raio_geofence_metros' not in columns:
                    print("Adicionando coluna raio_geofence_metros em obra...")
                    conn.execute(text('ALTER TABLE obra ADD COLUMN raio_geofence_metros INTEGER DEFAULT 100'))
                
                conn.commit()
            
            print("✅ Migração de Obra concluída!")
            
        except Exception as e:
            print(f"❌ Erro na migração de Obra: {e}")

def upgrade_registro_ponto():
    """Adiciona campos de localização no registro de ponto"""
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('registro_ponto')]
            
            with db.engine.connect() as conn:
                if 'latitude' not in columns:
                    print("Adicionando coluna latitude em registro_ponto...")
                    conn.execute(text('ALTER TABLE registro_ponto ADD COLUMN latitude DOUBLE PRECISION'))
                
                if 'longitude' not in columns:
                    print("Adicionando coluna longitude em registro_ponto...")
                    conn.execute(text('ALTER TABLE registro_ponto ADD COLUMN longitude DOUBLE PRECISION'))
                
                if 'distancia_obra_metros' not in columns:
                    print("Adicionando coluna distancia_obra_metros em registro_ponto...")
                    conn.execute(text('ALTER TABLE registro_ponto ADD COLUMN distancia_obra_metros DOUBLE PRECISION'))
                
                conn.commit()
            
            print("✅ Migração de RegistroPonto concluída!")
            
        except Exception as e:
            print(f"❌ Erro na migração de RegistroPonto: {e}")

if __name__ == '__main__':
    print("Iniciando migrações de geofencing...")
    upgrade()
    upgrade_registro_ponto()
    print("✅ Todas as migrações concluídas!")
