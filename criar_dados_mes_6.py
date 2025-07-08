#!/usr/bin/env python3
"""
Script para criar dados completos para junho 2025
"""

from app import app, db
from datetime import date, datetime, timedelta
from models import *
import random

def criar_dados_junho_2025():
    """Cria dados completos para junho 2025"""
    print("=== CRIANDO DADOS COMPLETOS PARA JUNHO 2025 ===")
    
    # Buscar entidades necessárias
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    obras = Obra.query.filter_by(status='Em andamento').all()
    veiculos = Veiculo.query.all()
    restaurantes = Restaurante.query.all()
    
    print(f"Funcionários: {len(funcionarios)}")
    print(f"Obras: {len(obras)}")
    print(f"Veículos: {len(veiculos)}")
    print(f"Restaurantes: {len(restaurantes)}")
    
    # Criar dados por categoria
    criar_ponto_junho(funcionarios, obras)
    criar_alimentacao_junho(funcionarios, restaurantes)
    criar_outros_custos_junho(funcionarios)
    criar_custos_veiculos_junho(veiculos, obras)
    criar_custos_obra_junho(obras)
    criar_rdos_junho(obras, funcionarios)
    
    db.session.commit()
    print("✅ Dados criados com sucesso!")

def criar_ponto_junho(funcionarios, obras):
    """Cria registros de ponto para junho"""
    print("\n--- Criando registros de ponto ---")
    
    dias_uteis = [
        date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4), date(2025, 6, 5), date(2025, 6, 6),
        date(2025, 6, 9), date(2025, 6, 10), date(2025, 6, 11), date(2025, 6, 12), date(2025, 6, 13),
        date(2025, 6, 16), date(2025, 6, 17), date(2025, 6, 18), date(2025, 6, 20),
        date(2025, 6, 23), date(2025, 6, 24), date(2025, 6, 25), date(2025, 6, 26), date(2025, 6, 27),
        date(2025, 6, 30)
    ]
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        obra = random.choice(obras)
        
        for data in dias_uteis:
            # 85% presença normal, 15% faltas
            if random.random() < 0.85:
                # Trabalho normal
                entrada = datetime.combine(data, datetime.strptime('08:00', '%H:%M').time())
                saida = datetime.combine(data, datetime.strptime('17:00', '%H:%M').time())
                
                # Pequenos atrasos (30% das vezes)
                if random.random() < 0.3:
                    entrada += timedelta(minutes=random.randint(5, 45))
                
                # Calcular horas
                horas_trabalhadas = 8.0
                horas_extras = 0.0
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data,
                    obra_id=obra.id,
                    hora_entrada=entrada.time(),
                    hora_saida=saida.time(),
                    hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
                    hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
                    horas_trabalhadas=horas_trabalhadas,
                    horas_extras=horas_extras,
                    horas_trabalhadas_calculadas=horas_trabalhadas,
                    total_atraso_minutos=max(0, (entrada - datetime.combine(data, datetime.strptime('08:00', '%H:%M').time())).total_seconds() / 60),
                    tipo_registro='trabalho_normal',
                    observacoes='Trabalho normal'
                )
                db.session.add(registro)
                registros_criados += 1
            else:
                # Falta (50% justificada)
                tipo = 'falta_justificada' if random.random() < 0.5 else 'falta'
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data,
                    obra_id=obra.id,
                    tipo_registro=tipo,
                    observacoes=f"Falta {'justificada' if tipo == 'falta_justificada' else 'não justificada'}"
                )
                db.session.add(registro)
                registros_criados += 1
        
        # Adicionar alguns sábados e domingos trabalhados
        sabados = [date(2025, 6, 7), date(2025, 6, 14)]
        for sabado in sabados:
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                data=sabado,
                obra_id=obra.id,
                hora_entrada=datetime.strptime('08:00', '%H:%M').time(),
                hora_saida=datetime.strptime('12:00', '%H:%M').time(),
                horas_trabalhadas=4,
                horas_extras=4,
                horas_trabalhadas_calculadas=4,
                total_atraso_minutos=0,
                tipo_registro='sabado_horas_extras',
                percentual_extras=50,
                observacoes="Sábado - 50% horas extras"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Feriado trabalhado (Corpus Christi)
        registro = RegistroPonto(
            funcionario_id=funcionario.id,
            data=date(2025, 6, 19),
            obra_id=obra.id,
            hora_entrada=datetime.strptime('08:00', '%H:%M').time(),
            hora_saida=datetime.strptime('17:00', '%H:%M').time(),
            hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
            hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
            horas_trabalhadas=8,
            horas_extras=8,
            horas_trabalhadas_calculadas=8,
            total_atraso_minutos=0,
            tipo_registro='feriado_trabalhado',
            percentual_extras=100,
            observacoes="Corpus Christi - 100% horas extras"
        )
        db.session.add(registro)
        registros_criados += 1
    
    print(f"Criados {registros_criados} registros de ponto")

