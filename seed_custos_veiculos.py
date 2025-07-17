#!/usr/bin/env python3
"""Script para popular custos de veículos"""

from app import app, db
from models import CustoVeiculo, Veiculo
from datetime import date, timedelta
import random

def criar_custos_veiculos():
    """Criar custos de veículos para testes"""
    
    with app.app_context():
        # Verificar se já existem dados
        if CustoVeiculo.query.count() > 0:
            print("Custos de veículos já existem. Limpando dados antigos...")
            CustoVeiculo.query.delete()
            db.session.commit()
        
        # Buscar veículos existentes
        veiculos = Veiculo.query.all()
        if not veiculos:
            print("Nenhum veículo encontrado. Execute primeiro o script de veículos.")
            return
        
        print(f"Criando custos para {len(veiculos)} veículos...")
        
        # Tipos de custo
        tipos_custo = ['combustivel', 'manutencao', 'seguro', 'multa', 'lavagem', 'outros']
        
        # Gerar custos para junho de 2025
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        custos_criados = 0
        
        for veiculo in veiculos:
            # Cada veículo terá entre 5-15 custos no período
            num_custos = random.randint(5, 15)
            
            for _ in range(num_custos):
                # Data aleatória no período
                dias = (data_fim - data_inicio).days
                data_custo = data_inicio + timedelta(days=random.randint(0, dias))
                
                # Tipo de custo
                tipo = random.choice(tipos_custo)
                
                # Valor baseado no tipo
                if tipo == 'combustivel':
                    valor = round(random.uniform(50, 150), 2)
                    descricao = f"Abastecimento - {random.choice(['Posto Shell', 'Posto Petrobras', 'Posto Ipiranga'])}"
                elif tipo == 'manutencao':
                    valor = round(random.uniform(100, 800), 2)
                    descricao = f"Manutenção - {random.choice(['Troca de óleo', 'Revisão geral', 'Pneus', 'Freios', 'Embreagem'])}"
                elif tipo == 'seguro':
                    valor = round(random.uniform(200, 500), 2)
                    descricao = "Pagamento de seguro veicular"
                elif tipo == 'multa':
                    valor = round(random.uniform(80, 300), 2)
                    descricao = f"Multa - {random.choice(['Excesso de velocidade', 'Estacionamento irregular', 'Não usar cinto'])}"
                elif tipo == 'lavagem':
                    valor = round(random.uniform(15, 35), 2)
                    descricao = "Lavagem e enceramento"
                else:  # outros
                    valor = round(random.uniform(20, 200), 2)
                    descricao = f"{random.choice(['Pedágio', 'Estacionamento', 'Documentação', 'Acessórios'])}"
                
                # KM atual (aumentando ao longo do tempo)
                km_base = 100000 + random.randint(0, 50000)
                km_atual = km_base + (data_custo - data_inicio).days * random.randint(50, 200)
                
                custo = CustoVeiculo(
                    veiculo_id=veiculo.id,
                    data_custo=data_custo,
                    valor=valor,
                    tipo_custo=tipo,
                    descricao=descricao,
                    km_atual=km_atual,
                    fornecedor=random.choice([
                        'Auto Center Silva', 'Oficina João', 'Posto Central',
                        'Mecânica Santos', 'Concessionária', 'Lava Jato Brilho'
                    ]) if random.random() > 0.3 else None
                )
                
                db.session.add(custo)
                custos_criados += 1
        
        db.session.commit()
        print(f"✅ {custos_criados} custos de veículos criados com sucesso!")
        
        # Estatísticas
        total_valor = db.session.query(db.func.sum(CustoVeiculo.valor)).scalar() or 0
        print(f"💰 Valor total dos custos: R$ {total_valor:,.2f}")
        
        for tipo in tipos_custo:
            count = CustoVeiculo.query.filter_by(tipo_custo=tipo).count()
            total_tipo = db.session.query(db.func.sum(CustoVeiculo.valor)).filter_by(tipo_custo=tipo).scalar() or 0
            print(f"   {tipo.title()}: {count} registros - R$ {total_tipo:,.2f}")

if __name__ == '__main__':
    criar_custos_veiculos()