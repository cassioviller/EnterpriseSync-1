#!/usr/bin/env python3
"""
Análise específica das horas extras do Carlos Alberto
"""

from app import app, db
from models import *
from datetime import datetime, date
import calendar

def buscar_carlos_alberto():
    """Buscar dados do funcionário Carlos Alberto"""
    
    with app.app_context():
        print("🔍 ANÁLISE HORAS EXTRAS - CARLOS ALBERTO")
        print("=" * 60)
        
        # Buscar Carlos Alberto (pode ser Carlos Pereira Lima baseado na imagem)
        carlos_list = Funcionario.query.filter(
            Funcionario.nome.ilike('%carlos%')
        ).all()
        
        print(f"📋 Funcionários Carlos encontrados: {len(carlos_list)}")
        for c in carlos_list:
            print(f"   ID {c.id}: {c.nome} - Salário: R$ {c.salario}")
        
        # Buscar por salário R$ 2.106,00 (da imagem)
        carlos = None
        for c in carlos_list:
            if c.salario and abs(float(c.salario) - 2106.00) < 1.0:
                carlos = c
                print(f"✅ Encontrado por salário: {c.nome}")
                break
        
        if not carlos:
            # Usar o primeiro Carlos com dados
            carlos = next((c for c in carlos_list if c.salario), None)
            if carlos:
                print(f"🔍 Usando para análise: {carlos.nome}")
            else:
                print(f"❌ Nenhum Carlos com salário encontrado")
                return None
        
        print(f"👤 FUNCIONÁRIO ENCONTRADO:")
        print(f"   ID: {carlos.id}")
        print(f"   Nome: {carlos.nome}")
        print(f"   Código: {carlos.codigo}")
        print(f"   Salário: R$ {carlos.salario}")
        # Buscar departamento se existir
        departamento = None
        if carlos.departamento_id:
            departamento = Departamento.query.get(carlos.departamento_id)
        print(f"   Departamento: {departamento.nome if departamento else 'N/A'}")
        print(f"   Função: {carlos.funcao}")
        
        # Buscar horário de trabalho
        if carlos.horario_trabalho_id:
            horario = HorarioTrabalho.query.get(carlos.horario_trabalho_id)
            print(f"\n⏰ HORÁRIO DE TRABALHO:")
            print(f"   Nome: {horario.nome}")
            print(f"   Entrada: {horario.entrada}")
            print(f"   Saída: {horario.saida}")
            print(f"   Horas diárias: {horario.horas_diarias}")
            print(f"   Dias da semana: {horario.dias_semana}")
        else:
            print(f"\n⚠️ Sem horário de trabalho configurado")
            horario = None
        
        return carlos, horario

def analisar_registros_julho_2025(carlos, horario):
    """Analisar registros de ponto de julho/2025"""
    
    with app.app_context():
        print(f"\n📅 REGISTROS JULHO/2025")
        print("=" * 60)
        
        # Buscar registros de julho/2025
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == carlos.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data).all()
        
        print(f"📊 Total de registros: {len(registros)}")
        
        total_horas_trabalhadas = 0
        total_horas_extras = 0
        total_sabados = 0
        total_domingos = 0
        
        for reg in registros:
            print(f"\n📅 {reg.data.strftime('%d/%m/%Y')} ({reg.data.strftime('%A')})")
            print(f"   Tipo: {reg.tipo_registro}")
            print(f"   Entrada: {reg.hora_entrada}")
            print(f"   Saída: {reg.hora_saida}")
            print(f"   Almoço: {reg.hora_almoco_saida} - {reg.hora_almoco_retorno}")
            print(f"   Horas trabalhadas: {reg.horas_trabalhadas}")
            print(f"   Horas extras: {reg.horas_extras}")
            print(f"   Percentual extras: {reg.percentual_extras}%")
            
            if reg.horas_trabalhadas:
                total_horas_trabalhadas += reg.horas_trabalhadas
            if reg.horas_extras:
                total_horas_extras += reg.horas_extras
            
            if 'sabado' in reg.tipo_registro:
                total_sabados += 1
            if 'domingo' in reg.tipo_registro:
                total_domingos += 1
        
        print(f"\n📈 TOTAIS JULHO/2025:")
        print(f"   Horas trabalhadas: {total_horas_trabalhadas:.1f}h")
        print(f"   Horas extras: {total_horas_extras:.1f}h")
        print(f"   Sábados: {total_sabados}")
        print(f"   Domingos: {total_domingos}")
        
        return {
            'total_horas_trabalhadas': total_horas_trabalhadas,
            'total_horas_extras': total_horas_extras,
            'total_sabados': total_sabados,
            'total_domingos': total_domingos,
            'registros': registros
        }

