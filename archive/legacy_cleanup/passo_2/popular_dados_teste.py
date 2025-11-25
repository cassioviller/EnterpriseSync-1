#!/usr/bin/env python3
"""
Script para popular dados de teste completos no SIGE
Testa todas as KPIs do dashboard com dados realistas
"""

import sys
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import (
    Funcionario, RegistroPonto, Obra, Proposta, 
    Departamento, Funcao, HorarioTrabalho,
    VehicleExpense, RegistroAlimentacao, OutroCusto
)

def criar_dados_basicos(admin_id=10):
    """Cria departamentos, funções e horários se não existirem"""
    
    # Criar departamento
    dept = Departamento.query.filter_by(nome="Teste Automático").first()
    if not dept:
        dept = Departamento(
            nome="Teste Automático",
            descricao="Departamento criado automaticamente para testes"
        )
        db.session.add(dept)
        db.session.flush()
    
    # Criar função
    funcao = Funcao.query.filter_by(nome="Operador Teste").first()
    if not funcao:
        funcao = Funcao(
            nome="Operador Teste",
            descricao="Função criada automaticamente para testes"
        )
        db.session.add(funcao)
        db.session.flush()
    
    # Criar horário
    horario = HorarioTrabalho.query.filter_by(nome="Comercial 44h").first()
    if not horario:
        horario = HorarioTrabalho(
            nome="Comercial 44h",
            entrada=datetime.strptime("08:00", "%H:%M").time(),
            saida=datetime.strptime("17:48", "%H:%M").time(),
            saida_almoco=datetime.strptime("12:00", "%H:%M").time(),
            retorno_almoco=datetime.strptime("13:00", "%H:%M").time(),
            dias_semana="1,2,3,4,5",  # Segunda a Sexta
            horas_diarias=8.8,
            valor_hora=15.0
        )
        db.session.add(horario)
        db.session.flush()
    
    return dept.id, funcao.id, horario.id

def criar_funcionario_teste(admin_id=10):
    """Cria um funcionário completo para testes"""
    
    print("📋 Criando funcionário de teste...")
    
    # Verificar se já existe
    func_existente = Funcionario.query.filter_by(
        cpf="999.999.999-99",
        admin_id=admin_id
    ).first()
    
    if func_existente:
        print(f"✅ Funcionário já existe: {func_existente.nome} (ID: {func_existente.id})")
        return func_existente
    
    # Criar dados básicos
    dept_id, funcao_id, horario_id = criar_dados_basicos(admin_id)
    
    # Gerar código
    ultimo_codigo = db.session.execute(
        db.text("SELECT codigo FROM funcionario WHERE admin_id = :admin_id ORDER BY id DESC LIMIT 1"),
        {"admin_id": admin_id}
    ).scalar()
    
    if ultimo_codigo and ultimo_codigo.startswith('F'):
        numero = int(ultimo_codigo[1:]) + 1
    else:
        numero = 1000
    
    codigo = f"F{numero:04d}"
    
    # Criar funcionário
    funcionario = Funcionario(
        codigo=codigo,
        nome="Teste Dashboard KPI",
        cpf="999.999.999-99",
        rg="99.999.999-9",
        data_nascimento=date(1990, 5, 15),
        endereco="Rua Teste, 123 - Centro",
        telefone="(11) 99999-9999",
        email="teste.dashboard@sige.com",
        data_admissao=date(2024, 10, 1),
        salario=5000.00,
        jornada_semanal=44,
        ativo=True,
        departamento_id=dept_id,
        funcao_id=funcao_id,
        horario_trabalho_id=horario_id,
        admin_id=admin_id
    )
    
    db.session.add(funcionario)
    db.session.flush()
    
    print(f"✅ Funcionário criado: {funcionario.nome} (ID: {funcionario.id}, Código: {funcionario.codigo})")
    return funcionario

