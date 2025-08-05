#!/usr/bin/env python3
"""
Debug do sistema de lançamento de alimentação por período
Simula uma requisição POST para identificar onde estão os problemas nas datas
"""
from app import app, db
from models import RegistroAlimentacao, Funcionario, Obra, Restaurante
from datetime import datetime, timedelta, date
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.DEBUG)

def testar_lancamento_periodo():
    """Simula um lançamento por período para debug"""
    print("🔧 DEBUG: Lançamento de Alimentação por Período")
    print("=" * 60)
    
    with app.app_context():
        # Dados de teste (simular form data)
        data_inicio_str = "2025-08-01"  # Hoje
        data_fim_str = "2025-08-03"     # Hoje + 2 dias
        
        print(f"📅 Período teste: {data_inicio_str} até {data_fim_str}")
        
        # Simular a lógica do views.py
        inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        print(f"🔍 Data início convertida: {inicio}")
        print(f"🔍 Data fim convertida: {fim}")
        
        # Gerar lista de datas
        datas_processamento = []
        data_atual = inicio
        
        while data_atual <= fim:
            datas_processamento.append(data_atual)
            print(f"   📅 Adicionada data: {data_atual}")
            data_atual += timedelta(days=1)
        
        print(f"\n✅ Total de datas geradas: {len(datas_processamento)}")
        
        # Verificar funcionários disponíveis
        funcionarios = Funcionario.query.filter_by(ativo=True).limit(2).all()
        print(f"👥 Funcionários de teste: {[f.nome for f in funcionarios]}")
        
        if not funcionarios:
            print("❌ Nenhum funcionário ativo encontrado!")
            return
        
        # Verificar obra disponível
        obra = Obra.query.filter_by(ativo=True).first()
        if not obra:
            print("❌ Nenhuma obra ativa encontrada!")
            return
        
        print(f"🏗️ Obra de teste: {obra.nome}")
        
        # Verificar restaurante disponível
        restaurante = Restaurante.query.first()
        if not restaurante:
            print("❌ Nenhum restaurante encontrado!")
            return
        
        print(f"🍽️ Restaurante de teste: {restaurante.nome}")
        
        # Simular criação de registros
        print(f"\n🔄 Simulando criação de registros...")
        registros_teste = []
        
        for data in datas_processamento:
            for funcionario in funcionarios[:1]:  # Apenas 1 funcionário para teste
                registro_data = {
                    'funcionario_id': funcionario.id,
                    'funcionario_nome': funcionario.nome,
                    'obra_id': obra.id,
                    'restaurante_id': restaurante.id,
                    'data': data,
                    'tipo': 'almoco',
                    'valor': 15.0
                }
                registros_teste.append(registro_data)
                print(f"   📝 {funcionario.nome} - {data} - Almoço - R$ 15,00")
        
        print(f"\n📊 RESUMO:")
        print(f"   • Período: {data_inicio_str} a {data_fim_str}")
        print(f"   • Dias: {len(datas_processamento)}")
        print(f"   • Funcionários: {len(funcionarios[:1])}")
        print(f"   • Total registros previstos: {len(registros_teste)}")
        
        # Verificar registros existentes no banco
        print(f"\n🔍 VERIFICANDO REGISTROS EXISTENTES NO BANCO:")
        registros_existentes = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= inicio,
            RegistroAlimentacao.data <= fim
        ).all()
        
        if registros_existentes:
            print(f"⚠️ Encontrados {len(registros_existentes)} registros existentes:")
            for reg in registros_existentes:
                funcionario = Funcionario.query.get(reg.funcionario_id)
                nome_func = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                print(f"   • {nome_func} - {reg.data} - {reg.tipo} - R$ {reg.valor}")
        else:
            print("✅ Nenhum registro existente no período")

def verificar_registros_recentes():
    """Verifica os registros mais recentes para análise"""
    print(f"\n🔍 REGISTROS MAIS RECENTES (últimos 5):")
    
    with app.app_context():
        registros_recentes = RegistroAlimentacao.query.order_by(
            RegistroAlimentacao.id.desc()
        ).limit(5).all()
        
        for reg in registros_recentes:
            funcionario = Funcionario.query.get(reg.funcionario_id)
            nome_func = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            
            print(f"   ID {reg.id}: {nome_func} - {reg.data} - {reg.tipo} - R$ {reg.valor}")
            print(f"      Criado em: {reg.created_at}")

if __name__ == "__main__":
    testar_lancamento_periodo()
    verificar_registros_recentes()