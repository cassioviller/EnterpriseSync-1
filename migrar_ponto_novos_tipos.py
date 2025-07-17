#!/usr/bin/env python3
"""
Script para adicionar colunas necessárias ao sistema de tipos de lançamento
com percentuais configuráveis de horas extras
"""

import os
import sys
from datetime import datetime
from sqlalchemy import text

# Adicionar o diretório atual ao path do Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def migrar_ponto_novos_tipos():
    """Adiciona colunas para tipos de lançamento e percentual de horas extras"""
    
    print("🚀 Iniciando migração do sistema de tipos de lançamento...")
    
    with app.app_context():
        try:
            # Verificar se as colunas já existem
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'registro_ponto' 
                AND column_name IN ('tipo_registro', 'percentual_extras')
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            print(f"Colunas existentes: {existing_columns}")
            
            # Adicionar coluna tipo_registro se não existir
            if 'tipo_registro' not in existing_columns:
                print("➕ Adicionando coluna 'tipo_registro'...")
                db.session.execute(text("""
                    ALTER TABLE registro_ponto 
                    ADD COLUMN tipo_registro VARCHAR(30) DEFAULT 'trabalhado'
                """))
                
                # Atualizar registros existentes baseado em observações
                print("🔄 Atualizando registros existentes...")
                db.session.execute(text("""
                    UPDATE registro_ponto 
                    SET tipo_registro = CASE 
                        WHEN observacoes ILIKE '%FERIADO_TRABALHADO%' THEN 'feriado_trabalhado'
                        WHEN observacoes ILIKE '%FALTA_JUSTIFICADA%' THEN 'falta_justificada'  
                        WHEN observacoes ILIKE '%FALTA%' THEN 'falta'
                        WHEN observacoes ILIKE '%FERIADO%' THEN 'feriado'
                        ELSE 'trabalhado'
                    END
                """))
                print("✅ Coluna 'tipo_registro' adicionada com sucesso!")
            else:
                print("ℹ️ Coluna 'tipo_registro' já existe")
            
            # Adicionar coluna percentual_extras se não existir
            if 'percentual_extras' not in existing_columns:
                print("➕ Adicionando coluna 'percentual_extras'...")
                db.session.execute(text("""
                    ALTER TABLE registro_ponto 
                    ADD COLUMN percentual_extras FLOAT DEFAULT 0.0
                """))
                
                # Configurar percentuais para registros existentes
                print("🔄 Configurando percentuais para registros existentes...")
                db.session.execute(text("""
                    UPDATE registro_ponto 
                    SET percentual_extras = CASE 
                        WHEN tipo_registro IN ('feriado_trabalhado', 'domingo_horas_extras') THEN 100.0
                        WHEN tipo_registro = 'sabado_horas_extras' THEN 50.0
                        ELSE 0.0
                    END
                """))
                print("✅ Coluna 'percentual_extras' adicionada com sucesso!")
            else:
                print("ℹ️ Coluna 'percentual_extras' já existe")
            
            # Commit das alterações
            db.session.commit()
            
            # Verificar resultado final
            result = db.session.execute(text("SELECT COUNT(*) FROM registro_ponto"))
            total_registros = result.fetchone()[0]
            
            result = db.session.execute(text("""
                SELECT tipo_registro, COUNT(*) as total
                FROM registro_ponto 
                GROUP BY tipo_registro
                ORDER BY total DESC
            """))
            tipos_distribuicao = result.fetchall()
            
            print(f"\n📊 Migração concluída com sucesso!")
            print(f"Total de registros: {total_registros}")
            print(f"Distribuição por tipo:")
            for tipo, total in tipos_distribuicao:
                print(f"  - {tipo}: {total} registros")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro durante a migração: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    if migrar_ponto_novos_tipos():
        print("\n🎉 Migração executada com sucesso!")
        print("\nNovos tipos disponíveis:")
        print("- trabalhado (padrão)")
        print("- falta")
        print("- falta_justificada")
        print("- feriado")
        print("- feriado_trabalhado (100% extra)")
        print("- sabado_horas_extras (50-60% configurável)")
        print("- domingo_horas_extras (100% extra)")
    else:
        print("\n💥 Falha na migração!")
        sys.exit(1)