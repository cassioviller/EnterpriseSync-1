#!/usr/bin/env python3
"""
VALIDAÇÃO: Correção do Vazamento de Funcionários Inativos

Testa se a correção aplicada em utils.py resolve o problema de vazamento.
"""

from app import app, db
from models import *
from datetime import date
from utils import calcular_kpis_funcionarios_geral

def testar_correcao_vazamento():
    """Testar se a correção resolveu o vazamento"""
    
    with app.app_context():
        print("🧪 TESTANDO CORREÇÃO DO VAZAMENTO")
        print("=" * 40)
        
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        admin_id = 10
        
        print(f"📅 Período: {data_inicio} a {data_fim}")
        print(f"🏢 Admin ID: {admin_id}")
        print()
        
        # 1. Teste ANTES da correção (simulando comportamento antigo)
        print("1. CONTAGEM MANUAL (antes da correção):")
        
        # Todos os funcionários (incluindo inativos)
        todos_funcionarios = Funcionario.query.filter_by(admin_id=admin_id).all()
        ativos_apenas = [f for f in todos_funcionarios if f.ativo]
        inativos_apenas = [f for f in todos_funcionarios if not f.ativo]
        
        print(f"   Total funcionários: {len(todos_funcionarios)}")
        print(f"   Ativos: {len(ativos_apenas)}")
        print(f"   Inativos: {len(inativos_apenas)}")
        
        # Contar faltas de todos
        faltas_todos = 0
        just_todos = 0
        
        for func in todos_funcionarios:
            faltas = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.tipo_registro == 'falta'
            ).count()
            
            just = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.tipo_registro == 'falta_justificada'
            ).count()
            
            faltas_todos += faltas
            just_todos += just
        
        print(f"   Faltas TODOS: {faltas_todos} normais, {just_todos} justificadas")
        
        # Contar faltas apenas ativos
        faltas_ativos = 0
        just_ativos = 0
        
        for func in ativos_apenas:
            faltas = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.tipo_registro == 'falta'
            ).count()
            
            just = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.tipo_registro == 'falta_justificada'
            ).count()
            
            faltas_ativos += faltas
            just_ativos += just
        
        print(f"   Faltas ATIVOS: {faltas_ativos} normais, {just_ativos} justificadas")
        print(f"   ⚠️ Vazamento: +{faltas_todos - faltas_ativos} normais, +{just_todos - just_ativos} justificadas")
        print()
        
        # 2. Teste DEPOIS da correção
        print("2. USANDO FUNÇÃO CORRIGIDA:")
        
        # Teste com incluir_inativos=False (padrão)
        kpis_sem_inativos = calcular_kpis_funcionarios_geral(
            data_inicio, data_fim, admin_id, incluir_inativos=False
        )
        
        print(f"   incluir_inativos=False:")
        print(f"     Funcionários: {kpis_sem_inativos['total_funcionarios']}")
        print(f"     Faltas: {kpis_sem_inativos['total_faltas_geral']} normais, {kpis_sem_inativos['total_faltas_justificadas_geral']} justificadas")
        
        # Teste com incluir_inativos=True
        kpis_com_inativos = calcular_kpis_funcionarios_geral(
            data_inicio, data_fim, admin_id, incluir_inativos=True
        )
        
        print(f"   incluir_inativos=True:")
        print(f"     Funcionários: {kpis_com_inativos['total_funcionarios']}")
        print(f"     Faltas: {kpis_com_inativos['total_faltas_geral']} normais, {kpis_com_inativos['total_faltas_justificadas_geral']} justificadas")
        
        print()
        
        # 3. Validação da correção
        print("3. VALIDAÇÃO DA CORREÇÃO:")
        
        correcao_ok = (
            kpis_sem_inativos['total_faltas_geral'] == faltas_ativos and
            kpis_sem_inativos['total_faltas_justificadas_geral'] == just_ativos
        )
        
        if correcao_ok:
            print("   ✅ CORREÇÃO APLICADA COM SUCESSO!")
            print("   - Função agora filtra funcionários inativos por padrão")
            print("   - Contagem de faltas corresponde apenas aos funcionários ativos")
        else:
            print("   ❌ CORREÇÃO NÃO FUNCIONOU!")
            print("   - Verificar implementação da função")
        
        print()
        
        # 4. Teste de produção simulado
        print("4. SIMULAÇÃO AMBIENTE PRODUÇÃO:")
        print("   Se produção usar incluir_inativos=False (correto):")
        print(f"     Faltas: {kpis_sem_inativos['total_faltas_geral']} normais, {kpis_sem_inativos['total_faltas_justificadas_geral']} justificadas")
        print("   Se produção usar incluir_inativos=True (problema):")
        print(f"     Faltas: {kpis_com_inativos['total_faltas_geral']} normais, {kpis_com_inativos['total_faltas_justificadas_geral']} justificadas")
        print(f"     ⚠️ Diferença: +{kpis_com_inativos['total_faltas_geral'] - kpis_sem_inativos['total_faltas_geral']} normais, +{kpis_com_inativos['total_faltas_justificadas_geral'] - kpis_sem_inativos['total_faltas_justificadas_geral']} justificadas")
        
        return {
            'correcao_ok': correcao_ok,
            'faltas_ativos': (faltas_ativos, just_ativos),
            'faltas_todos': (faltas_todos, just_todos),
            'funcao_sem_inativos': (kpis_sem_inativos['total_faltas_geral'], kpis_sem_inativos['total_faltas_justificadas_geral']),
            'funcao_com_inativos': (kpis_com_inativos['total_faltas_geral'], kpis_com_inativos['total_faltas_justificadas_geral'])
        }

if __name__ == "__main__":
    resultado = testar_correcao_vazamento()
    
    if resultado['correcao_ok']:
        print("\n🎉 CORREÇÃO VALIDADA!")
        print("   A função agora está protegida contra vazamento de funcionários inativos")
    else:
        print("\n⚠️ CORREÇÃO PRECISA DE AJUSTES")
        print("   Verificar implementação e testes adicionais")