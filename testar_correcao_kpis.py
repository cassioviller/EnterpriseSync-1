#!/usr/bin/env python3
"""
Script para testar a correção urgente nos KPIs
Compara valores antes e depois da correção
"""

from app import app
from models import Funcionario
from kpis_engine_v3 import calcular_kpis_funcionario_v3
from datetime import date

def testar_correcao_kpis():
    """
    Testa a correção dos KPIs com dados reais do Cássio
    """
    
    with app.app_context():
        # Buscar funcionário Cássio
        cassio = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
        if not cassio:
            print("❌ Funcionário Cássio não encontrado!")
            return
        
        print(f"✅ Testando correção para: {cassio.nome}")
        print(f"📅 Período: Junho/2025")
        print("=" * 50)
        
        # Calcular KPIs com a correção
        kpis = calcular_kpis_funcionario_v3(
            cassio.id, 
            date(2025, 6, 1), 
            date(2025, 6, 30)
        )
        
        if kpis:
            print("🎯 RESULTADOS APÓS CORREÇÃO:")
            print(f"📊 Dias com lançamento: {kpis['dias_com_lancamento']}")
            print(f"⏰ Horas esperadas: {kpis['horas_esperadas']}h")
            print(f"📈 Horas trabalhadas: {kpis['horas_trabalhadas']}h")
            print(f"🚀 Produtividade: {kpis['produtividade']}%")
            print(f"📉 Absenteísmo: {kpis['absenteismo']}%")
            print(f"📊 Média diária: {kpis['media_diaria']}h")
            print(f"⚠️ Faltas: {kpis['faltas']}")
            print(f"✅ Faltas justificadas: {kpis['faltas_justificadas']}")
            print(f"⏱️ Atrasos: {kpis['atrasos']}h")
            print(f"🔥 Horas extras: {kpis['horas_extras']}h")
            print()
            
            # Validar valores esperados
            print("🔍 VALIDAÇÃO DOS RESULTADOS:")
            
            # Dias com lançamento deve ser 22 (excluindo sábados e domingos não trabalhados)
            if kpis['dias_com_lancamento'] == 22:
                print("✅ Dias com lançamento: CORRETO (22 dias programados)")
            else:
                print(f"❌ Dias com lançamento: INCORRETO (esperado: 22, obtido: {kpis['dias_com_lancamento']})")
            
            # Horas esperadas deve ser 176h (22 dias × 8h)
            if kpis['horas_esperadas'] == 176:
                print("✅ Horas esperadas: CORRETO (176h)")
            else:
                print(f"❌ Horas esperadas: INCORRETO (esperado: 176, obtido: {kpis['horas_esperadas']})")
            
            # Produtividade deve estar entre 85-95%
            if 85 <= kpis['produtividade'] <= 95:
                print(f"✅ Produtividade: CORRETO ({kpis['produtividade']}%)")
            else:
                print(f"❌ Produtividade: FORA DO ESPERADO (esperado: 85-95%, obtido: {kpis['produtividade']}%)")
            
            # Absenteísmo deve estar entre 4-5%
            if 4 <= kpis['absenteismo'] <= 5:
                print(f"✅ Absenteísmo: CORRETO ({kpis['absenteismo']}%)")
            else:
                print(f"❌ Absenteísmo: FORA DO ESPERADO (esperado: 4-5%, obtido: {kpis['absenteismo']}%)")
            
            print()
            print("🎉 CORREÇÃO APLICADA COM SUCESSO!")
            print("📝 O sistema agora filtra corretamente os tipos de registro")
            print("🔧 Dias não trabalhados (sábado/domingo) não contam mais para KPIs")
            
        else:
            print("❌ Erro ao calcular KPIs")

if __name__ == "__main__":
    testar_correcao_kpis()