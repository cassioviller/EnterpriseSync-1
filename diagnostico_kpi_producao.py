#!/usr/bin/env python3
"""
Diagnóstico completo dos KPIs em produção
Para identificar por que o Custo Transporte está R$ 0,00
"""

from app import app, db
from sqlalchemy import text
from datetime import datetime, date

def diagnostico_completo_kpis():
    """Faz diagnóstico completo dos KPIs"""
    with app.app_context():
        try:
            print("🔍 DIAGNÓSTICO COMPLETO DE KPIs EM PRODUÇÃO")
            print("=" * 60)
            
            # PASSO 1: Verificar período analisado na tela
            periodo_inicio = date(2025, 7, 1)
            periodo_fim = date(2025, 7, 31)
            
            print(f"\n📅 Analisando período: {periodo_inicio} a {periodo_fim}")
            
            # PASSO 2: Verificar todos os registros de outro_custo no período
            print("\n📋 Todos os registros de outro_custo no período:")
            registros = db.session.execute(text('''
                SELECT data, tipo, categoria, valor, kpi_associado, funcionario_id
                FROM outro_custo
                WHERE data BETWEEN :inicio AND :fim
                ORDER BY data, tipo
            '''), {'inicio': periodo_inicio, 'fim': periodo_fim}).fetchall()
            
            print(f"Total de registros encontrados: {len(registros)}")
            
            if registros:
                print("\nDetalhes dos registros:")
                for i, row in enumerate(registros[:10]):  # Mostrar primeiros 10
                    print(f"  {i+1}. {row[0]} | {row[1]} | {row[2]} | R$ {row[3]:.2f} | KPI: {row[4]} | Func: {row[5]}")
                
                if len(registros) > 10:
                    print(f"  ... e mais {len(registros)-10} registros")
            
            # PASSO 3: Verificar totais por KPI no período
            print(f"\n💰 Totais por KPI no período ({periodo_inicio} a {periodo_fim}):")
            totais_periodo = db.session.execute(text('''
                SELECT kpi_associado, 
                       COUNT(*) as total_registros,
                       SUM(CASE WHEN categoria = 'adicional' THEN valor ELSE 0 END) as adicional,
                       SUM(CASE WHEN categoria = 'desconto' THEN valor ELSE 0 END) as desconto,
                       SUM(CASE WHEN categoria = 'adicional' THEN valor 
                                WHEN categoria = 'desconto' THEN -valor 
                                ELSE 0 END) as liquido
                FROM outro_custo
                WHERE data BETWEEN :inicio AND :fim
                GROUP BY kpi_associado
                ORDER BY kpi_associado
            '''), {'inicio': periodo_inicio, 'fim': periodo_fim}).fetchall()
            
            for row in totais_periodo:
                print(f"  {row[0]}:")
                print(f"    Registros: {row[1]}")
                print(f"    Adicional: R$ {row[2]:.2f}")
                print(f"    Desconto: R$ {row[3]:.2f}")
                print(f"    LÍQUIDO: R$ {row[4]:.2f}")
            
            # PASSO 4: Verificar especificamente registros de transporte
            print("\n🚌 Registros específicos de TRANSPORTE no período:")
            transporte = db.session.execute(text('''
                SELECT data, tipo, categoria, valor, kpi_associado
                FROM outro_custo
                WHERE data BETWEEN :inicio AND :fim
                  AND (LOWER(tipo) LIKE '%transporte%' 
                       OR LOWER(tipo) LIKE '%vale transporte%' 
                       OR LOWER(tipo) IN ('vt', 'vale_transporte'))
                ORDER BY data
            '''), {'inicio': periodo_inicio, 'fim': periodo_fim}).fetchall()
            
            if transporte:
                total_transporte = 0
                print(f"Encontrados {len(transporte)} registros de transporte:")
                for row in transporte:
                    valor_liquido = row[3] if row[2] == 'adicional' else -row[3]
                    total_transporte += valor_liquido
                    print(f"  {row[0]} | {row[1]} | {row[2]} | R$ {row[3]:.2f} | KPI: {row[4]}")
                print(f"TOTAL TRANSPORTE: R$ {total_transporte:.2f}")
            else:
                print("❌ Nenhum registro de transporte encontrado no período!")
            
            # PASSO 5: Verificar registros de alimentação
            print("\n🍽️ Registros específicos de ALIMENTAÇÃO no período:")
            alimentacao = db.session.execute(text('''
                SELECT data, tipo, categoria, valor, kpi_associado
                FROM outro_custo
                WHERE data BETWEEN :inicio AND :fim
                  AND (LOWER(tipo) LIKE '%alimenta%' 
                       OR LOWER(tipo) LIKE '%vale alimenta%' 
                       OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao'))
                ORDER BY data
            '''), {'inicio': periodo_inicio, 'fim': periodo_fim}).fetchall()
            
            if alimentacao:
                total_alimentacao = 0
                print(f"Encontrados {len(alimentacao)} registros de alimentação:")
                for row in alimentacao:
                    valor_liquido = row[3] if row[2] == 'adicional' else -row[3]
                    total_alimentacao += valor_liquido
                    print(f"  {row[0]} | {row[1]} | {row[2]} | R$ {row[3]:.2f} | KPI: {row[4]}")
                print(f"TOTAL ALIMENTAÇÃO: R$ {total_alimentacao:.2f}")
            else:
                print("❌ Nenhum registro de alimentação encontrado no período!")
            
            # PASSO 6: Verificar se existe algum problema com o filtro de período
            print("\n📊 Verificação de dados fora do período (para comparação):")
            fora_periodo = db.session.execute(text('''
                SELECT COUNT(*) as total,
                       MIN(data) as data_min,
                       MAX(data) as data_max
                FROM outro_custo
                WHERE data NOT BETWEEN :inicio AND :fim
            '''), {'inicio': periodo_inicio, 'fim': periodo_fim}).fetchone()
            
            print(f"Registros fora do período: {fora_periodo[0]}")
            print(f"Data mínima: {fora_periodo[1]}")
            print(f"Data máxima: {fora_periodo[2]}")
            
            return True
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            return False

if __name__ == "__main__":
    diagnostico_completo_kpis()