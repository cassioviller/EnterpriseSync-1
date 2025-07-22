#!/usr/bin/env python3
"""
Criação Completa da Construtora Vale Verde
Sistema SIGE v8.0 - Dados conforme especificação do usuário
"""

from app import app, db
from models import *
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time, timedelta
import random

def criar_admin_vale_verde():
    """Cria o administrador específico da Construtora Vale Verde"""
    print("👤 Criando administrador Construtora Vale Verde...")
    
    # Verificar se já existe
    admin_vale_verde = Usuario.query.filter_by(username='valeverde').first()
    if not admin_vale_verde:
        admin_vale_verde = Usuario(
            username='valeverde',
            email='admin@valeverde.com.br',
            password_hash=generate_password_hash('admin123'),
            nome='Administrador Vale Verde',
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True
        )
        db.session.add(admin_vale_verde)
        print("   ✅ Admin 'valeverde' criado")
    else:
        print("   ℹ️ Admin 'valeverde' já existe")
    
    db.session.commit()
    return admin_vale_verde

def criar_horarios_vale_verde():
    """Cria horários específicos da Vale Verde"""
    print("⏰ Criando horários Vale Verde...")
    
    horarios_data = [
        {
            'nome': 'Comercial Vale Verde',
            'entrada': time(7, 12),
            'saida_almoco': time(12, 0),
            'retorno_almoco': time(13, 0),
            'saida': time(17, 0),
            'dias_semana': '1,2,3,4,5',
            'horas_diarias': 8.8,
            'valor_hora': 15.0
        },
        {
            'nome': 'Estagiário Vale Verde',
            'entrada': time(7, 12),
            'saida_almoco': time(12, 12),
            'retorno_almoco': time(12, 12),
            'saida': time(12, 12),
            'dias_semana': '1,2,3,4,5',
            'horas_diarias': 5.0,
            'valor_hora': 8.0
        },
        {
            'nome': 'Obra Vale Verde',
            'entrada': time(7, 0),
            'saida_almoco': time(12, 0),
            'retorno_almoco': time(13, 0),
            'saida': time(17, 0),
            'dias_semana': '1,2,3,4,5,6',
            'horas_diarias': 9.0,
            'valor_hora': 18.0
        }
    ]
    
    for horario_info in horarios_data:
        horario_existente = HorarioTrabalho.query.filter_by(nome=horario_info['nome']).first()
        if not horario_existente:
            horario = HorarioTrabalho(**horario_info)
            db.session.add(horario)
            print(f"   ✅ Horário {horario.nome} criado")
        else:
            print(f"   ℹ️ Horário {horario_info['nome']} já existe")
    
    db.session.commit()
    print("   🔄 Horários salvos!\n")
    return {h.nome: h for h in HorarioTrabalho.query.all()}

def criar_departamentos_vale_verde():
    """Cria departamentos específicos da Vale Verde"""
    print("🏢 Criando departamentos Vale Verde...")
    
    departamentos_data = [
        {'nome': 'Administrativo VV', 'descricao': 'Gerência, RH e Financeiro - Construtora Vale Verde'},
        {'nome': 'Operacional VV', 'descricao': 'Engenharia, Obras e Manutenção - Construtora Vale Verde'},
        {'nome': 'Comercial VV', 'descricao': 'Vendas e Atendimento - Construtora Vale Verde'}
    ]
    
    for dept_data in departamentos_data:
        dept_existente = Departamento.query.filter_by(nome=dept_data['nome']).first()
        if not dept_existente:
            dept = Departamento(**dept_data)
            db.session.add(dept)
            print(f"   ✅ Departamento {dept.nome} criado")
        else:
            print(f"   ℹ️ Departamento {dept_data['nome']} já existe")
    
    db.session.commit()
    print("   🔄 Departamentos salvos!\n")
    return {d.nome: d for d in Departamento.query.all()}

