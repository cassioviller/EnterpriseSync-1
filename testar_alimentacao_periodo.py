#!/usr/bin/env python3
"""
Teste para verificar registros de alimentação por período
Analisa se as datas estão sendo salvas corretamente
"""
from app import app, db
from models import RegistroAlimentacao, Funcionario, Obra
from datetime import datetime, timedelta, date

with app.app_context():
    print("🔍 ANÁLISE DE REGISTROS DE ALIMENTAÇÃO POR PERÍODO")
    print("=" * 60)
    
    # Buscar registros mais recentes (últimos 7 dias)
    data_limite = date.today() - timedelta(days=7)
    
    registros = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.data >= data_limite
    ).order_by(RegistroAlimentacao.data.desc(), RegistroAlimentacao.id.desc()).all()
    
    print(f"📊 Encontrados {len(registros)} registros dos últimos 7 dias")
    print()
    
    # Agrupar por data para identificar padrões
    registros_por_data = {}
    
    for registro in registros:
        data_str = registro.data.strftime('%Y-%m-%d')
        if data_str not in registros_por_data:
            registros_por_data[data_str] = []
        registros_por_data[data_str].append(registro)
    
    # Mostrar padrões suspeitos
    for data_str, regs_data in registros_por_data.items():
        print(f"📅 {data_str} - {len(regs_data)} registros")
        
        # Agrupar por funcionário para detectar duplicatas
        por_funcionario = {}
        for reg in regs_data:
            func_id = reg.funcionario_id
            if func_id not in por_funcionario:
                por_funcionario[func_id] = []
            por_funcionario[func_id].append(reg)
        
        # Mostrar detalhes
        for func_id, regs_func in por_funcionario.items():
            funcionario = Funcionario.query.get(func_id)
            nome_func = funcionario.nome if funcionario else f"ID:{func_id}"
            
            if len(regs_func) > 1:
                print(f"   ⚠️ {nome_func}: {len(regs_func)} registros (DUPLICADO?)")
                for reg in regs_func:
                    print(f"      • ID {reg.id}: {reg.tipo} - R$ {reg.valor} - {reg.created_at}")
            else:
                reg = regs_func[0]
                print(f"   ✅ {nome_func}: {reg.tipo} - R$ {reg.valor}")
        print()
    
    # Verificar se há registros com datas muito antigas ou futuras
    print("🔍 VERIFICANDO DATAS SUSPEITAS:")
    
    registros_suspeitos = RegistroAlimentacao.query.filter(
        db.or_(
            RegistroAlimentacao.data < date(2025, 1, 1),  # Muito antiga
            RegistroAlimentacao.data > date.today() + timedelta(days=30)  # Muito futura
        )
    ).all()
    
    if registros_suspeitos:
        print(f"❌ Encontrados {len(registros_suspeitos)} registros com datas suspeitas:")
        for reg in registros_suspeitos:
            funcionario = Funcionario.query.get(reg.funcionario_id)
            nome_func = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            print(f"   • ID {reg.id}: {nome_func} - {reg.data} - Criado em {reg.created_at}")
    else:
        print("✅ Nenhuma data suspeita encontrada")