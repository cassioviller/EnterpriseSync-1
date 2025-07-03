#!/usr/bin/env python3
from datetime import datetime, date, time, timedelta
from app import app, db
from models import Funcionario, RegistroPonto, RegistroAlimentacao
import random

def criar_registros_junho_2025():
    """Criar registros de ponto e alimentação para junho de 2025 com perfis diferenciados"""
    
    with app.app_context():
        # Limpar registros existentes de junho 2025
        print("Limpando registros existentes...")
        RegistroPonto.query.filter(
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).delete()
        
        RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 6, 1),
            RegistroAlimentacao.data <= date(2025, 6, 30)
        ).delete()
        
        db.session.commit()
        
        # Funcionários com IDs específicos e perfis
        funcionarios = [
            {'id': 96, 'nome': 'João Silva Santos', 'perfil': 'excelente'},
            {'id': 97, 'nome': 'Maria Oliveira Costa', 'perfil': 'bom'},
            {'id': 98, 'nome': 'Carlos Pereira Lima', 'perfil': 'regular'},
            {'id': 99, 'nome': 'Ana Santos Rodrigues', 'perfil': 'ruim'},
            {'id': 100, 'nome': 'Pedro Lima Sousa', 'perfil': 'pessimo'}
        ]
        
        # Horário comercial: 08:00-12:00, 13:00-17:00
        horario_entrada = time(8, 0)  # 08:00
        horario_saida_almoco = time(12, 0)  # 12:00
        horario_retorno_almoco = time(13, 0)  # 13:00
        horario_saida = time(17, 0)  # 17:00
        
        # Gerar dados para cada funcionário
        for func in funcionarios:
            print(f"Gerando dados para {func['nome']} - Perfil: {func['perfil']}")
            
            # Junho 2025 - dias úteis (segunda a sexta)
            data_atual = date(2025, 6, 2)  # Segunda-feira
            
            while data_atual <= date(2025, 6, 30):
                # Pular fins de semana
                if data_atual.weekday() < 5:  # 0-4 = segunda a sexta
                    
                    # Definir comportamento baseado no perfil
                    if func['perfil'] == 'excelente':
                        # Sempre pontual, raramente falta, faz horas extras
                        chance_falta = 0.02  # 2%
                        chance_atraso = 0.05  # 5%
                        chance_horas_extras = 0.30  # 30%
                        atraso_maximo = 5  # minutos
                        
                    elif func['perfil'] == 'bom':
                        # Geralmente pontual, poucas faltas
                        chance_falta = 0.05  # 5%
                        chance_atraso = 0.15  # 15%
                        chance_horas_extras = 0.15  # 15%
                        atraso_maximo = 15  # minutos
                        
                    elif func['perfil'] == 'regular':
                        # Algumas faltas e atrasos moderados
                        chance_falta = 0.10  # 10%
                        chance_atraso = 0.25  # 25%
                        chance_horas_extras = 0.05  # 5%
                        atraso_maximo = 30  # minutos
                        
                    elif func['perfil'] == 'ruim':
                        # Faltas e atrasos frequentes
                        chance_falta = 0.20  # 20%
                        chance_atraso = 0.40  # 40%
                        chance_horas_extras = 0.02  # 2%
                        atraso_maximo = 60  # minutos
                        
                    else:  # pessimo
                        # Muito problemático
                        chance_falta = 0.35  # 35%
                        chance_atraso = 0.60  # 60%
                        chance_horas_extras = 0.00  # 0%
                        atraso_maximo = 120  # minutos
                    
                    # Verificar se vai faltar
                    if random.random() < chance_falta:
                        # Criar registro de falta
                        tem_justificativa = random.random() < 0.6  # 60% das faltas são justificadas
                        
                        justificativas = [
                            "Consulta médica",
                            "Problema familiar",
                            "Atestado médico",
                            "Emergência pessoal",
                            "Problema de transporte"
                        ]
                        
                        observacao = ""
                        if tem_justificativa:
                            observacao = f"Falta justificada: {random.choice(justificativas)}"
                        else:
                            observacao = "Falta sem justificativa"
                        
                        registro = RegistroPonto(
                            funcionario_id=func['id'],
                            data=data_atual,
                            observacoes=observacao
                        )
                        db.session.add(registro)
                        
                    else:
                        # Funcionário veio trabalhar
                        entrada_real = horario_entrada
                        saida_almoco_real = horario_saida_almoco
                        retorno_almoco_real = horario_retorno_almoco
                        saida_real = horario_saida
                        
                        # Aplicar atraso na entrada
                        if random.random() < chance_atraso:
                            atraso_minutos = random.randint(1, atraso_maximo)
                            entrada_real = (datetime.combine(date.today(), horario_entrada) + 
                                          timedelta(minutes=atraso_minutos)).time()
                        
                        # Aplicar horas extras
                        if random.random() < chance_horas_extras:
                            horas_extras_minutos = random.randint(30, 120)  # 30min a 2h
                            saida_real = (datetime.combine(date.today(), horario_saida) + 
                                        timedelta(minutes=horas_extras_minutos)).time()
                        
                        # Variações pequenas no horário de almoço
                        if random.random() < 0.3:  # 30% das vezes varia o almoço
                            variacao_almoco = random.randint(-15, 15)  # ±15 minutos
                            saida_almoco_real = (datetime.combine(date.today(), horario_saida_almoco) + 
                                               timedelta(minutes=variacao_almoco)).time()
                            retorno_almoco_real = (datetime.combine(date.today(), horario_retorno_almoco) + 
                                                 timedelta(minutes=variacao_almoco)).time()
                        
                        registro = RegistroPonto(
                            funcionario_id=func['id'],
                            data=data_atual,
                            hora_entrada=entrada_real,
                            hora_saida=saida_real,
                            hora_almoco_saida=saida_almoco_real,
                            hora_almoco_retorno=retorno_almoco_real,
                            observacoes=""
                        )
                        db.session.add(registro)
                        
                        # Criar registros de alimentação para dias trabalhados
                        if random.random() < 0.8:  # 80% das vezes almoça
                            valor_almoco = random.uniform(15.0, 25.0)  # R$ 15-25
                            
                            alimentacao = RegistroAlimentacao(
                                funcionario_id=func['id'],
                                data=data_atual,
                                tipo='almoco',
                                valor=valor_almoco,
                                observacoes='Almoço no refeitório'
                            )
                            db.session.add(alimentacao)
                        
                        # Às vezes café da manhã
                        if random.random() < 0.3:  # 30% das vezes toma café
                            valor_cafe = random.uniform(5.0, 10.0)  # R$ 5-10
                            
                            alimentacao = RegistroAlimentacao(
                                funcionario_id=func['id'],
                                data=data_atual,
                                tipo='cafe',
                                valor=valor_cafe,
                                observacoes='Café da manhã'
                            )
                            db.session.add(alimentacao)
                
                data_atual += timedelta(days=1)
        
        # Commit todas as alterações
        db.session.commit()
        print("Registros de junho 2025 criados com sucesso!")
        
        # Estatísticas
        total_registros_ponto = RegistroPonto.query.filter(
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).count()
        
        total_registros_alimentacao = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 6, 1),
            RegistroAlimentacao.data <= date(2025, 6, 30)
        ).count()
        
        print(f"Total de registros de ponto criados: {total_registros_ponto}")
        print(f"Total de registros de alimentação criados: {total_registros_alimentacao}")
        
        # Estatísticas por funcionário
        for func in funcionarios:
            registros_func = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func['id'],
                RegistroPonto.data >= date(2025, 6, 1),
                RegistroPonto.data <= date(2025, 6, 30)
            ).count()
            
            faltas = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func['id'],
                RegistroPonto.data >= date(2025, 6, 1),
                RegistroPonto.data <= date(2025, 6, 30),
                RegistroPonto.hora_entrada == None
            ).count()
            
            print(f"{func['nome']} ({func['perfil']}): {registros_func} registros, {faltas} faltas")

if __name__ == "__main__":
    criar_registros_junho_2025()