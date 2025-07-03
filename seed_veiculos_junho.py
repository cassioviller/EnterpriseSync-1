"""
Script para popular dados de veículos para junho de 2025
Inclui uso de veículos e custos diversos
"""

from datetime import datetime, date
import random
from app import app, db
from models import Veiculo, UsoVeiculo, CustoVeiculo, Funcionario, Obra

def criar_dados_veiculos_junho():
    """Criar dados de uso e custos de veículos para junho de 2025"""
    
    with app.app_context():
        # Buscar veículos e funcionários existentes
        veiculos = Veiculo.query.all()
        funcionarios = Funcionario.query.all()
        obras = Obra.query.all()
        
        if not veiculos:
            print("Nenhum veículo encontrado. Execute o populate_db.py primeiro.")
            return
        
        print(f"Criando dados para {len(veiculos)} veículos...")
        
        # Perfis de uso de veículos
        perfis_uso = {
            'intenso': {'dias_por_semana': 5, 'km_por_dia': 120},
            'moderado': {'dias_por_semana': 3, 'km_por_dia': 80},
            'leve': {'dias_por_semana': 2, 'km_por_dia': 50}
        }
        
        usos_criados = 0
        custos_criados = 0
        
        for veiculo in veiculos:
            # Definir perfil de uso baseado no tipo de veículo
            if veiculo.tipo == 'Caminhão':
                perfil = perfis_uso['intenso']
            elif veiculo.tipo == 'Van':
                perfil = perfis_uso['moderado']
            else:
                perfil = perfis_uso['leve']
            
            # Gerar usos para junho de 2025
            for dia in range(1, 31):  # Junho tem 30 dias
                data_uso = date(2025, 6, dia)
                
                # Verificar se deve usar o veículo neste dia
                if random.randint(1, 7) <= perfil['dias_por_semana']:
                    funcionario = random.choice(funcionarios)
                    obra = random.choice(obras) if random.choice([True, False]) else None
                    
                    # Calcular KM
                    km_base = veiculo.km_atual if veiculo.km_atual else 50000
                    km_inicial = km_base + (usos_criados * random.randint(30, 150))
                    km_rodado = random.randint(perfil['km_por_dia'] - 30, perfil['km_por_dia'] + 30)
                    km_final = km_inicial + km_rodado
                    
                    # Finalidades possíveis
                    finalidades = [
                        'Transporte de materiais',
                        'Visita técnica',
                        'Entrega de equipamentos',
                        'Reunião com cliente',
                        'Inspeção de obra',
                        'Transporte de funcionários',
                        'Coleta de materiais',
                        'Serviço externo'
                    ]
                    
                    uso = UsoVeiculo(
                        veiculo_id=veiculo.id,
                        funcionario_id=funcionario.id,
                        data_uso=data_uso,
                        km_inicial=km_inicial,
                        km_final=km_final,
                        finalidade=random.choice(finalidades),
                        observacoes=f"Uso em {data_uso.strftime('%d/%m/%Y')} - {km_rodado}km rodados"
                    )
                    
                    db.session.add(uso)
                    usos_criados += 1
                    
                    # Atualizar KM atual do veículo
                    veiculo.km_atual = km_final
                    
                    # Adicionar custos ocasionalmente
                    if random.random() < 0.3:  # 30% chance de ter custo
                        tipo_custo = random.choice(['combustivel', 'manutencao', 'lavagem', 'outros'])
                        
                        # Valores baseados no tipo de custo
                        valores_custo = {
                            'combustivel': random.uniform(80, 200),
                            'manutencao': random.uniform(150, 800),
                            'lavagem': random.uniform(15, 35),
                            'outros': random.uniform(50, 300)
                        }
                        
                        descricoes = {
                            'combustivel': f'Abastecimento - {random.randint(30, 60)}L',
                            'manutencao': random.choice(['Troca de óleo', 'Alinhamento', 'Revisão geral', 'Troca de pneus']),
                            'lavagem': 'Lavagem completa',
                            'outros': random.choice(['Pedágio', 'Estacionamento', 'Multa', 'Seguro'])
                        }
                        
                        fornecedores = {
                            'combustivel': random.choice(['Posto Ipiranga', 'Shell', 'Petrobras', 'Posto Central']),
                            'manutencao': random.choice(['Oficina do João', 'Auto Center Silva', 'Mecânica Boa Vista']),
                            'lavagem': random.choice(['Lava Rápido', 'Car Wash Premium']),
                            'outros': random.choice(['Ecorodovias', 'Zona Azul', 'Detran'])
                        }
                        
                        custo = CustoVeiculo(
                            veiculo_id=veiculo.id,
                            data_custo=data_uso,
                            valor=valores_custo[tipo_custo],
                            tipo_custo=tipo_custo,
                            descricao=descricoes[tipo_custo],
                            km_atual=km_final,
                            fornecedor=fornecedores[tipo_custo]
                        )
                        
                        db.session.add(custo)
                        custos_criados += 1
        
        # Adicionar alguns custos extras (seguros, IPVAs, etc.)
        for veiculo in veiculos:
            # Seguro mensal
            if random.random() < 0.8:  # 80% chance de ter seguro
                seguro = CustoVeiculo(
                    veiculo_id=veiculo.id,
                    data_custo=date(2025, 6, 1),
                    valor=random.uniform(200, 800),
                    tipo_custo='seguro',
                    descricao='Seguro mensal',
                    fornecedor='Seguradora ABC'
                )
                db.session.add(seguro)
                custos_criados += 1
        
        try:
            db.session.commit()
            print(f"✓ {usos_criados} usos de veículo criados para junho/2025")
            print(f"✓ {custos_criados} custos de veículo criados para junho/2025")
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar dados: {e}")

if __name__ == '__main__':
    criar_dados_veiculos_junho()