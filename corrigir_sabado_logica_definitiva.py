#!/usr/bin/env python3
"""
🔧 CORREÇÃO DEFINITIVA: Sábado com 0h trabalhadas, horas extras baseadas no horário normal
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from sqlalchemy import func, text
from datetime import date

def aplicar_logica_sabado_definitiva():
    """Aplicar lógica: Sábado = 0h trabalhadas, horas extras = horas do horário normal"""
    print("🔧 CORREÇÃO DEFINITIVA: Lógica Sábado")
    print("=" * 60)
    
    # Buscar todos os sábados trabalhados que ainda têm horas trabalhadas
    sabados = db.session.execute(text("""
        SELECT 
            r.id,
            r.data,
            r.funcionario_id,
            f.nome,
            r.horas_trabalhadas,
            r.horas_extras,
            h.horas_diarias
        FROM registro_ponto r
        JOIN funcionario f ON r.funcionario_id = f.id
        LEFT JOIN horario_trabalho h ON f.horario_trabalho_id = h.id
        WHERE r.tipo_registro = 'sabado_trabalhado'
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND r.horas_trabalhadas > 0
        ORDER BY r.data, f.nome
    """)).fetchall()
    
    print(f"📋 CORRIGINDO {len(sabados)} SÁBADOS:")
    
    registros_corrigidos = 0
    
    for sabado in sabados:
        # Lógica: No sábado, 0h trabalhadas, mas horas extras = horas do expediente normal
        horas_expediente_normal = sabado.horas_diarias or 8.0  # Default 8h se não tiver horário
        
        # Atualizar registro
        db.session.execute(text("""
            UPDATE registro_ponto 
            SET horas_trabalhadas = 0,
                horas_extras = :horas_extras,
                percentual_extras = 50
            WHERE id = :reg_id
        """), {
            'horas_extras': horas_expediente_normal,
            'reg_id': sabado.id
        })
        
        print(f"   {sabado.data} | {sabado.nome[:25]:<25} | "
              f"Era: {sabado.horas_trabalhadas:.1f}h trab + {sabado.horas_extras:.1f}h extras | "
              f"Agora: 0h trab + {horas_expediente_normal:.1f}h extras (baseado em {horas_expediente_normal:.1f}h normais)")
        
        registros_corrigidos += 1
    
    if registros_corrigidos > 0:
        db.session.commit()
        print(f"✅ {registros_corrigidos} sábados corrigidos com nova lógica")
    else:
        print(f"ℹ️  Nenhum sábado precisava de correção")
    
    return registros_corrigidos

def verificar_resultado_correcao():
    """Verificar se a correção foi aplicada corretamente"""
    print(f"\n🔍 VERIFICAÇÃO: Resultado da correção")
    print("=" * 60)
    
    # Verificar exemplo de sábados após correção
    sabados_apos = db.session.execute(text("""
        SELECT 
            r.data,
            f.nome,
            r.horas_trabalhadas,
            r.horas_extras,
            r.percentual_extras,
            h.horas_diarias
        FROM registro_ponto r
        JOIN funcionario f ON r.funcionario_id = f.id
        LEFT JOIN horario_trabalho h ON f.horario_trabalho_id = h.id
        WHERE r.tipo_registro = 'sabado_trabalhado'
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        ORDER BY r.horas_extras DESC
        LIMIT 10
    """)).fetchall()
    
    print(f"📋 SÁBADOS APÓS CORREÇÃO (top 10):")
    for sabado in sabados_apos:
        print(f"   {sabado.data} | {sabado.nome[:20]:<20} | "
              f"Trab: {sabado.horas_trabalhadas:.1f}h | "
              f"Extras: {sabado.horas_extras:.1f}h | "
              f"Horário: {sabado.horas_diarias or 8:.1f}h")
    
    # Verificar totais
    total_sabados = db.session.execute(text("""
        SELECT 
            COUNT(*) as registros,
            SUM(horas_trabalhadas) as total_trabalhadas,
            SUM(horas_extras) as total_extras
        FROM registro_ponto
        WHERE tipo_registro = 'sabado_trabalhado'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """)).fetchone()
    
    print(f"\n📊 TOTAIS SÁBADOS:")
    print(f"   Registros: {total_sabados.registros}")
    print(f"   Horas Trabalhadas: {total_sabados.total_trabalhadas:.1f}h (deve ser 0)")
    print(f"   Horas Extras: {total_sabados.total_extras:.1f}h")
    
    if total_sabados.total_trabalhadas == 0:
        print(f"   ✅ CORREÇÃO APLICADA! Sábados têm 0h trabalhadas")
    else:
        print(f"   ❌ Ainda há {total_sabados.total_trabalhadas:.1f}h trabalhadas em sábados")
    
    return total_sabados

def testar_kpis_apos_correcao():
    """Testar KPIs após aplicar a correção definitiva"""
    print(f"\n🧪 TESTE: KPIs após correção definitiva")
    print("=" * 60)
    
    # Buscar funcionário com mais horas extras
    func_teste = db.session.execute(text("""
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
    
    if not func_teste:
        print("❌ Nenhum funcionário com horas extras encontrado")
        return False
    
    print(f"👤 {func_teste.nome} (ID: {func_teste.id})")
    print(f"📊 DB Total Extras: {func_teste.total_extras:.1f}h")
    
    # Testar KPI Engine
    from kpis_engine import KPIsEngine
    engine = KPIsEngine()
    
    try:
        kpis = engine.calcular_kpis_funcionario(
            func_teste.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"🤖 KPI Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"💰 Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
        
        # Verificar sábados específicos deste funcionário
        sabados_func = db.session.execute(text("""
            SELECT COUNT(*), SUM(horas_extras)
            FROM registro_ponto
            WHERE funcionario_id = :func_id
                AND tipo_registro = 'sabado_trabalhado'
                AND data >= '2025-07-01' 
                AND data <= '2025-07-31'
        """), {'func_id': func_teste.id}).fetchone()
        
        print(f"🗓️  Sábados: {sabados_func[0] or 0} dias, {sabados_func[1] or 0:.1f}h extras")
        
        diferenca = abs(func_teste.total_extras - kpis['horas_extras'])
        if diferenca < 0.1:
            print(f"✅ KPI CORRETO! Diferença: {diferenca:.2f}h")
            return True
        else:
            print(f"❌ KPI INCORRETO! Diferença: {diferenca:.2f}h")
            return False
            
    except Exception as e:
        print(f"❌ ERRO no KPI Engine: {e}")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🔧 APLICANDO LÓGICA DEFINITIVA DOS SÁBADOS")
        print("=" * 80)
        print("📝 REGRA: Sábado = 0h trabalhadas + horas extras baseadas no expediente normal")
        print("=" * 80)
        
        # 1. Aplicar correção definitiva
        corrigidos = aplicar_logica_sabado_definitiva()
        
        # 2. Verificar resultado
        totais = verificar_resultado_correcao()
        
        # 3. Testar KPIs
        kpi_ok = testar_kpis_apos_correcao()
        
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Registros corrigidos: {corrigidos}")
        print(f"   Sábados com 0h trabalhadas: {'✅' if totais.total_trabalhadas == 0 else '❌'}")
        print(f"   Total horas extras sábado: {totais.total_extras:.1f}h")
        print(f"   KPIs funcionando: {'✅' if kpi_ok else '❌'}")
        
        if totais.total_trabalhadas == 0 and kpi_ok:
            print(f"\n🎉 CORREÇÃO DEFINITIVA APLICADA COM SUCESSO!")
            print(f"📊 Agora os sábados seguem a regra correta:")
            print(f"   • 0h na coluna 'horas trabalhadas'")
            print(f"   • Horas extras baseadas no expediente normal")
            print(f"   • 50% de adicional aplicado corretamente")
        else:
            print(f"\n❌ AINDA HÁ PROBLEMAS NA CORREÇÃO")
            print(f"   Verifique os logs acima para mais detalhes")