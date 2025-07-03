#!/usr/bin/env python3
"""
Script para popular o banco de dados do SIGE com dados de teste
"""

from app import app, db
from models import (
    Usuario, Departamento, Funcao, Funcionario, Obra, Veiculo, 
    Fornecedor, Cliente, Material, Servico, RegistroPonto, 
    RegistroAlimentacao, CustoObra
)
from werkzeug.security import generate_password_hash
from datetime import date, datetime, time, timedelta
import random

def create_sample_data():
    with app.app_context():
        # Limpar dados existentes (exceto usuário admin)
        RegistroAlimentacao.query.delete()
        RegistroPonto.query.delete()
        CustoObra.query.delete()
        Funcionario.query.delete()
        Obra.query.delete()
        Veiculo.query.delete()
        Fornecedor.query.delete()
        Cliente.query.delete()
        Material.query.delete()
        Servico.query.delete()
        Funcao.query.delete()
        Departamento.query.delete()
        
        # Criar departamentos
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
        
        # Criar funções
        funcoes = [
            Funcao(nome='Diretor Geral', descricao='Direção executiva da empresa', salario_base=15000.00),
            Funcao(nome='Engenheiro Civil', descricao='Projetos e supervisão de obras', salario_base=8500.00),
            Funcao(nome='Mestre de Obras', descricao='Coordenação de equipes de construção', salario_base=4500.00),
            Funcao(nome='Pedreiro', descricao='Execução de serviços de alvenaria', salario_base=2800.00),
            Funcao(nome='Eletricista', descricao='Instalações elétricas', salario_base=3200.00),
            Funcao(nome='Encanador', descricao='Instalações hidráulicas', salario_base=3000.00),
            Funcao(nome='Motorista', descricao='Condução de veículos da empresa', salario_base=2500.00),
            Funcao(nome='Auxiliar Administrativo', descricao='Apoio administrativo', salario_base=2200.00),
            Funcao(nome='Contador', descricao='Gestão contábil e fiscal', salario_base=6000.00),
            Funcao(nome='Técnico em Segurança', descricao='Segurança do trabalho', salario_base=4000.00)
        ]
        
        for funcao in funcoes:
            db.session.add(funcao)
        db.session.commit()
        
        # Criar funcionários
        funcionarios_data = [
            ('João Silva Santos', '123.456.789-01', 'joao.silva@estruturasdovale.com.br', 1, 1, 15000.00),
            ('Maria Oliveira Costa', '234.567.890-12', 'maria.oliveira@estruturasdovale.com.br', 2, 2, 8500.00),
            ('Carlos Pereira Lima', '345.678.901-23', 'carlos.pereira@estruturasdovale.com.br', 3, 3, 4500.00),
            ('Ana Santos Rodrigues', '456.789.012-34', 'ana.santos@estruturasdovale.com.br', 2, 2, 8500.00),
            ('Pedro Almeida Souza', '567.890.123-45', 'pedro.almeida@estruturasdovale.com.br', 3, 4, 2800.00),
            ('Luisa Ferreira Gomes', '678.901.234-56', 'luisa.ferreira@estruturasdovale.com.br', 1, 8, 2200.00),
            ('Roberto Costa Silva', '789.012.345-67', 'roberto.costa@estruturasdovale.com.br', 3, 5, 3200.00),
            ('Fernanda Lima Santos', '890.123.456-78', 'fernanda.lima@estruturasdovale.com.br', 5, 8, 2200.00),
            ('José Rodrigues Alves', '901.234.567-89', 'jose.rodrigues@estruturasdovale.com.br', 4, 7, 2500.00),
            ('Carmen Souza Pereira', '012.345.678-90', 'carmen.souza@estruturasdovale.com.br', 1, 9, 6000.00),
            ('Marcos Oliveira Silva', '123.987.654-32', 'marcos.oliveira@estruturasdovale.com.br', 3, 6, 3000.00),
            ('Julia Santos Costa', '234.876.543-21', 'julia.santos@estruturasdovale.com.br', 6, 10, 4000.00),
            ('Antonio Lima Ferreira', '345.765.432-10', 'antonio.lima@estruturasdovale.com.br', 3, 4, 2800.00),
            ('Beatriz Alves Rodrigues', '456.654.321-09', 'beatriz.alves@estruturasdovale.com.br', 2, 2, 8500.00),
            ('Ricardo Gomes Santos', '567.543.210-98', 'ricardo.gomes@estruturasdovale.com.br', 4, 7, 2500.00)
        ]
        
        for i, (nome, cpf, email, dept_id, func_id, salario) in enumerate(funcionarios_data):
            funcionario = Funcionario(
                nome=nome,
                cpf=cpf,
                rg=f'MG-{12345678 + i}',
                data_nascimento=date(1980 + i % 20, (i % 12) + 1, (i % 28) + 1),
                endereco=f'Rua das Flores, {100 + i * 10} - Belo Horizonte, MG',
                telefone=f'(31) 9{8000 + i}-{1234 + i}',
                email=email,
                data_admissao=date(2020 + i % 4, (i % 12) + 1, (i % 28) + 1),
                salario=salario,
                departamento_id=dept_id,
                funcao_id=func_id,
                ativo=True
            )
            db.session.add(funcionario)
        
        db.session.commit()
        
        # Criar obras
        obras_data = [
            ('Residencial Jardim das Palmeiras', 'Av. das Palmeiras, 1500 - Nova Lima, MG', 
             date(2024, 1, 15), date(2024, 12, 30), 850000.00, 'Em andamento', 2),
            ('Edifício Comercial Centro', 'Rua XV de Novembro, 234 - Centro, Belo Horizonte, MG',
             date(2024, 3, 1), date(2025, 2, 28), 1200000.00, 'Em andamento', 4),
            ('Casa Térrea Zona Sul', 'Rua dos Ipês, 45 - Zona Sul, Belo Horizonte, MG',
             date(2023, 10, 10), date(2024, 4, 15), 320000.00, 'Concluída', 2),
            ('Galpão Industrial Norte', 'Av. Industrial, 890 - Região Norte, Contagem, MG',
             date(2024, 6, 1), date(2024, 11, 30), 650000.00, 'Em andamento', 14),
            ('Reforma Shopping Popular', 'Rua do Comércio, 123 - Centro, Belo Horizonte, MG',
             date(2024, 8, 15), date(2024, 12, 20), 450000.00, 'Em andamento', 4)
        ]
        
        for nome, endereco, inicio, fim, orcamento, status, resp_id in obras_data:
            obra = Obra(
                nome=nome,
                endereco=endereco,
                data_inicio=inicio,
                data_previsao_fim=fim,
                orcamento=orcamento,
                status=status,
                responsavel_id=resp_id
            )
            db.session.add(obra)
        
        db.session.commit()
        
        # Criar veículos
        veiculos_data = [
            ('ABC-1234', 'Ford', 'F-4000', 2018, 'Caminhão', 'Disponível', 85000),
            ('DEF-5678', 'Volkswagen', 'Saveiro', 2020, 'Caminhão', 'Em uso', 45000),
            ('GHI-9012', 'Fiat', 'Strada', 2019, 'Caminhão', 'Disponível', 32000),
            ('JKL-3456', 'Toyota', 'Hilux', 2021, 'Caminhão', 'Em uso', 28000),
            ('MNO-7890', 'Chevrolet', 'S10', 2020, 'Caminhão', 'Manutenção', 55000),
            ('PQR-2468', 'Honda', 'CG 160', 2022, 'Moto', 'Disponível', 8500),
            ('STU-1357', 'Yamaha', 'Factor 125', 2021, 'Moto', 'Disponível', 12000),
            ('VWX-9753', 'Fiat', 'Uno', 2019, 'Carro', 'Em uso', 45000)
        ]
        
        for placa, marca, modelo, ano, tipo, status, km in veiculos_data:
            veiculo = Veiculo(
                placa=placa,
                marca=marca,
                modelo=modelo,
                ano=ano,
                tipo=tipo,
                status=status,
                km_atual=km,
                data_ultima_manutencao=date(2024, random.randint(1, 6), random.randint(1, 28)),
                data_proxima_manutencao=date(2024, random.randint(7, 12), random.randint(1, 28))
            )
            db.session.add(veiculo)
        
        db.session.commit()
        
        # Criar fornecedores
        fornecedores_data = [
            ('Materiais de Construção Silva Ltda', '12.345.678/0001-90', 'Materiais de construção'),
            ('Transportadora Rápida Express', '23.456.789/0001-01', 'Serviços de transporte'),
            ('Ferragens e Ferramentas Unidos', '34.567.890/0001-12', 'Ferramentas e equipamentos'),
            ('Construtora Parceira S.A.', '45.678.901/0001-23', 'Serviços especializados'),
            ('Combustíveis e Lubrificantes Ltda', '56.789.012/0001-34', 'Combustíveis e lubrificantes')
        ]
        
        for i, (nome, cnpj, tipo) in enumerate(fornecedores_data):
            fornecedor = Fornecedor(
                nome=nome,
                cnpj_cpf=cnpj,
                endereco=f'Rua dos Fornecedores, {200 + i * 50} - Belo Horizonte, MG',
                telefone=f'(31) 3{200 + i}-{5000 + i}',
                email=f'contato{i+1}@fornecedor.com.br',
                tipo_produto_servico=tipo
            )
            db.session.add(fornecedor)
        
        db.session.commit()
        
        # Criar clientes
        clientes_data = [
            ('Construtora Horizonte Ltda', '11.222.333/0001-44'),
            ('Incorporadora Vista Bela S.A.', '22.333.444/0001-55'),
            ('João Carlos Moreira', '123.456.789-10'),
            ('Empresa Industrial Norte Ltda', '33.444.555/0001-66'),
            ('Maria Fernanda Alves', '234.567.890-21')
        ]
        
        for i, (nome, doc) in enumerate(clientes_data):
            cliente = Cliente(
                nome=nome,
                cnpj_cpf=doc,
                endereco=f'Av. dos Clientes, {300 + i * 100} - Belo Horizonte, MG',
                telefone=f'(31) 3{300 + i}-{6000 + i}',
                email=f'cliente{i+1}@email.com.br'
            )
            db.session.add(cliente)
        
        db.session.commit()
        
        # Criar materiais
        materiais_data = [
            ('Cimento CP-II 50kg', 'Cimento Portland composto', 'sc', 32.50, 50, 120),
            ('Tijolo Cerâmico 6 furos', 'Tijolo cerâmico comum', 'un', 0.85, 1000, 2500),
            ('Areia Média', 'Areia para construção civil', 'm³', 45.00, 10, 25),
            ('Brita 1', 'Brita graduada número 1', 'm³', 55.00, 8, 18),
            ('Ferro 10mm CA-50', 'Ferro para construção', 'kg', 8.50, 500, 1200),
            ('Tinta Acrílica Branca', 'Tinta acrílica premium', 'lt', 85.00, 20, 45)
        ]
        
        for nome, desc, unidade, preco, min_estoque, estoque in materiais_data:
            material = Material(
                nome=nome,
                descricao=desc,
                unidade_medida=unidade,
                preco_unitario=preco,
                estoque_minimo=min_estoque,
                estoque_atual=estoque
            )
            db.session.add(material)
        
        db.session.commit()
        
        # Criar serviços
        servicos_data = [
            ('Alvenaria de Vedação', 'Execução de alvenaria de vedação', 25.00),
            ('Instalação Elétrica', 'Serviços de instalação elétrica', 45.00),
            ('Instalação Hidráulica', 'Serviços de instalação hidráulica', 40.00),
            ('Pintura Interna', 'Serviços de pintura interna', 18.00),
            ('Revestimento Cerâmico', 'Aplicação de revestimento cerâmico', 35.00),
            ('Carpintaria', 'Serviços de carpintaria', 55.00)
        ]
        
        for nome, desc, preco in servicos_data:
            servico = Servico(
                nome=nome,
                descricao=desc,
                preco_unitario=preco
            )
            db.session.add(servico)
        
        db.session.commit()
        
        # Criar registros de ponto (últimos 30 dias)
        hoje = date.today()
        funcionarios = Funcionario.query.all()
        obras = Obra.query.filter_by(status='Em andamento').all()
        
        for dias_atras in range(30, 0, -1):
            data_ponto = hoje - timedelta(days=dias_atras)
            
            # Pular fins de semana
            if data_ponto.weekday() >= 5:
                continue
                
            for funcionario in funcionarios[:10]:  # Apenas primeiros 10 funcionários
                if random.random() < 0.9:  # 90% de presença
                    hora_entrada = time(8, random.randint(0, 30))
                    hora_almoco_saida = time(12, 0)
                    hora_almoco_retorno = time(13, 0)
                    hora_saida = time(17, random.randint(0, 30))
                    
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=random.choice(obras).id if obras and random.random() < 0.7 else None,
                        data=data_ponto,
                        hora_entrada=hora_entrada,
                        hora_saida=hora_saida,
                        hora_almoco_saida=hora_almoco_saida,
                        hora_almoco_retorno=hora_almoco_retorno,
                        horas_trabalhadas=8.0 + random.uniform(-0.5, 1.0),
                        horas_extras=random.uniform(0, 2) if random.random() < 0.3 else 0,
                        observacoes='Registro normal' if random.random() < 0.8 else 'Hora extra autorizada'
                    )
                    db.session.add(registro)
        
        db.session.commit()
        
        # Criar registros de alimentação
        tipos_alimentacao = ['cafe', 'almoco', 'jantar', 'lanche']
        
        for dias_atras in range(15, 0, -1):
            data_alimentacao = hoje - timedelta(days=dias_atras)
            
            if data_alimentacao.weekday() >= 5:
                continue
                
            for funcionario in funcionarios[:8]:
                if random.random() < 0.8:  # 80% dos funcionários usam alimentação
                    tipo = random.choice(tipos_alimentacao)
                    valor = {
                        'cafe': random.uniform(8, 15),
                        'almoco': random.uniform(18, 35),
                        'jantar': random.uniform(20, 40),
                        'lanche': random.uniform(5, 12)
                    }[tipo]
                    
                    registro = RegistroAlimentacao(
                        funcionario_id=funcionario.id,
                        obra_id=random.choice(obras).id if obras and random.random() < 0.6 else None,
                        data=data_alimentacao,
                        tipo=tipo,
                        valor=valor,
                        observacoes=f'Alimentação - {tipo.title()}'
                    )
                    db.session.add(registro)
        
        db.session.commit()
        
        # Criar custos de obras
        tipos_custo = ['mao_obra', 'material', 'servico', 'veiculo', 'alimentacao']
        descricoes = {
            'mao_obra': ['Pagamento de funcionários', 'Horas extras', 'Adicional noturno'],
            'material': ['Compra de cimento', 'Aquisição de tijolos', 'Compra de ferro', 'Areia e brita'],
            'servico': ['Serviços de terceiros', 'Consultoria técnica', 'Aluguel de equipamentos'],
            'veiculo': ['Combustível', 'Manutenção preventiva', 'Seguro veicular'],
            'alimentacao': ['Vale alimentação', 'Refeições no local', 'Lanches da equipe']
        }
        
        for obra in obras:
            if obra.status == 'Em andamento':
                # Criar custos dos últimos 3 meses
                for dias_atras in range(90, 0, -5):
                    data_custo = hoje - timedelta(days=dias_atras)
                    
                    if random.random() < 0.4:  # 40% chance de ter custo neste dia
                        tipo = random.choice(tipos_custo)
                        descricao = random.choice(descricoes[tipo])
                        valor = random.uniform(500, 15000)
                        
                        custo = CustoObra(
                            obra_id=obra.id,
                            tipo=tipo,
                            descricao=descricao,
                            valor=valor,
                            data=data_custo
                        )
                        db.session.add(custo)
        
        db.session.commit()
        
        print("✅ Dados de teste criados com sucesso!")
        print(f"📊 Resumo dos dados criados:")
        print(f"   • {Departamento.query.count()} departamentos")
        print(f"   • {Funcao.query.count()} funções")
        print(f"   • {Funcionario.query.count()} funcionários")
        print(f"   • {Obra.query.count()} obras")
        print(f"   • {Veiculo.query.count()} veículos")
        print(f"   • {Fornecedor.query.count()} fornecedores")
        print(f"   • {Cliente.query.count()} clientes")
        print(f"   • {Material.query.count()} materiais")
        print(f"   • {Servico.query.count()} serviços")
        print(f"   • {RegistroPonto.query.count()} registros de ponto")
        print(f"   • {RegistroAlimentacao.query.count()} registros de alimentação")
        print(f"   • {CustoObra.query.count()} custos de obras")

if __name__ == '__main__':
    create_sample_data()