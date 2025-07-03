#!/usr/bin/env python3
"""
Script para popular a coluna obra de todos os funcionários e atualizar registros de ponto
com cálculo automático de horas trabalhadas, extras e atrasos.
"""

import random
from datetime import datetime, time, timedelta
from app import app, db
from models import Funcionario, Obra, RegistroPonto, HorarioTrabalho

def calcular_horas_trabalho(hora_entrada, hora_saida, hora_almoco_saida, hora_almoco_retorno, horario_trabalho):
    """
    Calcula horas trabalhadas, extras e atraso baseado no horário de trabalho padrão.
    """
    if not hora_entrada or not hora_saida:
        return 0.0, 0.0, 0.0
    
    # Converter para datetime para facilitar cálculos
    entrada = datetime.combine(datetime.today(), hora_entrada)
    saida = datetime.combine(datetime.today(), hora_saida)
    
    # Se saída for antes da entrada, assumir que passou da meia-noite
    if saida < entrada:
        saida += timedelta(days=1)
    
    # Calcular tempo de almoço
    tempo_almoco = timedelta(hours=1)  # Padrão 1 hora
    if hora_almoco_saida and hora_almoco_retorno:
        almoco_saida = datetime.combine(datetime.today(), hora_almoco_saida)
        almoco_retorno = datetime.combine(datetime.today(), hora_almoco_retorno)
        if almoco_retorno > almoco_saida:
            tempo_almoco = almoco_retorno - almoco_saida
    
    # Tempo total trabalhado
    tempo_total = saida - entrada - tempo_almoco
    horas_trabalhadas = tempo_total.total_seconds() / 3600
    
    # Calcular atraso (baseado no horário padrão de entrada 08:00)
    horario_entrada_padrao = time(8, 0)  # 08:00
    atraso = 0.0
    if hora_entrada > horario_entrada_padrao:
        entrada_padrao = datetime.combine(datetime.today(), horario_entrada_padrao)
        entrada_real = datetime.combine(datetime.today(), hora_entrada)
        atraso_delta = entrada_real - entrada_padrao
        atraso = atraso_delta.total_seconds() / 60  # em minutos
    
    # Calcular horas extras (acima de 8 horas trabalhadas)
    horas_extras = max(0.0, horas_trabalhadas - 8.0)
    
    # Ajustar horas trabalhadas para não contar extras
    horas_trabalhadas_efetivas = min(8.0, horas_trabalhadas)
    
    return horas_trabalhadas_efetivas, horas_extras, atraso

def popular_obras_funcionarios():
    """Popula a coluna obra para todos os funcionários e atualiza cálculos de ponto"""
    
    with app.app_context():
        print("👷 Iniciando população de obras para funcionários...")
        
        # Buscar todas as obras em andamento
        obras = Obra.query.filter_by(status='Em andamento').all()
        if not obras:
            print("❌ Nenhuma obra em andamento encontrada!")
            return
        
        # Buscar todos os funcionários ativos
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        if not funcionarios:
            print("❌ Nenhum funcionário ativo encontrado!")
            return
        
        print(f"📊 Encontrados:")
        print(f"   - {len(funcionarios)} funcionários ativos")
        print(f"   - {len(obras)} obras em andamento")
        
        # Atribuir obras aos funcionários (distribuição equilibrada)
        print("\n🏗️ Atribuindo obras aos funcionários...")
        for i, funcionario in enumerate(funcionarios):
            # Distribuir funcionários entre as obras
            obra_index = i % len(obras)
            obra = obras[obra_index]
            
            # Atualizar todos os registros de ponto deste funcionário
            registros_ponto = RegistroPonto.query.filter_by(funcionario_id=funcionario.id).all()
            
            for registro in registros_ponto:
                # Atribuir obra se não tiver
                if not registro.obra_id:
                    registro.obra_id = obra.id
                
                # Recalcular horas se tem horários
                if registro.hora_entrada and registro.hora_saida:
                    horas_trabalhadas, horas_extras, atraso = calcular_horas_trabalho(
                        registro.hora_entrada,
                        registro.hora_saida,
                        registro.hora_almoco_saida,
                        registro.hora_almoco_retorno,
                        None
                    )
                    
                    registro.horas_trabalhadas = horas_trabalhadas
                    registro.horas_extras = horas_extras
                    registro.atraso = atraso
            
            print(f"   ✓ {funcionario.nome} → {obra.nome} ({len(registros_ponto)} registros de ponto atualizados)")
        
        try:
            db.session.commit()
            print("\n✅ Obras atribuídas e cálculos atualizados com sucesso!")
            
            # Estatísticas finais
            print("\n📈 Estatísticas finais:")
            total_registros = RegistroPonto.query.count()
            com_obra = RegistroPonto.query.filter(RegistroPonto.obra_id.isnot(None)).count()
            com_horas = RegistroPonto.query.filter(RegistroPonto.horas_trabalhadas > 0).count()
            com_extras = RegistroPonto.query.filter(RegistroPonto.horas_extras > 0).count()
            com_atraso = RegistroPonto.query.filter(RegistroPonto.atraso > 0).count()
            
            print(f"   - Total de registros de ponto: {total_registros}")
            print(f"   - Com obra: {com_obra} ({com_obra/total_registros*100:.1f}%)")
            print(f"   - Com horas calculadas: {com_horas} ({com_horas/total_registros*100:.1f}%)")
            print(f"   - Com horas extras: {com_extras} ({com_extras/total_registros*100:.1f}%)")
            print(f"   - Com atraso: {com_atraso} ({com_atraso/total_registros*100:.1f}%)")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao salvar: {e}")

if __name__ == '__main__':
    popular_obras_funcionarios()