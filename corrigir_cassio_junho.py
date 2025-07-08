"""
Script para corrigir os registros do Cássio em junho de 2025
- Feriado trabalhado com 100% de horas extras
- Atrasos contabilizados corretamente nos KPIs
"""

from app import app, db
from models import Funcionario, RegistroPonto, Obra
from datetime import datetime, date, time

def corrigir_cassio_junho():
    """Corrige os registros do Cássio para junho de 2025"""
    
    with app.app_context():
        # Buscar Cássio
        cassio = Funcionario.query.filter_by(nome='Cássio Viller Silva de Azevedo').first()
        if not cassio:
            print("Cássio não encontrado!")
            return
            
        print(f"Cássio encontrado: ID {cassio.id}")
        
        # Buscar uma obra para associar
        obra = Obra.query.first()
        if not obra:
            print("Nenhuma obra encontrada!")
            return
            
        # Remover registros existentes do Cássio em junho
        registros_existentes = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == cassio.id,
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).all()
        
        for registro in registros_existentes:
            db.session.delete(registro)
        db.session.commit()
        
        print(f"Removidos {len(registros_existentes)} registros existentes")
        
        # Criar registros corretos para junho de 2025
        registros = [
            # Junho 2025 - Registros com atrasos e feriado trabalhado
            {
                'data': date(2025, 6, 7),
                'tipo_registro': 'feriado_trabalhado',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'horas_extras': 8.0,  # 100% das horas são extras em feriado
                'percentual_extras': 100.0,
                'observacoes': 'Feriado trabalhado - Corpus Christi'
            },
            {
                'data': date(2025, 6, 9),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 30),  # 30 min de atraso
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 7.5,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'minutos_atraso_entrada': 30,
                'total_atraso_minutos': 30,
                'total_atraso_horas': 0.5,
                'observacoes': 'Atraso na entrada - 30 minutos'
            },
            {
                'data': date(2025, 6, 10),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 15),  # 15 min de atraso
                'saida': time(16, 45),  # 15 min saída antecipada
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 7.5,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'minutos_atraso_entrada': 15,
                'minutos_atraso_saida': 15,
                'total_atraso_minutos': 30,
                'total_atraso_horas': 0.5,
                'saida_antecipada': True,
                'observacoes': 'Atraso entrada (15min) + saída antecipada (15min)'
            },
            {
                'data': date(2025, 6, 11),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Trabalho normal'
            },
            {
                'data': date(2025, 6, 12),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Trabalho normal'
            },
            {
                'data': date(2025, 6, 13),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 0),
                'saida': time(16, 0),
                'almoco_inicio': None,  # Sem almoço
                'almoco_fim': None,
                'horas_trabalhadas': 8.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Trabalho sem intervalo de almoço'
            },
            {
                'data': date(2025, 6, 14),
                'tipo_registro': 'sabado_horas_extras',
                'entrada': time(8, 0),
                'saida': time(12, 0),
                'almoco_inicio': None,
                'almoco_fim': None,
                'horas_trabalhadas': 4.0,
                'horas_extras': 4.0,
                'percentual_extras': 50.0,
                'observacoes': 'Sábado - 4h extras a 50%'
            },
            {
                'data': date(2025, 6, 15),
                'tipo_registro': 'domingo_horas_extras',
                'entrada': time(8, 0),
                'saida': time(12, 0),
                'almoco_inicio': None,
                'almoco_fim': None,
                'horas_trabalhadas': 4.0,
                'horas_extras': 4.0,
                'percentual_extras': 100.0,
                'observacoes': 'Domingo - 4h extras a 100%'
            },
            {
                'data': date(2025, 6, 16),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Trabalho normal'
            },
            {
                'data': date(2025, 6, 17),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Trabalho normal'
            },
            {
                'data': date(2025, 6, 18),
                'tipo_registro': 'trabalho_normal',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Trabalho normal'
            },
            {
                'data': date(2025, 6, 20),
                'tipo_registro': 'falta',
                'entrada': None,
                'saida': None,
                'almoco_inicio': None,
                'almoco_fim': None,
                'horas_trabalhadas': 0.0,
                'horas_extras': 0.0,
                'percentual_extras': 0.0,
                'observacoes': 'Falta não justificada'
            },
            {
                'data': date(2025, 6, 21),
                'tipo_registro': 'sabado_horas_extras',
                'entrada': time(8, 0),
                'saida': time(12, 0),
                'almoco_inicio': None,
                'almoco_fim': None,
                'horas_trabalhadas': 4.0,
                'horas_extras': 4.0,
                'percentual_extras': 50.0,
                'observacoes': 'Sábado - 4h extras a 50%'
            }
        ]
        
        # Criar registros
        for reg_data in registros:
            registro = RegistroPonto(
                funcionario_id=cassio.id,
                obra_id=obra.id,
                data=reg_data['data'],
                hora_entrada=reg_data['entrada'],
                hora_saida=reg_data['saida'],
                hora_almoco_saida=reg_data['almoco_inicio'],
                hora_almoco_retorno=reg_data['almoco_fim'],
                horas_trabalhadas=reg_data['horas_trabalhadas'],
                horas_extras=reg_data['horas_extras'],
                percentual_extras=reg_data['percentual_extras'],
                tipo_registro=reg_data['tipo_registro'],
                observacoes=reg_data['observacoes'],
                minutos_atraso_entrada=reg_data.get('minutos_atraso_entrada', 0),
                minutos_atraso_saida=reg_data.get('minutos_atraso_saida', 0),
                total_atraso_minutos=reg_data.get('total_atraso_minutos', 0),
                total_atraso_horas=reg_data.get('total_atraso_horas', 0.0),
                saida_antecipada=reg_data.get('saida_antecipada', False),
                meio_periodo=reg_data.get('meio_periodo', False)
            )
            db.session.add(registro)
        
        db.session.commit()
        print(f"Criados {len(registros)} novos registros para Cássio em junho/2025")
        
        # Verificar registros criados
        registros_criados = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == cassio.id,
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).order_by(RegistroPonto.data).all()
        
        print("\nRegistros criados:")
        for reg in registros_criados:
            print(f"  {reg.data} - {reg.tipo_registro} - {reg.horas_trabalhadas}h - {reg.horas_extras}h extras ({reg.percentual_extras}%) - Atraso: {reg.total_atraso_minutos}min")

if __name__ == "__main__":
    corrigir_cassio_junho()