#!/usr/bin/env python3
"""
Script para limpar todos os lançamentos do mês 6 (junho 2025) 
e recriar dados completos para testar todas as funcionalidades
"""

from app import app, db
from datetime import date, datetime, timedelta
from models import *
import random

def limpar_mes_6():
    """Remove todos os lançamentos do mês 6 (junho 2025)"""
    print("=== LIMPANDO LANÇAMENTOS DO MÊS 6 (JUNHO 2025) ===")
    
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Limpar registros de ponto
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    for registro in registros_ponto:
        db.session.delete(registro)
    print(f"Removidos {len(registros_ponto)} registros de ponto")
    
    # Limpar registros de alimentação
    registros_alimentacao = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).all()
    for registro in registros_alimentacao:
        db.session.delete(registro)
    print(f"Removidos {len(registros_alimentacao)} registros de alimentação")
    
    # Limpar outros custos
    outros_custos = OutroCusto.query.filter(
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).all()
    for custo in outros_custos:
        db.session.delete(custo)
    print(f"Removidos {len(outros_custos)} outros custos")
    
    # Limpar custos de veículos
    custos_veiculos = CustoVeiculo.query.filter(
        CustoVeiculo.data_custo >= data_inicio,
        CustoVeiculo.data_custo <= data_fim
    ).all()
    for custo in custos_veiculos:
        db.session.delete(custo)
    print(f"Removidos {len(custos_veiculos)} custos de veículos")
    
    # Limpar custos de obra
    custos_obra = CustoObra.query.filter(
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    ).all()
    for custo in custos_obra:
        db.session.delete(custo)
    print(f"Removidos {len(custos_obra)} custos de obra")
    
    # Limpar RDOs
    rdos = RDO.query.filter(
        RDO.data_relatorio >= data_inicio,
        RDO.data_relatorio <= data_fim
    ).all()
    for rdo in rdos:
        db.session.delete(rdo)
    print(f"Removidos {len(rdos)} RDOs")
    
    # Limpar ocorrências
    ocorrencias = Ocorrencia.query.filter(
        Ocorrencia.data_inicio >= data_inicio,
        Ocorrencia.data_inicio <= data_fim
    ).all()
    for ocorrencia in ocorrencias:
        db.session.delete(ocorrencia)
    print(f"Removidas {len(ocorrencias)} ocorrências")
    
    db.session.commit()
    print("✅ Limpeza concluída!")

def criar_dados_completos_mes_6():
    """Cria dados completos para o mês 6 (junho 2025)"""
    print("\n=== CRIANDO DADOS COMPLETOS PARA JUNHO 2025 ===")
    
    # Buscar funcionários ativos
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    print(f"Funcionários encontrados: {len(funcionarios)}")
    
    # Buscar obras e veículos
    obras = Obra.query.filter_by(status='Em andamento').all()
    veiculos = Veiculo.query.all()
    restaurantes = Restaurante.query.all()
    
    print(f"Obras ativas: {len(obras)}")
    print(f"Veículos: {len(veiculos)}")
    print(f"Restaurantes: {len(restaurantes)}")
    
    # Criar registros de ponto completos
    criar_registros_ponto_completos(funcionarios, obras)
    
    # Criar registros de alimentação
    criar_registros_alimentacao_completos(funcionarios, restaurantes)
    
    # Criar outros custos
    criar_outros_custos_completos(funcionarios)
    
    # Criar custos de veículos
    criar_custos_veiculos_completos(veiculos, obras)
    
    # Criar custos de obra
    criar_custos_obra_completos(obras)
    
    # Criar RDOs
    criar_rdos_completos(obras, funcionarios)
    
    # Criar ocorrências
    criar_ocorrencias_completas(funcionarios)
    
    db.session.commit()
    print("✅ Dados completos criados para junho 2025!")

