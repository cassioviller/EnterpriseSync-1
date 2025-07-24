#!/usr/bin/env python3
"""
Script para testar criação de funcionário e identificar problema
"""

from app import app, db
from models import *
from utils import validar_cpf, gerar_codigo_funcionario
from datetime import date

def testar_funcionario():
    with app.app_context():
        try:
            print("🔍 Testando criação de funcionário...")
            
            # Usar um admin existente
            admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
            if not admin:
                print("❌ Nenhum admin encontrado!")
                return
            
            print(f"✅ Admin encontrado: {admin.email}")
            
            # Dados de teste
            cpf_teste = "987.654.321-09"
            nome_teste = "Pedro Teste Funcionário"
            
            # Verificar se CPF já existe
            existente = Funcionario.query.filter_by(cpf=cpf_teste).first()
            if existente:
                print(f"⚠️  Funcionário já existe: {existente.nome}")
                return
            
            # Criar funcionário
            funcionario = Funcionario(
                nome=nome_teste,
                cpf=cpf_teste,
                admin_id=admin.id,
                data_admissao=date.today(),
                salario=2500.00,
                ativo=True
            )
            
            # Gerar código
            funcionario.codigo = gerar_codigo_funcionario()
            
            db.session.add(funcionario)
            db.session.commit()
            
            print(f"✅ Funcionário criado com sucesso!")
            print(f"   - ID: {funcionario.id}")
            print(f"   - Código: {funcionario.codigo}")
            print(f"   - Nome: {funcionario.nome}")
            print(f"   - CPF: {funcionario.cpf}")
            print(f"   - Admin ID: {funcionario.admin_id}")
            
            # Verificar na base
            verificacao = Funcionario.query.filter_by(cpf=cpf_teste).first()
            if verificacao:
                print(f"✅ Verificação: Funcionário encontrado na base!")
            else:
                print(f"❌ Verificação: Funcionário NÃO encontrado na base!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar funcionário: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    testar_funcionario()