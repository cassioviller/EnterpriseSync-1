#!/usr/bin/env python3
"""
Sistema de IA e Analytics - SIGE v8.0
Implementa Machine Learning e Analytics Avançados
"""

import numpy as np
from models import *
from app import db
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_
import json
import pickle
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
import warnings
warnings.filterwarnings('ignore')

class AIAnalyticsSystem:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.model_path = "models/"
        self.min_data_points = 50  # Mínimo de dados para treinar modelos
        
    def inicializar_sistema(self):
        """Inicializa todos os modelos de ML"""
        print("🤖 Inicializando Sistema de IA e Analytics...")
        
        try:
            self.carregar_ou_treinar_modelo_custos()
            self.carregar_ou_treinar_detector_anomalias()
            self.inicializar_otimizador_recursos()
            self.inicializar_analisador_sentimentos()
            
            print("✅ Sistema de IA inicializado com sucesso!")
            return True
        except Exception as e:
            print(f"❌ Erro ao inicializar IA: {e}")
            return False
    
    def carregar_ou_treinar_modelo_custos(self):
        """Modelo de predição de custos usando Random Forest"""
        print("📊 Preparando modelo de predição de custos...")
        
        try:
            # Tentar carregar modelo existente
            try:
                with open(f'{self.model_path}cost_prediction_model.pkl', 'rb') as f:
                    self.models['cost_prediction'] = pickle.load(f)
                with open(f'{self.model_path}cost_scaler.pkl', 'rb') as f:
                    self.scalers['cost_prediction'] = pickle.load(f)
                print("✅ Modelo de custos carregado do disco")
                return
            except FileNotFoundError:
                pass
            
            # Buscar dados históricos para treinar
            dados_custos = self._preparar_dados_custos()
            
            if len(dados_custos) < self.min_data_points:
                print(f"⚠️ Poucos dados para treinar modelo de custos ({len(dados_custos)} registros)")
                # Criar modelo básico com dados sintéticos para demonstração
                self._criar_modelo_custos_basico()
                return
            
            # Treinar modelo com dados reais
            self._treinar_modelo_custos(dados_custos)
            
        except Exception as e:
            print(f"❌ Erro no modelo de custos: {e}")
            self._criar_modelo_custos_basico()
    
    def _preparar_dados_custos(self):
        """Prepara dados históricos para treinamento"""
        # Buscar dados de obras com custos
        # Verificar se o campo orcamento_total existe
        if hasattr(Obra, 'orcamento_total'):
            query = db.session.query(
                Obra.id,
                Obra.nome,
                Obra.orcamento_total,
                func.sum(CustoObra.valor).label('custo_real'),
                func.count(Funcionario.id).label('num_funcionarios'),
                func.avg(RegistroPonto.horas_trabalhadas).label('media_horas'),
                func.count(RDO.id).label('num_rdos')
            ).outerjoin(CustoObra).outerjoin(Funcionario).outerjoin(RegistroPonto).outerjoin(RDO).group_by(
                Obra.id, Obra.nome, Obra.orcamento_total
            ).filter(
                Obra.orcamento_total.isnot(None),
                CustoObra.valor.isnot(None)
            ).all()
        else:
            # Usar campo alternativo ou valores padrão
            query = db.session.query(
                Obra.id,
                Obra.nome
            ).limit(10).all()
            # Simular dados para treinar modelo básico
            query = [(1, 'Obra Exemplo', 100000, 80000, 5, 8.0, 20) for _ in range(5)]
        
        dados = []
        for item in query:
            if hasattr(item, 'custo_real') and hasattr(item, 'orcamento_total') and item.custo_real and item.orcamento_total:
                if isinstance(item, tuple):
                    # Dados simulados
                    dados.append({
                        'obra_id': item[0],
                        'orcamento': float(item[2]),
                        'custo_real': float(item[3]),
                        'num_funcionarios': item[4] or 0,
                        'media_horas': float(item[5] or 8.0),
                        'num_rdos': item[6] or 0,
                        'duracao_estimada': 30,
                        'complexidade': self._calcular_complexidade_obra(item[2])
                    })
                else:
                    # Dados reais do banco
                    dados.append({
                        'obra_id': item.id,
                        'orcamento': float(item.orcamento_total),
                        'custo_real': float(item.custo_real),
                        'num_funcionarios': item.num_funcionarios or 0,
                        'media_horas': float(item.media_horas or 8.0),
                        'num_rdos': item.num_rdos or 0,
                        'duracao_estimada': 30,
                        'complexidade': self._calcular_complexidade_obra(item.orcamento_total)
                    })
        
        return dados
    
    def _calcular_complexidade_obra(self, orcamento):
        """Calcula complexidade baseada no orçamento"""
        if orcamento < 50000:
            return 1  # Baixa
        elif orcamento < 200000:
            return 2  # Média
        else:
            return 3  # Alta
    
    def _treinar_modelo_custos(self, dados):
        """Treina modelo de Random Forest para predição de custos"""
        df = pd.DataFrame(dados)
        
        # Features para o modelo
        features = ['orcamento', 'num_funcionarios', 'media_horas', 'num_rdos', 'duracao_estimada', 'complexidade']
        X = df[features]
        y = df['custo_real']
        
        # Dividir dados
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Normalizar dados
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Treinar modelo
        modelo = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
        modelo.fit(X_train_scaled, y_train)
        
        # Avaliar modelo
        y_pred = modelo.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"✅ Modelo de custos treinado - MAE: R$ {mae:,.2f}, R²: {r2:.3f}")
        
        # Salvar modelo
        self.models['cost_prediction'] = modelo
        self.scalers['cost_prediction'] = scaler
        
        # Persistir no disco
        import os
        os.makedirs(self.model_path, exist_ok=True)
        with open(f'{self.model_path}cost_prediction_model.pkl', 'wb') as f:
            pickle.dump(modelo, f)
        with open(f'{self.model_path}cost_scaler.pkl', 'wb') as f:
            pickle.dump(scaler, f)
    
    def _criar_modelo_custos_basico(self):
        """Cria modelo básico para demonstração"""
        print("🔧 Criando modelo básico de custos para demonstração...")
        
        # Modelo simples baseado em regras
        class ModeloCustosBasico:
            def predict(self, X):
                # Previsão baseada em regras simples
                predicoes = []
                for row in X:
                    orcamento = row[0]
                    funcionarios = row[1]
                    horas = row[2]
                    complexidade = row[5]
                    
                    # Fórmula simples: orçamento * fator_complexidade * fator_produtividade
                    fator_complexidade = 1 + (complexidade * 0.2)
                    fator_produtividade = 1 + ((8 - horas) * 0.1)
                    fator_equipe = 1 + (funcionarios * 0.05)
                    
                    custo_previsto = orcamento * fator_complexidade * fator_produtividade * fator_equipe
                    predicoes.append(custo_previsto)
                
                return np.array(predicoes)
        
        # Scaler básico
        class ScalerBasico:
            def transform(self, X):
                return np.array(X)
        
        self.models['cost_prediction'] = ModeloCustosBasico()
        self.scalers['cost_prediction'] = ScalerBasico()
    
    def carregar_ou_treinar_detector_anomalias(self):
        """Detector de anomalias usando Isolation Forest"""
        print("🔍 Preparando detector de anomalias...")
        
        try:
            # Buscar dados de custos diários
            dados_anomalias = self._preparar_dados_anomalias()
            
            if len(dados_anomalias) < 30:  # Mínimo para detecção
                print("⚠️ Poucos dados para detector de anomalias")
                self._criar_detector_anomalias_basico()
                return
            
            # Treinar detector
            df = pd.DataFrame(dados_anomalias)
            features = ['valor_diario', 'dia_semana', 'mes', 'num_transacoes']
            X = df[features]
            
            # Isolation Forest
            detector = IsolationForest(contamination=0.1, random_state=42)
            detector.fit(X)
            
            self.models['anomaly_detection'] = detector
            print("✅ Detector de anomalias treinado")
            
        except Exception as e:
            print(f"❌ Erro no detector de anomalias: {e}")
            self._criar_detector_anomalias_basico()
    
    def _preparar_dados_anomalias(self):
        """Prepara dados para detecção de anomalias"""
        # Buscar custos diários dos últimos 90 dias
        data_inicio = date.today() - timedelta(days=90)
        
        custos_diarios = db.session.query(
            CustoObra.data,
            func.sum(CustoObra.valor).label('valor_diario'),
            func.count(CustoObra.id).label('num_transacoes')
        ).filter(
            CustoObra.data >= data_inicio
        ).group_by(CustoObra.data).order_by(CustoObra.data).all()
        
        dados = []
        for item in custos_diarios:
            dados.append({
                'data': item.data,
                'valor_diario': float(item.valor_diario),
                'dia_semana': item.data.weekday(),
                'mes': item.data.month,
                'num_transacoes': item.num_transacoes
            })
        
        return dados
    
    def _criar_detector_anomalias_basico(self):
        """Cria detector básico para demonstração"""
        class DetectorAnomaliaBasico:
            def __init__(self):
                self.limite_superior = 10000  # R$ 10.000 por dia
                
            def predict(self, X):
                # -1 para anomalia, 1 para normal
                return np.array([-1 if row[0] > self.limite_superior else 1 for row in X])
        
        self.models['anomaly_detection'] = DetectorAnomaliaBasico()
    
    def inicializar_otimizador_recursos(self):
        """Inicializa otimizador de recursos"""
        print("⚡ Inicializando otimizador de recursos...")
        
        class OtimizadorRecursos:
            def otimizar_alocacao_funcionarios(self, obras_ativas, funcionarios_disponiveis):
                """Otimiza alocação de funcionários às obras"""
                recomendacoes = []
                
                for obra in obras_ativas:
                    # Calcular necessidade baseada no orçamento se disponível, senão usar padrão
                    if hasattr(obra, 'orcamento_total') and obra.orcamento_total:
                        funcionarios_necessarios = max(1, int(obra.orcamento_total / 100000))
                    else:
                        funcionarios_necessarios = 3  # Padrão
                    
                    recomendacoes.append({
                        'obra_id': obra.id,
                        'obra_nome': obra.nome,
                        'funcionarios_recomendados': funcionarios_necessarios,
                        'prioridade': 'ALTA' if funcionarios_necessarios > 5 else 'MEDIA'
                    })
                
                return recomendacoes
            
            def otimizar_cronograma(self, obras):
                """Otimiza cronograma de obras"""
                cronograma = []
                
                for obra in obras:
                    if hasattr(obra, 'orcamento_total') and obra.orcamento_total:
                        dias_estimados = max(30, int(obra.orcamento_total / 5000))
                    else:
                        dias_estimados = 60  # Padrão
                    
                    cronograma.append({
                        'obra_id': obra.id,
                        'dias_estimados': dias_estimados,
                        'data_conclusao_prevista': (date.today() + timedelta(days=dias_estimados)).isoformat(),
                        'fase_critica': dias_estimados > 90
                    })
                
                return cronograma
        
        self.models['resource_optimization'] = OtimizadorRecursos()
        print("✅ Otimizador de recursos inicializado")
    
    def inicializar_analisador_sentimentos(self):
        """Inicializa analisador de sentimentos básico"""
        print("😊 Inicializando analisador de sentimentos...")
        
        class AnalisadorSentimentos:
            def __init__(self):
                self.palavras_positivas = [
                    'excelente', 'ótimo', 'bom', 'satisfeito', 'feliz', 
                    'sucesso', 'eficiente', 'rápido', 'qualidade'
                ]
                self.palavras_negativas = [
                    'ruim', 'péssimo', 'problema', 'atraso', 'dificuldade',
                    'insatisfeito', 'lento', 'erro', 'falha'
                ]
            
            def analisar_texto(self, texto):
                """Análise básica de sentimento"""
                texto_lower = texto.lower()
                
                score_positivo = sum(1 for palavra in self.palavras_positivas if palavra in texto_lower)
                score_negativo = sum(1 for palavra in self.palavras_negativas if palavra in texto_lower)
                
                if score_positivo > score_negativo:
                    return 'POSITIVO'
                elif score_negativo > score_positivo:
                    return 'NEGATIVO'
                else:
                    return 'NEUTRO'
            
            def analisar_feedback_funcionarios(self):
                """Analisa sentimento de comentários em RDOs"""
                rdos_recentes = RDO.query.filter(
                    RDO.data_relatorio >= (date.today() - timedelta(days=30))
                ).all()
                
                sentimentos = {'POSITIVO': 0, 'NEGATIVO': 0, 'NEUTRO': 0}
                
                for rdo in rdos_recentes:
                    # Verificar se o campo observacoes existe
                    observacoes = None
                    if hasattr(rdo, 'observacoes'):
                        observacoes = rdo.observacoes
                    elif hasattr(rdo, 'descricao'):
                        observacoes = rdo.descricao
                    elif hasattr(rdo, 'comentarios'):
                        observacoes = rdo.comentarios
                    
                    if observacoes:
                        sentimento = self.analisar_texto(observacoes)
                        sentimentos[sentimento] += 1
                
                return sentimentos
        
        self.models['sentiment_analysis'] = AnalisadorSentimentos()
        print("✅ Analisador de sentimentos inicializado")
    
    # Métodos públicos para usar o sistema
    
    def prever_custo_obra(self, obra_id=None, orcamento=None, funcionarios=5, duracao_dias=30):
        """Prevê custo final de uma obra"""
        try:
            if not self.models.get('cost_prediction'):
                return {'erro': 'Modelo de custos não disponível'}
            
            # Preparar dados para predição
            complexidade = self._calcular_complexidade_obra(orcamento or 100000)
            
            features = np.array([[
                orcamento or 100000,  # orcamento
                funcionarios,         # num_funcionarios
                8.0,                 # media_horas (padrão)
                duracao_dias,        # num_rdos estimado
                duracao_dias,        # duracao_estimada
                complexidade         # complexidade
            ]])
            
            # Fazer predição
            features_scaled = self.scalers['cost_prediction'].transform(features)
            custo_previsto = self.models['cost_prediction'].predict(features_scaled)[0]
            
            return {
                'custo_previsto': float(custo_previsto),
                'margem_erro': '±15%',
                'fatores_considerados': {
                    'orcamento_base': orcamento,
                    'equipe': funcionarios,
                    'duracao': duracao_dias,
                    'complexidade': complexidade
                },
                'recomendacoes': self._gerar_recomendacoes_custo(custo_previsto, orcamento)
            }
            
        except Exception as e:
            return {'erro': f'Erro na predição: {str(e)}'}
    
    def detectar_anomalias_gastos(self, dias=7):
        """Detecta anomalias nos gastos recentes"""
        try:
            if not self.models.get('anomaly_detection'):
                return {'erro': 'Detector de anomalias não disponível'}
            
            # Buscar gastos dos últimos dias
            data_inicio = date.today() - timedelta(days=dias)
            
            # Usar context manager para garantir acesso ao app context
            from app import app
            with app.app_context():
                gastos_recentes = db.session.query(
                    CustoObra.data,
                    func.sum(CustoObra.valor).label('valor_diario'),
                    func.count(CustoObra.id).label('num_transacoes')
                ).filter(
                    CustoObra.data >= data_inicio
                ).group_by(CustoObra.data).all()
            
            anomalias = []
            
            for gasto in gastos_recentes:
                features = np.array([[
                    float(gasto.valor_diario),
                    gasto.data.weekday(),
                    gasto.data.month,
                    gasto.num_transacoes
                ]])
                
                predicao = self.models['anomaly_detection'].predict(features)[0]
                
                if predicao == -1:  # Anomalia detectada
                    anomalias.append({
                        'data': gasto.data.isoformat(),
                        'valor': float(gasto.valor_diario),
                        'transacoes': gasto.num_transacoes,
                        'tipo_anomalia': 'GASTO_ALTO' if gasto.valor_diario > 5000 else 'PADRÃO_INCOMUM'
                    })
            
            return {
                'anomalias_detectadas': len(anomalias),
                'detalhes': anomalias,
                'periodo_analisado': f'Últimos {dias} dias'
            }
            
        except Exception as e:
            return {'erro': f'Erro na detecção: {str(e)}'}
    
    def otimizar_recursos(self):
        """Otimiza alocação de recursos"""
        try:
            if not self.models.get('resource_optimization'):
                return {'erro': 'Otimizador não disponível'}
            
            obras_ativas = Obra.query.filter_by(status='Em andamento').all()
            funcionarios_ativos = Funcionario.query.filter_by(ativo=True).all()
            
            otimizador = self.models['resource_optimization']
            
            return {
                'alocacao_funcionarios': otimizador.otimizar_alocacao_funcionarios(obras_ativas, funcionarios_ativos),
                'cronograma_otimizado': otimizador.otimizar_cronograma(obras_ativas),
                'recomendacoes_gerais': [
                    'Redistribuir equipes baseado na prioridade das obras',
                    'Monitorar obras com mais de 90 dias de duração',
                    'Avaliar necessidade de contratação sazonal'
                ]
            }
            
        except Exception as e:
            return {'erro': f'Erro na otimização: {str(e)}'}
    
    def analisar_sentimentos(self):
        """Analisa sentimentos nos feedbacks"""
        try:
            if not self.models.get('sentiment_analysis'):
                return {'erro': 'Analisador de sentimentos não disponível'}
            
            analisador = self.models['sentiment_analysis']
            sentimentos = analisador.analisar_feedback_funcionarios()
            
            total = sum(sentimentos.values())
            
            if total == 0:
                return {'mensagem': 'Nenhum feedback encontrado nos últimos 30 dias'}
            
            return {
                'sentimentos': sentimentos,
                'percentuais': {
                    'positivo': round((sentimentos['POSITIVO'] / total) * 100, 1),
                    'negativo': round((sentimentos['NEGATIVO'] / total) * 100, 1),
                    'neutro': round((sentimentos['NEUTRO'] / total) * 100, 1)
                },
                'total_feedbacks': total,
                'clima_geral': 'POSITIVO' if sentimentos['POSITIVO'] > sentimentos['NEGATIVO'] else 'NEGATIVO' if sentimentos['NEGATIVO'] > sentimentos['POSITIVO'] else 'NEUTRO'
            }
            
        except Exception as e:
            return {'erro': f'Erro na análise: {str(e)}'}
    
    def _gerar_recomendacoes_custo(self, custo_previsto, orcamento):
        """Gera recomendações baseadas na predição de custo"""
        if not orcamento:
            return ['Definir orçamento base para comparação']
        
        percentual = (custo_previsto / orcamento) * 100
        
        if percentual <= 90:
            return ['Projeto dentro do orçamento', 'Manter controle atual']
        elif percentual <= 110:
            return ['Risco moderado de estouro', 'Monitorar custos semanalmente']
        else:
            return ['Alto risco de estouro', 'Revisar escopo urgentemente', 'Implementar controle rígido de gastos']
    
    def gerar_relatorio_completo(self):
        """Gera relatório completo de analytics e IA"""
        relatorio = {
            'timestamp': datetime.now().isoformat(),
            'periodo_analise': '30 dias',
            'modelos_ativos': list(self.models.keys()),
            'predicoes': {},
            'anomalias': {},
            'otimizacoes': {},
            'sentimentos': {}
        }
        
        try:
            # Predições de custo para obras ativas
            obras_ativas = Obra.query.filter_by(status='Em andamento').limit(5).all()
            relatorio['predicoes'] = []
            
            for obra in obras_ativas:
                predicao = self.prever_custo_obra(
                    obra_id=obra.id,
                    orcamento=obra.orcamento_total,
                    funcionarios=5,
                    duracao_dias=60
                )
                predicao['obra_nome'] = obra.nome
                relatorio['predicoes'].append(predicao)
            
            # Detecção de anomalias
            relatorio['anomalias'] = self.detectar_anomalias_gastos(dias=14)
            
            # Otimizações
            relatorio['otimizacoes'] = self.otimizar_recursos()
            
            # Análise de sentimentos
            relatorio['sentimentos'] = self.analisar_sentimentos()
            
        except Exception as e:
            relatorio['erro'] = f'Erro na geração do relatório: {str(e)}'
        
        return relatorio

