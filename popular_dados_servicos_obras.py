#!/usr/bin/env python3
"""
Script para popular dados de exemplo: Serviços e Obras com ServicoObra
Sistema SIGE v6.3 - Estruturas do Vale
"""

from app import app, db
from models import Servico, SubAtividade, Obra, ServicoObra, Funcionario
from datetime import datetime, date

def criar_servicos_exemplo():
    """Criar serviços de exemplo para construção civil"""
    
    servicos_dados = [
        {
            'nome': 'Concretagem de Fundação',
            'descricao': 'Concretagem de sapatas e blocos de fundação',
            'categoria': 'estrutura',
            'unidade_medida': 'm3',
            'unidade_simbolo': 'm³',
            'custo_unitario': 350.00,
            'complexidade': 4,
            'requer_especializacao': True,
            'subatividades': [
                {
                    'nome': 'Preparação da base',
                    'descricao': 'Limpeza e nivelamento da base',
                    'ordem_execucao': 1,
                    'ferramentas_necessarias': 'Pá, enxada, nível',
                    'materiais_principais': 'Brita, areia',
                    'qualificacao_minima': 'ajudante'
                },
                {
                    'nome': 'Armação',
                    'descricao': 'Montagem da armadura de ferro',
                    'ordem_execucao': 2,
                    'ferramentas_necessarias': 'Torquês, martelo, bancada',
                    'materiais_principais': 'Ferro, arame recozido',
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Concretagem',
                    'descricao': 'Lançamento e adensamento do concreto',
                    'ordem_execucao': 3,
                    'ferramentas_necessarias': 'Vibrador, pá, enxada',
                    'materiais_principais': 'Concreto usinado',
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Acabamento e Cura',
                    'descricao': 'Acabamento superficial e cura do concreto',
                    'ordem_execucao': 4,
                    'ferramentas_necessarias': 'Desempenadeira, aspersão',
                    'materiais_principais': 'Água',
                    'qualificacao_minima': 'ajudante'
                }
            ]
        },
        {
            'nome': 'Alvenaria de Blocos Cerâmicos',
            'descricao': 'Execução de paredes em alvenaria estrutural',
            'categoria': 'alvenaria',
            'unidade_medida': 'm2',
            'unidade_simbolo': 'm²',
            'custo_unitario': 85.00,
            'complexidade': 3,
            'requer_especializacao': False,
            'subatividades': [
                {
                    'nome': 'Marcação',
                    'descricao': 'Marcação da primeira fiada',
                    'ordem_execucao': 1,
                    'ferramentas_necessarias': 'Linha, esquadro, nível',
                    'materiais_principais': 'Argamassa',
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Assentamento',
                    'descricao': 'Assentamento dos blocos',
                    'ordem_execucao': 2,
                    'ferramentas_necessarias': 'Colher, martelo, nível',
                    'materiais_principais': 'Blocos cerâmicos, argamassa',
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Prumo e Nível',
                    'descricao': 'Verificação de prumo e nível',
                    'ordem_execucao': 3,
                    'ferramentas_necessarias': 'Prumo, nível',
                    'materiais_principais': '',
                    'qualificacao_minima': 'oficial'
                }
            ]
        },
        {
            'nome': 'Revestimento Cerâmico',
            'descricao': 'Aplicação de revestimento cerâmico em paredes e pisos',
            'categoria': 'acabamento',
            'unidade_medida': 'm2',
            'unidade_simbolo': 'm²',
            'custo_unitario': 45.00,
            'complexidade': 3,
            'requer_especializacao': True,
            'subatividades': [
                {
                    'nome': 'Preparação da base',
                    'descricao': 'Limpeza e preparação da superfície',
                    'ordem_execucao': 1,
                    'ferramentas_necessarias': 'Escova, pano, aspirador',
                    'materiais_principais': 'Detergente, primer',
                    'qualificacao_minima': 'ajudante'
                },
                {
                    'nome': 'Aplicação da cola',
                    'descricao': 'Aplicação do adesivo cerâmico',
                    'ordem_execucao': 2,
                    'ferramentas_necessarias': 'Desempenadeira dentada',
                    'materiais_principais': 'Adesivo cerâmico',
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Assentamento das peças',
                    'descricao': 'Colocação das peças cerâmicas',
                    'ordem_execucao': 3,
                    'ferramentas_necessarias': 'Martelo de borracha, esquadro',
                    'materiais_principais': 'Cerâmica, espaçadores',
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Rejuntamento',
                    'descricao': 'Aplicação do rejunte',
                    'ordem_execucao': 4,
                    'ferramentas_necessarias': 'Desempenadeira, esponja',
                    'materiais_principais': 'Rejunte',
                    'qualificacao_minima': 'meio_oficial'
                }
            ]
        },
        {
            'nome': 'Instalação Elétrica',
            'descricao': 'Instalação de rede elétrica residencial',
            'categoria': 'instalacoes',
            'unidade_medida': 'un',
            'unidade_simbolo': 'un',
            'custo_unitario': 25.00,
            'complexidade': 5,
            'requer_especializacao': True,
            'subatividades': [
                {
                    'nome': 'Tubulação',
                    'descricao': 'Instalação de eletrodutos',
                    'ordem_execucao': 1,
                    'ferramentas_necessarias': 'Furadeira, serra copo',
                    'materiais_principais': 'Eletrodutos, curvas, luvas',
                    'qualificacao_minima': 'especialista'
                },
                {
                    'nome': 'Fiação',
                    'descricao': 'Passagem dos cabos elétricos',
                    'ordem_execucao': 2,
                    'ferramentas_necessarias': 'Guia passante, alicate',
                    'materiais_principais': 'Cabos elétricos',
                    'qualificacao_minima': 'especialista'
                },
                {
                    'nome': 'Instalação de dispositivos',
                    'descricao': 'Instalação de tomadas e interruptores',
                    'ordem_execucao': 3,
                    'ferramentas_necessarias': 'Chaves, teste de fase',
                    'materiais_principais': 'Tomadas, interruptores, espelhos',
                    'qualificacao_minima': 'especialista'
                }
            ]
        },
        {
            'nome': 'Pintura Interna',
            'descricao': 'Pintura de paredes internas com tinta látex',
            'categoria': 'acabamento',
            'unidade_medida': 'm2',
            'unidade_simbolo': 'm²',
            'custo_unitario': 12.00,
            'complexidade': 2,
            'requer_especializacao': False,
            'subatividades': [
                {
                    'nome': 'Preparação da superfície',
                    'descricao': 'Lixamento e limpeza das paredes',
                    'ordem_execucao': 1,
                    'ferramentas_necessarias': 'Lixa, pano, escova',
                    'materiais_principais': 'Massa corrida, selador',
                    'qualificacao_minima': 'ajudante'
                },
                {
                    'nome': 'Primeira demão',
                    'descricao': 'Aplicação da primeira demão de tinta',
                    'ordem_execucao': 2,
                    'ferramentas_necessarias': 'Rolo, pincel, bandeja',
                    'materiais_principais': 'Tinta látex',
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Segunda demão',
                    'descricao': 'Aplicação da segunda demão de tinta',
                    'ordem_execucao': 3,
                    'ferramentas_necessarias': 'Rolo, pincel, bandeja',
                    'materiais_principais': 'Tinta látex',
                    'qualificacao_minima': 'meio_oficial'
                }
            ]
        }
    ]
    
    print("Criando serviços de exemplo...")
    
    for servico_data in servicos_dados:
        # Verificar se já existe
        servico_existente = Servico.query.filter_by(nome=servico_data['nome']).first()
        if servico_existente:
            print(f"  Serviço '{servico_data['nome']}' já existe, pulando...")
            continue
            
        # Criar serviço
        servico = Servico(
            nome=servico_data['nome'],
            descricao=servico_data['descricao'],
            categoria=servico_data['categoria'],
            unidade_medida=servico_data['unidade_medida'],
            unidade_simbolo=servico_data['unidade_simbolo'],
            custo_unitario=servico_data['custo_unitario'],
            complexidade=servico_data['complexidade'],
            requer_especializacao=servico_data['requer_especializacao'],
            ativo=True
        )
        
        db.session.add(servico)
        db.session.flush()  # Para obter o ID
        
        # Criar subatividades
        for sub_data in servico_data['subatividades']:
            subatividade = SubAtividade(
                servico_id=servico.id,
                nome=sub_data['nome'],
                descricao=sub_data['descricao'],
                ordem_execucao=sub_data['ordem_execucao'],
                ferramentas_necessarias=sub_data['ferramentas_necessarias'],
                materiais_principais=sub_data['materiais_principais'],
                qualificacao_minima=sub_data['qualificacao_minima'],
                requer_aprovacao=False,
                pode_executar_paralelo=True,
                ativo=True
            )
            db.session.add(subatividade)
        
        print(f"  ✓ Criado serviço: {servico_data['nome']} com {len(servico_data['subatividades'])} subatividades")
    
    db.session.commit()

