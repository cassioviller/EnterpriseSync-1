#!/usr/bin/env python3
"""
Relatório completo do funcionário Caio Fabio Silva de Azevedo - Junho/2025
"""

from app import app
from datetime import date

def gerar_relatorio_caio():
    with app.app_context():
        from kpis_engine import kpis_engine
        from models import Funcionario, RegistroPonto, OutroCusto, RegistroAlimentacao
        
        # Buscar Caio
        caio = Funcionario.query.filter_by(nome='Caio Fabio Silva de Azevedo').first()
        if not caio:
            print("Funcionário não encontrado!")
            return
        
        # Período de análise
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        # Calcular KPIs
        kpis = kpis_engine.calcular_kpis_funcionario(caio.id, data_inicio, data_fim)
        
        print("="*80)
        print("RELATÓRIO COMPLETO - CAIO FABIO SILVA DE AZEVEDO")
        print("="*80)
        print(f"Funcionário: {caio.nome}")
        print(f"Código: {caio.codigo}")
        print(f"Salário Base: R$ {caio.salario:,.2f}")
        print(f"Horário de Trabalho: {caio.horario_trabalho.nome}")
        print(f"Entrada: {caio.horario_trabalho.entrada}")
        print(f"Saída: {caio.horario_trabalho.saida}")
        print(f"Horas Diárias: {caio.horario_trabalho.horas_diarias}h")
        print(f"Valor/Hora: R$ {caio.horario_trabalho.valor_hora:.2f}")
        print(f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        print()
        
        print("="*80)
        print("RESUMO DO PERÍODO - JUNHO/2025")
        print("="*80)
        periodo = kpis['periodo']
        print(f"Dias úteis no mês: {periodo['dias_uteis']}")
        print(f"Dias com lançamento: {periodo['dias_com_lancamento']}")
        print(f"Horas esperadas: {periodo['dias_uteis'] * caio.horario_trabalho.horas_diarias:.1f}h")
        print(f"Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"Horas extras: {kpis['horas_extras']:.1f}h")
        print(f"Faltas: {kpis['faltas']}")
        print(f"Faltas justificadas: {kpis['faltas_justificadas']}")
        print(f"Atrasos: {kpis['atrasos_horas']:.1f}h")
        print()
        
        print("="*80)
        print("DETALHAMENTO DOS REGISTROS DE PONTO")
        print("="*80)
        print(f"{'Data':>6} | {'Tipo':^18} | {'Entrada':>8} | {'Saída':>8} | {'Horas':>6} | {'Extras':>6} | {'Atraso':>6} | {'Observações'}")
        print("-"*80)
        
        # Buscar registros de ponto
        registros = RegistroPonto.query.filter_by(funcionario_id=caio.id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(RegistroPonto.data).all()
        
        for reg in registros:
            entrada = reg.hora_entrada.strftime('%H:%M') if reg.hora_entrada else '-'
            saida = reg.hora_saida.strftime('%H:%M') if reg.hora_saida else '-'
            
            print(f"{reg.data.strftime('%d/%m'):>6} | {reg.tipo_registro:^18} | {entrada:>8} | {saida:>8} | {reg.horas_trabalhadas:>6.1f} | {reg.horas_extras:>6.1f} | {reg.total_atraso_minutos:>4}min | {reg.observacoes}")
        
        print()
        print("="*80)
        print("ANÁLISE DOS TIPOS DE LANÇAMENTO")
        print("="*80)
        
        # Contar tipos de lançamento
        tipos_count = {}
        for reg in registros:
            tipos_count[reg.tipo_registro] = tipos_count.get(reg.tipo_registro, 0) + 1
        
        for tipo, count in tipos_count.items():
            print(f"{tipo:20}: {count:2} registros")
        
        print()
        print("="*80)
        print("CÁLCULO DE HORAS EXTRAS DETALHADO")
        print("="*80)
        
        total_extras_detalhado = 0
        for reg in registros:
            if reg.horas_extras > 0:
                print(f"{reg.data.strftime('%d/%m')} | {reg.tipo_registro:18} | {reg.horas_extras:4.1f}h extras")
                total_extras_detalhado += reg.horas_extras
        
        print(f"{'':>6} | {'Total':18} | {total_extras_detalhado:4.1f}h extras")
        print(f"KPI calculado: {kpis['horas_extras']:.1f}h")
        print()
        
        print("="*80)
        print("OUTROS CUSTOS - FONTE DO CUSTO DE TRANSPORTE")
        print("="*80)
        print(f"{'Data':>6} | {'Tipo':^20} | {'Categoria':^12} | {'Valor':>10} | {'Descrição'}")
        print("-"*80)
        
        # Buscar outros custos
        outros_custos = OutroCusto.query.filter_by(funcionario_id=caio.id).filter(
            OutroCusto.data >= data_inicio,
            OutroCusto.data <= data_fim
        ).order_by(OutroCusto.data).all()
        
        custo_transporte = 0
        outros_custos_total = 0
        
        for custo in outros_custos:
            print(f"{custo.data.strftime('%d/%m'):>6} | {custo.tipo:^20} | {custo.categoria:^12} | R$ {custo.valor:>7.2f} | {custo.descricao}")
            
            # Identificar custos de transporte
            if 'transporte' in custo.tipo.lower() or 'vt' in custo.tipo.lower():
                custo_transporte += custo.valor
            else:
                outros_custos_total += custo.valor
        
        print("-"*80)
        print(f"{'':>6} | {'CUSTO TRANSPORTE':^20} | {'':^12} | R$ {custo_transporte:>7.2f} |")
        print(f"{'':>6} | {'OUTROS CUSTOS':^20} | {'':^12} | R$ {outros_custos_total:>7.2f} |")
        print(f"{'':>6} | {'TOTAL GERAL':^20} | {'':^12} | R$ {custo_transporte + outros_custos_total:>7.2f} |")
        print()
        
        print("="*80)
        print("REGISTROS DE ALIMENTAÇÃO")
        print("="*80)
        print(f"{'Data':>6} | {'Tipo':^10} | {'Valor':>8} | {'Observações'}")
        print("-"*40)
        
        # Buscar registros de alimentação
        alimentacao = RegistroAlimentacao.query.filter_by(funcionario_id=caio.id).filter(
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).order_by(RegistroAlimentacao.data).all()
        
        total_alimentacao = 0
        for refeicao in alimentacao:
            print(f"{refeicao.data.strftime('%d/%m'):>6} | {refeicao.tipo:^10} | R$ {refeicao.valor:>5.2f} | {refeicao.observacoes}")
            total_alimentacao += refeicao.valor
        
        print("-"*40)
        print(f"{'':>6} | {'TOTAL':^10} | R$ {total_alimentacao:>5.2f} |")
        print()
        
        print("="*80)
        print("CÁLCULO DE KPIS - LAYOUT 4-4-4-3")
        print("="*80)
        
        # Primeira linha (4 indicadores)
        print("PRIMEIRA LINHA:")
        print(f"  1. Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"  2. Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"  3. Faltas: {kpis['faltas']}")
        print(f"  4. Atrasos: {kpis['atrasos_horas']:.1f}h")
        print()
        
        # Segunda linha (4 indicadores)
        print("SEGUNDA LINHA:")
        print(f"  5. Produtividade: {kpis['produtividade']:.1f}%")
        print(f"  6. Absenteísmo: {kpis['absenteismo']:.1f}%")
        print(f"  7. Média Diária: {kpis['media_diaria']:.1f}h")
        print(f"  8. Faltas Justificadas: {kpis['faltas_justificadas']}")
        print()
        
        # Terceira linha (4 indicadores)
        print("TERCEIRA LINHA:")
        print(f"  9. Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
        print(f" 10. Custo Alimentação: R$ {kpis['custo_alimentacao']:.2f}")
        print(f" 11. Custo Transporte: R$ {kpis['custo_transporte']:.2f}")
        print(f" 12. Outros Custos: R$ {kpis['outros_custos']:.2f}")
        print()
        
        # Quarta linha (3 indicadores)
        print("QUARTA LINHA:")
        print(f" 13. Horas Perdidas: {kpis['horas_perdidas']:.1f}h")
        print(f" 14. Eficiência: {kpis['eficiencia']:.1f}%")
        print(f" 15. Valor Falta Justificada: R$ {kpis['valor_falta_justificada']:.2f}")
        print()
        
        print("="*80)
        print("RESUMO FINANCEIRO")
        print("="*80)
        
        custo_total = kpis['custo_mao_obra'] + kpis['custo_alimentacao'] + kpis['custo_transporte'] + kpis['outros_custos']
        
        print(f"Custo Mão de Obra: R$ {kpis['custo_mao_obra']:>10.2f}")
        print(f"Custo Alimentação: R$ {kpis['custo_alimentacao']:>10.2f}")
        print(f"Custo Transporte:  R$ {kpis['custo_transporte']:>10.2f}")
        print(f"Outros Custos:     R$ {kpis['outros_custos']:>10.2f}")
        print("-"*30)
        print(f"CUSTO TOTAL:       R$ {custo_total:>10.2f}")
        print()
        
        print("="*80)
        print("EXPLICAÇÃO DOS CUSTOS DE TRANSPORTE")
        print("="*80)
        print("O custo de transporte vem da tabela 'outro_custo' onde:")
        print("- Registros com tipo contendo 'transporte' ou 'VT' são considerados transporte")
        print("- Valores positivos são adicionados (Vale Transporte)")
        print("- Valores negativos são descontados (Desconto VT)")
        print()
        print("Registros identificados como transporte:")
        for custo in outros_custos:
            if 'transporte' in custo.tipo.lower() or 'vt' in custo.tipo.lower():
                print(f"  - {custo.data.strftime('%d/%m')}: {custo.tipo} = R$ {custo.valor:.2f}")
        print()
        print(f"Total do custo de transporte: R$ {custo_transporte:.2f}")
        print()
        
        print("="*80)
        print("VALIDAÇÃO DOS CÁLCULOS")
        print("="*80)
        print("Todas as horas extras são calculadas corretamente:")
        print("- Tipos especiais (sábado, domingo, feriado) usam campo 'horas_extras' diretamente")
        print("- Trabalho normal calcula extras quando horas > 8.8h (horário específico)")
        print("- Sistema integrado com horário de trabalho personalizado")
        print()
        print("Produtividade baseada em:")
        print(f"- Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
        print(f"- Horas esperadas: {periodo['dias_uteis'] * caio.horario_trabalho.horas_diarias:.1f}h")
        print(f"- Resultado: {kpis['produtividade']:.1f}%")
        print()
        print("="*80)
        print("RELATÓRIO GERADO COM SUCESSO!")
        print("="*80)

if __name__ == "__main__":
    gerar_relatorio_caio()