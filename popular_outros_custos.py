#!/usr/bin/env python3
"""
Script para popular outros custos para junho 2025
"""

from app import app, db
from datetime import date
from models import Funcionario, OutroCusto, CustoVeiculo, CustoObra, Veiculo, Obra
import random

def popular_outros_custos():
    """Popular outros custos para todos os funcionários"""
    print("=== Populando outros custos ===")
    
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        # Vale transporte mensal
        registro = OutroCusto(
            funcionario_id=funcionario.id,
            data=date(2025, 6, 1),
            tipo='Vale Transporte',
            categoria='Benefício',
            valor=150.00,
            descricao=f"Vale transporte mensal - {funcionario.nome}"
        )
        db.session.add(registro)
        registros_criados += 1
        
        # Desconto VT
        registro = OutroCusto(
            funcionario_id=funcionario.id,
            data=date(2025, 6, 1),
            tipo='Desconto VT 6%',
            categoria='Desconto',
            valor=9.00,
            descricao=f"Desconto vale transporte - {funcionario.nome}"
        )
        db.session.add(registro)
        registros_criados += 1
        
        # Outros custos aleatórios
        if random.random() < 0.5:  # 50% chance
            tipos_extras = ['Adiantamento Salário', 'Uniforme', 'EPI', 'Vale Alimentação']
            tipo_extra = random.choice(tipos_extras)
            valor_extra = random.choice([200.00, 300.00, 500.00])
            
            registro = OutroCusto(
                funcionario_id=funcionario.id,
                data=date(2025, 6, random.randint(5, 25)),
                tipo=tipo_extra,
                categoria='Outros',
                valor=valor_extra,
                descricao=f"{tipo_extra} - {funcionario.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    db.session.commit()
    print(f"Criados {registros_criados} outros custos")

def popular_custos_veiculos():
    """Popular custos de veículos"""
    print("=== Populando custos de veículos ===")
    
    veiculos = Veiculo.query.all()
    obras = Obra.query.filter_by(status='Em andamento').all()
    
    if not veiculos or not obras:
        print("Erro: Veículos ou obras não encontrados")
        return
    
    registros_criados = 0
    
    for veiculo in veiculos:
        obra = random.choice(obras)
        
        # Combustível (várias vezes no mês)
        for i in range(5):
            registro = CustoVeiculo(
                veiculo_id=veiculo.id,
                obra_id=obra.id,
                data_custo=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([250.00, 300.00, 350.00]),
                tipo_custo='combustivel',
                descricao=f"Abastecimento {veiculo.placa}",
                fornecedor='Posto Ipiranga'
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Manutenção
        registro = CustoVeiculo(
            veiculo_id=veiculo.id,
            obra_id=obra.id,
            data_custo=date(2025, 6, random.randint(10, 20)),
            valor=random.choice([800.00, 1200.00, 1500.00]),
            tipo_custo='manutencao',
            descricao=f"Manutenção {veiculo.placa}",
            fornecedor='Oficina Central'
        )
        db.session.add(registro)
        registros_criados += 1
    
    db.session.commit()
    print(f"Criados {registros_criados} custos de veículos")

def popular_custos_obras():
    """Popular custos de obras"""
    print("=== Populando custos de obras ===")
    
    obras = Obra.query.filter_by(status='Em andamento').all()
    
    if not obras:
        print("Erro: Obras não encontradas")
        return
    
    registros_criados = 0
    
    for obra in obras:
        # Materiais
        for i in range(6):
            registro = CustoObra(
                obra_id=obra.id,
                data=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([1500.00, 2000.00, 2500.00]),
                tipo='material',
                descricao=f"Material de construção - {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Equipamentos
        for i in range(3):
            registro = CustoObra(
                obra_id=obra.id,
                data=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([1000.00, 1500.00, 2000.00]),
                tipo='equipamento',
                descricao=f"Equipamento - {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Serviços
        for i in range(4):
            registro = CustoObra(
                obra_id=obra.id,
                data=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([800.00, 1200.00, 1600.00]),
                tipo='servico',
                descricao=f"Serviço terceirizado - {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    db.session.commit()
    print(f"Criados {registros_criados} custos de obras")

def main():
    """Função principal"""
    with app.app_context():
        print("POPULANDO CUSTOS ADICIONAIS - JUNHO 2025")
        print("=" * 45)
        
        popular_outros_custos()
        popular_custos_veiculos()
        popular_custos_obras()
        
        print("\n✅ Custos adicionais criados!")

if __name__ == "__main__":
    main()