def calcular_valor_hora(carlos, horario):
    """Calcular valor hora do funcionário"""
    
    print(f"\n💰 CÁLCULO VALOR HORA")
    print("=" * 60)
    
    salario_mensal = float(carlos.salario)
    print(f"💵 Salário mensal: R$ {salario_mensal:,.2f}")
    
    # Método 1: Por horas contratuais mensais
    if horario and horario.horas_diarias:
        # Assumir 22 dias úteis por mês (padrão)
        dias_trabalho_mes = 22
        horas_contratuais_mes = horario.horas_diarias * dias_trabalho_mes
        valor_hora_contratual = salario_mensal / horas_contratuais_mes
        
        print(f"📊 Método Contratual:")
        print(f"   Horas diárias: {horario.horas_diarias}")
        print(f"   Dias trabalho/mês: {dias_trabalho_mes}")
        print(f"   Horas contratuais/mês: {horas_contratuais_mes}")
        print(f"   Valor/hora: R$ {valor_hora_contratual:.2f}")
    else:
        valor_hora_contratual = None
        print(f"⚠️ Sem horário configurado para cálculo contratual")
    
    # Método 2: CLT padrão (220h/mês)
    horas_clt_mes = 220
    valor_hora_clt = salario_mensal / horas_clt_mes
    print(f"📊 Método CLT (220h/mês):")
    print(f"   Valor/hora: R$ {valor_hora_clt:.2f}")
    
    # Método 3: Por dias úteis julho/2025
    # Julho 2025 tem 23 dias úteis (segunda a sexta)
    dias_uteis_julho = 23
    if horario and horario.horas_diarias:
        horas_uteis_julho = dias_uteis_julho * horario.horas_diarias
        valor_hora_julho = salario_mensal / horas_uteis_julho
        print(f"📊 Método Julho/2025 ({dias_uteis_julho} dias úteis):")
        print(f"   Horas úteis julho: {horas_uteis_julho}")
        print(f"   Valor/hora: R$ {valor_hora_julho:.2f}")
    else:
        valor_hora_julho = None
    
    return {
        'valor_hora_contratual': valor_hora_contratual,
        'valor_hora_clt': valor_hora_clt,
        'valor_hora_julho': valor_hora_julho,
        'salario_mensal': salario_mensal
    }

