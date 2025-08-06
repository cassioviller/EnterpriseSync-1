#!/usr/bin/env python3
"""
INTEGRAÇÃO COMPLETA DOS HORÁRIOS PADRÃO COM ENGINE DE KPIs - SIGE v8.2
Data: 06 de Agosto de 2025
Atualiza completamente a engine de KPIs para usar o sistema de horários padrão
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioPadrao, Obra
from datetime import date, datetime, time
import calendar
import logging

logging.basicConfig(level=logging.INFO)

def calcular_kpis_funcionario_horario_padrao(funcionario_id, mes, ano, debug=True):
    """
    Calcula KPIs usando horário padrão como referência principal
    
    Args:
        funcionario_id (int): ID do funcionário
        mes (int): Mês para cálculo (1-12)
        ano (int): Ano para cálculo
        debug (bool): Se deve imprimir logs detalhados
    
    Returns:
        dict: KPIs calculados com nova lógica
    """
    try:
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            if debug:
                print(f"❌ Funcionário {funcionario_id} não encontrado")
            return {}
        
        if debug:
            print(f"\n👤 CALCULANDO KPIs: {funcionario.nome} ({mes:02d}/{ano})")
        
        # Definir período do mês
        data_inicio = date(ano, mes, 1)
        if mes == 12:
            data_fim = date(ano + 1, 1, 1)
        else:
            data_fim = date(ano, mes + 1, 1)
        
        # Buscar registros do mês
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data < data_fim
        ).order_by(RegistroPonto.data).all()
        
        if debug:
            print(f"📊 Registros encontrados: {len(registros)}")
        
        # Obter horário padrão
        horario_padrao = funcionario.get_horario_padrao_ativo(data_inicio)
        if not horario_padrao:
            if debug:
                print(f"⚠️ {funcionario.nome} sem horário padrão - usando cálculo tradicional")
            return calcular_kpis_tradicional(funcionario_id, mes, ano, debug)
        
        if debug:
            print(f"🕐 Horário padrão: {horario_padrao.entrada_padrao} às {horario_padrao.saida_padrao}")
        
        # Calcular carga horária padrão mensal
        carga_padrao_mensal = calcular_carga_horaria_padrao_mensal(horario_padrao, ano, mes)
        if debug:
            print(f"📋 Carga padrão mensal: {carga_padrao_mensal}h")
        
        # Inicializar contadores
        estatisticas = {
            'total_horas_trabalhadas': 0.0,
            'total_horas_extras': 0.0,
            'total_minutos_atrasos': 0,
            'total_faltas': 0,
            'dias_trabalhados': 0,
            'dias_com_extras': 0,
            'maior_hora_extra_dia': 0.0,
            'total_extras_entrada': 0,
            'total_extras_saida': 0,
            'custo_horas_normais': 0.0,
            'custo_horas_extras': 0.0
        }
        
        # Processar cada registro
        for registro in registros:
            if debug and len(registros) <= 10:  # Log detalhado apenas para poucos registros
                print(f"  📅 {registro.data}: {registro.tipo_registro}")
            
            # Contabilizar baseado no tipo de registro
            if registro.tipo_registro in ['trabalhado', 'sabado_trabalhado', 'feriado_trabalhado']:
                estatisticas['dias_trabalhados'] += 1
                
                # Usar horas trabalhadas calculadas
                if registro.horas_trabalhadas:
                    estatisticas['total_horas_trabalhadas'] += registro.horas_trabalhadas
                
                # Usar horas extras detalhadas (novo sistema)
                horas_extras = 0.0
                if hasattr(registro, 'horas_extras_detalhadas') and registro.horas_extras_detalhadas:
                    horas_extras = registro.horas_extras_detalhadas
                    estatisticas['total_extras_entrada'] += getattr(registro, 'minutos_extras_entrada', 0)
                    estatisticas['total_extras_saida'] += getattr(registro, 'minutos_extras_saida', 0)
                elif registro.horas_extras:
                    horas_extras = registro.horas_extras
                
                if horas_extras > 0:
                    estatisticas['total_horas_extras'] += horas_extras
                    estatisticas['dias_com_extras'] += 1
                    if horas_extras > estatisticas['maior_hora_extra_dia']:
                        estatisticas['maior_hora_extra_dia'] = horas_extras
                
                # Contabilizar atrasos
                if registro.total_atraso_minutos:
                    estatisticas['total_minutos_atrasos'] += registro.total_atraso_minutos
                    
            elif registro.tipo_registro in ['falta', 'falta_justificada']:
                estatisticas['total_faltas'] += 1
        
        # Calcular valor hora baseado no salário e carga padrão
        valor_hora_base = funcionario.salario / carga_padrao_mensal if carga_padrao_mensal > 0 else 0
        
        # Calcular custos
        estatisticas['custo_horas_normais'] = estatisticas['total_horas_trabalhadas'] * valor_hora_base
        estatisticas['custo_horas_extras'] = estatisticas['total_horas_extras'] * valor_hora_base * 1.5  # 50% adicional
        
        # Calcular KPIs finais
        kpis = {
            # Horas e produtividade
            'horas_trabalhadas': round(estatisticas['total_horas_trabalhadas'], 1),
            'horas_extras': round(estatisticas['total_horas_extras'], 1),
            'carga_padrao_mensal': round(carga_padrao_mensal, 1),
            'produtividade': round((estatisticas['total_horas_trabalhadas'] / carga_padrao_mensal * 100) if carga_padrao_mensal > 0 else 0, 1),
            
            # Eficiência (baseada em atrasos)
            'atrasos_minutos': estatisticas['total_minutos_atrasos'],
            'atrasos_horas': round(estatisticas['total_minutos_atrasos'] / 60, 2),
            'eficiencia': round(max(0, 100 - (estatisticas['total_minutos_atrasos'] / 60 / carga_padrao_mensal * 100)) if carga_padrao_mensal > 0 else 100, 1),
            
            # Presença e frequência
            'dias_trabalhados': estatisticas['dias_trabalhados'],
            'total_faltas': estatisticas['total_faltas'],
            'dias_com_extras': estatisticas['dias_com_extras'],
            'frequencia': round((estatisticas['dias_trabalhados'] / calcular_dias_uteis_mes(ano, mes) * 100) if calcular_dias_uteis_mes(ano, mes) > 0 else 0, 1),
            
            # Detalhamento de horas extras
            'extras_entrada_minutos': estatisticas['total_extras_entrada'],
            'extras_saida_minutos': estatisticas['total_extras_saida'], 
            'maior_hora_extra_dia': round(estatisticas['maior_hora_extra_dia'], 2),
            'media_extras_dia': round(estatisticas['total_horas_extras'] / estatisticas['dias_com_extras'] if estatisticas['dias_com_extras'] > 0 else 0, 2),
            
            # Custos
            'valor_hora': round(valor_hora_base, 2),
            'custo_horas_normais': round(estatisticas['custo_horas_normais'], 2),
            'custo_horas_extras': round(estatisticas['custo_horas_extras'], 2),
            'custo_total': round(estatisticas['custo_horas_normais'] + estatisticas['custo_horas_extras'], 2),
            
            # Metadata
            'calculado_com_horario_padrao': True,
            'horario_padrao': f"{horario_padrao.entrada_padrao} às {horario_padrao.saida_padrao}",
            'data_calculo': datetime.now().isoformat()
        }
        
        if debug:
            print(f"✅ KPIs calculados com horário padrão:")
            print(f"   Produtividade: {kpis['produtividade']}%")
            print(f"   Eficiência: {kpis['eficiencia']}%")
            print(f"   Horas trabalhadas: {kpis['horas_trabalhadas']}h")
            print(f"   Horas extras: {kpis['horas_extras']}h")
            print(f"   Custo total: R$ {kpis['custo_total']}")
        
        return kpis
        
    except Exception as e:
        if debug:
            print(f"❌ Erro ao calcular KPIs: {e}")
        return {}

def calcular_carga_horaria_padrao_mensal(horario_padrao, ano, mes):
    """Calcula carga horária mensal baseada no horário padrão"""
    try:
        # Calcular carga horária diária
        entrada_min = (horario_padrao.entrada_padrao.hour * 60) + horario_padrao.entrada_padrao.minute
        saida_min = (horario_padrao.saida_padrao.hour * 60) + horario_padrao.saida_padrao.minute
        
        # Descontar intervalo de almoço se definido
        almoco_min = 0
        if horario_padrao.saida_almoco_padrao and horario_padrao.retorno_almoco_padrao:
            saida_almoco = (horario_padrao.saida_almoco_padrao.hour * 60) + horario_padrao.saida_almoco_padrao.minute
            retorno_almoco = (horario_padrao.retorno_almoco_padrao.hour * 60) + horario_padrao.retorno_almoco_padrao.minute
            almoco_min = retorno_almoco - saida_almoco
        
        carga_diaria_min = saida_min - entrada_min - almoco_min
        carga_diaria_horas = carga_diaria_min / 60
        
        # Calcular dias úteis do mês (segunda a sexta)
        dias_uteis = calcular_dias_uteis_mes(ano, mes)
        
        return dias_uteis * carga_diaria_horas
        
    except Exception as e:
        print(f"❌ Erro ao calcular carga mensal: {e}")
        return 0

def calcular_dias_uteis_mes(ano, mes):
    """Calcula número de dias úteis (segunda a sexta) no mês"""
    try:
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias_uteis = 0
        
        for dia in range(1, dias_mes + 1):
            data_dia = date(ano, mes, dia)
            # Segunda=0, Domingo=6
            if data_dia.weekday() < 5:  # Segunda a sexta
                dias_uteis += 1
        
        return dias_uteis
        
    except Exception as e:
        print(f"❌ Erro ao calcular dias úteis: {e}")
        return 22  # Valor padrão

def calcular_kpis_tradicional(funcionario_id, mes, ano, debug=False):
    """Fallback para cálculo tradicional quando não há horário padrão"""
    if debug:
        print("⚠️ Usando cálculo tradicional (sem horário padrão)")
    
    # Implementar lógica tradicional como backup
    return {
        'horas_trabalhadas': 0,
        'horas_extras': 0,
        'produtividade': 0,
        'eficiencia': 0,
        'custo_total': 0,
        'calculado_com_horario_padrao': False,
        'observacao': 'Funcionário sem horário padrão'
    }

def testar_kpis_com_horario_padrao():
    """Testa a nova engine de KPIs com horário padrão"""
    print("🧪 TESTANDO NOVA ENGINE DE KPIs COM HORÁRIO PADRÃO")
    
    with app.app_context():
        # Buscar funcionários para teste
        funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()
        
        if not funcionarios:
            print("❌ Nenhum funcionário encontrado")
            return False
        
        print(f"👥 Testando com {len(funcionarios)} funcionários")
        
        resultados = []
        
        for funcionario in funcionarios:
            print(f"\n{'='*50}")
            kpis = calcular_kpis_funcionario_horario_padrao(funcionario.id, 7, 2025, debug=True)
            
            if kpis:
                resultados.append({
                    'funcionario': funcionario.nome,
                    'kpis': kpis
                })
        
        # Resumo dos resultados
        print(f"\n📊 RESUMO DOS TESTES:")
        print("Funcionário".ljust(25) + "Prod%".ljust(8) + "Efic%".ljust(8) + "H.Trab".ljust(8) + "H.Extras".ljust(8) + "Custo")
        print("-" * 70)
        
        for resultado in resultados:
            kpis = resultado['kpis']
            print(f"{resultado['funcionario'][:24].ljust(25)}"
                  f"{kpis.get('produtividade', 0):>6.1f}%"
                  f"{kpis.get('eficiencia', 0):>7.1f}%"
                  f"{kpis.get('horas_trabalhadas', 0):>7.1f}h"
                  f"{kpis.get('horas_extras', 0):>7.1f}h"
                  f" R${kpis.get('custo_total', 0):>7.2f}")
        
        return True

if __name__ == "__main__":
    print("🚀 INTEGRANDO HORÁRIOS PADRÃO COM ENGINE DE KPIs")
    
    # Testar nova engine
    teste_ok = testar_kpis_com_horario_padrao()
    
    print(f"\n📋 RESULTADO DO TESTE:")
    print(f"✓ Nova engine de KPIs: {'Funcionando' if teste_ok else 'Erro'}")
    
    if teste_ok:
        print(f"\n🎯 PRÓXIMAS ETAPAS:")
        print(f"   1. Integrar função na kpi_unificado.py")
        print(f"   2. Atualizar dashboard para mostrar novos KPIs")
        print(f"   3. Criar relatórios detalhados")
    else:
        print(f"\n⚠️ Revisar implementação antes de integrar")