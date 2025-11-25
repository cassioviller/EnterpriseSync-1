#!/usr/bin/env python3
"""
Script para popular dados de teste completos das KPIs:
- Alimentação
- Faltas Justificadas
- Custos por Obra (com funcionários associados)
"""

import sys
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import (
    Funcionario, RegistroPonto, Obra, 
    RegistroAlimentacao, Restaurante
)

def criar_restaurante(admin_id=10):
    """Cria restaurante para lançamentos de alimentação"""
    
    print("🍽️  Criando restaurante...")
    
    rest = Restaurante.query.filter_by(
        nome="Restaurante Teste Dashboard",
        admin_id=admin_id
    ).first()
    
    if rest:
        print(f"✅ Restaurante já existe: {rest.nome} (ID: {rest.id})")
        return rest
    
    rest = Restaurante(
        nome="Restaurante Teste Dashboard",
        endereco="Rua das Refeições, 100",
        telefone="(11) 3333-3333",
        razao_social="Restaurante Teste LTDA",
        cnpj="12.345.678/0001-99",
        pix="restaurante@teste.com",
        nome_conta="Restaurante Teste",
        admin_id=admin_id
    )
    
    db.session.add(rest)
    db.session.flush()
    
    print(f"✅ Restaurante criado: {rest.nome} (ID: {rest.id})")
    return rest

def buscar_funcionarios_obras(admin_id=10):
    """Busca funcionários e obras existentes"""
    
    print("\n📋 Buscando funcionários e obras...")
    
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).limit(5).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).limit(3).all()
    
    print(f"✅ Encontrados {len(funcionarios)} funcionários")
    print(f"✅ Encontradas {len(obras)} obras")
    
    if len(funcionarios) == 0:
        print("⚠️  AVISO: Nenhum funcionário encontrado! Execute popular_dados_teste.py primeiro")
        return [], []
    
    if len(obras) == 0:
        print("⚠️  AVISO: Nenhuma obra encontrada! Execute popular_dados_teste.py primeiro")
        return funcionarios, []
    
    return funcionarios, obras

def criar_registros_ponto_obras(funcionarios, obras, admin_id=10):
    """Cria registros de ponto associados às obras"""
    
    print("\n⏰ Criando registros de ponto com obras...")
    
    if not funcionarios or not obras:
        print("⚠️  Sem funcionários ou obras - pulando")
        return 0
    
    registros_criados = 0
    
    # Período: últimos 10 dias
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=9)
    
    # Distribuir funcionários pelas obras
    for i, func in enumerate(funcionarios):
        obra = obras[i % len(obras)]  # Rotaciona entre as obras
        
        data_atual = data_inicio
        while data_atual <= data_fim:
            # Pular finais de semana
            if data_atual.weekday() < 5:
                
                # Verificar se já existe
                existe = RegistroPonto.query.filter_by(
                    funcionario_id=func.id,
                    data=data_atual,
                    obra_id=obra.id
                ).first()
                
                if not existe:
                    # Criar alguns dias com falta justificada (30% de chance)
                    import random
                    eh_falta_justificada = random.random() < 0.3
                    
                    if eh_falta_justificada:
                        # Falta justificada
                        registro = RegistroPonto(
                            funcionario_id=func.id,
                            obra_id=obra.id,
                            data=data_atual,
                            tipo_registro='falta_justificada',
                            observacoes='Atestado médico',
                            admin_id=admin_id
                        )
                    else:
                        # Dia normal de trabalho
                        entrada = datetime.combine(data_atual, datetime.strptime("08:00", "%H:%M").time())
                        saida = datetime.combine(data_atual, datetime.strptime("17:48", "%H:%M").time())
                        horas = 8.8
                        
                        registro = RegistroPonto(
                            funcionario_id=func.id,
                            obra_id=obra.id,
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
        
        print(f"   ✅ {func.nome[:30]:30} → Obra: {obra.nome[:30]:30}")
    
    db.session.flush()
    print(f"✅ {registros_criados} registros de ponto criados (com obras)")
    return registros_criados

def criar_registros_alimentacao(funcionarios, obras, restaurante, admin_id=10):
    """Cria registros de alimentação para funcionários e obras"""
    
    print("\n🍽️  Criando registros de alimentação...")
    
    if not funcionarios or not obras or not restaurante:
        print("⚠️  Faltam dados necessários - pulando")
        return 0
    
    registros_criados = 0
    
    # Período: últimos 10 dias
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=9)
    
    # Para cada funcionário, criar registros de almoço nos dias trabalhados
    for func in funcionarios:
        # Buscar registros de ponto do funcionário
        registros_ponto = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == func.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro == 'normal'  # Só criar alimentação em dias trabalhados
        ).all()
        
        for reg in registros_ponto:
            # Verificar se já existe
            existe = RegistroAlimentacao.query.filter_by(
                funcionario_id=func.id,
                data=reg.data,
                obra_id=reg.obra_id
            ).first()
            
            if not existe:
                # Valor do almoço: R$ 25,00 a R$ 35,00
                import random
                valor_almoco = round(random.uniform(25.0, 35.0), 2)
                
                registro_alim = RegistroAlimentacao(
                    funcionario_id=func.id,
                    obra_id=reg.obra_id,
                    restaurante_id=restaurante.id,
                    data=reg.data,
                    tipo='almoco',
                    valor=valor_almoco,
                    observacoes=f'Almoço - {restaurante.nome}'
                )
                
                db.session.add(registro_alim)
                registros_criados += 1
    
    db.session.flush()
    print(f"✅ {registros_criados} registros de alimentação criados")
    return registros_criados

