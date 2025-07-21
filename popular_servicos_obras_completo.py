#!/usr/bin/env python3
"""
Script para popular as obras com serviços associados
"""

from app import app, db
from models import Obra, Servico, ServicoObra

def popular_servicos_obras():
    with app.app_context():
        print("Iniciando população de serviços nas obras...")
        
        # Buscar todas as obras
        obras = Obra.query.all()
        servicos = Servico.query.filter_by(ativo=True).all()
        
        if not obras:
            print("Nenhuma obra encontrada!")
            return
            
        if not servicos:
            print("Nenhum serviço encontrado!")
            return
            
        print(f"Encontradas {len(obras)} obras e {len(servicos)} serviços")
        
        # Limpar associações existentes
        ServicoObra.query.delete()
        db.session.commit()
        print("Associações existentes removidas")
        
        # Associar serviços às obras
        for i, obra in enumerate(obras):
            print(f"\nProcessando obra: {obra.nome}")
            
            if i == 0:  # Primeira obra - Residencial Belo Horizonte
                # Serviços mais comuns para construção residencial
                servicos_obra = [
                    {'servico_nome': 'Fundação em Concreto Armado', 'quantidade': 45.0, 'executada': 12.0},
                    {'servico_nome': 'Alvenaria de Blocos Cerâmicos', 'quantidade': 280.0, 'executada': 75.0},
                    {'servico_nome': 'Estrutura de Concreto Armado', 'quantidade': 35.0, 'executada': 8.0},
                    {'servico_nome': 'Cobertura em Telhas Cerâmicas', 'quantidade': 150.0, 'executada': 0.0},
                    {'servico_nome': 'Revestimento Cerâmico', 'quantidade': 120.0, 'executada': 25.0},
                    {'servico_nome': 'Pintura Interna e Externa', 'quantidade': 300.0, 'executada': 45.0},
                ]
                
            elif i == 1:  # Segunda obra - Prédio Comercial
                # Serviços para construção comercial
                servicos_obra = [
                    {'servico_nome': 'Fundação em Concreto Armado', 'quantidade': 80.0, 'executada': 80.0},
                    {'servico_nome': 'Estrutura de Concreto Armado', 'quantidade': 120.0, 'executada': 95.0},
                    {'servico_nome': 'Alvenaria de Blocos Cerâmicos', 'quantidade': 450.0, 'executada': 350.0},
                    {'servico_nome': 'Instalações Elétricas', 'quantidade': 25.0, 'executada': 18.0},
                    {'servico_nome': 'Instalações Hidráulicas', 'quantidade': 30.0, 'executada': 22.0},
                    {'servico_nome': 'Esquadrias de Alumínio', 'quantidade': 45.0, 'executada': 15.0},
                    {'servico_nome': 'Revestimento Cerâmico', 'quantidade': 200.0, 'executada': 80.0},
                ]
                
            else:  # Demais obras
                # Serviços variados
                servicos_obra = [
                    {'servico_nome': 'Escavação e Terraplanagem', 'quantidade': 180.0, 'executada': 180.0},
                    {'servico_nome': 'Fundação em Concreto Armado', 'quantidade': 65.0, 'executada': 40.0},
                    {'servico_nome': 'Alvenaria de Blocos Cerâmicos', 'quantidade': 320.0, 'executada': 160.0},
                    {'servico_nome': 'Cobertura em Telhas Cerâmicas', 'quantidade': 180.0, 'executada': 45.0},
                    {'servico_nome': 'Pintura Interna e Externa', 'quantidade': 250.0, 'executada': 0.0},
                ]
            
            # Criar associações
            for servico_data in servicos_obra:
                servico = Servico.query.filter_by(nome=servico_data['servico_nome']).first()
                if servico:
                    servico_obra_obj = ServicoObra(
                        obra_id=obra.id,
                        servico_id=servico.id,
                        quantidade_planejada=servico_data['quantidade'],
                        quantidade_executada=servico_data['executada'],
                        observacoes=f"Serviço associado automaticamente à obra {obra.nome}",
                        ativo=True
                    )
                    db.session.add(servico_obra_obj)
                    print(f"  ✓ {servico.nome}: {servico_data['quantidade']} {servico.unidade_simbolo} (executado: {servico_data['executada']})")
                else:
                    print(f"  ✗ Serviço '{servico_data['servico_nome']}' não encontrado!")
        
        # Salvar mudanças
        db.session.commit()
        print(f"\n✅ População concluída! Todas as obras agora possuem serviços associados.")
        
        # Verificar resultado
        print("\n📊 Resumo das associações:")
        for obra in obras:
            total_servicos = ServicoObra.query.filter_by(obra_id=obra.id, ativo=True).count()
            print(f"  {obra.nome}: {total_servicos} serviços associados")

if __name__ == '__main__':
    popular_servicos_obras()