#!/usr/bin/env python3
"""
Populador de Dados Completo - Construtora Vale Verde
Sistema SIGE v8.0 - Dados realistas para teste e validação
"""

from app import app, db
from models import *
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time, timedelta
import random

# Dados específicos do arquivo anexo

def limpar_dados_existentes():
    """Limpa dados existentes para recriação"""
    print("🗑️ Verificando dados existentes...")
    
    try:
        # Primeiro, remove constraints FK temporariamente para Obra
        from sqlalchemy import text
        db.session.execute(text("UPDATE obra SET responsavel_id = NULL WHERE responsavel_id IS NOT NULL;"))
        db.session.commit()
        
        # Ordem de limpeza respeitando FK constraints
        models_to_clear = [
            RegistroAlimentacao, OutroCusto, CustoVeiculo, CustoObra, 
            RegistroPonto, Ocorrencia, RDO, Funcionario, 
            Usuario, HorarioTrabalho, Funcao, Departamento, 
            Obra, Veiculo, Restaurante
        ]
        
        for model in models_to_clear:
            try:
                count = db.session.query(model).count()
                if count > 0:
                    db.session.query(model).delete()
                    print(f"   ✅ {model.__name__} limpo ({count} registros)")
                else:
                    print(f"   ℹ️ {model.__name__} já vazio")
            except Exception as e:
                print(f"   ⚠️ Erro ao limpar {model.__name__}: {e}")
                db.session.rollback()
        
        db.session.commit()
        print("   🔄 Dados limpos com sucesso!\n")
        
    except Exception as e:
        print(f"   ❌ Erro geral na limpeza: {e}")
        db.session.rollback()

def criar_horarios_trabalho():
    """Cria os horários de trabalho"""
    print("⏰ Criando horários de trabalho...")
    
    horarios = [
        {
            'nome': 'Comercial',
            'entrada': time(7, 12),
            'saida_almoco': time(12, 0),
            'retorno_almoco': time(13, 0),
            'saida': time(17, 0),
            'dias_semana': '1,2,3,4,5',  # Seg-Sex
            'horas_diarias': 8.8,
            'valor_hora': 15.0
        },
        {
            'nome': 'Estagiario',
            'entrada': time(7, 12),
            'saida_almoco': time(12, 12),
            'retorno_almoco': time(12, 12),
            'saida': time(12, 12),
            'dias_semana': '1,2,3,4,5',  # Seg-Sex
            'horas_diarias': 5.0,
            'valor_hora': 8.0
        },
        {
            'nome': 'Obra',
            'entrada': time(7, 0),
            'saida_almoco': time(12, 0),
            'retorno_almoco': time(13, 0),
            'saida': time(17, 0),
            'dias_semana': '1,2,3,4,5,6',  # Seg-Sáb
            'horas_diarias': 9.0,
            'valor_hora': 18.0
        }
    ]
    
    for horario_data in horarios:
        horario_existente = HorarioTrabalho.query.filter_by(nome=horario_data['nome']).first()
        if not horario_existente:
            horario = HorarioTrabalho(**horario_data)
            db.session.add(horario)
            print(f"   ✅ Horário {horario.nome} criado")
        else:
            print(f"   ℹ️ Horário {horario_data['nome']} já existe")
    
    db.session.commit()
    print("   🔄 Horários salvos!\n")
    return {h.nome: h for h in HorarioTrabalho.query.all()}

def criar_departamentos():
    """Cria os departamentos"""
    print("🏢 Criando departamentos...")
    
    departamentos = [
        {'nome': 'Administrativo', 'descricao': 'Gerência, RH e Financeiro'},
        {'nome': 'Operacional', 'descricao': 'Engenharia, Obras e Manutenção'},
        {'nome': 'Comercial', 'descricao': 'Vendas e Atendimento'}
    ]
    
    for dept_data in departamentos:
        dept = Departamento(**dept_data)
        db.session.add(dept)
        print(f"   ✅ Departamento {dept.nome} criado")
    
    db.session.commit()
    print("   🔄 Departamentos salvos!\n")
    return {d.nome: d for d in Departamento.query.all()}

