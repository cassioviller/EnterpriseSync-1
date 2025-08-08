#!/usr/bin/env python3
"""
Teste da correção completa de KPI associado
Valida a lógica implementada no docker-entrypoint.sh
"""

from app import app, db
from sqlalchemy import text

def test_correcao_kpi_completa():
    """Testa a correção completa dos KPIs associados"""
    with app.app_context():
        try:
            print("🔧 Testando correção completa de KPI...")
            
            # PASSO 1: Verificar estado atual
            print("\n📊 Estado atual dos KPIs:")
            result = db.session.execute(text('''
                SELECT tipo, kpi_associado, COUNT(*) as quantidade
                FROM outro_custo
                GROUP BY tipo, kpi_associado
                ORDER BY tipo, kpi_associado
            ''')).fetchall()
            
            for row in result:
                print(f"  {row[0]} → {row[1]} ({row[2]} registros)")
            
            # PASSO 2: Simular correção (mesmo código do docker-entrypoint.sh)
            print("\n🔧 Executando correção de associações...")
            updated_kpis = db.session.execute(text('''
                UPDATE outro_custo 
                SET kpi_associado = CASE 
                    WHEN LOWER(tipo) LIKE '%transporte%' OR LOWER(tipo) LIKE '%vale transporte%' OR LOWER(tipo) IN ('vt', 'vale_transporte') THEN 'custo_transporte'
                    WHEN LOWER(tipo) LIKE '%alimenta%' OR LOWER(tipo) LIKE '%vale alimenta%' OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao') THEN 'custo_alimentacao'
                    WHEN LOWER(tipo) LIKE '%semana viagem%' OR LOWER(tipo) LIKE '%viagem%' THEN 'custo_alimentacao'
                    ELSE 'outros_custos'
                END
                WHERE CASE 
                    WHEN LOWER(tipo) LIKE '%transporte%' OR LOWER(tipo) LIKE '%vale transporte%' OR LOWER(tipo) IN ('vt', 'vale_transporte') THEN 'custo_transporte'
                    WHEN LOWER(tipo) LIKE '%alimenta%' OR LOWER(tipo) LIKE '%vale alimenta%' OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao') THEN 'custo_alimentacao'
                    WHEN LOWER(tipo) LIKE '%semana viagem%' OR LOWER(tipo) LIKE '%viagem%' THEN 'custo_alimentacao'
                    ELSE 'outros_custos'
                END != kpi_associado
            ''')).rowcount
            
            if updated_kpis > 0:
                db.session.commit()
                print(f'✅ {updated_kpis} associações de KPI corrigidas')
            else:
                print('✅ Associações de KPI já estão corretas')
            
            # PASSO 3: Verificar totais por KPI
            print("\n📈 Totais por KPI após correção:")
            totals = db.session.execute(text('''
                SELECT kpi_associado, 
                       COUNT(*) as total_registros,
                       SUM(CASE WHEN categoria = 'adicional' THEN valor ELSE 0 END) as valor_adicional,
                       SUM(CASE WHEN categoria = 'desconto' THEN valor ELSE 0 END) as valor_desconto,
                       SUM(CASE WHEN categoria = 'adicional' THEN valor 
                                WHEN categoria = 'desconto' THEN -valor 
                                ELSE 0 END) as valor_liquido
                FROM outro_custo
                GROUP BY kpi_associado
                ORDER BY kpi_associado
            ''')).fetchall()
            
            for row in totals:
                print(f"  {row[0]}:")
                print(f"    Registros: {row[1]}")
                print(f"    Valor Líquido: R$ {row[4]:.2f}")
                print(f"    (Adicional: R$ {row[2]:.2f}, Desconto: R$ {row[3]:.2f})")
            
            # PASSO 4: Verificar problemas remanescentes
            print("\n🔍 Verificando problemas remanescentes:")
            problemas = db.session.execute(text('''
                SELECT tipo, kpi_associado, COUNT(*) 
                FROM outro_custo
                WHERE CASE 
                    WHEN LOWER(tipo) LIKE '%transporte%' OR LOWER(tipo) LIKE '%vale transporte%' OR LOWER(tipo) IN ('vt', 'vale_transporte') THEN 'custo_transporte'
                    WHEN LOWER(tipo) LIKE '%alimenta%' OR LOWER(tipo) LIKE '%vale alimenta%' OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao') THEN 'custo_alimentacao'
                    WHEN LOWER(tipo) LIKE '%semana viagem%' OR LOWER(tipo) LIKE '%viagem%' THEN 'custo_alimentacao'
                    ELSE 'outros_custos'
                END != kpi_associado
                GROUP BY tipo, kpi_associado
            ''')).fetchall()
            
            if problemas:
                print("❌ Problemas encontrados:")
                for row in problemas:
                    print(f"  {row[0]} → {row[1]} ({row[2]} registros)")
            else:
                print("✅ Nenhum problema encontrado - todos os KPIs estão corretos!")
                
            return len(problemas) == 0
            
        except Exception as e:
            print(f'❌ Erro no teste: {e}')
            return False

if __name__ == "__main__":
    success = test_correcao_kpi_completa()
    exit(0 if success else 1)