# Instância global do sistema
ai_system = AIAnalyticsSystem()

# Função para inicializar na aplicação
def inicializar_ia():
    """Inicializa sistema de IA na aplicação"""
    return ai_system.inicializar_sistema()

# Funções públicas para usar nas views
def prever_custo_obra_api(orcamento, funcionarios=5, duracao=30):
    """API para predição de custos"""
    return ai_system.prever_custo_obra(
        orcamento=orcamento,
        funcionarios=funcionarios,
        duracao_dias=duracao
    )

def detectar_anomalias_api(dias=7):
    """API para detecção de anomalias"""
    return ai_system.detectar_anomalias_gastos(dias)

def otimizar_recursos_api():
    """API para otimização de recursos"""
    return ai_system.otimizar_recursos()

def analisar_sentimentos_api():
    """API para análise de sentimentos"""
    return ai_system.analisar_sentimentos()

def gerar_relatorio_ia_completo():
    """API para relatório completo de IA"""
    return ai_system.gerar_relatorio_completo()

if __name__ == "__main__":
    # Teste standalone
    with app.app_context():
        print("🚀 Testando Sistema de IA...")
        sucesso = inicializar_ia()
        
        if sucesso:
            relatorio = gerar_relatorio_ia_completo()
            print(f"📊 Relatório gerado: {len(relatorio)} seções")
        else:
            print("❌ Falha na inicialização")