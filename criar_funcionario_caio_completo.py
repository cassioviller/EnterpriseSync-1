#!/usr/bin/env python3
"""
Script para criar funcionário Caio Fabio Silva de Azevedo
com horário de trabalho das 7h12 às 17h e popular com todos os tipos de lançamento
"""

from app import app
from datetime import date, datetime, time
import random

def criar_funcionario_caio():
    with app.app_context():
        from models import db, Funcionario, Departamento, Funcao, HorarioTrabalho, RegistroPonto, OutroCusto, RegistroAlimentacao
        
        print("=== CRIANDO FUNCIONÁRIO CAIO FABIO SILVA DE AZEVEDO ===")
        
        # 1. Criar horário de trabalho das 7h12 às 17h
        print("\n1. Criando horário de trabalho personalizado...")
        
        # Verificar se já existe
        horario_existente = HorarioTrabalho.query.filter_by(nome="Turno 7h12-17h").first()
        if horario_existente:
            print("   - Horário já existe, usando existente")
            horario = horario_existente
        else:
            # Calcular horas diárias: 17h - 7h12 - 1h almoço = 8h48min = 8.8h
            horario = HorarioTrabalho(
                nome="Turno 7h12-17h",
                entrada=time(7, 12),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                dias_semana="1,2,3,4,5",  # Segunda a Sexta
                horas_diarias=8.8,  # 8h48min
                valor_hora=15.00  # R$ 15,00/hora
            )
            db.session.add(horario)
            db.session.commit()
            print(f"   - Horário criado: {horario.nome} - {horario.horas_diarias}h diárias")
        
        # 2. Criar funcionário
        print("\n2. Criando funcionário...")
        
        # Verificar se já existe
        funcionario_existente = Funcionario.query.filter_by(cpf="12345678901").first()
        if funcionario_existente:
            print("   - Funcionário já existe, excluindo para recriar...")
            db.session.delete(funcionario_existente)
            db.session.commit()
        
        # Buscar departamento e função
        departamento = Departamento.query.first()
        funcao = Funcao.query.first()
        
        if not departamento:
            departamento = Departamento(nome="Obras", descricao="Setor de Obras")
            db.session.add(departamento)
            db.session.commit()
        
        if not funcao:
            funcao = Funcao(nome="Pedreiro", descricao="Pedreiro", salario_base=2500.00)
            db.session.add(funcao)
            db.session.commit()
        
        # Gerar próximo código
        ultimo_funcionario = Funcionario.query.order_by(Funcionario.id.desc()).first()
        if ultimo_funcionario and ultimo_funcionario.codigo:
            numero = int(ultimo_funcionario.codigo.replace('F', '')) + 1
        else:
            numero = 1
        codigo = f"F{numero:04d}"
        
        funcionario = Funcionario(
            nome="Caio Fabio Silva de Azevedo",
            codigo=codigo,
            cpf="12345678901",
            telefone="(11) 98765-4321",
            email="caio.fabio@estruturasdovale.com.br",
            salario=3500.00,
            departamento_id=departamento.id,
            funcao_id=funcao.id,
            horario_trabalho_id=horario.id,
            ativo=True,
            data_admissao=date(2024, 1, 15)
        )
        db.session.add(funcionario)
        db.session.commit()
        
        print(f"   - Funcionário criado: {funcionario.nome} ({funcionario.codigo})")
        print(f"   - Horário: {horario.nome}")
        print(f"   - Horas diárias: {horario.horas_diarias}h")
        print(f"   - Valor/hora: R$ {horario.valor_hora}")
        
        return funcionario, horario

