#!/usr/bin/env python3
"""
Script para gerar lançamentos de ponto para um funcionário em julho 2025
"""

from datetime import date, datetime, timedelta
import calendar
from models import db, RegistroPonto, Funcionario
from app import app

def gerar_lancamentos_julho_funcionario(funcionario_id, ano=2025, mes=7):
    """Gerar lançamentos de ponto para todos os dias de julho 2025"""
    
    with app.app_context():
        # Verificar se funcionário existe
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            print(f"❌ Funcionário ID {funcionario_id} não encontrado")
            return False
        
        print(f"✅ Gerando lançamentos para: {funcionario.nome}")
        
        # Limpar registros existentes do funcionário em julho 2025
        registros_existentes = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= date(ano, mes, 1),
            RegistroPonto.data <= date(ano, mes, 31)
        ).delete()
        
        print(f"🗑️ Removidos {registros_existentes} registros existentes")
        
        # Obter todos os dias do mês
        primeiro_dia, ultimo_dia = calendar.monthrange(ano, mes)
        
        registros_criados = 0
        
        for dia in range(1, ultimo_dia + 1):
            data_atual = date(ano, mes, dia)
            dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
            
            # Segunda a sexta: trabalho normal (Horário Vale Verde: 7h12 às 17h)
            if dia_semana < 5:  # Segunda a sexta
                tipo_registro = 'trabalho_normal'
                hora_entrada = '07:12'
                hora_almoco_saida = '12:00'
                hora_almoco_retorno = '13:00'
                hora_saida = '17:00'
                horas_trabalhadas = 8.8  # 7h12 às 17h com 1h almoço = 8h48min
                horas_extras = 0.0
                
                # Adicionar algumas variações realistas
                if dia % 7 == 0:  # A cada 7 dias, adicionar horas extras
                    hora_saida = '19:00'
                    horas_trabalhadas = 10.8  # 7h12 às 19h com 1h almoço = 10h48min
                    horas_extras = 2.0
                
                if dia % 10 == 0:  # A cada 10 dias, pequeno atraso
                    hora_entrada = '07:30'
                    total_atraso_minutos = 18  # 18 minutos de atraso
                    total_atraso_horas = 0.3
                else:
                    total_atraso_minutos = 0
                    total_atraso_horas = 0.0
                
            elif dia_semana == 5:  # Sábado
                if dia % 2 == 0:  # Trabalha sábados alternados
                    tipo_registro = 'sabado_trabalhado'
                    hora_entrada = '07:12'
                    hora_almoco_saida = None
                    hora_almoco_retorno = None
                    hora_saida = '12:00'
                    horas_trabalhadas = 4.8
                    horas_extras = 4.8  # Sábado é 100% extra
                    total_atraso_minutos = 0
                    total_atraso_horas = 0.0
                else:
                    tipo_registro = 'sabado_folga'
                    hora_entrada = None
                    hora_almoco_saida = None
                    hora_almoco_retorno = None
                    hora_saida = None
                    horas_trabalhadas = 0.0
                    horas_extras = 0.0
                    total_atraso_minutos = 0
                    total_atraso_horas = 0.0
                    
            else:  # Domingo
                tipo_registro = 'domingo_folga'
                hora_entrada = None
                hora_almoco_saida = None
                hora_almoco_retorno = None
                hora_saida = None
                horas_trabalhadas = 0.0
                horas_extras = 0.0
                total_atraso_minutos = 0
                total_atraso_horas = 0.0
            
            # Adicionar algumas faltas realistas
            if dia in [15, 25]:  # 2 faltas no mês
                tipo_registro = 'falta'
                hora_entrada = None
                hora_almoco_saida = None
                hora_almoco_retorno = None
                hora_saida = None
                horas_trabalhadas = 0.0
                horas_extras = 0.0
                total_atraso_minutos = 0
                total_atraso_horas = 0.0
            
            # Criar registro de ponto
            registro = RegistroPonto(
                funcionario_id=funcionario_id,
                data=data_atual,
                tipo_registro=tipo_registro,
                hora_entrada=hora_entrada,
                hora_almoco_saida=hora_almoco_saida,
                hora_almoco_retorno=hora_almoco_retorno,
                hora_saida=hora_saida,
                horas_trabalhadas=horas_trabalhadas,
                horas_extras=horas_extras,
                total_atraso_minutos=total_atraso_minutos,
                total_atraso_horas=total_atraso_horas,
                observacoes=f"Gerado automaticamente para {data_atual.strftime('%d/%m/%Y')}"
            )
            
            db.session.add(registro)
            registros_criados += 1
        
        # Salvar no banco
        db.session.commit()
        
        print(f"✅ Criados {registros_criados} registros para {funcionario.nome} em julho/2025")
        
        # Mostrar resumo
        resumo = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= date(ano, mes, 1),
            RegistroPonto.data <= date(ano, mes, 31)
        ).count()
        
        print(f"📊 Total de registros criados: {resumo}")
        return True

if __name__ == '__main__':
    # Será chamado com o ID do funcionário criado
    pass