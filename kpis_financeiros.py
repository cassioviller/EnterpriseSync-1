# KPIs FINANCEIROS AVANÇADOS - SIGE v8.0
# Novos indicadores para gestão estratégica

from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import Obra, RegistroPonto, RDO, ServicoObra
from calculadora_obra import CalculadoraObra

class KPIsFinanceiros:
    """
    KPIs financeiros avançados para gestão estratégica de obras
    """
    
    @staticmethod
    def custo_por_m2(obra_id, data_inicio=None, data_fim=None):
        """
        KPI: Custo por metro quadrado construído
        Fundamental para benchmarking e controle de custos
        """
        calculadora = CalculadoraObra(obra_id, data_inicio, data_fim)
        custo_total = calculadora.calcular_custo_total()['total']
        
        obra = Obra.query.get(obra_id)
        area_m2 = obra.area_total_m2 if obra and obra.area_total_m2 else 1
        
        custo_por_m2 = custo_total / area_m2
        benchmark_mercado = 1200.00  # R$/m² - configurável por região
        
        return {
            'valor': custo_por_m2,
            'custo_total': custo_total,
            'area_m2': area_m2,
            'benchmark_mercado': benchmark_mercado,
            'percentual_benchmark': (custo_por_m2 / benchmark_mercado) * 100,
            'status': 'acima' if custo_por_m2 > benchmark_mercado else 'dentro',
            'diferenca_benchmark': custo_por_m2 - benchmark_mercado
        }
    
    @staticmethod
    def margem_lucro_realizada(obra_id, data_inicio=None, data_fim=None):
        """
        KPI: Margem de lucro realizada vs planejada
        Essencial para controle de rentabilidade
        """
        calculadora = CalculadoraObra(obra_id, data_inicio, data_fim)
        custo_real = calculadora.calcular_custo_total()['total']
        
        obra = Obra.query.get(obra_id)
        if not obra:
            return {'erro': 'Obra não encontrada'}
        
        valor_contrato = obra.valor_contrato or obra.orcamento_total or 0
        
        if valor_contrato <= 0:
            return {
                'erro': 'Valor do contrato não definido',
                'custo_real': custo_real
            }
        
        margem_absoluta = valor_contrato - custo_real
        margem_percentual = (margem_absoluta / valor_contrato) * 100
        
        # Classificação da margem
        if margem_percentual >= 20:
            classificacao = 'excelente'
        elif margem_percentual >= 15:
            classificacao = 'boa'
        elif margem_percentual >= 10:
            classificacao = 'regular'
        elif margem_percentual >= 0:
            classificacao = 'baixa'
        else:
            classificacao = 'prejuizo'
        
        return {
            'margem_absoluta': margem_absoluta,
            'margem_percentual': margem_percentual,
            'valor_contrato': valor_contrato,
            'custo_real': custo_real,
            'classificacao': classificacao,
            'status': 'positiva' if margem_percentual > 0 else 'negativa'
        }
    
    @staticmethod
    def desvio_orcamentario(obra_id, data_inicio=None, data_fim=None):
        """
        KPI: Desvio orçamentário com projeção de conclusão
        Alerta precoce para estouro de orçamento
        """
        calculadora = CalculadoraObra(obra_id, data_inicio, data_fim)
        custo_atual = calculadora.calcular_custo_total()['total']
        
        obra = Obra.query.get(obra_id)
        if not obra or not obra.orcamento_total:
            return {'erro': 'Orçamento não definido'}
        
        orcamento_total = obra.orcamento_total
        
        # Calcular progresso físico para projeção
        progresso_fisico = KPIsFinanceiros.calcular_progresso_fisico(obra_id)
        
        # Projetar custo final baseado no progresso
        if progresso_fisico > 0:
            custo_projetado = custo_atual / (progresso_fisico / 100)
        else:
            custo_projetado = custo_atual
        
        # Calcular desvios
        desvio_atual = ((custo_atual - (orcamento_total * progresso_fisico / 100)) / orcamento_total) * 100
        desvio_projetado = ((custo_projetado - orcamento_total) / orcamento_total) * 100
        
        # Classificar alerta
        if desvio_projetado > 25:
            alerta = 'critico'
        elif desvio_projetado > 15:
            alerta = 'alto'
        elif desvio_projetado > 5:
            alerta = 'medio'
        else:
            alerta = 'normal'
        
        return {
            'desvio_atual': desvio_atual,
            'desvio_projetado': desvio_projetado,
            'custo_atual': custo_atual,
            'custo_projetado': custo_projetado,
            'orcamento_total': orcamento_total,
            'progresso_fisico': progresso_fisico,
            'alerta': alerta,
            'excesso_projetado': max(0, custo_projetado - orcamento_total)
        }
    
    @staticmethod
    def roi_projetado(obra_id, data_inicio=None, data_fim=None):
        """
        KPI: ROI (Return on Investment) projetado
        Análise de retorno sobre investimento
        """
        margem = KPIsFinanceiros.margem_lucro_realizada(obra_id, data_inicio, data_fim)
        
        if 'erro' in margem:
            return margem
        
        obra = Obra.query.get(obra_id)
        
        # Estimar investimento inicial (30% do orçamento)
        orcamento_total = getattr(obra, 'orcamento_total', None) or getattr(obra, 'orcamento', 0)
        investimento_inicial = orcamento_total * 0.3
        
        if investimento_inicial <= 0:
            return {'erro': 'Investimento inicial não definido'}
        
        roi = (margem['margem_absoluta'] / investimento_inicial) * 100
        
        # Classificação do ROI
        if roi >= 50:
            classificacao = 'excelente'
        elif roi >= 30:
            classificacao = 'bom'
        elif roi >= 15:
            classificacao = 'regular'
        elif roi >= 0:
            classificacao = 'baixo'
        else:
            classificacao = 'ruim'
        
        tempo_retorno = 0
        if margem['margem_absoluta'] > 0:
            tempo_retorno = (investimento_inicial / margem['margem_absoluta']) * 12
        
        return {
            'roi_percentual': roi,
            'margem_absoluta': margem['margem_absoluta'],
            'investimento_inicial': investimento_inicial,
            'classificacao': classificacao,
            'tempo_retorno_meses': tempo_retorno
        }
    
    @staticmethod
    def velocidade_queima_orcamento(obra_id, data_inicio=None, data_fim=None):
        """
        KPI: Velocidade de queima do orçamento
        Indica se o ritmo de gastos está adequado ao cronograma
        """
        calculadora = CalculadoraObra(obra_id, data_inicio, data_fim)
        custo_atual = calculadora.calcular_custo_total()['total']
        
        obra = Obra.query.get(obra_id)
        if not obra or not obra.orcamento_total or not obra.data_inicio or not obra.data_fim_prevista:
            return {'erro': 'Dados da obra incompletos'}
        
        # Calcular tempo decorrido vs tempo total
        hoje = datetime.now().date()
        tempo_total = (obra.data_fim_prevista - obra.data_inicio).days
        tempo_decorrido = (hoje - obra.data_inicio).days
        
        if tempo_total <= 0:
            return {'erro': 'Datas da obra inválidas'}
        
        percentual_tempo = min(100, (tempo_decorrido / tempo_total) * 100)
        percentual_orcamento = (custo_atual / obra.orcamento_total) * 100
        
        # Calcular velocidade (razão entre % orçamento gasto e % tempo decorrido)
        if percentual_tempo > 0:
            velocidade = percentual_orcamento / percentual_tempo
        else:
            velocidade = 0
        
        # Classificar velocidade
        if velocidade > 1.2:
            status = 'muito_rapida'
            recomendacao = 'Reduzir ritmo de gastos'
        elif velocidade > 1.1:
            status = 'rapida'
            recomendacao = 'Monitorar gastos de perto'
        elif velocidade >= 0.9:
            status = 'adequada'
            recomendacao = 'Manter ritmo atual'
        else:
            status = 'lenta'
            recomendacao = 'Acelerar execução se necessário'
        
        return {
            'velocidade': velocidade,
            'percentual_tempo': percentual_tempo,
            'percentual_orcamento': percentual_orcamento,
            'custo_atual': custo_atual,
            'orcamento_total': obra.orcamento_total,
            'status': status,
            'recomendacao': recomendacao,
            'dias_restantes': max(0, (obra.data_fim_prevista - hoje).days)
        }
    
    @staticmethod
    def calcular_progresso_fisico(obra_id):
        """
        Calcula progresso físico baseado em RDOs e serviços
        """
        # Estimativa de progresso baseada em tempo decorrido (método simplificado)
        obra = Obra.query.get(obra_id)
        if not obra or not obra.data_inicio:
            return 0
        
        hoje = datetime.now().date()
        data_fim = getattr(obra, 'data_fim_prevista', None) or getattr(obra, 'data_previsao_fim', None)
        
        if not data_fim:
            # Se não há data fim, estimar baseado em 6 meses padrão
            tempo_decorrido = (hoje - obra.data_inicio).days
            return min(100, max(0, (tempo_decorrido / 180) * 100))
        
        tempo_total = (data_fim - obra.data_inicio).days
        tempo_decorrido = (hoje - obra.data_inicio).days
        
        return min(100, max(0, (tempo_decorrido / tempo_total) * 100)) if tempo_total > 0 else 0
        


