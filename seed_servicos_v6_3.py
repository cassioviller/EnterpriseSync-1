#!/usr/bin/env python3
"""
Script para popular serviços conforme especificação SIGE v6.3
Sistema de coleta de dados reais via RDO
"""

import sys
import os
from datetime import datetime

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Servico, SubAtividade

def create_sample_services():
    """Cria serviços de exemplo para demonstrar o sistema SIGE v6.3"""
    
    services_data = [
        {
            'nome': 'Alvenaria de Vedação',
            'descricao': 'Execução de alvenaria de vedação com blocos cerâmicos, incluindo levantamento, prumo e nivelamento.',
            'categoria': 'alvenaria',
            'unidade_medida': 'm2',
            'complexidade': 2,
            'requer_especializacao': False,
            'subatividades': [
                {
                    'nome': 'Marcação e Nivelamento',
                    'descricao': 'Marcação da primeira fiada com nível e esquadro',
                    'ferramentas_necessarias': 'Nível, esquadro, linha de nylon, lápis de carpinteiro',
                    'materiais_principais': 'Argamassa de assentamento',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': False,
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Assentamento dos Blocos',
                    'descricao': 'Assentamento dos blocos cerâmicos com argamassa',
                    'ferramentas_necessarias': 'Colher de pedreiro, martelo, nível de bolha',
                    'materiais_principais': 'Blocos cerâmicos, argamassa de assentamento',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'ajudante'
                },
                {
                    'nome': 'Verificação de Prumo e Nível',
                    'descricao': 'Verificação final do prumo e nível da alvenaria',
                    'ferramentas_necessarias': 'Prumo, nível, régua de alumínio',
                    'materiais_principais': '',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': False,
                    'qualificacao_minima': 'oficial'
                }
            ]
        },
        {
            'nome': 'Estrutura de Concreto Armado',
            'descricao': 'Execução de estrutura de concreto armado incluindo armação, forma e concretagem.',
            'categoria': 'estrutura',
            'unidade_medida': 'm3',
            'complexidade': 5,
            'requer_especializacao': True,
            'subatividades': [
                {
                    'nome': 'Montagem da Armação',
                    'descricao': 'Corte, dobra e montagem da armação conforme projeto',
                    'ferramentas_necessarias': 'Máquina de cortar ferro, dobradeira, alicate',
                    'materiais_principais': 'Ferro CA-50, CA-60, arame recozido',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Montagem da Forma',
                    'descricao': 'Montagem e escoramento das formas de madeira ou metálicas',
                    'ferramentas_necessarias': 'Martelo, furadeira, serra circular, nível',
                    'materiais_principais': 'Madeira, pregos, parafusos, escoras',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Concretagem',
                    'descricao': 'Lançamento e adensamento do concreto',
                    'ferramentas_necessarias': 'Vibrador, régua de sarrafeamento, colher',
                    'materiais_principais': 'Concreto usinado',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': False,
                    'qualificacao_minima': 'especialista'
                }
            ]
        },
        {
            'nome': 'Pintura Interna',
            'descricao': 'Aplicação de pintura interna em paredes com tinta látex acrílica.',
            'categoria': 'pintura',
            'unidade_medida': 'm2',
            'complexidade': 1,
            'requer_especializacao': False,
            'subatividades': [
                {
                    'nome': 'Preparação da Superfície',
                    'descricao': 'Limpeza e preparação da superfície para pintura',
                    'ferramentas_necessarias': 'Lixa, espátula, pano',
                    'materiais_principais': 'Lixa, massa corrida, selador',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'ajudante'
                },
                {
                    'nome': 'Aplicação da Tinta',
                    'descricao': 'Aplicação da tinta com rolo ou pincel',
                    'ferramentas_necessarias': 'Rolo, pincel, bandeja',
                    'materiais_principais': 'Tinta látex acrílica',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'ajudante'
                }
            ]
        },
        {
            'nome': 'Instalação Elétrica',
            'descricao': 'Instalação de sistema elétrico residencial incluindo eletrodutos, fiação e pontos.',
            'categoria': 'instalacoes',
            'unidade_medida': 'm',
            'complexidade': 4,
            'requer_especializacao': True,
            'subatividades': [
                {
                    'nome': 'Marcação dos Pontos',
                    'descricao': 'Marcação de pontos elétricos conforme projeto',
                    'ferramentas_necessarias': 'Trena, lápis, nível',
                    'materiais_principais': '',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': False,
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Instalação dos Eletrodutos',
                    'descricao': 'Instalação de eletrodutos e caixas elétricas',
                    'ferramentas_necessarias': 'Furadeira, martelo, alicate',
                    'materiais_principais': 'Eletrodutos, caixas elétricas, abraçadeiras',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Passagem da Fiação',
                    'descricao': 'Passagem dos fios elétricos pelos eletrodutos',
                    'ferramentas_necessarias': 'Passa-fio, alicate desencapador',
                    'materiais_principais': 'Fios elétricos, fita isolante',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Conexões e Testes',
                    'descricao': 'Conexão dos pontos elétricos e testes do sistema',
                    'ferramentas_necessarias': 'Multímetro, chaves de fenda',
                    'materiais_principais': 'Interruptores, tomadas, disjuntores',
                    'requer_aprovacao': True,
                    'pode_executar_paralelo': False,
                    'qualificacao_minima': 'especialista'
                }
            ]
        },
        {
            'nome': 'Revestimento Cerâmico',
            'descricao': 'Aplicação de revestimento cerâmico em paredes e pisos.',
            'categoria': 'pisos',
            'unidade_medida': 'm2',
            'complexidade': 3,
            'requer_especializacao': False,
            'subatividades': [
                {
                    'nome': 'Preparação do Contrapiso',
                    'descricao': 'Limpeza e nivelamento do contrapiso',
                    'ferramentas_necessarias': 'Vassoura, mangueira, nível',
                    'materiais_principais': 'Argamassa de regularização',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'ajudante'
                },
                {
                    'nome': 'Aplicação da Argamassa Colante',
                    'descricao': 'Aplicação da argamassa colante com desempenadeira',
                    'ferramentas_necessarias': 'Desempenadeira dentada, balde',
                    'materiais_principais': 'Argamassa colante',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'meio_oficial'
                },
                {
                    'nome': 'Assentamento das Cerâmicas',
                    'descricao': 'Assentamento das peças cerâmicas',
                    'ferramentas_necessarias': 'Cortador de cerâmica, nivel, martelo de borracha',
                    'materiais_principais': 'Cerâmica, espaçadores',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'oficial'
                },
                {
                    'nome': 'Rejuntamento',
                    'descricao': 'Aplicação do rejunte e limpeza final',
                    'ferramentas_necessarias': 'Desempenadeira de borracha, esponja',
                    'materiais_principais': 'Rejunte, esponja, pano',
                    'requer_aprovacao': False,
                    'pode_executar_paralelo': True,
                    'qualificacao_minima': 'meio_oficial'
                }
            ]
        }
    ]
    
    with app.app_context():
        print("🏗️  Criando serviços SIGE v6.3...")
        
        # Limpar serviços existentes
        SubAtividade.query.delete()
        Servico.query.delete()
        db.session.commit()
        
        for service_data in services_data:
            print(f"   📋 Criando serviço: {service_data['nome']}")
            
            # Criar serviço
            servico = Servico(
                nome=service_data['nome'],
                descricao=service_data['descricao'],
                categoria=service_data['categoria'],
                unidade_medida=service_data['unidade_medida'],
                complexidade=service_data['complexidade'],
                requer_especializacao=service_data['requer_especializacao'],
                ativo=True
            )
            
            db.session.add(servico)
            db.session.flush()  # Para obter o ID
            
            # Criar subatividades
            for i, sub_data in enumerate(service_data['subatividades']):
                print(f"      • {sub_data['nome']}")
                
                subatividade = SubAtividade(
                    servico_id=servico.id,
                    nome=sub_data['nome'],
                    descricao=sub_data['descricao'],
                    ordem_execucao=i + 1,
                    ferramentas_necessarias=sub_data['ferramentas_necessarias'],
                    materiais_principais=sub_data['materiais_principais'],
                    requer_aprovacao=sub_data['requer_aprovacao'],
                    pode_executar_paralelo=sub_data['pode_executar_paralelo'],
                    qualificacao_minima=sub_data['qualificacao_minima'],
                    ativo=True
                )
                
                db.session.add(subatividade)
        
        db.session.commit()
        
        # Estatísticas
        total_servicos = Servico.query.count()
        total_subatividades = SubAtividade.query.count()
        
        print(f"\n✅ Serviços criados com sucesso!")
        print(f"   📊 Total de serviços: {total_servicos}")
        print(f"   📊 Total de subatividades: {total_subatividades}")
        
        # Estatísticas por categoria
        print("\n📈 Estatísticas por categoria:")
        categorias = db.session.query(Servico.categoria, db.func.count(Servico.id)).group_by(Servico.categoria).all()
        for categoria, count in categorias:
            print(f"   • {categoria.title()}: {count} serviços")
        
        # Estatísticas por complexidade
        print("\n📈 Estatísticas por complexidade:")
        complexidades = db.session.query(Servico.complexidade, db.func.count(Servico.id)).group_by(Servico.complexidade).all()
        complexidade_names = {1: 'Muito Simples', 2: 'Simples', 3: 'Médio', 4: 'Complexo', 5: 'Muito Complexo'}
        for complexidade, count in complexidades:
            print(f"   • {complexidade_names[complexidade]}: {count} serviços")
        
        # Estatísticas por qualificação
        print("\n📈 Estatísticas por qualificação mínima:")
        qualificacoes = db.session.query(SubAtividade.qualificacao_minima, db.func.count(SubAtividade.id)).group_by(SubAtividade.qualificacao_minima).all()
        qualificacao_names = {
            'ajudante': 'Ajudante',
            'meio_oficial': 'Meio Oficial', 
            'oficial': 'Oficial',
            'especialista': 'Especialista',
            '': 'Nenhuma'
        }
        for qualificacao, count in qualificacoes:
            nome = qualificacao_names.get(qualificacao, qualificacao or 'Nenhuma')
            print(f"   • {nome}: {count} subatividades")
        
        print(f"\n🎯 Sistema SIGE v6.3 pronto para coleta de dados via RDO!")
        print(f"   🔄 Os dados de produtividade serão calculados automaticamente")
        print(f"   💰 Custos baseados nos salários reais dos funcionários")
        print(f"   📊 Estimativas geradas com base em dados coletados")

if __name__ == '__main__':
    create_sample_services()