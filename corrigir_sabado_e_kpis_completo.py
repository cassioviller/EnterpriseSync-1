#!/usr/bin/env python3
"""
🔧 CORREÇÃO COMPLETA: Refazer cálculo das horas extras do sábado e KPIs
"""

from app import app, db
from models import RegistroPonto, Funcionario
from sqlalchemy import func, text
from datetime import date

def diagnosticar_problema_sabado():
    """Diagnosticar o problema real com sábados"""
    print("🔍 DIAGNÓSTICO: Problema Sábado")
    print("=" * 60)
    
    # Listar todos os sábados com horas extras
    sabados = db.session.execute(text("""
        SELECT 
            r.data,
            f.nome,
            r.tipo_registro,
            r.horas_trabalhadas,
            r.horas_extras,
            r.percentual_extras
        FROM registro_ponto r
        JOIN funcionario f ON r.funcionario_id = f.id
        WHERE EXTRACT(DOW FROM r.data) = 6  -- Sábado
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND r.horas_extras > 0
        ORDER BY r.horas_extras DESC
    """)).fetchall()
    
    print(f"📋 SÁBADOS COM HORAS EXTRAS ({len(sabados)}):")
    total_sabados = 0
    for sabado in sabados:
        print(f"   {sabado.data} | {sabado.nome[:25]:<25} | "
              f"{sabado.tipo_registro} | "
              f"Extras: {sabado.horas_extras:.1f}h | "
              f"Perc: {sabado.percentual_extras or 0:.0f}%")
        total_sabados += sabado.horas_extras
    
    print(f"\n📊 TOTAL SÁBADOS: {total_sabados:.1f}h")
    return sabados, total_sabados

def corrigir_tipos_sabado():
    """Corrigir e padronizar todos os tipos de sábado"""
    print(f"\n🔧 CORREÇÃO: Padronizar tipos de sábado")
    print("=" * 60)
    
    # Verificar tipos atuais
    tipos_atuais = db.session.execute(text("""
        SELECT DISTINCT tipo_registro, COUNT(*)
        FROM registro_ponto
        WHERE EXTRACT(DOW FROM data) = 6  -- Sábado
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        GROUP BY tipo_registro
        ORDER BY COUNT(*) DESC
    """)).fetchall()
    
    print(f"📋 TIPOS ATUAIS DE SÁBADO:")
    for tipo in tipos_atuais:
        print(f"   {tipo[0]}: {tipo[1]} registros")
    
    # Corrigir todos os sábados para usar 'sabado_trabalhado' quando há horas trabalhadas
    resultado = db.session.execute(text("""
        UPDATE registro_ponto 
        SET tipo_registro = 'sabado_trabalhado'
        WHERE EXTRACT(DOW FROM data) = 6  -- Sábado
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
            AND tipo_registro != 'sabado_trabalhado'
    """))
    
    print(f"✅ {resultado.rowcount} registros corrigidos para 'sabado_trabalhado'")
    
    # Verificar tipos após correção
    tipos_corrigidos = db.session.execute(text("""
        SELECT DISTINCT tipo_registro, COUNT(*)
        FROM registro_ponto
        WHERE EXTRACT(DOW FROM data) = 6  -- Sábado
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        GROUP BY tipo_registro
        ORDER BY COUNT(*) DESC
    """)).fetchall()
    
    print(f"\n📋 TIPOS APÓS CORREÇÃO:")
    for tipo in tipos_corrigidos:
        print(f"   {tipo[0]}: {tipo[1]} registros")
    
    db.session.commit()
    return resultado.rowcount

def corrigir_percentuais_sabado():
    """Corrigir percentuais extras dos sábados"""
    print(f"\n🔧 CORREÇÃO: Percentuais de sábado")
    print("=" * 60)
    
    # Definir percentual 50% para todos os sábados trabalhados
    resultado = db.session.execute(text("""
        UPDATE registro_ponto 
        SET percentual_extras = 50
        WHERE tipo_registro = 'sabado_trabalhado'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras > 0
            AND (percentual_extras IS NULL OR percentual_extras = 0)
    """))
    
    print(f"✅ {resultado.rowcount} sábados com percentual 50% definido")
    
    db.session.commit()
    return resultado.rowcount

def recalcular_horas_extras_sabado():
    """Recalcular horas extras dos sábados baseado na legislação"""
    print(f"\n🔧 RECÁLCULO: Horas extras de sábado")
    print("=" * 60)
    
    # Buscar sábados trabalhados
    sabados_trabalhados = db.session.execute(text("""
        SELECT 
            id,
            data,
            funcionario_id,
            horas_trabalhadas,
            horas_extras
        FROM registro_ponto
        WHERE tipo_registro = 'sabado_trabalhado'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_trabalhadas > 0
        ORDER BY data
    """)).fetchall()
    
    print(f"📋 RECALCULANDO {len(sabados_trabalhados)} SÁBADOS:")
    
    registros_atualizados = 0
    
    for sabado in sabados_trabalhados:
        # No sábado, TODAS as horas trabalhadas são horas extras (50% adicional)
        novas_horas_extras = sabado.horas_trabalhadas
        
        if abs(sabado.horas_extras - novas_horas_extras) > 0.1:
            # Atualizar registro
            db.session.execute(text("""
                UPDATE registro_ponto 
                SET horas_extras = :novas_extras,
                    percentual_extras = 50
                WHERE id = :reg_id
            """), {
                'novas_extras': novas_horas_extras,
                'reg_id': sabado.id
            })
            
            print(f"   {sabado.data} | Func {sabado.funcionario_id} | "
                  f"Era: {sabado.horas_extras:.1f}h → Agora: {novas_horas_extras:.1f}h")
            registros_atualizados += 1
    
    if registros_atualizados > 0:
        db.session.commit()
        print(f"✅ {registros_atualizados} sábados recalculados")
    else:
        print(f"ℹ️  Todos os sábados já estavam corretos")
    
    return registros_atualizados

