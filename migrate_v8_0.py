#!/usr/bin/env python3
"""
Script de migração para SIGE v8.0
Adiciona novos campos e tabelas para os módulos implementados
"""

import os
import sys
from app import app, db
from models import *

def migrar_sige_v8():
    """Executa migração para SIGE v8.0"""
    with app.app_context():
        try:
            print("🚀 Iniciando migração SIGE v8.0...")
            
            # Adicionar novas colunas na tabela obra
            print("📝 Adicionando colunas do Portal do Cliente na tabela 'obra'...")
            
            try:
                db.session.execute("""
                    ALTER TABLE obra ADD COLUMN IF NOT EXISTS token_cliente VARCHAR(255) UNIQUE;
                """)
                print("✅ Coluna 'token_cliente' adicionada")
            except Exception as e:
                print(f"⚠️  Coluna 'token_cliente' já existe ou erro: {e}")
            
            try:
                db.session.execute("""
                    ALTER TABLE obra ADD COLUMN IF NOT EXISTS cliente_nome VARCHAR(100);
                """)
                print("✅ Coluna 'cliente_nome' adicionada")
            except Exception as e:
                print(f"⚠️  Coluna 'cliente_nome' já existe ou erro: {e}")
            
            try:
                db.session.execute("""
                    ALTER TABLE obra ADD COLUMN IF NOT EXISTS proposta_origem_id INTEGER 
                    REFERENCES proposta_comercial(id);
                """)
                print("✅ Coluna 'proposta_origem_id' adicionada")
            except Exception as e:
                print(f"⚠️  Coluna 'proposta_origem_id' já existe ou erro: {e}")
            
            # Criar todas as tabelas novas
            print("🗃️  Criando novas tabelas...")
            db.create_all()
            
            db.session.commit()
            
            print("✅ Migração SIGE v8.0 concluída com sucesso!")
            print("""
            📋 Novos módulos implementados:
            - ✅ Sistema de Propostas Comerciais
            - ✅ Portal do Cliente  
            - ✅ Gestão de Equipes com RDO Automático
            """)
            
        except Exception as e:
            print(f"❌ Erro na migração: {e}")
            db.session.rollback()
            return False
            
    return True

if __name__ == "__main__":
    migrar_sige_v8()