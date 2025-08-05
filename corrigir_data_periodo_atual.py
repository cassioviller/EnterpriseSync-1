#!/usr/bin/env python3
"""
CORREÇÃO URGENTE: Problema de Data no Lançamento por Período
Problema identificado: Sistema salvando data atual em vez da data selecionada
"""

from app import app, db
from models import RegistroAlimentacao, Funcionario
from datetime import datetime, date

def identificar_problema_data():
    """Identifica exatamente onde está o problema de data"""
    
    with app.app_context():
        print("🔍 IDENTIFICANDO PROBLEMA DE DATA")
        print("=" * 50)
        
        # Buscar registros recentes que deveriam ser de julho mas estão em agosto
        registros_suspeitos = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1)  # Registros em agosto
        ).order_by(RegistroAlimentacao.id.desc()).limit(5).all()
        
        print("📋 REGISTROS SUSPEITOS (devem ser julho mas estão agosto):")
        for reg in registros_suspeitos:
            try:
                funcionario = Funcionario.query.filter_by(id=reg.funcionario_id).first()
                nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                
                print(f"   ID {reg.id}: {nome}")
                print(f"      Data: {reg.data} (mês {reg.data.month})")
                if hasattr(reg, 'created_at') and reg.created_at:
                    print(f"      Criado: {reg.created_at}")
                print()
            except Exception as e:
                print(f"   Erro ao processar registro {reg.id}: {str(e)}")

def testar_conversao_data_manual():
    """Testa conversão de data manualmente"""
    
    print("🧪 TESTE MANUAL DE CONVERSÃO:")
    print("-" * 40)
    
    # Testar os casos que estão dando problema
    casos = [
        "2025-07-15",  # Julho - como deveria ser
        "2025-08-05",  # Agosto - como está sendo salvo
    ]
    
    for caso in casos:
        try:
            data_convertida = datetime.strptime(caso, '%Y-%m-%d').date()
            print(f"   '{caso}' → {data_convertida} (mês {data_convertida.month})")
        except Exception as e:
            print(f"   Erro em '{caso}': {str(e)}")

def encontrar_linha_problema():
    """Simula o problema para encontrar a linha específica"""
    
    print("\n🔧 SIMULANDO O PROBLEMA:")
    print("-" * 40)
    
    # Simular dados que vêm do formulário (período julho)
    data_inicio_form = "2025-07-01"
    data_fim_form = "2025-07-07"
    
    print(f"Frontend envia: {data_inicio_form} até {data_fim_form}")
    
    # Simular conversão no backend
    try:
        from datetime import timedelta
        
        inicio = datetime.strptime(data_inicio_form, '%Y-%m-%d').date()
        fim = datetime.strptime(data_fim_form, '%Y-%m-%d').date()
        
        print(f"Backend converte para: {inicio} até {fim}")
        print(f"Mês início: {inicio.month}, Mês fim: {fim.month}")
        
        # Gerar datas do período
        datas_processamento = []
        data_atual = inicio
        while data_atual <= fim:
            datas_processamento.append(data_atual)
            data_atual += timedelta(days=1)
        
        print(f"Datas geradas: {datas_processamento}")
        
        # Verificar se as datas estão corretas
        for data in datas_processamento:
            if data.month != 7:
                print(f"❌ ERRO: Data {data} não é julho!")
            else:
                print(f"✅ OK: Data {data} é julho")
                
    except Exception as e:
        print(f"❌ Erro na conversão: {str(e)}")

if __name__ == "__main__":
    identificar_problema_data()
    testar_conversao_data_manual()
    encontrar_linha_problema()