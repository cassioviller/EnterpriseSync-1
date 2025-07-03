#!/usr/bin/env python3
"""
Script simples para popular o banco de dados do SIGE
"""

from app import app, db
from models import (
    Usuario, Departamento, Funcao, Funcionario, Obra, Veiculo, 
    Servico, RegistroPonto, RegistroAlimentacao, CustoObra, HorarioTrabalho
)
from werkzeug.security import generate_password_hash
from datetime import date, datetime, time
import logging

logging.basicConfig(level=logging.INFO)

def populate_database():
    with app.app_context():
        print("Iniciando população do banco de dados...")
        
        # Limpar dados existentes
        RegistroAlimentacao.query.delete()
        RegistroPonto.query.delete()
        CustoObra.query.delete()
        Funcionario.query.delete()
        Obra.query.delete()
        Veiculo.query.delete()
        Servico.query.delete()
        Funcao.query.delete()
        Departamento.query.delete()
        HorarioTrabalho.query.delete()
        Usuario.query.delete()
        db.session.commit()
        
        # 1. Criar horários de trabalho
        horarios = [
            HorarioTrabalho(
                nome='Comercial - Segunda a Sexta',
                entrada=time(8, 0),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                dias_semana='1,2,3,4,5'
            ),
            HorarioTrabalho(
                nome='Obra - Segunda a Sábado',
                entrada=time(7, 0),
                saida_almoco=time(11, 30),
                retorno_almoco=time(12, 30),
                saida=time(16, 0),
                dias_semana='1,2,3,4,5,6'
            ),
            HorarioTrabalho(
                nome='Noturno - Segunda a Sexta',
                entrada=time(22, 0),
                saida_almoco=time(2, 0),
                retorno_almoco=time(3, 0),
                saida=time(6, 0),
                dias_semana='1,2,3,4,5'
            )
        ]
        
        for horario in horarios:
            db.session.add(horario)
        db.session.commit()
        print(f"✓ Criados {len(horarios)} horários de trabalho")
        
        # 2. Criar departamentos
        departamentos = [
            Departamento(nome='Administração', descricao='Setor administrativo e financeiro'),
            Departamento(nome='Engenharia', descricao='Projetos e planejamento de obras'),
            Departamento(nome='Construção Civil', descricao='Execução de obras e serviços'),
            Departamento(nome='Manutenção', descricao='Manutenção de equipamentos e veículos'),
            Departamento(nome='Recursos Humanos', descricao='Gestão de pessoas e benefícios'),
            Departamento(nome='Segurança do Trabalho', descricao='Segurança e saúde ocupacional')
        ]
        
        for dept in departamentos:
            db.session.add(dept)
        db.session.commit()
        print(f"✓ Criados {len(departamentos)} departamentos")
        
        # 3. Criar funções
        funcoes = [
            Funcao(nome='Diretor Geral', descricao='Direção executiva da empresa', salario_base=20000.00),
            Funcao(nome='Engenheiro Civil', descricao='Projetos e supervisão de obras', salario_base=8500.00),
            Funcao(nome='Pedreiro', descricao='Execução de obras de alvenaria', salario_base=4500.00),
            Funcao(nome='Servente', descricao='Auxiliar geral de obras', salario_base=2800.00),
            Funcao(nome='Contador', descricao='Gestão contábil e fiscal', salario_base=7200.00),
            Funcao(nome='Mecânico', descricao='Manutenção de veículos e equipamentos', salario_base=3800.00),
            Funcao(nome='Auxiliar Administrativo', descricao='Suporte administrativo', salario_base=2500.00),
            Funcao(nome='Analista de RH', descricao='Gestão de recursos humanos', salario_base=5500.00),
            Funcao(nome='Técnico em Segurança', descricao='Segurança do trabalho', salario_base=4200.00),
            Funcao(nome='Técnico em Segurança do Trabalho', descricao='Segurança e saúde ocupacional', salario_base=4000.00)
        ]
        
        for funcao in funcoes:
            db.session.add(funcao)
        db.session.commit()
        print(f"✓ Criadas {len(funcoes)} funções")
        
        # 4. Criar usuário admin
        admin_user = Usuario(
            username='admin',
            email='admin@estruturasdovale.com.br',
            password_hash=generate_password_hash('admin123'),
            nome='Administrador do Sistema',
            ativo=True
        )
        db.session.add(admin_user)
        db.session.commit()
        print("✓ Usuário administrador criado: admin/admin123")
        
        # 5. Buscar os IDs criados para usar nos funcionários
        dept_admin = Departamento.query.filter_by(nome='Administração').first()
        dept_eng = Departamento.query.filter_by(nome='Engenharia').first()
        dept_const = Departamento.query.filter_by(nome='Construção Civil').first()
        dept_manut = Departamento.query.filter_by(nome='Manutenção').first()
        dept_rh = Departamento.query.filter_by(nome='Recursos Humanos').first()
        dept_seg = Departamento.query.filter_by(nome='Segurança do Trabalho').first()
        
        func_diretor = Funcao.query.filter_by(nome='Diretor Geral').first()
        func_eng = Funcao.query.filter_by(nome='Engenheiro Civil').first()
        func_pedreiro = Funcao.query.filter_by(nome='Pedreiro').first()
        func_servente = Funcao.query.filter_by(nome='Servente').first()
        func_contador = Funcao.query.filter_by(nome='Contador').first()
        func_mecanico = Funcao.query.filter_by(nome='Mecânico').first()
        func_aux_adm = Funcao.query.filter_by(nome='Auxiliar Administrativo').first()
        func_analista_rh = Funcao.query.filter_by(nome='Analista de RH').first()
        func_tec_seg = Funcao.query.filter_by(nome='Técnico em Segurança').first()
        
        # 6. Criar funcionários
        funcionarios = [
            Funcionario(
                nome='João Silva Santos',
                cpf='123.456.789-01',
                rg='MG-12345678',
                data_nascimento=date(1980, 1, 1),
                endereco='Rua das Flores, 100 - Belo Horizonte, MG',
                telefone='(31) 98000-1234',
                email='joao.silva@estruturasdovale.com.br',
                data_admissao=date(2020, 1, 1),
                salario=15000.00,
                departamento_id=dept_admin.id,
                funcao_id=func_diretor.id,
                ativo=True
            ),
            Funcionario(
                nome='Maria Oliveira Costa',
                cpf='234.567.890-12',
                rg='MG-12345679',
                data_nascimento=date(1985, 5, 15),
                endereco='Rua das Flores, 110 - Belo Horizonte, MG',
                telefone='(31) 98001-1235',
                email='maria.oliveira@estruturasdovale.com.br',
                data_admissao=date(2021, 3, 10),
                salario=8500.00,
                departamento_id=dept_eng.id,
                funcao_id=func_eng.id,
                ativo=True
            ),
            Funcionario(
                nome='Carlos Pereira Lima',
                cpf='345.678.901-23',
                rg='MG-12345680',
                data_nascimento=date(1990, 8, 20),
                endereco='Rua das Flores, 120 - Belo Horizonte, MG',
                telefone='(31) 98002-1236',
                email='carlos.pereira@estruturasdovale.com.br',
                data_admissao=date(2022, 6, 5),
                salario=4500.00,
                departamento_id=dept_const.id,
                funcao_id=func_pedreiro.id,
                ativo=True
            ),
            Funcionario(
                nome='Ana Santos Rodrigues',
                cpf='456.789.012-34',
                rg='MG-12345681',
                data_nascimento=date(1992, 12, 3),
                endereco='Rua das Flores, 130 - Belo Horizonte, MG',
                telefone='(31) 98003-1237',
                email='ana.santos@estruturasdovale.com.br',
                data_admissao=date(2023, 1, 15),
                salario=2800.00,
                departamento_id=dept_const.id,
                funcao_id=func_servente.id,
                ativo=True
            ),
            Funcionario(
                nome='Pedro Lima Sousa',
                cpf='567.890.123-45',
                rg='MG-12345682',
                data_nascimento=date(1978, 4, 12),
                endereco='Rua das Flores, 140 - Belo Horizonte, MG',
                telefone='(31) 98004-1238',
                email='pedro.lima@estruturasdovale.com.br',
                data_admissao=date(2019, 9, 8),
                salario=7200.00,
                departamento_id=dept_admin.id,
                funcao_id=func_contador.id,
                ativo=True
            )
        ]
        
        for funcionario in funcionarios:
            db.session.add(funcionario)
        db.session.commit()
        print(f"✓ Criados {len(funcionarios)} funcionários")
        
        # 7. Criar algumas obras
        obras = [
            Obra(
                nome='Residencial Belo Horizonte',
                endereco='Av. Brasil, 1000 - Belo Horizonte, MG',
                data_inicio=date(2024, 1, 15),
                data_previsao_fim=date(2024, 12, 31),
                orcamento=500000.00,
                status='Em andamento',
                responsavel_id=funcionarios[1].id  # Maria Oliveira (Engenheira)
            ),
            Obra(
                nome='Comercial Centro',
                endereco='Rua da Liberdade, 500 - Belo Horizonte, MG',
                data_inicio=date(2024, 3, 1),
                data_previsao_fim=date(2024, 10, 15),
                orcamento=300000.00,
                status='Em andamento',
                responsavel_id=funcionarios[1].id  # Maria Oliveira (Engenheira)
            )
        ]
        
        for obra in obras:
            db.session.add(obra)
        db.session.commit()
        print(f"✓ Criadas {len(obras)} obras")
        
        # 8. Criar alguns veículos
        veiculos = [
            Veiculo(
                placa='ABC-1234',
                marca='Ford',
                modelo='F-4000',
                ano=2020,
                tipo='Caminhão',
                status='Disponível',
                km_atual=45000
            ),
            Veiculo(
                placa='DEF-5678',
                marca='Volkswagen',
                modelo='Saveiro',
                ano=2021,
                tipo='Caminhão',
                status='Em uso',
                km_atual=32000
            )
        ]
        
        for veiculo in veiculos:
            db.session.add(veiculo)
        db.session.commit()
        print(f"✓ Criados {len(veiculos)} veículos")
        
        # 9. Criar alguns serviços
        servicos = [
            Servico(
                nome='Alvenaria de Vedação',
                descricao='Execução de alvenaria de vedação',
                preco_unitario=25.00
            ),
            Servico(
                nome='Concretagem',
                descricao='Serviços de concretagem',
                preco_unitario=180.00
            ),
            Servico(
                nome='Instalação Elétrica',
                descricao='Instalações elétricas residenciais',
                preco_unitario=45.00
            )
        ]
        
        for servico in servicos:
            db.session.add(servico)
        db.session.commit()
        print(f"✓ Criados {len(servicos)} serviços")
        
        print("\n🎉 Banco de dados populado com sucesso!")
        print(f"   • {HorarioTrabalho.query.count()} horários de trabalho")
        print(f"   • {Departamento.query.count()} departamentos")
        print(f"   • {Funcao.query.count()} funções")
        print(f"   • {Funcionario.query.count()} funcionários")
        print(f"   • {Obra.query.count()} obras")
        print(f"   • {Veiculo.query.count()} veículos")
        print(f"   • {Servico.query.count()} serviços")

if __name__ == '__main__':
    populate_database()