#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para adicionar campo 'codigo' aos funcionários existentes
e garantir que todos tenham códigos únicos no formato F0001, F0002, etc.
"""

from app import app, db
from models import Funcionario
from sqlalchemy import text

def adicionar_campo_codigo():
    """Adiciona o campo código à tabela funcionario"""
    
    with app.app_context():
        try:
            # Verificar se o campo já existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='funcionario' AND column_name='codigo'
            """))
            
            if result.fetchone():
                print("Campo 'codigo' já existe na tabela funcionario")
                return
            
            # Adicionar o campo código
            print("Adicionando campo 'codigo' à tabela funcionario...")
            db.session.execute(text("""
                ALTER TABLE funcionario 
                ADD COLUMN codigo VARCHAR(10) UNIQUE
            """))
            
            db.session.commit()
            print("Campo 'codigo' adicionado com sucesso!")
            
            # Gerar códigos para funcionários existentes
            gerar_codigos_funcionarios()
            
        except Exception as e:
            print(f"Erro ao adicionar campo código: {e}")
            db.session.rollback()

def gerar_codigos_funcionarios():
    """Gera códigos únicos para funcionários que não possuem"""
    
    with app.app_context():
        try:
            # Buscar funcionários sem código
            funcionarios_sem_codigo = Funcionario.query.filter(
                Funcionario.codigo.is_(None)
            ).all()
            
            if not funcionarios_sem_codigo:
                print("Todos os funcionários já possuem códigos")
                return
            
            print(f"Gerando códigos para {len(funcionarios_sem_codigo)} funcionários...")
            
            # Buscar o último código usado
            ultimo_funcionario = Funcionario.query.filter(
                Funcionario.codigo.isnot(None)
            ).order_by(Funcionario.codigo.desc()).first()
            
            if ultimo_funcionario and ultimo_funcionario.codigo:
                # Extrair número do último código (ex: F0005 -> 5)
                ultimo_numero = int(ultimo_funcionario.codigo[1:])
            else:
                ultimo_numero = 0
            
            # Gerar códigos sequenciais
            for i, funcionario in enumerate(funcionarios_sem_codigo, start=1):
                novo_numero = ultimo_numero + i
                novo_codigo = f"F{novo_numero:04d}"  # F0001, F0002, etc.
                
                funcionario.codigo = novo_codigo
                print(f"Funcionário {funcionario.nome} -> {novo_codigo}")
            
            db.session.commit()
            print("Códigos gerados com sucesso!")
            
        except Exception as e:
            print(f"Erro ao gerar códigos: {e}")
            db.session.rollback()

if __name__ == '__main__':
    adicionar_campo_codigo()