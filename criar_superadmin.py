#!/usr/bin/env python3
"""
Script para criar super admin e dados básicos no banco SQLite local
"""

from app import app, db
from models import Usuario, TipoUsuario, Departamento, Funcao, HorarioTrabalho, Servico
from werkzeug.security import generate_password_hash
from datetime import time

def criar_dados_basicos():
    with app.app_context():
        print("🔧 Criando super admin e dados básicos...")
        
        try:
            # Criar super admin
            if not Usuario.query.filter_by(username='axiom').first():
                super_admin = Usuario(
                    username='axiom',
                    email='axiom@sige.com',
                    password_hash=generate_password_hash('cassio123'),
                    tipo_usuario=TipoUsuario.SUPER_ADMIN,
                    ativo=True
                )
                db.session.add(super_admin)
                print("✅ Super Admin 'axiom' criado")
            
            # Criar admin valeverde
            if not Usuario.query.filter_by(username='valeverde').first():
                admin = Usuario(
                    username='valeverde',
                    email='admin@valeverde.com.br',
                    password_hash=generate_password_hash('admin123'),
                    tipo_usuario=TipoUsuario.ADMIN,
                    ativo=True
                )
                db.session.add(admin)
                print("✅ Admin 'valeverde' criado")
            
            # Criar alguns departamentos básicos
            departamentos_basicos = [
                "Recursos Humanos", "Engenharia", "Operações", 
                "Administração", "Financeiro"
            ]
            
            for nome_dept in departamentos_basicos:
                if not Departamento.query.filter_by(nome=nome_dept).first():
                    dept = Departamento(nome=nome_dept, descricao=f"Departamento de {nome_dept}")
                    db.session.add(dept)
            
            # Criar algumas funções básicas
            funcoes_basicas = [
                ("Engenheiro Civil", "Responsável por projetos estruturais", 8000.00),
                ("Pedreiro", "Execução de alvenaria e estruturas", 3500.00),
                ("Servente", "Apoio geral na obra", 2200.00),
                ("Encarregado", "Supervisão de equipes", 5000.00)
            ]
            
            for nome, desc, salario in funcoes_basicas:
                if not Funcao.query.filter_by(nome=nome).first():
                    funcao = Funcao(nome=nome, descricao=desc, salario_base=salario)
                    db.session.add(funcao)
            
            # Criar horário básico
            if not HorarioTrabalho.query.filter_by(nome="Padrão 8h").first():
                horario = HorarioTrabalho(
                    nome="Padrão 8h",
                    entrada=time(7, 0),
                    saida_almoco=time(12, 0),
                    retorno_almoco=time(13, 0),
                    saida=time(16, 0),
                    horas_diarias=8.0,
                    dias_semana="Segunda a Sexta",
                    valor_hora=15.00
                )
                db.session.add(horario)
            
            # Criar alguns serviços básicos
            servicos_basicos = [
                ("Alvenaria de Vedação", "alvenaria", "m²", 3),
                ("Concretagem", "estrutura", "m³", 4),
                ("Pintura", "acabamento", "m²", 2),
                ("Instalação Elétrica", "instalacoes", "m²", 4)
            ]
            
            for nome, categoria, unidade, complexidade in servicos_basicos:
                if not Servico.query.filter_by(nome=nome).first():
                    servico = Servico(
                        nome=nome,
                        categoria=categoria,
                        unidade_medida=unidade,
                        complexidade=complexidade,
                        requer_especializacao=complexidade >= 4,
                        ativo=True
                    )
                    db.session.add(servico)
            
            db.session.commit()
            print("✅ Dados básicos criados com sucesso!")
            
            # Mostrar resumo
            print(f"\n📊 Resumo dos dados criados:")
            print(f"Usuários: {Usuario.query.count()}")
            print(f"Departamentos: {Departamento.query.count()}")
            print(f"Funções: {Funcao.query.count()}")
            print(f"Horários: {HorarioTrabalho.query.count()}")
            print(f"Serviços: {Servico.query.count()}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    criar_dados_basicos()