def criar_alimentacao_junho(funcionarios, restaurantes):
    """Cria registros de alimentação"""
    print("\n--- Criando registros de alimentação ---")
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        # 15 dias de alimentação por funcionário
        for dia in range(1, 31, 2):
            data = date(2025, 6, dia)
            if data.weekday() < 5:  # Apenas dias úteis
                restaurante = random.choice(restaurantes)
                
                registro = RegistroAlimentacao(
                    funcionario_id=funcionario.id,
                    restaurante_id=restaurante.id,
                    data=data,
                    valor=random.choice([15.00, 18.50, 22.00, 25.00]),
                    tipo_refeicao='Almoço',
                    observacoes=f"Almoço no {restaurante.nome}"
                )
                db.session.add(registro)
                registros_criados += 1
    
    print(f"Criados {registros_criados} registros de alimentação")

def criar_outros_custos_junho(funcionarios):
    """Cria outros custos"""
    print("\n--- Criando outros custos ---")
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        # Vale transporte
        registro = OutroCusto(
            funcionario_id=funcionario.id,
            data=date(2025, 6, 1),
            tipo='Vale Transporte',
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
            valor=9.00,
            descricao=f"Desconto vale transporte - {funcionario.nome}"
        )
        db.session.add(registro)
        registros_criados += 1
        
        # Outros custos aleatórios
        if random.random() < 0.4:  # 40% chance
            registro = OutroCusto(
                funcionario_id=funcionario.id,
                data=date(2025, 6, random.randint(10, 20)),
                tipo=random.choice(['Adiantamento Salário', 'Uniforme', 'EPI']),
                valor=random.choice([200.00, 300.00, 500.00]),
                descricao=f"Custo adicional - {funcionario.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    print(f"Criados {registros_criados} outros custos")

def criar_custos_veiculos_junho(veiculos, obras):
    """Cria custos de veículos"""
    print("\n--- Criando custos de veículos ---")
    
    registros_criados = 0
    
    for veiculo in veiculos:
        obra = random.choice(obras)
        
        # Combustível (múltiplos abastecimentos)
        for i in range(6):  # 6 abastecimentos no mês
            registro = CustoVeiculo(
                veiculo_id=veiculo.id,
                obra_id=obra.id,
                data_custo=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([250.00, 300.00, 350.00]),
                tipo_custo='combustivel',
                descricao=f"Abastecimento {veiculo.placa}"
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
            descricao=f"Manutenção preventiva {veiculo.placa}"
        )
        db.session.add(registro)
        registros_criados += 1
    
    print(f"Criados {registros_criados} custos de veículos")

def criar_custos_obra_junho(obras):
    """Cria custos de obra"""
    print("\n--- Criando custos de obra ---")
    
    registros_criados = 0
    
    for obra in obras:
        # Materiais
        for i in range(8):  # 8 compras de material
            registro = CustoObra(
                obra_id=obra.id,
                data=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([1500.00, 2000.00, 2500.00, 3000.00]),
                tipo='material',
                descricao=f"Material de construção - {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Equipamentos
        for i in range(3):  # 3 equipamentos
            registro = CustoObra(
                obra_id=obra.id,
                data=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([1000.00, 1500.00, 2000.00]),
                tipo='equipamento',
                descricao=f"Equipamento/Ferramenta - {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Serviços
        for i in range(5):  # 5 serviços
            registro = CustoObra(
                obra_id=obra.id,
                data=date(2025, 6, random.randint(1, 30)),
                valor=random.choice([800.00, 1200.00, 1600.00]),
                tipo='servico',
                descricao=f"Serviço terceirizado - {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    print(f"Criados {registros_criados} custos de obra")

def criar_rdos_junho(obras, funcionarios):
    """Cria RDOs"""
    print("\n--- Criando RDOs ---")
    
    registros_criados = 0
    
    for obra in obras:
        # RDOs em dias úteis (1 a cada 2 dias)
        for dia in range(2, 31, 2):
            data = date(2025, 6, dia)
            if data.weekday() < 5:  # Apenas dias úteis
                funcionario = random.choice(funcionarios)
                
                numero_rdo = f"RDO-{obra.id:03d}-{data.strftime('%Y%m%d')}"
                
                rdo = RDO(
                    numero_rdo=numero_rdo,
                    data_relatorio=data,
                    obra_id=obra.id,
                    criado_por_id=funcionario.id,
                    tempo_manha=random.choice(['Ensolarado', 'Nublado', 'Chuvoso']),
                    tempo_tarde=random.choice(['Ensolarado', 'Nublado', 'Parcialmente nublado']),
                    tempo_noite=random.choice(['Claro', 'Nublado', 'Chuvoso']),
                    observacoes_meteorologicas='Condições meteorológicas normais para o período',
                    comentario_geral=f'Atividades desenvolvidas conforme cronograma na obra {obra.nome}',
                    status='Finalizado'
                )
                db.session.add(rdo)
                registros_criados += 1
    
    print(f"Criados {registros_criados} RDOs")

def main():
    """Função principal"""
    with app.app_context():
        criar_dados_junho_2025()

if __name__ == "__main__":
    main()