def criar_funcoes():
    """Cria as funções"""
    print("👷 Criando funções...")
    
    funcoes = [
        {'nome': 'Gerente Geral', 'descricao': 'Gerenciamento geral da empresa', 'salario_base': 8500.0},
        {'nome': 'Analista RH', 'descricao': 'Recursos humanos', 'salario_base': 4500.0},
        {'nome': 'Assistente Financeiro', 'descricao': 'Assistência financeira', 'salario_base': 3800.0},
        {'nome': 'Engenheiro Civil', 'descricao': 'Projetos e supervisão técnica', 'salario_base': 7200.0},
        {'nome': 'Mestre de Obras', 'descricao': 'Coordenação de obras', 'salario_base': 4200.0},
        {'nome': 'Pedreiro', 'descricao': 'Execução de alvenaria', 'salario_base': 2800.0},
        {'nome': 'Servente', 'descricao': 'Serviços gerais de obra', 'salario_base': 1800.0},
        {'nome': 'Vendedor', 'descricao': 'Vendas e atendimento', 'salario_base': 3500.0},
        {'nome': 'Estagiario', 'descricao': 'Estágio curricular', 'salario_base': 1200.0}
    ]
    
    for funcao_data in funcoes:
        funcao = Funcao(**funcao_data)
        db.session.add(funcao)
        print(f"   ✅ Função {funcao.nome} criada")
    
    db.session.commit()
    print("   🔄 Funções salvas!\n")
    return {f.nome: f for f in Funcao.query.all()}

def criar_usuarios_admin():
    """Cria usuários administrativos"""
    print("👤 Criando usuários administrativos...")
    
    # Verificar se já existem
    super_admin = Usuario.query.filter_by(username='axiom').first()
    if not super_admin:
        super_admin = Usuario(
            username='axiom',
            email='axiom@valeverde.com.br',
            password_hash=generate_password_hash('cassio123'),
            nome='Axiom Super Admin',
            tipo_usuario=TipoUsuario.SUPER_ADMIN,
            ativo=True
        )
        db.session.add(super_admin)
        print("   ✅ Super Admin 'axiom' criado")
    else:
        print("   ℹ️ Super Admin 'axiom' já existe")
    
    admin = Usuario.query.filter_by(username='admin').first()
    if not admin:
        admin = Usuario(
            username='admin',
            email='admin@valeverde.com.br',
            password_hash=generate_password_hash('admin123'),
            nome='Administrador Vale Verde',
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True
        )
        db.session.add(admin)
        print("   ✅ Admin 'admin' criado")
    else:
        print("   ℹ️ Admin 'admin' já existe")
    
    db.session.commit()
    return admin