def criar_obra_exemplo():
    """Criar uma obra de exemplo com serviços associados"""
    
    # Verificar se já existe
    obra_existente = Obra.query.filter_by(nome='Residencial Vila Verde - Casa 1').first()
    if obra_existente:
        print("Obra de exemplo já existe, atualizando serviços...")
        obra = obra_existente
    else:
        # Buscar responsável (primeiro funcionário ativo)
        responsavel = Funcionario.query.filter_by(ativo=True).first()
        
        # Criar obra
        obra = Obra(
            nome='Residencial Vila Verde - Casa 1',
            codigo='RVV-C001',
            endereco='Rua das Palmeiras, 123 - Loteamento Vila Verde',
            data_inicio=date(2025, 6, 1),
            data_previsao_fim=date(2025, 12, 15),
            orcamento=280000.00,
            area_total_m2=150.00,
            status='Em andamento',
            responsavel_id=responsavel.id if responsavel else None,
            ativo=True
        )
        
        db.session.add(obra)
        db.session.flush()
        print(f"  ✓ Criada obra: {obra.nome}")
    
    # Associar serviços à obra
    servicos_obra_dados = [
        {'nome': 'Concretagem de Fundação', 'quantidade': 8.5},
        {'nome': 'Alvenaria de Blocos Cerâmicos', 'quantidade': 180.0},
        {'nome': 'Revestimento Cerâmico', 'quantidade': 95.0},
        {'nome': 'Instalação Elétrica', 'quantidade': 25.0},
        {'nome': 'Pintura Interna', 'quantidade': 320.0}
    ]
    
    print("Associando serviços à obra...")
    
    for servico_data in servicos_obra_dados:
        servico = Servico.query.filter_by(nome=servico_data['nome']).first()
        if not servico:
            print(f"  ⚠ Serviço '{servico_data['nome']}' não encontrado")
            continue
            
        # Verificar se associação já existe
        servico_obra_existente = ServicoObra.query.filter_by(
            obra_id=obra.id,
            servico_id=servico.id
        ).first()
        
        if servico_obra_existente:
            print(f"  Serviço '{servico_data['nome']}' já associado à obra, atualizando...")
            servico_obra_existente.quantidade_planejada = servico_data['quantidade']
            servico_obra_existente.ativo = True
        else:
            servico_obra = ServicoObra(
                obra_id=obra.id,
                servico_id=servico.id,
                quantidade_planejada=servico_data['quantidade'],
                quantidade_executada=0.0,
                observacoes=f"Planejado para casa de {obra.area_total_m2:.0f}m²",
                ativo=True
            )
            db.session.add(servico_obra)
            print(f"  ✓ Associado: {servico_data['nome']} - {servico_data['quantidade']} {servico.unidade_simbolo}")
    
    db.session.commit()
    return obra

def main():
    """Função principal"""
    print("=" * 60)
    print("POPULANDO DADOS DE EXEMPLO - SERVIÇOS E OBRAS")
    print("Sistema SIGE v6.3 - Estruturas do Vale")
    print("=" * 60)
    
    with app.app_context():
        try:
            # Criar serviços
            criar_servicos_exemplo()
            print()
            
            # Criar obra com serviços
            obra = criar_obra_exemplo()
            print()
            
            print("=" * 60)
            print("DADOS CRIADOS COM SUCESSO!")
            print("=" * 60)
            print(f"📋 Serviços criados: {Servico.query.count()}")
            print(f"🏗️  Obras: {Obra.query.count()}")
            print(f"🔗 Associações Obra-Serviço: {ServicoObra.query.count()}")
            print()
            print("Para testar:")
            print("1. Acesse a página de Obras")
            print("2. Clique em 'Novo RDO' na obra 'Residencial Vila Verde - Casa 1'")
            print("3. Os serviços serão pré-selecionados automaticamente!")
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    main()