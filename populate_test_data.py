#!/usr/bin/env python3
"""
Script de População de Dados de Teste - SIGE (EnterpriseSync)
==============================================================

Este script popula o banco de dados com dados de teste realistas
para validação completa do sistema via interface.

Uso:
    python3 populate_test_data.py

Requisitos:
    - Aplicação Flask configurada
    - Banco de dados acessível
    - Migrations executadas (incluindo admin_id em todas as tabelas)
"""

import sys
import os
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

# Adicionar diretório da aplicação ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import (
    Usuario, Obra, Funcionario, Departamento, Funcao, HorarioTrabalho,
    RDO, RegistroAlimentacao, CustoObra, Veiculo, UsoVeiculo,
    CustoVeiculo, Servico, Restaurante
)

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

ADMIN_ID = 56  # ID do admin criado anteriormente
VERBOSE = True  # Mostrar logs detalhados

# Cores para output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(message, color=Colors.OKBLUE):
    """Log colorido"""
    if VERBOSE:
        print(f"{color}{message}{Colors.ENDC}")

def success(message):
    """Log de sucesso"""
    log(f"✅ {message}", Colors.OKGREEN)

def error(message):
    """Log de erro"""
    log(f"❌ {message}", Colors.FAIL)

def warning(message):
    """Log de aviso"""
    log(f"⚠️  {message}", Colors.WARNING)

def info(message):
    """Log de informação"""
    log(f"ℹ️  {message}", Colors.OKCYAN)

# ============================================================================
# FUNÇÕES DE LIMPEZA
# ============================================================================

def limpar_dados_teste():
    """Remove dados de teste anteriores"""
    log("\n" + "="*80, Colors.HEADER)
    log("LIMPEZA DE DADOS DE TESTE ANTERIORES", Colors.HEADER)
    log("="*80, Colors.HEADER)
    
    try:
        # Ordem de exclusão respeitando foreign keys
        tabelas = [
            ('CustoVeiculo', CustoVeiculo),
            ('UsoVeiculo', UsoVeiculo),
            ('Veiculo', Veiculo),
            ('CustoObra', CustoObra),
            ('RegistroAlimentacao', RegistroAlimentacao),
            ('RDO', RDO),
            ('Funcionario', Funcionario),
            ('HorarioTrabalho', HorarioTrabalho),
            ('Funcao', Funcao),
            ('Departamento', Departamento),
            ('Servico', Servico),
            ('Restaurante', Restaurante),
            ('Obra', Obra),
        ]
        
        for nome, modelo in tabelas:
            count = modelo.query.filter_by(admin_id=ADMIN_ID).count()
            if count > 0:
                modelo.query.filter_by(admin_id=ADMIN_ID).delete()
                info(f"Removidos {count} registros de {nome}")
        
        db.session.commit()
        success("Limpeza concluída com sucesso!")
        
    except Exception as e:
        db.session.rollback()
        error(f"Erro na limpeza: {str(e)}")
        raise

# ============================================================================
# FUNÇÕES DE POPULAÇÃO
# ============================================================================

def criar_departamentos():
    """Cria departamentos de teste"""
    log("\n📁 Criando Departamentos...", Colors.HEADER)
    
    departamentos_data = [
        {"nome": "Engenharia", "descricao": "Equipe de engenharia e projetos"},
        {"nome": "Obras", "descricao": "Equipe de execução de obras"},
        {"nome": "Administrativo", "descricao": "Equipe administrativa"},
        {"nome": "Manutenção", "descricao": "Equipe de manutenção"},
    ]
    
    departamentos = []
    for data in departamentos_data:
        dept = Departamento(
            nome=data["nome"],
            descricao=data["descricao"],
            admin_id=ADMIN_ID
        )
        db.session.add(dept)
        departamentos.append(dept)
        info(f"Departamento: {data['nome']}")
    
    db.session.flush()
    success(f"{len(departamentos)} departamentos criados")
    return departamentos

