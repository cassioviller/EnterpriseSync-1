"""
RELATÓRIOS FINANCEIROS AVANÇADOS - SIGE v8.0
Sistema completo de análise financeira da frota

Funcionalidades:
- Custo total de propriedade (TCO) por veículo
- Breakdown de custos por categoria
- Análise de depreciação e valor residual
- ROI por veículo/obra
- Previsão de custos futuros
- Análise de eficiência financeira
- Comparativo de custos entre veículos
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
import pandas as pd
import numpy as np
from io import BytesIO

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
financeiros_bp = Blueprint('relatorios_financeiros', __name__, url_prefix='/relatorios/financeiros')

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

# ===== DASHBOARD FINANCEIRO PRINCIPAL =====

@financeiros_bp.route('/')
@login_required
@admin_required
def dashboard_financeiro():
    """Dashboard principal de análise financeira"""
    admin_id = get_admin_id()
    
    # Período padrão (último ano)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=365)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    veiculo_id = request.args.get('veiculo_id', type=int)
    categoria_custo = request.args.get('categoria_custo')
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # === INDICADORES FINANCEIROS PRINCIPAIS ===
        indicadores_principais = calcular_indicadores_financeiros(admin_id, data_inicio, data_fim)
        
        # === TCO POR VEÍCULO ===
        tco_veiculos = calcular_tco_veiculos(admin_id, data_inicio, data_fim, veiculo_id)
        
        # === ANÁLISE DE CUSTOS POR CATEGORIA ===
        custos_categoria = analisar_custos_por_categoria(admin_id, data_inicio, data_fim)
        
        # === EVOLUÇÃO FINANCEIRA ===
        evolucao_financeira = analisar_evolucao_financeira(admin_id, data_inicio, data_fim)
        
        # === ROI POR OBRA ===
        roi_obras = calcular_roi_por_obra(admin_id, data_inicio, data_fim)
        
        # === EFICIÊNCIA FINANCEIRA ===
        eficiencia_financeira = analisar_eficiencia_financeira(admin_id, data_inicio, data_fim)
        
        # === PREVISÕES ===
        previsoes = gerar_previsoes_financeiras(admin_id, data_inicio, data_fim)
        
        # === BENCHMARKS ===
        benchmarks = calcular_benchmarks_financeiros(admin_id, data_inicio, data_fim)
        
        # === DADOS PARA FILTROS ===
        veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        categorias = obter_categorias_custo(admin_id)
        
        return render_template('relatorios/financeiros/dashboard.html',
                             indicadores_principais=indicadores_principais,
                             tco_veiculos=tco_veiculos,
                             custos_categoria=custos_categoria,
                             evolucao_financeira=evolucao_financeira,
                             roi_obras=roi_obras,
                             eficiencia_financeira=eficiencia_financeira,
                             previsoes=previsoes,
                             benchmarks=benchmarks,
                             veiculos=veiculos,
                             obras=obras,
                             categorias=categorias,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             filtros={
                                 'veiculo_id': veiculo_id,
                                 'categoria_custo': categoria_custo
                             })
        
    except Exception as e:
        logger.error(f"Erro no dashboard financeiro: {e}")
        flash('Erro ao carregar dashboard financeiro', 'danger')
        return redirect(url_for('main.dashboard'))

def calcular_indicadores_financeiros(admin_id, data_inicio, data_fim):
    """Calcula indicadores financeiros principais"""
    
    try:
        # Custos totais por categoria
        custos_periodo = db.session.query(
            CustoVeiculo.tipo_custo,
            func.sum(CustoVeiculo.valor).label('total'),
            func.count(CustoVeiculo.id).label('registros'),
            func.avg(CustoVeiculo.valor).label('media')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(CustoVeiculo.tipo_custo).all()
        
        # Totais gerais
        custo_total = sum(float(c.total or 0) for c in custos_periodo)
        registros_total = sum(c.registros for c in custos_periodo)
        
        # KM rodado no período
        km_total = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).scalar() or 0
        
        # Número de veículos ativos
        veiculos_ativos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).count()
        
        # Valor do contrato das obras (para cálculo de ROI)
        valor_contratos = db.session.query(func.sum(Obra.valor_contrato)).filter(
            Obra.admin_id == admin_id,
            Obra.ativo == True
        ).scalar() or 0
        
        # Calcular indicadores derivados
        custo_por_km = custo_total / max(float(km_total), 1) if km_total > 0 else 0
        custo_por_veiculo = custo_total / max(veiculos_ativos, 1)
        dias_periodo = (data_fim - data_inicio).days + 1
        custo_por_dia = custo_total / max(dias_periodo, 1)
        
        # ROI simplificado
        roi_geral = 0
        if custo_total > 0 and valor_contratos > 0:
            roi_geral = ((valor_contratos - custo_total) / custo_total) * 100
        
        # Breakdown por categoria
        custos_por_categoria = {}
        for c in custos_periodo:
            custos_por_categoria[c.tipo_custo] = {
                'total': float(c.total or 0),
                'percentual': (float(c.total or 0) / max(custo_total, 1)) * 100,
                'registros': c.registros,
                'media': float(c.media or 0)
            }
        
        return {
            'custo_total': custo_total,
            'registros_total': registros_total,
            'km_total': float(km_total),
            'veiculos_ativos': veiculos_ativos,
            'custo_por_km': round(custo_por_km, 2),
            'custo_por_veiculo': round(custo_por_veiculo, 2),
            'custo_por_dia': round(custo_por_dia, 2),
            'roi_geral': round(roi_geral, 2),
            'dias_periodo': dias_periodo,
            'custos_por_categoria': custos_por_categoria
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular indicadores financeiros: {e}")
        return {}

def calcular_tco_veiculos(admin_id, data_inicio, data_fim, veiculo_filtro=None):
    """Calcula TCO (Total Cost of Ownership) por veículo"""
    
    try:
        # Query base para custos por veículo
        query = db.session.query(
            Veiculo.id,
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            Veiculo.tipo,
            Veiculo.ano,
            func.sum(CustoVeiculo.valor).label('custo_total'),
            func.sum(case([(CustoVeiculo.tipo_custo == 'combustivel', CustoVeiculo.valor)], else_=0)).label('custo_combustivel'),
            func.sum(case([(CustoVeiculo.tipo_custo == 'manutencao', CustoVeiculo.valor)], else_=0)).label('custo_manutencao'),
            func.sum(case([(CustoVeiculo.tipo_custo == 'seguro', CustoVeiculo.valor)], else_=0)).label('custo_seguro'),
            func.sum(case([(CustoVeiculo.tipo_custo == 'ipva', CustoVeiculo.valor)], else_=0)).label('custo_ipva'),
            func.sum(case([(CustoVeiculo.tipo_custo == 'multa', CustoVeiculo.valor)], else_=0)).label('custo_multa'),
            func.sum(case([(CustoVeiculo.tipo_custo == 'outros', CustoVeiculo.valor)], else_=0)).label('custo_outros'),
            func.count(CustoVeiculo.id).label('total_registros')
        ).select_from(Veiculo)\
        .outerjoin(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == Veiculo.id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .filter(Veiculo.admin_id == admin_id, Veiculo.ativo == True)
        
        if veiculo_filtro:
            query = query.filter(Veiculo.id == veiculo_filtro)
        
        dados_custos = query.group_by(
            Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo, 
            Veiculo.tipo, Veiculo.ano
        ).all()
        
        # Obter dados de uso para cada veículo
        uso_veiculos = db.session.query(
            Veiculo.id,
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_uso')
        ).select_from(Veiculo)\
        .outerjoin(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == Veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .filter(Veiculo.admin_id == admin_id)\
        .group_by(Veiculo.id).all()
        
        # Criar dicionário de uso
        uso_dict = {u.id: {'km_total': float(u.km_total or 0), 'dias_uso': u.dias_uso or 0} for u in uso_veiculos}
        
        tco_lista = []
        for v in dados_custos:
            uso_data = uso_dict.get(v.id, {'km_total': 0, 'dias_uso': 0})
            
            # Calcular TCO e métricas
            custo_total = float(v.custo_total or 0)
            km_total = uso_data['km_total']
            dias_uso = uso_data['dias_uso']
            
            custo_por_km = custo_total / max(km_total, 1) if km_total > 0 else 0
            custo_por_dia = custo_total / max(dias_uso, 1) if dias_uso > 0 else 0
            
            # Calcular depreciação estimada (simplificada)
            idade_veiculo = date.today().year - (v.ano or date.today().year)
            depreciacao_anual = custo_total * 0.15  # 15% ao ano (estimativa)
            valor_residual = max(0, custo_total - (depreciacao_anual * idade_veiculo))
            
            # Score de eficiência financeira
            score_eficiencia = calcular_score_eficiencia_financeira(
                custo_por_km, dias_uso, custo_total, km_total
            )
            
            tco_lista.append({
                'veiculo_id': v.id,
                'placa': v.placa,
                'marca': v.marca,
                'modelo': v.modelo,
                'tipo': v.tipo,
                'ano': v.ano,
                'custo_total': custo_total,
                'custo_combustivel': float(v.custo_combustivel or 0),
                'custo_manutencao': float(v.custo_manutencao or 0),
                'custo_seguro': float(v.custo_seguro or 0),
                'custo_ipva': float(v.custo_ipva or 0),
                'custo_multa': float(v.custo_multa or 0),
                'custo_outros': float(v.custo_outros or 0),
                'total_registros': v.total_registros,
                'km_total': km_total,
                'dias_uso': dias_uso,
                'custo_por_km': round(custo_por_km, 2),
                'custo_por_dia': round(custo_por_dia, 2),
                'idade_veiculo': idade_veiculo,
                'valor_residual_estimado': round(valor_residual, 2),
                'score_eficiencia': round(score_eficiencia, 1)
            })
        
        return sorted(tco_lista, key=lambda x: x['custo_total'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro ao calcular TCO: {e}")
        return []

def analisar_custos_por_categoria(admin_id, data_inicio, data_fim):
    """Análise detalhada de custos por categoria"""
    
    try:
        # Custos por categoria e mês
        custos_categoria_mes = db.session.query(
            CustoVeiculo.tipo_custo,
            extract('year', CustoVeiculo.data_custo).label('ano'),
            extract('month', CustoVeiculo.data_custo).label('mes'),
            func.sum(CustoVeiculo.valor).label('total'),
            func.count(CustoVeiculo.id).label('registros'),
            func.avg(CustoVeiculo.valor).label('media')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(
            CustoVeiculo.tipo_custo,
            extract('year', CustoVeiculo.data_custo),
            extract('month', CustoVeiculo.data_custo)
        ).order_by('ano', 'mes').all()
        
        # Custos por categoria e veículo
        custos_categoria_veiculo = db.session.query(
            CustoVeiculo.tipo_custo,
            Veiculo.placa,
            func.sum(CustoVeiculo.valor).label('total'),
            func.count(CustoVeiculo.id).label('registros')
        ).join(Veiculo)\
        .filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(CustoVeiculo.tipo_custo, Veiculo.placa)\
        .order_by(CustoVeiculo.tipo_custo, desc('total')).all()
        
        # Organizar dados por categoria
        analise_categoria = defaultdict(lambda: {
            'evolucao_mensal': [],
            'top_veiculos': [],
            'total_categoria': 0,
            'registros_categoria': 0
        })
        
        # Evolução mensal por categoria
        for c in custos_categoria_mes:
            periodo = f"{int(c.ano)}-{int(c.mes):02d}"
            analise_categoria[c.tipo_custo]['evolucao_mensal'].append({
                'periodo': periodo,
                'total': float(c.total or 0),
                'registros': c.registros,
                'media': float(c.media or 0)
            })
            analise_categoria[c.tipo_custo]['total_categoria'] += float(c.total or 0)
            analise_categoria[c.tipo_custo]['registros_categoria'] += c.registros
        
        # Top veículos por categoria
        for c in custos_categoria_veiculo:
            if len(analise_categoria[c.tipo_custo]['top_veiculos']) < 10:
                analise_categoria[c.tipo_custo]['top_veiculos'].append({
                    'placa': c.placa,
                    'total': float(c.total or 0),
                    'registros': c.registros
                })
        
        return dict(analise_categoria)
        
    except Exception as e:
        logger.error(f"Erro na análise por categoria: {e}")
        return {}

def analisar_evolucao_financeira(admin_id, data_inicio, data_fim):
    """Análise da evolução financeira ao longo do tempo"""
    
    try:
        # Evolução mensal de custos
        evolucao_mensal = db.session.query(
            extract('year', CustoVeiculo.data_custo).label('ano'),
            extract('month', CustoVeiculo.data_custo).label('mes'),
            func.sum(CustoVeiculo.valor).label('custo_total'),
            func.count(CustoVeiculo.id).label('total_registros'),
            func.count(func.distinct(CustoVeiculo.veiculo_id)).label('veiculos_com_custo')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(
            extract('year', CustoVeiculo.data_custo),
            extract('month', CustoVeiculo.data_custo)
        ).order_by('ano', 'mes').all()
        
        # Evolução de KM rodado
        evolucao_km = db.session.query(
            extract('year', UsoVeiculo.data_uso).label('ano'),
            extract('month', UsoVeiculo.data_uso).label('mes'),
            func.sum(UsoVeiculo.km_rodado).label('km_total')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(
            extract('year', UsoVeiculo.data_uso),
            extract('month', UsoVeiculo.data_uso)
        ).order_by('ano', 'mes').all()
        
        # Combinar dados
        evolucao_financeira = []
        km_dict = {f"{int(k.ano)}-{int(k.mes):02d}": float(k.km_total or 0) for k in evolucao_km}
        
        for e in evolucao_mensal:
            periodo = f"{int(e.ano)}-{int(e.mes):02d}"
            km_periodo = km_dict.get(periodo, 0)
            custo_total = float(e.custo_total or 0)
            custo_por_km = custo_total / max(km_periodo, 1) if km_periodo > 0 else 0
            
            evolucao_financeira.append({
                'periodo': periodo,
                'custo_total': custo_total,
                'km_total': km_periodo,
                'custo_por_km': round(custo_por_km, 2),
                'total_registros': e.total_registros,
                'veiculos_com_custo': e.veiculos_com_custo
            })
        
        # Calcular tendências
        if len(evolucao_financeira) >= 2:
            custos_recentes = [e['custo_total'] for e in evolucao_financeira[-3:]]
            custos_anteriores = [e['custo_total'] for e in evolucao_financeira[:-3]]
            
            if custos_anteriores and custos_recentes:
                media_recente = sum(custos_recentes) / len(custos_recentes)
                media_anterior = sum(custos_anteriores) / len(custos_anteriores)
                tendencia = ((media_recente - media_anterior) / max(media_anterior, 1)) * 100
            else:
                tendencia = 0
        else:
            tendencia = 0
        
        return {
            'evolucao_mensal': evolucao_financeira,
            'tendencia': round(tendencia, 2)
        }
        
    except Exception as e:
        logger.error(f"Erro na evolução financeira: {e}")
        return {'evolucao_mensal': [], 'tendencia': 0}

def calcular_roi_por_obra(admin_id, data_inicio, data_fim):
    """Calcula ROI (Return on Investment) por obra"""
    
    try:
        # Custos por obra (através das alocações)
        custos_obra = db.session.query(
            Obra.id,
            Obra.nome,
            Obra.valor_contrato,
            func.sum(CustoVeiculo.valor).label('custo_veiculos')
        ).select_from(Obra)\
        .join(AlocacaoVeiculo, AlocacaoVeiculo.obra_id == Obra.id)\
        .join(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == AlocacaoVeiculo.veiculo_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .filter(Obra.admin_id == admin_id, Obra.ativo == True)\
        .group_by(Obra.id, Obra.nome, Obra.valor_contrato).all()
        
        roi_obras = []
        for obra in custos_obra:
            valor_contrato = float(obra.valor_contrato or 0)
            custo_veiculos = float(obra.custo_veiculos or 0)
            
            if custo_veiculos > 0:
                roi = ((valor_contrato - custo_veiculos) / custo_veiculos) * 100
                margem = ((valor_contrato - custo_veiculos) / max(valor_contrato, 1)) * 100
            else:
                roi = 0
                margem = 0
            
            roi_obras.append({
                'obra_id': obra.id,
                'nome': obra.nome,
                'valor_contrato': valor_contrato,
                'custo_veiculos': custo_veiculos,
                'roi': round(roi, 2),
                'margem': round(margem, 2),
                'lucro_estimado': round(valor_contrato - custo_veiculos, 2)
            })
        
        return sorted(roi_obras, key=lambda x: x['roi'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro no cálculo de ROI: {e}")
        return []

def analisar_eficiencia_financeira(admin_id, data_inicio, data_fim):
    """Análise de eficiência financeira da frota"""
    
    try:
        # Eficiência por tipo de veículo
        eficiencia_tipo = db.session.query(
            Veiculo.tipo,
            func.count(func.distinct(Veiculo.id)).label('total_veiculos'),
            func.sum(CustoVeiculo.valor).label('custo_total'),
            func.sum(UsoVeiculo.km_rodado).label('km_total')
        ).select_from(Veiculo)\
        .outerjoin(CustoVeiculo, and_(
            CustoVeiculo.veiculo_id == Veiculo.id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ))\
        .outerjoin(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == Veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .filter(Veiculo.admin_id == admin_id, Veiculo.ativo == True)\
        .group_by(Veiculo.tipo).all()
        
        # Benchmark de custos
        custos_por_km = []
        for dados in eficiencia_tipo:
            custo_total = float(dados.custo_total or 0)
            km_total = float(dados.km_total or 0)
            custo_por_km = custo_total / max(km_total, 1) if km_total > 0 else 0
            
            if custo_por_km > 0:
                custos_por_km.append(custo_por_km)
        
        # Calcular percentis
        if custos_por_km:
            custos_sorted = sorted(custos_por_km)
            n = len(custos_sorted)
            p25 = custos_sorted[int(n * 0.25)] if n > 0 else 0
            p50 = custos_sorted[int(n * 0.50)] if n > 0 else 0
            p75 = custos_sorted[int(n * 0.75)] if n > 0 else 0
        else:
            p25 = p50 = p75 = 0
        
        eficiencia_lista = []
        for dados in eficiencia_tipo:
            custo_total = float(dados.custo_total or 0)
            km_total = float(dados.km_total or 0)
            custo_por_km = custo_total / max(km_total, 1) if km_total > 0 else 0
            custo_por_veiculo = custo_total / max(dados.total_veiculos, 1)
            
            # Classificação de eficiência
            if custo_por_km <= p25:
                eficiencia_classe = 'Excelente'
            elif custo_por_km <= p50:
                eficiencia_classe = 'Boa'
            elif custo_por_km <= p75:
                eficiencia_classe = 'Regular'
            else:
                eficiencia_classe = 'Baixa'
            
            eficiencia_lista.append({
                'tipo': dados.tipo,
                'total_veiculos': dados.total_veiculos,
                'custo_total': custo_total,
                'km_total': km_total,
                'custo_por_km': round(custo_por_km, 2),
                'custo_por_veiculo': round(custo_por_veiculo, 2),
                'eficiencia_classe': eficiencia_classe
            })
        
        return {
            'eficiencia_por_tipo': eficiencia_lista,
            'benchmarks': {
                'p25': round(p25, 2),
                'p50': round(p50, 2),
                'p75': round(p75, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Erro na análise de eficiência: {e}")
        return {'eficiencia_por_tipo': [], 'benchmarks': {}}

def gerar_previsoes_financeiras(admin_id, data_inicio, data_fim):
    """Gera previsões financeiras baseadas em tendências"""
    
    try:
        # Dados históricos mensais (últimos 12 meses antes do período)
        data_historica_inicio = data_inicio - timedelta(days=365)
        
        dados_historicos = db.session.query(
            extract('year', CustoVeiculo.data_custo).label('ano'),
            extract('month', CustoVeiculo.data_custo).label('mes'),
            func.sum(CustoVeiculo.valor).label('custo_total')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_historica_inicio,
            CustoVeiculo.data_custo < data_inicio
        ).group_by(
            extract('year', CustoVeiculo.data_custo),
            extract('month', CustoVeiculo.data_custo)
        ).order_by('ano', 'mes').all()
        
        if len(dados_historicos) < 3:
            return {'erro': 'Dados históricos insuficientes para previsão'}
        
        # Calcular tendência linear simples
        custos_historicos = [float(d.custo_total or 0) for d in dados_historicos]
        
        # Usar numpy para regressão linear simples
        x = np.arange(len(custos_historicos))
        y = np.array(custos_historicos)
        
        # Coeficientes da regressão linear
        coeficientes = np.polyfit(x, y, 1)
        tendencia_mensal = coeficientes[0]  # Inclinação
        
        # Projeção para os próximos 6 meses
        proximo_mes = data_fim + timedelta(days=32)
        proximo_mes = proximo_mes.replace(day=1)
        
        previsoes_mensais = []
        for i in range(6):
            mes_projecao = proximo_mes + timedelta(days=32*i)
            mes_projecao = mes_projecao.replace(day=1)
            
            # Previsão baseada na tendência
            indice_futuro = len(custos_historicos) + i
            custo_previsto = max(0, coeficientes[1] + (tendencia_mensal * indice_futuro))
            
            previsoes_mensais.append({
                'periodo': mes_projecao.strftime('%Y-%m'),
                'custo_previsto': round(custo_previsto, 2),
                'confianca': max(0, 100 - (i * 15))  # Confiança decresce com tempo
            })
        
        # Análise de sazonalidade simples
        if len(dados_historicos) >= 12:
            # Calcular média por mês do ano
            sazonalidade = defaultdict(list)
            for d in dados_historicos:
                mes = int(d.mes)
                sazonalidade[mes].append(float(d.custo_total or 0))
            
            fatores_sazonais = {}
            for mes in range(1, 13):
                if mes in sazonalidade:
                    fatores_sazonais[mes] = np.mean(sazonalidade[mes])
                else:
                    fatores_sazonais[mes] = np.mean(custos_historicos)
        else:
            fatores_sazonais = {i: np.mean(custos_historicos) for i in range(1, 13)}
        
        return {
            'previsoes_mensais': previsoes_mensais,
            'tendencia_mensal': round(tendencia_mensal, 2),
            'fatores_sazonais': {k: round(v, 2) for k, v in fatores_sazonais.items()},
            'custo_medio_historico': round(np.mean(custos_historicos), 2)
        }
        
    except Exception as e:
        logger.error(f"Erro nas previsões financeiras: {e}")
        return {'erro': 'Erro ao gerar previsões'}

def calcular_benchmarks_financeiros(admin_id, data_inicio, data_fim):
    """Calcula benchmarks financeiros da frota"""
    
    try:
        # Benchmarks gerais
        custo_total = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).scalar() or 0
        
        km_total = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).scalar() or 0
        
        # Benchmarks por categoria de custo
        benchmarks_categoria = db.session.query(
            CustoVeiculo.tipo_custo,
            func.sum(CustoVeiculo.valor).label('total'),
            func.avg(CustoVeiculo.valor).label('media'),
            func.min(CustoVeiculo.valor).label('minimo'),
            func.max(CustoVeiculo.valor).label('maximo')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(CustoVeiculo.tipo_custo).all()
        
        # Benchmarks por tipo de veículo
        benchmarks_veiculo = db.session.query(
            Veiculo.tipo,
            func.avg(CustoVeiculo.valor).label('custo_medio'),
            func.sum(CustoVeiculo.valor).label('custo_total'),
            func.count(func.distinct(Veiculo.id)).label('total_veiculos')
        ).join(CustoVeiculo)\
        .filter(
            Veiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(Veiculo.tipo).all()
        
        # Formatação dos benchmarks
        categoria_benchmarks = {}
        for b in benchmarks_categoria:
            categoria_benchmarks[b.tipo_custo] = {
                'total': float(b.total or 0),
                'media': float(b.media or 0),
                'minimo': float(b.minimo or 0),
                'maximo': float(b.maximo or 0),
                'percentual': (float(b.total or 0) / max(float(custo_total), 1)) * 100
            }
        
        veiculo_benchmarks = {}
        for b in benchmarks_veiculo:
            veiculo_benchmarks[b.tipo] = {
                'custo_medio': float(b.custo_medio or 0),
                'custo_total': float(b.custo_total or 0),
                'total_veiculos': b.total_veiculos
            }
        
        return {
            'custo_total_geral': float(custo_total),
            'km_total_geral': float(km_total),
            'custo_por_km_geral': round(float(custo_total) / max(float(km_total), 1), 2),
            'categoria_benchmarks': categoria_benchmarks,
            'veiculo_benchmarks': veiculo_benchmarks
        }
        
    except Exception as e:
        logger.error(f"Erro nos benchmarks: {e}")
        return {}

# ===== RELATÓRIOS ESPECÍFICOS =====

@financeiros_bp.route('/tco/<int:veiculo_id>')
@login_required
@admin_required
def relatorio_tco_detalhado(veiculo_id):
    """Relatório detalhado de TCO de um veículo específico"""
    admin_id = get_admin_id()
    
    veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=admin_id).first_or_404()
    
    # Período padrão (desde a compra ou últimos 2 anos)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=730)  # 2 anos
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # TCO detalhado do veículo
        tco_detalhado = calcular_tco_veiculo_detalhado(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Evolução de custos
        evolucao_custos = analisar_evolucao_custos_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Comparação com similares
        comparacao_similares = comparar_tco_similares(veiculo, admin_id, data_inicio, data_fim)
        
        # Projeções
        projecoes_veiculo = projetar_custos_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        return render_template('relatorios/financeiros/tco_detalhado.html',
                             veiculo=veiculo,
                             tco_detalhado=tco_detalhado,
                             evolucao_custos=evolucao_custos,
                             comparacao_similares=comparacao_similares,
                             projecoes_veiculo=projecoes_veiculo,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"Erro no TCO detalhado: {e}")
        flash('Erro ao carregar TCO detalhado', 'danger')
        return redirect(url_for('relatorios_financeiros.dashboard_financeiro'))

def calcular_tco_veiculo_detalhado(veiculo_id, admin_id, data_inicio, data_fim):
    """Calcula TCO detalhado de um veículo específico"""
    
    try:
        # Custos detalhados por categoria e data
        custos_detalhados = db.session.query(CustoVeiculo)\
        .filter(
            CustoVeiculo.veiculo_id == veiculo_id,
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).order_by(CustoVeiculo.data_custo.desc()).all()
        
        # Uso no período
        uso_periodo = db.session.query(
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_uso'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        # Organizar custos por categoria
        custos_por_categoria = defaultdict(list)
        custo_total = 0
        
        for custo in custos_detalhados:
            custos_por_categoria[custo.tipo_custo].append({
                'id': custo.id,
                'data': custo.data_custo.strftime('%d/%m/%Y'),
                'valor': float(custo.valor),
                'descricao': custo.descricao,
                'km_atual': custo.km_atual
            })
            custo_total += float(custo.valor)
        
        # Resumo por categoria
        resumo_categorias = {}
        for categoria, custos in custos_por_categoria.items():
            total_categoria = sum(c['valor'] for c in custos)
            resumo_categorias[categoria] = {
                'total': total_categoria,
                'registros': len(custos),
                'media': total_categoria / len(custos) if custos else 0,
                'percentual': (total_categoria / max(custo_total, 1)) * 100,
                'custos': custos
            }
        
        # Métricas de eficiência
        km_total = float(uso_periodo.km_total or 0)
        dias_uso = uso_periodo.dias_uso or 0
        horas_total = float(uso_periodo.horas_total or 0)
        
        custo_por_km = custo_total / max(km_total, 1) if km_total > 0 else 0
        custo_por_dia = custo_total / max(dias_uso, 1) if dias_uso > 0 else 0
        custo_por_hora = custo_total / max(horas_total, 1) if horas_total > 0 else 0
        
        return {
            'custo_total': custo_total,
            'km_total': km_total,
            'dias_uso': dias_uso,
            'horas_total': horas_total,
            'custo_por_km': round(custo_por_km, 2),
            'custo_por_dia': round(custo_por_dia, 2),
            'custo_por_hora': round(custo_por_hora, 2),
            'resumo_categorias': resumo_categorias,
            'total_registros': len(custos_detalhados)
        }
        
    except Exception as e:
        logger.error(f"Erro no TCO detalhado: {e}")
        return {'erro': 'Erro ao calcular TCO detalhado'}

# ===== UTILITÁRIOS =====

def calcular_score_eficiencia_financeira(custo_por_km, dias_uso, custo_total, km_total):
    """Calcula score de eficiência financeira (0-100)"""
    
    if custo_per_km == 0 and km_total == 0:
        return 0
    
    # Normalizar métricas (valores arbitrários ajustáveis)
    score_custo = max(0, 100 - (custo_per_km * 10))  # Menos custo por km = melhor
    score_uso = min(100, (km_total / 1000) * 100)  # Mais km = melhor utilização
    score_consistencia = min(100, (dias_uso / 30) * 100)  # Mais dias de uso = melhor
    
    # Média ponderada
    score_final = (score_custo * 0.5 + score_uso * 0.3 + score_consistencia * 0.2)
    return max(0, min(100, score_final))

def obter_categorias_custo(admin_id):
    """Obtém categorias de custo únicas"""
    
    try:
        categorias = db.session.query(CustoVeiculo.tipo_custo)\
        .filter(CustoVeiculo.admin_id == admin_id)\
        .distinct().all()
        
        return [c.tipo_custo for c in categorias if c.tipo_custo]
        
    except Exception as e:
        logger.error(f"Erro ao obter categorias: {e}")
        return []

# ===== APIS =====

@financeiros_bp.route('/api/dados-financeiros')
@login_required
@admin_required
def api_dados_financeiros():
    """API para dados financeiros via AJAX"""
    admin_id = get_admin_id()
    
    tipo = request.args.get('tipo', 'indicadores')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    veiculo_id = request.args.get('veiculo_id', type=int)
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        if tipo == 'tco':
            dados = calcular_tco_veiculos(admin_id, data_inicio_obj, data_fim_obj, veiculo_id)
        elif tipo == 'categoria':
            dados = analisar_custos_por_categoria(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'evolucao':
            dados = analisar_evolucao_financeira(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'roi':
            dados = calcular_roi_por_obra(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'previsoes':
            dados = gerar_previsoes_financeiras(admin_id, data_inicio_obj, data_fim_obj)
        else:
            dados = calcular_indicadores_financeiros(admin_id, data_inicio_obj, data_fim_obj)
        
        return jsonify({
            'success': True,
            'dados': dados
        })
        
    except Exception as e:
        logger.error(f"Erro na API financeira: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500