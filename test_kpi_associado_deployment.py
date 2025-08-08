#!/usr/bin/env python3
"""
Teste de verificação da coluna kpi_associado durante deployment
Este script simula o processo de verificação que ocorre no docker-entrypoint.sh
"""

from app import app, db
from sqlalchemy import text

def test_kpi_associado_column():
    """Testa a verificação e criação da coluna kpi_associado"""
    with app.app_context():
        try:
            print("🔧 Testando verificação da coluna kpi_associado...")
            
            # Verificar se kpi_associado existe
            result = db.session.execute(text('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'kpi_associado'
            '''))
            
            column_exists = result.fetchone()
            
            if not column_exists:
                print('⚡ Coluna kpi_associado não encontrada - seria adicionada no deployment')
                print('SQL que seria executado:')
                print("  ALTER TABLE outro_custo ADD COLUMN kpi_associado VARCHAR(30) DEFAULT 'outros_custos'")
                print("  UPDATE outro_custo SET kpi_associado = 'outros_custos' WHERE kpi_associado IS NULL")
            else:
                print('✅ Coluna kpi_associado já existe')
                
                # Verificar se há registros sem valor
                count_null = db.session.execute(text('''
                    SELECT COUNT(*) 
                    FROM outro_custo 
                    WHERE kpi_associado IS NULL
                ''')).scalar()
                
                print(f'📊 Registros com kpi_associado NULL: {count_null}')
                
                # Mostrar alguns dados de exemplo
                sample_data = db.session.execute(text('''
                    SELECT id, tipo, kpi_associado 
                    FROM outro_custo 
                    LIMIT 3
                ''')).fetchall()
                
                print('📋 Dados de exemplo:')
                for row in sample_data:
                    print(f'  ID: {row[0]}, Tipo: {row[1]}, KPI: {row[2]}')
                    
            return True
            
        except Exception as e:
            print(f'❌ Erro no teste: {e}')
            return False

if __name__ == "__main__":
    success = test_kpi_associado_column()
    exit(0 if success else 1)