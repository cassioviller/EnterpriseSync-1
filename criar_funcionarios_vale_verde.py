#!/usr/bin/env python3
"""
CRIAR FUNCIONÁRIOS VALE VERDE E REGISTROS DE FOLGA
Cria funcionários específicos da Vale Verde e seus registros
"""

from app import app, db
from models import *
from datetime import date, datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def criar_funcionarios_vale_verde():
    """Cria funcionários específicos da construtora Vale Verde"""
    
    print("CRIANDO FUNCIONÁRIOS VALE VERDE")
    print("=" * 50)
    
    # Buscar obra Vale Verde
    obra_vale_verde = Obra.query.filter(Obra.nome.contains('Vale Verde')).first()
    
    if not obra_vale_verde:
        print("❌ Obra Vale Verde não encontrada. Criando...")
        # Criar obra Vale Verde
        obra_vale_verde = Obra(
            nome='Residencial Vale Verde',
            endereco='Rua das Flores, 123 - Vale Verde',
            data_inicio=date(2025, 5, 1),
            data_previsao_fim=date(2025, 12, 31),
            orcamento=2500000.0,
            status='Em andamento'
        )
        db.session.add(obra_vale_verde)
        db.session.commit()
        print(f"✅ Obra criada: {obra_vale_verde.nome}")
    
    # Buscar horário de trabalho de obra
    horario_obra = HorarioTrabalho.query.filter_by(nome='Obra').first()
    
    if not horario_obra:
        print("❌ Horário 'Obra' não encontrado. Criando...")
        horario_obra = HorarioTrabalho(
            nome='Obra',
            entrada=datetime.strptime('07:00', '%H:%M').time(),
            saida_almoco=datetime.strptime('12:00', '%H:%M').time(),
            retorno_almoco=datetime.strptime('13:00', '%H:%M').time(),
            saida=datetime.strptime('16:00', '%H:%M').time(),
            dias_semana='1,2,3,4,5',  # Segunda a sexta
            horas_diarias=8.0,
            valor_hora=25.0
        )
        db.session.add(horario_obra)
        db.session.commit()
        print(f"✅ Horário criado: {horario_obra.nome}")
    
    # Funcionários para criar
    funcionarios_vale_verde = [
        {
            'nome': 'Carlos Silva Vale Verde',
            'cpf': '111.222.333-44',
            'salario': 3500.0,
            'data_admissao': date(2025, 5, 1)
        },
        {
            'nome': 'Maria Santos Vale Verde', 
            'cpf': '222.333.444-55',
            'salario': 3200.0,
            'data_admissao': date(2025, 5, 15)
        },
        {
            'nome': 'João Oliveira Vale Verde',
            'cpf': '333.444.555-66', 
            'salario': 2800.0,
            'data_admissao': date(2025, 6, 1)
        },
        {
            'nome': 'Ana Costa Vale Verde',
            'cpf': '444.555.666-77',
            'salario': 3000.0,
            'data_admissao': date(2025, 6, 15)
        }
    ]
    
    funcionarios_criados = []
    
    for dados_func in funcionarios_vale_verde:
        # Verificar se já existe
        func_existente = Funcionario.query.filter_by(cpf=dados_func['cpf']).first()
        
        if not func_existente:
            # Gerar código único
            ultimo_funcionario = Funcionario.query.order_by(Funcionario.id.desc()).first()
            proximo_numero = (ultimo_funcionario.id + 1) if ultimo_funcionario else 1
            codigo = f"F{proximo_numero:04d}"
            
            # Criar funcionário
            funcionario = Funcionario(
                codigo=codigo,
                nome=dados_func['nome'],
                cpf=dados_func['cpf'],
                data_admissao=dados_func['data_admissao'],
                salario=dados_func['salario'],
                horario_trabalho_id=horario_obra.id,
                ativo=True
            )
            
            db.session.add(funcionario)
            funcionarios_criados.append(funcionario)
            print(f"✅ Funcionário criado: {funcionario.nome}")
        else:
            funcionarios_criados.append(func_existente)
            print(f"⚠️  Funcionário já existe: {func_existente.nome}")
    
    db.session.commit()
    
    return funcionarios_criados, obra_vale_verde

