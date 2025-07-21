#!/usr/bin/env python3
"""
Script para criar serviços faltantes no sistema
"""

from app import app, db
from models import Servico

def criar_servicos_faltantes():
    with app.app_context():
        print("Criando serviços faltantes...")
        
        servicos_para_criar = [
            {
                'nome': 'Fundação em Concreto Armado',
                'descricao': 'Execução de fundações em concreto armado',
                'categoria': 'estrutura',
                'unidade_medida': 'm3',
                'unidade_simbolo': 'm³',
                'custo_unitario': 450.00,
                'complexidade': 4
            },
            {
                'nome': 'Cobertura em Telhas Cerâmicas',
                'descricao': 'Instalação de cobertura com telhas cerâmicas',
                'categoria': 'acabamento',
                'unidade_medida': 'm2',
                'unidade_simbolo': 'm²',
                'custo_unitario': 85.00,
                'complexidade': 3
            },
            {
                'nome': 'Pintura Interna e Externa',
                'descricao': 'Serviços de pintura interna e externa',
                'categoria': 'acabamento',
                'unidade_medida': 'm2',
                'unidade_simbolo': 'm²',
                'custo_unitario': 25.00,
                'complexidade': 2
            },
            {
                'nome': 'Instalações Elétricas',
                'descricao': 'Instalação de sistemas elétricos',
                'categoria': 'instalacoes',
                'unidade_medida': 'un',
                'unidade_simbolo': 'un',
                'custo_unitario': 350.00,
                'complexidade': 4
            },
            {
                'nome': 'Instalações Hidráulicas',
                'descricao': 'Instalação de sistemas hidráulicos',
                'categoria': 'instalacoes',
                'unidade_medida': 'un',
                'unidade_simbolo': 'un',
                'custo_unitario': 280.00,
                'complexidade': 4
            },
            {
                'nome': 'Esquadrias de Alumínio',
                'descricao': 'Instalação de esquadrias de alumínio',
                'categoria': 'acabamento',
                'unidade_medida': 'un',
                'unidade_simbolo': 'un',
                'custo_unitario': 420.00,
                'complexidade': 3
            },
            {
                'nome': 'Escavação e Terraplanagem',
                'descricao': 'Serviços de escavação e terraplanagem',
                'categoria': 'estrutura',
                'unidade_medida': 'm3',
                'unidade_simbolo': 'm³',
                'custo_unitario': 35.00,
                'complexidade': 2
            }
        ]
        
        servicos_criados = 0
        for servico_data in servicos_para_criar:
            # Verificar se o serviço já existe
            servico_existente = Servico.query.filter_by(nome=servico_data['nome']).first()
            if not servico_existente:
                servico = Servico(
                    nome=servico_data['nome'],
                    descricao=servico_data['descricao'],
                    categoria=servico_data['categoria'],
                    unidade_medida=servico_data['unidade_medida'],
                    unidade_simbolo=servico_data['unidade_simbolo'],
                    custo_unitario=servico_data['custo_unitario'],
                    complexidade=servico_data['complexidade'],
                    requer_especializacao=servico_data['complexidade'] >= 4,
                    ativo=True
                )
                db.session.add(servico)
                servicos_criados += 1
                print(f"✓ Criado: {servico_data['nome']}")
            else:
                print(f"- Já existe: {servico_data['nome']}")
        
        db.session.commit()
        print(f"\n✅ {servicos_criados} novos serviços criados!")
        
        # Listar todos os serviços
        print("\n📋 Serviços disponíveis no sistema:")
        servicos = Servico.query.filter_by(ativo=True).order_by(Servico.categoria, Servico.nome).all()
        for servico in servicos:
            print(f"  - {servico.nome} ({servico.categoria}) - {servico.unidade_simbolo}")

if __name__ == '__main__':
    criar_servicos_faltantes()