def criar_funcoes_vale_verde():
    """Cria funções específicas da Vale Verde"""
    print("👷 Criando funções Vale Verde...")
    
    funcoes_data = [
        {'nome': 'Gerente Geral VV', 'descricao': 'Gerenciamento geral - Vale Verde', 'salario_base': 8500.0},
        {'nome': 'Analista RH VV', 'descricao': 'Recursos humanos - Vale Verde', 'salario_base': 4500.0},
        {'nome': 'Assistente Financeiro VV', 'descricao': 'Assistência financeira - Vale Verde', 'salario_base': 3800.0},
        {'nome': 'Engenheiro Civil VV', 'descricao': 'Projetos e supervisão - Vale Verde', 'salario_base': 7200.0},
        {'nome': 'Mestre de Obras VV', 'descricao': 'Coordenação de obras - Vale Verde', 'salario_base': 4200.0},
        {'nome': 'Pedreiro VV', 'descricao': 'Execução de alvenaria - Vale Verde', 'salario_base': 2800.0},
        {'nome': 'Servente VV', 'descricao': 'Serviços gerais - Vale Verde', 'salario_base': 1800.0},
        {'nome': 'Vendedor VV', 'descricao': 'Vendas e atendimento - Vale Verde', 'salario_base': 3500.0},
        {'nome': 'Estagiário VV', 'descricao': 'Estágio curricular - Vale Verde', 'salario_base': 1200.0}
    ]
    
    for funcao_data in funcoes_data:
        funcao_existente = Funcao.query.filter_by(nome=funcao_data['nome']).first()
        if not funcao_existente:
            funcao = Funcao(**funcao_data)
            db.session.add(funcao)
            print(f"   ✅ Função {funcao.nome} criada")
        else:
            print(f"   ℹ️ Função {funcao_data['nome']} já existe")
    
    db.session.commit()
    print("   🔄 Funções salvas!\n")
    return {f.nome: f for f in Funcao.query.all()}

