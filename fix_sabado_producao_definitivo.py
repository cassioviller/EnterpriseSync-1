#!/usr/bin/env python3
"""
🔧 FIX DEFINITIVO PRODUÇÃO: Problema específico do Antonio com 7.9h sábado
Este script resolve especificamente o problema onde sábados estão em horas_trabalhadas mas não em horas_extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from sqlalchemy import text, func
from datetime import date

def executar_correcao_completa_sabados():
    """Executar correção completa e definitiva dos sábados"""
    print("🔧 CORREÇÃO COMPLETA E DEFINITIVA - SÁBADOS")
    print("=" * 70)
    
    # 1. Identificar todos os sábados que precisam correção
    print("📊 FASE 1: Identificando registros que precisam correção...")
    
    sabados_problema = db.session.execute(text("""
        SELECT 
            r.id,
            r.data,
            r.funcionario_id,
            r.tipo_registro,
            r.horas_trabalhadas,
            r.horas_extras,
            f.nome,
            EXTRACT(DOW FROM r.data) as dia_semana
        FROM registro_ponto r
        JOIN funcionario f ON r.funcionario_id = f.id
        WHERE (
            -- Critério 1: Tipo sabado_trabalhado com horas < trabalhadas
            (r.tipo_registro = 'sabado_trabalhado' AND r.horas_trabalhadas > 0 AND (r.horas_extras IS NULL OR r.horas_extras < r.horas_trabalhadas))
            OR
            -- Critério 2: Sábados (dia da semana 6) com qualquer tipo e horas trabalhadas > extras
            (EXTRACT(DOW FROM r.data) = 6 AND r.horas_trabalhadas > 0 AND (r.horas_extras IS NULL OR r.horas_extras < r.horas_trabalhadas))
        )
        AND r.data >= '2025-07-01' 
        AND r.data <= '2025-07-31'
        ORDER BY r.data, f.nome
    """)).fetchall()
    
    print(f"📊 REGISTROS ENCONTRADOS: {len(sabados_problema)}")
    
    if len(sabados_problema) == 0:
        print("✅ Todos os sábados já estão corretos!")
        return 0
    
    # Mostrar alguns exemplos
    print("\n📋 EXEMPLOS QUE SERÃO CORRIGIDOS:")
    for i, reg in enumerate(sabados_problema[:10]):
        print(f"   {reg.data} | {reg.nome[:25]:<25} | {reg.tipo_registro:<20} | "
              f"Trab: {reg.horas_trabalhadas:>4.1f}h | Extras: {reg.horas_extras or 0:>4.1f}h")
    
    if len(sabados_problema) > 10:
        print(f"   ... e mais {len(sabados_problema) - 10} registros")
    
    # 2. Aplicar correção
    print(f"\n🔧 FASE 2: Aplicando correção...")
    
    ids_para_corrigir = [reg.id for reg in sabados_problema]
    
    if ids_para_corrigir:
        # Converter lista para string para usar no SQL
        ids_str = ','.join(map(str, ids_para_corrigir))
        
        resultado = db.session.execute(text(f"""
            UPDATE registro_ponto 
            SET 
                horas_extras = horas_trabalhadas,
                percentual_extras = 50.0,
                tipo_registro = CASE 
                    WHEN EXTRACT(DOW FROM data) = 6 THEN 'sabado_trabalhado'
                    ELSE tipo_registro
                END
            WHERE id IN ({ids_str})
        """))
        
        db.session.commit()
        print(f"✅ {resultado.rowcount} registros atualizados com sucesso!")
    
    return len(sabados_problema)

def verificar_antonio_especifico():
    """Verificar especificamente casos similares ao Antonio"""
    print(f"\n🔍 VERIFICAÇÃO: Casos Similares ao Antonio")
    print("=" * 70)
    
    # Buscar funcionários com registros de sábado em julho
    funcionarios_sabado = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            f.salario,
            COUNT(r.id) as total_registros,
            SUM(CASE WHEN EXTRACT(DOW FROM r.data) = 6 THEN r.horas_trabalhadas ELSE 0 END) as horas_sabado,
            SUM(CASE WHEN EXTRACT(DOW FROM r.data) = 6 THEN r.horas_extras ELSE 0 END) as extras_sabado,
            SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        HAVING SUM(CASE WHEN EXTRACT(DOW FROM r.data) = 6 THEN r.horas_trabalhadas ELSE 0 END) > 0
        ORDER BY total_extras DESC
    """)).fetchall()
    
    print(f"📊 FUNCIONÁRIOS COM SÁBADOS: {len(funcionarios_sabado)}")
    
    for i, func in enumerate(funcionarios_sabado[:5]):
        print(f"\n👤 {func.nome}")
        print(f"   💰 Salário: R$ {func.salario:.2f}")
        print(f"   📊 Registros: {func.total_registros}")
        print(f"   🕐 Horas Sábado: {func.horas_sabado:.1f}h")
        print(f"   ⚡ Extras Sábado: {func.extras_sabado:.1f}h")
        print(f"   📈 Total Extras: {func.total_extras:.1f}h")
        
        if func.horas_sabado > func.extras_sabado:
            print(f"   ⚠️  PROBLEMA: {func.horas_sabado - func.extras_sabado:.1f}h de sábado não contabilizadas!")
        else:
            print(f"   ✅ OK: Sábados corretos")
    
    return funcionarios_sabado

