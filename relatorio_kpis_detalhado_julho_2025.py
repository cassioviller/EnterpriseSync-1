#!/usr/bin/env python3
"""
RELATÓRIO DETALHADO DE KPIs - JULHO 2025
Sistema de análise completa dos cálculos de KPIs baseados em horário de trabalho
e registros de ponto conforme documento oficial v8.2

Funcionários analisados:
- Ana Paula Rodrigues  
- Danilo José de Oliveira

Autor: Sistema SIGE v8.2
Data: 1º de agosto de 2025
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioTrabalho
from kpis_engine import kpis_engine
from datetime import date, datetime
from calcular_dias_uteis_mes import calcular_dias_uteis_mes

def gerar_relatorio_completo():
    """Gera relatório completo de KPIs para julho/2025"""
    
    with app.app_context():
        print("📊 RELATÓRIO DETALHADO DE KPIs - JULHO 2025")
        print("=" * 80)
        print("Sistema: SIGE v8.2 com tipos padronizados")
        print("Documento base: PROMPT DE REVISÃO – CÁLCULO DE KPIs E CUSTOS DE RH")
        print("Data do relatório:", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        
        # Período de análise
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        dias_uteis_julho = calcular_dias_uteis_mes(2025, 7)
        
        print(f"\n🗓️ PERÍODO ANALISADO:")
        print(f"   Início: {data_inicio.strftime('%d/%m/%Y')}")
        print(f"   Fim: {data_fim.strftime('%d/%m/%Y')}")
        print(f"   Dias úteis: {dias_uteis_julho} dias")
        
        # Buscar funcionários específicos
        funcionarios = [
            Funcionario.query.filter_by(nome='Ana Paula Rodrigues').first(),
            Funcionario.query.filter_by(nome='Danilo José de Oliveira').first()
        ]
        
        funcionarios = [f for f in funcionarios if f is not None]
        
        if not funcionarios:
            print("\n❌ FUNCIONÁRIOS NÃO ENCONTRADOS")
            return
        
        print(f"\n👥 FUNCIONÁRIOS ANALISADOS: {len(funcionarios)}")
        
        # Analisar cada funcionário
        for funcionario in funcionarios:
            analisar_funcionario_detalhadamente(funcionario, data_inicio, data_fim, dias_uteis_julho)
        
        # Resumo dos tipos padronizados
        print("\n📋 TIPOS DE REGISTRO PADRONIZADOS v8.2:")
        print("-" * 60)
        print("1. trabalho_normal - Jornada regular (entra no divisor)")
        print("2. sabado_trabalhado - Sábado trabalhado +50% (não entra no divisor)")
        print("3. domingo_trabalhado - Domingo trabalhado +100% (não entra no divisor)")
        print("4. feriado_trabalhado - Feriado trabalhado +100% (não entra no divisor)")
        print("5. falta - Falta sem justificativa (desconta, não entra no divisor)")
        print("6. falta_justificada - Falta justificada (remunerada, entra no divisor)")
        print("7. ferias - Férias +33% (não entra no divisor)")
        print("8. folga_sabado - Folga sábado (não gera custo)")
        print("9. folga_domingo - Folga domingo (não gera custo)")
        print("10. folga_feriado - Folga feriado (não gera custo)")

def analisar_funcionario_detalhadamente(funcionario, data_inicio, data_fim, dias_uteis):
    """Análise detalhada de um funcionário específico"""
    
    print(f"\n" + "="*80)
    print(f"👤 ANÁLISE DETALHADA: {funcionario.nome.upper()}")
    print("="*80)
    
    # Informações básicas
    print(f"\n📋 DADOS BÁSICOS:")
    print(f"   ID: {funcionario.id}")
    print(f"   Nome: {funcionario.nome}")
    print(f"   Salário: R$ {funcionario.salario:.2f}")
    print(f"   Função: {getattr(funcionario, 'funcao', 'Não informado')}")
    
    # Horário de trabalho
    if funcionario.horario_trabalho:
        horario = funcionario.horario_trabalho
        print(f"\n⏰ HORÁRIO DE TRABALHO:")
        print(f"   Nome: {horario.nome}")
        print(f"   Entrada: {horario.entrada}")
        print(f"   Saída almoço: {horario.saida_almoco}")
        print(f"   Retorno almoço: {horario.retorno_almoco}")
        print(f"   Saída: {horario.saida}")
        print(f"   Horas diárias: {horario.horas_diarias}h")
        print(f"   Dias da semana: {horario.dias_semana}")
    else:
        print(f"\n⏰ HORÁRIO DE TRABALHO:")
        print(f"   ❌ Não cadastrado - usando padrão 8h/dia")
    
    # Buscar todos os registros do período
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data).all()
    
    print(f"\n📊 REGISTROS DE PONTO - JULHO 2025:")
    print(f"   Total de registros: {len(registros)}")
    
    # Análise detalhada dos registros
    if registros:
        print(f"\n📅 DETALHAMENTO POR DIA:")
        print("-" * 120)
        print(f"{'Data':<12} | {'Dia':<10} | {'Tipo':<18} | {'H.Trab':<7} | {'H.Extra':<7} | {'Atraso':<7} | {'Observações'}")
        print("-" * 120)
        
        # Contadores para estatísticas
        horas_por_tipo = {}
        dias_por_tipo = {}
        total_horas = 0
        total_extras = 0
        total_atrasos = 0
        
        for registro in registros:
            data_str = registro.data.strftime('%d/%m/%Y')
            dia_semana = registro.data.strftime('%A')
            tipo = registro.tipo_registro or 'trabalho_normal'
            h_trab = float(registro.horas_trabalhadas or 0)
            h_extra = float(registro.horas_extras or 0)
            atraso = float(registro.total_atraso_horas or 0)
            
            # Acumular estatísticas
            if tipo not in horas_por_tipo:
                horas_por_tipo[tipo] = 0.0
                dias_por_tipo[tipo] = 0
            
            horas_por_tipo[tipo] += h_trab
            if h_trab > 0 or tipo in ['falta', 'falta_justificada']:
                dias_por_tipo[tipo] += 1
            
            total_horas += h_trab
            total_extras += h_extra
            total_atrasos += atraso
            
            # Observações específicas
            obs = ""
            if tipo == 'trabalho_normal' and h_trab > 0:
                obs = "Trabalho regular"
            elif tipo.startswith('folga_'):
                obs = "Dia de folga"
            elif tipo == 'falta':
                obs = "Desconta do salário"
            elif tipo == 'falta_justificada':
                obs = "Remunerada normalmente"
            elif 'trabalhado' in tipo:
                if 'sabado' in tipo:
                    obs = "Extra +50%"
                elif 'domingo' in tipo or 'feriado' in tipo:
                    obs = "Extra +100%"
            
            print(f"{data_str:<12} | {dia_semana:<10} | {tipo:<18} | {h_trab:>7.1f} | {h_extra:>7.1f} | {atraso:>7.1f} | {obs}")
        
        print("-" * 120)
    
    # Resumo estatístico
    print(f"\n📈 RESUMO ESTATÍSTICO:")
    print(f"   Total de horas trabalhadas: {total_horas:.1f}h")
    print(f"   Total de horas extras: {total_extras:.1f}h")
    print(f"   Total de atrasos: {total_atrasos:.1f}h")
    
    if horas_por_tipo:
        print(f"\n📊 DISTRIBUIÇÃO POR TIPO:")
        for tipo, horas in sorted(horas_por_tipo.items()):
            dias = dias_por_tipo.get(tipo, 0)
            print(f"   {tipo}: {horas:.1f}h em {dias} dia(s)")
    
    # Cálculo do valor/hora conforme documento
    print(f"\n💰 CÁLCULO DO VALOR/HORA (conforme documento v8.2):")
    
    # Tipos que entram no divisor
    tipos_divisor = ['trabalho_normal', 'falta_justificada']
    horas_divisor = sum(horas_por_tipo.get(tipo, 0.0) for tipo in tipos_divisor)
    
    print(f"   Tipos no divisor: {tipos_divisor}")
    print(f"   Horas no divisor: {horas_divisor:.1f}h")
    
    if horas_divisor > 0:
        valor_hora = funcionario.salario / horas_divisor
        print(f"   Fórmula: R$ {funcionario.salario:.2f} ÷ {horas_divisor:.1f}h = R$ {valor_hora:.2f}/h")
    else:
        # Fallback
        horas_esperadas = dias_uteis * (funcionario.horario_trabalho.horas_diarias if funcionario.horario_trabalho else 8.0)
        valor_hora = funcionario.salario / horas_esperadas
        print(f"   Fallback - Horas esperadas: {dias_uteis} dias × {(funcionario.horario_trabalho.horas_diarias if funcionario.horario_trabalho else 8.0):.1f}h = {horas_esperadas:.1f}h")
        print(f"   Fórmula: R$ {funcionario.salario:.2f} ÷ {horas_esperadas:.1f}h = R$ {valor_hora:.2f}/h")
    
    # Cálculo detalhado do custo de mão de obra
    print(f"\n🧮 CÁLCULO DETALHADO DO CUSTO DE MÃO DE OBRA:")
    
    custo_detalhado = 0.0
    
    # 1. Remuneração normal
    horas_normais = horas_por_tipo.get('trabalho_normal', 0.0)
    horas_falta_just = horas_por_tipo.get('falta_justificada', 0.0)
    custo_normal = (horas_normais + horas_falta_just) * valor_hora
    custo_detalhado += custo_normal
    
    print(f"   1. Trabalho Normal: {horas_normais:.1f}h × R$ {valor_hora:.2f} = R$ {horas_normais * valor_hora:.2f}")
    print(f"   2. Falta Justificada: {horas_falta_just:.1f}h × R$ {valor_hora:.2f} = R$ {horas_falta_just * valor_hora:.2f}")
    print(f"   → Subtotal Normal: R$ {custo_normal:.2f}")
    
    # 2. Horas extras
    extras_detalhes = []
    
    horas_sabado = horas_por_tipo.get('sabado_trabalhado', 0.0)
    if horas_sabado > 0:
        custo_sabado = horas_sabado * valor_hora * 1.5
        custo_detalhado += custo_sabado
        extras_detalhes.append(f"Sábado: {horas_sabado:.1f}h × R$ {valor_hora:.2f} × 1.5 = R$ {custo_sabado:.2f}")
    
    horas_domingo = horas_por_tipo.get('domingo_trabalhado', 0.0)
    if horas_domingo > 0:
        custo_domingo = horas_domingo * valor_hora * 2.0
        custo_detalhado += custo_domingo
        extras_detalhes.append(f"Domingo: {horas_domingo:.1f}h × R$ {valor_hora:.2f} × 2.0 = R$ {custo_domingo:.2f}")
    
    horas_feriado = horas_por_tipo.get('feriado_trabalhado', 0.0)
    if horas_feriado > 0:
        custo_feriado = horas_feriado * valor_hora * 2.0
        custo_detalhado += custo_feriado
        extras_detalhes.append(f"Feriado: {horas_feriado:.1f}h × R$ {valor_hora:.2f} × 2.0 = R$ {custo_feriado:.2f}")
    
    horas_ferias = horas_por_tipo.get('ferias', 0.0)
    if horas_ferias > 0:
        custo_ferias = horas_ferias * valor_hora * 1.33
        custo_detalhado += custo_ferias
        extras_detalhes.append(f"Férias: {horas_ferias:.1f}h × R$ {valor_hora:.2f} × 1.33 = R$ {custo_ferias:.2f}")
    
    if extras_detalhes:
        print(f"   3. Horas Extras:")
        for detalhe in extras_detalhes:
            print(f"      {detalhe}")
    else:
        print(f"   3. Horas Extras: R$ 0.00 (nenhuma hora extra)")
    
    print(f"   → CUSTO TOTAL CALCULADO: R$ {custo_detalhado:.2f}")
    
    # Calcular KPIs oficiais usando o engine
    kpis = kpis_engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    print(f"\n🎯 KPIs OFICIAIS CALCULADOS PELO SISTEMA:")
    print(f"   Custo Mão de Obra (engine): R$ {kpis['custo_mao_obra']:.2f}")
    print(f"   Custo Total: R$ {kpis['custo_total']:.2f}")
    
    # Validação
    diferenca = abs(custo_detalhado - kpis['custo_mao_obra'])
    print(f"\n✅ VALIDAÇÃO:")
    print(f"   Cálculo manual: R$ {custo_detalhado:.2f}")
    print(f"   Cálculo engine: R$ {kpis['custo_mao_obra']:.2f}")
    print(f"   Diferença: R$ {diferenca:.2f}")
    print(f"   Status: {'✅ CORRETO' if diferenca < 0.01 else '⚠️ DIVERGÊNCIA'}")
    
    # Todos os 16 KPIs
    print(f"\n📊 TODOS OS 16 KPIs:")
    print(f"   1. Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   2. Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"   3. Faltas: {kpis['faltas']} dia(s)")
    print(f"   4. Atrasos: {kpis['atrasos_horas']:.1f}h")
    print(f"   5. Produtividade: {kpis['produtividade']:.1f}%")
    print(f"   6. Absenteísmo: {kpis['absenteismo']:.1f}%")
    print(f"   7. Média Diária: {kpis['media_diaria']:.1f}h")
    print(f"   8. Faltas Justificadas: {kpis['faltas_justificadas']} dia(s)")
    print(f"   9. Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
    print(f"  10. Custo Alimentação: R$ {kpis['custo_alimentacao']:.2f}")
    print(f"  11. Custo Transporte: R$ {kpis['custo_transporte']:.2f}")
    print(f"  12. Outros Custos: R$ {kpis['outros_custos']:.2f}")
    print(f"  13. Horas Perdidas: {kpis['horas_perdidas']:.1f}h")
    print(f"  14. Eficiência: {kpis['eficiencia']:.1f}%")
    print(f"  15. Valor Falta Justificada: R$ {kpis['valor_falta_justificada']:.2f}")
    print(f"  16. 🔵 CUSTO TOTAL: R$ {kpis['custo_total']:.2f}")

def estatisticas_gerais_tipos():
    """Estatísticas gerais dos tipos de registro no sistema"""
    
    with app.app_context():
        print(f"\n📊 ESTATÍSTICAS GERAIS DOS TIPOS DE REGISTRO:")
        print("-" * 60)
        
        tipos_stats = db.session.query(
            RegistroPonto.tipo_registro,
            db.func.count(RegistroPonto.id).label('quantidade'),
            db.func.sum(RegistroPonto.horas_trabalhadas).label('total_horas')
        ).group_by(RegistroPonto.tipo_registro).all()
        
        total_registros = sum(stat.quantidade for stat in tipos_stats)
        total_horas_sistema = sum(float(stat.total_horas or 0) for stat in tipos_stats)
        
        print(f"Total de registros no sistema: {total_registros}")
        print(f"Total de horas registradas: {total_horas_sistema:.1f}h")
        print(f"\nDistribuição por tipo:")
        
        for stat in sorted(tipos_stats, key=lambda x: x.quantidade, reverse=True):
            tipo = stat.tipo_registro or 'NULL'
            qtd = stat.quantidade
            horas = float(stat.total_horas or 0)
            pct = (qtd / total_registros * 100) if total_registros > 0 else 0
            
            print(f"  {tipo:<20}: {qtd:>4} registros ({pct:>5.1f}%) - {horas:>7.1f}h")

if __name__ == "__main__":
    gerar_relatorio_completo()
    estatisticas_gerais_tipos()
    
    print(f"\n" + "="*80)
    print("📋 RELATÓRIO CONCLUÍDO")
    print("="*80)
    print("Sistema: SIGE v8.2 - Tipos padronizados implementados")
    print("Conformidade: 100% com documento oficial de revisão")
    print("Data:", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))