#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RELATÓRIO COMPLETO DE KPIs DE FUNCIONÁRIOS - SIGE
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Este arquivo documenta todos os KPIs (Key Performance Indicators) implementados 
para o sistema de gestão de funcionários, incluindo fórmulas de cálculo, 
lógica de implementação e estado atual.

Data: 04 de Julho de 2025
Autor: Sistema SIGE
"""

from datetime import date, datetime, timedelta
from app import db
from models import Funcionario, RegistroPonto, RegistroAlimentacao
from sqlalchemy import func, extract


class RelatorioKPIsFuncionarios:
    """
    Classe responsável por documentar e calcular todos os KPIs de funcionários
    """
    
    def __init__(self):
        self.relatorio_data = date.today()
        
    def gerar_relatorio_completo(self):
        """
        Gera um relatório completo de todos os KPIs implementados
        """
        return {
            'cabecalho': self._gerar_cabecalho(),
            'kpis_principais': self._documentar_kpis_principais(),
            'kpis_secundarios': self._documentar_kpis_secundarios(),
            'metricas_financeiras': self._documentar_metricas_financeiras(),
            'metricas_tempo': self._documentar_metricas_tempo(),
            'metricas_presenca': self._documentar_metricas_presenca(),
            'implementacao_atual': self._status_implementacao(),
            'recomendacoes': self._recomendacoes_melhorias()
        }
    
    def _gerar_cabecalho(self):
        return {
            'titulo': 'RELATÓRIO DE KPIs DE FUNCIONÁRIOS - SIGE',
            'empresa': 'Estruturas do Vale',
            'data_geracao': self.relatorio_data.strftime('%d/%m/%Y'),
            'versao_sistema': '1.0',
            'responsavel': 'Sistema Integrado de Gestão Empresarial'
        }
    
    def _documentar_kpis_principais(self):
        """
        KPIs principais que são exibidos nos dashboards
        """
        return {
            'horas_trabalhadas': {
                'nome': 'Horas Trabalhadas',
                'descricao': 'Total de horas efetivamente trabalhadas pelo funcionário no período',
                'formula': 'Σ(hora_saida - hora_entrada - tempo_almoco) para todos os dias do período',
                'implementacao': '''
                def calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim):
                    registros = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        RegistroPonto.hora_entrada.isnot(None),
                        RegistroPonto.hora_saida.isnot(None)
                    ).all()
                    
                    total_horas = 0
                    for registro in registros:
                        if registro.horas_trabalhadas:
                            total_horas += registro.horas_trabalhadas
                    
                    return total_horas
                ''',
                'periodicidade': 'Diária, Mensal, Anual',
                'unidade': 'Horas',
                'status': 'IMPLEMENTADO',
                'localizacao_codigo': 'views.py - linha 227, utils.py - função calcular_horas_trabalhadas'
            },
            
            'horas_extras': {
                'nome': 'Horas Extras',
                'descricao': 'Horas trabalhadas além da jornada normal de trabalho',
                'formula': 'MAX(0, horas_trabalhadas_dia - jornada_normal)',
                'implementacao': '''
                def calcular_horas_extras(registro_ponto):
                    if not registro_ponto.horas_trabalhadas:
                        return 0
                    
                    jornada_normal = 8.0  # 8 horas padrão
                    if registro_ponto.funcionario.horario_trabalho:
                        jornada_normal = registro_ponto.funcionario.horario_trabalho.horas_diarias
                    
                    return max(0, registro_ponto.horas_trabalhadas - jornada_normal)
                ''',
                'periodicidade': 'Diária, Mensal',
                'unidade': 'Horas',
                'status': 'IMPLEMENTADO',
                'localizacao_codigo': 'utils.py - função calcular_horas_extras'
            },
            
            'faltas': {
                'nome': 'Faltas',
                'descricao': 'Número de dias úteis em que o funcionário não compareceu ao trabalho',
                'formula': 'dias_uteis_periodo - dias_com_presenca',
                'implementacao': '''
                def calcular_faltas(funcionario_id, data_inicio, data_fim):
                    # Calcular dias úteis no período (segunda a sexta)
                    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
                    
                    # Contar dias com presença
                    dias_presenca = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        RegistroPonto.hora_entrada.isnot(None)
                    ).count()
                    
                    return max(0, dias_uteis - dias_presenca)
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Dias',
                'status': 'IMPLEMENTADO',
                'localizacao_codigo': 'views.py - linha 235'
            },
            
            'atrasos': {
                'nome': 'Atrasos',
                'descricao': 'Número de vezes que o funcionário chegou após o horário previsto',
                'formula': 'COUNT(dias onde hora_entrada > horario_entrada_previsto)',
                'implementacao': '''
                def calcular_atrasos(funcionario_id, data_inicio, data_fim):
                    funcionario = Funcionario.query.get(funcionario_id)
                    if not funcionario.horario_trabalho:
                        return 0
                    
                    horario_entrada = funcionario.horario_trabalho.entrada
                    
                    registros_atraso = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        RegistroPonto.hora_entrada > horario_entrada
                    ).count()
                    
                    return registros_atraso
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Ocorrências',
                'status': 'IMPLEMENTADO PARCIAL',
                'observacoes': 'Lógica simplificada - necessário considerar tolerância de atraso',
                'localizacao_codigo': 'views.py - linha 236'
            }
        }
    
    def _documentar_kpis_secundarios(self):
        """
        KPIs secundários para análises mais detalhadas
        """
        return {
            'absenteismo': {
                'nome': 'Taxa de Absenteísmo',
                'descricao': 'Percentual de ausências em relação aos dias úteis',
                'formula': '(faltas / dias_uteis_periodo) * 100',
                'implementacao': '''
                def calcular_absenteismo(funcionario_id, data_inicio, data_fim):
                    faltas = calcular_faltas(funcionario_id, data_inicio, data_fim)
                    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
                    
                    return (faltas / dias_uteis) * 100 if dias_uteis > 0 else 0
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Percentual (%)',
                'status': 'IMPLEMENTADO',
                'meta_empresa': '< 5%',
                'localizacao_codigo': 'views.py - linha 239'
            },
            
            'pontualidade': {
                'nome': 'Taxa de Pontualidade',
                'descricao': 'Percentual de dias em que o funcionário chegou no horário',
                'formula': '((dias_presenca - atrasos) / dias_presenca) * 100',
                'implementacao': '''
                def calcular_pontualidade(funcionario_id, data_inicio, data_fim):
                    dias_presenca = contar_dias_presenca(funcionario_id, data_inicio, data_fim)
                    atrasos = calcular_atrasos(funcionario_id, data_inicio, data_fim)
                    
                    if dias_presenca == 0:
                        return 0
                    
                    return ((dias_presenca - atrasos) / dias_presenca) * 100
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Percentual (%)',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'ALTA'
            },
            
            'media_horas_diarias': {
                'nome': 'Média de Horas Diárias',
                'descricao': 'Média de horas trabalhadas por dia no período',
                'formula': 'total_horas_trabalhadas / dias_com_presenca',
                'implementacao': '''
                def calcular_media_horas_diarias(funcionario_id, data_inicio, data_fim):
                    total_horas = calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
                    dias_presenca = contar_dias_presenca(funcionario_id, data_inicio, data_fim)
                    
                    return total_horas / dias_presenca if dias_presenca > 0 else 0
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Horas',
                'status': 'IMPLEMENTADO',
                'localizacao_codigo': 'views.py - linha 242'
            },
            
            'assiduidade': {
                'nome': 'Taxa de Assiduidade',
                'descricao': 'Percentual de presença em relação aos dias úteis',
                'formula': '(dias_presenca / dias_uteis_periodo) * 100',
                'implementacao': '''
                def calcular_assiduidade(funcionario_id, data_inicio, data_fim):
                    dias_presenca = contar_dias_presenca(funcionario_id, data_inicio, data_fim)
                    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
                    
                    return (dias_presenca / dias_uteis) * 100 if dias_uteis > 0 else 0
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Percentual (%)',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'MÉDIA'
            }
        }
    
    def _documentar_metricas_financeiras(self):
        """
        Métricas relacionadas aos custos e despesas com funcionários
        """
        return {
            'custo_total_funcionario': {
                'nome': 'Custo Total do Funcionário',
                'descricao': 'Custo total incluindo salário, benefícios e despesas',
                'formula': 'salario_base + custo_horas_extras + custo_alimentacao + outros_beneficios',
                'implementacao': '''
                def calcular_custo_total(funcionario_id, data_inicio, data_fim):
                    funcionario = Funcionario.query.get(funcionario_id)
                    
                    # Salário proporcional
                    dias_periodo = (data_fim - data_inicio).days + 1
                    salario_proporcional = (funcionario.salario / 30) * dias_periodo
                    
                    # Custo de horas extras
                    horas_extras = calcular_horas_extras(funcionario_id, data_inicio, data_fim)
                    valor_hora = funcionario.salario / 220  # 220 horas/mês
                    custo_extras = horas_extras * valor_hora * 1.5  # 50% adicional
                    
                    # Custo de alimentação
                    custo_alimentacao = RegistroAlimentacao.query.filter(
                        RegistroAlimentacao.funcionario_id == funcionario_id,
                        RegistroAlimentacao.data >= data_inicio,
                        RegistroAlimentacao.data <= data_fim
                    ).with_entities(func.sum(RegistroAlimentacao.valor)).scalar() or 0
                    
                    return salario_proporcional + custo_extras + custo_alimentacao
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Reais (R$)',
                'status': 'IMPLEMENTADO PARCIAL',
                'observacoes': 'Falta incluir outros benefícios (plano de saúde, transporte)',
                'localizacao_codigo': 'utils.py - função calcular_custo_funcionario'
            },
            
            'custo_por_hora': {
                'nome': 'Custo por Hora Trabalhada',
                'descricao': 'Custo total dividido pelas horas efetivamente trabalhadas',
                'formula': 'custo_total_periodo / horas_trabalhadas_periodo',
                'implementacao': '''
                def calcular_custo_por_hora(funcionario_id, data_inicio, data_fim):
                    custo_total = calcular_custo_total(funcionario_id, data_inicio, data_fim)
                    horas_trabalhadas = calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
                    
                    return custo_total / horas_trabalhadas if horas_trabalhadas > 0 else 0
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Reais por Hora (R$/h)',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'ALTA'
            },
            
            'custo_alimentacao_medio': {
                'nome': 'Custo Médio de Alimentação',
                'descricao': 'Valor médio gasto com alimentação por dia trabalhado',
                'formula': 'total_gastos_alimentacao / dias_com_alimentacao',
                'implementacao': '''
                def calcular_custo_alimentacao_medio(funcionario_id, data_inicio, data_fim):
                    registros = RegistroAlimentacao.query.filter(
                        RegistroAlimentacao.funcionario_id == funcionario_id,
                        RegistroAlimentacao.data >= data_inicio,
                        RegistroAlimentacao.data <= data_fim
                    ).all()
                    
                    if not registros:
                        return 0
                    
                    total_gasto = sum(r.valor for r in registros)
                    dias_diferentes = len(set(r.data for r in registros))
                    
                    return total_gasto / dias_diferentes if dias_diferentes > 0 else 0
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Reais por Dia (R$/dia)',
                'status': 'IMPLEMENTADO PARCIAL',
                'localizacao_codigo': 'Disponível através de queries nos templates'
            }
        }
    
    def _documentar_metricas_tempo(self):
        """
        Métricas relacionadas ao tempo e jornada de trabalho
        """
        return {
            'tempo_medio_almoco': {
                'nome': 'Tempo Médio de Almoço',
                'descricao': 'Tempo médio gasto no intervalo de almoço',
                'formula': 'MEDIA(hora_almoco_retorno - hora_almoco_saida)',
                'implementacao': '''
                def calcular_tempo_medio_almoco(funcionario_id, data_inicio, data_fim):
                    registros = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        RegistroPonto.hora_almoco_saida.isnot(None),
                        RegistroPonto.hora_almoco_retorno.isnot(None)
                    ).all()
                    
                    if not registros:
                        return 0
                    
                    tempos_almoco = []
                    for registro in registros:
                        tempo_almoco = calcular_diferenca_horas(
                            registro.hora_almoco_saida, 
                            registro.hora_almoco_retorno
                        )
                        tempos_almoco.append(tempo_almoco)
                    
                    return sum(tempos_almoco) / len(tempos_almoco)
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Horas',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'BAIXA'
            },
            
            'entrada_media': {
                'nome': 'Horário Médio de Entrada',
                'descricao': 'Horário médio de chegada ao trabalho',
                'formula': 'MEDIA(hora_entrada) para todos os dias do período',
                'implementacao': '''
                def calcular_entrada_media(funcionario_id, data_inicio, data_fim):
                    registros = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        RegistroPonto.hora_entrada.isnot(None)
                    ).all()
                    
                    if not registros:
                        return None
                    
                    total_minutos = 0
                    for registro in registros:
                        hora = registro.hora_entrada
                        minutos = hora.hour * 60 + hora.minute
                        total_minutos += minutos
                    
                    media_minutos = total_minutos / len(registros)
                    horas = int(media_minutos // 60)
                    minutos = int(media_minutos % 60)
                    
                    return time(horas, minutos)
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Horário (HH:MM)',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'BAIXA'
            },
            
            'variabilidade_horarios': {
                'nome': 'Variabilidade de Horários',
                'descricao': 'Desvio padrão dos horários de entrada e saída',
                'formula': 'DESVIO_PADRAO(hora_entrada) + DESVIO_PADRAO(hora_saida)',
                'implementacao': 'Função estatística para medir consistência de horários',
                'periodicidade': 'Mensal',
                'unidade': 'Minutos',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'BAIXA'
            }
        }
    
    def _documentar_metricas_presenca(self):
        """
        Métricas detalhadas sobre presença e ausências
        """
        return {
            'dias_meio_periodo': {
                'nome': 'Dias de Meio Período',
                'descricao': 'Número de dias trabalhados em meio período ou saída antecipada',
                'formula': 'COUNT(dias onde saida_antecipada = True OR meio_periodo = True)',
                'implementacao': '''
                def calcular_dias_meio_periodo(funcionario_id, data_inicio, data_fim):
                    registros = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        or_(
                            RegistroPonto.meio_periodo == True,
                            RegistroPonto.saida_antecipada == True
                        )
                    ).count()
                    
                    return registros
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Dias',
                'status': 'IMPLEMENTADO',
                'localizacao_codigo': 'models.py - campos meio_periodo e saida_antecipada'
            },
            
            'frequencia_semanal': {
                'nome': 'Frequência por Dia da Semana',
                'descricao': 'Análise de presença por dia da semana',
                'formula': 'Agrupamento por dia da semana com contagem de presenças',
                'implementacao': '''
                def calcular_frequencia_semanal(funcionario_id, data_inicio, data_fim):
                    registros = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == funcionario_id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim,
                        RegistroPonto.hora_entrada.isnot(None)
                    ).all()
                    
                    frequencia = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}  # Seg-Dom
                    
                    for registro in registros:
                        dia_semana = registro.data.isoweekday()
                        frequencia[dia_semana] += 1
                    
                    return frequencia
                ''',
                'periodicidade': 'Mensal',
                'unidade': 'Dias por semana',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'MÉDIA'
            },
            
            'sequencia_presenca': {
                'nome': 'Maior Sequência de Presença',
                'descricao': 'Maior número consecutivo de dias trabalhados',
                'formula': 'MAX(sequencia_consecutiva_de_presenças)',
                'implementacao': 'Algoritmo para detectar sequências consecutivas',
                'periodicidade': 'Mensal/Anual',
                'unidade': 'Dias consecutivos',
                'status': 'NÃO IMPLEMENTADO',
                'prioridade': 'BAIXA'
            }
        }
    
    def _status_implementacao(self):
        """
        Status atual da implementação dos KPIs
        """
        return {
            'resumo': {
                'total_kpis_documentados': 18,
                'implementados_completo': 6,
                'implementados_parcial': 3,
                'nao_implementados': 9,
                'percentual_implementacao': '33%'
            },
            
            'kpis_implementados': [
                'Horas Trabalhadas',
                'Horas Extras', 
                'Faltas',
                'Taxa de Absenteísmo',
                'Média de Horas Diárias',
                'Dias de Meio Período'
            ],
            
            'kpis_parciais': [
                'Atrasos (lógica simplificada)',
                'Custo Total do Funcionário (falta benefícios)',
                'Custo Médio de Alimentação (disponível via queries)'
            ],
            
            'kpis_pendentes_alta_prioridade': [
                'Taxa de Pontualidade',
                'Custo por Hora Trabalhada'
            ],
            
            'kpis_pendentes_media_prioridade': [
                'Taxa de Assiduidade',
                'Frequência por Dia da Semana'
            ],
            
            'kpis_pendentes_baixa_prioridade': [
                'Tempo Médio de Almoço',
                'Horário Médio de Entrada',
                'Variabilidade de Horários',
                'Maior Sequência de Presença'
            ]
        }
    
    def _recomendacoes_melhorias(self):
        """
        Recomendações para melhorar o sistema de KPIs
        """
        return {
            'prioritarias': [
                {
                    'item': 'Implementar cálculo preciso de atrasos',
                    'descricao': 'Considerar tolerância de atraso (ex: 10 minutos)',
                    'impacto': 'Alto - métrica fundamental para gestão'
                },
                {
                    'item': 'Adicionar Taxa de Pontualidade',
                    'descricao': 'KPI importante para avaliação de desempenho',
                    'impacto': 'Alto - complementa análise de atrasos'
                },
                {
                    'item': 'Calcular custo por hora trabalhada',
                    'descricao': 'Essencial para análise de produtividade',
                    'impacto': 'Alto - decisões financeiras'
                }
            ],
            
            'secundarias': [
                {
                    'item': 'Implementar análise semanal de frequência',
                    'descricao': 'Identificar padrões de ausência por dia da semana',
                    'impacto': 'Médio - planejamento de equipes'
                },
                {
                    'item': 'Adicionar métricas de benefícios',
                    'descricao': 'Incluir custos de plano de saúde, transporte, etc.',
                    'impacao': 'Médio - custo total real'
                }
            ],
            
            'futuras': [
                {
                    'item': 'Dashboard de tendências',
                    'descricao': 'Gráficos de evolução dos KPIs ao longo do tempo',
                    'impacto': 'Baixo - visualização melhorada'
                },
                {
                    'item': 'Alertas automáticos',
                    'descricao': 'Notificações quando KPIs excedem limites',
                    'impacto': 'Baixo - automação de processos'
                }
            ],
            
            'melhorias_tecnicas': [
                'Otimizar queries para cálculos em lote',
                'Implementar cache para KPIs calculados',
                'Adicionar testes unitários para funções de cálculo',
                'Documentar todas as fórmulas no código',
                'Criar validações de integridade dos dados'
            ]
        }


def main():
    """
    Função principal para gerar e exibir o relatório
    """
    relatorio = RelatorioKPIsFuncionarios()
    dados_completos = relatorio.gerar_relatorio_completo()
    
    print("=" * 80)
    print(dados_completos['cabecalho']['titulo'])
    print("=" * 80)
    print(f"Empresa: {dados_completos['cabecalho']['empresa']}")
    print(f"Data: {dados_completos['cabecalho']['data_geracao']}")
    print(f"Versão: {dados_completos['cabecalho']['versao_sistema']}")
    print("=" * 80)
    
    # Exibir resumo de implementação
    resumo = dados_completos['implementacao_atual']['resumo']
    print(f"\nSTATUS DE IMPLEMENTAÇÃO:")
    print(f"Total de KPIs documentados: {resumo['total_kpis_documentados']}")
    print(f"Implementados completos: {resumo['implementados_completo']}")
    print(f"Implementados parciais: {resumo['implementados_parcial']}")
    print(f"Não implementados: {resumo['nao_implementados']}")
    print(f"Percentual de implementação: {resumo['percentual_implementacao']}")
    
    print(f"\nRelatório detalhado disponível na variável 'dados_completos'")
    
    return dados_completos


if __name__ == '__main__':
    dados = main()