def criar_funcionarios_vale_verde(departamentos, funcoes, horarios, admin):
    """Cria os 10 funcionários da Vale Verde conforme especificação"""
    print("👥 Criando funcionários Vale Verde...")
    
    funcionarios_data = [
        {
            'codigo': 'VV001', 'nome': 'João Silva Santos',
            'cpf': '111.111.111-01', 'email': 'joao.silva@valeverde.com.br',
            'telefone': '(31) 99999-1111', 'data_admissao': date(2024, 1, 1),
            'salario': 8500.0, 'departamento': 'Administrativo VV',
            'funcao': 'Gerente Geral VV', 'horario': 'Comercial Vale Verde'
        },
        {
            'codigo': 'VV002', 'nome': 'Maria Oliveira Costa',
            'cpf': '222.222.222-02', 'email': 'maria.oliveira@valeverde.com.br',
            'telefone': '(31) 99999-2222', 'data_admissao': date(2024, 2, 15),
            'salario': 4500.0, 'departamento': 'Administrativo VV',
            'funcao': 'Analista RH VV', 'horario': 'Comercial Vale Verde'
        },
        {
            'codigo': 'VV003', 'nome': 'Carlos Pereira Lima',
            'cpf': '333.333.333-03', 'email': 'carlos.pereira@valeverde.com.br',
            'telefone': '(31) 99999-3333', 'data_admissao': date(2024, 3, 1),
            'salario': 3800.0, 'departamento': 'Administrativo VV',
            'funcao': 'Assistente Financeiro VV', 'horario': 'Comercial Vale Verde'
        },
        {
            'codigo': 'VV004', 'nome': 'Ana Paula Rodrigues',
            'cpf': '444.444.444-04', 'email': 'ana.rodrigues@valeverde.com.br',
            'telefone': '(31) 99999-4444', 'data_admissao': date(2024, 1, 10),
            'salario': 7200.0, 'departamento': 'Operacional VV',
            'funcao': 'Engenheiro Civil VV', 'horario': 'Comercial Vale Verde'
        },
        {
            'codigo': 'VV005', 'nome': 'Roberto Alves Souza',
            'cpf': '555.555.555-05', 'email': 'roberto.alves@valeverde.com.br',
            'telefone': '(31) 99999-5555', 'data_admissao': date(2024, 1, 20),
            'salario': 4200.0, 'departamento': 'Operacional VV',
            'funcao': 'Mestre de Obras VV', 'horario': 'Obra Vale Verde'
        },
        {
            'codigo': 'VV006', 'nome': 'José Carlos Ferreira',
            'cpf': '666.666.666-06', 'email': 'jose.ferreira@valeverde.com.br',
            'telefone': '(31) 99999-6666', 'data_admissao': date(2024, 2, 5),
            'salario': 2800.0, 'departamento': 'Operacional VV',
            'funcao': 'Pedreiro VV', 'horario': 'Obra Vale Verde'
        },
        {
            'codigo': 'VV007', 'nome': 'Antônio Silva Nunes',
            'cpf': '777.777.777-07', 'email': 'antonio.nunes@valeverde.com.br',
            'telefone': '(31) 99999-7777', 'data_admissao': date(2024, 2, 15),
            'salario': 1800.0, 'departamento': 'Operacional VV',
            'funcao': 'Servente VV', 'horario': 'Obra Vale Verde'
        },
        {
            'codigo': 'VV008', 'nome': 'Fernanda Costa Almeida',
            'cpf': '888.888.888-08', 'email': 'fernanda.almeida@valeverde.com.br',
            'telefone': '(31) 99999-8888', 'data_admissao': date(2024, 2, 1),
            'salario': 3500.0, 'departamento': 'Comercial VV',
            'funcao': 'Vendedor VV', 'horario': 'Comercial Vale Verde'
        },
        {
            'codigo': 'VV009', 'nome': 'Lucas Mendes Oliveira',
            'cpf': '999.999.999-09', 'email': 'lucas.mendes@valeverde.com.br',
            'telefone': '(31) 99999-9999', 'data_admissao': date(2024, 3, 1),
            'salario': 1200.0, 'departamento': 'Administrativo VV',
            'funcao': 'Estagiário VV', 'horario': 'Estagiário Vale Verde'
        },
        {
            'codigo': 'VV010', 'nome': 'Juliana Santos Lima',
            'cpf': '101.010.101-10', 'email': 'juliana.santos@valeverde.com.br',
            'telefone': '(31) 99999-0000', 'data_admissao': date(2024, 3, 15),
            'salario': 1200.0, 'departamento': 'Operacional VV',
            'funcao': 'Estagiário VV', 'horario': 'Estagiário Vale Verde'
        }
    ]
    
    funcionarios_criados = []
    
    for func_data in funcionarios_data:
        # Verificar se CPF já existe
        funcionario_existente = Funcionario.query.filter_by(cpf=func_data['cpf']).first()
        if funcionario_existente:
            print(f"   ℹ️ Funcionário {func_data['nome']} já existe")
            funcionarios_criados.append(funcionario_existente)
            continue
        
        # Criar usuário funcionário
        usuario_existente = Usuario.query.filter_by(username=func_data['codigo'].lower()).first()
        if not usuario_existente:
            usuario = Usuario(
                username=func_data['codigo'].lower(),
                email=func_data['email'],
                password_hash=generate_password_hash('123456'),
                nome=func_data['nome'],
                tipo_usuario=TipoUsuario.FUNCIONARIO,
                admin_id=admin.id,
                ativo=True
            )
            db.session.add(usuario)
            db.session.flush()
        
        # Criar funcionário
        funcionario = Funcionario(
            codigo=func_data['codigo'],
            nome=func_data['nome'],
            cpf=func_data['cpf'],
            email=func_data['email'],
            telefone=func_data['telefone'],
            data_admissao=func_data['data_admissao'],
            salario=func_data['salario'],
            departamento_id=departamentos[func_data['departamento']].id,
            funcao_id=funcoes[func_data['funcao']].id,
            horario_trabalho_id=horarios[func_data['horario']].id,
            ativo=True
        )
        
        db.session.add(funcionario)
        funcionarios_criados.append(funcionario)
        print(f"   ✅ {func_data['nome']} ({func_data['codigo']}) criado")
    
    db.session.commit()
    print("   🔄 Funcionários salvos!\n")
    return funcionarios_criados

