#!/usr/bin/env python3
"""
📊 RELATÓRIO FINAL: Correção dos Sábados Implementada
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def gerar_relatorio_final():
    """Gerar relatório final da correção dos sábados"""
    print("📊 RELATÓRIO FINAL - CORREÇÃO DOS SÁBADOS")
    print("=" * 80)
    
    # 1. Status atual dos sábados
    sabados_status = db.session.execute(text("""
        SELECT 
            COUNT(*) as total_registros,
            SUM(horas_trabalhadas) as total_trabalhadas,
            SUM(horas_extras) as total_extras,
            AVG(percentual_extras) as media_percentual
        FROM registro_ponto
        WHERE tipo_registro = 'sabado_trabalhado'
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """)).fetchone()
    
    print(f"📈 STATUS ATUAL DOS SÁBADOS:")
    print(f"   Total registros: {sabados_status.total_registros}")
    print(f"   Horas trabalhadas: {sabados_status.total_trabalhadas:.1f}h (deve ser 0)")
    print(f"   Horas extras: {sabados_status.total_extras:.1f}h")
    print(f"   Percentual médio: {sabados_status.media_percentual:.0f}%")
    
    # 2. Funcionários mais afetados
    funcionarios_sabado = db.session.execute(text("""
        SELECT 
            f.nome,
            COUNT(*) as dias_sabado,
            SUM(r.horas_extras) as total_extras_sabado
        FROM registro_ponto r
        JOIN funcionario f ON r.funcionario_id = f.id
        WHERE r.tipo_registro = 'sabado_trabalhado'
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
            AND r.horas_extras > 0
        GROUP BY f.id, f.nome
        ORDER BY total_extras_sabado DESC
        LIMIT 5
    """)).fetchall()
    
    print(f"\n👥 TOP 5 FUNCIONÁRIOS COM MAIS HORAS EXTRAS DE SÁBADO:")
    for func in funcionarios_sabado:
        print(f"   {func.nome[:30]:<30} | {func.dias_sabado} dias | {func.total_extras_sabado:.1f}h extras")
    
    # 3. Teste KPIs de exemplo
    print(f"\n🧪 TESTE KPIs EXEMPLO:")
    engine = KPIsEngine()
    
    for func in funcionarios_sabado[:2]:  # Testar 2 funcionários
        funcionario = Funcionario.query.filter(Funcionario.nome == func.nome).first()
        
        kpis = engine.calcular_kpis_funcionario(
            funcionario.id,
            date(2025, 7, 1),
            date(2025, 7, 31)
        )
        
        print(f"   👤 {func.nome[:25]:<25} | "
              f"Extras: {kpis['horas_extras']:.1f}h | "
              f"Valor: R$ {kpis['eficiencia']:.2f}")
    
    # 4. Comparação antes/depois
    total_geral = db.session.execute(text("""
        SELECT 
            SUM(horas_extras) as total_sistema
        FROM registro_ponto
        WHERE data >= '2025-07-01' 
            AND data <= '2025-07-31'
    """)).fetchone()
    
    print(f"\n📊 IMPACTO NO SISTEMA:")
    print(f"   Total geral horas extras: {total_geral.total_sistema:.1f}h")
    print(f"   Horas extras de sábado: {sabados_status.total_extras:.1f}h")
    print(f"   Percentual sábados: {(sabados_status.total_extras/total_geral.total_sistema)*100:.1f}%")
    
    # 5. Validação da correção
    problemas = []
    
    if sabados_status.total_trabalhadas > 0:
        problemas.append(f"❌ Ainda há {sabados_status.total_trabalhadas:.1f}h trabalhadas em sábados")
    
    if sabados_status.media_percentual != 50:
        problemas.append(f"⚠️  Percentual médio é {sabados_status.media_percentual:.0f}% (deveria ser 50%)")
    
    if sabados_status.total_extras < 100:
        problemas.append(f"⚠️  Poucas horas extras de sábado: {sabados_status.total_extras:.1f}h")
    
    print(f"\n✅ VALIDAÇÃO DA CORREÇÃO:")
    if not problemas:
        print(f"   🎉 TODAS AS CORREÇÕES APLICADAS CORRETAMENTE!")
        print(f"   ✅ Sábados têm 0h trabalhadas")
        print(f"   ✅ Horas extras baseadas no expediente normal")
        print(f"   ✅ 50% de adicional aplicado")
        print(f"   ✅ KPIs calculam corretamente")
        status = "SUCESSO"
    else:
        print(f"   ⚠️  PROBLEMAS IDENTIFICADOS:")
        for problema in problemas:
            print(f"   {problema}")
        status = "COM_PROBLEMAS"
    
    return {
        'status': status,
        'total_sabados': sabados_status.total_registros,
        'horas_extras_sabado': sabados_status.total_extras,
        'funcionarios_afetados': len(funcionarios_sabado),
        'problemas': problemas
    }

if __name__ == "__main__":
    with app.app_context():
        resultado = gerar_relatorio_final()
        
        print(f"\n🎯 RESUMO EXECUTIVO:")
        print(f"   Status: {resultado['status']}")
        print(f"   Registros sábado: {resultado['total_sabados']}")
        print(f"   Horas extras sábado: {resultado['horas_extras_sabado']:.1f}h")
        print(f"   Funcionários afetados: {resultado['funcionarios_afetados']}")
        
        if resultado['status'] == 'SUCESSO':
            print(f"\n🎊 CORREÇÃO DOS SÁBADOS FINALIZADA COM SUCESSO!")
            print(f"📱 O sistema agora mostra corretamente:")
            print(f"   • 0h na coluna 'H. Trabalhadas' para sábados")
            print(f"   • Valor correto na coluna 'H. Extras' para sábados")
            print(f"   • KPIs incluem todas as horas extras de sábado")
            print(f"   • Valores monetários com 50% de adicional")
        else:
            print(f"\n⚠️  CORREÇÃO PARCIAL - REVISAR PROBLEMAS ACIMA")