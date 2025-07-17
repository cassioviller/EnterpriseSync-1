#!/usr/bin/env python3
"""
Script para testar as correções dos KPIs v3.1
Valida se os cálculos estão usando dias_com_lancamento ao invés de dias_uteis
"""

from datetime import date
from app import app, db
from models import Funcionario, RegistroPonto
from kpis_engine_v3 import calcular_kpis_funcionario_v3


def main():
    """
    Testa as correções dos KPIs para o funcionário Cássio
    """
    with app.app_context():
        # Buscar Cássio
        cassio = Funcionario.query.filter_by(codigo='F0006').first()
        if not cassio:
            print("❌ Funcionário Cássio não encontrado")
            return
        
        print(f"🔍 Testando KPIs corrigidos para: {cassio.nome}")
        print("-" * 60)
        
        # Calcular KPIs para junho/2025
        kpis = calcular_kpis_funcionario_v3(
            cassio.id,
            date(2025, 6, 1),
            date(2025, 6, 30)
        )
        
        if not kpis:
            print("❌ Erro ao calcular KPIs")
            return
        
        # Buscar registros para análise
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == cassio.id,
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).all()
        
        print(f"📊 Registros encontrados: {len(registros)}")
        
        # Mostrar tipos de registros
        tipos_registros = {}
        for registro in registros:
            tipo = registro.tipo_registro
            tipos_registros[tipo] = tipos_registros.get(tipo, 0) + 1
        
        print("\n📋 Tipos de registros:")
        for tipo, count in tipos_registros.items():
            print(f"  - {tipo}: {count}")
        
        print("\n" + "=" * 60)
        print("🎯 RESULTADOS DOS KPIs CORRIGIDOS")
        print("=" * 60)
        
        # Dados base
        print(f"📅 Período: {kpis['periodo']}")
        print(f"📊 Dias com lançamento: {kpis['dias_com_lancamento']}")
        print(f"⏰ Horas esperadas: {kpis['horas_esperadas']}h")
        
        print("\n📈 KPIs Básicos:")
        print(f"  - Horas trabalhadas: {kpis['horas_trabalhadas']}h")
        print(f"  - Horas extras: {kpis['horas_extras']}h")
        print(f"  - Faltas: {kpis['faltas']}")
        print(f"  - Atrasos: {kpis['atrasos']}h")
        
        print("\n📊 KPIs Analíticos (CORRIGIDOS):")
        print(f"  - Produtividade: {kpis['produtividade']}%")
        print(f"  - Absenteísmo: {kpis['absenteismo']}%")
        print(f"  - Média diária: {kpis['media_diaria']}h")
        print(f"  - Faltas justificadas: {kpis['faltas_justificadas']}")
        
        print("\n💰 KPIs Financeiros:")
        print(f"  - Custo mão de obra: R$ {kpis['custo_mao_obra']:.2f}")
        print(f"  - Custo alimentação: R$ {kpis['custo_alimentacao']:.2f}")
        print(f"  - Outros custos: R$ {kpis['outros_custos']:.2f}")
        
        print("\n📋 KPIs Resumo:")
        print(f"  - Custo total: R$ {kpis['custo_total']:.2f}")
        print(f"  - Eficiência: {kpis['eficiencia']}%")
        print(f"  - Horas perdidas: {kpis['horas_perdidas']}h")
        
        # Validações específicas
        print("\n" + "=" * 60)
        print("✅ VALIDAÇÕES")
        print("=" * 60)
        
        # Esperado para Cássio: 14 dias com lançamento, 83h trabalhadas
        dias_esperados = 14
        horas_esperadas = 83.0
        produtividade_esperada = 74.1
        
        print(f"📊 Dias com lançamento: {kpis['dias_com_lancamento']} (esperado: {dias_esperados})")
        if kpis['dias_com_lancamento'] == dias_esperados:
            print("  ✅ CORRETO")
        else:
            print("  ❌ INCORRETO")
        
        print(f"⏰ Horas trabalhadas: {kpis['horas_trabalhadas']}h (esperado: {horas_esperadas}h)")
        if abs(kpis['horas_trabalhadas'] - horas_esperadas) < 0.1:
            print("  ✅ CORRETO")
        else:
            print("  ❌ INCORRETO")
        
        print(f"📈 Produtividade: {kpis['produtividade']}% (esperado: ~{produtividade_esperada}%)")
        if abs(kpis['produtividade'] - produtividade_esperada) < 1.0:
            print("  ✅ CORRETO")
        else:
            print("  ❌ INCORRETO")
        
        # Validação da fórmula
        produtividade_calculada = (kpis['horas_trabalhadas'] / kpis['horas_esperadas']) * 100
        print(f"\n🧮 Verificação da fórmula:")
        print(f"  Produtividade = {kpis['horas_trabalhadas']}h ÷ {kpis['horas_esperadas']}h × 100")
        print(f"  Produtividade = {produtividade_calculada:.1f}%")
        
        if abs(kpis['produtividade'] - produtividade_calculada) < 0.1:
            print("  ✅ FÓRMULA CORRETA")
        else:
            print("  ❌ FÓRMULA INCORRETA")
        
        # Validação do absenteísmo
        absenteismo_calculado = (kpis['faltas'] / kpis['dias_com_lancamento']) * 100
        print(f"\n🧮 Verificação do absenteísmo:")
        print(f"  Absenteísmo = {kpis['faltas']} ÷ {kpis['dias_com_lancamento']} × 100")
        print(f"  Absenteísmo = {absenteismo_calculado:.1f}%")
        
        if abs(kpis['absenteismo'] - absenteismo_calculado) < 0.1:
            print("  ✅ FÓRMULA CORRETA")
        else:
            print("  ❌ FÓRMULA INCORRETA")
        
        print("\n" + "=" * 60)
        print("🎯 RESUMO FINAL")
        print("=" * 60)
        
        if (kpis['dias_com_lancamento'] == dias_esperados and 
            abs(kpis['horas_trabalhadas'] - horas_esperadas) < 0.1 and
            abs(kpis['produtividade'] - produtividade_esperada) < 1.0):
            print("✅ TODAS AS CORREÇÕES IMPLEMENTADAS COM SUCESSO!")
            print("✅ Sistema agora usa dias_com_lancamento ao invés de dias_uteis")
            print("✅ Produtividade corrigida: 51.9% → 74.1%")
            print("✅ Absenteísmo corrigido: 5.0% → 7.1%")
        else:
            print("❌ ALGUMAS CORREÇÕES PRECISAM SER AJUSTADAS")
            print("❌ Verificar implementação das funções auxiliares")


if __name__ == "__main__":
    main()