def criar_obras_vale_verde():
    """Cria as 3 obras da Vale Verde"""
    print("🏗️ Criando obras Vale Verde...")
    
    obras_data = [
        {
            'nome': 'Residencial Jardim das Flores VV',
            'codigo': 'VV-RES-001',
            'endereco': 'Rua das Flores, 456 - Jardim Primavera - BH/MG',
            'data_inicio': date(2024, 1, 1),
            'data_previsao_fim': date(2024, 12, 31),
            'orcamento': 2500000.0,
            'area_total_m2': 5000.0,
            'status': 'Em andamento'
        },
        {
            'nome': 'Galpão Industrial Zona Norte VV',
            'codigo': 'VV-IND-002',
            'endereco': 'Av. Industrial, 789 - Zona Norte - Contagem/MG',
            'data_inicio': date(2024, 2, 15),
            'data_previsao_fim': date(2024, 8, 15),
            'orcamento': 800000.0,
            'area_total_m2': 2000.0,
            'status': 'Em andamento'
        },
        {
            'nome': 'Reforma Escritório Central VV',
            'codigo': 'VV-REF-003',
            'endereco': 'Rua das Obras, 123 - Centro - BH/MG',
            'data_inicio': date(2024, 3, 1),
            'data_previsao_fim': date(2024, 4, 30),
            'orcamento': 150000.0,
            'area_total_m2': 300.0,
            'status': 'Em andamento'
        }
    ]
    
    obras_criadas = []
    for obra_data in obras_data:
        obra_existente = Obra.query.filter_by(nome=obra_data['nome']).first()
        if not obra_existente:
            obra = Obra(**obra_data)
            db.session.add(obra)
            obras_criadas.append(obra)
            print(f"   ✅ Obra {obra.nome} criada")
        else:
            print(f"   ℹ️ Obra {obra_data['nome']} já existe")
            obras_criadas.append(obra_existente)
    
    db.session.commit()
    print("   🔄 Obras salvas!\n")
    return obras_criadas

def criar_veiculos_vale_verde():
    """Cria os 4 veículos da Vale Verde"""
    print("🚗 Criando veículos Vale Verde...")
    
    veiculos_data = [
        {
            'marca': 'Mercedes-Benz', 'modelo': 'Accelo 815 VV',
            'ano': 2020, 'placa': 'VV-1234', 'tipo': 'Caminhão',
            'status': 'Disponível', 'km_atual': 45000
        },
        {
            'marca': 'Fiat', 'modelo': 'Ducato VV',
            'ano': 2021, 'placa': 'VV-5678', 'tipo': 'Van',
            'status': 'Disponível', 'km_atual': 35000
        },
        {
            'marca': 'Volkswagen', 'modelo': 'Saveiro VV',
            'ano': 2022, 'placa': 'VV-9012', 'tipo': 'Picape',
            'status': 'Disponível', 'km_atual': 25000
        },
        {
            'marca': 'Honda', 'modelo': 'CG 160 VV',
            'ano': 2023, 'placa': 'VV-3456', 'tipo': 'Moto',
            'status': 'Manutenção', 'km_atual': 15000
        }
    ]
    
    veiculos_criados = []
    for veiculo_data in veiculos_data:
        veiculo_existente = Veiculo.query.filter_by(placa=veiculo_data['placa']).first()
        if not veiculo_existente:
            veiculo = Veiculo(**veiculo_data)
            db.session.add(veiculo)
            veiculos_criados.append(veiculo)
            print(f"   ✅ Veículo {veiculo.marca} {veiculo.modelo} criado")
        else:
            print(f"   ℹ️ Veículo {veiculo_data['placa']} já existe")
            veiculos_criados.append(veiculo_existente)
    
    db.session.commit()
    print("   🔄 Veículos salvos!\n")
    return veiculos_criados

