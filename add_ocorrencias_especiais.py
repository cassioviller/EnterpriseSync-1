#!/usr/bin/env python3
from datetime import datetime, date, time, timedelta
from app import app, db
from models import Funcionario, RegistroPonto, RegistroAlimentacao
import random

def adicionar_ocorrencias_especiais():
    """Adicionar algumas ocorrências especiais para tornar os dados mais realistas"""
    
    with app.app_context():
        # Adicionar algumas situações especiais
        
        # 1. João Silva Santos (excelente) - trabalhou em feriado e fins de semana
        print("Adicionando trabalho em fim de semana para João Silva Santos...")
        
        # Trabalhou no sábado 07/06 para entrega urgente
        registro_sabado = RegistroPonto(
            funcionario_id=96,  # João Silva Santos
            data=date(2025, 6, 7),  # Sábado
            hora_entrada=time(9, 0),
            hora_saida=time(15, 0),
            observacoes="Trabalho voluntário - Entrega urgente projeto cliente ABC"
        )
        db.session.add(registro_sabado)
        
        # Alimentação no sábado
        almoco_sabado = RegistroAlimentacao(
            funcionario_id=96,
            data=date(2025, 6, 7),
            tipo='almoco',
            valor=28.50,
            observacoes='Almoço - Trabalho em fim de semana'
        )
        db.session.add(almoco_sabado)
        
        # 2. Maria Oliveira Costa (bom) - saída antecipada por emergência médica
        print("Adicionando saída antecipada para Maria Oliveira Costa...")
        
        # Substituir um registro existente
        registro_emergencia = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == 97,
            RegistroPonto.data == date(2025, 6, 12)
        ).first()
        
        if registro_emergencia:
            registro_emergencia.hora_saida = time(14, 30)
            registro_emergencia.observacoes = "Saída antecipada - Emergência familiar autorizada pela chefia"
        
        # 3. Carlos Pereira Lima (regular) - chegada muito atrasada
        print("Adicionando atraso significativo para Carlos Pereira Lima...")
        
        registro_atraso = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == 98,
            RegistroPonto.data == date(2025, 6, 18)
        ).first()
        
        if registro_atraso:
            registro_atraso.hora_entrada = time(10, 45)
            registro_atraso.observacoes = "Atraso de 2h45min - Problema no transporte público"
        
        # 4. Ana Santos Rodrigues (ruim) - falta consecutiva sem justificativa
        print("Adicionando faltas consecutivas para Ana Santos Rodrigues...")
        
        # Falta segunda-feira sem justificativa
        falta_segunda = RegistroPonto(
            funcionario_id=99,  # Ana Santos Rodrigues
            data=date(2025, 6, 16),  # Segunda
            observacoes="Falta sem justificativa - Não compareceu nem comunicou"
        )
        db.session.add(falta_segunda)
        
        # Falta terça-feira sem justificativa
        falta_terca = RegistroPonto(
            funcionario_id=99,
            data=date(2025, 6, 17),  # Terça
            observacoes="Falta sem justificativa - 2º dia consecutivo"
        )
        db.session.add(falta_terca)
        
        # 5. Pedro Lima Sousa (péssimo) - padrão de saídas antecipadas não autorizadas
        print("Adicionando saídas antecipadas não autorizadas para Pedro Lima Sousa...")
        
        # Várias saídas antecipadas
        datas_saidas_antecipadas = [
            date(2025, 6, 10),
            date(2025, 6, 13),
            date(2025, 6, 19),
            date(2025, 6, 24)
        ]
        
        for data_saida in datas_saidas_antecipadas:
            registro = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == 100,
                RegistroPonto.data == data_saida
            ).first()
            
            if registro and registro.hora_entrada:  # Se não for falta
                registro.hora_saida = time(15, 30)  # Saída 1h30 antes
                registro.observacoes = "Saída antecipada não autorizada"
        
        # 6. Adicionar algumas refeições diferenciadas
        print("Adicionando registros de alimentação especiais...")
        
        # João (excelente) - jantou trabalhando até tarde
        jantar_extra = RegistroAlimentacao(
            funcionario_id=96,
            data=date(2025, 6, 25),
            tipo='jantar',
            valor=32.00,
            observacoes='Jantar - Trabalho até 18h46 (horas extras)'
        )
        db.session.add(jantar_extra)
        
        # Maria (bom) - almoço especial aniversário empresa
        almoco_aniversario = RegistroAlimentacao(
            funcionario_id=97,
            data=date(2025, 6, 15),
            tipo='almoco',
            valor=45.00,
            observacoes='Almoço especial - Aniversário da empresa'
        )
        db.session.add(almoco_aniversario)
        
        # 7. Adicionar alguns registros de horas extras justificadas
        print("Adicionando horas extras específicas...")
        
        # João - projeto urgente
        for data in [date(2025, 6, 23), date(2025, 6, 24), date(2025, 6, 25)]:
            registro = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == 96,
                RegistroPonto.data == data
            ).first()
            
            if registro:
                # Já tem horas extras, vamos adicionar observação
                if registro.hora_saida > time(17, 30):
                    registro.observacoes = "Horas extras - Projeto urgente Cliente ABC - Autorizado pela diretoria"
        
        # Maria - fechamento mensal
        registro_fechamento = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == 97,
            RegistroPonto.data == date(2025, 6, 30)
        ).first()
        
        if registro_fechamento:
            registro_fechamento.hora_saida = time(19, 15)
            registro_fechamento.observacoes = "Horas extras - Fechamento mensal do departamento"
        
        # Jantar para Maria no fechamento
        jantar_fechamento = RegistroAlimentacao(
            funcionario_id=97,
            data=date(2025, 6, 30),
            tipo='jantar',
            valor=28.00,
            observacoes='Jantar - Fechamento mensal (horas extras)'
        )
        db.session.add(jantar_fechamento)
        
        # Commit todas as alterações
        db.session.commit()
        print("Ocorrências especiais adicionadas com sucesso!")
        
        # Estatísticas finais
        print("\n=== RESUMO DOS PERFIS ===")
        
        funcionarios = [
            {'id': 96, 'nome': 'João Silva Santos', 'perfil': 'excelente'},
            {'id': 97, 'nome': 'Maria Oliveira Costa', 'perfil': 'bom'},
            {'id': 98, 'nome': 'Carlos Pereira Lima', 'perfil': 'regular'},
            {'id': 99, 'nome': 'Ana Santos Rodrigues', 'perfil': 'ruim'},
            {'id': 100, 'nome': 'Pedro Lima Sousa', 'perfil': 'pessimo'}
        ]
        
        for func in funcionarios:
            registros = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func['id'],
                RegistroPonto.data >= date(2025, 6, 1),
                RegistroPonto.data <= date(2025, 6, 30)
            ).all()
            
            faltas = sum(1 for r in registros if r.hora_entrada is None)
            atrasos = sum(1 for r in registros if r.hora_entrada and r.hora_entrada > time(8, 5))
            horas_extras = sum(1 for r in registros if r.hora_saida and r.hora_saida > time(17, 30))
            
            alimentacao = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.funcionario_id == func['id'],
                RegistroAlimentacao.data >= date(2025, 6, 1),
                RegistroAlimentacao.data <= date(2025, 6, 30)
            ).count()
            
            print(f"\n{func['nome']} ({func['perfil'].upper()}):")
            print(f"  - Total de registros: {len(registros)}")
            print(f"  - Faltas: {faltas}")
            print(f"  - Atrasos (>5min): {atrasos}")
            print(f"  - Dias com horas extras: {horas_extras}")
            print(f"  - Registros de alimentação: {alimentacao}")

if __name__ == "__main__":
    adicionar_ocorrencias_especiais()