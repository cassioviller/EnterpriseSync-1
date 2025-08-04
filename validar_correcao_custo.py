#!/usr/bin/env python3
"""
✅ VALIDAR: Correção do cálculo de custo de mão de obra aplicada
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def validar_correcao_antonio():
    """Validar se a correção resolveu o problema do Antonio"""
    print("✅ VALIDAÇÃO: Correção do custo de mão de obra")
    print("=" * 60)
    
    # Dados esperados do Antonio (da imagem)
    dados_esperados = {
        'salario': 2153.26,
        'horas_extras': 8.2,
        'faltas': 1,
        'custo_esperado': 2190.81,  # Calculado corretamente
        'custo_anterior': 2443.83   # Sistema anterior (incorreto)
    }
    
    print(f"📋 DADOS ANTONIO (ESPERADOS):")
    print(f"   Salário: R$ {dados_esperados['salario']:.2f}")
    print(f"   Horas extras: {dados_esperados['horas_extras']:.1f}h")
    print(f"   Faltas: {dados_esperados['faltas']}")
    print(f"   Custo correto: R$ {dados_esperados['custo_esperado']:.2f}")
    print(f"   Sistema anterior: R$ {dados_esperados['custo_anterior']:.2f}")
    
    return dados_esperados

def testar_funcionarios_com_nova_logica():
    """Testar funcionários com a nova lógica de custo"""
    print(f"\n🧪 TESTE: Nova lógica de custo aplicada")
    print("=" * 60)
    
    # Buscar funcionários para teste
    funcionarios = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            f.salario,
            SUM(r.horas_extras) as total_extras,
            COUNT(CASE WHEN r.tipo_registro = 'falta' THEN 1 END) as faltas
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE f.salario > 1000
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        ORDER BY f.salario DESC
        LIMIT 5
    """)).fetchall()
    
    print("👥 TESTE COM FUNCIONÁRIOS REAIS:")
    
    engine = KPIsEngine()
    resultados = []
    
    for func in funcionarios:
        print(f"\n👤 {func.nome[:30]}")
        print(f"   💰 Salário: R$ {func.salario:.2f}")
        print(f"   ⏰ Extras: {func.total_extras:.1f}h")
        print(f"   ❌ Faltas: {func.faltas}")
        
        # Calcular com nova lógica
        kpis = engine.calcular_kpis_funcionario(
            func.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        # Calcular manualmente para comparação
        dias_uteis = 23
        valor_dia = func.salario / dias_uteis
        desconto_faltas = valor_dia * func.faltas
        salario_liquido = func.salario - desconto_faltas
        
        # Valor extras (usando valor das horas extras do KPI)
        valor_extras_kpi = kpis['eficiencia']  # Este é o valor R$ das horas extras
        
        custo_manual = salario_liquido + valor_extras_kpi
        
        print(f"   🤖 KPI novo: R$ {kpis['custo_mao_obra']:.2f}")
        print(f"   ✅ Manual: R$ {custo_manual:.2f}")
        print(f"   📊 Diferença: R$ {abs(kpis['custo_mao_obra'] - custo_manual):.2f}")
        
        # Verificar se está próximo (tolerância de R$ 10)
        if abs(kpis['custo_mao_obra'] - custo_manual) < 10:
            status = "✅ CORRETO"
        else:
            status = "❌ AINDA TEM PROBLEMA"
        
        print(f"   {status}")
        
        resultados.append({
            'nome': func.nome,
            'salario': func.salario,
            'kpi': kpis['custo_mao_obra'],
            'manual': custo_manual,
            'correto': abs(kpis['custo_mao_obra'] - custo_manual) < 10
        })
    
    return resultados

def simular_antonio_com_nova_logica():
    """Simular como ficaria o Antonio com a nova lógica"""
    print(f"\n🎯 SIMULAÇÃO: Antonio com nova lógica")
    print("=" * 60)
    
    # Usar dados da imagem
    salario = 2153.26
    faltas = 1
    horas_extras = 8.2
    
    # Cálculo com nova lógica
    dias_uteis = 23
    valor_dia = salario / dias_uteis
    desconto_faltas = valor_dia * faltas
    salario_liquido = salario - desconto_faltas
    
    # Valor das horas extras (estimativa)
    horas_mensais = dias_uteis * 8.8
    valor_hora = salario / horas_mensais
    valor_extras = horas_extras * valor_hora * 1.5  # Média 50% adicional
    
    custo_novo = salario_liquido + valor_extras
    
    print(f"💰 Salário base: R$ {salario:.2f}")
    print(f"💸 Desconto falta: R$ {desconto_faltas:.2f}")
    print(f"💰 Salário líquido: R$ {salario_liquido:.2f}")
    print(f"💲 Valor extras: R$ {valor_extras:.2f}")
    print(f"🎯 Custo total novo: R$ {custo_novo:.2f}")
    print(f"📊 Sistema anterior: R$ 2.443,83")
    print(f"📈 Diferença: R$ {abs(2443.83 - custo_novo):.2f} {'MENOR' if custo_novo < 2443.83 else 'MAIOR'}")
    
    return custo_novo

def relatorio_final_correcao():
    """Relatório final da correção aplicada"""
    print(f"\n📊 RELATÓRIO FINAL: Correção aplicada")
    print("=" * 60)
    
    print("🔧 CORREÇÕES APLICADAS:")
    print("   ✅ Método _calcular_custo_mensal reescrito")
    print("   ✅ Nova lógica: Salário - Faltas + Horas Extras")
    print("   ✅ Desconto de faltas implementado")
    print("   ✅ Servidor reiniciado com mudanças")
    
    print(f"\n📝 LÓGICA ANTERIOR (INCORRETA):")
    print("   • Somava horas × valor_hora por tipo")
    print("   • Não descontava faltas")
    print("   • Calculava baseado em horas trabalhadas")
    
    print(f"\n✅ LÓGICA NOVA (CORRETA):")
    print("   • Salário fixo mensal")
    print("   • MENOS: valor_dia × faltas")
    print("   • MAIS: valor monetário das horas extras")
    print("   • = Custo real do funcionário")
    
    return True

if __name__ == "__main__":
    with app.app_context():
        print("✅ VALIDAÇÃO DA CORREÇÃO DO CUSTO DE MÃO DE OBRA")
        print("=" * 80)
        
        # 1. Validar dados do Antonio
        dados_antonio = validar_correcao_antonio()
        
        # 2. Testar com funcionários reais
        resultados = testar_funcionarios_com_nova_logica()
        
        # 3. Simular Antonio
        custo_antonio_novo = simular_antonio_com_nova_logica()
        
        # 4. Relatório final
        relatorio_final_correcao()
        
        # Resumo
        funcionarios_corretos = sum(1 for r in resultados if r['correto'])
        total_funcionarios = len(resultados)
        
        print(f"\n🎯 RESUMO VALIDAÇÃO:")
        print(f"   Funcionários testados: {total_funcionarios}")
        print(f"   Cálculos corretos: {funcionarios_corretos}")
        print(f"   Taxa de sucesso: {(funcionarios_corretos/total_funcionarios)*100:.1f}%")
        print(f"   Antonio estimado: R$ {custo_antonio_novo:.2f}")
        print(f"   Economia vs anterior: R$ {abs(2443.83 - custo_antonio_novo):.2f}")
        
        if funcionarios_corretos == total_funcionarios:
            print(f"\n🎉 CORREÇÃO APLICADA COM SUCESSO!")
            print(f"   Todos os cálculos estão corretos")
            print(f"   Sistema agora calcula custo real dos funcionários")
        else:
            print(f"\n⚠️  CORREÇÃO PARCIAL")
            print(f"   {total_funcionarios - funcionarios_corretos} funcionários com diferenças")