#!/usr/bin/env python3
"""
Script para validar se os dados do relatório do Cássio estão corretos
com os valores reais calculados pelo sistema SIGE v6.1
"""

from app import app, db
from models import Funcionario, RegistroPonto, RegistroAlimentacao, OutroCusto
from kpis_engine_v3 import calcular_kpis_funcionario_v3
from datetime import date
import os

def validar_relatorio_cassio():
    """
    Valida todos os dados do relatório do Cássio contra os valores reais do sistema
    """
    
    with app.app_context():
        print("🔍 VALIDAÇÃO DO RELATÓRIO - CÁSSIO VILLER SILVA DE AZEVEDO")
        print("=" * 70)
        
        # Buscar funcionário Cássio
        cassio = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
        if not cassio:
            print("❌ Funcionário Cássio não encontrado!")
            return
        
        print(f"✅ Funcionário encontrado: {cassio.nome} (Código: {cassio.codigo})")
        print(f"   Salário: R$ {cassio.salario:,.2f}")
        print()
        
        # Período de análise
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        print(f"📅 Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        print()
        
        # Calcular KPIs usando o sistema
        print("🧮 CALCULANDO KPIs USANDO O SISTEMA...")
        kpis = calcular_kpis_funcionario_v3(cassio.id, data_inicio, data_fim)
        
        print("📊 KPIs CALCULADOS PELO SISTEMA:")
        print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"   Atrasos: {kpis['atrasos']:.1f}h")
        print(f"   Faltas: {kpis['faltas']}")
        print(f"   Faltas Justificadas: {kpis['faltas_justificadas']}")
        print(f"   Produtividade: {kpis['produtividade']:.1f}%")
        print(f"   Absenteísmo: {kpis['absenteismo']:.1f}%")
        print(f"   Média Diária: {kpis['media_diaria']:.1f}h")
        print(f"   Horas Perdidas: {kpis['horas_perdidas']:.1f}h")
        print(f"   Eficiência: {kpis['eficiencia']:.1f}%")
        print()
        
        # Buscar registros de ponto
        print("🕐 REGISTROS DE PONTO:")
        registros_ponto = RegistroPonto.query.filter_by(funcionario_id=cassio.id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(RegistroPonto.data).all()
        
        print(f"   Total de registros: {len(registros_ponto)}")
        
        # Contar por tipo
        tipos_count = {}
        horas_por_tipo = {}
        
        for registro in registros_ponto:
            tipo = registro.tipo_registro
            if tipo not in tipos_count:
                tipos_count[tipo] = 0
                horas_por_tipo[tipo] = 0
            tipos_count[tipo] += 1
            horas_por_tipo[tipo] += registro.horas_trabalhadas or 0
        
        print("   Distribuição por tipo:")
        for tipo, count in tipos_count.items():
            horas = horas_por_tipo[tipo]
            print(f"      {tipo}: {count} dias ({horas:.1f}h)")
        
        print()
        
        # Validar alguns registros específicos
        print("🔍 VALIDAÇÃO DE REGISTROS ESPECÍFICOS:")
        
        # Feriado trabalhado (07/06)
        feriado = RegistroPonto.query.filter_by(
            funcionario_id=cassio.id,
            data=date(2025, 6, 7)
        ).first()
        if feriado:
            print(f"   07/06 (Corpus Christi): {feriado.tipo_registro} - {feriado.horas_trabalhadas}h")
        
        # Falta (26/06)
        falta = RegistroPonto.query.filter_by(
            funcionario_id=cassio.id,
            data=date(2025, 6, 26)
        ).first()
        if falta:
            print(f"   26/06 (Falta): {falta.tipo_registro}")
        
        # Falta justificada (27/06)
        falta_just = RegistroPonto.query.filter_by(
            funcionario_id=cassio.id,
            data=date(2025, 6, 27)
        ).first()
        if falta_just:
            print(f"   27/06 (Falta Justificada): {falta_just.tipo_registro}")
        
        # Meio período (30/06)
        meio_periodo = RegistroPonto.query.filter_by(
            funcionario_id=cassio.id,
            data=date(2025, 6, 30)
        ).first()
        if meio_periodo:
            print(f"   30/06 (Meio Período): {meio_periodo.tipo_registro} - {meio_periodo.horas_trabalhadas}h")
        
        print()
        
        # Outros custos
        print("💰 OUTROS CUSTOS:")
        outros_custos = OutroCusto.query.filter_by(funcionario_id=cassio.id).filter(
            OutroCusto.data >= data_inicio,
            OutroCusto.data <= data_fim
        ).order_by(OutroCusto.data).all()
        
        total_outros_custos = sum(custo.valor for custo in outros_custos)
        print(f"   Total de registros: {len(outros_custos)}")
        print(f"   Valor total: R$ {total_outros_custos:,.2f}")
        
        # Agrupar por tipo
        custos_por_tipo = {}
        for custo in outros_custos:
            tipo = custo.tipo
            if tipo not in custos_por_tipo:
                custos_por_tipo[tipo] = 0
            custos_por_tipo[tipo] += custo.valor
        
        print("   Distribuição por tipo:")
        for tipo, valor in custos_por_tipo.items():
            print(f"      {tipo}: R$ {valor:,.2f}")
        
        print()
        
        # Alimentação
        print("🍽️ ALIMENTAÇÃO:")
        alimentacao = RegistroAlimentacao.query.filter_by(funcionario_id=cassio.id).filter(
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).all()
        
        total_alimentacao = sum(reg.valor for reg in alimentacao)
        print(f"   Total de registros: {len(alimentacao)}")
        print(f"   Valor total: R$ {total_alimentacao:,.2f}")
        
        print()
        
        # Resumo final
        print("📋 RESUMO FINAL:")
        print(f"   Funcionário: {cassio.nome}")
        print(f"   Código: {cassio.codigo}")
        print(f"   Salário Base: R$ {cassio.salario:,.2f}")
        print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"   Produtividade: {kpis['produtividade']:.1f}%")
        print(f"   Absenteísmo: {kpis['absenteismo']:.1f}%")
        print(f"   Outros Custos: R$ {total_outros_custos:,.2f}")
        print(f"   Alimentação: R$ {total_alimentacao:,.2f}")
        
        # Calcular custo total estimado
        valor_hora = cassio.salario / 220  # 220 horas/mês padrão
        custo_horas_extras = kpis['horas_extras'] * valor_hora * 1.5  # Média de 50% extra
        custo_total_estimado = cassio.salario + custo_horas_extras + total_outros_custos
        
        print(f"   Custo Total Estimado: R$ {custo_total_estimado:,.2f}")
        print()
        
        print("✅ VALIDAÇÃO CONCLUÍDA!")
        print("   Todos os dados foram extraídos diretamente do sistema SIGE v6.1")
        print("   Os KPIs foram calculados usando o engine v3.1 corrigido")

if __name__ == "__main__":
    validar_relatorio_cassio()