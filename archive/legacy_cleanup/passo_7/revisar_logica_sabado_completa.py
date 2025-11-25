#!/usr/bin/env python3
"""
🔍 REVISÃO COMPLETA: Padronizar lógica de sábado e eliminar confusão
"""

from app import app, db
from models import RegistroPonto, Funcionario
from sqlalchemy import func, text
from datetime import date

def analisar_tipos_sabado_database():
    """Analisar quais tipos de sábado existem no database"""
    print("🔍 ANÁLISE: Tipos de Sábado no Database")
    print("=" * 60)
    
    tipos_sabado = db.session.execute(text("""
        SELECT 
            tipo_registro,
            COUNT(*) as count,
            SUM(horas_trabalhadas) as total_trabalhadas,
            SUM(horas_extras) as total_extras
        FROM registro_ponto 
        WHERE data >= '2025-07-01' AND data <= '2025-07-31'
            AND tipo_registro LIKE '%sabado%'
        GROUP BY tipo_registro
        ORDER BY count DESC
    """)).fetchall()
    
    print(f"📊 TIPOS DE SÁBADO ENCONTRADOS:")
    for tipo in tipos_sabado:
        print(f"   {tipo.tipo_registro}: {tipo.count} registros, "
              f"{tipo.total_trabalhadas:.1f}h trabalhadas, "
              f"{tipo.total_extras:.1f}h extras")
    
    return tipos_sabado

def verificar_codigo_inconsistente():
    """Verificar inconsistências no código"""
    print(f"\n🔍 ANÁLISE: Inconsistências no Código")
    print("=" * 60)
    
    # Ler kpis_engine.py
    with open('kpis_engine.py', 'r') as f:
        conteudo = f.read()
    
    # Procurar referências inconsistentes
    referencias = []
    if 'sabado_trabalhado' in conteudo:
        referencias.append('sabado_trabalhado')
    if 'sabado_horas_extras' in conteudo:
        referencias.append('sabado_horas_extras')
    
    print(f"📋 REFERÊNCIAS ENCONTRADAS NO KPI ENGINE:")
    for ref in referencias:
        linhas = [i+1 for i, linha in enumerate(conteudo.split('\n')) if ref in linha]
        print(f"   {ref}: linhas {linhas}")
    
    return referencias

def padronizar_tipo_sabado():
    """Padronizar todos os sábados para usar apenas 'sabado_trabalhado'"""
    print(f"\n🔧 PADRONIZAÇÃO: Unificar tipo de sábado")
    print("=" * 60)
    
    # Atualizar todos sabado_horas_extras para sabado_trabalhado
    resultado = db.session.execute(text("""
        UPDATE registro_ponto 
        SET tipo_registro = 'sabado_trabalhado'
        WHERE tipo_registro = 'sabado_horas_extras'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """))
    
    print(f"✅ {resultado.rowcount} registros padronizados para 'sabado_trabalhado'")
    
    # Verificar sábados por dia da semana também
    resultado2 = db.session.execute(text("""
        UPDATE registro_ponto 
        SET tipo_registro = 'sabado_trabalhado'
        WHERE EXTRACT(DOW FROM data) = 6  -- Sábado
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
            AND tipo_registro != 'sabado_trabalhado'
    """))
    
    print(f"✅ {resultado2.rowcount} registros adicionais corrigidos por dia da semana")
    
    db.session.commit()
    return resultado.rowcount + resultado2.rowcount

def corrigir_kpis_engine_sabado():
    """Corrigir todas as referências no KPIs engine para usar apenas sabado_trabalhado"""
    print(f"\n🔧 CORREÇÃO: KPIs Engine - Padronizar sábado")
    print("=" * 60)
    
    # Ler arquivo atual
    with open('kpis_engine.py', 'r') as f:
        conteudo = f.read()
    
    # Substituições para padronizar
    conteudo_corrigido = conteudo
    
    # Remover todas as referências a sabado_horas_extras
    conteudo_corrigido = conteudo_corrigido.replace(
        "['sabado_trabalhado', 'sabado_horas_extras']",
        "['sabado_trabalhado']"
    )
    
    conteudo_corrigido = conteudo_corrigido.replace(
        "'sabado_horas_extras'",
        "'sabado_trabalhado'"
    )
    
    # Verificar mudanças
    if conteudo != conteudo_corrigido:
        with open('kpis_engine.py', 'w') as f:
            f.write(conteudo_corrigido)
        print("✅ Arquivo kpis_engine.py atualizado")
        return True
    else:
        print("ℹ️  Nenhuma mudança necessária no kpis_engine.py")
        return False

