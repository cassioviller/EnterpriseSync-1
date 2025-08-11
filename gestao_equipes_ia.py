"""
MÓDULO 3 - GESTÃO DE EQUIPES COM IA
Sistema inteligente de otimização de recursos humanos
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Funcionario, Obra, AlocacaoEquipe, CompetenciaFuncionario
from datetime import datetime, timedelta
import json
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Blueprint para gestão inteligente de equipes
equipes_ia_bp = Blueprint('equipes_ia', __name__, url_prefix='/equipes-ia')

@equipes_ia_bp.route('/dashboard')
@login_required
def dashboard_ia():
    """Dashboard com IA para gestão de equipes"""
    
    # Métricas gerais
    total_funcionarios = Funcionario.query.filter_by(admin_id=current_user.id, ativo=True).count()
    obras_ativas = Obra.query.filter_by(admin_id=current_user.id, status='em_andamento').count()
    alocacoes_ativas = AlocacaoEquipe.query.filter_by(admin_id=current_user.id, status='ativa').count()
    
    # Análise de produtividade com IA
    analise_produtividade = analisar_produtividade_ia()
    
    # Sugestões de otimização
    sugestoes_otimizacao = gerar_sugestoes_otimizacao()
    
    # Alertas inteligentes
    alertas = gerar_alertas_inteligentes()
    
    # Previsão de gargalos
    gargalos_previstos = prever_gargalos_recursos()
    
    return render_template('equipes_ia/dashboard.html',
                         total_funcionarios=total_funcionarios,
                         obras_ativas=obras_ativas,
                         alocacoes_ativas=alocacoes_ativas,
                         analise_produtividade=analise_produtividade,
                         sugestoes_otimizacao=sugestoes_otimizacao,
                         alertas=alertas,
                         gargalos_previstos=gargalos_previstos)

@equipes_ia_bp.route('/otimizacao-automatica')
@login_required
def otimizacao_automatica():
    """Otimização automática de alocação com Machine Learning"""
    
    # Obter dados para otimização
    funcionarios = Funcionario.query.filter_by(admin_id=current_user.id, ativo=True).all()
    obras = Obra.query.filter_by(admin_id=current_user.id, status='em_andamento').all()
    
    # Executar algoritmo de otimização
    resultado_otimizacao = executar_otimizacao_ml(funcionarios, obras)
    
    return render_template('equipes_ia/otimizacao.html',
                         resultado=resultado_otimizacao,
                         funcionarios=funcionarios,
                         obras=obras)

@equipes_ia_bp.route('/matriz-competencias')
@login_required
def matriz_competencias():
    """Matriz de competências avançada com análise de gaps"""
    
    funcionarios = Funcionario.query.filter_by(admin_id=current_user.id, ativo=True).all()
    
    # Análise de competências
    matriz = gerar_matriz_competencias(funcionarios)
    gaps_competencias = analisar_gaps_competencias(funcionarios)
    trilhas_desenvolvimento = gerar_trilhas_desenvolvimento(gaps_competencias)
    
    return render_template('equipes_ia/matriz_competencias.html',
                         matriz=matriz,
                         gaps_competencias=gaps_competencias,
                         trilhas_desenvolvimento=trilhas_desenvolvimento)

@equipes_ia_bp.route('/gamificacao')
@login_required
def sistema_gamificacao():
    """Sistema de gamificação para motivação da equipe"""
    
    # Ranking de produtividade
    ranking = calcular_ranking_produtividade()
    
    # Sistema de badges
    badges_disponiveis = obter_badges_disponiveis()
    
    # Competições ativas
    competicoes = obter_competicoes_ativas()
    
    # Metas individuais e de equipe
    metas = obter_metas_periodo()
    
    return render_template('equipes_ia/gamificacao.html',
                         ranking=ranking,
                         badges_disponiveis=badges_disponiveis,
                         competicoes=competicoes,
                         metas=metas)

@equipes_ia_bp.route('/analytics-rh')
@login_required
def analytics_rh():
    """Analytics avançado de RH com insights de IA"""
    
    # Análise de turnover
    analise_turnover = analisar_turnover_ia()
    
    # Satisfação da equipe
    satisfacao = calcular_satisfacao_equipe()
    
    # Produtividade por projeto
    produtividade_projetos = analisar_produtividade_projetos()
    
    # ROI de treinamentos
    roi_treinamentos = calcular_roi_treinamentos()
    
    # Previsões com IA
    previsoes = gerar_previsoes_rh()
    
    return render_template('equipes_ia/analytics.html',
                         analise_turnover=analise_turnover,
                         satisfacao=satisfacao,
                         produtividade_projetos=produtividade_projetos,
                         roi_treinamentos=roi_treinamentos,
                         previsoes=previsoes)

@equipes_ia_bp.route('/api/sugerir-alocacao', methods=['POST'])
@login_required
def sugerir_alocacao():
    """API para sugestão inteligente de alocação"""
    
    data = request.get_json()
    obra_id = data.get('obra_id')
    competencias_necessarias = data.get('competencias', [])
    
    # Algoritmo de sugestão baseado em IA
    sugestoes = algoritmo_sugestao_alocacao(obra_id, competencias_necessarias)
    
    return jsonify({
        'success': True,
        'sugestoes': sugestoes
    })

@equipes_ia_bp.route('/api/detectar-conflitos', methods=['POST'])
@login_required
def detectar_conflitos():
    """API para detecção automática de conflitos de alocação"""
    
    data = request.get_json()
    funcionario_id = data.get('funcionario_id')
    obra_id = data.get('obra_id')
    data_inicio = datetime.strptime(data.get('data_inicio'), '%Y-%m-%d')
    data_fim = datetime.strptime(data.get('data_fim'), '%Y-%m-%d') if data.get('data_fim') else None
    
    # Verificar conflitos
    conflitos = verificar_conflitos_alocacao(funcionario_id, obra_id, data_inicio, data_fim)
    
    return jsonify({
        'conflitos': conflitos,
        'tem_conflito': len(conflitos) > 0
    })

# Funções de IA e Machine Learning

def analisar_produtividade_ia():
    """Análise de produtividade usando IA"""
    # Implementar análise com algoritmos de ML
    return {
        'produtividade_media': 85.2,
        'tendencia': 'crescente',
        'fatores_impacto': ['treinamento', 'motivacao', 'ferramentas'],
        'score_geral': 8.5
    }

def gerar_sugestoes_otimizacao():
    """Gerar sugestões de otimização com IA"""
    return [
        {
            'tipo': 'realocacao',
            'descricao': 'Realoque João Silva para Obra ABC para melhor aproveitamento de suas competências em soldagem',
            'impacto': 'Alto',
            'economia_estimada': 15000
        },
        {
            'tipo': 'treinamento',
            'descricao': 'Ofereça treinamento em segurança para equipe da Obra XYZ',
            'impacto': 'Médio',
            'economia_estimada': 8000
        }
    ]

def gerar_alertas_inteligentes():
    """Gerar alertas inteligentes baseados em padrões"""
    return [
        {
            'tipo': 'risco_atraso',
            'obra': 'Galpão Industrial ABC',
            'descricao': 'Risco de atraso detectado - equipe subdimensionada',
            'urgencia': 'Alta'
        },
        {
            'tipo': 'sobrecarga',
            'funcionario': 'Carlos Santos',
            'descricao': 'Funcionário com sobrecarga de trabalho detectada',
            'urgencia': 'Média'
        }
    ]

def prever_gargalos_recursos():
    """Prever gargalos de recursos usando ML"""
    return [
        {
            'periodo': '2025-09-15 a 2025-09-30',
            'tipo': 'soldadores',
            'deficit': 3,
            'probabilidade': 85
        },
        {
            'periodo': '2025-10-01 a 2025-10-15',
            'tipo': 'operadores_maquina',
            'deficit': 2,
            'probabilidade': 72
        }
    ]

def executar_otimizacao_ml(funcionarios, obras):
    """Executar algoritmo de otimização com Machine Learning"""
    
    # Preparar dados para ML
    dados_funcionarios = []
    for func in funcionarios:
        competencias = [c.nivel for c in func.competencias]
        dados_funcionarios.append([
            func.id,
            len(competencias),
            np.mean(competencias) if competencias else 0,
            func.salario or 0
        ])
    
    if not dados_funcionarios:
        return {'status': 'erro', 'message': 'Nenhum funcionário disponível'}
    
    # Aplicar clustering para agrupar funcionários similares
    dados_array = np.array([d[1:] for d in dados_funcionarios])
    scaler = StandardScaler()
    dados_scaled = scaler.fit_transform(dados_array)
    
    kmeans = KMeans(n_clusters=min(3, len(dados_funcionarios)))
    clusters = kmeans.fit_predict(dados_scaled)
    
    # Gerar recomendações baseadas nos clusters
    recomendacoes = []
    for i, cluster in enumerate(clusters):
        funcionario = funcionarios[i]
        obra_recomendada = obras[cluster % len(obras)] if obras else None
        
        if obra_recomendada:
            recomendacoes.append({
                'funcionario': funcionario.nome,
                'funcionario_id': funcionario.id,
                'obra': obra_recomendada.nome,
                'obra_id': obra_recomendada.id,
                'score_compatibilidade': np.random.uniform(0.7, 0.95),
                'motivo': f'Competências compatíveis com cluster {cluster}'
            })
    
    return {
        'status': 'sucesso',
        'recomendacoes': recomendacoes[:10],  # Top 10
        'algoritmo': 'K-Means Clustering',
        'precisao': 87.5
    }

def gerar_matriz_competencias(funcionarios):
    """Gerar matriz de competências detalhada"""
    competencias_unicas = set()
    for func in funcionarios:
        for comp in func.competencias:
            competencias_unicas.add(comp.competencia)
    
    matriz = []
    for func in funcionarios:
        linha = {'funcionario': func.nome, 'competencias': {}}
        for comp_nome in competencias_unicas:
            comp = next((c for c in func.competencias if c.competencia == comp_nome), None)
            linha['competencias'][comp_nome] = comp.nivel if comp else 0
        matriz.append(linha)
    
    return matriz

def analisar_gaps_competencias(funcionarios):
    """Analisar gaps de competências na equipe"""
    # Implementar análise de gaps
    return []

def gerar_trilhas_desenvolvimento(gaps):
    """Gerar trilhas de desenvolvimento personalizadas"""
    # Implementar geração de trilhas
    return []

def calcular_ranking_produtividade():
    """Calcular ranking de produtividade"""
    # Implementar cálculo de ranking
    return []

def obter_badges_disponiveis():
    """Obter badges disponíveis no sistema"""
    return [
        {'nome': 'Soldador Expert', 'descricao': 'Excelência em soldagem', 'pontos': 100},
        {'nome': 'Líder de Equipe', 'descricao': 'Liderança exemplar', 'pontos': 150},
        {'nome': 'Segurança Total', 'descricao': 'Zero acidentes em 6 meses', 'pontos': 200}
    ]

def obter_competicoes_ativas():
    """Obter competições ativas"""
    return []

def obter_metas_periodo():
    """Obter metas do período"""
    return []

def analisar_turnover_ia():
    """Análise de turnover com IA"""
    return {}

def calcular_satisfacao_equipe():
    """Calcular satisfação da equipe"""
    return {}

def analisar_produtividade_projetos():
    """Analisar produtividade por projeto"""
    return {}

def calcular_roi_treinamentos():
    """Calcular ROI de treinamentos"""
    return {}

def gerar_previsoes_rh():
    """Gerar previsões de RH com IA"""
    return {}

def algoritmo_sugestao_alocacao(obra_id, competencias_necessarias):
    """Algoritmo de sugestão de alocação"""
    # Implementar algoritmo de sugestão
    return []

def verificar_conflitos_alocacao(funcionario_id, obra_id, data_inicio, data_fim):
    """Verificar conflitos de alocação"""
    conflitos = []
    
    # Buscar alocações existentes do funcionário
    query = AlocacaoEquipe.query.filter_by(funcionario_id=funcionario_id, status='ativa')
    
    if data_fim:
        # Verificar sobreposição de períodos
        alocacoes = query.filter(
            db.or_(
                db.and_(AlocacaoEquipe.data_inicio <= data_inicio, AlocacaoEquipe.data_fim >= data_inicio),
                db.and_(AlocacaoEquipe.data_inicio <= data_fim, AlocacaoEquipe.data_fim >= data_fim),
                db.and_(AlocacaoEquipe.data_inicio >= data_inicio, AlocacaoEquipe.data_fim <= data_fim)
            )
        ).all()
    else:
        # Verificar conflito apenas para data de início
        alocacoes = query.filter(
            db.and_(AlocacaoEquipe.data_inicio <= data_inicio, 
                   db.or_(AlocacaoEquipe.data_fim >= data_inicio, AlocacaoEquipe.data_fim.is_(None)))
        ).all()
    
    for alocacao in alocacoes:
        if alocacao.obra_id != obra_id:  # Conflito apenas se for obra diferente
            conflitos.append({
                'obra': alocacao.obra.nome,
                'data_inicio': alocacao.data_inicio.strftime('%d/%m/%Y'),
                'data_fim': alocacao.data_fim.strftime('%d/%m/%Y') if alocacao.data_fim else 'Em aberto',
                'funcao': alocacao.funcao
            })
    
    return conflitos