def criar_registros_ponto(funcionario, admin_id=10):
    """Cria registros de ponto para outubro/2025"""
    
    print("⏰ Criando registros de ponto...")
    
    # Período: 1 a 17 de outubro/2025
    data_inicio = date(2025, 10, 1)
    data_fim = date(2025, 10, 17)
    
    registros_criados = 0
    data_atual = data_inicio
    
    while data_atual <= data_fim:
        # Pular finais de semana
        if data_atual.weekday() < 5:  # Segunda a Sexta
            
            # Verificar se já existe
            existe = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_atual
            ).first()
            
            if not existe:
                # Horários base
                entrada = datetime.combine(data_atual, datetime.strptime("08:00", "%H:%M").time())
                saida = datetime.combine(data_atual, datetime.strptime("17:48", "%H:%M").time())
                
                # Calcular horas (9h48min = 9.8h)
                horas = 8.8  # 8h48min efetivas (9h48 - 1h almoço)
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_atual,
                    hora_entrada=entrada.time(),
                    hora_saida=saida.time(),
                    horas_trabalhadas=horas,
                    horas_extras=0,
                    tipo_registro='normal',
                    admin_id=admin_id
                )
                
                db.session.add(registro)
                registros_criados += 1
        
        data_atual += timedelta(days=1)
    
    db.session.flush()
    print(f"✅ {registros_criados} registros de ponto criados")

def criar_obra_teste(admin_id=10):
    """Cria uma obra para testes"""
    
    print("🏗️ Criando obra de teste...")
    
    # Verificar se já existe
    obra_existente = Obra.query.filter_by(
        nome="Obra Teste Dashboard",
        admin_id=admin_id
    ).first()
    
    if obra_existente:
        print(f"✅ Obra já existe: {obra_existente.nome} (ID: {obra_existente.id})")
        return obra_existente
    
    # Gerar código
    ultimo_codigo = db.session.execute(
        db.text("SELECT codigo FROM obra WHERE admin_id = :admin_id ORDER BY id DESC LIMIT 1"),
        {"admin_id": admin_id}
    ).scalar()
    
    if ultimo_codigo and ultimo_codigo.startswith('OB'):
        numero = int(ultimo_codigo[2:]) + 1
    else:
        numero = 100
    
    codigo = f"OB{numero:03d}"
    
    obra = Obra(
        codigo=codigo,
        nome="Obra Teste Dashboard",
        endereco="Av. Principal, 1000",
        data_inicio=date(2025, 10, 1),
        data_previsao_fim=date(2025, 12, 31),
        orcamento=500000.00,
        valor_contrato=550000.00,
        area_total_m2=1000.0,
        status='Em andamento',
        cliente_nome="Cliente Teste SIGE",
        ativo=True,
        admin_id=admin_id
    )
    
    db.session.add(obra)
    db.session.flush()
    
    print(f"✅ Obra criada: {obra.nome} (ID: {obra.id}, Código: {obra.codigo})")
    return obra

