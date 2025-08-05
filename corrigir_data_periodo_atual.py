#!/usr/bin/env python3
"""
CORREÇÃO URGENTE: Registros de Alimentação com Data Incorreta
Corrigir registros de 30/07/2025 que foram salvos em agosto
"""

from app import app, db
from models import RegistroAlimentacao
from datetime import date, datetime
from sqlalchemy import and_

def identificar_registros_incorretos():
    """Identifica registros que foram salvos com data errada"""
    
    with app.app_context():
        print("🔍 IDENTIFICANDO REGISTROS COM DATA INCORRETA")
        print("=" * 60)
        
        # Buscar registros de agosto que podem ter sido criados incorretamente
        registros_agosto = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1),
            RegistroAlimentacao.data <= date(2025, 8, 5)
        ).order_by(RegistroAlimentacao.data, RegistroAlimentacao.funcionario_id).all()
        
        print(f"📊 Encontrados {len(registros_agosto)} registros em agosto (01-05/08)")
        
        # Agrupar por data para análise
        por_data = {}
        for registro in registros_agosto:
            data_str = registro.data.strftime('%d/%m/%Y')
            if data_str not in por_data:
                por_data[data_str] = []
            por_data[data_str].append(registro)
        
        print("\n📅 Registros por data:")
        for data_str, regs in por_data.items():
            print(f"   {data_str}: {len(regs)} registros")
            
            # Mostrar detalhes dos primeiros registros
            for i, reg in enumerate(regs[:3]):
                from models import Funcionario
                funcionario = Funcionario.query.get(reg.funcionario_id)
                funcionario_nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                print(f"      {i+1}. {funcionario_nome} - {reg.tipo} - R$ {reg.valor}")
            
            if len(regs) > 3:
                print(f"      ... e mais {len(regs) - 3} registros")
        
        return registros_agosto

def corrigir_para_30_julho():
    """Corrige registros para 30/07/2025"""
    
    with app.app_context():
        print("\n🔧 CORREÇÃO: Movendo registros para 30/07/2025")
        print("-" * 50)
        
        # Data de destino
        data_correta = date(2025, 7, 30)
        
        # Buscar registros de agosto recentes (últimos 2 dias)
        registros_recentes = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1),
            RegistroAlimentacao.data <= date(2025, 8, 5)
        ).all()
        
        print(f"📋 Registros a corrigir: {len(registros_recentes)}")
        
        # Confirmar se devemos corrigir
        resposta = input("❓ Corrigir todas as datas para 30/07/2025? (s/n): ")
        
        if resposta.lower() == 's':
            corrigidos = 0
            
            for registro in registros_recentes:
                data_original = registro.data
                registro.data = data_correta
                
                from models import Funcionario
                funcionario = Funcionario.query.get(registro.funcionario_id)
                funcionario_nome = funcionario.nome if funcionario else f"ID:{registro.funcionario_id}"
                print(f"   ✅ {funcionario_nome}: {data_original} → {data_correta}")
                corrigidos += 1
            
            try:
                db.session.commit()
                print(f"\n🎉 SUCESSO: {corrigidos} registros corrigidos!")
                print(f"   Todos os registros agora estão em 30/07/2025")
                
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ ERRO: {str(e)}")
                
        else:
            print("⚠️ Correção cancelada pelo usuário")

def verificar_registros_julho():
    """Verifica se há registros em julho para referência"""
    
    with app.app_context():
        print("\n📊 VERIFICAÇÃO: Registros em julho")
        print("-" * 40)
        
        registros_julho = RegistroAlimentacao.query.filter(
            and_(
                RegistroAlimentacao.data >= date(2025, 7, 1),
                RegistroAlimentacao.data <= date(2025, 7, 31)
            )
        ).order_by(RegistroAlimentacao.data.desc()).all()
        
        print(f"Total em julho: {len(registros_julho)}")
        
        # Mostrar últimos registros
        if registros_julho:
            print("Últimos registros de julho:")
            for reg in registros_julho[:5]:
                from models import Funcionario
                funcionario = Funcionario.query.get(reg.funcionario_id)
                funcionario_nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                print(f"   {reg.data.strftime('%d/%m/%Y')}: {funcionario_nome} - {reg.tipo}")

if __name__ == "__main__":
    registros_incorretos = identificar_registros_incorretos()
    verificar_registros_julho()
    
    if registros_incorretos:
        corrigir_para_30_julho()
    else:
        print("\n✅ Nenhum registro incorreto encontrado")