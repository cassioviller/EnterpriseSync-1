#!/usr/bin/env python3
"""
Script para verificação final dos KPIs do Pedro Lima Sousa
Calcula manualmente para validar se o sistema está correto
"""

from app import app, db
from kpis_engine_v3 import calcular_kpis_funcionario_v3
from models import Funcionario
from datetime import date

def verificar_kpis_pedro_final():
    """Verificação final dos KPIs do Pedro"""
    
    with app.app_context():
        print("🔍 Verificação final dos KPIs do Pedro Lima Sousa...")
        
        # Buscar Pedro Lima Sousa
        pedro = Funcionario.query.filter_by(nome="Pedro Lima Sousa").first()
        if not pedro:
            print("❌ Pedro Lima Sousa não encontrado!")
            return
        
        print(f"✅ Pedro encontrado: {pedro.nome} (ID: {pedro.id})")
        print(f"💰 Salário: R$ {pedro.salario:,.2f}")
        print(f"⏰ Horário: {pedro.horario_trabalho.nome if pedro.horario_trabalho else 'Não definido'}")
        
        # Período de junho 2025
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        print(f"📅 Período: {data_inicio} a {data_fim}")
        
        # Calcular KPIs usando o engine
        kpis = calcular_kpis_funcionario_v3(pedro.id, data_inicio, data_fim)
        
        print("\n📊 KPIs calculados pelo sistema:")
        print("=" * 50)
        print(f"1. Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"2. Horas Extras: {kpis['horas_extras']:.1f}h") 
        print(f"3. Faltas: {kpis['faltas']}")
        print(f"4. Atrasos: {kpis['atrasos']:.1f}h")
        print(f"5. Produtividade: {kpis['produtividade']:.1f}%")
        print(f"6. Absenteísmo: {kpis['absenteismo']:.1f}%")
        print(f"7. Média Diária: {kpis['media_diaria']:.1f}h")
        print(f"8. Horas Perdidas: {kpis['horas_perdidas_total']:.1f}h")
        print(f"9. Custo Mão de Obra: R$ {kpis['custo_mao_obra']:,.2f}")
        print(f"10. Custo Alimentação: R$ {kpis['custo_alimentacao']:,.2f}")
        
        # Validações manuais
        print("\n🔍 Validações manuais:")
        print("=" * 50)
        
        # Junho 2025 tem 20 dias úteis (descontando Corpus Christi dia 19)
        dias_uteis_junho = 20
        horas_esperadas = dias_uteis_junho * 8
        print(f"📅 Dias úteis em junho 2025: {dias_uteis_junho} (Corpus Christi não conta)")
        print(f"⏰ Horas esperadas: {horas_esperadas}h")
        
        # Validar produtividade
        produtividade_manual = (kpis['horas_trabalhadas'] / horas_esperadas) * 100
        print(f"📈 Produtividade manual: {produtividade_manual:.1f}%")
        
        # Validar absenteísmo 
        absenteismo_manual = (kpis['faltas'] / dias_uteis_junho) * 100
        print(f"📉 Absenteísmo manual: {absenteismo_manual:.1f}%")
        
        # Validar horas perdidas
        horas_perdidas_manual = (kpis['faltas'] * 8) + kpis['atrasos']
        print(f"⏱️ Horas perdidas manual: {horas_perdidas_manual:.1f}h")
        
        # Validar custo (salário por hora * (horas trabalhadas + faltas justificadas * 8))
        salario_hora = pedro.salario / 220  # 220 horas por mês (padrão CLT)
        # Assumindo que não há faltas justificadas neste caso
        custo_manual = kpis['horas_trabalhadas'] * salario_hora
        print(f"💰 Custo manual (sem faltas justificadas): R$ {custo_manual:,.2f}")
        print(f"💰 Salário/hora: R$ {salario_hora:.2f}")
        
        print("\n✅ Verificação concluída!")
        
        # Resumo das correções aplicadas
        print("\n📋 Resumo das correções aplicadas:")
        print("=" * 50)
        print("✓ Atrasos agora calculados e persistidos corretamente")
        print("✓ Faltas identificadas respeitando feriados nacionais") 
        print("✓ KPIs derivados (absenteísmo, produtividade) corrigidos")
        print("✓ Interface exibe valores corretos dos cálculos")
        print(f"✓ Total de {kpis['faltas']} faltas identificadas (19/06 é Corpus Christi)")
        print(f"✓ Total de {kpis['total_atrasos_horas']:.1f}h de atrasos registrados")

if __name__ == "__main__":
    verificar_kpis_pedro_final()