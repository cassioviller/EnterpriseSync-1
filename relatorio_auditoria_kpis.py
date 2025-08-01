#!/usr/bin/env python3
"""
Relatório de Auditoria de KPIs
Identifica inconsistências e valida cálculos
"""

from app import app, db
from models import Funcionario, Usuario
from kpis_engine import KPIsEngine
from kpis_engine_corrigido import CorrectedKPIService, KPIValidationService
from datetime import date, datetime
import json

def gerar_relatorio_auditoria_completo():
    """Gera relatório completo de auditoria de KPIs"""
    with app.app_context():
        print("=" * 100)
        print("RELATÓRIO DE AUDITORIA DE KPIs - SISTEMA SIGE")
        print("=" * 100)
        
        # Buscar funcionários ativos
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        
        print(f"📊 TOTAL DE FUNCIONÁRIOS ATIVOS: {len(funcionarios)}")
        print(f"📅 PERÍODO DE ANÁLISE: Julho/2025")
        
        validator = KPIValidationService()
        resultados_auditoria = []
        
        funcionarios_inconsistentes = 0
        total_diferencas = 0
        
        print("\n" + "=" * 100)
        print("AUDITORIA POR FUNCIONÁRIO")
        print("=" * 100)
        
        for funcionario in funcionarios:
            print(f"\n🔍 Auditando: {funcionario.nome} (ID: {funcionario.id})")
            
            try:
                validacao = validator.validate_employee_kpis(
                    funcionario.id,
                    date(2025, 7, 1),
                    date(2025, 7, 31)
                )
                
                if not validacao['is_consistent']:
                    funcionarios_inconsistentes += 1
                    num_diferencas = len(validacao['diferencas'])
                    total_diferencas += num_diferencas
                    
                    print(f"  ⚠️  {num_diferencas} inconsistências detectadas:")
                    for kpi, diff in validacao['diferencas'].items():
                        print(f"    • {kpi}: {diff['atual']} → {diff['corrigido']} (Δ {diff['diferenca']:.2f})")
                    
                    resultados_auditoria.append({
                        'funcionario_id': funcionario.id,
                        'funcionario_nome': funcionario.nome,
                        'inconsistencias': num_diferencas,
                        'detalhes': validacao['diferencas']
                    })
                else:
                    print("  ✅ KPIs consistentes")
                    
            except Exception as e:
                print(f"  ❌ Erro na auditoria: {str(e)}")
        
        print("\n" + "=" * 100)
        print("RESUMO EXECUTIVO DA AUDITORIA")
        print("=" * 100)
        
        print(f"📈 ESTATÍSTICAS GERAIS:")
        print(f"  • Total de funcionários auditados: {len(funcionarios)}")
        print(f"  • Funcionários com inconsistências: {funcionarios_inconsistentes}")
        print(f"  • Taxa de consistência: {((len(funcionarios) - funcionarios_inconsistentes) / len(funcionarios) * 100):.1f}%")
        print(f"  • Total de diferenças encontradas: {total_diferencas}")
        
        if funcionarios_inconsistentes > 0:
            print(f"\n⚠️  AÇÃO REQUERIDA:")
            print(f"  • {funcionarios_inconsistentes} funcionários precisam de correção nos KPIs")
            print(f"  • Recomenda-se migrar para o engine corrigido")
            print(f"  • Implementar validações automáticas")
        else:
            print(f"\n✅ SISTEMA ÍNTEGRO:")
            print(f"  • Todos os KPIs estão consistentes")
            print(f"  • Não há necessidade de correções")
        
        print("\n" + "=" * 100)
        print("KPIs MAIS AFETADOS")
        print("=" * 100)
        
        # Contar quais KPIs têm mais problemas
        kpis_problemas = {}
        for resultado in resultados_auditoria:
            for kpi in resultado['detalhes'].keys():
                kpis_problemas[kpi] = kpis_problemas.get(kpi, 0) + 1
        
        if kpis_problemas:
            print("KPIs com mais inconsistências:")
            for kpi, count in sorted(kpis_problemas.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {kpi}: {count} funcionários afetados")
        
        print("\n" + "=" * 100)
        print("RECOMENDAÇÕES TÉCNICAS")
        print("=" * 100)
        
        print("1. ⚙️  MIGRAÇÃO DE ENGINE:")
        print("   • Substituir KPIsEngine por CorrectedKPIService")
        print("   • Atualizar views.py para usar engine corrigido")
        print("   • Implementar transição gradual")
        
        print("\n2. 🔧 CORREÇÕES DE TIPOS:")
        print("   • Padronizar tipos de lançamento de ponto")
        print("   • Atualizar interface de cadastro")
        print("   • Criar validações de entrada")
        
        print("\n3. ✅ VALIDAÇÕES AUTOMÁTICAS:")
        print("   • Implementar auditoria automática diária")
        print("   • Criar alertas para inconsistências")
        print("   • Dashboard de qualidade de dados")
        
        print("\n4. 📊 MONITORAMENTO:")
        print("   • Logs de cálculo de KPIs")
        print("   • Métricas de performance")
        print("   • Relatórios de tendências")
        
        print("\n✅ AUDITORIA CONCLUÍDA")
        
        return {
            'total_funcionarios': len(funcionarios),
            'funcionarios_inconsistentes': funcionarios_inconsistentes,
            'total_diferencas': total_diferencas,
            'resultados': resultados_auditoria,
            'kpis_problemas': kpis_problemas
        }

if __name__ == "__main__":
    resultado = gerar_relatorio_auditoria_completo()