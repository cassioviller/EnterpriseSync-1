#!/usr/bin/env python3
"""
Script para debug das faltas do Pedro Lima Sousa
Verifica exatamente quais dias são considerados faltas
"""

from app import app, db
from kpis_engine_v3 import identificar_faltas_periodo, calcular_dias_uteis
from models import RegistroPonto, Funcionario
from datetime import datetime, date, timedelta
from sqlalchemy import and_

def debug_faltas_pedro():
    """Debug detalhado das faltas do Pedro"""
    
    with app.app_context():
        print("🔍 Debug das faltas do Pedro Lima Sousa...")
        
        # Buscar Pedro Lima Sousa
        pedro = Funcionario.query.filter_by(nome="Pedro Lima Sousa").first()
        if not pedro:
            print("❌ Pedro Lima Sousa não encontrado!")
            return
        
        # Período de junho 2025
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        print(f"📊 Período: {data_inicio} a {data_fim}")
        
        # Calcular dias úteis manualmente
        feriados_2025 = [
            date(2025, 1, 1),   # Ano Novo
            date(2025, 2, 17),  # Carnaval (Segunda-feira)
            date(2025, 2, 18),  # Carnaval (Terça-feira)
            date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
            date(2025, 4, 21),  # Tiradentes
            date(2025, 5, 1),   # Dia do Trabalhador
            date(2025, 6, 19),  # Corpus Christi
            date(2025, 9, 7),   # Independência
            date(2025, 10, 12), # Nossa Senhora Aparecida
            date(2025, 11, 2),  # Finados
            date(2025, 11, 15), # Proclamação da República
            date(2025, 12, 25)  # Natal
        ]
        
        # Verificar todos os dias de junho
        print("\n📅 Análise dia a dia de junho 2025:")
        print("=" * 60)
        
        data_atual = data_inicio
        dias_uteis_total = 0
        dias_com_registro = 0
        dias_falta = []
        
        while data_atual <= data_fim:
            dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
            eh_util = dia_semana < 5  # Segunda a sexta
            eh_feriado = data_atual in feriados_2025
            
            # Buscar registro de ponto
            registro = RegistroPonto.query.filter(
                and_(
                    RegistroPonto.funcionario_id == pedro.id,
                    RegistroPonto.data == data_atual
                )
            ).first()
            
            status = ""
            if eh_feriado:
                status = "FERIADO"
            elif not eh_util:
                status = "FIM DE SEMANA"
            elif registro and registro.hora_entrada:
                status = f"PRESENTE (entrada: {registro.hora_entrada})"
                dias_com_registro += 1
            elif eh_util and not eh_feriado:
                status = "FALTA"
                dias_falta.append(data_atual)
            
            if eh_util and not eh_feriado:
                dias_uteis_total += 1
            
            # Mapear dia da semana
            dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            dia_str = dias_semana[dia_semana]
            
            print(f"{data_atual} ({dia_str}): {status}")
            
            data_atual += timedelta(days=1)
        
        print("=" * 60)
        print(f"📊 Resumo manual:")
        print(f"   - Dias úteis total: {dias_uteis_total}")
        print(f"   - Dias com registro: {dias_com_registro}")
        print(f"   - Faltas identificadas: {len(dias_falta)}")
        
        print(f"\n📋 Datas de falta:")
        for falta in dias_falta:
            print(f"   - {falta}")
        
        # Comparar com a função do engine
        print(f"\n🔍 Comparação com função do engine:")
        faltas_engine = identificar_faltas_periodo(pedro.id, data_inicio, data_fim)
        dias_uteis_engine = calcular_dias_uteis(data_inicio, data_fim)
        
        print(f"   - Dias úteis (engine): {dias_uteis_engine}")
        print(f"   - Faltas (engine): {len(faltas_engine)}")
        
        print(f"\n📋 Faltas identificadas pelo engine:")
        for falta in sorted(faltas_engine):
            print(f"   - {falta}")
        
        # Verificar diferenças
        manual_set = set(dias_falta)
        engine_set = set(faltas_engine)
        
        diferenca_manual = manual_set - engine_set
        diferenca_engine = engine_set - manual_set
        
        if diferenca_manual:
            print(f"\n⚠️  Faltas identificadas manualmente mas não pelo engine:")
            for falta in diferenca_manual:
                print(f"   - {falta}")
        
        if diferenca_engine:
            print(f"\n⚠️  Faltas identificadas pelo engine mas não manualmente:")
            for falta in diferenca_engine:
                print(f"   - {falta}")
        
        if manual_set == engine_set:
            print(f"\n✅ Faltas identificadas corretamente!")
        else:
            print(f"\n❌ Discrepância na identificação de faltas!")

if __name__ == "__main__":
    debug_faltas_pedro()