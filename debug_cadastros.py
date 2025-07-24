#!/usr/bin/env python3
"""
Script para testar problemas de cadastro das páginas de configuração
"""

from app import app, db
from models import *

def testar_cadastros():
    with app.app_context():
        print("🔍 Testando problemas de cadastro nas páginas de configuração...")
        
        # 1. Verificar se os modelos existem
        print("\n1. Verificando modelos:")
        try:
            departamentos = Departamento.query.count()
            print(f"✅ Departamentos: {departamentos} registros")
        except Exception as e:
            print(f"❌ Erro no modelo Departamento: {e}")
        
        try:
            funcoes = Funcao.query.count()
            print(f"✅ Funções: {funcoes} registros")
        except Exception as e:
            print(f"❌ Erro no modelo Funcao: {e}")
        
        try:
            horarios = HorarioTrabalho.query.count()
            print(f"✅ Horários: {horarios} registros")
        except Exception as e:
            print(f"❌ Erro no modelo HorarioTrabalho: {e}")
        
        try:
            servicos = Servico.query.count()
            print(f"✅ Serviços: {servicos} registros")
        except Exception as e:
            print(f"❌ Erro no modelo Servico: {e}")
        
        # 2. Testar criação de dados
        print("\n2. Testando criação de dados:")
        
        # Testar departamento
        try:
            dept = Departamento(nome="Teste Departamento", descricao="Teste")
            db.session.add(dept)
            db.session.flush()
            print(f"✅ Departamento criado com ID: {dept.id}")
            db.session.rollback()
        except Exception as e:
            print(f"❌ Erro ao criar departamento: {e}")
            db.session.rollback()
        
        # Testar função
        try:
            func = Funcao(nome="Teste Função", descricao="Teste", salario_base=2500.00)
            db.session.add(func)
            db.session.flush()
            print(f"✅ Função criada com ID: {func.id}")
            db.session.rollback()
        except Exception as e:
            print(f"❌ Erro ao criar função: {e}")
            db.session.rollback()
        
        # Testar horário
        try:
            from datetime import time
            horario = HorarioTrabalho(
                nome="Teste Horário",
                entrada=time(8, 0),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                horas_diarias=8.0,
                dias_semana="Segunda a Sexta"
            )
            db.session.add(horario)
            db.session.flush()
            print(f"✅ Horário criado com ID: {horario.id}")
            db.session.rollback()
        except Exception as e:
            print(f"❌ Erro ao criar horário: {e}")
            db.session.rollback()
        
        # Testar serviço
        try:
            servico = Servico(
                nome="Teste Serviço",
                categoria="Teste",
                unidade_medida="m²",
                ativo=True
            )
            db.session.add(servico)
            db.session.flush()
            print(f"✅ Serviço criado com ID: {servico.id}")
            db.session.rollback()
        except Exception as e:
            print(f"❌ Erro ao criar serviço: {e}")
            db.session.rollback()

if __name__ == "__main__":
    testar_cadastros()