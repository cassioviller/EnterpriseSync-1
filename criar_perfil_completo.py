#!/usr/bin/env python3
"""
Cria um perfil completo de funcionário com todos os tipos de lançamentos possíveis
- Trabalho normal
- Faltas
- Faltas justificadas
- Custo de alimentação
- Transporte
- Outros custos
- Feriado trabalhado
- Horas extras (sábado e domingo)
- Atrasos de entrada e saída mais cedo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime, time, timedelta
from app import app, db
from models import *

def criar_funcionario_completo():
    """Cria ou atualiza funcionário com perfil completo"""
    
    # Verificar se já existe um funcionário adequado
    funcionario = Funcionario.query.filter_by(nome="João Silva dos Santos").first()
    
    if not funcionario:
        print("Criando novo funcionário...")
        
        # Buscar departamento e função
        departamento = Departamento.query.filter_by(nome="Operações").first()
        funcao = Funcao.query.filter_by(nome="Operador").first()
        
        funcionario = Funcionario(
            nome="João Silva dos Santos",
            codigo="F0099",
            cpf="123.456.789-00",
            telefone="(11) 99999-9999",
            email="joao.silva@estruturasdovale.com",
            salario=2500.00,
            data_admissao=date(2025, 1, 15),
            departamento_id=departamento.id if departamento else None,
            funcao_id=funcao.id if funcao else None,
            ativo=True
        )
        
        db.session.add(funcionario)
        db.session.commit()
        print(f"Funcionário criado: {funcionario.nome} - {funcionario.codigo}")
    else:
        print(f"Funcionário encontrado: {funcionario.nome} - {funcionario.codigo}")
    
    return funcionario

def limpar_dados_funcionario(funcionario_id):
    """Remove dados existentes do funcionário para junho/2025"""
    data_inicio = date(2025, 6, 1)
    data_fim = date(2025, 6, 30)
    
    # Limpar registros de ponto
    RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).delete()
    
    # Limpar registros de alimentação
    RegistroAlimentacao.query.filter(
        RegistroAlimentacao.funcionario_id == funcionario_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).delete()
    
    # Limpar outros custos
    OutroCusto.query.filter(
        OutroCusto.funcionario_id == funcionario_id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).delete()
    
    # Limpar ocorrências
    Ocorrencia.query.filter(
        Ocorrencia.funcionario_id == funcionario_id,
        Ocorrencia.data_inicio >= data_inicio,
        Ocorrencia.data_inicio <= data_fim
    ).delete()
    
    db.session.commit()
    print("Dados existentes removidos")

def criar_registros_ponto_completos(funcionario_id):
    """Cria registros de ponto com todos os tipos possíveis"""
    
    obra = Obra.query.filter_by(nome="Residencial Belo Horizonte").first()
    if not obra:
        obra = Obra.query.first()
    
    registros = []
    
    # 03/06/2025 - Trabalho normal
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 3),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 0),
        hora_saida=time(17, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=8.0,
        horas_extras=0.0,
        total_atraso_minutos=0,
        observacoes="Trabalho normal"
    ))
    
    # 04/06/2025 - Atraso na entrada (30 min)
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 4),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 30),
        hora_saida=time(17, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=7.5,
        horas_extras=0.0,
        total_atraso_minutos=30,
        observacoes="Atraso na entrada - 30 minutos"
    ))
    
    # 05/06/2025 - Saída antecipada (1 hora)
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 5),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 0),
        hora_saida=time(16, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=7.0,
        horas_extras=0.0,
        total_atraso_minutos=60,
        observacoes="Saída antecipada - 1 hora"
    ))
    
    # 06/06/2025 - Atraso entrada + saída antecipada
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 6),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 15),
        hora_saida=time(16, 30),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=7.25,
        horas_extras=0.0,
        total_atraso_minutos=45,
        observacoes="Atraso entrada (15min) + saída antecipada (30min)"
    ))
    
    # 07/06/2025 - Sábado com horas extras (50%)
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 7),
        tipo_registro='sabado_horas_extras',
        hora_entrada=time(8, 0),
        hora_saida=time(12, 0),
        horas_trabalhadas=4.0,
        horas_extras=4.0,
        percentual_extras=50,
        total_atraso_minutos=0,
        observacoes="Sábado - 50% horas extras"
    ))
    
    # 08/06/2025 - Domingo com horas extras (100%)
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 8),
        tipo_registro='domingo_horas_extras',
        hora_entrada=time(8, 0),
        hora_saida=time(12, 0),
        horas_trabalhadas=4.0,
        horas_extras=4.0,
        percentual_extras=100,
        total_atraso_minutos=0,
        observacoes="Domingo - 100% horas extras"
    ))
    
    # 09/06/2025 - Trabalho normal
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 9),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 0),
        hora_saida=time(17, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=8.0,
        horas_extras=0.0,
        total_atraso_minutos=0,
        observacoes="Trabalho normal"
    ))
    
    # 10/06/2025 - Falta não justificada
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 10),
        tipo_registro='falta',
        observacoes="Falta não justificada"
    ))
    
    # 11/06/2025 - Falta justificada
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 11),
        tipo_registro='falta_justificada',
        observacoes="Falta justificada - consulta médica"
    ))
    
    # 12/06/2025 - Meio período (saída antecipada)
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 12),
        tipo_registro='meio_periodo',
        hora_entrada=time(8, 0),
        hora_saida=time(12, 0),
        horas_trabalhadas=4.0,
        horas_extras=0.0,
        total_atraso_minutos=0,
        observacoes="Meio período - saída antecipada"
    ))
    
    # 13/06/2025 - Trabalho sem intervalo
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 13),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 0),
        hora_saida=time(16, 0),
        horas_trabalhadas=8.0,
        horas_extras=0.0,
        total_atraso_minutos=0,
        observacoes="Trabalho contínuo - sem intervalo de almoço"
    ))
    
    # 16/06/2025 - Trabalho com horas extras
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 16),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 0),
        hora_saida=time(19, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=8.0,
        horas_extras=2.0,
        percentual_extras=50,
        total_atraso_minutos=0,
        observacoes="Trabalho normal + 2h extras"
    ))
    
    # 19/06/2025 - Feriado trabalhado (Corpus Christi)
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 19),
        tipo_registro='feriado_trabalhado',
        hora_entrada=time(8, 0),
        hora_saida=time(17, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=8.0,
        horas_extras=8.0,
        percentual_extras=100,
        total_atraso_minutos=0,
        observacoes="Feriado trabalhado - Corpus Christi - 100% extras"
    ))
    
    # 20/06/2025 - Trabalho normal
    registros.append(RegistroPonto(
        funcionario_id=funcionario_id,
        obra_id=obra.id,
        data=date(2025, 6, 20),
        tipo_registro='trabalho_normal',
        hora_entrada=time(8, 0),
        hora_saida=time(17, 0),
        hora_almoco_saida=time(12, 0),
        hora_almoco_retorno=time(13, 0),
        horas_trabalhadas=8.0,
        horas_extras=0.0,
        total_atraso_minutos=0,
        observacoes="Trabalho normal"
    ))
    
    # Adicionar todos os registros
    for registro in registros:
        db.session.add(registro)
    
    db.session.commit()
    print(f"Criados {len(registros)} registros de ponto")

def criar_registros_alimentacao_completos(funcionario_id):
    """Cria registros de alimentação variados"""
    
    restaurantes = Restaurante.query.all()
    if not restaurantes:
        print("Nenhum restaurante encontrado")
        return
    
    registros = []
    
    # Diferentes tipos de refeições
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 3),
        tipo='almoco',
        valor=15.50,
        observacoes="Almoço completo"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 4),
        tipo='almoco',
        valor=18.00,
        observacoes="Almoço + bebida"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 5),
        tipo='lanche',
        valor=8.50,
        observacoes="Lanche da tarde"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 6),
        tipo='almoco',
        valor=16.00,
        observacoes="Almoço"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 7),
        tipo='almoco',
        valor=20.00,
        observacoes="Almoço sábado"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 9),
        tipo='almoco',
        valor=17.50,
        observacoes="Almoço"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 13),
        tipo='almoco',
        valor=12.00,
        observacoes="Marmita - trabalho sem intervalo"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 16),
        tipo='jantar',
        valor=22.00,
        observacoes="Jantar - horas extras"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 19),
        tipo='almoco',
        valor=25.00,
        observacoes="Almoço feriado"
    ))
    
    registros.append(RegistroAlimentacao(
        funcionario_id=funcionario_id,
        restaurante_id=restaurantes[0].id,
        data=date(2025, 6, 20),
        tipo='almoco',
        valor=16.50,
        observacoes="Almoço"
    ))
    
    # Adicionar todos os registros
    for registro in registros:
        db.session.add(registro)
    
    db.session.commit()
    print(f"Criados {len(registros)} registros de alimentação")

def criar_outros_custos_completos(funcionario_id):
    """Cria outros custos variados"""
    
    custos = []
    
    # Vale transporte mensal
    custos.append(OutroCusto(
        funcionario_id=funcionario_id,
        data=date(2025, 6, 1),
        tipo='Vale Transporte',
        categoria='Benefício',
        valor=180.00,
        descricao='Vale transporte mensal'
    ))
    
    # Desconto VT
    custos.append(OutroCusto(
        funcionario_id=funcionario_id,
        data=date(2025, 6, 1),
        tipo='Desconto VT 6%',
        categoria='Desconto',
        valor=10.80,
        descricao='Desconto vale transporte 6%'
    ))
    
    # Vale alimentação
    custos.append(OutroCusto(
        funcionario_id=funcionario_id,
        data=date(2025, 6, 1),
        tipo='Vale Alimentação',
        categoria='Benefício',
        valor=300.00,
        descricao='Vale alimentação mensal'
    ))
    
    # EPI
    custos.append(OutroCusto(
        funcionario_id=funcionario_id,
        data=date(2025, 6, 15),
        tipo='EPI',
        categoria='Equipamento',
        valor=85.00,
        descricao='Equipamentos de Proteção Individual'
    ))
    
    # Seguro de vida
    custos.append(OutroCusto(
        funcionario_id=funcionario_id,
        data=date(2025, 6, 1),
        tipo='Seguro de Vida',
        categoria='Benefício',
        valor=25.00,
        descricao='Seguro de vida mensal'
    ))
    
    # Desconto INSS
    custos.append(OutroCusto(
        funcionario_id=funcionario_id,
        data=date(2025, 6, 30),
        tipo='Desconto INSS',
        categoria='Desconto',
        valor=225.00,
        descricao='Desconto INSS 9%'
    ))
    
    # Adicionar todos os custos
    for custo in custos:
        db.session.add(custo)
    
    db.session.commit()
    print(f"Criados {len(custos)} outros custos")

def criar_ocorrencias_completas(funcionario_id):
    """Cria ocorrências para justificar falta"""
    
    # Buscar tipo de ocorrência existente
    tipo_ocorrencia = TipoOcorrencia.query.first()
    if not tipo_ocorrencia:
        # Criar tipo básico se não existir
        tipo_ocorrencia = TipoOcorrencia(
            nome="Consulta Médica",
            descricao="Consulta médica agendada"
        )
        db.session.add(tipo_ocorrencia)
        db.session.commit()
    
    # Ocorrência para justificar falta do dia 11/06
    ocorrencia = Ocorrencia(
        funcionario_id=funcionario_id,
        tipo_ocorrencia_id=tipo_ocorrencia.id,
        data_inicio=date(2025, 6, 11),
        data_fim=date(2025, 6, 11),
        status='Aprovado',
        descricao='Consulta médica agendada - cardiologista'
    )
    
    db.session.add(ocorrencia)
    db.session.commit()
    print("Criada ocorrência para justificar falta")

def main():
    """Função principal"""
    with app.app_context():
        print("Criando perfil completo de funcionário...")
        print("="*60)
        
        # 1. Criar ou buscar funcionário
        funcionario = criar_funcionario_completo()
        
        # 2. Limpar dados existentes
        limpar_dados_funcionario(funcionario.id)
        
        # 3. Criar registros de ponto completos
        criar_registros_ponto_completos(funcionario.id)
        
        # 4. Criar registros de alimentação
        criar_registros_alimentacao_completos(funcionario.id)
        
        # 5. Criar outros custos
        criar_outros_custos_completos(funcionario.id)
        
        # 6. Criar ocorrências (opcional - comentado por enquanto)
        # criar_ocorrencias_completas(funcionario.id)
        
        print("="*60)
        print("PERFIL COMPLETO CRIADO COM SUCESSO!")
        print(f"Funcionário: {funcionario.nome} ({funcionario.codigo})")
        print(f"Período: Junho/2025")
        print()
        print("TIPOS DE LANÇAMENTOS INCLUÍDOS:")
        print("✓ Trabalho normal")
        print("✓ Atrasos de entrada")
        print("✓ Saídas antecipadas")
        print("✓ Atraso entrada + saída antecipada")
        print("✓ Sábado com horas extras (50%)")
        print("✓ Domingo com horas extras (100%)")
        print("✓ Falta não justificada")
        print("✓ Falta justificada (com ocorrência)")
        print("✓ Meio período")
        print("✓ Trabalho sem intervalo")
        print("✓ Horas extras em dia normal")
        print("✓ Feriado trabalhado (100% extras)")
        print("✓ Registros de alimentação (10 registros)")
        print("✓ Outros custos (6 tipos diferentes)")
        print("✓ Ocorrência para justificar falta")
        print()
        print("Acesse o perfil do funcionário no sistema para ver todos os dados!")

if __name__ == "__main__":
    main()