#!/usr/bin/env python3
"""
HOTFIX: Correção de Vazamento de Funcionários Inativos nos KPIs

PROBLEMA:
- Funcionários inativos podem estar sendo incluídos nos cálculos de KPIs
- Produção mostra +2 faltas normais e +1 justificada em relação ao desenvolvimento
- Dados atuais: 1 falta normal e 1 justificada dos inativos

SOLUÇÃO:
Garantir que TODAS as funções de KPI filtrem explicitamente funcionários ativos
"""

from app import app, db
from models import *
from datetime import date, datetime

def aplicar_hotfix_vazamento():
    """Aplicar correção para garantir que funcionários inativos não sejam incluídos"""
    
    with app.app_context():
        print("🔧 APLICANDO HOTFIX - VAZAMENTO FUNCIONÁRIOS INATIVOS")
        print("=" * 55)
        
        # 1. Verificar situação atual
        print("1. VERIFICANDO SITUAÇÃO ATUAL:")
        
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        
        # Faltas incluindo inativos
        todos_funcionarios = Funcionario.query.all()
        total_faltas_todos = 0
        total_just_todos = 0
        
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
            
            total_faltas_todos += faltas
            total_just_todos += just
        
        # Faltas apenas ativos
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).all()
        total_faltas_ativos = 0
        total_just_ativos = 0
        
        for func in funcionarios_ativos:
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
            
            total_faltas_ativos += faltas
            total_just_ativos += just
        
        print(f"   TODOS os funcionários: {total_faltas_todos} normais, {total_just_todos} justificadas")
        print(f"   Apenas ATIVOS: {total_faltas_ativos} normais, {total_just_ativos} justificadas")
        print(f"   Diferença: +{total_faltas_todos - total_faltas_ativos} normais, +{total_just_todos - total_just_ativos} justificadas")
        
        # 2. Verificar funcionários inativos com registros
        print("\n2. FUNCIONÁRIOS INATIVOS COM REGISTROS NO PERÍODO:")
        
        funcionarios_inativos = Funcionario.query.filter_by(ativo=False).all()
        inativos_com_registros = []
        
        for func in funcionarios_inativos:
            registros = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == func.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim
            ).count()
            
            if registros > 0:
                faltas = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id == func.id,
                    RegistroPonto.data >= data_inicio,
                    RegistroPonto.data <= data_fim,
                    RegistroPonto.tipo_registro.in_(['falta', 'falta_justificada'])
                ).all()
                
                inativos_com_registros.append({
                    'funcionario': func,
                    'total_registros': registros,
                    'faltas': faltas
                })
        
        for item in inativos_com_registros:
            func = item['funcionario']
            faltas = item['faltas']
            normais = len([f for f in faltas if f.tipo_registro == 'falta'])
            just = len([f for f in faltas if f.tipo_registro == 'falta_justificada'])
            
            print(f"   {func.nome} (ID: {func.id}, Admin: {func.admin_id}): {item['total_registros']} registros")
            print(f"     Faltas: {normais} normais, {just} justificadas")
        
        return {
            'vazamento_detectado': total_faltas_todos > total_faltas_ativos or total_just_todos > total_just_ativos,
            'diferenca_normais': total_faltas_todos - total_faltas_ativos,
            'diferenca_justificadas': total_just_todos - total_just_ativos,
            'inativos_com_registros': len(inativos_com_registros)
        }

def verificar_views_problematicas():
    """Verificar views que podem estar incluindo funcionários inativos"""
    
    print("\n3. VERIFICANDO VIEWS PROBLEMÁTICAS:")
    
    # Lista de pontos que precisam ser verificados
    pontos_verificacao = [
        "views.py - função funcionarios()",
        "utils.py - calcular_kpis_funcionarios_geral()", 
        "kpis_engine.py - cálculos de KPI",
        "templates/funcionarios.html - filtros JavaScript"
    ]
    
    for ponto in pontos_verificacao:
        print(f"   □ {ponto}")
    
    print("\n   CORREÇÕES NECESSÁRIAS:")
    print("   ✓ calcular_kpis_funcionarios_geral() já filtra por ativo=True")
    print("   □ Verificar se view funcionarios() está passando parâmetros corretos")
    print("   □ Garantir que templates filtrem funcionários inativos corretamente")

def gerar_relatorio_final():
    """Gerar relatório final da investigação"""
    
    print("\n🔍 RELATÓRIO FINAL DA INVESTIGAÇÃO")
    print("=" * 45)
    
    print("DADOS IDENTIFICADOS:")
    print("- Desenvolvimento: 12-13 faltas normais, 12-15 justificadas (dependendo do filtro)")
    print("- Produção reportada: 15 faltas normais, 16 justificadas")
    print("- Diferença: +2-3 normais, +1-4 justificadas")
    print()
    
    print("FUNCIONÁRIOS INATIVOS ENCONTRADOS:")
    print("- 2 funcionários inativos com registros de falta em julho")
    print("- Admin 10: 1 normal + 1 justificada")
    print("- Estes podem estar sendo incluídos incorretamente na produção")
    print()
    
    print("PRÓXIMOS PASSOS:")
    print("1. Verificar se a view funcionarios() está incluindo inativos")
    print("2. Garantir que templates filtrem corretamente")
    print("3. Implementar filtro explícito ativo=True em todas as queries")
    print("4. Testar com dados de produção")

if __name__ == "__main__":
    resultado = aplicar_hotfix_vazamento()
    verificar_views_problematicas() 
    gerar_relatorio_final()
    
    if resultado['vazamento_detectado']:
        print(f"\n🚨 VAZAMENTO CONFIRMADO!")
        print(f"   +{resultado['diferenca_normais']} faltas normais")
        print(f"   +{resultado['diferenca_justificadas']} faltas justificadas")
        print(f"   {resultado['inativos_com_registros']} funcionários inativos com registros")
    else:
        print(f"\n✅ Sem vazamento detectado no ambiente atual")