def criar_funcoes():
    """Cria funções de teste"""
    log("\n👷 Criando Funções...", Colors.HEADER)
    
    funcoes_data = [
        {"nome": "Engenheiro Civil", "descricao": "Responsável técnico"},
        {"nome": "Mestre de Obras", "descricao": "Supervisão de obras"},
        {"nome": "Pedreiro", "descricao": "Execução de alvenaria"},
        {"nome": "Servente", "descricao": "Serviços gerais"},
        {"nome": "Eletricista", "descricao": "Instalações elétricas"},
        {"nome": "Encanador", "descricao": "Instalações hidráulicas"},
    ]
    
    funcoes = []
    for data in funcoes_data:
        funcao = Funcao(
            nome=data["nome"],
            descricao=data["descricao"],
            admin_id=ADMIN_ID
        )
        db.session.add(funcao)
        funcoes.append(funcao)
        info(f"Função: {data['nome']}")
    
    db.session.flush()
    success(f"{len(funcoes)} funções criadas")
    return funcoes

def criar_horarios_trabalho():
    """Cria horários de trabalho de teste"""
    log("\n⏰ Criando Horários de Trabalho...", Colors.HEADER)
    
    horarios_data = [
        {
            "nome": "Comercial - 8h (Teste)",
            "entrada": "08:00:00",
            "saida_almoco": "12:00:00",
            "retorno_almoco": "13:00:00",
            "saida": "17:00:00",
            "dias_semana": "1,2,3,4,5",
            "horas_diarias": 8.0,
            "valor_hora": 25.00
        },
        {
            "nome": "Obra - 9h (Teste)",
            "entrada": "07:00:00",
            "saida_almoco": "12:00:00",
            "retorno_almoco": "13:00:00",
            "saida": "17:00:00",
            "dias_semana": "1,2,3,4,5,6",
            "horas_diarias": 9.0,
            "valor_hora": 20.00
        },
    ]
    
    horarios = []
    for data in horarios_data:
        horario = HorarioTrabalho(
            nome=data["nome"],
            entrada=data["entrada"],
            saida_almoco=data["saida_almoco"],
            retorno_almoco=data["retorno_almoco"],
            saida=data["saida"],
            dias_semana=data["dias_semana"],
            horas_diarias=data["horas_diarias"],
            valor_hora=data["valor_hora"],
            admin_id=ADMIN_ID
        )
        db.session.add(horario)
        horarios.append(horario)
        info(f"Horário: {data['nome']}")
    
    db.session.flush()
    success(f"{len(horarios)} horários criados")
    return horarios

def criar_obras():
    """Cria obras de teste"""
    log("\n🏗️  Criando Obras...", Colors.HEADER)
    
    obras_data = [
        {
            "nome": "Edifício Residencial Sunset",
            "endereco": "Rua das Flores, 123 - Centro - São Paulo/SP",
            "valor_contrato": 1500000.00,
            "data_inicio": date.today() - timedelta(days=60),
            "data_previsao_fim": date.today() + timedelta(days=120),
        },
        {
            "nome": "Reforma Comercial Plaza Shopping",
            "endereco": "Av. Paulista, 1000 - São Paulo/SP",
            "valor_contrato": 800000.00,
            "data_inicio": date.today() - timedelta(days=30),
            "data_previsao_fim": date.today() + timedelta(days=90),
        },
        {
            "nome": "Construção Galpão Industrial",
            "endereco": "Rod. Anhanguera, Km 45 - Jundiaí/SP",
            "valor_contrato": 2000000.00,
            "data_inicio": date.today() - timedelta(days=90),
            "data_previsao_fim": date.today() + timedelta(days=60),
        },
    ]
    
    obras = []
    for data in obras_data:
        obra = Obra(
            nome=data["nome"],
            endereco=data["endereco"],
            valor_contrato=data["valor_contrato"],
            data_inicio=data["data_inicio"],
            data_previsao_fim=data["data_previsao_fim"],
            ativo=True,
            admin_id=ADMIN_ID
        )
        db.session.add(obra)
        obras.append(obra)
        info(f"Obra: {data['nome']}")
    
    db.session.flush()
    success(f"{len(obras)} obras criadas")
    return obras

