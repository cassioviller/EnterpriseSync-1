#!/usr/bin/env python3
"""
Script para popular dados básicos de funcionários e obras para junho 2025
"""

from app import app, db
from datetime import date, datetime, timedelta
from models import Funcionario, Obra, RegistroPonto, RegistroAlimentacao, OutroCusto, Restaurante
import random

def popular_registros_ponto():
    """Popula registros de ponto para funcionários ativos"""
    print("=== Populando registros de ponto ===")
    
    funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()  # Apenas 3 funcionários
    obras = Obra.query.filter_by(status='Em andamento').all()
    
    if not funcionarios or not obras:
        print("Erro: Funcionários ou obras não encontrados")
        return
    
    # Dias úteis de junho (sem feriados)
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
            # 90% presença, 10% falta
            if random.random() < 0.9:
                # Trabalho normal
                entrada = datetime.combine(data, datetime.strptime('08:00', '%H:%M').time())
                saida = datetime.combine(data, datetime.strptime('17:00', '%H:%M').time())
                
                # Pequenos atrasos ocasionais
                if random.random() < 0.3:
                    entrada += timedelta(minutes=random.randint(10, 30))
                
                atraso_minutos = max(0, (entrada - datetime.combine(data, datetime.strptime('08:00', '%H:%M').time())).total_seconds() / 60)
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data,
                    obra_id=obra.id,
                    hora_entrada=entrada.time(),
                    hora_saida=saida.time(),
                    hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
                    hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
                    horas_trabalhadas=8.0,
                    horas_extras=0.0,
                    horas_trabalhadas_calculadas=8.0,
                    total_atraso_minutos=atraso_minutos,
                    tipo_registro='trabalho_normal',
                    observacoes='Trabalho normal'
                )
                db.session.add(registro)
                registros_criados += 1
            else:
                # Falta
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data,
                    obra_id=obra.id,
                    tipo_registro='falta',
                    observacoes='Falta não justificada'
                )
                db.session.add(registro)
                registros_criados += 1
    
    # Feriado trabalhado (Corpus Christi - 19/06)
    for funcionario in funcionarios:
        obra = random.choice(obras)
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
    
    db.session.commit()
    print(f"Criados {registros_criados} registros de ponto")

def popular_alimentacao():
    """Popula registros de alimentação"""
    print("=== Populando registros de alimentação ===")
    
    funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()
    restaurantes = Restaurante.query.all()
    
    if not restaurantes:
        print("Erro: Nenhum restaurante encontrado")
        return
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        # Alimentação em dias alternados
        for dia in range(2, 31, 2):
            data = date(2025, 6, dia)
            if data.weekday() < 5:  # Apenas dias úteis
                restaurante = random.choice(restaurantes)
                
                registro = RegistroAlimentacao(
                    funcionario_id=funcionario.id,
                    restaurante_id=restaurante.id,
                    data=data,
                    valor=random.choice([18.00, 22.00, 25.00]),
                    tipo_refeicao='Almoço',
                    observacoes=f"Almoço no {restaurante.nome}"
                )
                db.session.add(registro)
                registros_criados += 1
    
    db.session.commit()
    print(f"Criados {registros_criados} registros de alimentação")

def popular_outros_custos():
    """Popula outros custos"""
    print("=== Populando outros custos ===")
    
    funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()
    
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
    
    db.session.commit()
    print(f"Criados {registros_criados} outros custos")

def main():
    """Função principal"""
    with app.app_context():
        print("POPULANDO DADOS BÁSICOS - JUNHO 2025")
        print("=" * 40)
        
        popular_registros_ponto()
        popular_alimentacao()
        popular_outros_custos()
        
        print("\n✅ Dados básicos criados!")

if __name__ == "__main__":
    main()