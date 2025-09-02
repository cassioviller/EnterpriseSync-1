#!/usr/bin/env python3
"""
Script de Teste Completo para SIGE v8.0
Cria 3 funcionários, 3 serviços com subatividades, uma obra,
e um mês completo de RDOs, pontos, alimentação e transporte
para validar os cálculos de custos.
"""

import sys
sys.path.append('.')
from models import *
from datetime import datetime, date, timedelta
import random

# Conectar ao banco
from app import app, db

def gerar_codigo_funcionario():
    """Gera código único para funcionário"""
    # Buscar o último código existente
    funcionarios = Funcionario.query.filter(Funcionario.codigo.like('F%')).order_by(Funcionario.codigo.desc()).all()
    
    if funcionarios:
        # Extrair números dos códigos existentes
        numeros = []
        for f in funcionarios:
            if f.codigo and f.codigo.startswith('F') and len(f.codigo) > 1:
                try:
                    numeros.append(int(f.codigo[1:]))
                except ValueError:
                    continue
        
        if numeros:
            num = max(numeros) + 1
        else:
            num = 1
    else:
        num = 1
    
    # Verificar se o código já existe e incrementar se necessário
    while True:
        codigo = f"F{num:04d}"
        existente = Funcionario.query.filter_by(codigo=codigo).first()
        if not existente:
            return codigo
        num += 1

def criar_funcionarios():
    """Criar 3 funcionários de teste"""
    print('=== CRIANDO 3 FUNCIONÁRIOS DE TESTE ===')
    
    funcionarios_data = [
        {'nome': 'Carlos Silva Teste', 'cpf': '11122233001', 'email': 'carlos.teste@sige.com', 'telefone': '11999887766', 'salario': 2500.00},
        {'nome': 'João Santos Teste', 'cpf': '22233344001', 'email': 'joao.teste@sige.com', 'telefone': '11888776655', 'salario': 1800.00},
        {'nome': 'Maria Oliveira Teste', 'cpf': '33344455001', 'email': 'maria.teste@sige.com', 'telefone': '11777665544', 'salario': 3200.00}
    ]
    
    funcionarios_criados = []
    for func_data in funcionarios_data:
        # Verificar se já existe
        func_existente = Funcionario.query.filter_by(cpf=func_data['cpf']).first()
        if not func_existente:
            funcionario = Funcionario(
                codigo=gerar_codigo_funcionario(),
                nome=func_data['nome'],
                cpf=func_data['cpf'],
                email=func_data['email'],
                telefone=func_data['telefone'],
                data_admissao=date(2025, 8, 1),
                salario=func_data['salario'],
                admin_id=10,
                ativo=True
            )
            db.session.add(funcionario)
            db.session.flush()
            funcionarios_criados.append(funcionario)
            print(f'✅ Funcionário criado: {funcionario.nome} - ID: {funcionario.id} - Código: {funcionario.codigo}')
        else:
            funcionarios_criados.append(func_existente)
            print(f'🔄 Funcionário já existe: {func_existente.nome} - ID: {func_existente.id}')
    
    return funcionarios_criados

def criar_servicos():
    """Criar 3 serviços com subatividades"""
    print('=== CRIANDO 3 SERVIÇOS COM SUBATIVIDADES ===')
    
    servicos_data = [
        {
            'nome': 'Fundação e Estrutura Teste',
            'descricao': 'Serviços de fundação e estrutura de concreto',
            'subatividades': ['Escavação', 'Armação', 'Concretagem', 'Desforma']
        },
        {
            'nome': 'Alvenaria e Revestimento Teste', 
            'descricao': 'Serviços de alvenaria e revestimentos',
            'subatividades': ['Alvenaria', 'Chapisco', 'Reboco', 'Revestimento']
        },
        {
            'nome': 'Instalações Elétricas Teste',
            'descricao': 'Serviços de instalações elétricas',
            'subatividades': ['Eletrodutos', 'Fiação', 'Quadros', 'Acabamentos']
        }
    ]
    
    servicos_criados = []
    for serv_data in servicos_data:
        # Verificar se já existe
        serv_existente = Servico.query.filter_by(nome=serv_data['nome'], admin_id=10).first()
        if not serv_existente:
            servico = Servico(
                nome=serv_data['nome'],
                descricao=serv_data['descricao'],
                admin_id=10,
                ativo=True
            )
            db.session.add(servico)
            db.session.flush()
            servicos_criados.append(servico)
            print(f'✅ Serviço criado: {servico.nome} - ID: {servico.id}')
        else:
            servicos_criados.append(serv_existente)
            print(f'🔄 Serviço já existe: {serv_existente.nome} - ID: {serv_existente.id}')
    
    # Criar subatividades para cada serviço
    for i, servico in enumerate(servicos_criados):
        subatividades = servicos_data[i]['subatividades']
        for sub_nome in subatividades:
            # Verificar se já existe
            sub_existente = SubatividadeMestre.query.filter_by(nome=sub_nome).first()
            if not sub_existente:
                subatividade = SubatividadeMestre(
                    nome=sub_nome
                )
                db.session.add(subatividade)
                print(f'  ✅ Subatividade criada: {sub_nome}')
            else:
                print(f'  🔄 Subatividade já existe: {sub_nome}')
    
    return servicos_criados

