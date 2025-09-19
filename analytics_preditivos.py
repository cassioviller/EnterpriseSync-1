"""
SISTEMA DE ANÁLISES PREDITIVAS - SIGE v8.0
Análises avançadas com machine learning para otimização da frota

Funcionalidades:
- Previsão de manutenções baseada em padrões
- Identificação de veículos problemáticos
- Predição de custos futuros
- Análise de vida útil remanescente
- Otimização de alocação de frota
- Detecção de anomalias em tempo real
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_, text, extract, case
from sqlalchemy.orm import joinedload
import json
import logging
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.cluster import KMeans
import warnings
warnings.filterwarnings('ignore')

# Importar modelos
from models import (
    db, Veiculo, CustoVeiculo, UsoVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
analytics_bp = Blueprint('analytics_preditivos', __name__, url_prefix='/analytics/veiculos')

def get_admin_id():
    """Obtém admin_id do usuário atual"""
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario.value == 'admin':
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return current_user.id

class EngineAnalyticsPreditivo:
    """Engine principal de análises preditivas"""
    
    def __init__(self, admin_id):
        self.admin_id = admin_id
        self.modelos_treinados = {}
        self.scalers = {}
        
    def executar_analise_completa(self):
        """Executa análise preditiva completa"""
        try:
            resultados = {}
            
            # 1. Previsão de manutenções
            resultados['previsao_manutencoes'] = self.prever_manutencoes()
            
            # 2. Identificação de veículos problemáticos
            resultados['veiculos_problematicos'] = self.identificar_veiculos_problematicos()
            
            # 3. Predição de custos
            resultados['predicao_custos'] = self.prever_custos_futuros()
            
            # 4. Análise de vida útil
            resultados['vida_util'] = self.analisar_vida_util()
            
            # 5. Otimização de alocação
            resultados['otimizacao_alocacao'] = self.otimizar_alocacao_frota()
            
            # 6. Detecção de anomalias
            resultados['deteccao_anomalias'] = self.detectar_anomalias()
            
            # 7. Recomendações
            resultados['recomendacoes'] = self.gerar_recomendacoes(resultados)
            
            return resultados
            
        except Exception as e:
            logger.error(f"Erro na análise preditiva: {e}")
            return {}
    
    def prever_manutencoes(self):
        """Prevê próximas manutenções usando machine learning"""
        try:
            # Obter dados históricos de manutenção
            dados_historicos = self._obter_dados_manutencao_historicos()
            
            if len(dados_historicos) < 10:  # Mínimo de dados para ML
                return {'erro': 'Dados insuficientes para previsão de manutenções'}
            
            # Preparar features
            df = pd.DataFrame(dados_historicos)
            features = ['km_atual', 'dias_desde_ultima_manutencao', 'idade_veiculo', 
                       'custo_manutencao_media', 'uso_intensidade']
            
            X = df[features].fillna(0)
            y = df['dias_ate_proxima_manutencao'].fillna(0)
            
            # Treinar modelo
            if len(X) > 5:
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                
                modelo = RandomForestRegressor(n_estimators=100, random_state=42)
                modelo.fit(X_train, y_train)
                
                # Avaliação
                y_pred = modelo.predict(X_test)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                # Previsões para veículos atuais
                veiculos_atuais = self._obter_dados_veiculos_atuais()
                if veiculos_atuais:
                    df_atual = pd.DataFrame(veiculos_atuais)
                    X_atual = df_atual[features].fillna(0)
                    previsoes = modelo.predict(X_atual)
                    
                    # Combinar previsões com dados dos veículos
                    for i, veiculo in enumerate(veiculos_atuais):
                        veiculo['dias_previstos_manutencao'] = max(1, int(previsoes[i]))
                        veiculo['data_prevista_manutencao'] = (
                            date.today() + timedelta(days=int(previsoes[i]))
                        ).strftime('%d/%m/%Y')
                        
                        # Classificar urgência
                        if previsoes[i] <= 7:
                            veiculo['urgencia'] = 'Crítica'
                        elif previsoes[i] <= 30:
                            veiculo['urgencia'] = 'Alta'
                        elif previsoes[i] <= 60:
                            veiculo['urgencia'] = 'Média'
                        else:
                            veiculo['urgencia'] = 'Baixa'
                    
                    return {
                        'previsoes': veiculos_atuais,
                        'performance_modelo': {
                            'mae': round(mae, 2),
                            'r2_score': round(r2, 3),
                            'total_veiculos': len(veiculos_atuais)
                        }
                    }
            
            return {'erro': 'Dados insuficientes para treinar modelo'}
            
        except Exception as e:
            logger.error(f"Erro na previsão de manutenções: {e}")
            return {'erro': str(e)}
    
    def identificar_veiculos_problematicos(self):
        """Identifica veículos com padrões problemáticos"""
        try:
            # Obter dados de desempenho dos veículos
            dados_desempenho = self._obter_dados_desempenho_veiculos()
            
            if len(dados_desempenho) < 5:
                return {'erro': 'Dados insuficientes para análise'}
            
            df = pd.DataFrame(dados_desempenho)
            
            # Features para análise de problemas
            features = ['custo_por_km', 'frequencia_manutencao', 'tempo_parada_medio',
                       'consumo_combustivel', 'idade_veiculo', 'km_total']
            
            X = df[features].fillna(df[features].median())
            
            # Normalizar dados
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Usar Isolation Forest para detectar outliers
            isolation_forest = IsolationForest(contamination=0.1, random_state=42)
            outliers = isolation_forest.fit_predict(X_scaled)
            
            # Clustering para agrupar veículos similares
            kmeans = KMeans(n_clusters=min(4, len(df)), random_state=42)
            clusters = kmeans.fit_predict(X_scaled)
            
            # Analisar resultados
            problematicos = []
            for i, (idx, row) in enumerate(df.iterrows()):
                is_outlier = outliers[i] == -1
                cluster = clusters[i]
                
                # Score de problema (0-100, maior = mais problemático)
                score_problema = self._calcular_score_problema(row, is_outlier, cluster, df)
                
                if score_problema > 60 or is_outlier:  # Threshold para considerar problemático
                    problemas = []
                    
                    # Identificar tipos de problemas
                    if row['custo_por_km'] > df['custo_por_km'].quantile(0.75):
                        problemas.append('Alto custo por KM')
                    
                    if row['frequencia_manutencao'] > df['frequencia_manutencao'].quantile(0.75):
                        problemas.append('Manutenções frequentes')
                    
                    if row['tempo_parada_medio'] > df['tempo_parada_medio'].quantile(0.75):
                        problemas.append('Tempo de parada elevado')
                    
                    if row['consumo_combustivel'] > df['consumo_combustivel'].quantile(0.75):
                        problemas.append('Alto consumo de combustível')
                    
                    problematicos.append({
                        'veiculo_id': row['veiculo_id'],
                        'placa': row['placa'],
                        'marca': row['marca'],
                        'modelo': row['modelo'],
                        'score_problema': round(score_problema, 1),
                        'is_outlier': is_outlier,
                        'cluster': int(cluster),
                        'problemas_identificados': problemas,
                        'custo_por_km': round(row['custo_por_km'], 3),
                        'frequencia_manutencao': round(row['frequencia_manutencao'], 1),
                        'recomendacao': self._gerar_recomendacao_veiculo(problemas)
                    })
            
            # Ordenar por score de problema
            problematicos.sort(key=lambda x: x['score_problema'], reverse=True)
            
            return {
                'veiculos_problematicos': problematicos,
                'total_veiculos_analisados': len(df),
                'total_problematicos': len(problematicos),
                'clusters': {
                    'total_clusters': int(kmeans.n_clusters),
                    'cluster_centers': kmeans.cluster_centers_.tolist()
                }
            }
            
        except Exception as e:
            logger.error(f"Erro na identificação de veículos problemáticos: {e}")
            return {'erro': str(e)}
    
    def prever_custos_futuros(self):
        """Prevê custos futuros baseado em tendências históricas"""
        try:
            # Obter dados históricos de custos mensais
            dados_custos = self._obter_dados_custos_mensais()
            
            if len(dados_custos) < 6:  # Mínimo 6 meses
                return {'erro': 'Dados históricos insuficientes'}
            
            # Previsão por categoria de custo
            previsoes_por_categoria = {}
            
            categorias = ['combustivel', 'manutencao', 'seguro', 'ipva', 'multa', 'outros']
            
            for categoria in categorias:
                dados_categoria = [d for d in dados_custos if categoria in d]
                
                if len(dados_categoria) >= 3:
                    # Preparar dados para regressão temporal
                    X = np.array(range(len(dados_categoria))).reshape(-1, 1)
                    y = np.array([d[categoria] for d in dados_categoria])
                    
                    # Treinar modelo de regressão linear
                    modelo = LinearRegression()
                    modelo.fit(X, y)
                    
                    # Prever próximos 6 meses
                    X_futuro = np.array(range(len(dados_categoria), len(dados_categoria) + 6)).reshape(-1, 1)
                    previsoes = modelo.predict(X_futuro)
                    
                    # Calcular tendência
                    tendencia = modelo.coef_[0]
                    
                    previsoes_por_categoria[categoria] = {
                        'previsoes_6_meses': [max(0, p) for p in previsoes.tolist()],
                        'tendencia_mensal': round(tendencia, 2),
                        'r2_score': round(modelo.score(X, y), 3),
                        'media_historica': round(np.mean(y), 2)
                    }
            
            # Previsão total
            if previsoes_por_categoria:
                previsoes_totais = []
                for i in range(6):
                    total_mes = sum(
                        cat_data['previsoes_6_meses'][i] 
                        for cat_data in previsoes_por_categoria.values()
                    )
                    previsoes_totais.append(round(total_mes, 2))
                
                # Calcular intervalos de confiança simples
                historico_total = [sum(d[cat] for cat in categorias if cat in d) for d in dados_custos]
                desvio_padrao = np.std(historico_total)
                
                intervalos_confianca = [
                    {
                        'previsao': prev,
                        'limite_inferior': max(0, prev - 1.96 * desvio_padrao),
                        'limite_superior': prev + 1.96 * desvio_padrao
                    }
                    for prev in previsoes_totais
                ]
                
                return {
                    'previsoes_por_categoria': previsoes_por_categoria,
                    'previsoes_totais': previsoes_totais,
                    'intervalos_confianca': intervalos_confianca,
                    'total_historico': historico_total[-1] if historico_total else 0,
                    'variacao_prevista': round(
                        ((previsoes_totais[0] - historico_total[-1]) / max(historico_total[-1], 1)) * 100, 2
                    ) if historico_total else 0
                }
            
            return {'erro': 'Não foi possível gerar previsões'}
            
        except Exception as e:
            logger.error(f"Erro na previsão de custos: {e}")
            return {'erro': str(e)}
    
    def analisar_vida_util(self):
        """Analisa vida útil remanescente dos veículos"""
        try:
            veiculos_analise = self._obter_dados_vida_util()
            
            if not veiculos_analise:
                return {'erro': 'Nenhum veículo para análise'}
            
            analises = []
            
            for veiculo in veiculos_analise:
                # Calcular idade atual
                idade_atual = date.today().year - veiculo.get('ano', date.today().year)
                
                # Estimar vida útil total baseada no tipo de veículo
                vida_util_estimada = self._estimar_vida_util_veiculo(veiculo['tipo'])
                
                # Calcular desgaste baseado em uso e manutenções
                fator_desgaste = self._calcular_fator_desgaste(veiculo)
                
                # Vida útil remanescente ajustada
                vida_util_remanescente = max(0, vida_util_estimada - (idade_atual * fator_desgaste))
                
                # Valor residual estimado
                valor_residual = self._estimar_valor_residual(veiculo, vida_util_remanescente, vida_util_estimada)
                
                # Recomendação
                if vida_util_remanescente < 2:
                    recomendacao = 'Substituição recomendada'
                    prioridade = 'Alta'
                elif vida_util_remanescente < 5:
                    recomendacao = 'Monitorar closely'
                    prioridade = 'Média'
                else:
                    recomendacao = 'Veículo em boa condição'
                    prioridade = 'Baixa'
                
                analises.append({
                    'veiculo_id': veiculo['veiculo_id'],
                    'placa': veiculo['placa'],
                    'marca': veiculo['marca'],
                    'modelo': veiculo['modelo'],
                    'idade_atual': idade_atual,
                    'vida_util_estimada': vida_util_estimada,
                    'vida_util_remanescente': round(vida_util_remanescente, 1),
                    'fator_desgaste': round(fator_desgaste, 2),
                    'valor_residual_estimado': round(valor_residual, 2),
                    'percentual_vida_util': round((vida_util_remanescente / vida_util_estimada) * 100, 1),
                    'recomendacao': recomendacao,
                    'prioridade': prioridade
                })
            
            # Ordenar por vida útil remanescente
            analises.sort(key=lambda x: x['vida_util_remanescente'])
            
            return {
                'analises_vida_util': analises,
                'resumo': {
                    'total_veiculos': len(analises),
                    'substituicao_recomendada': len([a for a in analises if a['prioridade'] == 'Alta']),
                    'monitoramento': len([a for a in analises if a['prioridade'] == 'Média']),
                    'bom_estado': len([a for a in analises if a['prioridade'] == 'Baixa'])
                }
            }
            
        except Exception as e:
            logger.error(f"Erro na análise de vida útil: {e}")
            return {'erro': str(e)}
    
    def otimizar_alocacao_frota(self):
        """Otimiza alocação da frota usando análise de dados"""
        try:
            # Obter dados de obras e veículos
            dados_obras = self._obter_dados_obras_alocacao()
            dados_veiculos = self._obter_dados_veiculos_disponiveis()
            
            if not dados_obras or not dados_veiculos:
                return {'erro': 'Dados insuficientes para otimização'}
            
            # Criar matriz de adequação veículo-obra
            matriz_adequacao = self._calcular_matriz_adequacao(dados_veiculos, dados_obras)
            
            # Algoritmo de otimização simples (húngaro seria ideal, mas complexo)
            alocacoes_otimizadas = self._algoritmo_alocacao_simples(matriz_adequacao, dados_veiculos, dados_obras)
            
            # Calcular benefícios da otimização
            beneficios = self._calcular_beneficios_otimizacao(alocacoes_otimizadas)
            
            return {
                'alocacoes_otimizadas': alocacoes_otimizadas,
                'beneficios': beneficios,
                'matriz_adequacao': matriz_adequacao,
                'total_veiculos': len(dados_veiculos),
                'total_obras': len(dados_obras)
            }
            
        except Exception as e:
            logger.error(f"Erro na otimização de alocação: {e}")
            return {'erro': str(e)}
    
    def detectar_anomalias(self):
        """Detecta anomalias em tempo real"""
        try:
            # Período recente para análise
            data_limite = date.today() - timedelta(days=30)
            
            anomalias = []
            
            # Anomalias de custo
            anomalias_custo = self._detectar_anomalias_custo(data_limite)
            anomalias.extend(anomalias_custo)
            
            # Anomalias de uso
            anomalias_uso = self._detectar_anomalias_uso(data_limite)
            anomalias.extend(anomalias_uso)
            
            # Anomalias de manutenção
            anomalias_manutencao = self._detectar_anomalias_manutencao(data_limite)
            anomalias.extend(anomalias_manutencao)
            
            # Classificar por severidade
            anomalias.sort(key=lambda x: x.get('severidade', 0), reverse=True)
            
            return {
                'anomalias_detectadas': anomalias,
                'total_anomalias': len(anomalias),
                'periodo_analise': data_limite.strftime('%d/%m/%Y'),
                'resumo_por_tipo': {
                    'custo': len([a for a in anomalias if a['tipo'] == 'custo']),
                    'uso': len([a for a in anomalias if a['tipo'] == 'uso']),
                    'manutencao': len([a for a in anomalias if a['tipo'] == 'manutencao'])
                }
            }
            
        except Exception as e:
            logger.error(f"Erro na detecção de anomalias: {e}")
            return {'erro': str(e)}
    
    def gerar_recomendacoes(self, resultados_analises):
        """Gera recomendações baseadas nas análises"""
        try:
            recomendacoes = []
            
            # Recomendações baseadas em manutenções
            if 'previsao_manutencoes' in resultados_analises:
                manutencoes = resultados_analises['previsao_manutencoes']
                if 'previsoes' in manutencoes:
                    criticas = [p for p in manutencoes['previsoes'] if p.get('urgencia') == 'Crítica']
                    if criticas:
                        recomendacoes.append({
                            'tipo': 'Manutenção Crítica',
                            'prioridade': 'Alta',
                            'descricao': f'{len(criticas)} veículos precisam de manutenção urgente',
                            'acao': 'Agendar manutenções imediatamente',
                            'veiculos_afetados': [v['placa'] for v in criticas]
                        })
            
            # Recomendações baseadas em veículos problemáticos
            if 'veiculos_problematicos' in resultados_analises:
                problematicos = resultados_analises['veiculos_problematicos']
                if 'veiculos_problematicos' in problematicos:
                    top_problematicos = problematicos['veiculos_problematicos'][:3]
                    if top_problematicos:
                        recomendacoes.append({
                            'tipo': 'Veículos Problemáticos',
                            'prioridade': 'Média',
                            'descricao': f'{len(top_problematicos)} veículos identificados como problemáticos',
                            'acao': 'Avaliar substituição ou intensificar manutenção',
                            'veiculos_afetados': [v['placa'] for v in top_problematicos]
                        })
            
            # Recomendações baseadas em previsão de custos
            if 'predicao_custos' in resultados_analises:
                custos = resultados_analises['predicao_custos']
                if 'variacao_prevista' in custos and custos['variacao_prevista'] > 20:
                    recomendacoes.append({
                        'tipo': 'Aumento de Custos',
                        'prioridade': 'Média',
                        'descricao': f'Previsão de aumento de {custos["variacao_prevista"]:.1f}% nos custos',
                        'acao': 'Revisar orçamento e planos de manutenção',
                        'impacto_financeiro': custos.get('previsoes_totais', [0])[0]
                    })
            
            # Recomendações de otimização
            if 'otimizacao_alocacao' in resultados_analises:
                otimizacao = resultados_analises['otimizacao_alocacao']
                if 'beneficios' in otimizacao:
                    beneficios = otimizacao['beneficios']
                    if beneficios.get('economia_estimada', 0) > 1000:
                        recomendacoes.append({
                            'tipo': 'Otimização de Alocação',
                            'prioridade': 'Baixa',
                            'descricao': f'Economia estimada de R$ {beneficios["economia_estimada"]:.2f}',
                            'acao': 'Implementar alocações otimizadas sugeridas',
                            'beneficio_financeiro': beneficios['economia_estimada']
                        })
            
            return {
                'recomendacoes': recomendacoes,
                'total_recomendacoes': len(recomendacoes),
                'score_otimizacao': self._calcular_score_otimizacao(recomendacoes)
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar recomendações: {e}")
            return {'erro': str(e)}
    
    # === MÉTODOS DE APOIO ===
    
    def _obter_dados_manutencao_historicos(self):
        """Obtém dados históricos de manutenção para ML"""
        # Implementação simplificada - retornar dados mock ou query real
        return []
    
    def _obter_dados_veiculos_atuais(self):
        """Obtém dados atuais dos veículos para previsão"""
        # Implementação simplificada
        return []
    
    def _obter_dados_desempenho_veiculos(self):
        """Obtém dados de desempenho dos veículos"""
        # Implementação simplificada
        return []
    
    def _calcular_score_problema(self, row, is_outlier, cluster, df):
        """Calcula score de problema do veículo"""
        score = 0
        
        # Penalizar outliers
        if is_outlier:
            score += 30
        
        # Analisar métricas individuais
        if row['custo_por_km'] > df['custo_por_km'].quantile(0.8):
            score += 25
        
        if row['frequencia_manutencao'] > df['frequencia_manutencao'].quantile(0.8):
            score += 20
        
        if row['tempo_parada_medio'] > df['tempo_parada_medio'].quantile(0.8):
            score += 15
        
        if row['consumo_combustivel'] > df['consumo_combustivel'].quantile(0.8):
            score += 10
        
        return min(100, score)
    
    def _gerar_recomendacao_veiculo(self, problemas):
        """Gera recomendação específica para veículo"""
        if 'Alto custo por KM' in problemas and 'Manutenções frequentes' in problemas:
            return 'Considerar substituição do veículo'
        elif 'Manutenções frequentes' in problemas:
            return 'Revisar plano de manutenção preventiva'
        elif 'Alto custo por KM' in problemas:
            return 'Investigar causas do alto custo operacional'
        else:
            return 'Monitoramento contínuo recomendado'
    
    def _obter_dados_custos_mensais(self):
        """Obtém dados de custos mensais históricos"""
        # Implementação simplificada
        return []
    
    def _obter_dados_vida_util(self):
        """Obtém dados para análise de vida útil"""
        # Implementação simplificada
        return []
    
    def _estimar_vida_util_veiculo(self, tipo_veiculo):
        """Estima vida útil baseada no tipo de veículo"""
        estimativas = {
            'Caminhão': 15,
            'Van': 12,
            'Pickup': 12,
            'Carro': 10,
            'Motocicleta': 8
        }
        return estimativas.get(tipo_veiculo, 10)
    
    def _calcular_fator_desgaste(self, veiculo):
        """Calcula fator de desgaste baseado no uso"""
        # Implementação simplificada
        return 1.0
    
    def _estimar_valor_residual(self, veiculo, vida_remanescente, vida_total):
        """Estima valor residual do veículo"""
        # Implementação simplificada
        percentual_remanescente = vida_remanescente / vida_total
        valor_inicial = veiculo.get('valor_inicial', 50000)
        return valor_inicial * percentual_remanescente * 0.6  # Fator de depreciação
    
    # Implementar outros métodos conforme necessário...
    def _obter_dados_obras_alocacao(self):
        return []
    
    def _obter_dados_veiculos_disponiveis(self):
        return []
    
    def _calcular_matriz_adequacao(self, veiculos, obras):
        return []
    
    def _algoritmo_alocacao_simples(self, matriz, veiculos, obras):
        return []
    
    def _calcular_beneficios_otimizacao(self, alocacoes):
        return {}
    
    def _detectar_anomalias_custo(self, data_limite):
        return []
    
    def _detectar_anomalias_uso(self, data_limite):
        return []
    
    def _detectar_anomalias_manutencao(self, data_limite):
        return []
    
    def _calcular_score_otimizacao(self, recomendacoes):
        return 75  # Score placeholder

# ===== ROTAS DO BLUEPRINT =====

@analytics_bp.route('/')
@login_required
@admin_required
def dashboard_analytics():
    """Dashboard principal de análises preditivas"""
    admin_id = get_admin_id()
    
    try:
        # Executar análise completa
        engine = EngineAnalyticsPreditivo(admin_id)
        resultados = engine.executar_analise_completa()
        
        return render_template('analytics/dashboard.html',
                             resultados=resultados)
        
    except Exception as e:
        logger.error(f"Erro no dashboard analytics: {e}")
        flash('Erro ao carregar análises preditivas', 'danger')
        return redirect(url_for('main.dashboard'))

@analytics_bp.route('/api/executar-analise', methods=['POST'])
@login_required
@admin_required
def api_executar_analise():
    """API para executar análise específica"""
    admin_id = get_admin_id()
    
    try:
        dados = request.get_json()
        tipo_analise = dados.get('tipo', 'completa')
        
        engine = EngineAnalyticsPreditivo(admin_id)
        
        if tipo_analise == 'manutencoes':
            resultado = engine.prever_manutencoes()
        elif tipo_analise == 'problematicos':
            resultado = engine.identificar_veiculos_problematicos()
        elif tipo_analise == 'custos':
            resultado = engine.prever_custos_futuros()
        elif tipo_analise == 'vida_util':
            resultado = engine.analisar_vida_util()
        elif tipo_analise == 'otimizacao':
            resultado = engine.otimizar_alocacao_frota()
        elif tipo_analise == 'anomalias':
            resultado = engine.detectar_anomalias()
        else:
            resultado = engine.executar_analise_completa()
        
        return jsonify({
            'success': True,
            'resultado': resultado
        })
        
    except Exception as e:
        logger.error(f"Erro na API analytics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/relatorio-preditivo')
@login_required
@admin_required
def relatorio_preditivo():
    """Relatório completo de análises preditivas"""
    admin_id = get_admin_id()
    
    try:
        engine = EngineAnalyticsPreditivo(admin_id)
        resultados = engine.executar_analise_completa()
        
        return render_template('analytics/relatorio_preditivo.html',
                             resultados=resultados,
                             data_geracao=datetime.now())
        
    except Exception as e:
        logger.error(f"Erro no relatório preditivo: {e}")
        flash('Erro ao gerar relatório preditivo', 'danger')
        return redirect(url_for('analytics_preditivos.dashboard_analytics'))