#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corrigir problemas do RDO
"""

from app import app, db
from models import Servico, SubAtividade

def criar_servicos_exemplo():
    """Cria alguns serviços de exemplo para testar o RDO"""
    
    with app.app_context():
        print("=== CRIANDO SERVIÇOS DE EXEMPLO ===")
        
        # Verificar se já existem serviços
        if Servico.query.count() >= 5:
            print("✅ Já existem serviços suficientes")
            return
        
        servicos_exemplo = [
            {
                'nome': 'Concretagem de Laje',
                'categoria': 'estrutura',
                'unidade_medida': 'm3',
                'unidade_simbolo': 'm³',
                'descricao': 'Concretagem de laje de concreto armado',
                'complexidade': 4,
                'requer_especializacao': True
            },
            {
                'nome': 'Alvenaria de Vedação',
                'categoria': 'alvenaria',
                'unidade_medida': 'm2',
                'unidade_simbolo': 'm²',
                'descricao': 'Execução de alvenaria de vedação com tijolos',
                'complexidade': 3,
                'requer_especializacao': False
            },
            {
                'nome': 'Instalação Elétrica',
                'categoria': 'elétrica',
                'unidade_medida': 'm',
                'unidade_simbolo': 'm',
                'descricao': 'Instalação de tubulação e fiação elétrica',
                'complexidade': 4,
                'requer_especializacao': True
            },
            {
                'nome': 'Pintura Interna',
                'categoria': 'pintura',
                'unidade_medida': 'm2',
                'unidade_simbolo': 'm²',
                'descricao': 'Pintura interna com tinta acrílica',
                'complexidade': 2,
                'requer_especializacao': False
            },
            {
                'nome': 'Revestimento Cerâmico',
                'categoria': 'pisos',
                'unidade_medida': 'm2',
                'unidade_simbolo': 'm²',
                'descricao': 'Aplicação de revestimento cerâmico',
                'complexidade': 3,
                'requer_especializacao': True
            }
        ]
        
        for servico_data in servicos_exemplo:
            # Verificar se já existe
            servico_existente = Servico.query.filter_by(nome=servico_data['nome']).first()
            if not servico_existente:
                servico = Servico(**servico_data)
                db.session.add(servico)
                print(f"✅ Criado: {servico.nome}")
        
        db.session.commit()
        print("✅ Serviços criados com sucesso!")

if __name__ == '__main__':
    criar_servicos_exemplo()