def criar_obra(servicos):
    """Criar obra de teste com os serviços"""
    print('=== CRIANDO OBRA DE TESTE ===')
    
    obra_nome = 'Projeto Teste Completo - Validação de Custos SIGE'
    obra_existente = Obra.query.filter_by(nome=obra_nome).first()
    
    if not obra_existente:
        obra = Obra(
            nome=obra_nome,
            endereco='Rua dos Testes SIGE, 123 - São Paulo/SP',
            status='Em andamento',
            data_inicio=date(2025, 9, 1),
            data_previsao_fim=date(2025, 10, 31),
            area_total_m2=250.0,
            orcamento=150000.00,
            valor_contrato=180000.00,
            codigo='SIGE2025',
            cliente_nome='Cliente Teste SIGE Ltda',
            cliente_email='cliente@sige-teste.com',
            cliente_telefone='11999888777',
            portal_ativo=True,
            admin_id=10
        )
        db.session.add(obra)
        db.session.flush()
        print(f'✅ Obra criada: {obra.nome} - ID: {obra.id}')
        
        # Associar serviços à obra
        for servico in servicos:
            # Verificar se já existe associação
            servico_obra_existente = ServicoObra.query.filter_by(
                obra_id=obra.id,
                servico_id=servico.id
            ).first()
            
            if not servico_obra_existente:
                servico_obra = ServicoObra(
                    obra_id=obra.id,
                    servico_id=servico.id,
                    quantidade_planejada=100.0,  # Campo obrigatório
                    quantidade_executada=0.0
                )
                db.session.add(servico_obra)
                print(f'  ✅ Serviço associado: {servico.nome}')
        
        obra_id = obra.id
    else:
        obra_id = obra_existente.id
        print(f'🔄 Obra já existe: {obra_existente.nome} - ID: {obra_id}')
    
    return obra_id

def criar_rdos_e_pontos(funcionarios, obra_id):
    """Criar RDOs e registros de ponto para setembro 2025"""
    print('=== CRIANDO MÊS DE RDOs E REGISTROS DE PONTO ===')
    
    data_inicio = date(2025, 9, 1)
    data_fim = date(2025, 9, 30)
    
    data_atual = data_inicio
    rdos_criados = 0
    pontos_criados = 0
    
    while data_atual <= data_fim:
        # Pular finais de semana (sábado=5, domingo=6)
        if data_atual.weekday() < 5:  # Segunda a sexta
            
            # Verificar se RDO já existe para esta data
            rdo_existente = RDO.query.filter_by(obra_id=obra_id, data=data_atual).first()
            
            if not rdo_existente:
                # Criar RDO
                rdo = RDO(
                    obra_id=obra_id,
                    data=data_atual,
                    clima='Ensolarado',
                    local='Campo',
                    atividades_executadas=f'Atividades de teste SIGE - {data_atual.strftime("%d/%m/%Y")}',
                    materiais_utilizados='Materiais diversos para teste',
                    observacoes='RDO de teste para validação de custos SIGE',
                    admin_id=10
                )
                db.session.add(rdo)
                db.session.flush()
                
                # Adicionar funcionários no RDO com horas variadas
                for funcionario in funcionarios:
                    # Horas aleatórias entre 7 e 9 horas
                    horas_trabalhadas = round(random.uniform(7.0, 9.0), 1)
                    
                    rdo_mao_obra = RDOMaoObra(
                        rdo_id=rdo.id,
                        funcionario_id=funcionario.id,
                        horas_trabalhadas=horas_trabalhadas,
                        atividade='Atividades gerais de construção'
                    )
                    db.session.add(rdo_mao_obra)
                
                rdos_criados += 1
            
            # Criar registros de ponto para cada funcionário
            for funcionario in funcionarios:
                # Verificar se já existe ponto
                ponto_existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_atual
                ).first()
                
                if not ponto_existente:
                    # Horários variados mas realistas
                    entrada_base = 7 + random.randint(0, 30)/60.0  # 7:00 a 7:30
                    saida_almoco = entrada_base + 4  # 4h depois
                    volta_almoco = saida_almoco + 1  # 1h de almoço
                    saida_final = volta_almoco + random.uniform(4.0, 4.5)  # 4 a 4.5h tarde
                    
                    # Converter para datetime
                    entrada_dt = datetime.combine(data_atual, datetime.min.time().replace(
                        hour=int(entrada_base), 
                        minute=int((entrada_base % 1) * 60)
                    ))
                    
                    saida_almoco_dt = datetime.combine(data_atual, datetime.min.time().replace(
                        hour=int(saida_almoco), 
                        minute=int((saida_almoco % 1) * 60)
                    ))
                    
                    volta_almoco_dt = datetime.combine(data_atual, datetime.min.time().replace(
                        hour=int(volta_almoco), 
                        minute=int((volta_almoco % 1) * 60)
                    ))
                    
                    saida_final_dt = datetime.combine(data_atual, datetime.min.time().replace(
                        hour=int(saida_final), 
                        minute=int((saida_final % 1) * 60)
                    ))
                    
                    # Criar registro de ponto
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        entrada=entrada_dt,
                        saida_almoco=saida_almoco_dt,
                        volta_almoco=volta_almoco_dt,
                        saida=saida_final_dt,
                        obra_id=obra_id,
                        admin_id=10
                    )
                    db.session.add(registro)
                    pontos_criados += 1
            
            if rdos_criados % 5 == 0 and rdos_criados > 0:
                print(f'📅 {rdos_criados} RDOs criados até {data_atual.strftime("%d/%m/%Y")}')
        
        data_atual += timedelta(days=1)
    
    print(f'✅ Total de RDOs criados: {rdos_criados}')
    print(f'✅ Total de registros de ponto criados: {pontos_criados}')