def gerar_relatorio_kpis(funcionarios, obras, admin_id=10):
    """Gera relatório das KPIs populadas"""
    
    print("\n" + "="*70)
    print("📊 RELATÓRIO DE KPIs POPULADAS")
    print("="*70)
    
    # Período de análise
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=9)
    
    print(f"\n📅 Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
    print(f"🏢 Admin: Vale Verde (ID: {admin_id})")
    
    # 1. Alimentação
    print("\n🍽️  KPI: ALIMENTAÇÃO")
    print("-" * 70)
    
    alimentacao_total = db.session.query(
        db.func.count(RegistroAlimentacao.id),
        db.func.sum(RegistroAlimentacao.valor)
    ).join(
        Funcionario, RegistroAlimentacao.funcionario_id == Funcionario.id
    ).filter(
        Funcionario.admin_id == admin_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).first()
    
    qtd_alimentacao = alimentacao_total[0] or 0
    custo_alimentacao = float(alimentacao_total[1] or 0)
    
    print(f"   Total de refeições: {qtd_alimentacao}")
    print(f"   Custo total: R$ {custo_alimentacao:,.2f}")
    if qtd_alimentacao > 0:
        print(f"   Custo médio/refeição: R$ {custo_alimentacao/qtd_alimentacao:.2f}")
    
    # 2. Faltas Justificadas
    print("\n📋 KPI: FALTAS JUSTIFICADAS")
    print("-" * 70)
    
    faltas = RegistroPonto.query.filter(
        RegistroPonto.admin_id == admin_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro == 'falta_justificada'
    ).all()
    
    custo_faltas = 0
    for falta in faltas:
        func = Funcionario.query.get(falta.funcionario_id)
        if func and func.salario:
            import calendar
            mes = falta.data.month
            ano = falta.data.year
            dias_uteis = sum(1 for dia in range(1, calendar.monthrange(ano, mes)[1] + 1) 
                            if date(ano, mes, dia).weekday() < 5)
            valor_dia = func.salario / dias_uteis
            custo_faltas += valor_dia
    
    print(f"   Quantidade de faltas: {len(faltas)}")
    print(f"   Custo total: R$ {custo_faltas:,.2f}")
    if len(faltas) > 0:
        print(f"   Custo médio/falta: R$ {custo_faltas/len(faltas):.2f}")
    
    # 3. Custos por Obra
    print("\n🏗️  KPI: CUSTOS POR OBRA")
    print("-" * 70)
    
    for obra in obras:
        # Mão de obra
        registros_obra = RegistroPonto.query.filter(
            RegistroPonto.obra_id == obra.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro == 'normal'
        ).all()
        
        custo_mao_obra = 0
        for reg in registros_obra:
            func = Funcionario.query.get(reg.funcionario_id)
            if func and func.salario:
                # Valor hora aproximado
                valor_hora = func.salario / 220  # aproximação
                horas = (reg.horas_trabalhadas or 0)
                custo_mao_obra += horas * valor_hora
        
        # Alimentação
        alim_obra = db.session.query(
            db.func.sum(RegistroAlimentacao.valor)
        ).filter(
            RegistroAlimentacao.obra_id == obra.id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).scalar() or 0
        
        custo_total_obra = custo_mao_obra + float(alim_obra)
        
        print(f"\n   📍 {obra.nome}")
        print(f"      Mão de Obra: R$ {custo_mao_obra:,.2f}")
        print(f"      Alimentação: R$ {float(alim_obra):,.2f}")
        print(f"      TOTAL: R$ {custo_total_obra:,.2f}")
    
    print("\n" + "="*70)

def main():
    """Função principal"""
    
    print("\n" + "="*70)
    print("🚀 POPULAR KPIs COMPLETAS - DASHBOARD SIGE")
    print("="*70 + "\n")
    
    admin_id = 10  # Vale Verde
    
    try:
        with app.app_context():
            # 1. Buscar funcionários e obras existentes
            funcionarios, obras = buscar_funcionarios_obras(admin_id)
            
            if not funcionarios:
                print("\n❌ ERRO: Nenhum funcionário encontrado!")
                print("Execute primeiro: python3 popular_dados_teste.py")
                return 1
            
            # 2. Criar restaurante
            restaurante = criar_restaurante(admin_id)
            
            # 3. Criar registros de ponto com obras
            criar_registros_ponto_obras(funcionarios, obras, admin_id)
            
            # 4. Criar registros de alimentação
            criar_registros_alimentacao(funcionarios, obras, restaurante, admin_id)
            
            # Commit
            db.session.commit()
            
            # 5. Gerar relatório
            gerar_relatorio_kpis(funcionarios, obras, admin_id)
            
            print("\n✅ DADOS POPULADOS COM SUCESSO!")
            print("\n🎯 Próximos passos:")
            print("   1. Acesse: http://localhost:5000/login")
            print("   2. Login: valeverde / admin123")
            print("   3. Dashboard mostrará as 3 KPIs populadas")
            print("   4. Execute teste e2e para validar\n")
            
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
