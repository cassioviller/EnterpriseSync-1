#!/usr/bin/env python3
"""
Teste de adição da coluna kpi_associado
Simula o processo que acontece no docker-entrypoint.sh
"""

from app import app, db
from sqlalchemy import text

def test_add_kpi_associado():
    """Testa a adição da coluna kpi_associado quando ela não existe"""
    with app.app_context():
        try:
            print("🔧 Testando adição da coluna kpi_associado...")
            
            # PASSO 1: Verificar se a coluna existe
            result = db.session.execute(text('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'kpi_associado'
            '''))
            
            column_exists = result.fetchone()
            
            if column_exists:
                print("✅ Coluna kpi_associado já existe")
                
                # Vamos simular a remoção para testar a adição (CUIDADO: só em desenvolvimento)
                print("🧪 Simulando remoção da coluna para teste...")
                db.session.execute(text('ALTER TABLE outro_custo DROP COLUMN IF EXISTS kpi_associado'))
                db.session.commit()
                print("⚠️ Coluna removida temporariamente para teste")
                
                # PASSO 2: Verificar novamente após remoção
                result = db.session.execute(text('''
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'outro_custo' AND column_name = 'kpi_associado'
                '''))
                column_exists = result.fetchone()
            
            if not column_exists:
                print('⚡ Adicionando coluna kpi_associado...')
                
                # PASSO 3: Adicionar a coluna (mesmo código do docker-entrypoint.sh)
                db.session.execute(text("ALTER TABLE outro_custo ADD COLUMN kpi_associado VARCHAR(30) DEFAULT 'outros_custos'"))
                
                # PASSO 4: Atualizar registros existentes
                updated = db.session.execute(text('''
                    UPDATE outro_custo 
                    SET kpi_associado = 'outros_custos'
                    WHERE kpi_associado IS NULL
                ''')).rowcount
                
                db.session.commit()
                print(f'✅ Coluna kpi_associado adicionada - {updated} registros atualizados')
                
                # PASSO 5: Verificar se foi realmente adicionada
                result = db.session.execute(text('''
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'outro_custo' AND column_name = 'kpi_associado'
                '''))
                col_info = result.fetchone()
                
                if col_info:
                    print(f"📋 Coluna criada: {col_info[0]} ({col_info[1]}) default: {col_info[2]}")
                else:
                    print("❌ Erro: Coluna não foi criada")
                    return False
                    
                # PASSO 6: Verificar dados
                sample_data = db.session.execute(text('''
                    SELECT id, tipo, kpi_associado 
                    FROM outro_custo 
                    LIMIT 3
                ''')).fetchall()
                
                print('📊 Dados após adição:')
                for row in sample_data:
                    print(f'  ID: {row[0]}, Tipo: {row[1]}, KPI: {row[2]}')
                    
            return True
            
        except Exception as e:
            print(f'❌ Erro no teste: {e}')
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = test_add_kpi_associado()
    exit(0 if success else 1)