def criar_funcionarios(departamentos, funcoes, horarios):
    """Cria funcionários de teste"""
    log("\n👥 Criando Funcionários...", Colors.HEADER)
    
    nomes = [
        "João Silva Santos",
        "Maria Oliveira Costa",
        "Pedro Henrique Souza",
        "Ana Paula Ferreira",
        "Carlos Eduardo Lima",
        "Juliana Rodrigues Alves",
        "Fernando Martins Pereira",
        "Beatriz Santos Oliveira",
        "Rafael Costa Mendes",
        "Camila Almeida Rocha"
    ]
    
    funcionarios = []
    timestamp = datetime.now().strftime('%H%M%S')
    for i, nome in enumerate(nomes):
        cpf_num = random.randint(10000000000, 99999999999)
        codigo = f"FT{timestamp}{str(i+1).zfill(2)}"  # FT11035301, FT11035302, etc.
        
        func = Funcionario(
            codigo=codigo,
            nome=nome,
            cpf=str(cpf_num),
            rg=str(random.randint(100000000, 999999999)),
            data_nascimento=date(1990, 1, 1) + timedelta(days=random.randint(0, 10000)),
            telefone=f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
            email=f"{nome.lower().replace(' ', '.')}@teste.com",
            endereco=f"Rua Teste, {random.randint(1, 999)} - São Paulo/SP - CEP: {random.randint(10000, 99999)}-{random.randint(100, 999)}",
            data_admissao=date.today() - timedelta(days=random.randint(30, 365)),
            departamento_id=random.choice(departamentos).id,
            funcao_id=random.choice(funcoes).id,
            horario_trabalho_id=random.choice(horarios).id,
            salario=float(random.randint(2000, 8000)),
            ativo=True,
            admin_id=ADMIN_ID
        )
        db.session.add(func)
        funcionarios.append(func)
        info(f"Funcionário: {codigo} - {nome}")
    
    db.session.flush()
    success(f"{len(funcionarios)} funcionários criados")
    return funcionarios

def criar_restaurantes():
    """Cria restaurantes de teste"""
    log("\n🍽️  Criando Restaurantes...", Colors.HEADER)
    
    restaurantes_data = [
        {"nome": "Restaurante Bom Sabor", "telefone": "(11) 3000-1000", "endereco": "Rua A, 100"},
        {"nome": "Cantina da Obra", "telefone": "(11) 3000-2000", "endereco": "Rua B, 200"},
    ]
    
    restaurantes = []
    for data in restaurantes_data:
        rest = Restaurante(
            nome=data["nome"],
            telefone=data["telefone"],
            endereco=data["endereco"],
            admin_id=ADMIN_ID
        )
        db.session.add(rest)
        restaurantes.append(rest)
        info(f"Restaurante: {data['nome']}")
    
    db.session.flush()
    success(f"{len(restaurantes)} restaurantes criados")
    return restaurantes

def criar_veiculos():
    """Cria veículos de teste"""
    log("\n🚗 Criando Veículos...", Colors.HEADER)
    
    veiculos_data = [
        {
            "placa": "ABC1234",
            "modelo": "Hilux",
            "marca": "Toyota",
            "ano": 2020,
            "tipo": "Utilitário"
        },
        {
            "placa": "DEF5678",
            "modelo": "Ranger",
            "marca": "Ford",
            "ano": 2019,
            "tipo": "Utilitário"
        },
        {
            "placa": "GHI9012",
            "modelo": "Sprinter",
            "marca": "Mercedes",
            "ano": 2021,
            "tipo": "Van"
        },
    ]
    
    veiculos = []
    for data in veiculos_data:
        veiculo = Veiculo(
            placa=data["placa"],
            modelo=data["modelo"],
            marca=data["marca"],
            ano=data["ano"],
            tipo=data["tipo"],
            ativo=True,
            admin_id=ADMIN_ID
        )
        db.session.add(veiculo)
        veiculos.append(veiculo)
        info(f"Veículo: {data['placa']} - {data['marca']} {data['modelo']}")
    
    db.session.flush()
    success(f"{len(veiculos)} veículos criados")
    return veiculos

