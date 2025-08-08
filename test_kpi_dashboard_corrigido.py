#!/usr/bin/env python3
"""
Teste do dashboard de KPIs após correção
"""

from app import app, db
from kpi_unificado import KPIUnificado
from datetime import date

def test_kpi_dashboard():
    """Testa os KPIs do dashboard após correção"""
    with app.app_context():
        try:
            print("🔧 TESTE DO DASHBOARD DE KPIs APÓS CORREÇÃO")
            print("=" * 60)
            
            # Parâmetros do teste (mesmo período da tela)
            admin_id = 10  # Administrador Vale Verde (onde estão os dados)
            data_inicio = date(2025, 7, 1)
            data_fim = date(2025, 7, 31)
            
            print(f"Admin ID: {admin_id}")
            print(f"Período: {data_inicio} a {data_fim}")
            
            # Criar instância do KPI
            kpi = KPIUnificado(admin_id=admin_id, data_inicio=data_inicio, data_fim=data_fim)
            
            # Calcular custos detalhados
            print("\n💰 TESTE: Calcular custos detalhados")
            custos = kpi.calcular_custos_periodo()
            
            print("Resultados:")
            for tipo, valor in custos.items():
                print(f"  {tipo}: R$ {valor:.2f}")
            
            # Testar dashboard completo
            print("\n📊 TESTE: Dashboard completo")
            dashboard_data = kpi.calcular_kpis_dashboard()
            
            if 'custos_detalhados' in dashboard_data:
                custos_dash = dashboard_data['custos_detalhados']
                print("Custos no dashboard:")
                print(f"  Alimentação: R$ {custos_dash.get('alimentacao', 0):.2f}")
                print(f"  Transporte: R$ {custos_dash.get('transporte', 0):.2f}")
                print(f"  Outros: R$ {custos_dash.get('outros', 0):.2f}")
                print(f"  Mão de Obra: R$ {custos_dash.get('mao_obra', 0):.2f}")
                print(f"  Total: R$ {custos_dash.get('total', 0):.2f}")
            
            # Verificar se os valores batem com nossa expectativa
            print("\n✅ VERIFICAÇÃO:")
            transporte_esperado = 880.00  # 4 registros de R$ 220 (Vale Transporte)
            alimentacao_esperada = 2390.50  # R$ 1760 (Vale Alimentação) + R$ 630.50 (Refeições obra)
            
            transporte_atual = custos.get('transporte', 0)
            alimentacao_atual = custos.get('alimentacao', 0)
            
            if transporte_atual == transporte_esperado:
                print(f"✅ Transporte CORRETO: R$ {transporte_atual:.2f}")
            else:
                print(f"❌ Transporte INCORRETO: R$ {transporte_atual:.2f} (esperado: R$ {transporte_esperado:.2f})")
            
            if alimentacao_atual == alimentacao_esperada:
                print(f"✅ Alimentação CORRETO: R$ {alimentacao_atual:.2f}")
            else:
                print(f"❌ Alimentação INCORRETO: R$ {alimentacao_atual:.2f} (esperado: R$ {alimentacao_esperada:.2f})")
            
            # Se tudo estiver correto
            if transporte_atual == transporte_esperado and alimentacao_atual == alimentacao_esperada:
                print("\n🎉 SUCESSO! Os KPIs estão calculando corretamente!")
                print("🔄 Agora o dashboard deve mostrar os valores corretos")
                return True
            else:
                print("\n💥 PROBLEMA AINDA EXISTE")
                return False
                
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    test_kpi_dashboard()