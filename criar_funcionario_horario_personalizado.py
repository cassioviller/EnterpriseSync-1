#!/usr/bin/env python3
"""
CRIAR FUNCIONÁRIO COM HORÁRIO PERSONALIZADO (9h-16h)
E popular com diversos tipos de registros de ponto
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioTrabalho, Obra, Usuario
from werkzeug.security import generate_password_hash
from datetime import date, time, datetime, timedelta
import random

def criar_funcionario_horario_personalizado():
    """Cria funcionário com horário 9h-16h e popula com registros variados"""
    
    with app.app_context():
        print("👤 CRIANDO FUNCIONÁRIO COM HORÁRIO PERSONALIZADO")
        print("=" * 60)
        
        # Buscar um admin existente
        admin = Usuario.query.first()
        if not admin:
            print("❌ Nenhum admin encontrado no sistema!")
            return
        
        print(f"👨‍💼 Admin encontrado: {admin.nome} (ID: {admin.id})")
        
        # Verificar se já existe
        funcionario_existente = Funcionario.query.filter_by(nome="Carlos Silva Teste").first()
        if funcionario_existente:
            print(f"ℹ️  Funcionário já existe (ID: {funcionario_existente.id}), removendo registros antigos...")
            # Remover registros de ponto antigos
            RegistroPonto.query.filter_by(funcionario_id=funcionario_existente.id).delete()
            funcionario = funcionario_existente
        else:
            # Criar novo funcionário
            funcionario = Funcionario(
                codigo="F9999",  # Código único
                nome="Carlos Silva Teste",
                cpf="12345678910",
                salario=5500.00,
                data_admissao=date(2024, 1, 15),
                ativo=True,
                admin_id=admin.id
            )
            db.session.add(funcionario)
            db.session.flush()  # Para obter o ID
            print(f"✅ Funcionário criado: {funcionario.nome} (ID: {funcionario.id})")
        
        # Criar horário de trabalho personalizado (9h-16h)
        horario_existente = HorarioTrabalho.query.filter_by(nome="Horário 9h-16h Teste").first()
        if horario_existente:
            print(f"🕘 Horário de trabalho já existe: {horario_existente.nome}")
            funcionario.horario_trabalho_id = horario_existente.id
        else:
            # Criar novo horário baseado na estrutura real
            horario = HorarioTrabalho(
                nome="Horário 9h-16h Teste",
                entrada=time(9, 0),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(16, 0),
                dias_semana="1,2,3,4,5",  # Segunda a sexta
                horas_diarias=7.0,  # 7 horas líquidas
                valor_hora=15.0
            )
            db.session.add(horario)
            db.session.flush()  # Para obter o ID
            funcionario.horario_trabalho_id = horario.id
            print("🕘 Horário de trabalho criado: 09:00-16:00 (seg-sex)")
        
        # Buscar uma obra para associar os registros
        obra = Obra.query.filter_by(ativo=True).first()
        if not obra:
            print("⚠️  Nenhuma obra ativa encontrada, criando obra teste...")
            obra = Obra(
                nome="Obra Teste - Sistema",
                endereco="Rua Teste, 123",
                status="em_andamento",
                data_inicio=date(2025, 1, 1),
                admin_id=1,
                ativo=True
            )
            db.session.add(obra)
            db.session.flush()
        
        print(f"🏗️  Registros serão associados à obra: {obra.nome}")
        
        # Dados para registros variados (últimas 2 semanas)
        data_inicial = date(2025, 7, 20)
        registros_criados = 0
        
        # Lista de cenários para testar
        cenarios = [
            # Dias normais com variações
            {"entrada": time(9, 0), "saida": time(16, 0), "tipo": "trabalho_normal", "desc": "Horário exato"},
            {"entrada": time(8, 45), "saida": time(16, 0), "tipo": "trabalho_normal", "desc": "15min antes"},
            {"entrada": time(9, 15), "saida": time(16, 0), "tipo": "trabalho_normal", "desc": "15min atraso"},
            {"entrada": time(9, 0), "saida": time(16, 30), "tipo": "trabalho_normal", "desc": "30min extras"},
            {"entrada": time(8, 50), "saida": time(16, 45), "tipo": "trabalho_normal", "desc": "10min antes + 45min extras"},
            
            # Cenários com atrasos significativos
            {"entrada": time(9, 30), "saida": time(16, 0), "tipo": "trabalho_normal", "desc": "30min atraso"},
            {"entrada": time(10, 0), "saida": time(16, 0), "tipo": "trabalho_normal", "desc": "1h atraso"},
            {"entrada": time(9, 45), "saida": time(15, 30), "tipo": "trabalho_normal", "desc": "45min atraso + 30min saída antes"},
            
            # Cenários com horas extras
            {"entrada": time(9, 0), "saida": time(17, 0), "tipo": "trabalho_normal", "desc": "1h extras"},
            {"entrada": time(8, 30), "saida": time(17, 30), "tipo": "trabalho_normal", "desc": "30min antes + 1h30 extras"},
            {"entrada": time(9, 0), "saida": time(18, 0), "tipo": "trabalho_normal", "desc": "2h extras"},
            
            # Tipos especiais
            {"entrada": time(9, 0), "saida": time(15, 0), "tipo": "sabado_trabalhado", "desc": "Sábado - 6h trabalhadas"},
            {"entrada": time(10, 0), "saida": time(14, 0), "tipo": "domingo_trabalhado", "desc": "Domingo - 4h trabalhadas"},
            {"entrada": time(9, 0), "saida": time(13, 0), "tipo": "feriado_trabalhado", "desc": "Feriado - 4h trabalhadas"},
            
            # Faltas e folgas
            {"entrada": None, "saida": None, "tipo": "falta", "desc": "Falta não justificada"},
            {"entrada": None, "saida": None, "tipo": "folga", "desc": "Folga programada"},
            {"entrada": None, "saida": None, "tipo": "ferias", "desc": "Dia de férias"},
            
            # Casos mistos
            {"entrada": time(8, 40), "saida": time(15, 45), "tipo": "trabalho_normal", "desc": "20min antes + 15min saída antes"},
            {"entrada": time(9, 20), "saida": time(16, 40), "tipo": "trabalho_normal", "desc": "20min atraso + 40min extras"},
        ]
        
        # Criar registros para os últimos 20 dias úteis
        for i in range(20):
            data_registro = data_inicial + timedelta(days=i)
            
            # Pular fins de semana para alguns tipos
            if data_registro.weekday() >= 5:  # Sábado (5) ou Domingo (6)
                # Apenas alguns registros em fins de semana
                if i % 7 != 0:  # Só criar registro no fim de semana ocasionalmente
                    continue
                cenario = random.choice([c for c in cenarios if c["tipo"] in ["sabado_trabalhado", "domingo_trabalhado", "folga"]])
            else:
                # Dias úteis - usar qualquer cenário
                cenario = cenarios[i % len(cenarios)]
            
            # Calcular horas trabalhadas
            horas_trabalhadas = 0
            if cenario["entrada"] and cenario["saida"]:
                entrada_min = cenario["entrada"].hour * 60 + cenario["entrada"].minute
                saida_min = cenario["saida"].hour * 60 + cenario["saida"].minute
                total_min = saida_min - entrada_min - 60  # Menos 1h almoço
                horas_trabalhadas = round(max(0, total_min / 60.0), 2)
            
            # Criar registro
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                obra_id=obra.id,
                data=data_registro,
                hora_entrada=cenario["entrada"],
                hora_saida=cenario["saida"],
                tipo_registro=cenario["tipo"],
                horas_trabalhadas=horas_trabalhadas,
                observacoes=f"Teste: {cenario['desc']}"
            )
            
            db.session.add(registro)
            registros_criados += 1
            
            print(f"📅 {data_registro.strftime('%d/%m')} - {cenario['desc']} ({cenario['tipo']})")
        
        # Commit das alterações
        try:
            db.session.commit()
            print(f"\n✅ FUNCIONÁRIO E REGISTROS CRIADOS COM SUCESSO!")
            print(f"   👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
            print(f"   🕘 Horário: 09:00-16:00 (7h/dia com 1h almoço)")  
            print(f"   📊 Registros criados: {registros_criados}")
            print(f"   🏗️  Obra associada: {obra.nome}")
            
            # Agora aplicar correção de horas extras usando o horário personalizado
            print(f"\n🔧 APLICANDO CORREÇÃO DE HORAS EXTRAS (HORÁRIO 9h-16h)...")
            aplicar_correcao_horario_personalizado(funcionario.id)
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")
            raise

def aplicar_correcao_horario_personalizado(funcionario_id):
    """Aplica correção específica para horário 9h-16h"""
    
    # Horário padrão personalizado: 09:00 - 16:00
    padrao_entrada_min = 9 * 60      # 540 min (09:00)
    padrao_saida_min = 16 * 60       # 960 min (16:00)
    
    # Buscar registros do funcionário
    registros = RegistroPonto.query.filter_by(funcionario_id=funcionario_id).all()
    
    registros_corrigidos = 0
    
    for registro in registros:
        if not registro.hora_entrada or not registro.hora_saida:
            # Tipos sem horário (falta, folga, etc.)
            registro.horas_extras = 0
            registro.total_atraso_horas = 0
            registro.percentual_extras = 0
            continue
            
        # Calcular com base no horário personalizado
        real_entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
        real_saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
        
        if registro.tipo_registro in ['sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
            # Tipos especiais: todas as horas são extras
            registro.horas_extras = registro.horas_trabalhadas or 0
            registro.total_atraso_horas = 0
            registro.percentual_extras = 100.0 if registro.tipo_registro != 'sabado_trabalhado' else 50.0
        else:
            # Tipos normais: calcular extras e atrasos independentemente
            
            # ATRASOS (chegou depois OU saiu antes do horário padrão)
            atraso_entrada = max(0, real_entrada_min - padrao_entrada_min)
            atraso_saida = max(0, padrao_saida_min - real_saida_min)
            total_atraso_min = atraso_entrada + atraso_saida
            
            # EXTRAS (chegou antes OU saiu depois do horário padrão)
            extra_entrada = max(0, padrao_entrada_min - real_entrada_min)
            extra_saida = max(0, real_saida_min - padrao_saida_min)
            total_extra_min = extra_entrada + extra_saida
            
            # Aplicar valores
            registro.total_atraso_horas = round(total_atraso_min / 60.0, 2)
            registro.horas_extras = round(total_extra_min / 60.0, 2)
            registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
            
        registros_corrigidos += 1
    
    db.session.commit()
    print(f"   ✅ {registros_corrigidos} registros corrigidos com horário 09:00-16:00")
    
    # Mostrar alguns exemplos
    print(f"\n📊 EXEMPLOS DE CÁLCULOS (Base: 09:00-16:00):")
    exemplos = RegistroPonto.query.filter_by(funcionario_id=funcionario_id).limit(5).all()
    
    for reg in exemplos:
        if reg.hora_entrada and reg.hora_saida:
            print(f"   📅 {reg.data.strftime('%d/%m')} {reg.hora_entrada}-{reg.hora_saida}: "
                  f"{reg.horas_extras}h extras, {reg.total_atraso_horas or 0}h atrasos")

if __name__ == "__main__":
    criar_funcionario_horario_personalizado()