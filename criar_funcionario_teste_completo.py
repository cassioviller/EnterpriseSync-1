#!/usr/bin/env python3
"""
Script para criar funcionário de teste com mês completo de registros de ponto
Inclui todos os tipos de lançamentos para validar KPIs
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import (Usuario, TipoUsuario, Funcionario, Departamento, Funcao, 
                   HorarioTrabalho, RegistroPonto, TipoRegistro, Obra)
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash
import calendar

def criar_funcionario_teste():
    """Criar funcionário de teste completo"""
    with app.app_context():
        print("🔧 Criando funcionário de teste...")
        
        # Verificar se já existe
        funcionario_teste = Funcionario.query.filter_by(
            cpf='123.456.789-00'
        ).first()
        
        if funcionario_teste:
            print(f"✅ Funcionário teste já existe: {funcionario_teste.nome}")
            return funcionario_teste
        
        # Buscar departamento e função existentes ou criar
        departamento = Departamento.query.filter_by(nome='Operacional').first()
        if not departamento:
            departamento = Departamento(nome='Operacional', descricao='Departamento Operacional')
            db.session.add(departamento)
        
        funcao = Funcao.query.filter_by(nome='Soldador').first()
        if not funcao:
            funcao = Funcao(nome='Soldador', descricao='Soldador Especializado')
            db.session.add(funcao)
        
        # Buscar horário padrão ou criar
        horario = HorarioTrabalho.query.filter_by(nome='Comercial').first()
        if not horario:
            horario = HorarioTrabalho(
                nome='Comercial',
                entrada_manha='08:00',
                saida_almoco='12:00', 
                entrada_tarde='13:00',
                saida_tarde='18:00',
                carga_horaria_diaria=8.0,
                dias_trabalho='Segunda a Sexta'
            )
            db.session.add(horario)
        
        # Criar funcionário
        funcionario_teste = Funcionario(
            nome='Carlos Alberto da Silva',
            cpf='123.456.789-00',
            email='carlos.teste@sige.com',
            telefone='(31) 99999-9999',
            endereco='Rua Teste, 123 - Bairro Teste - Cidade Teste/MG',
            data_nascimento=date(1985, 3, 15),
            data_admissao=date(2024, 1, 1),
            salario=4500.00,
            departamento_id=departamento.id,
            funcao_id=funcao.id,
            horario_trabalho_id=horario.id,
            admin_id=4,  # Mesmo admin dos outros funcionários
            ativo=True
        )
        
        db.session.add(funcionario_teste)
        db.session.commit()
        
        print(f"✅ Funcionário criado: {funcionario_teste.nome} (ID: {funcionario_teste.id})")
        return funcionario_teste

def obter_obra_teste():
    """Obter ou criar obra para os registros"""
    obra = Obra.query.filter_by(admin_id=4, status='Em andamento').first()
    if not obra:
        obra = Obra(
            nome='Galpão Industrial Teste',
            descricao='Obra para testes de registro de ponto',
            status='Em andamento',
            data_inicio=date(2024, 1, 1),
            admin_id=4
        )
        db.session.add(obra)
        db.session.commit()
    
    return obra

def criar_registros_mes_completo(funcionario, obra, ano=2024, mes=7):
    """Criar registros de ponto para um mês completo"""
    with app.app_context():
        print(f"📅 Criando registros para {mes:02d}/{ano}...")
        
        # Limpar registros existentes do período
        data_inicio = date(ano, mes, 1)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_fim = date(ano, mes, ultimo_dia)
        
        RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).delete()
        
        # Feriados de julho 2024 (exemplo)
        feriados = [
            date(2024, 7, 9),   # Revolução Constitucionalista (SP)
        ]
        
        registros_criados = 0
        
        for dia in range(1, ultimo_dia + 1):
            data_registro = date(ano, mes, dia)
            dia_semana = data_registro.weekday()  # 0=segunda, 6=domingo
            
            # Determinar tipo do dia
            is_feriado = data_registro in feriados
            is_sabado = dia_semana == 5
            is_domingo = dia_semana == 6
            is_dia_util = dia_semana < 5  # Segunda a sexta
            
            # Cenários de registro
            if is_domingo:
                if dia % 4 == 0:  # Alguns domingos trabalhados
                    # Domingo trabalhado - pagamento em dobro
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        hora_entrada='08:00',
                        hora_saida='17:00',
                        horas_trabalhadas=8.0,
                        horas_extras=8.0,  # Domingo = tudo hora extra
                        tipo_registro=TipoRegistro.PONTO_NORMAL,
                        observacoes='Domingo trabalhado - hora extra 100%'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                else:
                    # Domingo folga - não criar registro
                    pass
                    
            elif is_sabado:
                if dia % 3 == 0:  # Alguns sábados trabalhados
                    # Sábado trabalhado - hora extra 50%
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        hora_entrada='08:00',
                        hora_saida='12:00',
                        horas_trabalhadas=4.0,
                        horas_extras=4.0,  # Sábado = hora extra 50%
                        tipo_registro=TipoRegistro.PONTO_NORMAL,
                        observacoes='Sábado trabalhado - hora extra 50%'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                else:
                    # Sábado folga - não criar registro
                    pass
                    
            elif is_feriado:
                if dia == 9:  # Trabalhou no feriado
                    # Feriado trabalhado - hora extra 100%
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        hora_entrada='08:00',
                        hora_saida='17:00',
                        horas_trabalhadas=8.0,
                        horas_extras=8.0,  # Feriado = tudo hora extra
                        tipo_registro=TipoRegistro.PONTO_NORMAL,
                        observacoes='Feriado trabalhado - hora extra 100%'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                else:
                    # Feriado não trabalhado
                    pass
                    
            elif is_dia_util:
                # Dias úteis - variações
                if dia == 5:  # Falta injustificada
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        tipo_registro=TipoRegistro.FALTA,
                        observacoes='Falta injustificada'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                    
                elif dia == 12:  # Falta justificada
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        tipo_registro=TipoRegistro.FALTA_JUSTIFICADA,
                        observacoes='Consulta médica'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                    
                elif dia == 15:  # Atraso
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        hora_entrada='08:30',  # 30 min de atraso
                        hora_saida='18:00',
                        horas_trabalhadas=7.5,
                        tipo_registro=TipoRegistro.ATRASO,
                        observacoes='Atraso de 30 minutos'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                    
                elif dia in [3, 10, 17, 24, 31]:  # Dias com hora extra
                    # Dia normal com 2 horas extras
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        hora_entrada='08:00',
                        hora_saida='20:00',  # 2h a mais
                        horas_trabalhadas=8.0,
                        horas_extras=2.0,
                        tipo_registro=TipoRegistro.PONTO_NORMAL,
                        observacoes='Hora extra para conclusão de atividades'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                    
                else:  # Dia normal
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_registro,
                        hora_entrada='08:00',
                        hora_saida='18:00',
                        horas_trabalhadas=8.0,
                        horas_extras=0.0,
                        tipo_registro=TipoRegistro.PONTO_NORMAL,
                        observacoes='Dia normal de trabalho'
                    )
                    db.session.add(registro)
                    registros_criados += 1
        
        db.session.commit()
        print(f"✅ {registros_criados} registros criados para {funcionario.nome}")
        
        return registros_criados

def main():
    """Função principal"""
    print("🚀 Iniciando criação de funcionário teste com registros completos...")
    
    try:
        # Criar funcionário
        funcionario = criar_funcionario_teste()
        
        # Obter obra
        obra = obter_obra_teste()
        
        # Criar registros para julho/2024
        registros = criar_registros_mes_completo(funcionario, obra, 2024, 7)
        
        print("\n📊 RESUMO DA CRIAÇÃO:")
        print(f"   Funcionário: {funcionario.nome}")
        print(f"   CPF: {funcionario.cpf}")
        print(f"   Salário: R$ {funcionario.salario:,.2f}")
        print(f"   Registros criados: {registros}")
        print(f"   Período: 01/07/2024 a 31/07/2024")
        print("\n✅ Funcionário de teste criado com sucesso!")
        print("   Acesse /funcionarios para ver os KPIs atualizados")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()