def criar_propostas_teste(admin_id=10):
    """Cria propostas comerciais para teste"""
    
    print("📄 Criando propostas comerciais...")
    
    propostas_criadas = 0
    
    # Proposta Aprovada
    prop_aprovada = Proposta.query.filter_by(
        titulo="Proposta Teste Aprovada",
        admin_id=admin_id
    ).first()
    
    if not prop_aprovada:
        # Gerar número
        ano_atual = date.today().year
        count = db.session.execute(
            db.text("SELECT COUNT(*) FROM propostas_comerciais WHERE EXTRACT(YEAR FROM data_proposta) = :ano AND admin_id = :admin_id"),
            {"ano": ano_atual, "admin_id": admin_id}
        ).scalar() or 0
        
        numero = f"{(count + 1):03d}.{str(ano_atual)[-2:]}"
        
        prop_aprovada = Proposta(
            numero=numero,
            data_proposta=date(2025, 10, 5),
            cliente_nome="Cliente Aprovado Teste",
            cliente_telefone="(11) 98888-8888",
            cliente_email="cliente1@teste.com",
            titulo="Proposta Teste Aprovada",
            descricao="Descrição da proposta aprovada",
            valor_total=Decimal('150000.00'),
            status='aprovada',
            admin_id=admin_id
        )
        db.session.add(prop_aprovada)
        propostas_criadas += 1
    
    # Proposta Enviada
    prop_enviada = Proposta.query.filter_by(
        titulo="Proposta Teste Enviada",
        admin_id=admin_id
    ).first()
    
    if not prop_enviada:
        ano_atual = date.today().year
        count = db.session.execute(
            db.text("SELECT COUNT(*) FROM propostas_comerciais WHERE EXTRACT(YEAR FROM data_proposta) = :ano AND admin_id = :admin_id"),
            {"ano": ano_atual, "admin_id": admin_id}
        ).scalar() or 0
        
        numero = f"{(count + 2):03d}.{str(ano_atual)[-2:]}"
        
        prop_enviada = Proposta(
            numero=numero,
            data_proposta=date(2025, 10, 10),
            cliente_nome="Cliente Aguardando Teste",
            cliente_telefone="(11) 97777-7777",
            cliente_email="cliente2@teste.com",
            titulo="Proposta Teste Enviada",
            descricao="Descrição da proposta enviada",
            valor_total=Decimal('80000.00'),
            status='enviada',
            admin_id=admin_id
        )
        db.session.add(prop_enviada)
        propostas_criadas += 1
    
    db.session.flush()
    print(f"✅ {propostas_criadas} propostas criadas")

def criar_outros_custos(funcionario, admin_id=10):
    """Cria outros custos para teste"""
    
    print("💰 Criando outros custos...")
    
    # Verificar se já existe
    custo_existente = OutroCusto.query.filter_by(
        descricao="Material Teste - Dashboard",
        admin_id=admin_id
    ).first()
    
    if custo_existente:
        print("✅ Outros custos já existem")
        return
    
    custo = OutroCusto(
        funcionario_id=funcionario.id,
        data=date(2025, 10, 15),
        tipo='material',
        descricao="Material Teste - Dashboard",
        valor=Decimal('1250.00'),
        categoria='construcao',
        admin_id=admin_id
    )
    
    db.session.add(custo)
    db.session.flush()
    print("✅ Outros custos criados")

def main():
    """Função principal"""
    
    print("\n" + "="*60)
    print("🚀 POPULAR DADOS DE TESTE - DASHBOARD SIGE")
    print("="*60 + "\n")
    
    admin_id = 10  # Vale Verde
    
    try:
        with app.app_context():
            # 1. Criar funcionário
            funcionario = criar_funcionario_teste(admin_id)
            
            # 2. Criar registros de ponto
            criar_registros_ponto(funcionario, admin_id)
            
            # 3. Criar obra
            obra = criar_obra_teste(admin_id)
            
            # 4. Criar propostas
            criar_propostas_teste(admin_id)
            
            # 5. Criar outros custos
            criar_outros_custos(funcionario, admin_id)
            
            # Commit final
            db.session.commit()
            
            print("\n" + "="*60)
            print("✅ DADOS DE TESTE CRIADOS COM SUCESSO!")
            print("="*60)
            print(f"\n📊 Resumo:")
            print(f"   - Funcionário: {funcionario.nome} (ID: {funcionario.id})")
            print(f"   - Registros de Ponto: Outubro 1-17/2025")
            print(f"   - Obra: {obra.nome} (ID: {obra.id})")
            print(f"   - Propostas: 2 (1 aprovada, 1 enviada)")
            print(f"   - Outros Custos: R$ 1.250,00")
            print(f"\n🎯 Dashboard agora deve exibir KPIs reais!")
            print(f"   Acesse: /dashboard\n")
            
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            db.session.rollback()
        except:
            pass
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