def criar_rdos(obras, funcionarios):
    """Cria RDOs de teste para os últimos 30 dias"""
    log("\n📋 Criando RDOs...", Colors.HEADER)
    
    rdos = []
    # Criar RDOs para as duas primeiras obras
    for obra in obras[:2]:
        # Últimos 30 dias
        for days_ago in range(30):
            data_rdo = date.today() - timedelta(days=days_ago)
            
            # Pular domingos
            if data_rdo.weekday() == 6:
                continue
            
            rdo = RDO(
                data=data_rdo,
                obra_id=obra.id,
                funcionario_id=random.choice(funcionarios).id,
                observacoes=f"RDO de teste - {data_rdo}",
                admin_id=ADMIN_ID
            )
            db.session.add(rdo)
            rdos.append(rdo)
    
    db.session.flush()
    success(f"{len(rdos)} RDOs criados")
    return rdos

def criar_registros_alimentacao(restaurantes, obras, funcionarios):
    """Cria registros de alimentação para os últimos 30 dias"""
    log("\n🍽️  Criando Registros de Alimentação...", Colors.HEADER)
    
    registros = []
    # Últimos 30 dias
    for days_ago in range(30):
        data_reg = date.today() - timedelta(days=days_ago)
        
        # Pular domingos
        if data_reg.weekday() == 6:
            continue
        
        # 3-5 refeições por dia
        for _ in range(random.randint(3, 5)):
            registro = RegistroAlimentacao(
                data=data_reg,
                valor=Decimal(random.uniform(15.0, 30.0)),
                tipo="Almoço",
                restaurante_id=random.choice(restaurantes).id,
                obra_id=random.choice(obras).id,
                funcionario_id=random.choice(funcionarios).id,
                admin_id=ADMIN_ID
            )
            db.session.add(registro)
            registros.append(registro)
    
    db.session.flush()
    success(f"{len(registros)} registros de alimentação criados")
    return registros

def criar_custos_obra(obras):
    """Cria custos de obra para os últimos 30 dias"""
    log("\n💰 Criando Custos de Obra...", Colors.HEADER)
    
    custos = []
    tipos = ["Material", "Mão de Obra", "Equipamento"]
    
    # Últimos 30 dias
    for days_ago in range(30):
        data_custo = date.today() - timedelta(days=days_ago)
        
        # 2-4 custos por dia
        for _ in range(random.randint(2, 4)):
            custo = CustoObra(
                data=data_custo,
                tipo_custo=random.choice(tipos),
                valor=Decimal(random.uniform(500.0, 5000.0)),
                descricao=f"Custo de {random.choice(tipos)} - {data_custo}",
                obra_id=random.choice(obras).id,
                admin_id=ADMIN_ID
            )
            db.session.add(custo)
            custos.append(custo)
    
    db.session.flush()
    success(f"{len(custos)} custos de obra criados")
    return custos

def criar_usos_veiculos(veiculos, obras):
    """Cria usos de veículos para os últimos 60 dias"""
    log("\n🚗 Criando Usos de Veículos...", Colors.HEADER)
    
    usos = []
    km_inicial = 10000
    
    # Últimos 60 dias
    for days_ago in range(60):
        data_uso = date.today() - timedelta(days=days_ago)
        
        for veiculo in veiculos:
            km_percorrido = random.randint(50, 200)
            uso = UsoVeiculo(
                data=data_uso,
                veiculo_id=veiculo.id,
                obra_id=random.choice(obras).id,
                km_inicial=km_inicial,
                km_final=km_inicial + km_percorrido,
                objetivo=f"Transporte de materiais - {data_uso}",
                admin_id=ADMIN_ID
            )
            db.session.add(uso)
            usos.append(uso)
            km_inicial += km_percorrido
    
    db.session.flush()
    success(f"{len(usos)} usos de veículos criados")
    return usos

