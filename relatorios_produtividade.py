"""
RELATÓRIOS DE PRODUTIVIDADE - SIGE v8.0
Sistema avançado de análise de produtividade e eficiência da frota

Funcionalidades:
- Produtividade por veículo (km/dia, horas úteis, eficiência)
- Comparativo entre veículos similares
- Ranking de desempenho (melhor/pior)
- Análise de sazonalidade de uso
- Benchmarking e metas de performance
"""

from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_, text, extract, case
from sqlalchemy.orm import joinedload
import json
import logging
from decimal import Decimal
from collections import defaultdict
import numpy as np
from statistics import mean, median

# Importar modelos
from models import (
    db, Veiculo, CustoVeiculo, UsoVeiculo, AlocacaoVeiculo, ManutencaoVeiculo,
    Obra, Funcionario, Usuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
produtividade_bp = Blueprint('relatorios_produtividade', __name__, url_prefix='/relatorios/produtividade')

def get_admin_id():
    """Obtém admin_id do usuário atual"""
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario.value == 'admin':
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return current_user.id

def safe_db_operation(operation, default_value=None):
    """Executa operação no banco com tratamento seguro"""
    try:
        return operation()
    except Exception as e:
        logger.error(f"Erro na operação DB: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return default_value

# ===== RELATÓRIOS DE PRODUTIVIDADE =====

@produtividade_bp.route('/')
@login_required
@admin_required
def index_produtividade():
    """Página inicial dos relatórios de produtividade"""
    admin_id = get_admin_id()
    
    # Período padrão (últimos 30 dias)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=30)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    veiculo_id = request.args.get('veiculo_id', type=int)
    obra_id = request.args.get('obra_id', type=int)
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # === ANÁLISE GERAL DE PRODUTIVIDADE ===
        produtividade_geral = calcular_produtividade_geral(admin_id, data_inicio, data_fim)
        
        # === RANKING DE VEÍCULOS ===
        ranking_veiculos = calcular_ranking_veiculos(admin_id, data_inicio, data_fim)
        
        # === COMPARATIVO POR CATEGORIA ===
        comparativo_categoria = comparativo_por_categoria(admin_id, data_inicio, data_fim)
        
        # === ANÁLISE TEMPORAL ===
        analise_temporal = analise_tendencia_uso(admin_id, data_inicio, data_fim)
        
        # === METAS E BENCHMARKS ===
        metas_performance = calcular_metas_e_benchmarks(admin_id, data_inicio, data_fim)
        
        # === FILTROS PARA O FORMULÁRIO ===
        veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        return render_template('relatorios/produtividade/index.html',
                             produtividade_geral=produtividade_geral,
                             ranking_veiculos=ranking_veiculos,
                             comparativo_categoria=comparativo_categoria,
                             analise_temporal=analise_temporal,
                             metas_performance=metas_performance,
                             veiculos=veiculos,
                             obras=obras,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             veiculo_id=veiculo_id,
                             obra_id=obra_id)
        
    except Exception as e:
        logger.error(f"Erro no relatório de produtividade: {e}")
        flash('Erro ao carregar relatório de produtividade', 'danger')
        return redirect(url_for('main.dashboard'))

def calcular_produtividade_geral(admin_id, data_inicio, data_fim):
    """Calcula métricas gerais de produtividade da frota"""
    
    try:
        # Consulta principal com métricas agregadas
        dados_base = db.session.query(
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_uteis')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        if not dados_base or not dados_base.km_total:
            return {
                'km_total': 0, 'horas_total': 0, 'veiculos_utilizados': 0,
                'km_por_dia': 0, 'horas_por_dia': 0, 'km_por_veiculo': 0,
                'utilizacao_frota': 0, 'eficiencia_temporal': 0
            }
        
        # Calcular métricas derivadas
        dias_periodo = (data_fim - data_inicio).days + 1
        frota_total = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).count()
        
        km_por_dia = float(dados_base.km_total) / max(dados_base.dias_uteis, 1)
        horas_por_dia = float(dados_base.horas_total) / max(dados_base.dias_uteis, 1)
        km_por_veiculo = float(dados_base.km_total) / max(dados_base.veiculos_utilizados, 1)
        utilizacao_frota = (dados_base.veiculos_utilizados / max(frota_total, 1)) * 100
        eficiencia_temporal = float(dados_base.km_total) / max(float(dados_base.horas_total), 1)
        
        return {
            'km_total': float(dados_base.km_total or 0),
            'horas_total': float(dados_base.horas_total or 0),
            'veiculos_utilizados': dados_base.veiculos_utilizados or 0,
            'total_usos': dados_base.total_usos or 0,
            'dias_uteis': dados_base.dias_uteis or 0,
            'km_por_dia': round(km_por_dia, 2),
            'horas_por_dia': round(horas_por_dia, 2),
            'km_por_veiculo': round(km_por_veiculo, 2),
            'utilizacao_frota': round(utilizacao_frota, 2),
            'eficiencia_temporal': round(eficiencia_temporal, 2),
            'frota_total': frota_total
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular produtividade geral: {e}")
        return {}

def calcular_ranking_veiculos(admin_id, data_inicio, data_fim):
    """Calcula ranking de produtividade dos veículos"""
    
    try:
        # Query complexa para ranking
        dados = db.session.query(
            Veiculo.id,
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            Veiculo.tipo,
            func.coalesce(func.sum(UsoVeiculo.km_rodado), 0).label('km_total'),
            func.coalesce(func.sum(UsoVeiculo.horas_uso), 0).label('horas_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_ativo'),
            func.coalesce(func.sum(CustoVeiculo.valor), 0).label('custo_total')
        ).select_from(Veiculo)\
        .outerjoin(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == Veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .outerjoin(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == Veiculo.id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .filter(Veiculo.admin_id == admin_id, Veiculo.ativo == True)\
        .group_by(Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo, Veiculo.tipo)\
        .all()
        
        ranking = []
        for d in dados:
            # Calcular métricas de produtividade
            km_por_dia = float(d.km_total) / max(d.dias_ativo, 1) if d.dias_ativo > 0 else 0
            km_por_uso = float(d.km_total) / max(d.total_usos, 1) if d.total_usos > 0 else 0
            custo_por_km = float(d.custo_total) / max(float(d.km_total), 1) if d.km_total > 0 else 0
            eficiencia_temporal = float(d.km_total) / max(float(d.horas_total), 1) if d.horas_total > 0 else 0
            
            # Score de produtividade (0-100)
            score_produtividade = calcular_score_produtividade(
                km_por_dia, km_por_uso, custo_por_km, eficiencia_temporal, d.dias_ativo
            )
            
            # Classificação baseada no score
            if score_produtividade >= 80:
                classificacao = 'Excelente'
                cor_classificacao = 'success'
            elif score_produtividade >= 60:
                classificacao = 'Bom'
                cor_classificacao = 'primary'
            elif score_produtividade >= 40:
                classificacao = 'Regular'
                cor_classificacao = 'warning'
            else:
                classificacao = 'Ruim'
                cor_classificacao = 'danger'
            
            ranking.append({
                'veiculo_id': d.id,
                'placa': d.placa,
                'marca': d.marca,
                'modelo': d.modelo,
                'tipo': d.tipo,
                'km_total': float(d.km_total),
                'horas_total': float(d.horas_total),
                'total_usos': d.total_usos,
                'dias_ativo': d.dias_ativo,
                'custo_total': float(d.custo_total),
                'km_por_dia': round(km_por_dia, 2),
                'km_por_uso': round(km_por_uso, 2),
                'custo_por_km': round(custo_por_km, 2),
                'eficiencia_temporal': round(eficiencia_temporal, 2),
                'score_produtividade': round(score_produtividade, 1),
                'classificacao': classificacao,
                'cor_classificacao': cor_classificacao
            })
        
        # Ordenar por score de produtividade
        return sorted(ranking, key=lambda x: x['score_produtividade'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro ao calcular ranking: {e}")
        return []

def comparativo_por_categoria(admin_id, data_inicio, data_fim):
    """Compara produtividade por categoria/tipo de veículo"""
    
    try:
        dados = db.session.query(
            Veiculo.tipo,
            func.count(func.distinct(Veiculo.id)).label('total_veiculos'),
            func.coalesce(func.sum(UsoVeiculo.km_rodado), 0).label('km_total'),
            func.coalesce(func.sum(UsoVeiculo.horas_uso), 0).label('horas_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.coalesce(func.sum(CustoVeiculo.valor), 0).label('custo_total')
        ).select_from(Veiculo)\
        .outerjoin(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == Veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .outerjoin(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == Veiculo.id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .filter(Veiculo.admin_id == admin_id, Veiculo.ativo == True)\
        .group_by(Veiculo.tipo)\
        .all()
        
        comparativo = []
        for d in dados:
            km_por_veiculo = float(d.km_total) / max(d.total_veiculos, 1)
            custo_por_veiculo = float(d.custo_total) / max(d.total_veiculos, 1)
            eficiencia_categoria = float(d.km_total) / max(float(d.horas_total), 1) if d.horas_total > 0 else 0
            
            comparativo.append({
                'tipo': d.tipo,
                'total_veiculos': d.total_veiculos,
                'km_total': float(d.km_total),
                'horas_total': float(d.horas_total),
                'total_usos': d.total_usos,
                'custo_total': float(d.custo_total),
                'km_por_veiculo': round(km_por_veiculo, 2),
                'custo_por_veiculo': round(custo_por_veiculo, 2),
                'eficiencia_categoria': round(eficiencia_categoria, 2)
            })
        
        return sorted(comparativo, key=lambda x: x['km_por_veiculo'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro no comparativo por categoria: {e}")
        return []

def analise_tendencia_uso(admin_id, data_inicio, data_fim):
    """Analisa tendências de uso ao longo do tempo"""
    
    try:
        # Análise semanal
        dados_semanais = db.session.query(
            extract('week', UsoVeiculo.data_uso).label('semana'),
            extract('year', UsoVeiculo.data_uso).label('ano'),
            func.sum(UsoVeiculo.km_rodado).label('km_semana'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_ativos'),
            func.sum(UsoVeiculo.horas_uso).label('horas_semana')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(
            extract('week', UsoVeiculo.data_uso),
            extract('year', UsoVeiculo.data_uso)
        ).order_by('ano', 'semana').all()
        
        # Análise por dia da semana
        dados_dia_semana = db.session.query(
            extract('dow', UsoVeiculo.data_uso).label('dia_semana'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio'),
            func.count(UsoVeiculo.id).label('total_usos')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(extract('dow', UsoVeiculo.data_uso))\
        .order_by('dia_semana').all()
        
        # Mapear nomes dos dias
        nomes_dias = {0: 'Domingo', 1: 'Segunda', 2: 'Terça', 3: 'Quarta', 
                     4: 'Quinta', 5: 'Sexta', 6: 'Sábado'}
        
        tendencia_dia_semana = []
        for d in dados_dia_semana:
            tendencia_dia_semana.append({
                'dia': nomes_dias.get(int(d.dia_semana), 'Desconhecido'),
                'km_medio': round(float(d.km_medio or 0), 2),
                'total_usos': d.total_usos
            })
        
        # Preparar dados semanais
        tendencia_semanal = []
        for d in dados_semanais:
            tendencia_semanal.append({
                'periodo': f"{int(d.ano)}-W{int(d.semana)}",
                'km_semana': float(d.km_semana or 0),
                'veiculos_ativos': d.veiculos_ativos,
                'horas_semana': float(d.horas_semana or 0)
            })
        
        return {
            'tendencia_semanal': tendencia_semanal,
            'tendencia_dia_semana': tendencia_dia_semana
        }
        
    except Exception as e:
        logger.error(f"Erro na análise temporal: {e}")
        return {'tendencia_semanal': [], 'tendencia_dia_semana': []}

def calcular_metas_e_benchmarks(admin_id, data_inicio, data_fim):
    """Calcula metas e benchmarks de performance"""
    
    try:
        # Obter dados históricos (últimos 6 meses para benchmark)
        data_historica = data_inicio - timedelta(days=180)
        
        dados_historicos = db.session.query(
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_historica,
            UsoVeiculo.data_uso < data_inicio
        ).first()
        
        dados_atuais = db.session.query(
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        # Calcular benchmarks e metas
        if dados_historicos and dados_historicos.km_total:
            benchmark_km_dia = float(dados_historicos.km_total) / 180  # 6 meses
            meta_km_dia = benchmark_km_dia * 1.1  # Meta 10% acima do histórico
        else:
            benchmark_km_dia = 0
            meta_km_dia = 100  # Meta padrão
        
        if dados_atuais and dados_atuais.km_total:
            dias_periodo = (data_fim - data_inicio).days + 1
            km_dia_atual = float(dados_atuais.km_total) / dias_periodo
            atingimento_meta = (km_dia_atual / max(meta_km_dia, 1)) * 100
        else:
            km_dia_atual = 0
            atingimento_meta = 0
        
        return {
            'benchmark_km_dia': round(benchmark_km_dia, 2),
            'meta_km_dia': round(meta_km_dia, 2),
            'km_dia_atual': round(km_dia_atual, 2),
            'atingimento_meta': round(atingimento_meta, 2),
            'status_meta': 'success' if atingimento_meta >= 100 else 'warning' if atingimento_meta >= 80 else 'danger'
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular metas: {e}")
        return {
            'benchmark_km_dia': 0, 'meta_km_dia': 0, 'km_dia_atual': 0,
            'atingimento_meta': 0, 'status_meta': 'secondary'
        }

def calcular_score_produtividade(km_por_dia, km_por_uso, custo_por_km, eficiencia_temporal, dias_ativo):
    """Calcula score de produtividade (0-100) baseado em múltiplos fatores"""
    
    if km_por_dia == 0:
        return 0
    
    # Normalizar métricas (valores arbitrários ajustáveis)
    score_uso = min(100, (km_por_dia / 50) * 100)  # 50km/dia = 100%
    score_eficiencia = min(100, (km_por_uso / 30) * 100)  # 30km/uso = 100%
    score_custo = max(0, 100 - (custo_por_km * 20))  # Menos custo = melhor
    score_tempo = min(100, eficiencia_temporal * 5)  # Mais km/hora = melhor
    score_consistencia = min(100, (dias_ativo / 20) * 100)  # 20 dias ativos = 100%
    
    # Média ponderada
    score_final = (
        score_uso * 0.3 +
        score_eficiencia * 0.2 +
        score_custo * 0.2 +
        score_tempo * 0.15 +
        score_consistencia * 0.15
    )
    
    return max(0, min(100, score_final))

# ===== RELATÓRIOS ESPECÍFICOS =====

@produtividade_bp.route('/veiculo/<int:veiculo_id>')
@login_required
@admin_required
def produtividade_veiculo_detalhado(veiculo_id):
    """Análise detalhada de produtividade de um veículo específico"""
    admin_id = get_admin_id()
    
    veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=admin_id).first_or_404()
    
    # Período padrão (últimos 90 dias)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=90)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # Análise detalhada do veículo
        analise_detalhada = analisar_veiculo_detalhado(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Comparação com veículos similares
        comparacao_similares = comparar_com_similares(veiculo, admin_id, data_inicio, data_fim)
        
        # Evolução temporal
        evolucao_temporal = evolucao_produtividade_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Análise por obra
        analise_por_obra = produtividade_por_obra(veiculo_id, admin_id, data_inicio, data_fim)
        
        return render_template('relatorios/produtividade/veiculo_detalhado.html',
                             veiculo=veiculo,
                             analise_detalhada=analise_detalhada,
                             comparacao_similares=comparacao_similares,
                             evolucao_temporal=evolucao_temporal,
                             analise_por_obra=analise_por_obra,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"Erro na análise detalhada: {e}")
        flash('Erro ao carregar análise detalhada', 'danger')
        return redirect(url_for('relatorios_produtividade.index_produtividade'))

def analisar_veiculo_detalhado(veiculo_id, admin_id, data_inicio, data_fim):
    """Análise detalhada de um veículo específico"""
    
    try:
        # Dados básicos do período
        dados = db.session.query(
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_ativo'),
            func.max(UsoVeiculo.km_rodado).label('maior_km_dia'),
            func.min(UsoVeiculo.km_rodado).label('menor_km_dia'),
            func.avg(UsoVeiculo.km_rodado).label('media_km_uso')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        # Custos do período
        custo_total = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.veiculo_id == veiculo_id,
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).scalar() or 0
        
        if not dados or not dados.km_total:
            return {'erro': 'Nenhum dado de uso encontrado para o período'}
        
        dias_periodo = (data_fim - data_inicio).days + 1
        
        return {
            'km_total': float(dados.km_total),
            'horas_total': float(dados.horas_total or 0),
            'total_usos': dados.total_usos,
            'dias_ativo': dados.dias_ativo,
            'dias_periodo': dias_periodo,
            'custo_total': float(custo_total),
            'km_por_dia': round(float(dados.km_total) / max(dados.dias_ativo, 1), 2),
            'km_por_uso': round(float(dados.media_km_uso or 0), 2),
            'custo_por_km': round(float(custo_total) / max(float(dados.km_total), 1), 2),
            'eficiencia_temporal': round(float(dados.km_total) / max(float(dados.horas_total), 1), 2),
            'utilizacao_periodo': round((dados.dias_ativo / dias_periodo) * 100, 2),
            'maior_km_dia': float(dados.maior_km_dia or 0),
            'menor_km_dia': float(dados.menor_km_dia or 0)
        }
        
    except Exception as e:
        logger.error(f"Erro na análise detalhada: {e}")
        return {'erro': 'Erro ao calcular análise detalhada'}

def comparar_com_similares(veiculo, admin_id, data_inicio, data_fim):
    """Compara veículo com outros similares (mesmo tipo)"""
    
    try:
        # Buscar veículos similares
        veiculos_similares = db.session.query(
            Veiculo.id,
            Veiculo.placa,
            func.coalesce(func.sum(UsoVeiculo.km_rodado), 0).label('km_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.coalesce(func.sum(CustoVeiculo.valor), 0).label('custo_total')
        ).select_from(Veiculo)\
        .outerjoin(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == Veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .outerjoin(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == Veiculo.id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .filter(
            Veiculo.admin_id == admin_id,
            Veiculo.tipo == veiculo.tipo,
            Veiculo.ativo == True,
            Veiculo.id != veiculo.id
        ).group_by(Veiculo.id, Veiculo.placa).all()
        
        # Dados do veículo atual
        dados_atual = db.session.query(
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(CustoVeiculo.valor).label('custo_total')
        ).select_from(UsoVeiculo)\
        .outerjoin(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == UsoVeiculo.veiculo_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .filter(
            UsoVeiculo.veiculo_id == veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        if not dados_atual or not dados_atual.km_total:
            return {'erro': 'Sem dados do veículo atual'}
        
        # Calcular médias dos similares
        if veiculos_similares:
            km_similares = [float(v.km_total) for v in veiculos_similares if v.km_total > 0]
            custo_similares = [float(v.custo_total) for v in veiculos_similares if v.custo_total > 0]
            
            media_km = mean(km_similares) if km_similares else 0
            media_custo = mean(custo_similares) if custo_similares else 0
            
            # Posição do veículo atual
            km_atual = float(dados_atual.km_total)
            posicao = sum(1 for km in km_similares if km < km_atual) + 1
            total_similares = len(km_similares) + 1
            
            return {
                'total_similares': total_similares,
                'posicao': posicao,
                'percentil': round((posicao / total_similares) * 100, 1),
                'km_atual': km_atual,
                'media_km_similares': round(media_km, 2),
                'diferenca_media': round(((km_atual - media_km) / max(media_km, 1)) * 100, 2),
                'custo_atual': float(dados_atual.custo_total or 0),
                'media_custo_similares': round(media_custo, 2)
            }
        else:
            return {'erro': 'Nenhum veículo similar encontrado'}
        
    except Exception as e:
        logger.error(f"Erro na comparação com similares: {e}")
        return {'erro': 'Erro ao comparar com similares'}

def evolucao_produtividade_veiculo(veiculo_id, admin_id, data_inicio, data_fim):
    """Evolução da produtividade ao longo do tempo"""
    
    try:
        # Dados semanais
        dados_semanais = db.session.query(
            extract('week', UsoVeiculo.data_uso).label('semana'),
            extract('year', UsoVeiculo.data_uso).label('ano'),
            func.sum(UsoVeiculo.km_rodado).label('km_semana'),
            func.sum(UsoVeiculo.horas_uso).label('horas_semana'),
            func.count(UsoVeiculo.id).label('usos_semana')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(
            extract('week', UsoVeiculo.data_uso),
            extract('year', UsoVeiculo.data_uso)
        ).order_by('ano', 'semana').all()
        
        evolucao = []
        for d in dados_semanais:
            eficiencia = float(d.km_semana) / max(float(d.horas_semana), 1)
            evolucao.append({
                'periodo': f"{int(d.ano)}-W{int(d.semana)}",
                'km_semana': float(d.km_semana),
                'horas_semana': float(d.horas_semana or 0),
                'usos_semana': d.usos_semana,
                'eficiencia': round(eficiencia, 2)
            })
        
        return evolucao
        
    except Exception as e:
        logger.error(f"Erro na evolução temporal: {e}")
        return []

def produtividade_por_obra(veiculo_id, admin_id, data_inicio, data_fim):
    """Análise de produtividade por obra"""
    
    try:
        dados = db.session.query(
            Obra.nome,
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_obra')
        ).join(AlocacaoVeiculo, AlocacaoVeiculo.obra_id == Obra.id)\
        .join(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == AlocacaoVeiculo.veiculo_id,
            UsoVeiculo.data_uso >= AlocacaoVeiculo.data_inicio,
            or_(
                AlocacaoVeiculo.data_fim.is_(None),
                UsoVeiculo.data_uso <= AlocacaoVeiculo.data_fim
            )
        ))\
        .filter(
            AlocacaoVeiculo.veiculo_id == veiculo_id,
            AlocacaoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(Obra.nome).all()
        
        por_obra = []
        for d in dados:
            km_por_dia = float(d.km_total) / max(d.dias_obra, 1)
            por_obra.append({
                'obra': d.nome,
                'km_total': float(d.km_total),
                'total_usos': d.total_usos,
                'dias_obra': d.dias_obra,
                'km_por_dia': round(km_por_dia, 2)
            })
        
        return sorted(por_obra, key=lambda x: x['km_total'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro na análise por obra: {e}")
        return []

# ===== APIS E EXPORTAÇÃO =====

@produtividade_bp.route('/api/dados-produtividade')
@login_required
@admin_required
def api_dados_produtividade():
    """API para dados de produtividade via AJAX"""
    admin_id = get_admin_id()
    
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo', 'geral')
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        if tipo == 'ranking':
            dados = calcular_ranking_veiculos(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'categoria':
            dados = comparativo_por_categoria(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'temporal':
            dados = analise_tendencia_uso(admin_id, data_inicio_obj, data_fim_obj)
        else:
            dados = calcular_produtividade_geral(admin_id, data_inicio_obj, data_fim_obj)
        
        return jsonify({
            'success': True,
            'dados': dados
        })
        
    except Exception as e:
        logger.error(f"Erro na API de produtividade: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500