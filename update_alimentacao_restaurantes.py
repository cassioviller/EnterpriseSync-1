"""
Script para atualizar registros de alimentação com restaurantes
"""

import random
from app import app, db
from models import RegistroAlimentacao, Restaurante

def atualizar_alimentacao_com_restaurantes():
    """Atualizar registros de alimentação existentes com restaurantes"""
    
    with app.app_context():
        # Buscar restaurantes existentes
        restaurantes = Restaurante.query.all()
        
        if not restaurantes:
            print("Nenhum restaurante encontrado. Criando restaurantes de exemplo...")
            
            # Criar restaurantes de exemplo
            restaurantes_dados = [
                {
                    'nome': 'Restaurante do João',
                    'endereco': 'Rua das Flores, 123 - Centro',
                    'telefone': '(11) 3333-4444',
                    'contato_responsavel': 'João Silva'
                },
                {
                    'nome': 'Cantina da Maria',
                    'endereco': 'Av. Principal, 456 - Bairro Industrial',
                    'telefone': '(11) 5555-6666',
                    'contato_responsavel': 'Maria Santos'
                },
                {
                    'nome': 'Lanchonete Central',
                    'endereco': 'Praça Central, 789 - Centro',
                    'telefone': '(11) 7777-8888',
                    'contato_responsavel': 'Pedro Costa'
                },
                {
                    'nome': 'Restaurante Popular',
                    'endereco': 'Rua do Comércio, 321 - Vila Nova',
                    'telefone': '(11) 9999-0000',
                    'contato_responsavel': 'Ana Oliveira'
                }
            ]
            
            for dados in restaurantes_dados:
                restaurante = Restaurante(
                    nome=dados['nome'],
                    endereco=dados['endereco'],
                    telefone=dados['telefone'],
                    contato_responsavel=dados['contato_responsavel'],
                    ativo=True
                )
                db.session.add(restaurante)
                restaurantes.append(restaurante)
            
            db.session.commit()
            print(f"✓ {len(restaurantes_dados)} restaurantes criados")
        
        # Buscar registros de alimentação sem restaurante
        registros_sem_restaurante = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.restaurante_id.is_(None)
        ).all()
        
        print(f"Atualizando {len(registros_sem_restaurante)} registros de alimentação...")
        
        atualizados = 0
        for registro in registros_sem_restaurante:
            # Atribuir restaurante baseado no tipo de alimentação
            if registro.tipo in ['almoco', 'jantar']:
                # Refeições principais vão para restaurantes maiores
                restaurante = random.choice([r for r in restaurantes if 'Restaurante' in r.nome])
            else:
                # Lanches e cafés podem ir para qualquer lugar
                restaurante = random.choice(restaurantes)
            
            registro.restaurante_id = restaurante.id
            atualizados += 1
        
        try:
            db.session.commit()
            print(f"✓ {atualizados} registros de alimentação atualizados com restaurantes")
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao atualizar registros: {e}")

if __name__ == '__main__':
    atualizar_alimentacao_com_restaurantes()