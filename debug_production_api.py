#!/usr/bin/env python3
"""
Debug API de Serviços em Produção - SIGE v8.1
Identifica diferenças entre desenvolvimento e produção
"""

import os
import sys
from sqlalchemy import text
from flask import Flask

# Tentar importar o contexto da aplicação
try:
    from app import app, db
    from models import *
    with app.app_context():
        print("🔍 DIAGNÓSTICO PRODUÇÃO vs DESENVOLVIMENTO - API SERVIÇOS")
        print("=" * 60)
        
        # 1. Verificar estrutura da tabela servico_obra
        print("\n📋 1. ESTRUTURA TABELA servico_obra:")
        try:
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'servico_obra' 
                ORDER BY ordinal_position
            """)).fetchall()
            
            for row in result:
                print(f"   - {row[0]}: {row[1]} {'NULL' if row[2] == 'YES' else 'NOT NULL'} {f'DEFAULT {row[3]}' if row[3] else ''}")
                
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        # 2. Verificar constraints e índices
        print("\n🔗 2. CONSTRAINTS:")
        try:
            result = db.session.execute(text("""
                SELECT constraint_name, constraint_type 
                FROM information_schema.table_constraints 
                WHERE table_name = 'servico_obra'
            """)).fetchall()
            
            for row in result:
                print(f"   - {row[0]}: {row[1]}")
                
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        # 3. Verificar dados existentes
        print("\n📊 3. DADOS EXISTENTES:")
        try:
            total_servico_obra = db.session.execute(text("SELECT COUNT(*) FROM servico_obra")).fetchone()[0]
            print(f"   - Total registros servico_obra: {total_servico_obra}")
            
            # Verificar por admin_id
            admin_counts = db.session.execute(text("""
                SELECT admin_id, COUNT(*) 
                FROM servico_obra 
                WHERE admin_id IS NOT NULL 
                GROUP BY admin_id 
                ORDER BY admin_id
            """)).fetchall()
            
            print(f"   - Por admin_id: {dict(admin_counts)}")
            
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        # 4. Verificar modelo Python
        print("\n🐍 4. MODELO PYTHON ServicoObra:")
        try:
            # Verificar se a classe existe
            print(f"   - Classe ServicoObra existe: {'✅' if 'ServicoObra' in globals() else '❌'}")
            
            if 'ServicoObra' in globals():
                # Verificar campos
                campos = [attr for attr in dir(ServicoObra) if not attr.startswith('_')]
                print(f"   - Campos disponíveis: {campos}")
                
                # Tentar criar instância
                try:
                    instance = ServicoObra()
                    print("   - ✅ Instância criada com sucesso")
                except Exception as e:
                    print(f"   - ❌ Erro ao criar instância: {e}")
            
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        # 5. Testar inserção de dados
        print("\n🧪 5. TESTE DE INSERÇÃO:")
        try:
            # Tentar inserir um registro de teste
            test_data = {
                'obra_id': 1,
                'servico_id': 1,
                'quantidade_planejada': 1.0,
                'quantidade_executada': 0.0,
                'ativo': True
            }
            
            # Verificar se obra e serviço existem
            obra_exists = db.session.execute(text("SELECT COUNT(*) FROM obra WHERE id = 1")).fetchone()[0] > 0
            servico_exists = db.session.execute(text("SELECT COUNT(*) FROM servico WHERE id = 1")).fetchone()[0] > 0
            
            print(f"   - Obra ID 1 existe: {'✅' if obra_exists else '❌'}")
            print(f"   - Serviço ID 1 existe: {'✅' if servico_exists else '❌'}")
            
            if obra_exists and servico_exists:
                # Testar inserção SQL direta
                try:
                    db.session.execute(text("""
                        INSERT INTO servico_obra (obra_id, servico_id, quantidade_planejada, quantidade_executada, ativo)
                        VALUES (:obra_id, :servico_id, :quantidade_planejada, :quantidade_executada, :ativo)
                        ON CONFLICT (obra_id, servico_id) DO NOTHING
                    """), test_data)
                    
                    print("   - ✅ Inserção SQL direta funcionou")
                    db.session.rollback()  # Não commitar o teste
                    
                except Exception as e:
                    print(f"   - ❌ Erro inserção SQL: {e}")
                    db.session.rollback()
            
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        # 6. Verificar problemas específicos de produção
        print("\n🚨 6. PROBLEMAS COMUNS PRODUÇÃO:")
        
        # Verificar se tabela tem campo data_criacao vs created_at
        try:
            columns = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'servico_obra' 
                AND column_name IN ('created_at', 'data_criacao', 'updated_at', 'data_atualizacao')
            """)).fetchall()
            
            column_names = [row[0] for row in columns]
            print(f"   - Campos de data encontrados: {column_names}")
            
            if 'data_criacao' in column_names and 'created_at' not in column_names:
                print("   ⚠️ POSSÍVEL PROBLEMA: Usando 'data_criacao' mas código espera 'created_at'")
            elif 'created_at' in column_names:
                print("   ✅ Campo 'created_at' presente")
                
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        print("\n" + "=" * 60)
        print("✅ DIAGNÓSTICO CONCLUÍDO")
        
except Exception as e:
    print(f"❌ ERRO CRÍTICO: {e}")
    print("Certifique-se de que está rodando no contexto da aplicação Flask")