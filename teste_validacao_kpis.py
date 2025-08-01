#!/usr/bin/env python3
"""
Teste de Validação Cruzada dos KPIs
Compara engine atual vs engine corrigido
"""

from app import app, db
from models import Funcionario
from kpis_engine import KPIsEngine
from kpis_engine_corrigido import CorrectedKPIService, KPIValidationService
from datetime import date

def executar_validacao_completa():
    """Executa validação completa dos KPIs"""
    with app.app_context():
        print("=" * 100)
        print("VALIDAÇÃO CRUZADA DE KPIs - ENGINE ATUAL VS CORRIGIDO")
        print("=" * 100)
        
        # Buscar funcionário de teste
        funcionario = Funcionario.query.filter_by(nome='Teste Completo KPIs').first()
        if not funcionario:
            print("❌ Funcionário de teste não encontrado")
            return
        
        print(f"\n🔍 FUNCIONÁRIO: {funcionario.nome} (ID: {funcionario.id})")
        print(f"📅 PERÍODO: Julho/2025")
        
        # Executar ambos os engines
        print("\n" + "=" * 100)
        print("EXECUTANDO CÁLCULOS...")
        print("=" * 100)
        
        # Engine atual
        print("⚙️  Executando engine atual...")
        engine_atual = KPIsEngine()
        kpis_atual = engine_atual.calcular_kpis_funcionario(
            funcionario.id, 
            date(2025, 7, 1), 
            date(2025, 7, 31)
        )
        
        # Engine corrigido
        print("⚙️  Executando engine corrigido...")
        engine_corrigido = CorrectedKPIService()
        kpis_corrigido = engine_corrigido.calcular_kpis_funcionario(
            funcionario.id,
            date(2025, 7, 1), 
            date(2025, 7, 31)
        )
        
        # Validação cruzada
        print("✅ Executando validação cruzada...")
        validator = KPIValidationService()
        validacao = validator.validate_employee_kpis(
            funcionario.id,
            date(2025, 7, 1), 
            date(2025, 7, 31)
        )
        
        # Mostrar resultados
        print("\n" + "=" * 100)
        print("COMPARAÇÃO DE RESULTADOS")
        print("=" * 100)
        
        kpis_comparar = [
            ('horas_trabalhadas', 'Horas Trabalhadas'),
            ('horas_extras', 'Horas Extras'),
            ('faltas', 'Faltas'),
            ('atrasos_horas', 'Atrasos (h)'),
            ('produtividade', 'Produtividade (%)'),
            ('absenteismo', 'Absenteísmo (%)'),
            ('media_diaria', 'Média Diária (h)'),
            ('faltas_justificadas', 'Faltas Justificadas'),
            ('custo_mao_obra', 'Custo Mão de Obra'),
            ('custo_alimentacao', 'Custo Alimentação'),
            ('horas_perdidas', 'Horas Perdidas'),
            ('eficiencia', 'Eficiência (%)')
        ]
        
        print(f"{'KPI':<25} | {'ATUAL':<12} | {'CORRIGIDO':<12} | {'DIFERENÇA':<12} | {'STATUS'}")
        print("-" * 80)
        
        total_diferencas = 0
        for key, nome in kpis_comparar:
            valor_atual = kpis_atual.get(key, 0)
            valor_corrigido = kpis_corrigido.get(key, 0)
            
            # Tratar valores None
            if valor_atual is None:
                valor_atual = 0
            if valor_corrigido is None:
                valor_corrigido = 0
                
            diferenca = abs(float(valor_atual) - float(valor_corrigido))
            
            if diferenca > 0.01:
                status = "❌ DIFERENTE"
                total_diferencas += 1
            else:
                status = "✅ IGUAL"
            
            # Formatação baseada no tipo de valor
            if key in ['custo_mao_obra', 'custo_alimentacao', 'valor_falta_justificada']:
                atual_fmt = f"R$ {valor_atual:.2f}"
                corrigido_fmt = f"R$ {valor_corrigido:.2f}"
                diff_fmt = f"R$ {diferenca:.2f}"
            elif key in ['produtividade', 'absenteismo', 'eficiencia']:
                atual_fmt = f"{valor_atual:.1f}%"
                corrigido_fmt = f"{valor_corrigido:.1f}%"
                diff_fmt = f"{diferenca:.1f}%"
            elif key in ['horas_trabalhadas', 'horas_extras', 'atrasos_horas', 'media_diaria', 'horas_perdidas']:
                atual_fmt = f"{valor_atual:.1f}h"
                corrigido_fmt = f"{valor_corrigido:.1f}h"
                diff_fmt = f"{diferenca:.1f}h"
            else:
                atual_fmt = str(valor_atual)
                corrigido_fmt = str(valor_corrigido)
                diff_fmt = str(diferenca)
            
            print(f"{nome:<25} | {atual_fmt:<12} | {corrigido_fmt:<12} | {diff_fmt:<12} | {status}")
        
        print("\n" + "=" * 100)
        print("RESUMO DA VALIDAÇÃO")
        print("=" * 100)
        
        if total_diferencas == 0:
            print("✅ SUCESSO: Todos os KPIs estão consistentes entre os engines!")
            print("✅ Os valores nos cards e detalhes serão idênticos.")
        else:
            print(f"⚠️  ATENÇÃO: {total_diferencas} KPIs com diferenças detectadas.")
            print("🔧 Recomenda-se usar o engine corrigido para garantir consistência.")
        
        # Mostrar detalhes das principais diferenças
        if validacao['diferencas']:
            print("\n📋 DETALHES DAS PRINCIPAIS DIFERENÇAS:")
            for key, diff in validacao['diferencas'].items():
                print(f"  • {key}: {diff['atual']} → {diff['corrigido']} (Δ {diff['diferenca']})")
        
        print("\n" + "=" * 100)
        print("ANÁLISE DE TIPOS DE REGISTRO")
        print("=" * 100)
        
        # Analisar tipos de registro utilizados
        from models import RegistroPonto
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).all()
        
        tipos_contagem = {}
        for registro in registros:
            tipo = registro.tipo_registro or 'undefined'
            tipos_contagem[tipo] = tipos_contagem.get(tipo, 0) + 1
        
        print("TIPOS DE REGISTRO ENCONTRADOS:")
        for tipo, count in sorted(tipos_contagem.items()):
            print(f"  • {tipo}: {count} ocorrências")
        
        print("\n✅ VALIDAÇÃO CONCLUÍDA")
        
        return {
            'consistent': total_diferencas == 0,
            'differences_count': total_diferencas,
            'kpis_atual': kpis_atual,
            'kpis_corrigido': kpis_corrigido
        }

if __name__ == "__main__":
    resultado = executar_validacao_completa()