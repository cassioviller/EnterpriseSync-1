"""
Script para popular o banco de dados com dados de exemplo para restaurantes
"""

from app import app, db
from models import Restaurante

def seed_restaurantes():
    """Criar restaurantes de exemplo"""
    
    with app.app_context():
        # Verificar se já existem restaurantes
        if Restaurante.query.first():
            print("Restaurantes já existem no banco. Skipping...")
            return
        
        restaurantes = [
            {
                'nome': 'Restaurante do João',
                'endereco': 'Rua das Flores, 123 - Centro',
                'telefone': '(11) 99999-1234',
                'email': 'contato@restaurantejoao.com',
                'contato_responsavel': 'João Silva',
                'ativo': True
            },
            {
                'nome': 'Marmitas da Dona Maria',
                'endereco': 'Av. Principal, 456 - Bairro Industrial',
                'telefone': '(11) 98888-5678',
                'email': 'donamaria@marmitas.com',
                'contato_responsavel': 'Maria Santos',
                'ativo': True
            },
            {
                'nome': 'Cantina do Zé',
                'endereco': 'Rua do Trabalho, 789 - Vila Operária',
                'telefone': '(11) 97777-9012',
                'email': 'ze@cantina.com',
                'contato_responsavel': 'José Oliveira',
                'ativo': True
            },
            {
                'nome': 'Lanchonete Express',
                'endereco': 'Praça Central, 321 - Centro',
                'telefone': '(11) 96666-3456',
                'email': 'express@lanches.com',
                'contato_responsavel': 'Ana Costa',
                'ativo': True
            },
            {
                'nome': 'Restaurante Família',
                'endereco': 'Rua da Paz, 654 - Vila Nova',
                'telefone': '(11) 95555-7890',
                'email': 'familia@restaurante.com',
                'contato_responsavel': 'Carlos Mendes',
                'ativo': False  # Um restaurante inativo para teste
            }
        ]
        
        for rest_data in restaurantes:
            restaurante = Restaurante(**rest_data)
            db.session.add(restaurante)
        
        db.session.commit()
        print(f"✓ {len(restaurantes)} restaurantes criados com sucesso!")

if __name__ == '__main__':
    seed_restaurantes()