def refazer_kpi_engine_completo():
    """Refazer completamente a função de KPI horas extras"""
    print(f"\n🔧 REFAZER: KPI Engine - Horas Extras")
    print("=" * 60)
    
    # Ler arquivo atual
    with open('kpis_engine.py', 'r') as f:
        conteudo = f.read()
    
    # Localizar e substituir a função _calcular_horas_extras
    nova_funcao = '''    def _calcular_horas_extras(self, funcionario_id, data_inicio, data_fim):
        """2. Horas Extras: Soma TOTAL de todas as horas extras incluindo sábados"""
        # SOMA SIMPLES E DIRETA - SEM FILTROS QUE EXCLUAM REGISTROS
        total = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_extras.isnot(None)
        ).scalar()
        
        return float(total or 0.0)'''
    
    # Encontrar início e fim da função atual
    inicio = conteudo.find('def _calcular_horas_extras(self, funcionario_id, data_inicio, data_fim):')
    if inicio == -1:
        print("❌ Função _calcular_horas_extras não encontrada")
        return False
    
    # Encontrar o fim da função (próxima def ou final da classe)
    linhas = conteudo[inicio:].split('\n')
    fim_relativo = 0
    dentro_funcao = False
    
    for i, linha in enumerate(linhas):
        if linha.strip().startswith('def _calcular_horas_extras'):
            dentro_funcao = True
            continue
        
        if dentro_funcao and linha.strip().startswith('def ') and not linha.strip().startswith('def _calcular_horas_extras'):
            fim_relativo = i
            break
        elif dentro_funcao and i > 0 and linha and not linha.startswith('    ') and not linha.startswith('\t'):
            fim_relativo = i
            break
    
    if fim_relativo == 0:
        fim_relativo = len(linhas)
    
    fim = inicio + len('\n'.join(linhas[:fim_relativo]))
    
    # Substituir a função
    novo_conteudo = conteudo[:inicio] + nova_funcao + conteudo[fim:]
    
    # Escrever arquivo
    with open('kpis_engine.py', 'w') as f:
        f.write(novo_conteudo)
    
    print("✅ Função _calcular_horas_extras refeita completamente")
    return True

def testar_correcao_final():
    """Testar se as correções funcionaram"""
    print(f"\n🧪 TESTE: Correções aplicadas")
    print("=" * 60)
    
    # Testar funcionário com mais horas extras
    funcionario = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND r.horas_extras > 0
        GROUP BY f.id, f.nome
        ORDER BY total_extras DESC
        LIMIT 1
    """)).fetchone()
    
    if not funcionario:
        print("❌ Nenhum funcionário com horas extras encontrado")
        return False
    
    print(f"👤 Testando: {funcionario.nome} (ID: {funcionario.id})")
    print(f"📊 Horas Extras (DB): {funcionario.total_extras:.1f}h")
    
    # Testar KPI Engine
    from kpis_engine import KPIsEngine
    engine = KPIsEngine()
    
    try:
        horas_kpi = engine._calcular_horas_extras(
            funcionario.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"🤖 Horas Extras (KPI): {horas_kpi:.1f}h")
        
        diferenca = abs(funcionario.total_extras - horas_kpi)
        if diferenca < 0.1:
            print(f"✅ CORREÇÃO FUNCIONOU! Diferença: {diferenca:.2f}h")
            return True
        else:
            print(f"❌ AINDA HÁ PROBLEMA! Diferença: {diferenca:.2f}h")
            return False
            
    except Exception as e:
        print(f"❌ ERRO no KPI Engine: {e}")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO COMPLETA - SÁBADOS E KPIs HORAS EXTRAS")
        print("=" * 80)
        
        # 1. Diagnosticar problema
        sabados, total_sabados = diagnosticar_problema_sabado()
        
        # 2. Corrigir tipos de sábado
        tipos_corrigidos = corrigir_tipos_sabado()
        
        # 3. Corrigir percentuais
        percentuais_corrigidos = corrigir_percentuais_sabado()
        
        # 4. Recalcular horas extras
        horas_recalculadas = recalcular_horas_extras_sabado()
        
        # 5. Refazer KPI engine
        kpi_refeito = refazer_kpi_engine_completo()
        
        # 6. Testar correção
        teste_ok = testar_correcao_final()
        
        print(f"\n🎯 RESUMO DAS CORREÇÕES:")
        print(f"   Sábados encontrados: {len(sabados)} com {total_sabados:.1f}h extras")
        print(f"   Tipos corrigidos: {tipos_corrigidos}")
        print(f"   Percentuais corrigidos: {percentuais_corrigidos}")
        print(f"   Horas recalculadas: {horas_recalculadas}")
        print(f"   KPI engine refeito: {'✅' if kpi_refeito else '❌'}")
        print(f"   Teste final: {'✅ SUCESSO' if teste_ok else '❌ FALHOU'}")
        
        if teste_ok:
            print(f"\n🎉 CORREÇÃO COMPLETA APLICADA!")
            print(f"   Reinicie o servidor para ver as mudanças")
            print(f"   Os sábados agora são contabilizados corretamente")
        else:
            print(f"\n❌ AINDA HÁ PROBLEMAS")
            print(f"   Verifique os logs acima para mais detalhes")