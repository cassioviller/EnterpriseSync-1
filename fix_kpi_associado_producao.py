#!/usr/bin/env python3
"""
Script para corrigir associações de KPI em produção
Aplicar via comando direto no ambiente de produção
"""

from app import app, db
from sqlalchemy import text
import sys

def aplicar_correcao_kpi_producao():
    """Aplica correção de KPI associado em produção"""
    with app.app_context():
        try:
            print("🔧 CORREÇÃO DE KPI EM PRODUÇÃO")
            print("=" * 50)
            
            # PASSO 1: Verificar estado atual
            print("\n📊 Estado atual dos KPIs:")
            result = db.session.execute(text('''
                SELECT kpi_associado, COUNT(*) as total, SUM(valor) as soma_valor
                FROM outro_custo
                GROUP BY kpi_associado
                ORDER BY kpi_associado
            ''')).fetchall()
            
            for row in result:
                print(f"  {row[0]}: {row[1]} registros, R$ {row[2]:.2f}")
            
            # PASSO 2: Verificar registros que precisam ser corrigidos
            print("\n🔍 Registros que precisam correção:")
            problemas = db.session.execute(text('''
                SELECT tipo, kpi_associado, COUNT(*) as quantidade,
                       CASE 
                           WHEN LOWER(tipo) LIKE '%transporte%' OR LOWER(tipo) LIKE '%vale transporte%' OR LOWER(tipo) IN ('vt', 'vale_transporte') THEN 'custo_transporte'
                           WHEN LOWER(tipo) LIKE '%alimenta%' OR LOWER(tipo) LIKE '%vale alimenta%' OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao') THEN 'custo_alimentacao'
                           WHEN LOWER(tipo) LIKE '%semana viagem%' OR LOWER(tipo) LIKE '%viagem%' THEN 'custo_alimentacao'
                           ELSE 'outros_custos'
                       END as kpi_correto
                FROM outro_custo
                WHERE CASE 
                    WHEN LOWER(tipo) LIKE '%transporte%' OR LOWER(tipo) LIKE '%vale transporte%' OR LOWER(tipo) IN ('vt', 'vale_transporte') THEN 'custo_transporte'
                    WHEN LOWER(tipo) LIKE '%alimenta%' OR LOWER(tipo) LIKE '%vale alimenta%' OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao') THEN 'custo_alimentacao'
                    WHEN LOWER(tipo) LIKE '%semana viagem%' OR LOWER(tipo) LIKE '%viagem%' THEN 'custo_alimentacao'
                    ELSE 'outros_custos'
                END != kpi_associado
                GROUP BY tipo, kpi_associado, kpi_correto
                ORDER BY tipo
            ''')).fetchall()
            
            if problemas:
                print("❌ Problemas encontrados:")
                total_problemas = 0
                for row in problemas:
                    print(f"  {row[0]} → {row[1]} (deveria ser {row[3]}) - {row[2]} registros")
                    total_problemas += row[2]
                print(f"\nTotal de registros para corrigir: {total_problemas}")
            else:
                print("✅ Nenhum problema encontrado")
                return True
            
            # PASSO 3: Aplicar correção
            print(f"\n⚡ Aplicando correção em {total_problemas} registros...")
            
            updated = db.session.execute(text('''
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
            
            db.session.commit()
            print(f"✅ {updated} registros corrigidos com sucesso!")
            
            # PASSO 4: Verificar resultado final
            print("\n📈 Estado final dos KPIs:")
            result_final = db.session.execute(text('''
                SELECT kpi_associado, COUNT(*) as total, SUM(valor) as soma_valor
                FROM outro_custo
                GROUP BY kpi_associado
                ORDER BY kpi_associado
            ''')).fetchall()
            
            for row in result_final:
                print(f"  {row[0]}: {row[1]} registros, R$ {row[2]:.2f}")
            
            # PASSO 5: Verificação final
            verificacao = db.session.execute(text('''
                SELECT COUNT(*) 
                FROM outro_custo
                WHERE CASE 
                    WHEN LOWER(tipo) LIKE '%transporte%' OR LOWER(tipo) LIKE '%vale transporte%' OR LOWER(tipo) IN ('vt', 'vale_transporte') THEN 'custo_transporte'
                    WHEN LOWER(tipo) LIKE '%alimenta%' OR LOWER(tipo) LIKE '%vale alimenta%' OR LOWER(tipo) IN ('va', 'vale_alimentacao', 'refeicao') THEN 'custo_alimentacao'
                    WHEN LOWER(tipo) LIKE '%semana viagem%' OR LOWER(tipo) LIKE '%viagem%' THEN 'custo_alimentacao'
                    ELSE 'outros_custos'
                END != kpi_associado
            ''')).scalar()
            
            if verificacao == 0:
                print("\n✅ CORREÇÃO APLICADA COM SUCESSO!")
                print("✅ Todos os KPIs estão agora associados corretamente")
                return True
            else:
                print(f"\n❌ Ainda existem {verificacao} registros com problemas")
                return False
                
        except Exception as e:
            print(f"❌ ERRO: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("APLICAÇÃO DE CORREÇÃO KPI EM PRODUÇÃO")
    print("Executando correção...")
    
    success = aplicar_correcao_kpi_producao()
    
    if success:
        print("\n🎉 MISSÃO CUMPRIDA!")
        print("Os KPIs de transporte e alimentação agora mostrarão os valores corretos")
        sys.exit(0)
    else:
        print("\n💥 FALHA NA CORREÇÃO")
        print("Verifique os logs e tente novamente")
        sys.exit(1)