def criar_alimentacao_e_transporte(funcionarios, obra_id):
    """Criar lançamentos de alimentação e transporte"""
    print('=== CRIANDO LANÇAMENTOS DE ALIMENTAÇÃO E TRANSPORTE ===')
    
    data_inicio = date(2025, 9, 1)
    data_fim = date(2025, 9, 30)
    
    data_atual = data_inicio
    alimentacao_criados = 0
    transporte_criados = 0
    
    while data_atual <= data_fim:
        # Pular finais de semana
        if data_atual.weekday() < 5:  # Segunda a sexta
            
            for funcionario in funcionarios:
                # Criar lançamento de alimentação
                alimentacao_existente = RegistroAlimentacao.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_atual
                ).first()
                
                if not alimentacao_existente:
                    # Valores de alimentação (R$ 15-25 por dia)
                    valor_alimentacao = round(random.uniform(15.0, 25.0), 2)
                    
                    registro_alimentacao = RegistroAlimentacao(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        tipo_refeicao='Almoço',
                        valor=valor_alimentacao,
                        obra_id=obra_id,
                        observacoes=f'Alimentação teste SIGE {data_atual.strftime("%d/%m/%Y")}',
                        admin_id=10
                    )
                    db.session.add(registro_alimentacao)
                    alimentacao_criados += 1
                
                # Criar transporte (mais esporádico - 60% dos dias)
                if random.random() < 0.6:  # 60% de chance
                    transporte_existente = OutrosCustos.query.filter_by(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        tipo='Transporte'
                    ).first()
                    
                    if not transporte_existente:
                        # Valores de transporte (R$ 8-15)
                        valor_transporte = round(random.uniform(8.0, 15.0), 2)
                        
                        registro_transporte = OutrosCustos(
                            funcionario_id=funcionario.id,
                            data=data_atual,
                            tipo='Transporte',
                            descricao='Vale transporte teste SIGE',
                            valor=valor_transporte,
                            obra_id=obra_id,
                            admin_id=10
                        )
                        db.session.add(registro_transporte)
                        transporte_criados += 1
        
        data_atual += timedelta(days=1)
    
    print(f'✅ Lançamentos de alimentação criados: {alimentacao_criados}')
    print(f'✅ Lançamentos de transporte criados: {transporte_criados}')

def main():
    """Função principal do teste"""
    with app.app_context():
        try:
            print('🎯 INICIANDO TESTE COMPLETO SIGE v8.0')
            print('=' * 60)
            
            # 1. Criar funcionários
            funcionarios = criar_funcionarios()
            
            # 2. Criar serviços
            servicos = criar_servicos()
            
            # 3. Criar obra
            obra_id = criar_obra(servicos)
            
            # 4. Criar RDOs e pontos
            criar_rdos_e_pontos(funcionarios, obra_id)
            
            # 5. Criar alimentação e transporte
            criar_alimentacao_e_transporte(funcionarios, obra_id)
            
            # Commit final
            db.session.commit()
            
            print('=' * 60)
            print('🎉 TESTE COMPLETO CRIADO COM SUCESSO!')
            print(f'📊 Dados criados para setembro/2025')
            print(f'🏗️  Obra ID: {obra_id}')
            print(f'👥 Funcionários: {len(funcionarios)}')
            print(f'🔧 Serviços: {len(servicos)}')
            print('💰 Verificar custos na página de detalhes da obra')
            
        except Exception as e:
            db.session.rollback()
            print(f'❌ ERRO durante criação do teste: {str(e)}')
            raise

if __name__ == '__main__':
    main()