def criar_funcionarios(departamentos, funcoes, horarios, admin):
    """Cria os funcionários"""
    print("👥 Criando funcionários...")
    
    funcionarios_data = [
        {
            'codigo': 'F0001', 'nome': 'João Silva Santos',
            'cpf': '123.456.789-01', 'email': 'joao.silva@valeverde.com.br',
            'telefone': '(31) 99999-1111', 'data_admissao': date(2024, 1, 1),
            'salario': 8500.0, 'departamento': 'Administrativo',
            'funcao': 'Gerente Geral', 'horario': 'Comercial'
        },
        {
            'codigo': 'F0002', 'nome': 'Maria Oliveira Costa',
            'cpf': '234.567.890-12', 'email': 'maria.oliveira@valeverde.com.br',
            'telefone': '(31) 99999-2222', 'data_admissao': date(2024, 2, 15),
            'salario': 4500.0, 'departamento': 'Administrativo',
            'funcao': 'Analista RH', 'horario': 'Comercial'
        },
        {
            'codigo': 'F0003', 'nome': 'Carlos Pereira Lima',
            'cpf': '345.678.901-23', 'email': 'carlos.pereira@valeverde.com.br',
            'telefone': '(31) 99999-3333', 'data_admissao': date(2024, 3, 1),
            'salario': 3800.0, 'departamento': 'Administrativo',
            'funcao': 'Assistente Financeiro', 'horario': 'Comercial'
        },
        {
            'codigo': 'F0004', 'nome': 'Ana Paula Rodrigues',
            'cpf': '456.789.012-34', 'email': 'ana.rodrigues@valeverde.com.br',
            'telefone': '(31) 99999-4444', 'data_admissao': date(2024, 1, 10),
            'salario': 7200.0, 'departamento': 'Operacional',
            'funcao': 'Engenheiro Civil', 'horario': 'Comercial'
        },
        {
            'codigo': 'F0005', 'nome': 'Roberto Alves Souza',
            'cpf': '567.890.123-45', 'email': 'roberto.alves@valeverde.com.br',
            'telefone': '(31) 99999-5555', 'data_admissao': date(2024, 1, 20),
            'salario': 4200.0, 'departamento': 'Operacional',
            'funcao': 'Mestre de Obras', 'horario': 'Obra'
        },
        {
            'codigo': 'F0006', 'nome': 'José Carlos Ferreira',
            'cpf': '678.901.234-56', 'email': 'jose.ferreira@valeverde.com.br',
            'telefone': '(31) 99999-6666', 'data_admissao': date(2024, 2, 5),
            'salario': 2800.0, 'departamento': 'Operacional',
            'funcao': 'Pedreiro', 'horario': 'Obra'
        },
        {
            'codigo': 'F0007', 'nome': 'Antônio Silva Nunes',
            'cpf': '789.012.345-67', 'email': 'antonio.nunes@valeverde.com.br',
            'telefone': '(31) 99999-7777', 'data_admissao': date(2024, 2, 15),
            'salario': 1800.0, 'departamento': 'Operacional',
            'funcao': 'Servente', 'horario': 'Obra'
        },
        {
            'codigo': 'F0008', 'nome': 'Fernanda Costa Almeida',
            'cpf': '890.123.456-78', 'email': 'fernanda.almeida@valeverde.com.br',
            'telefone': '(31) 99999-8888', 'data_admissao': date(2024, 2, 1),
            'salario': 3500.0, 'departamento': 'Comercial',
            'funcao': 'Vendedor', 'horario': 'Comercial'
        },
        {
            'codigo': 'F0009', 'nome': 'Lucas Mendes Oliveira',
            'cpf': '901.234.567-89', 'email': 'lucas.mendes@valeverde.com.br',
            'telefone': '(31) 99999-9999', 'data_admissao': date(2024, 3, 1),
            'salario': 1200.0, 'departamento': 'Administrativo',
            'funcao': 'Estagiario', 'horario': 'Estagiario'
        },
        {
            'codigo': 'F0010', 'nome': 'Juliana Santos Lima',
            'cpf': '012.345.678-90', 'email': 'juliana.santos@valeverde.com.br',
            'telefone': '(31) 99999-0000', 'data_admissao': date(2024, 3, 15),
            'salario': 1200.0, 'departamento': 'Operacional',
            'funcao': 'Estagiario', 'horario': 'Estagiario'
        }
    ]
    
    funcionarios_criados = []
    
    for func_data in funcionarios_data:
        # Criar usuário funcionário
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
        db.session.flush()  # Para obter o ID
        
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

def criar_obras():
    """Cria as obras"""
    print("🏗️ Criando obras...")
    
    obras = [
        {
            'nome': 'Residencial Jardim das Flores',
            'descricao': 'Condomínio residencial com 50 apartamentos',
            'data_inicio': date(2024, 1, 1),
            'data_fim_prevista': date(2024, 12, 31),
            'status': 'Em andamento',
            'cliente': 'Incorporadora Belo Horizonte Ltda',
            'valor_contrato': 2500000.0
        },
        {
            'nome': 'Galpão Industrial Zona Norte',
            'descricao': 'Galpão industrial de 2.000m²',
            'data_inicio': date(2024, 2, 15),
            'data_fim_prevista': date(2024, 8, 15),
            'status': 'Em andamento',
            'cliente': 'Indústria Metalúrgica Norte Ltda',
            'valor_contrato': 800000.0
        },
        {
            'nome': 'Reforma Escritório Central',
            'descricao': 'Reforma completa do escritório administrativo',
            'data_inicio': date(2024, 3, 1),
            'data_fim_prevista': date(2024, 4, 30),
            'status': 'Em andamento',
            'cliente': 'Construtora Vale Verde (própria)',
            'valor_contrato': 150000.0
        }
    ]
    
    obras_criadas = []
    for obra_data in obras:
        obra = Obra(**obra_data)
        db.session.add(obra)
        obras_criadas.append(obra)
        print(f"   ✅ Obra {obra.nome} criada")
    
    db.session.commit()
    print("   🔄 Obras salvas!\n")
    return obras_criadas

