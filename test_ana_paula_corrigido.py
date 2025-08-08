#!/usr/bin/env python3
"""
Teste específico para Ana Paula Rodrigues - Verificação dos KPIs corrigidos
"""

from app import app, db
from utils import calcular_kpis_funcionario_periodo
from models import Funcionario
from datetime import date

def test_ana_paula_kpis():
    """Testa os KPIs da Ana Paula Rodrigues após correção"""
    with app.app_context():
        try:
            print("🔧 TESTE: Ana Paula Rodrigues - KPIs Julho 2025")
            print("=" * 60)
            
            # Encontrar Ana Paula Rodrigues
            ana_paula = Funcionario.query.filter(
                Funcionario.nome.like('%Ana Paula Rodrigues%')
            ).first()
            
            if not ana_paula:
                print("❌ Ana Paula Rodrigues não encontrada!")
                return False
            
            print(f"✅ Funcionária encontrada: {ana_paula.nome} (ID: {ana_paula.id})")
            print(f"   Admin ID: {ana_paula.admin_id}")
            
            # Período de julho 2025
            data_inicio = date(2025, 7, 1)
            data_fim = date(2025, 7, 31)
            
            print(f"   Período: {data_inicio} a {data_fim}")
            
            # Calcular KPIs usando a função corrigida
            kpis = calcular_kpis_funcionario_periodo(ana_paula.id, data_inicio, data_fim)
            
            if not kpis:
                print("❌ Não foi possível calcular KPIs!")
                return False
            
            print("\n💰 CUSTOS CALCULADOS:")
            print(f"  Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
            print(f"  Custo Alimentação: R$ {kpis['custo_alimentacao']:.2f}")
            print(f"  Custo Transporte: R$ {kpis['custo_transporte']:.2f}")
            print(f"  Outros Custos: R$ {kpis['outros_custos']:.2f}")
            print(f"  Custo Total: R$ {kpis['custo_total']:.2f}")
            
            print("\n📊 OUTROS KPIS:")
            print(f"  Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
            print(f"  Horas Extras: {kpis['horas_extras']:.1f}h")
            print(f"  Faltas: {kpis['faltas']}")
            print(f"  Atrasos: {kpis['atrasos']}")
            print(f"  Produtividade: {kpis['produtividade']:.1f}%")
            print(f"  Absenteísmo: {kpis['absenteismo']:.1f}%")
            
            # Verificar valores esperados
            print("\n✅ VERIFICAÇÃO:")
            
            # Ana Paula deveria ter:
            # - Vale Transporte: R$ 220,00
            # - Vale Alimentação: R$ 440,00
            # - EPI (Capacete): R$ 85,00
            # - Desconto VT: -R$ 13,20
            
            if kpis['custo_transporte'] == 220.0:
                print(f"✅ Transporte CORRETO: R$ {kpis['custo_transporte']:.2f}")
            else:
                print(f"❌ Transporte INCORRETO: R$ {kpis['custo_transporte']:.2f} (esperado: R$ 220,00)")
            
            if kpis['custo_alimentacao'] >= 440.0:  # Pode ter refeições adicionais
                print(f"✅ Alimentação OK: R$ {kpis['custo_alimentacao']:.2f} (inclui vale + refeições)")
            else:
                print(f"❌ Alimentação INCORRETO: R$ {kpis['custo_alimentacao']:.2f} (esperado: pelo menos R$ 440,00)")
            
            if kpis['outros_custos'] >= 71.8:  # R$ 85,00 - R$ 13,20 = R$ 71,80
                print(f"✅ Outros Custos OK: R$ {kpis['outros_custos']:.2f}")
            else:
                print(f"❌ Outros Custos: R$ {kpis['outros_custos']:.2f} (esperado: pelo menos R$ 71,80)")
            
            # Sucesso se transporte estiver correto (principal problema)
            if kpis['custo_transporte'] == 220.0:
                print("\n🎉 SUCESSO! O transporte está sendo calculado corretamente!")
                print("🔄 A página de perfil deve mostrar os valores corretos agora")
                return True
            else:
                print("\n💥 AINDA HÁ PROBLEMAS no cálculo")
                return False
                
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    test_ana_paula_kpis()