#!/usr/bin/env python3
"""
DEBUG URGENTE: Data do período sendo salva incorreta
Problema: Lançamento de julho (mes 7) está sendo salvo como agosto (mes atual)
"""

from app import app, db
from models import RegistroAlimentacao, Funcionario
from datetime import datetime, date

def analisar_problema_data():
    """Analisa o problema específico das datas incorretas"""
    
    with app.app_context():
        print("🚨 DEBUG CRÍTICO: Datas de Alimentação Incorretas")
        print("=" * 60)
        
        # Buscar registros mais recentes
        registros_recentes = RegistroAlimentacao.query.order_by(
            RegistroAlimentacao.created_at.desc()
        ).limit(10).all()
        
        print("📊 ÚLTIMOS 10 REGISTROS CRIADOS:")
        for reg in registros_recentes:
            funcionario = Funcionario.query.get(reg.funcionario_id)
            nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            
            # Diferença entre data do registro e data de criação
            diferenca = (reg.created_at.date() - reg.data).days
            
            status = "✅ OK" if abs(diferenca) <= 1 else f"❌ ERRO ({diferenca} dias)"
            
            print(f"   ID {reg.id}: {nome}")
            print(f"      Data registro: {reg.data} (mês {reg.data.month})")
            print(f"      Data criação: {reg.created_at.date()} (mês {reg.created_at.month})")
            print(f"      Status: {status}")
            print()
        
        # Verificar registros problemáticos específicos
        registros_agosto = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1),
            RegistroAlimentacao.created_at >= datetime(2025, 8, 1)
        ).count()
        
        registros_julho = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 7, 1),
            RegistroAlimentacao.data < date(2025, 8, 1)
        ).count()
        
        print(f"📈 ESTATÍSTICAS:")
        print(f"   Registros em agosto: {registros_agosto}")
        print(f"   Registros em julho: {registros_julho}")
        
        # Verificar se há registros criados hoje mas com data de julho
        hoje = date.today()
        registros_hoje_julho = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.created_at >= datetime.combine(hoje, datetime.min.time()),
            RegistroAlimentacao.data < date(2025, 8, 1)
        ).all()
        
        if registros_hoje_julho:
            print(f"\n⚠️ ENCONTRADOS {len(registros_hoje_julho)} registros criados hoje com data de julho:")
            for reg in registros_hoje_julho:
                funcionario = Funcionario.query.get(reg.funcionario_id)
                nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                print(f"   • {nome}: {reg.data} (criado hoje)")

def testar_conversao_data_frontend():
    """Testa se o problema é na conversão do frontend"""
    
    print("\n🧪 TESTANDO CONVERSÃO DE DATAS:")
    print("-" * 40)
    
    # Simular dados que podem vir do frontend
    casos_teste = [
        "2025-07-15",  # Formato ISO
        "15/07/2025",  # Formato brasileiro
        "07/15/2025",  # Formato americano
        "2025-7-15",   # Sem zero à esquerda
    ]
    
    for caso in casos_teste:
        print(f"\n📅 Testando: '{caso}'")
        
        try:
            # Tentar conversão ISO (padrão do HTML date input)
            if '-' in caso and len(caso.split('-')[0]) == 4:  # YYYY-MM-DD
                data_convertida = datetime.strptime(caso, '%Y-%m-%d').date()
                print(f"   ✅ ISO: {data_convertida} (mês {data_convertida.month})")
            
            # Tentar formato brasileiro
            elif '/' in caso and len(caso.split('/')[2]) == 4:  # DD/MM/YYYY
                data_convertida = datetime.strptime(caso, '%d/%m/%Y').date()
                print(f"   ✅ BR: {data_convertida} (mês {data_convertida.month})")
            
            else:
                print(f"   ❓ Formato não reconhecido")
                
        except Exception as e:
            print(f"   ❌ Erro na conversão: {str(e)}")

if __name__ == "__main__":
    analisar_problema_data()
    testar_conversao_data_frontend()