class KPIsOperacionais:
    """
    KPIs operacionais complementares
    """
    
    @staticmethod
    def indice_produtividade_obra(obra_id, data_inicio=None, data_fim=None):
        """
        KPI: Índice de produtividade (físico vs cronológico)
        """
        progresso_fisico = KPIsFinanceiros.calcular_progresso_fisico(obra_id)
        
        obra = Obra.query.get(obra_id)
        if not obra or not obra.data_inicio or not obra.data_fim_prevista:
            return {'erro': 'Dados da obra incompletos'}
        
        # Calcular progresso cronológico
        hoje = datetime.now().date()
        total_dias = (obra.data_fim_prevista - obra.data_inicio).days
        dias_decorridos = (hoje - obra.data_inicio).days
        
        if total_dias <= 0:
            return {'erro': 'Datas da obra inválidas'}
        
        progresso_cronologico = min(100, max(0, (dias_decorridos / total_dias) * 100))
        
        # Calcular índice de produtividade
        if progresso_cronologico > 0:
            indice = progresso_fisico / progresso_cronologico
        else:
            indice = 0
        
        # Classificar status
        if indice > 1.15:
            status = 'muito_adiantada'
        elif indice > 1.05:
            status = 'adiantada'
        elif indice >= 0.95:
            status = 'no_prazo'
        elif indice >= 0.85:
            status = 'atrasada'
        else:
            status = 'muito_atrasada'
        
        return {
            'indice': indice,
            'progresso_fisico': progresso_fisico,
            'progresso_cronologico': progresso_cronologico,
            'status': status,
            'dias_diferenca': (progresso_fisico - progresso_cronologico) * total_dias / 100
        }