def testar_funcionario_193h_especifico():
    """Encontrar e testar especificamente o funcionário com 193h"""
    print(f"\n🎯 TESTE: Funcionário Específico (193h)")
    print("=" * 60)
    
    # Buscar funcionário com exatamente 193.0h
    funcionario = db.session.execute(text("""
        SELECT 
            f.id, 
            f.nome, 
            f.salario,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        ORDER BY ABS(SUM(r.horas_trabalhadas) - 193.0)
        LIMIT 1
    """)).fetchone()
    
    if not funcionario:
        print("❌ Funcionário não encontrado")
        return None
    
    print(f"👤 Funcionário: {funcionario.nome}")
    print(f"📊 Horas Trabalhadas: {funcionario.total_trabalhadas:.1f}h")
    print(f"⚡ Horas Extras (DB): {funcionario.total_extras:.1f}h")
    
    # Listar registros de sábado deste funcionário
    sabados = db.session.execute(text("""
        SELECT 
            data,
            tipo_registro,
            horas_trabalhadas,
            horas_extras,
            percentual_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND (EXTRACT(DOW FROM data) = 6 OR tipo_registro LIKE '%sabado%')
        ORDER BY data
    """), {'func_id': funcionario.id}).fetchall()
    
    print(f"\n📋 SÁBADOS DESTE FUNCIONÁRIO ({len(sabados)}):")
    total_sabados = 0
    for sabado in sabados:
        print(f"   {sabado.data} | {sabado.tipo_registro} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h")
        total_sabados += sabado.horas_extras or 0
    
    print(f"📊 TOTAL SÁBADOS: {total_sabados:.1f}h")
    
    # Testar KPI
    from kpis_engine import KPIsEngine
    engine = KPIsEngine()
    
    try:
        kpis = engine.calcular_kpis_funcionario(
            funcionario.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"\n🤖 RESULTADO KPI:")
        print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"   Valor: R$ {kpis['eficiencia']:.2f}")
        
        if abs(kpis['horas_extras'] - funcionario.total_extras) < 0.1:
            print(f"✅ KPI CORRETO!")
        else:
            print(f"❌ KPI INCORRETO! Diferença: {abs(kpis['horas_extras'] - funcionario.total_extras):.1f}h")
        
        return funcionario, kpis
        
    except Exception as e:
        print(f"❌ ERRO no KPI: {e}")
        return funcionario, None

def verificar_query_direta():
    """Verificar se a query direta está funcionando"""
    print(f"\n🔍 VERIFICAÇÃO: Query Direta")
    print("=" * 60)
    
    # Query exata que deveria estar no KPI
    total_direto = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"📊 QUERY DIRETA (geral): {total_direto:.1f}h")
    
    # Por funcionário específico
    funcionario_id = db.session.execute(text("""
        SELECT f.id
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id
        ORDER BY ABS(SUM(r.horas_trabalhadas) - 193.0)
        LIMIT 1
    """)).scalar()
    
    if funcionario_id:
        total_func = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31),
            RegistroPonto.horas_extras.isnot(None)
        ).scalar() or 0
        
        print(f"📊 QUERY DIRETA (func {funcionario_id}): {total_func:.1f}h")
    
    return total_direto

if __name__ == "__main__":
    with app.app_context():
        print("🔍 REVISÃO COMPLETA - PADRONIZAR LÓGICA SÁBADO")
        print("=" * 80)
        
        # 1. Analisar tipos no database
        tipos = analisar_tipos_sabado_database()
        
        # 2. Verificar código inconsistente
        refs = verificar_codigo_inconsistente()
        
        # 3. Padronizar database
        padronizados = padronizar_tipo_sabado()
        
        # 4. Corrigir KPIs engine
        arquivo_corrigido = corrigir_kpis_engine_sabado()
        
        # 5. Testar funcionário específico
        funcionario, kpis = testar_funcionario_193h_especifico()
        
        # 6. Verificar query direta
        total_query = verificar_query_direta()
        
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Tipos padronizados: {padronizados}")
        print(f"   Arquivo corrigido: {'✅' if arquivo_corrigido else '❌'}")
        print(f"   Query direta: {total_query:.1f}h")
        
        if funcionario and kpis:
            print(f"   Funcionário teste: {funcionario.nome}")
            print(f"   KPI resultado: {kpis['horas_extras']:.1f}h")
        
        if total_query > 100 and padronizados > 0:
            print(f"\n✅ CORREÇÃO APLICADA!")
            print(f"   Reinicie o servidor para ver as mudanças")
        else:
            print(f"\n❌ AINDA HÁ PROBLEMAS")
            print(f"   Total query baixo: {total_query:.1f}h")