def criar_registros_folga_funcionarios(funcionarios, obra):
    """Cria registros de folga para os funcionários da Vale Verde"""
    
    print(f"\nCRIANDO REGISTROS DE FOLGA PARA {len(funcionarios)} FUNCIONÁRIOS")
    print("=" * 60)
    
    # Período: últimos 3 meses
    data_inicio = date(2025, 5, 1)
    data_fim = date.today()
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        print(f"Processando: {funcionario.nome}")
        
        data_atual = data_inicio
        while data_atual <= data_fim:
            dia_semana = data_atual.weekday()  # 0=Segunda, 6=Domingo
            
            # Criar folgas para sábados e domingos
            if dia_semana in [5, 6]:  # Sábado=5, Domingo=6
                # Verificar se já existe registro
                registro_existente = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id == funcionario.id,
                    RegistroPonto.data == data_atual
                ).first()
                
                if not registro_existente:
                    # Determinar tipo
                    tipo_folga = 'sabado_folga' if dia_semana == 5 else 'domingo_folga'
                    
                    # Criar registro
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro=tipo_folga,
                        horas_trabalhadas=0,
                        observacoes=f'Folga Vale Verde - {data_atual.strftime("%d/%m/%Y")}'
                    )
                    
                    db.session.add(registro)
                    registros_criados += 1
            
            data_atual += timedelta(days=1)
    
    db.session.commit()
    print(f"✅ Total de registros de folga criados: {registros_criados}")
    
    return registros_criados

def criar_registros_trabalho_exemplo(funcionarios, obra):
    """Cria alguns registros de trabalho de exemplo"""
    
    print(f"\nCRIANDO REGISTROS DE TRABALHO DE EXEMPLO")
    print("=" * 50)
    
    registros_trabalho = 0
    
    # Criar registros para julho (exemplo)
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    for funcionario in funcionarios[:2]:  # Apenas 2 funcionários
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            dia_semana = data_atual.weekday()
            
            # Trabalho apenas em dias úteis
            if dia_semana < 5:  # Segunda a sexta
                registro_existente = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id == funcionario.id,
                    RegistroPonto.data == data_atual
                ).first()
                
                if not registro_existente:
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='trabalho_normal',
                        horas_trabalhadas=8.0,
                        observacoes=f'Trabalho Vale Verde - {data_atual.strftime("%d/%m/%Y")}'
                    )
                    
                    db.session.add(registro)
                    registros_trabalho += 1
            
            data_atual += timedelta(days=1)
    
    db.session.commit()
    print(f"✅ Registros de trabalho criados: {registros_trabalho}")
    
    return registros_trabalho

if __name__ == "__main__":
    with app.app_context():
        print("CRIANDO ESTRUTURA COMPLETA VALE VERDE")
        print("=" * 80)
        
        # Criar funcionários e obra
        funcionarios, obra = criar_funcionarios_vale_verde()
        
        # Criar registros de folga
        folgas_criadas = criar_registros_folga_funcionarios(funcionarios, obra)
        
        # Criar alguns registros de trabalho
        trabalho_criado = criar_registros_trabalho_exemplo(funcionarios, obra)
        
        print("\n" + "=" * 80)
        print("RESUMO FINAL")
        print("=" * 80)
        print(f"✅ Funcionários Vale Verde: {len(funcionarios)}")
        print(f"✅ Obra: {obra.nome}")
        print(f"✅ Registros de folga: {folgas_criadas}")
        print(f"✅ Registros de trabalho: {trabalho_criado}")
        print("✅ Sistema pronto para testar tipos v8.1")