def popular_mes_completo(funcionario_id):
    """Popular mês completo de junho/2025 com todos os tipos de lançamento"""
    with app.app_context():
        from models import db, RegistroPonto, OutroCusto, RegistroAlimentacao
        
        print(f"\n=== POPULANDO MÊS COMPLETO - JUNHO/2025 ===")
        
        # Limpar registros existentes
        RegistroPonto.query.filter_by(funcionario_id=funcionario_id).delete()
        OutroCusto.query.filter_by(funcionario_id=funcionario_id).delete()
        RegistroAlimentacao.query.filter_by(funcionario_id=funcionario_id).delete()
        db.session.commit()
        
        # Junho 2025 tem 30 dias
        registros_criados = 0
        
        # Definir padrão de lançamentos para todos os dias do mês
        padrao_lancamentos = {
            # Semana 1: 1-7 junho (dom-sab)
            1: {"tipo": "domingo_nao_trabalhado", "obs": "Domingo de folga"},
            2: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            3: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            4: {"tipo": "trabalho_normal", "entrada": "07:25", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00", "atraso": 13},  # 13min atraso
            5: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            6: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "16:45", "almoco_inicio": "12:00", "almoco_fim": "13:00", "saida_antecipada": 15},  # 15min saída antecipada
            7: {"tipo": "sabado_horas_extras", "entrada": "07:12", "saida": "13:00", "horas_extras": 5.8},  # Sábado com extras
            
            # Semana 2: 8-14 junho (dom-sab)
            8: {"tipo": "domingo_nao_trabalhado", "obs": "Domingo de folga"},
            9: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            10: {"tipo": "falta", "obs": "Falta não justificada"},
            11: {"tipo": "falta_justificada", "obs": "Consulta médica"},
            12: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            13: {"tipo": "meio_periodo", "entrada": "07:12", "saida": "12:00", "obs": "Meio período - manhã"},
            14: {"tipo": "sabado_horas_extras", "entrada": "07:12", "saida": "12:00", "horas_extras": 4.8},  # Sábado com extras
            
            # Semana 3: 15-21 junho (dom-sab)
            15: {"tipo": "domingo_horas_extras", "entrada": "08:00", "saida": "14:00", "horas_extras": 6.0},  # Domingo com extras
            16: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            17: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            18: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            19: {"tipo": "feriado_trabalhado", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00", "horas_extras": 8.8, "obs": "Corpus Christi trabalhado"},
            20: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            21: {"tipo": "sabado_nao_trabalhado", "obs": "Sábado de folga"},
            
            # Semana 4: 22-28 junho (dom-sab)
            22: {"tipo": "domingo_nao_trabalhado", "obs": "Domingo de folga"},
            23: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            24: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            25: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            26: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
            27: {"tipo": "trabalho_normal", "entrada": "07:30", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00", "atraso": 18},  # 18min atraso
            28: {"tipo": "sabado_nao_trabalhado", "obs": "Sábado de folga"},
            
            # Semana 5: 29-30 junho (dom-seg)
            29: {"tipo": "domingo_nao_trabalhado", "obs": "Domingo de folga"},
            30: {"tipo": "trabalho_normal", "entrada": "07:12", "saida": "17:00", "almoco_inicio": "12:00", "almoco_fim": "13:00"},
        }
        
        # Criar registros de ponto
        for dia in range(1, 31):  # 30 dias
            data_registro = date(2025, 6, dia)
            config = padrao_lancamentos[dia]
            
            # Pular domingos e sábados não trabalhados
            if config["tipo"] in ["domingo_nao_trabalhado", "sabado_nao_trabalhado"]:
                continue
            
            # Criar registro de ponto
            if config["tipo"] == "falta":
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    data=data_registro,
                    tipo_registro=config["tipo"],
                    observacoes=config.get("obs", ""),
                    horas_trabalhadas=0.0,
                    horas_extras=0.0,
                    total_atraso_horas=0.0,
                    total_atraso_minutos=0
                )
            elif config["tipo"] == "falta_justificada":
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    data=data_registro,
                    tipo_registro=config["tipo"],
                    observacoes=config.get("obs", ""),
                    horas_trabalhadas=0.0,
                    horas_extras=0.0,
                    total_atraso_horas=0.0,
                    total_atraso_minutos=0
                )
            elif config["tipo"] == "meio_periodo":
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    data=data_registro,
                    tipo_registro=config["tipo"],
                    hora_entrada=datetime.strptime(config["entrada"], "%H:%M").time(),
                    hora_saida=datetime.strptime(config["saida"], "%H:%M").time(),
                    observacoes=config.get("obs", ""),
                    horas_trabalhadas=4.8,  # Meio período
                    horas_extras=0.0,
                    total_atraso_horas=config.get("atraso", 0) / 60.0,
                    total_atraso_minutos=config.get("atraso", 0)
                )
            elif config["tipo"] in ["sabado_horas_extras", "domingo_horas_extras", "feriado_trabalhado"]:
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    data=data_registro,
                    tipo_registro=config["tipo"],
                    hora_entrada=datetime.strptime(config["entrada"], "%H:%M").time(),
                    hora_saida=datetime.strptime(config["saida"], "%H:%M").time(),
                    hora_almoco_saida=datetime.strptime(config.get("almoco_inicio", "12:00"), "%H:%M").time() if config.get("almoco_inicio") else None,
                    hora_almoco_retorno=datetime.strptime(config.get("almoco_fim", "13:00"), "%H:%M").time() if config.get("almoco_fim") else None,
                    observacoes=config.get("obs", ""),
                    horas_trabalhadas=config.get("horas_extras", 8.8),
                    horas_extras=config.get("horas_extras", 0.0),
                    total_atraso_horas=config.get("atraso", 0) / 60.0,
                    total_atraso_minutos=config.get("atraso", 0)
                )
            else:  # trabalho_normal
                atraso_min = config.get("atraso", 0) + config.get("saida_antecipada", 0)
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    data=data_registro,
                    tipo_registro=config["tipo"],
                    hora_entrada=datetime.strptime(config["entrada"], "%H:%M").time(),
                    hora_saida=datetime.strptime(config["saida"], "%H:%M").time(),
                    hora_almoco_saida=datetime.strptime(config.get("almoco_inicio", "12:00"), "%H:%M").time() if config.get("almoco_inicio") else None,
                    hora_almoco_retorno=datetime.strptime(config.get("almoco_fim", "13:00"), "%H:%M").time() if config.get("almoco_fim") else None,
                    observacoes=config.get("obs", ""),
                    horas_trabalhadas=8.8 - (atraso_min / 60.0),  # Descontar atrasos
                    horas_extras=0.0,
                    total_atraso_horas=atraso_min / 60.0,
                    total_atraso_minutos=atraso_min
                )
            
            db.session.add(registro)
            registros_criados += 1
        
        db.session.commit()
        print(f"   - Registros de ponto criados: {registros_criados}")
        
        # Criar registros de outros custos
        outros_custos = [
            {"data": date(2025, 6, 1), "tipo": "Vale Transporte", "categoria": "adicional", "valor": 200.00, "descricao": "Vale transporte mensal"},
            {"data": date(2025, 6, 1), "tipo": "Desconto VT 6%", "categoria": "desconto", "valor": -12.00, "descricao": "Desconto vale transporte"},
            {"data": date(2025, 6, 15), "tipo": "Vale Alimentação", "categoria": "adicional", "valor": 450.00, "descricao": "Vale alimentação mensal"},
            {"data": date(2025, 6, 20), "tipo": "EPI - Capacete", "categoria": "adicional", "valor": 25.00, "descricao": "Equipamento de proteção"},
            {"data": date(2025, 6, 25), "tipo": "Uniforme", "categoria": "adicional", "valor": 80.00, "descricao": "Uniforme de trabalho"},
        ]
        
        for custo in outros_custos:
            registro = OutroCusto(
                funcionario_id=funcionario_id,
                data=custo["data"],
                tipo=custo["tipo"],
                categoria=custo["categoria"],
                valor=custo["valor"],
                descricao=custo["descricao"]
            )
            db.session.add(registro)
        
        db.session.commit()
        print(f"   - Outros custos criados: {len(outros_custos)}")
        
        # Criar registros de alimentação
        registros_alimentacao = [
            {"data": date(2025, 6, 2), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 3), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 4), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 5), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 6), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 9), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 12), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 16), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 17), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 18), "tipo": "Lanche", "valor": 12.00},
            {"data": date(2025, 6, 19), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 20), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 23), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 24), "tipo": "Almoço", "valor": 18.50},
            {"data": date(2025, 6, 25), "tipo": "Almoço", "valor": 18.50},
        ]
        
        for alim in registros_alimentacao:
            registro = RegistroAlimentacao(
                funcionario_id=funcionario_id,
                data=alim["data"],
                tipo_refeicao=alim["tipo"],
                valor=alim["valor"],
                descricao=f'{alim["tipo"]} - R$ {alim["valor"]}'
            )
            db.session.add(registro)
        
        db.session.commit()
        print(f"   - Registros de alimentação criados: {len(registros_alimentacao)}")
        
        print(f"\n=== RESUMO DO MÊS POPULADO ===")
        print(f"   - Registros de ponto: {registros_criados}")
        print(f"   - Outros custos: {len(outros_custos)}")
        print(f"   - Registros de alimentação: {len(registros_alimentacao)}")
        
        return registros_criados

if __name__ == "__main__":
    # Criar funcionário
    funcionario, horario = criar_funcionario_caio()
    
    # Popular mês completo
    registros_criados = popular_mes_completo(funcionario.id)
    
    print(f"\n=== PROCESSO CONCLUÍDO ===")
    print(f"Funcionário: {funcionario.nome} ({funcionario.codigo})")
    print(f"Horário: {horario.nome}")
    print(f"Registros criados: {registros_criados}")
    print(f"ID do funcionário: {funcionario.id}")