def criar_custos_veiculos(veiculos):
    """Cria custos de veículos para os últimos 30 dias"""
    log("\n💰 Criando Custos de Veículos...", Colors.HEADER)
    
    custos = []
    tipos = ["Combustível", "Manutenção", "Seguro"]
    
    # Últimos 30 dias
    for days_ago in range(30):
        data_custo = date.today() - timedelta(days=days_ago)
        
        for veiculo in veiculos:
            if random.random() > 0.7:  # 30% de chance por dia
                custo = CustoVeiculo(
                    data=data_custo,
                    veiculo_id=veiculo.id,
                    tipo_custo=random.choice(tipos),
                    valor=Decimal(random.uniform(100.0, 500.0)),
                    descricao=f"Custo de {random.choice(tipos)} - {data_custo}",
                    admin_id=ADMIN_ID
                )
                db.session.add(custo)
                custos.append(custo)
    
    db.session.flush()
    success(f"{len(custos)} custos de veículos criados")
    return custos

# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    """Função principal de execução"""
    log("\n" + "="*80, Colors.HEADER)
    log("POPULAÇÃO DE DADOS DE TESTE - SIGE", Colors.HEADER)
    log("="*80, Colors.HEADER)
    
    with app.app_context():
        try:
            # 1. Limpar dados anteriores
            limpar_dados_teste()
            
            # 2. Criar dados básicos
            departamentos = criar_departamentos()
            funcoes = criar_funcoes()
            horarios = criar_horarios_trabalho()
            obras = criar_obras()
            funcionarios = criar_funcionarios(departamentos, funcoes, horarios)
            restaurantes = criar_restaurantes()
            veiculos = criar_veiculos()
            
            # 3. Criar dados transacionais (desabilitado por hora)
            # rdos = criar_rdos(obras, funcionarios)
            # registros_alimentacao = criar_registros_alimentacao(restaurantes, obras, funcionarios)
            # custos_obra = criar_custos_obra(obras)
            # usos_veiculos = criar_usos_veiculos(veiculos, obras)
            # custos_veiculos = criar_custos_veiculos(veiculos)
            rdos = []
            registros_alimentacao = []
            custos_obra = []
            usos_veiculos = []
            custos_veiculos = []
            
            # 4. Commit final
            db.session.commit()
            
            # 5. Resumo
            log("\n" + "="*80, Colors.HEADER)
            log("RESUMO DA POPULAÇÃO", Colors.HEADER)
            log("="*80, Colors.HEADER)
            success(f"{len(departamentos)} Departamentos")
            success(f"{len(funcoes)} Funções")
            success(f"{len(horarios)} Horários de Trabalho")
            success(f"{len(obras)} Obras")
            success(f"{len(funcionarios)} Funcionários")
            success(f"{len(restaurantes)} Restaurantes")
            success(f"{len(veiculos)} Veículos")
            success(f"{len(rdos)} RDOs")
            success(f"{len(registros_alimentacao)} Registros de Alimentação")
            success(f"{len(custos_obra)} Custos de Obra")
            success(f"{len(usos_veiculos)} Usos de Veículos")
            success(f"{len(custos_veiculos)} Custos de Veículos")
            log("="*80, Colors.HEADER)
            success("POPULAÇÃO CONCLUÍDA COM SUCESSO!")
            log("="*80, Colors.HEADER)
            
        except Exception as e:
            db.session.rollback()
            error(f"Erro durante a população: {str(e)}")
            import traceback
            traceback.print_exc()
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