def criar_registros_ponto_completos(funcionarios, obras):
    """Cria registros de ponto diversos para junho"""
    print("\n--- Criando registros de ponto ---")
    
    # Dias úteis de junho 2025 (excluindo feriados)
    dias_uteis = []
    for dia in range(1, 31):
        data = date(2025, 6, dia)
        if data.weekday() < 5:  # Segunda a sexta
            dias_uteis.append(data)
    
    # Remover Corpus Christi (19/06)
    corpus_christi = date(2025, 6, 19)
    if corpus_christi in dias_uteis:
        dias_uteis.remove(corpus_christi)
    
    tipos_registro = [
        'trabalho_normal',
        'falta',
        'falta_justificada',
        'feriado_trabalhado',
        'sabado_horas_extras',
        'domingo_horas_extras',
        'meio_periodo'
    ]
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        obra = random.choice(obras)
        
        # Criar registros para cada dia útil (com algumas variações)
        for data in dias_uteis:
            # 20% chance de falta
            if random.random() < 0.2:
                tipo = random.choice(['falta', 'falta_justificada'])
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data,
                    obra_id=obra.id,
                    tipo_registro=tipo,
                    observacoes=f"Falta {'justificada' if tipo == 'falta_justificada' else 'não justificada'}"
                )
                db.session.add(registro)
                registros_criados += 1
                continue
            
            # Horário normal com pequenas variações
            entrada = datetime.combine(data, datetime.strptime('08:00', '%H:%M').time())
            saida = datetime.combine(data, datetime.strptime('17:00', '%H:%M').time())
            almoco_saida = datetime.combine(data, datetime.strptime('12:00', '%H:%M').time())
            almoco_retorno = datetime.combine(data, datetime.strptime('13:00', '%H:%M').time())
            
            # Adicionar variações (atrasos, saídas antecipadas)
            if random.random() < 0.3:  # 30% chance de atraso
                atraso_minutos = random.randint(5, 60)
                entrada += timedelta(minutes=atraso_minutos)
            
            if random.random() < 0.2:  # 20% chance de saída antecipada
                saida_antecipada = random.randint(15, 120)
                saida -= timedelta(minutes=saida_antecipada)
            
            # Calcular horas trabalhadas
            tempo_total = saida - entrada
            tempo_almoco = almoco_retorno - almoco_saida
            horas_trabalhadas = (tempo_total - tempo_almoco).total_seconds() / 3600
            
            # Horas extras (acima de 8h)
            horas_extras = max(0, horas_trabalhadas - 8)
            
            # Calcular atrasos
            atraso_entrada = max(0, (entrada - datetime.combine(data, datetime.strptime('08:00', '%H:%M').time())).total_seconds() / 60)
            saida_antecipada_min = max(0, (datetime.combine(data, datetime.strptime('17:00', '%H:%M').time()) - saida).total_seconds() / 60)
            total_atraso = atraso_entrada + saida_antecipada_min
            
            # Percentual de horas extras
            percentual_extras = 50 if data.weekday() == 5 else 100 if data.weekday() == 6 else 0
            
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                data=data,
                obra_id=obra.id,
                hora_entrada=entrada.time(),
                hora_saida=saida.time(),
                hora_almoco_saida=almoco_saida.time(),
                hora_almoco_retorno=almoco_retorno.time(),
                horas_trabalhadas=horas_trabalhadas,
                horas_extras=horas_extras,
                horas_trabalhadas_calculadas=horas_trabalhadas,
                total_atraso_minutos=total_atraso,
                tipo_registro='trabalho_normal',
                percentual_extras=percentual_extras,
                observacoes=f"Trabalho normal - {horas_trabalhadas:.1f}h"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Adicionar alguns registros especiais (sábados e domingos)
        sabados = [date(2025, 6, 7), date(2025, 6, 14), date(2025, 6, 21), date(2025, 6, 28)]
        domingos = [date(2025, 6, 1), date(2025, 6, 8), date(2025, 6, 15), date(2025, 6, 22), date(2025, 6, 29)]
        
        # Alguns sábados trabalhados
        for sabado in sabados[:2]:  # Apenas 2 sábados
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
        
        # Alguns domingos trabalhados
        for domingo in domingos[:1]:  # Apenas 1 domingo
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                data=domingo,
                obra_id=obra.id,
                hora_entrada=datetime.strptime('08:00', '%H:%M').time(),
                hora_saida=datetime.strptime('12:00', '%H:%M').time(),
                horas_trabalhadas=4,
                horas_extras=4,
                horas_trabalhadas_calculadas=4,
                total_atraso_minutos=0,
                tipo_registro='domingo_horas_extras',
                percentual_extras=100,
                observacoes="Domingo - 100% horas extras"
            )
            db.session.add(registro)
            registros_criados += 1
        
        # Feriado trabalhado (Corpus Christi)
        registro = RegistroPonto(
            funcionario_id=funcionario.id,
            data=corpus_christi,
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

def criar_registros_alimentacao_completos(funcionarios, restaurantes):
    """Cria registros de alimentação para junho"""
    print("\n--- Criando registros de alimentação ---")
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        # Criar registros para dias aleatórios do mês
        for dia in range(1, 31, 2):  # Dias alternados
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

def criar_outros_custos_completos(funcionarios):
    """Cria outros custos para junho"""
    print("\n--- Criando outros custos ---")
    
    registros_criados = 0
    tipos_custos = [
        'Vale Transporte',
        'Vale Alimentação',
        'Desconto VT 6%',
        'Desconto INSS',
        'Adiantamento Salário',
        'Uniforme',
        'EPI - Equipamento'
    ]
    
    for funcionario in funcionarios:
        # Criar 2-4 outros custos por funcionário
        num_custos = random.randint(2, 4)
        
        for i in range(num_custos):
            data = date(2025, 6, random.randint(1, 30))
            tipo = random.choice(tipos_custos)
            
            # Valores baseados no tipo
            if 'Vale' in tipo:
                valor = random.choice([120.00, 150.00, 180.00])
            elif 'Desconto' in tipo:
                valor = random.choice([50.00, 75.00, 100.00])
            elif 'Adiantamento' in tipo:
                valor = random.choice([500.00, 800.00, 1000.00])
            else:
                valor = random.choice([80.00, 120.00, 200.00])
            
            registro = OutroCusto(
                funcionario_id=funcionario.id,
                data=data,
                tipo=tipo,
                valor=valor,
                descricao=f"{tipo} - {funcionario.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    print(f"Criados {registros_criados} outros custos")

def criar_custos_veiculos_completos(veiculos, obras):
    """Cria custos de veículos para junho"""
    print("\n--- Criando custos de veículos ---")
    
    registros_criados = 0
    tipos_custos = ['combustivel', 'manutencao', 'seguro', 'outros']
    
    for veiculo in veiculos:
        obra = random.choice(obras)
        
        # Criar 5-10 custos por veículo
        num_custos = random.randint(5, 10)
        
        for i in range(num_custos):
            data = date(2025, 6, random.randint(1, 30))
            tipo = random.choice(tipos_custos)
            
            # Valores baseados no tipo
            if tipo == 'combustivel':
                valor = random.choice([200.00, 250.00, 300.00, 350.00])
            elif tipo == 'manutencao':
                valor = random.choice([500.00, 800.00, 1200.00, 1500.00])
            elif tipo == 'seguro':
                valor = random.choice([400.00, 600.00, 800.00])
            else:
                valor = random.choice([100.00, 200.00, 300.00])
            
            registro = CustoVeiculo(
                veiculo_id=veiculo.id,
                obra_id=obra.id,
                data_custo=data,
                valor=valor,
                tipo_custo=tipo,
                descricao=f"{tipo.title()} - {veiculo.placa}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    print(f"Criados {registros_criados} custos de veículos")

def criar_custos_obra_completos(obras):
    """Cria custos de obra para junho"""
    print("\n--- Criando custos de obra ---")
    
    registros_criados = 0
    tipos_custos = ['material', 'equipamento', 'servico', 'outros']
    
    for obra in obras:
        # Criar 8-15 custos por obra
        num_custos = random.randint(8, 15)
        
        for i in range(num_custos):
            data = date(2025, 6, random.randint(1, 30))
            tipo = random.choice(tipos_custos)
            
            # Valores baseados no tipo
            if tipo == 'material':
                valor = random.choice([1000.00, 1500.00, 2000.00, 2500.00])
            elif tipo == 'equipamento':
                valor = random.choice([800.00, 1200.00, 1800.00, 2200.00])
            elif tipo == 'servico':
                valor = random.choice([500.00, 800.00, 1200.00, 1600.00])
            else:
                valor = random.choice([200.00, 400.00, 600.00, 800.00])
            
            registro = CustoObra(
                obra_id=obra.id,
                data=data,
                valor=valor,
                tipo=tipo,
                descricao=f"{tipo.title()} para {obra.nome}"
            )
            db.session.add(registro)
            registros_criados += 1
    
    print(f"Criados {registros_criados} custos de obra")

def criar_rdos_completos(obras, funcionarios):
    """Cria RDOs para junho"""
    print("\n--- Criando RDOs ---")
    
    registros_criados = 0
    
    for obra in obras:
        # Criar RDOs para dias úteis
        for dia in range(1, 31, 3):  # A cada 3 dias
            data = date(2025, 6, dia)
            if data.weekday() < 5:  # Apenas dias úteis
                funcionario = random.choice(funcionarios)
                
                numero_rdo = f"RDO-{obra.id:03d}-{data.strftime('%Y%m%d')}"
                
                rdo = RDO(
                    numero_rdo=numero_rdo,
                    data_relatorio=data,
                    obra_id=obra.id,
                    criado_por_id=funcionario.id,
                    tempo_manha='Ensolarado',
                    tempo_tarde='Parcialmente nublado',
                    tempo_noite='Claro',
                    observacoes_meteorologicas='Dia favorável para trabalho',
                    comentario_geral=f'Atividades desenvolvidas normalmente na obra {obra.nome}',
                    status='Finalizado'
                )
                db.session.add(rdo)
                registros_criados += 1
    
    print(f"Criados {registros_criados} RDOs")

def criar_ocorrencias_completas(funcionarios):
    """Cria ocorrências para junho"""
    print("\n--- Criando ocorrências ---")
    
    registros_criados = 0
    
    # Buscar tipos de ocorrência
    tipos = TipoOcorrencia.query.all()
    if not tipos:
        print("Nenhum tipo de ocorrência encontrado")
        return
    
    for funcionario in funcionarios:
        # 30% chance de ter uma ocorrência
        if random.random() < 0.3:
            tipo = random.choice(tipos)
            data_inicio = date(2025, 6, random.randint(1, 25))
            data_fim = data_inicio + timedelta(days=random.randint(1, 5))
            
            ocorrencia = Ocorrencia(
                funcionario_id=funcionario.id,
                tipo_ocorrencia_id=tipo.id,
                data_inicio=data_inicio,
                data_fim=data_fim,
                status='Aprovado',
                descricao=f"Ocorrência de {tipo.nome} para {funcionario.nome}"
            )
            db.session.add(ocorrencia)
            registros_criados += 1
    
    print(f"Criadas {registros_criados} ocorrências")

def main():
    """Função principal"""
    with app.app_context():
        print("LIMPEZA E RECRIAÇÃO DE DADOS - JUNHO 2025")
        print("=" * 50)
        
        # Limpar dados existentes
        limpar_mes_6()
        
        # Criar novos dados completos
        criar_dados_completos_mes_6()
        
        print("\n" + "=" * 50)
        print("✅ PROCESSO CONCLUÍDO!")
        print("Dados completos criados para junho 2025")
        print("Agora você pode testar todas as funcionalidades do sistema")

if __name__ == "__main__":
    main()