#!/usr/bin/env python3
"""
Script para criar obra com foco em revestimento cerâmico
"""

from app import app, db
from models import Obra, Servico, ServicoObra, Funcionario
from datetime import date, timedelta

def criar_obra_revestimento():
    with app.app_context():
        print("Criando obra com foco em revestimento cerâmico...")
        
        # Buscar funcionário responsável
        responsavel = Funcionario.query.first()
        
        # Criar nova obra
        obra = Obra(
            nome="Casa Residencial - Revestimento Cerâmico",
            endereco="Rua das Cerâmicas, 123 - Bairro Vila Nova",
            data_inicio=date.today() - timedelta(days=30),
            data_previsao_fim=date.today() + timedelta(days=60),
            orcamento=185000.00,
            status="Em andamento",
            responsavel_id=responsavel.id if responsavel else None
        )
        db.session.add(obra)
        db.session.flush()  # Para obter o ID da obra
        
        print(f"✓ Obra criada: {obra.nome}")
        
        # Buscar serviço de revestimento cerâmico
        servico_revestimento = Servico.query.filter_by(nome="Revestimento Cerâmico").first()
        
        if servico_revestimento:
            # Criar associação com subatividades detalhadas
            servico_obra = ServicoObra(
                obra_id=obra.id,
                servico_id=servico_revestimento.id,
                quantidade_planejada=280.0,
                quantidade_executada=95.0,
                observacoes="Revestimento principal com subatividades detalhadas",
                ativo=True
            )
            db.session.add(servico_obra)
            print(f"✓ Serviço associado: {servico_revestimento.nome} - 280m² (95m² executados)")
            
            # Criar outros serviços complementares
            outros_servicos = [
                {'nome': 'Fundação em Concreto Armado', 'planejada': 45.0, 'executada': 45.0},
                {'nome': 'Alvenaria de Blocos Cerâmicos', 'planejada': 180.0, 'executada': 180.0},
                {'nome': 'Instalações Hidráulicas', 'planejada': 12.0, 'executada': 8.0}
            ]
            
            for servico_data in outros_servicos:
                servico = Servico.query.filter_by(nome=servico_data['nome']).first()
                if servico:
                    servico_obra_extra = ServicoObra(
                        obra_id=obra.id,
                        servico_id=servico.id,
                        quantidade_planejada=servico_data['planejada'],
                        quantidade_executada=servico_data['executada'],
                        observacoes=f"Serviço complementar",
                        ativo=True
                    )
                    db.session.add(servico_obra_extra)
                    print(f"✓ Serviço complementar: {servico.nome}")
        
        db.session.commit()
        print(f"\n✅ Obra criada com sucesso! ID: {obra.id}")
        print(f"📋 Total de serviços associados: {len(outros_servicos) + 1}")

if __name__ == '__main__':
    criar_obra_revestimento()