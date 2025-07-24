#!/usr/bin/env python3
"""
Script para configurar banco de dados em produção
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

import os
import sys
from datetime import datetime, date
from werkzeug.security import generate_password_hash

# Configurar Flask app
os.environ.setdefault('FLASK_APP', 'main.py')

# Importar após configurar FLASK_APP
from app import app, db
from models import *

def create_super_admin():
    """Cria super admin se não existir"""
    print("🔧 Verificando Super Admin...")
    
    # Verificar por username 'admin' primeiro
    admin_user = Usuario.query.filter_by(username='admin').first()
    
    if admin_user:
        # Se existe, atualizar para SUPER_ADMIN se necessário
        if admin_user.tipo_usuario != TipoUsuario.SUPER_ADMIN:
            admin_user.tipo_usuario = TipoUsuario.SUPER_ADMIN
            admin_user.ativo = True
            db.session.commit()
            print(f"✅ Usuário admin atualizado para SUPER_ADMIN: {admin_user.email}")
        else:
            print(f"✅ Super Admin já existe: {admin_user.email}")
        return admin_user
    
    # Se não existe, criar novo
    print("   Criando Super Admin...")
    super_admin = Usuario(
        nome='Super Administrador',
        username='admin',
        email='admin@sige.com',
        password_hash=generate_password_hash('admin123'),
        tipo_usuario=TipoUsuario.SUPER_ADMIN,
        ativo=True
    )
    db.session.add(super_admin)
    db.session.commit()
    print(f"✅ Super Admin criado: admin@sige.com / admin123")
    
    return super_admin

def create_demo_admin():
    """Cria admin de demonstração"""
    print("🏗️ Criando Admin de Demonstração...")
    
    demo_admin = Usuario.query.filter_by(username='valeverde').first()
    
    if not demo_admin:
        demo_admin = Usuario(
            nome='Vale Verde Construções',
            username='valeverde',
            email='admin@valeverde.com',
            password_hash=generate_password_hash('admin123'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True
        )
        db.session.add(demo_admin)
        db.session.commit()
        print("✅ Admin de demonstração criado: valeverde / admin123")
    else:
        print("✅ Admin de demonstração já existe")
    
    return demo_admin

def create_basic_data(admin_id):
    """Cria dados básicos para o sistema"""
    print("📋 Criando dados básicos...")
    
    # Departamentos
    if Departamento.query.count() == 0:
        departamentos = [
            Departamento(nome='Administração', descricao='Setor administrativo'),
            Departamento(nome='Obras', descricao='Execução de obras'),
            Departamento(nome='Engenharia', descricao='Projetos e planejamento'),
            Departamento(nome='Manutenção', descricao='Manutenção de equipamentos')
        ]
        for dept in departamentos:
            db.session.add(dept)
        print("✅ Departamentos criados")
    else:
        print("✅ Departamentos já existem")
    
    # Funções
    if Funcao.query.count() == 0:
        funcoes = [
            Funcao(nome='Pedreiro', salario_base=2500.0, descricao='Execução de alvenaria'),
            Funcao(nome='Servente', salario_base=1800.0, descricao='Auxílio geral'),
            Funcao(nome='Encarregado', salario_base=3500.0, descricao='Supervisão de equipes'),
            Funcao(nome='Engenheiro', salario_base=8000.0, descricao='Gestão técnica')
        ]
        for funcao in funcoes:
            db.session.add(funcao)
        print("✅ Funções criadas")
    else:
        print("✅ Funções já existem")
    
    # Horários de Trabalho
    if HorarioTrabalho.query.count() == 0:
        from datetime import time
        horario = HorarioTrabalho(
            nome='Padrão (7h12-17h)',
            entrada=time(7, 12),
            saida_almoco=time(12, 0),
            retorno_almoco=time(13, 0),
            saida=time(17, 0),
            dias_semana='1,2,3,4,5',
            horas_diarias=8.0,
            valor_hora=15.0
        )
        db.session.add(horario)
        print("✅ Horário de trabalho padrão criado")
    else:
        print("✅ Horário de trabalho já existe")
    
    # Obra de demonstração
    obras_admin = Obra.query.filter_by(admin_id=admin_id).count()
    if obras_admin == 0:
        obra = Obra(
            nome='Obra Demonstração - Residencial Jardim',
            codigo='OB001',
            endereco='Rua das Flores, 123 - Centro',
            data_inicio=date(2025, 1, 15),
            data_previsao_fim=date(2025, 12, 30),
            orcamento=250000.0,
            valor_contrato=280000.0,
            area_total_m2=120.0,
            status='Em andamento',
            admin_id=admin_id
        )
        db.session.add(obra)
        print("✅ Obra de demonstração criada")
    else:
        print("✅ Obras já existem para este admin")
    
    # Veículos
    veiculos_admin = Veiculo.query.filter_by(admin_id=admin_id).count()
    if veiculos_admin == 0:
        veiculos = [
            Veiculo(
                placa='ABC-1234',
                marca='Ford',
                modelo='Ranger',
                ano=2020,
                tipo='Caminhonete',
                status='Disponível',
                admin_id=admin_id
            ),
            Veiculo(
                placa='DEF-5678',
                marca='Mercedes',
                modelo='Sprinter',
                ano=2019,
                tipo='Van',
                status='Disponível',
                admin_id=admin_id
            )
        ]
        for veiculo in veiculos:
            db.session.add(veiculo)
        print("✅ Veículos de demonstração criados")
    else:
        print("✅ Veículos já existem para este admin")
    
    db.session.commit()

def create_demo_employees(admin_id):
    """Cria funcionários de demonstração"""
    print("👥 Criando funcionários de demonstração...")
    
    if Funcionario.query.count() < 3:
        # Buscar dados necessários
        dept_obras = Departamento.query.filter_by(nome='Obras').first()
        funcao_pedreiro = Funcao.query.filter_by(nome='Pedreiro').first()
        funcao_servente = Funcao.query.filter_by(nome='Servente').first()
        horario = HorarioTrabalho.query.first()
        
        funcionarios = [
            Funcionario(
                codigo='F0001',
                nome='João Silva Santos',
                cpf='123.456.789-01',
                rg='12.345.678-9',
                data_nascimento=date(1985, 3, 15),
                endereco='Rua A, 100',
                telefone='(11) 98765-4321',
                email='joao@valeverde.com',
                data_admissao=date(2024, 1, 10),
                salario=2800.0,
                departamento_id=dept_obras.id if dept_obras else None,
                funcao_id=funcao_pedreiro.id if funcao_pedreiro else None,
                horario_trabalho_id=horario.id if horario else None,
                admin_id=admin_id
            ),
            Funcionario(
                codigo='F0002',
                nome='Maria Oliveira Costa',
                cpf='987.654.321-02',
                rg='98.765.432-1',
                data_nascimento=date(1990, 7, 22),
                endereco='Rua B, 200',
                telefone='(11) 91234-5678',
                email='maria@valeverde.com',
                data_admissao=date(2024, 2, 15),
                salario=2000.0,
                departamento_id=dept_obras.id if dept_obras else None,
                funcao_id=funcao_servente.id if funcao_servente else None,
                horario_trabalho_id=horario.id if horario else None,
                admin_id=admin_id
            ),
            Funcionario(
                codigo='F0003',
                nome='Pedro Santos Lima',
                cpf='456.789.123-03',
                rg='45.678.912-3',
                data_nascimento=date(1988, 11, 8),
                endereco='Rua C, 300',
                telefone='(11) 95555-1234',
                email='pedro@valeverde.com',
                data_admissao=date(2024, 3, 1),
                salario=2600.0,
                departamento_id=dept_obras.id if dept_obras else None,
                funcao_id=funcao_pedreiro.id if funcao_pedreiro else None,
                horario_trabalho_id=horario.id if horario else None,
                admin_id=admin_id
            )
        ]
        
        for funcionario in funcionarios:
            db.session.add(funcionario)
        
        db.session.commit()
        print("✅ Funcionários de demonstração criados")

def main():
    """Função principal"""
    print("🚀 CONFIGURAÇÃO DO BANCO DE DADOS - SIGE v8.0")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Criar tabelas
            print("📅 Criando tabelas do banco...")
            db.create_all()
            print("✅ Tabelas criadas com sucesso")
            
            # Criar super admin
            super_admin = create_super_admin()
            
            # Criar admin de demonstração
            demo_admin = create_demo_admin()
            
            # Criar dados básicos
            create_basic_data(demo_admin.id)
            
            # Criar funcionários de demonstração
            create_demo_employees(demo_admin.id)
            
            print("\n🎯 CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 50)
            print("🔑 CREDENCIAIS DE ACESSO:")
            print(f"   Super Admin: admin@sige.com / admin123")
            print(f"   Admin Demo:  valeverde / admin123")
            print("\n📊 DADOS CRIADOS:")
            print(f"   • {Usuario.query.count()} usuários")
            print(f"   • {Funcionario.query.count()} funcionários")
            print(f"   • {Obra.query.count()} obras")
            print(f"   • {Veiculo.query.count()} veículos")
            print(f"   • {Departamento.query.count()} departamentos")
            print(f"   • {Funcao.query.count()} funções")
            
        except Exception as e:
            print(f"❌ Erro durante configuração: {e}")
            return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)