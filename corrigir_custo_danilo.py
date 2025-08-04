#!/usr/bin/env python3
"""
🔧 CORRIGIR: Custo de mão de obra baseado na imagem do Antonio
Salário: R$ 2.153,26
Horas extras: 8.2h  
Faltas: 1
Custo atual (incorreto): R$ 2.443,83
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def calcular_custo_correto_antonio():
    """Calcular custo correto baseado nos dados da imagem"""
    print("🧮 CÁLCULO CORRETO - ANTONIO FERNANDES DA SILVA")
    print("=" * 60)
    
    # Dados da imagem
    salario_base = 2153.26
    horas_extras = 8.2
    faltas = 1
    custo_atual_sistema = 2443.83
    
    print(f"💰 Salário base: R$ {salario_base:.2f}")
    print(f"⏰ Horas extras: {horas_extras:.1f}h")
    print(f"❌ Faltas: {faltas} dia(s)")
    print(f"🤖 Sistema mostra: R$ {custo_atual_sistema:.2f}")
    
    # Julho 2025 tem 23 dias úteis
    dias_uteis_julho = 23
    valor_por_dia = salario_base / dias_uteis_julho
    
    print(f"\n📅 Dias úteis julho: {dias_uteis_julho}")
    print(f"💵 Valor por dia: R$ {valor_por_dia:.2f}")
    
    # Desconto por falta
    desconto_falta = valor_por_dia * faltas
    salario_apos_falta = salario_base - desconto_falta
    
    print(f"💸 Desconto falta: R$ {desconto_falta:.2f}")
    print(f"💰 Salário após falta: R$ {salario_apos_falta:.2f}")
    
    # Valor das horas extras
    # Assumindo 8.8h/dia (padrão serralheiro)
    horas_mensais = dias_uteis_julho * 8.8
    valor_hora = salario_base / horas_mensais
    
    print(f"\n⏱️  Horas mensais: {horas_mensais:.1f}h")
    print(f"💲 Valor hora: R$ {valor_hora:.2f}")
    
    # Sábado trabalho = 50% adicional, normal = 60%
    # Pela imagem, vejo que tem 7.9h no sábado (50%) 
    # Assumindo 0.3h extras normais (60%)
    
    extras_sabado = 7.9  # Da imagem do sábado
    extras_normais = horas_extras - extras_sabado  # 8.2 - 7.9 = 0.3h
    
    valor_extras_sabado = extras_sabado * valor_hora * 1.5  # 50% adicional
    valor_extras_normais = extras_normais * valor_hora * 1.6  # 60% adicional
    total_valor_extras = valor_extras_sabado + valor_extras_normais
    
    print(f"🔢 Extras sábado: {extras_sabado:.1f}h × R$ {valor_hora:.2f} × 1.5 = R$ {valor_extras_sabado:.2f}")
    print(f"🔢 Extras normais: {extras_normais:.1f}h × R$ {valor_hora:.2f} × 1.6 = R$ {valor_extras_normais:.2f}")
    print(f"💰 Total extras: R$ {total_valor_extras:.2f}")
    
    # Custo total correto
    custo_correto = salario_apos_falta + total_valor_extras
    
    print(f"\n🎯 CUSTO TOTAL CORRETO:")
    print(f"   R$ {salario_apos_falta:.2f} (salário - falta) + R$ {total_valor_extras:.2f} (extras)")
    print(f"   = R$ {custo_correto:.2f}")
    
    diferenca = custo_atual_sistema - custo_correto
    print(f"\n📊 COMPARAÇÃO:")
    print(f"   Sistema atual: R$ {custo_atual_sistema:.2f}")
    print(f"   Cálculo correto: R$ {custo_correto:.2f}")
    print(f"   Diferença: R$ {diferenca:.2f} ({'MAIOR' if diferenca > 0 else 'MENOR'})")
    
    return custo_correto

def analisar_problema_kpi_engine():
    """Analisar o problema no método _calcular_custo_mensal"""
    print(f"\n🔍 PROBLEMA NO MÉTODO _calcular_custo_mensal")
    print("=" * 60)
    
    print("❌ PROBLEMAS IDENTIFICADOS:")
    print("   1. Não desconta faltas do salário base")
    print("   2. Calcula baseado em 'horas trabalhadas' em vez de salário fixo")
    print("   3. Pode estar contando horas extras como horas normais")
    print("   4. Lógica não segue: Salário - Faltas + Valor Extras")
    
    print(f"\n📝 LÓGICA ATUAL (INCORRETA):")
    print("   • Soma todas as horas por tipo")
    print("   • Multiplica por valor_hora com percentuais")
    print("   • Não considera salário fixo mensal")
    print("   • Não desconta faltas")
    
    print(f"\n✅ LÓGICA CORRETA:")
    print("   • Salário fixo mensal")
    print("   • MENOS: valor_dia × quantidade_faltas")
    print("   • MAIS: valor das horas extras (hora × percentual)")
    print("   • = Custo total real")

def testar_com_funcionarios_reais():
    """Testar com funcionários que existem no sistema"""
    print(f"\n🧪 TESTE COM FUNCIONÁRIOS REAIS")
    print("=" * 60)
    
    # Buscar funcionários com dados similares
    funcionarios = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            f.salario,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras,
            COUNT(CASE WHEN r.tipo_registro = 'falta' THEN 1 END) as faltas
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE f.salario > 2000
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        ORDER BY f.salario DESC
        LIMIT 5
    """)).fetchall()
    
    print("👥 FUNCIONÁRIOS COM SALÁRIO > R$ 2.000:")
    
    engine = KPIsEngine()
    
    for func in funcionarios:
        print(f"\n👤 {func.nome}")
        print(f"   💰 Salário: R$ {func.salario:.2f}")
        print(f"   ⏰ Extras: {func.total_extras:.1f}h")
        print(f"   ❌ Faltas: {func.faltas}")
        
        # Calcular KPI atual
        kpis = engine.calcular_kpis_funcionario(
            func.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        # Calcular correto manualmente
        dias_uteis = 23
        valor_dia = func.salario / dias_uteis
        desconto_faltas = valor_dia * func.faltas
        salario_liquido = func.salario - desconto_faltas
        
        # Valor extras (estimativa 50% adicional)
        horas_mensais = dias_uteis * 8.8
        valor_hora = func.salario / horas_mensais
        valor_extras = func.total_extras * valor_hora * 1.5
        
        custo_correto = salario_liquido + valor_extras
        
        print(f"   🤖 KPI: R$ {kpis['custo_mao_obra']:.2f}")
        print(f"   ✅ Correto: R$ {custo_correto:.2f}")
        print(f"   📊 Dif: R$ {abs(kpis['custo_mao_obra'] - custo_correto):.2f}")
        
        if abs(kpis['custo_mao_obra'] - custo_correto) > 200:
            print(f"   ❌ GRANDE DIFERENÇA!")

def propor_correcao_metodo():
    """Propor correção do método _calcular_custo_mensal"""
    print(f"\n🔧 PROPOSTA DE CORREÇÃO")
    print("=" * 60)
    
    print("📝 SUBSTITUIR método _calcular_custo_mensal por:")
    print("""
def _calcular_custo_mensal(self, funcionario_id, data_inicio, data_fim):
    \"\"\"Calcular custo mensal CORRETO: salário - faltas + horas extras\"\"\"
    funcionario = Funcionario.query.get(funcionario_id)
    if not funcionario or not funcionario.salario:
        return 0.0
    
    salario_base = float(funcionario.salario)
    
    # 1. Calcular dias úteis do período
    dias_uteis = self._calcular_dias_uteis_periodo(data_inicio, data_fim)
    if dias_uteis == 0:
        return salario_base  # Fallback
    
    valor_por_dia = salario_base / dias_uteis
    
    # 2. Contar faltas e descontar do salário
    faltas = db.session.query(func.count(RegistroPonto.id)).filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
        RegistroPonto.tipo_registro == 'falta'
    ).scalar() or 0
    
    desconto_faltas = valor_por_dia * faltas
    salario_liquido = salario_base - desconto_faltas
    
    # 3. Calcular valor das horas extras
    valor_horas_extras = self._calcular_valor_horas_extras(funcionario_id, data_inicio, data_fim)
    
    # 4. Custo total = salário líquido + horas extras
    return salario_liquido + valor_horas_extras
    """)

if __name__ == "__main__":
    with app.app_context():
        print("🔧 ANÁLISE E CORREÇÃO DO CUSTO DE MÃO DE OBRA")
        print("=" * 80)
        print("📋 Baseado nos dados da imagem do Antonio Fernandes da Silva")
        print("=" * 80)
        
        # 1. Calcular custo correto do Antonio
        custo_correto_antonio = calcular_custo_correto_antonio()
        
        # 2. Analisar problema na engine
        analisar_problema_kpi_engine()
        
        # 3. Testar com funcionários reais
        testar_com_funcionarios_reais()
        
        # 4. Propor correção
        propor_correcao_metodo()
        
        print(f"\n🎯 CONCLUSÃO:")
        print(f"   📊 Antonio deveria custar: R$ {custo_correto_antonio:.2f}")
        print(f"   🤖 Sistema mostra: R$ 2.443,83")
        print(f"   ❌ Diferença: R$ {abs(2443.83 - custo_correto_antonio):.2f}")
        print(f"   🔧 Solução: Corrigir método _calcular_custo_mensal")
        print(f"   ✅ Nova lógica: Salário - Faltas + Horas Extras")