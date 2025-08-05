#!/usr/bin/env python3
"""
CORREÇÃO CRÍTICA: Sistema de Alimentação por Período
Identificação e correção do problema de datas incorretas
"""

from app import app, db
from models import RegistroAlimentacao, Funcionario
from datetime import datetime, date, timedelta

def verificar_registros_agosto():
    """Verifica registros em agosto que deveriam ser julho"""
    
    with app.app_context():
        print("🚨 VERIFICAÇÃO: Registros de Agosto que deveriam ser Julho")
        print("=" * 60)
        
        # Buscar registros em agosto (suspeitos)
        registros_agosto = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1),
            RegistroAlimentacao.data <= date(2025, 8, 31)
        ).order_by(RegistroAlimentacao.id.desc()).limit(20).all()
        
        print(f"📊 Encontrados {len(registros_agosto)} registros em agosto:")
        
        for reg in registros_agosto:
            funcionario = Funcionario.query.filter_by(id=reg.funcionario_id).first()
            nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            
            print(f"   ID {reg.id}: {nome}")
            print(f"      Data: {reg.data} ({reg.data.strftime('%d/%m/%Y')})")
            print(f"      Tipo: {reg.tipo} - Valor: R$ {reg.valor}")
            print()
        
        return registros_agosto

def corrigir_datas_incorretas():
    """Corrige as datas dos registros que foram salvos incorretamente"""
    
    with app.app_context():
        print("\n🔧 CORREÇÃO: Alterar registros de agosto para julho")
        print("-" * 60)
        
        # Identificar registros que claramente deveriam ser julho
        # (baseado na imagem do usuário que mostra registros em agosto)
        registros_para_corrigir = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 3),
            RegistroAlimentacao.data <= date(2025, 8, 5)
        ).all()
        
        if not registros_para_corrigir:
            print("✅ Nenhum registro para corrigir encontrado")
            return
        
        print(f"📋 Encontrados {len(registros_para_corrigir)} registros para corrigir:")
        
        corrigidos = 0
        for reg in registros_para_corrigir:
            funcionario = Funcionario.query.filter_by(id=reg.funcionario_id).first()
            nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            
            # Calcular data correta (subtrair um mês)
            data_original = reg.data
            data_corrigida = date(2025, 7, data_original.day)
            
            print(f"🔄 {nome}:")
            print(f"   Antes: {data_original.strftime('%d/%m/%Y')} (mês {data_original.month})")
            print(f"   Depois: {data_corrigida.strftime('%d/%m/%Y')} (mês {data_corrigida.month})")
            
            # Verificar se já existe um registro na data corrigida
            registro_existente = RegistroAlimentacao.query.filter_by(
                funcionario_id=reg.funcionario_id,
                data=data_corrigida,
                tipo=reg.tipo
            ).first()
            
            if registro_existente:
                print(f"   ⚠️ Já existe registro em {data_corrigida}, removendo duplicata")
                db.session.delete(reg)
            else:
                print(f"   ✅ Corrigindo data")
                reg.data = data_corrigida
            
            corrigidos += 1
        
        try:
            db.session.commit()
            print(f"\n🎯 {corrigidos} registros corrigidos com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao salvar: {str(e)}")
            db.session.rollback()

def adicionar_debug_frontend():
    """Adiciona debug no código para identificar o problema"""
    
    print("\n🔍 ADICIONANDO DEBUG NO FRONTEND")
    print("-" * 40)
    
    # Simular o que pode estar acontecendo no frontend
    casos_problematicos = [
        # Caso 1: Data sendo convertida para timestamp
        ("2025-07-15", "Seleção normal de julho"),
        
        # Caso 2: Timezone causing issues
        ("2025-07-15T00:00:00", "Com timestamp"),
        
        # Caso 3: JavaScript Date object
        ("new Date('2025-07-15')", "JavaScript Date"),
    ]
    
    for caso, descricao in casos_problematicos:
        print(f"📅 {descricao}: {caso}")
        
        # Se for uma string de data simples
        if caso.startswith("2025-") and "T" not in caso and "Date" not in caso:
            try:
                data_convertida = datetime.strptime(caso, '%Y-%m-%d').date()
                print(f"   Resultado: {data_convertida} (mês {data_convertida.month})")
            except:
                print(f"   ❌ Erro na conversão")
        else:
            print(f"   ⚠️ Formato complexo - requer análise no navegador")

if __name__ == "__main__":
    verificar_registros_agosto()
    corrigir_datas_incorretas()
    adicionar_debug_frontend()