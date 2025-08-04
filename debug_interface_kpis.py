#!/usr/bin/env python3
"""
🔍 DEBUG: Interface dos KPIs - Por que mostra 0.3h em vez do valor correto?
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def debug_kpi_interface():
    """Debug específico do que está sendo enviado para a interface"""
    print("🔍 DEBUG: Interface KPIs - Funcionário Danilo")
    print("=" * 60)
    
    # Buscar Danilo (funcionário da imagem)
    danilo = Funcionario.query.filter(Funcionario.nome.like('%Danilo%')).first()
    
    if not danilo:
        print("❌ Danilo não encontrado")
        return
    
    print(f"👤 Funcionário: {danilo.nome} (ID: {danilo.id})")
    
    # Calcular KPIs como a interface faz
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        danilo.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"\n📊 KPIs CALCULADOS PELO ENGINE:")
    for chave, valor in kpis.items():
        print(f"   {chave}: {valor}")
    
    # Verificar especificamente horas extras
    total_extras_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == danilo.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"\n🔍 VERIFICAÇÃO DIRETA:")
    print(f"   Horas Extras (DB): {total_extras_db:.1f}h")
    print(f"   Horas Extras (KPI): {kpis['horas_extras']:.1f}h")
    
    # Listar registros do Danilo
    registros = db.session.execute(text("""
        SELECT 
            data,
            tipo_registro,
            horas_trabalhadas,
            horas_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        ORDER BY data
    """), {'func_id': danilo.id}).fetchall()
    
    print(f"\n📋 REGISTROS DANILO ({len(registros)}):")
    for reg in registros[:10]:  # Primeiros 10
        print(f"   {reg.data} | {reg.tipo_registro} | "
              f"Trab: {reg.horas_trabalhadas:.1f}h | "
              f"Extras: {reg.horas_extras or 0:.1f}h")
    
    if len(registros) > 10:
        print(f"   ... e mais {len(registros) - 10} registros")
    
    return danilo, kpis

def testar_funcionario_com_extras():
    """Testar funcionário que sabemos ter horas extras"""
    print(f"\n🧪 TESTE: Funcionário com Horas Extras Conhecidas")
    print("=" * 60)
    
    # Buscar funcionário com mais horas extras
    funcionario = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND r.horas_extras IS NOT NULL
            AND r.horas_extras > 0
        GROUP BY f.id, f.nome
        ORDER BY total_extras DESC
        LIMIT 1
    """)).fetchone()
    
    if not funcionario:
        print("❌ Nenhum funcionário com horas extras encontrado")
        return None, None
    
    print(f"👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
    print(f"⚡ Horas Extras (DB): {funcionario.total_extras:.1f}h")
    
    # Calcular KPI
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"🤖 Horas Extras (KPI): {kpis['horas_extras']:.1f}h")
    print(f"💰 Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    
    diferenca = abs(funcionario.total_extras - kpis['horas_extras'])
    if diferenca < 0.1:
        print(f"✅ KPI CORRETO! Diferença: {diferenca:.2f}h")
        status = "CORRETO"
    else:
        print(f"❌ KPI INCORRETO! Diferença: {diferenca:.2f}h")
        status = "INCORRETO"
    
    return funcionario, kpis, status

def debug_funcao_calcular_horas_extras():
    """Debug direto da função _calcular_horas_extras"""
    print(f"\n🔧 DEBUG: Função _calcular_horas_extras")
    print("=" * 60)
    
    # Buscar Danilo
    danilo = Funcionario.query.filter(Funcionario.nome.like('%Danilo%')).first()
    
    if not danilo:
        print("❌ Danilo não encontrado")
        return
    
    engine = KPIsEngine()
    
    # Chamar função específica
    horas_extras = engine._calcular_horas_extras(
        danilo.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"🎯 RESULTADO _calcular_horas_extras: {horas_extras:.1f}h")
    
    # Comparar com query manual
    query_manual = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == danilo.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"📊 Query Manual: {query_manual:.1f}h")
    
    if abs(horas_extras - query_manual) < 0.1:
        print(f"✅ Função está correta!")
    else:
        print(f"❌ Função tem problema! Diferença: {abs(horas_extras - query_manual):.1f}h")
    
    return horas_extras, query_manual

def verificar_template_interface():
    """Verificar se o template está usando a chave correta"""
    print(f"\n📋 VERIFICAÇÃO: Template da Interface")
    print("=" * 60)
    
    # Ler o template
    try:
        with open('templates/funcionario_perfil.html', 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Procurar por horas_extras
        if 'kpis.horas_extras' in conteudo:
            print("✅ Template usa 'kpis.horas_extras' - correto")
        else:
            print("❌ Template NÃO usa 'kpis.horas_extras'")
        
        # Procurar outras possíveis chaves
        chaves_procuradas = ['horas_extras', 'eficiencia', 'valor_horas_extras']
        for chave in chaves_procuradas:
            if f'kpis.{chave}' in conteudo:
                print(f"📋 Template usa: kpis.{chave}")
        
        # Procurar linha específica das horas extras
        linhas = conteudo.split('\n')
        for i, linha in enumerate(linhas):
            if 'Horas Extras' in linha and 'kpis' in linha:
                print(f"📍 Linha {i+1}: {linha.strip()}")
        
    except Exception as e:
        print(f"❌ Erro ao ler template: {e}")

if __name__ == "__main__":
    with app.app_context():
        print("🔍 DEBUG INTERFACE KPIs - POR QUE MOSTRA 0.3H?")
        print("=" * 80)
        
        # 1. Debug KPI do Danilo (funcionário da imagem)
        danilo, kpis_danilo = debug_kpi_interface()
        
        # 2. Testar funcionário com horas extras
        func_extras, kpis_extras, status = testar_funcionario_com_extras()
        
        # 3. Debug da função específica
        horas_func, horas_manual = debug_funcao_calcular_horas_extras()
        
        # 4. Verificar template
        verificar_template_interface()
        
        print(f"\n🎯 DIAGNÓSTICO FINAL:")
        if danilo and kpis_danilo:
            print(f"   Danilo - Horas Extras: {kpis_danilo['horas_extras']:.1f}h")
        if func_extras and kpis_extras:
            print(f"   {func_extras.nome} - Horas Extras: {kpis_extras['horas_extras']:.1f}h")
            print(f"   Status KPI: {status}")
        
        print(f"   Função _calcular_horas_extras: {horas_func:.1f}h")
        print(f"   Query manual: {horas_manual:.1f}h")
        
        if kpis_danilo and kpis_danilo['horas_extras'] == 0 and func_extras and kpis_extras['horas_extras'] > 0:
            print(f"\n💡 CONCLUSÃO:")
            print(f"   Danilo realmente tem 0h extras (por isso mostra 0.3h)")
            print(f"   O sistema funciona, mas você está vendo funcionário sem extras")
            print(f"   Teste com {func_extras.nome} que tem {kpis_extras['horas_extras']:.1f}h")