#!/usr/bin/env python3
"""
Script para testar o Engine de KPIs v4.0 integrado com horários de trabalho
"""

from datetime import date
from app import app
from models import Funcionario
from kpis_engine_v4 import calcular_kpis_funcionario_v4


def testar_kpis_integrados():
    """
    Testa KPIs integrados com horários
    """
    with app.app_context():
        # Buscar Cássio
        cassio = Funcionario.query.filter(Funcionario.nome.ilike('%Cássio%')).first()
        
        if cassio:
            print(f"=== TESTE KPIs v4.0 - {cassio.nome} ===")
            
            # Calcular KPIs
            kpis = calcular_kpis_funcionario_v4(
                cassio.id,
                date(2025, 6, 1),
                date(2025, 6, 30)
            )
            
            if kpis:
                horario = kpis['horario_info']
                
                print(f"\n📋 HORÁRIO DE TRABALHO:")
                print(f"Nome: {horario['nome']}")
                print(f"Horário: {horario['entrada'].strftime('%H:%M')} às {horario['saida'].strftime('%H:%M')}")
                print(f"Almoço: {horario['almoco_inicio'].strftime('%H:%M')} às {horario['almoco_fim'].strftime('%H:%M')}")
                print(f"Horas/dia: {horario['horas_diarias']}h")
                print(f"Valor/hora: R$ {horario['valor_hora']:.2f}")
                
                print(f"\n📊 KPIs BÁSICOS (Linha 1):")
                print(f"1. Horas Trabalhadas: {kpis['horas_trabalhadas']}h")
                print(f"2. Horas Extras: {kpis['horas_extras']}h")
                print(f"3. Faltas: {kpis['faltas']}")
                print(f"4. Atrasos: {kpis['atrasos']}h")
                
                print(f"\n📈 KPIs ANALÍTICOS (Linha 2):")
                print(f"5. Produtividade: {kpis['produtividade']}%")
                print(f"6. Absenteísmo: {kpis['absenteismo']}%")
                print(f"7. Média Diária: {kpis['media_diaria']}h")
                print(f"8. Faltas Justificadas: {kpis['faltas_justificadas']}")
                
                print(f"\n💰 KPIs FINANCEIROS (Linha 3):")
                print(f"9. Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
                print(f"10. Custo Alimentação: R$ {kpis['custo_alimentacao']:.2f}")
                print(f"11. Custo Transporte: R$ {kpis['custo_transporte']:.2f}")
                print(f"12. Outros Custos: R$ {kpis['outros_custos']:.2f}")
                
                print(f"\n🎯 KPIs RESUMO (Linha 4):")
                print(f"13. Horas Perdidas: {kpis['horas_perdidas']}h")
                print(f"14. Eficiência: {kpis['eficiencia']}%")
                print(f"15. Valor Falta Justificada: R$ {kpis['valor_falta_justificada']:.2f}")
                
                print(f"\n🔍 ANÁLISE DETALHADA:")
                print(f"Período: {kpis['periodo']}")
                print(f"Horário: {horario['nome']} ({horario['horas_diarias']}h/dia)")
                print(f"Valor/hora: R$ {horario['valor_hora']:.2f}")
                
                # Cálculos de validação
                dias_programados = kpis['horas_trabalhadas'] / kpis['media_diaria'] if kpis['media_diaria'] > 0 else 0
                horas_esperadas = dias_programados * horario['horas_diarias'] if dias_programados > 0 else 0
                
                print(f"\n📋 VALIDAÇÃO DOS CÁLCULOS:")
                print(f"Dias programados estimados: {dias_programados:.1f}")
                print(f"Horas esperadas: {horas_esperadas:.1f}h")
                print(f"Produtividade calculada: {(kpis['horas_trabalhadas'] / horas_esperadas * 100):.1f}%" if horas_esperadas > 0 else "N/A")
                
                print(f"\n✅ TESTE CONCLUÍDO COM SUCESSO!")
                return True
            else:
                print("❌ Erro ao calcular KPIs")
                return False
        else:
            print("❌ Funcionário Cássio não encontrado")
            return False


def comparar_kpis_v3_v4():
    """
    Compara KPIs v3.1 vs v4.0 para verificar melhorias
    """
    from kpis_engine_v3 import calcular_kpis_funcionario_v3
    
    with app.app_context():
        cassio = Funcionario.query.filter(Funcionario.nome.ilike('%Cássio%')).first()
        
        if cassio:
            print(f"\n=== COMPARAÇÃO KPIs v3.1 vs v4.0 ===")
            
            # KPIs v3.1
            kpis_v3 = calcular_kpis_funcionario_v3(
                cassio.id,
                date(2025, 6, 1),
                date(2025, 6, 30)
            )
            
            # KPIs v4.0
            kpis_v4 = calcular_kpis_funcionario_v4(
                cassio.id,
                date(2025, 6, 1),
                date(2025, 6, 30)
            )
            
            if kpis_v3 and kpis_v4:
                print(f"\n📊 COMPARAÇÃO DE KPIs:")
                print(f"{'KPI':<20} {'v3.1':<12} {'v4.0':<12} {'Diferença':<12}")
                print("-" * 56)
                
                comparacoes = [
                    ('Produtividade', f"{kpis_v3.get('produtividade', 0):.1f}%", f"{kpis_v4['produtividade']:.1f}%"),
                    ('Absenteísmo', f"{kpis_v3.get('absenteismo', 0):.1f}%", f"{kpis_v4['absenteismo']:.1f}%"),
                    ('Média Diária', f"{kpis_v3.get('media_diaria', 0):.1f}h", f"{kpis_v4['media_diaria']:.1f}h"),
                    ('Horas Trabalhadas', f"{kpis_v3.get('horas_trabalhadas', 0):.1f}h", f"{kpis_v4['horas_trabalhadas']:.1f}h"),
                    ('Horas Extras', f"{kpis_v3.get('horas_extras', 0):.1f}h", f"{kpis_v4['horas_extras']:.1f}h"),
                    ('Faltas', f"{kpis_v3.get('faltas', 0)}", f"{kpis_v4['faltas']}"),
                    ('Atrasos', f"{kpis_v3.get('atrasos', 0):.2f}h", f"{kpis_v4['atrasos']:.2f}h"),
                ]
                
                for nome, v3, v4 in comparacoes:
                    diff = "✓" if v3 == v4 else "≠"
                    print(f"{nome:<20} {v3:<12} {v4:<12} {diff:<12}")
                
                print(f"\n🆕 NOVOS KPIs v4.0:")
                print(f"Custo Mão de Obra: R$ {kpis_v4['custo_mao_obra']:.2f}")
                print(f"Custo Alimentação: R$ {kpis_v4['custo_alimentacao']:.2f}")
                print(f"Custo Transporte: R$ {kpis_v4['custo_transporte']:.2f}")
                print(f"Outros Custos: R$ {kpis_v4['outros_custos']:.2f}")
                print(f"Valor Falta Justificada: R$ {kpis_v4['valor_falta_justificada']:.2f}")
                
                print(f"\n📋 INFORMAÇÕES DO HORÁRIO:")
                horario = kpis_v4['horario_info']
                print(f"Nome: {horario['nome']}")
                print(f"Horas/dia: {horario['horas_diarias']}h")
                print(f"Valor/hora: R$ {horario['valor_hora']:.2f}")
                
                print(f"\n✅ COMPARAÇÃO CONCLUÍDA!")
                return True
            else:
                print("❌ Erro ao calcular KPIs para comparação")
                return False
        else:
            print("❌ Funcionário não encontrado")
            return False


if __name__ == "__main__":
    print("🚀 TESTANDO ENGINE DE KPIs v4.0")
    print("=" * 50)
    
    # Teste principal
    sucesso_teste = testar_kpis_integrados()
    
    if sucesso_teste:
        # Comparação com versão anterior
        comparar_kpis_v3_v4()
    
    print("\n🎉 TESTES FINALIZADOS!")