def criar_veiculos():
    """Cria os veículos"""
    print("🚗 Criando veículos...")
    
    veiculos = [
        {
            'marca': 'Mercedes-Benz', 'modelo': 'Accelo 815',
            'ano': 2020, 'placa': 'ABC-1234', 'cor': 'Branco',
            'combustivel': 'Diesel', 'status': 'Ativo'
        },
        {
            'marca': 'Fiat', 'modelo': 'Ducato',
            'ano': 2021, 'placa': 'DEF-5678', 'cor': 'Branco',
            'combustivel': 'Diesel', 'status': 'Ativo'
        },
        {
            'marca': 'Volkswagen', 'modelo': 'Saveiro',
            'ano': 2022, 'placa': 'GHI-9012', 'cor': 'Branco',
            'combustivel': 'Flex', 'status': 'Ativo'
        },
        {
            'marca': 'Honda', 'modelo': 'CG 160',
            'ano': 2023, 'placa': 'JKL-3456', 'cor': 'Vermelha',
            'combustivel': 'Gasolina', 'status': 'Manutenção'
        }
    ]
    
    veiculos_criados = []
    for veiculo_data in veiculos:
        veiculo = Veiculo(**veiculo_data)
        db.session.add(veiculo)
        veiculos_criados.append(veiculo)
        print(f"   ✅ Veículo {veiculo.marca} {veiculo.modelo} criado")
    
    db.session.commit()
    print("   🔄 Veículos salvos!\n")
    return veiculos_criados

def criar_restaurantes():
    """Cria os restaurantes"""
    print("🍽️ Criando restaurantes...")
    
    restaurantes = [
        {
            'nome': 'Restaurante do Zé',
            'endereco': 'Rua da Comida, 456 - Centro - BH/MG',
            'telefone': '(31) 3333-5555',
            'especialidade': 'Comida caseira'
        },
        {
            'nome': 'Lanchonete da Obra',
            'endereco': 'Av. Industrial, 789 - Contagem/MG',
            'telefone': '(31) 3333-6666',
            'especialidade': 'Lanches e marmitas'
        },
        {
            'nome': 'Cantina Central',
            'endereco': 'Rua das Obras, 200 - Centro - BH/MG',
            'telefone': '(31) 3333-7777',
            'especialidade': 'Self-service'
        }
    ]
    
    restaurantes_criados = []
    for rest_data in restaurantes:
        restaurante = Restaurante(**rest_data)
        db.session.add(restaurante)
        restaurantes_criados.append(restaurante)
        print(f"   ✅ Restaurante {restaurante.nome} criado")
    
    db.session.commit()
    print("   🔄 Restaurantes salvos!\n")
    return restaurantes_criados

def main():
    """Função principal"""
    print("🎯 POPULANDO SISTEMA SIGE - CONSTRUTORA VALE VERDE")
    print("=" * 80)
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("🏢 Empresa: Construtora Vale Verde Ltda")
    
    with app.app_context():
        try:
            # 1. Limpar dados existentes
            limpar_dados_existentes()
            
            # 2. Criar estrutura básica
            horarios = criar_horarios_trabalho()
            departamentos = criar_departamentos()
            funcoes = criar_funcoes()
            
            # 3. Criar usuários admin
            admin = criar_usuarios_admin()
            
            # 4. Criar funcionários
            funcionarios = criar_funcionarios(departamentos, funcoes, horarios, admin)
            
            # 5. Criar obras, veículos e restaurantes
            obras = criar_obras()
            veiculos = criar_veiculos()
            restaurantes = criar_restaurantes()
            
            print("=" * 80)
            print("🎉 POPULAÇÃO COMPLETA DO SISTEMA!")
            print(f"   👥 Funcionários criados: {len(funcionarios)}")
            print(f"   🏗️ Obras criadas: {len(obras)}")
            print(f"   🚗 Veículos criados: {len(veiculos)}")
            print(f"   🍽️ Restaurantes criados: {len(restaurantes)}")
            print(f"   ⏰ Horários de trabalho: {len(horarios)}")
            print(f"   🏢 Departamentos: {len(departamentos)}")
            print(f"   👷 Funções: {len(funcoes)}")
            
            print(f"\n💡 CREDENCIAIS DE ACESSO:")
            print(f"   🔐 Super Admin: axiom / cassio123")
            print(f"   🔐 Admin: admin / admin123")
            print(f"   🔐 Funcionários: [codigo] / 123456 (ex: f0001/123456)")
            
            print(f"\n🚀 PRÓXIMOS PASSOS:")
            print(f"   📊 Popular registros de ponto (julho/2024)")
            print(f"   🍽️ Criar lançamentos de alimentação")
            print(f"   🚗 Registrar uso de veículos")
            print(f"   📋 Criar RDOs das obras")
            print(f"   💰 Adicionar custos diversos")
            
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Erro durante a população: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    main()