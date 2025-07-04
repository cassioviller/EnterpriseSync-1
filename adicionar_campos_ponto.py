#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para adicionar campos necessários à tabela registro_ponto
para suporte ao sistema de KPIs v3.0
"""

from app import app, db
from sqlalchemy import text

def adicionar_campos_ponto():
    """Adiciona campos necessários para o sistema de KPIs v3.0"""
    
    with app.app_context():
        try:
            print("Verificando e adicionando campos à tabela registro_ponto...")
            
            # Lista de campos para adicionar
            campos_para_adicionar = [
                ('minutos_atraso_entrada', 'INTEGER DEFAULT 0'),
                ('minutos_atraso_saida', 'INTEGER DEFAULT 0'),
                ('total_atraso_minutos', 'INTEGER DEFAULT 0'),
                ('total_atraso_horas', 'FLOAT DEFAULT 0.0'),
                ('meio_periodo', 'BOOLEAN DEFAULT FALSE'),
                ('saida_antecipada', 'BOOLEAN DEFAULT FALSE'),
                ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for campo, tipo in campos_para_adicionar:
                try:
                    # Verificar se o campo já existe
                    result = db.session.execute(text(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='registro_ponto' AND column_name='{campo}'
                    """))
                    
                    if result.fetchone():
                        print(f"Campo '{campo}' já existe")
                        continue
                    
                    # Adicionar o campo
                    print(f"Adicionando campo '{campo}'...")
                    db.session.execute(text(f"""
                        ALTER TABLE registro_ponto 
                        ADD COLUMN {campo} {tipo}
                    """))
                    
                    db.session.commit()
                    print(f"Campo '{campo}' adicionado com sucesso!")
                    
                except Exception as e:
                    print(f"Erro ao adicionar campo '{campo}': {e}")
                    db.session.rollback()
                    continue
            
            print("Migração da tabela registro_ponto concluída!")
            
        except Exception as e:
            print(f"Erro geral na migração: {e}")
            db.session.rollback()

def adicionar_campos_funcionario():
    """Adiciona campos necessários à tabela funcionario"""
    
    with app.app_context():
        try:
            print("Verificando e adicionando campos à tabela funcionario...")
            
            # Lista de campos para adicionar
            campos_para_adicionar = [
                ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for campo, tipo in campos_para_adicionar:
                try:
                    # Verificar se o campo já existe
                    result = db.session.execute(text(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='funcionario' AND column_name='{campo}'
                    """))
                    
                    if result.fetchone():
                        print(f"Campo '{campo}' já existe na tabela funcionario")
                        continue
                    
                    # Adicionar o campo
                    print(f"Adicionando campo '{campo}' à tabela funcionario...")
                    db.session.execute(text(f"""
                        ALTER TABLE funcionario 
                        ADD COLUMN {campo} {tipo}
                    """))
                    
                    db.session.commit()
                    print(f"Campo '{campo}' adicionado com sucesso à tabela funcionario!")
                    
                except Exception as e:
                    print(f"Erro ao adicionar campo '{campo}' à tabela funcionario: {e}")
                    db.session.rollback()
                    continue
            
            print("Migração da tabela funcionario concluída!")
            
        except Exception as e:
            print(f"Erro geral na migração da tabela funcionario: {e}")
            db.session.rollback()

if __name__ == '__main__':
    adicionar_campos_ponto()
    adicionar_campos_funcionario()