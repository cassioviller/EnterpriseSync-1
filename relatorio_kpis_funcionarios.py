cular_entrada_media(funcionario_id, data_inicio, data_fim):
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