def analisar_custo_mao_obra(carlos, dados_julho, valores_hora):
    """Analisar cálculo do custo de mão de obra"""
    
    print(f"\n🔧 ANÁLISE CUSTO MÃO DE OBRA")
    print("=" * 60)
    
    print(f"📋 DADOS DA IMAGEM:")
    print(f"   Salário: R$ 2.106,00")
    print(f"   Horas Extras: 7.8h")
    print(f"   Custo Total: R$ 2.125,38")
    print(f"   Custo Adicional: R$ {2125.38 - 2106.00:.2f}")
    
    print(f"\n📊 DADOS CALCULADOS:")
    print(f"   Horas extras sistema: {dados_julho['total_horas_extras']:.1f}h")
    
    # Testar diferentes cenários de cálculo
    print(f"\n🧮 CENÁRIOS DE CÁLCULO:")
    
    if valores_hora['valor_hora_clt']:
        custo_extras_clt = dados_julho['total_horas_extras'] * valores_hora['valor_hora_clt'] * 1.5
        custo_total_clt = valores_hora['salario_mensal'] + custo_extras_clt
        print(f"   Cenário CLT (220h/mês + 50% extras):")
        print(f"     Valor/hora: R$ {valores_hora['valor_hora_clt']:.2f}")
        print(f"     Custo extras: R$ {custo_extras_clt:.2f}")
        print(f"     Custo total: R$ {custo_total_clt:.2f}")
    
    if valores_hora['valor_hora_contratual']:
        custo_extras_contratual = dados_julho['total_horas_extras'] * valores_hora['valor_hora_contratual'] * 1.5
        custo_total_contratual = valores_hora['salario_mensal'] + custo_extras_contratual
        print(f"   Cenário Contratual + 50% extras:")
        print(f"     Valor/hora: R$ {valores_hora['valor_hora_contratual']:.2f}")
        print(f"     Custo extras: R$ {custo_extras_contratual:.2f}")
        print(f"     Custo total: R$ {custo_total_contratual:.2f}")
    
    # Calcular valor/hora reverso baseado na diferença
    diferenca_custo = 2125.38 - 2106.00
    if dados_julho['total_horas_extras'] > 0:
        valor_hora_reverso = diferenca_custo / dados_julho['total_horas_extras']
        print(f"   Cenário Reverso (baseado na diferença):")
        print(f"     Diferença: R$ {diferenca_custo:.2f}")
        print(f"     Horas extras: {dados_julho['total_horas_extras']:.1f}h")
        print(f"     Valor/hora extras: R$ {valor_hora_reverso:.2f}")
        print(f"     Valor/hora base: R$ {valor_hora_reverso / 1.5:.2f}")

def verificar_kpis_sistema(carlos):
    """Verificar como o sistema calcula KPIs"""
    
    print(f"\n🎯 VERIFICAÇÃO KPIs SISTEMA")
    print("=" * 60)
    
    with app.app_context():
        # Importar função de KPIs
        try:
            from calculadora_obra import CalculadoraObra
            
            # Calcular KPIs de julho/2025
            calc = CalculadoraObra()
            kpis = calc.calcular_kpis_funcionario(
                funcionario_id=carlos.id,
                data_inicio=date(2025, 7, 1),
                data_fim=date(2025, 7, 31)
            )
            
            print(f"📊 KPIs do sistema:")
            print(f"   Horas trabalhadas: {kpis.get('horas_trabalhadas', 'N/A')}")
            print(f"   Horas extras: {kpis.get('horas_extras', 'N/A')}")
            print(f"   Custo mão de obra: R$ {kpis.get('custo_mao_obra', 'N/A')}")
            print(f"   Produtividade: {kpis.get('produtividade', 'N/A')}%")
            
            return kpis
            
        except Exception as e:
            print(f"❌ Erro ao calcular KPIs: {e}")
            return None

if __name__ == "__main__":
    print("🔍 ANÁLISE COMPLETA HORAS EXTRAS - CARLOS ALBERTO")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # 1. Buscar funcionário
    resultado = buscar_carlos_alberto()
    if not resultado:
        exit(1)
    
    carlos, horario = resultado
    
    # 2. Analisar registros de julho
    dados_julho = analisar_registros_julho_2025(carlos, horario)
    
    # 3. Calcular valor hora
    valores_hora = calcular_valor_hora(carlos, horario)
    
    # 4. Analisar custo mão de obra
    analisar_custo_mao_obra(carlos, dados_julho, valores_hora)
    
    # 5. Verificar KPIs do sistema
    kpis_sistema = verificar_kpis_sistema(carlos)
    
    print(f"\n" + "=" * 60)
    print("🎯 CONCLUSÃO DA ANÁLISE")
    print(f"   Discrepância encontrada entre 7.8h (imagem) e {dados_julho['total_horas_extras']:.1f}h (sistema)")
    print(f"   Necessário investigar lógica de cálculo de horas extras")
    print(f"   Verificar se percentuais de sábado/domingo estão sendo aplicados corretamente")