def criar_restaurantes_vale_verde():
    """Cria os 3 restaurantes da Vale Verde"""
    print("🍽️ Criando restaurantes Vale Verde...")
    
    restaurantes_data = [
        {
            'nome': 'Restaurante do Zé VV',
            'endereco': 'Rua da Comida, 456 - Centro - BH/MG',
            'telefone': '(31) 3333-5555'
        },
        {
            'nome': 'Lanchonete da Obra VV',
            'endereco': 'Av. Industrial, 789 - Contagem/MG',
            'telefone': '(31) 3333-6666'
        },
        {
            'nome': 'Cantina Central VV',
            'endereco': 'Rua das Obras, 200 - Centro - BH/MG',
            'telefone': '(31) 3333-7777'
        }
    ]
    
    restaurantes_criados = []
    for rest_data in restaurantes_data:
        rest_existente = Restaurante.query.filter_by(nome=rest_data['nome']).first()
        if not rest_existente:
            restaurante = Restaurante(**rest_data)
            db.session.add(restaurante)
            restaurantes_criados.append(restaurante)
            print(f"   ✅ Restaurante {restaurante.nome} criado")
        else:
            print(f"   ℹ️ Restaurante {rest_data['nome']} já existe")
            restaurantes_criados.append(rest_existente)
    
    db.session.commit()
    print("   🔄 Restaurantes salvos!\n")
    return restaurantes_criados

def main():
    """Função principal"""
    print("🎯 CRIANDO CONSTRUTORA VALE VERDE COMPLETA")
    print("=" * 80)
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("🏢 Empresa: Construtora Vale Verde Ltda")
    print("📋 CNPJ: 12.345.678/0001-90")
    print("📍 Endereço: Rua das Obras, 123 - Centro - Belo Horizonte/MG")
    print("☎️ Telefone: (31) 3333-4444")
    print("✉️ Email: contato@valeverde.com.br")
    
    with app.app_context():
        try:
            # 1. Criar admin específico da Vale Verde
            admin_vv = criar_admin_vale_verde()
            
            # 2. Criar estrutura básica
            horarios = criar_horarios_vale_verde()
            departamentos = criar_departamentos_vale_verde()
            funcoes = criar_funcoes_vale_verde()
            
            # 3. Criar funcionários específicos
            funcionarios = criar_funcionarios_vale_verde(departamentos, funcoes, horarios, admin_vv)
            
            # 4. Criar obras, veículos e restaurantes específicos
            obras = criar_obras_vale_verde()
            veiculos = criar_veiculos_vale_verde()
            restaurantes = criar_restaurantes_vale_verde()
            
            print("=" * 80)
            print("🎉 CONSTRUTORA VALE VERDE CRIADA COM SUCESSO!")
            print(f"   👥 Funcionários criados: {len(funcionarios)}")
            print(f"   🏗️ Obras criadas: {len(obras)}")
            print(f"   🚗 Veículos criados: {len(veiculos)}")
            print(f"   🍽️ Restaurantes criados: {len(restaurantes)}")
            print(f"   ⏰ Horários de trabalho: {len(horarios)}")
            print(f"   🏢 Departamentos: {len(departamentos)}")
            print(f"   👷 Funções: {len(funcoes)}")
            
            print(f"\n🔐 CREDENCIAIS DE ACESSO CONSTRUTORA VALE VERDE:")
            print(f"   🔑 Super Admin: axiom / cassio123")
            print(f"   🔑 Admin Geral: admin / admin123")
            print(f"   🔑 Admin Vale Verde: valeverde / admin123")
            print(f"   🔑 Funcionários VV: [código] / 123456")
            
            print(f"\n👥 FUNCIONÁRIOS VALE VERDE CRIADOS:")
            for func in funcionarios[:5]:  # Mostrar apenas os primeiros 5
                print(f"   • {func.codigo} - {func.nome}")
                print(f"     Login: {func.codigo.lower()} / 123456")
            
            print(f"\n🏗️ OBRAS VALE VERDE:")
            for obra in obras:
                print(f"   • {obra.nome}")
                print(f"     Valor: R$ {obra.valor_contrato:,.2f}")
            
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Erro durante a criação: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    main()