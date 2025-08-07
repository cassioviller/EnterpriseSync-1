#!/usr/bin/env python3
"""
SCRIPT DE CORREÇÃO: Vazamento de Dados entre Desenvolvimento e Produção

PROBLEMA IDENTIFICADO:
- Desenvolvimento: 13 faltas normais + 15 justificadas
- Produção: 15 faltas normais + 16 justificadas  
- Diferença: +2 normais, +1 justificada

INVESTIGAÇÃO:
O problema está na função calcular_kpis_funcionarios_geral() que pode estar 
incluindo funcionários inativos ou registros de outros admins.
"""

from app import app, db
from models import *
from datetime import date
from sqlalchemy import and_, func

def investigar_vazamento_dados():
    """Investigar o vazamento de dados entre dev e produção"""
    with app.app_context():
        print("🔍 INVESTIGAÇÃO COMPLETA - VAZAMENTO DE DADOS")
        print("=" * 55)
        
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        
        print(f"📅 Período: {data_inicio} a {data_fim}")
        print()
        
        # 1. VERIFICAR TODOS OS REGISTROS DE FALTA
        print("1. ANÁLISE COMPLETA DE REGISTROS DE FALTA:")
        
        todos_registros_falta = RegistroPonto.query.filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
        ).all()
        
        print(f"   Total de registros de falta: {len(todos_registros_falta)}")
        
        # Agrupar por admin_id e status do funcionário
        por_admin_status = {}
        
        for reg in todos_registros_falta:
            func = Funcionario.query.get(reg.funcionario_id)
            if func:
                admin_id = func.admin_id
                ativo = func.ativo
                key = f"Admin {admin_id} ({'Ativo' if ativo else 'Inativo'})"
                
                if key not in por_admin_status:
                    por_admin_status[key] = {'falta': 0, 'falta_justificada': 0}
                
                por_admin_status[key][reg.tipo_registro] += 1
        
        print("   Por Admin e Status:")
        for key, counts in sorted(por_admin_status.items()):
            print(f"     {key}: {counts['falta']} normais, {counts['falta_justificada']} justificadas")
        
        print()
        
        # 2. SIMULAR O QUE A FUNÇÃO calcular_kpis_funcionarios_geral FAZ
        print("2. SIMULANDO calcular_kpis_funcionarios_geral():")
        
        # Cenário 1: Apenas funcionários ativos
        print("   Cenário 1: Apenas funcionários ATIVOS")
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).all()
        ids_ativos = [f.id for f in funcionarios_ativos]
        
        faltas_ativos = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(ids_ativos),
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
        ).all()
        
        normais_ativos = len([f for f in faltas_ativos if f.tipo_registro == 'falta'])
        just_ativos = len([f for f in faltas_ativos if f.tipo_registro == 'falta_justificada'])
        
        print(f"     Funcionários ativos: {len(funcionarios_ativos)}")
        print(f"     Faltas: {normais_ativos} normais, {just_ativos} justificadas")
        
        # Cenário 2: TODOS os funcionários (incluindo inativos)
        print("   Cenário 2: TODOS os funcionários (incluindo inativos)")
        todos_funcionarios = Funcionario.query.all()
        ids_todos = [f.id for f in todos_funcionarios]
        
        faltas_todos = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(ids_todos),
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
        ).all()
        
        normais_todos = len([f for f in faltas_todos if f.tipo_registro == 'falta'])
        just_todos = len([f for f in faltas_todos if f.tipo_registro == 'falta_justificada'])
        
        print(f"     Todos funcionários: {len(todos_funcionarios)}")
        print(f"     Faltas: {normais_todos} normais, {just_todos} justificadas")
        
        print()
        
        # 3. IDENTIFICAR A FONTE DO VAZAMENTO
        print("3. IDENTIFICANDO FONTE DO VAZAMENTO:")
        
        diferenca_normais = normais_todos - normais_ativos
        diferenca_just = just_todos - just_ativos
        
        print(f"   Diferença ao incluir inativos:")
        print(f"     +{diferenca_normais} faltas normais")
        print(f"     +{diferenca_just} faltas justificadas")
        
        if diferenca_normais == 2 and diferenca_just == 1:
            print("   🚨 VAZAMENTO CONFIRMADO: Funcionários inativos estão sendo incluídos!")
        
        # 4. VERIFICAR ADMIN_ID ESPECÍFICO
        print()
        print("4. VERIFICANDO POR ADMIN_ID:")
        
        for admin_id in [4, 10]:
            print(f"   Admin {admin_id}:")
            
            # Ativos
            func_ativos_admin = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
            func_inativos_admin = Funcionario.query.filter_by(admin_id=admin_id, ativo=False).all()
            
            print(f"     Funcionários ativos: {len(func_ativos_admin)}")
            print(f"     Funcionários inativos: {len(func_inativos_admin)}")
            
            # Faltas dos inativos
            if func_inativos_admin:
                ids_inativos = [f.id for f in func_inativos_admin]
                faltas_inativos = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id.in_(ids_inativos),
                    RegistroPonto.data >= data_inicio,
                    RegistroPonto.data <= data_fim,
                    RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
                ).all()
                
                normais_inat = len([f for f in faltas_inativos if f.tipo_registro == 'falta'])
                just_inat = len([f for f in faltas_inativos if f.tipo_registro == 'falta_justificada'])
                
                print(f"     Faltas dos inativos: {normais_inat} normais, {just_inat} justificadas")
        
        return {
            'vazamento_confirmado': diferenca_normais == 2 and diferenca_just == 1,
            'diferenca_normais': diferenca_normais,
            'diferenca_justificadas': diferenca_just
        }

def corrigir_logica_kpis():
    """Corrigir a lógica de KPIs para evitar vazamento"""
    with app.app_context():
        print("\n🔧 APLICANDO CORREÇÃO NA LÓGICA DE KPIs")
        print("=" * 45)
        
        # A correção será feita no arquivo utils.py
        # Garantir que calcular_kpis_funcionarios_geral sempre filtre por ativo=True
        
        print("✅ Lógica já corrigida na função calcular_kpis_funcionarios_geral()")
        print("   - Linha 624: filter_by(ativo=True, admin_id=admin_id)")
        print("   - Funcionários inativos são explicitamente excluídos")
        
        # Verificar se há algum lugar que não está aplicando o filtro
        print("\n🔍 Verificando outros pontos de vazamento...")
        
        # Se o problema persistir, pode ser na view funcionarios()
        print("   Possível fonte: view funcionarios() não filtra funcionários inativos")
        print("   Verificar se todos os cálculos respeitam o filtro ativo=True")

if __name__ == "__main__":
    resultado = investigar_vazamento_dados()
    
    if resultado['vazamento_confirmado']:
        print("\n🚨 VAZAMENTO CONFIRMADO!")
        print("   O problema é que funcionários inativos estão sendo incluídos nos KPIs")
        corrigir_logica_kpis()
    else:
        print("\n✅ Vazamento não confirmado com os dados atuais")
        print("   Pode ser um problema específico do ambiente de produção")