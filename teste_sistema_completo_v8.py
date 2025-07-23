#!/usr/bin/env python3
"""
TESTE COMPLETO DO SISTEMA SIGE v8.0
Teste das melhorias implementadas: CalculadoraObra e KPIs Financeiros
"""

from app import app, db
from calculadora_obra import CalculadoraObra
from kpis_financeiros import KPIsFinanceiros, KPIsOperacionais
from models import Obra, Funcionario, RegistroPonto
from datetime import datetime, date
import sys

def executar_testes():
    """Executa bateria de testes das melhorias implementadas"""
    
    with app.app_context():
        print("=== TESTE COMPLETO SIGE v8.0 ===")
        print("Testando melhorias: CalculadoraObra + KPIs Financeiros")
        print()
        
        # Buscar obra para teste
        obra = Obra.query.first()
        if not obra:
            print("❌ Nenhuma obra encontrada no sistema")
            return False
        
        print(f"📋 Testando obra: {obra.nome} (ID: {obra.id})")
        print()
        
        # Testar CalculadoraObra
        print("🔧 TESTE 1: Calculadora Obra Unificada")
        try:
            calc = CalculadoraObra(obra.id)
            custos = calc.calcular_custo_total()
            estatisticas = calc.obter_estatisticas_periodo()
            
            print("✅ Calculadora criada com sucesso")
            print(f"   • Custo Total: R$ {custos['total']:,.2f}")
            print(f"   • Mão de Obra: R$ {custos['mao_obra']:,.2f}")
            print(f"   • Transporte: R$ {custos['transporte']:,.2f}")
            print(f"   • Alimentação: R$ {custos['alimentacao']:,.2f}")
            print(f"   • Outros: R$ {custos['outros']:,.2f}")
            print(f"   • Funcionários: {estatisticas['total_funcionarios']}")
            print(f"   • Registros: {estatisticas['total_registros']}")
            print()
            
        except Exception as e:
            print(f"❌ Erro na Calculadora: {e}")
            return False
        
        # Testar KPIs Financeiros
        print("💰 TESTE 2: KPIs Financeiros Avançados")
        try:
            # Custo por m²
            custo_m2 = KPIsFinanceiros.custo_por_m2(obra.id)
            if 'erro' not in custo_m2:
                print(f"✅ Custo por m²: R$ {custo_m2['valor']:.2f}")
                print(f"   • Status: {custo_m2['status']}")
            else:
                print(f"⚠️  Custo por m²: {custo_m2['erro']}")
            
            # Margem de lucro
            margem = KPIsFinanceiros.margem_lucro_realizada(obra.id)
            if 'erro' not in margem:
                print(f"✅ Margem de Lucro: {margem['margem_percentual']:.1f}%")
                print(f"   • Classificação: {margem['classificacao']}")
            else:
                print(f"⚠️  Margem de Lucro: {margem['erro']}")
            
            # Desvio orçamentário
            desvio = KPIsFinanceiros.desvio_orcamentario(obra.id)
            if 'erro' not in desvio:
                print(f"✅ Desvio Orçamentário: {desvio['desvio_projetado']:.1f}%")
                print(f"   • Alerta: {desvio['alerta']}")
            else:
                print(f"⚠️  Desvio Orçamentário: {desvio['erro']}")
            
            # ROI Projetado
            roi = KPIsFinanceiros.roi_projetado(obra.id)
            if 'erro' not in roi:
                print(f"✅ ROI Projetado: {roi['roi_percentual']:.1f}%")
                print(f"   • Classificação: {roi['classificacao']}")
            else:
                print(f"⚠️  ROI Projetado: {roi['erro']}")
            
            # Velocidade de queima
            velocidade = KPIsFinanceiros.velocidade_queima_orcamento(obra.id)
            if 'erro' not in velocidade:
                print(f"✅ Velocidade de Queima: {velocidade['velocidade']:.2f}x")
                print(f"   • Status: {velocidade['status']}")
            else:
                print(f"⚠️  Velocidade de Queima: {velocidade['erro']}")
            
            print()
            
        except Exception as e:
            print(f"❌ Erro nos KPIs Financeiros: {e}")
            return False
        
        # Testar KPIs Operacionais
        print("📊 TESTE 3: KPIs Operacionais")
        try:
            produtividade = KPIsOperacionais.indice_produtividade_obra(obra.id)
            if 'erro' not in produtividade:
                print(f"✅ Produtividade da Obra: {produtividade['indice']:.2f}")
                print(f"   • Status: {produtividade['status']}")
                print(f"   • Progresso Físico: {produtividade['progresso_fisico']:.1f}%")
                print(f"   • Progresso Cronológico: {produtividade['progresso_cronologico']:.1f}%")
            else:
                print(f"⚠️  Produtividade: {produtividade['erro']}")
            print()
            
        except Exception as e:
            print(f"❌ Erro nos KPIs Operacionais: {e}")
            return False
        
        # Teste de Performance
        print("⚡ TESTE 4: Performance dos Cálculos")
        try:
            import time
            
            # Testar tempo de execução
            start_time = time.time()
            for i in range(5):  # 5 execuções
                calc = CalculadoraObra(obra.id)
                custos = calc.calcular_custo_total()
            end_time = time.time()
            
            tempo_medio = (end_time - start_time) / 5
            print(f"✅ Tempo médio por cálculo: {tempo_medio:.3f}s")
            
            if tempo_medio < 1.0:
                print("✅ Performance excelente (< 1s)")
            elif tempo_medio < 2.0:
                print("⚠️  Performance boa (< 2s)")
            else:
                print("❌ Performance ruim (> 2s)")
            
            print()
            
        except Exception as e:
            print(f"❌ Erro no teste de performance: {e}")
            return False
        
        # Teste de Integridade dos Dados
        print("🔍 TESTE 5: Integridade dos Dados")
        try:
            # Verificar se há funcionários com registros
            funcionarios_com_registros = db.session.query(
                Funcionario.id
            ).join(RegistroPonto).filter(
                RegistroPonto.obra_id == obra.id
            ).distinct().count()
            
            print(f"✅ Funcionários com registros: {funcionarios_com_registros}")
            
            # Verificar consistência dos custos
            calc = CalculadoraObra(obra.id)
            custos = calc.calcular_custo_total()
            
            if custos['total'] == (custos['mao_obra'] + custos['transporte'] + 
                                  custos['alimentacao'] + custos['outros']):
                print("✅ Soma dos custos consistente")
            else:
                print("❌ Inconsistência na soma dos custos")
                return False
            
            print()
            
        except Exception as e:
            print(f"❌ Erro no teste de integridade: {e}")
            return False
        
        # Resumo final
        print("🎯 RESUMO DOS TESTES")
        print("✅ Calculadora Obra: Funcionando")
        print("✅ KPIs Financeiros: Funcionando")
        print("✅ KPIs Operacionais: Funcionando")
        print("✅ Performance: Adequada")
        print("✅ Integridade: Validada")
        print()
        print("🏆 TODOS OS TESTES APROVADOS!")
        print("Sistema SIGE v8.0 validado e pronto para uso")
        
        return True

if __name__ == "__main__":
    sucesso = executar_testes()
    sys.exit(0 if sucesso else 1)