def testar_kpi_final():
    """Teste final com KPIs"""
    print(f"\n🧪 TESTE FINAL: KPIs Após Correção")
    print("=" * 70)
    
    # Pegar funcionário com mais horas extras para testar
    funcionario = db.session.execute(text("""
        SELECT f.id, f.nome, f.salario, SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND r.horas_extras > 0
        GROUP BY f.id, f.nome, f.salario
        ORDER BY total_extras DESC
        LIMIT 1
    """)).fetchone()
    
    if not funcionario:
        print("❌ Nenhum funcionário com horas extras encontrado")
        return
    
    print(f"👤 Testando: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario:.2f}")
    print(f"📊 Horas Extras (DB): {funcionario.total_extras:.1f}h")
    
    # Calcular via KPI engine
    try:
        from kpis_engine import KPIsEngine
        engine = KPIsEngine()
        
        kpis = engine.calcular_kpis_funcionario(
            funcionario.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"\n📊 RESULTADO KPI:")
        print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
        
        # Comparar
        diferenca = abs(kpis['horas_extras'] - funcionario.total_extras)
        if diferenca < 0.1:
            print(f"✅ KPI CORRETO! Diferença: {diferenca:.2f}h")
        else:
            print(f"❌ KPI INCORRETO! Diferença: {diferenca:.2f}h")
        
        return kpis
        
    except Exception as e:
        print(f"❌ ERRO ao calcular KPI: {e}")
        return None

def criar_resumo_final():
    """Criar resumo final da situação"""
    print(f"\n📋 RESUMO FINAL DA SITUAÇÃO")
    print("=" * 70)
    
    # Total geral
    totais = db.session.execute(text("""
        SELECT 
            COUNT(*) as registros,
            SUM(horas_trabalhadas) as total_trabalhadas,
            SUM(horas_extras) as total_extras
        FROM registro_ponto
        WHERE data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """)).fetchone()
    
    # Sábados específicos
    sabados = db.session.execute(text("""
        SELECT 
            COUNT(*) as registros_sabado,
            SUM(horas_trabalhadas) as trab_sabado,
            SUM(horas_extras) as extras_sabado
        FROM registro_ponto
        WHERE EXTRACT(DOW FROM data) = 6
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
    """)).fetchone()
    
    print(f"📊 TOTAIS GERAIS JULHO 2025:")
    print(f"   Registros: {totais.registros}")
    print(f"   Horas Trabalhadas: {totais.total_trabalhadas:.1f}h")
    print(f"   Horas Extras: {totais.total_extras:.1f}h")
    
    print(f"\n📊 SÁBADOS JULHO 2025:")
    print(f"   Registros: {sabados.registros_sabado}")
    print(f"   Horas Trabalhadas: {sabados.trab_sabado:.1f}h")
    print(f"   Horas Extras: {sabados.extras_sabado:.1f}h")
    
    if abs((sabados.trab_sabado or 0) - (sabados.extras_sabado or 0)) < 0.1:
        print(f"✅ SÁBADOS ESTÃO CORRETOS!")
    else:
        print(f"❌ AINDA HÁ PROBLEMA NOS SÁBADOS!")
        print(f"   Diferença: {(sabados.trab_sabado or 0) - (sabados.extras_sabado or 0):.1f}h")

if __name__ == "__main__":
    with app.app_context():
        print("🔧 FIX DEFINITIVO PRODUÇÃO - ANTONIO SÁBADO 7.9H")
        print("=" * 80)
        
        # 1. Executar correção completa
        corrigidos = executar_correcao_completa_sabados()
        
        # 2. Verificar casos específicos
        funcionarios = verificar_antonio_especifico()
        
        # 3. Testar KPI
        kpi_resultado = testar_kpi_final()
        
        # 4. Resumo final
        criar_resumo_final()
        
        print(f"\n🎯 CONCLUSÃO:")
        if corrigidos > 0:
            print(f"   ✅ {corrigidos} registros corrigidos")
            print(f"   🔄 Reinicie o servidor")
            print(f"   📱 Atualize a página do funcionário")
            print(f"   🎉 As 7.9h de sábado devem aparecer nos KPIs!")
        else:
            print(f"   ✅ Sistema já estava correto")
            print(f"   🤔 Problema pode ser no cálculo dos KPIs")
            print(f"   📧 Verifique se há filtros ou condições específicas")