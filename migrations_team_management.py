#!/usr/bin/env python3
"""
Migration Script: Advanced Team Management Fields
Adds support for Field/Office separation and HorarioTrabalho integration

CRITICAL: Run this before using the new team management features
"""

from app import app, db
from sqlalchemy import text, Column, String, Boolean, DateTime, Time
import logging

logging.basicConfig(level=logging.INFO)

def migrate_team_management_fields():
    """Add new fields for advanced team management"""
    
    with app.app_context():
        try:
            print("🔄 Iniciando migração para gestão de equipe avançada...")
            
            # 1. Adicionar campo local_trabalho na tabela allocation
            try:
                db.session.execute(text("""
                    ALTER TABLE allocation 
                    ADD COLUMN IF NOT EXISTS local_trabalho VARCHAR(20) DEFAULT 'campo'
                """))
                print("✅ Campo local_trabalho adicionado à tabela allocation")
            except Exception as e:
                print(f"ℹ️ Campo local_trabalho já existe ou erro: {e}")
            
            # 2. Adicionar campos de integração de ponto na tabela allocation_employee
            try:
                db.session.execute(text("""
                    ALTER TABLE allocation_employee 
                    ADD COLUMN IF NOT EXISTS tipo_lancamento VARCHAR(30) DEFAULT 'trabalho_normal'
                """))
                print("✅ Campo tipo_lancamento adicionado à tabela allocation_employee")
            except Exception as e:
                print(f"ℹ️ Campo tipo_lancamento já existe ou erro: {e}")
            
            try:
                db.session.execute(text("""
                    ALTER TABLE allocation_employee 
                    ADD COLUMN IF NOT EXISTS sincronizado_ponto BOOLEAN DEFAULT FALSE
                """))
                print("✅ Campo sincronizado_ponto adicionado à tabela allocation_employee")
            except Exception as e:
                print(f"ℹ️ Campo sincronizado_ponto já existe ou erro: {e}")
            
            try:
                db.session.execute(text("""
                    ALTER TABLE allocation_employee 
                    ADD COLUMN IF NOT EXISTS data_sincronizacao TIMESTAMP
                """))
                print("✅ Campo data_sincronizacao adicionado à tabela allocation_employee")
            except Exception as e:
                print(f"ℹ️ Campo data_sincronizacao já existe ou erro: {e}")
            
            # 3. Atualizar constraint unique da tabela allocation para incluir local_trabalho
            try:
                # Remover constraint antiga se existir
                db.session.execute(text("""
                    ALTER TABLE allocation 
                    DROP CONSTRAINT IF EXISTS uk_allocation_admin_obra_data
                """))
                
                # Adicionar nova constraint com local_trabalho
                db.session.execute(text("""
                    ALTER TABLE allocation 
                    ADD CONSTRAINT uk_allocation_admin_obra_data_local 
                    UNIQUE (admin_id, obra_id, data_alocacao, local_trabalho)
                """))
                print("✅ Constraint única atualizada para incluir local_trabalho")
            except Exception as e:
                print(f"ℹ️ Constraint já existe ou erro: {e}")
            
            # 4. Adicionar índices para performance
            try:
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_allocation_local 
                    ON allocation (local_trabalho)
                """))
                print("✅ Índice idx_allocation_local criado")
            except Exception as e:
                print(f"ℹ️ Índice já existe ou erro: {e}")
            
            # 5. Verificar se campos HorarioTrabalho existem (devem já existir)
            try:
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'horario_trabalho'
                    AND column_name IN ('entrada', 'saida', 'dias_semana')
                """)).fetchall()
                
                if len(result) >= 3:
                    print("✅ Campos HorarioTrabalho confirmados")
                else:
                    print("⚠️ Alguns campos HorarioTrabalho podem estar ausentes")
                    
            except Exception as e:
                print(f"ℹ️ Erro ao verificar HorarioTrabalho: {e}")
            
            # 6. Verificar se relacionamento funcionario.horario_trabalho_id existe
            try:
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'funcionario'
                    AND column_name = 'horario_trabalho_id'
                """)).fetchone()
                
                if result:
                    print("✅ Relacionamento funcionario.horario_trabalho_id confirmado")
                else:
                    print("⚠️ Campo horario_trabalho_id pode estar ausente na tabela funcionario")
                    
            except Exception as e:
                print(f"ℹ️ Erro ao verificar relacionamento: {e}")
            
            # Commit das mudanças
            db.session.commit()
            print("✅ Migração concluída com sucesso!")
            
            # 7. Verificação final
            print("\n🔍 Verificação final das tabelas:")
            tables_to_check = ['allocation', 'allocation_employee', 'horario_trabalho', 'funcionario']
            
            for table in tables_to_check:
                try:
                    columns = db.session.execute(text(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}'
                        ORDER BY ordinal_position
                    """)).fetchall()
                    
                    print(f"  📋 {table}: {len(columns)} colunas")
                    
                except Exception as e:
                    print(f"  ❌ Erro ao verificar {table}: {e}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na migração: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("🚀 Executando migração para gestão de equipe avançada...")
    success = migrate_team_management_fields()
    
    if success:
        print("🎉 Migração concluída! Sistema pronto para gestão de equipe avançada.")
    else:
        print("💥 Migração falhou. Verifique os logs acima.")