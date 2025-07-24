#!/usr/bin/env python3
"""
Script para corrigir os problemas de cadastro nas páginas de configuração específico para produção
"""

from app import app, db
from models import *
from forms import DepartamentoForm, FuncaoForm
from werkzeug.security import generate_password_hash
from datetime import datetime, time

def corrigir_problemas():
    with app.app_context():
        print("🔧 Corrigindo problemas de cadastro no ambiente de produção...")
        
        # 1. Testar criação direta de dados (sem formulário)
        print("\n1. Testando criação direta de dados:")
        
        try:
            # Teste 1: Departamento
            dept_teste = Departamento(
                nome=f"Depto Teste {datetime.now().strftime('%H%M%S')}",
                descricao="Teste de produção"
            )
            db.session.add(dept_teste)
            db.session.commit()
            print(f"✅ Departamento criado: {dept_teste.nome} (ID: {dept_teste.id})")
            
            # Teste 2: Função
            func_teste = Funcao(
                nome=f"Função Teste {datetime.now().strftime('%H%M%S')}",
                descricao="Teste de produção",
                salario_base=2500.00
            )
            db.session.add(func_teste)
            db.session.commit()
            print(f"✅ Função criada: {func_teste.nome} (ID: {func_teste.id})")
            
            # Teste 3: Horário
            horario_teste = HorarioTrabalho(
                nome=f"Horário Teste {datetime.now().strftime('%H%M%S')}",
                entrada=time(8, 0),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                horas_diarias=8.0,
                dias_semana="Segunda a Sexta",
                valor_hora=15.00
            )
            db.session.add(horario_teste)
            db.session.commit()
            print(f"✅ Horário criado: {horario_teste.nome} (ID: {horario_teste.id})")
            
            # Teste 4: Serviço
            servico_teste = Servico(
                nome=f"Serviço Teste {datetime.now().strftime('%H%M%S')}",
                categoria="teste",
                unidade_medida="m²",
                complexidade=3,
                requer_especializacao=False,
                ativo=True
            )
            db.session.add(servico_teste)
            db.session.commit()
            print(f"✅ Serviço criado: {servico_teste.nome} (ID: {servico_teste.id})")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na criação direta: {e}")
        
        # 2. Verificar se os dados foram criados
        print("\n2. Verificando totais após criação:")
        print(f"Departamentos: {Departamento.query.count()}")
        print(f"Funções: {Funcao.query.count()}")
        print(f"Horários: {HorarioTrabalho.query.count()}")
        print(f"Serviços: {Servico.query.count()}")
        
        # 3. Verificar usuários e autenticação
        print("\n3. Verificando usuários:")
        usuarios = Usuario.query.all()
        for user in usuarios[:5]:  # Mostrar apenas 5
            print(f"- {user.username} ({user.tipo_usuario.name}) - Ativo: {user.ativo}")
        
        print(f"\nTotal de usuários: {len(usuarios)}")

if __name__ == "__main__":
    corrigir_problemas()