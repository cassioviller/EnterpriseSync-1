"""
DASHBOARDS ESPECÍFICOS - SIGE v8.0
Dashboards especializados para aspectos específicos da gestão de frota

Funcionalidades:
- Dashboard de Manutenção (programadas, corretivas, custos)
- Dashboard de Combustível (consumo, eficiência, gastos)
- Dashboard de Obras (veículos por projeto, custos por obra)
- Dashboard de Frota (status, localização, disponibilidade)
- Dashboard de Segurança (multas, acidentes, documentos)
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

# Importar modelos
from models import (
    db, Veiculo, CustoVeiculo, UsoVeiculo, AlocacaoVeiculo, ManutencaoVeiculo,
    AlertaVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
dashboards_bp = Blueprint('dashboards_especificos', __name__, url_prefix='/dashboards/especificos')

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

# ===== DASHBOARD DE MANUTENÇÃO =====

@dashboards_bp.route('/manutencao')
@login_required
@admin_required
def dashboard_manutencao():
    """Dashboard especializado em manutenção"""
    admin_id = get_admin_id()
    
    # Período padrão (últimos 6 meses)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=180)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    veiculo_id = request.args.get('veiculo_id', type=int)
    categoria = request.args.get('categoria')
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # === KPIs DE MANUTENÇÃO ===
        kpis_manutencao = calcular_kpis_manutencao(admin_id, data_inicio, data_fim)
        
        # === MANUTENÇÕES POR STATUS ===
        manutencoes_status = analisar_manutencoes_por_status(admin_id)
        
        # === EVOLUÇÃO DE MANUTENÇÕES ===
        evolucao_manutencoes = analisar_evolucao_manutencoes(admin_id, data_inicio, data_fim)
        
        # === CUSTOS DE MANUTENÇÃO ===
        custos_manutencao = analisar_custos_manutencao(admin_id, data_inicio, data_fim)
        
        # === EFICIÊNCIA DE MANUTENÇÃO ===
        eficiencia_manutencao = calcular_eficiencia_manutencao(admin_id, data_inicio, data_fim)
        
        # === PRÓXIMAS MANUTENÇÕES ===
        proximas_manutencoes = obter_proximas_manutencoes(admin_id)
        
        # === MANUTENÇÕES CRÍTICAS ===
        manutencoes_criticas = identificar_manutencoes_criticas(admin_id)
        
        # === ANÁLISE POR CATEGORIA ===
        analise_categoria = analisar_manutencao_por_categoria(admin_id, data_inicio, data_fim)
        
        # === DADOS PARA FILTROS ===
        veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
        categorias = obter_categorias_manutencao(admin_id)
        
        return render_template('dashboards/especificos/manutencao.html',
                             kpis_manutencao=kpis_manutencao,
                             manutencoes_status=manutencoes_status,
                             evolucao_manutencoes=evolucao_manutencoes,
                             custos_manutencao=custos_manutencao,
                             eficiencia_manutencao=eficiencia_manutencao,
                             proximas_manutencoes=proximas_manutencoes,
                             manutencoes_criticas=manutencoes_criticas,
                             analise_categoria=analise_categoria,
                             veiculos=veiculos,
                             categorias=categorias,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             filtros={'veiculo_id': veiculo_id, 'categoria': categoria})
        
    except Exception as e:
        logger.error(f"Erro no dashboard de manutenção: {e}")
        flash('Erro ao carregar dashboard de manutenção', 'danger')
        return redirect(url_for('main.dashboard'))

def calcular_kpis_manutencao(admin_id, data_inicio, data_fim):
    """Calcula KPIs principais de manutenção"""
    try:
        # Manutenções no período
        total_manutencoes = ManutencaoVeiculo.query.filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim
        ).count()
        
        # Custo total de manutenções
        custo_total = db.session.query(func.sum(ManutencaoVeiculo.valor_total)).filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim
        ).scalar() or 0
        
        # Veículos com manutenção no período
        veiculos_manutencao = db.session.query(
            func.count(func.distinct(ManutencaoVeiculo.veiculo_id))
        ).filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim
        ).scalar() or 0
        
        # Manutenções vencidas
        hoje = date.today()
        manutencoes_vencidas = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao < hoje
        ).count()
        
        # Tempo médio de manutenção
        tempo_medio = db.session.query(func.avg(ManutencaoVeiculo.tempo_parada_horas)).filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim,
            ManutencaoVeiculo.tempo_parada_horas.isnot(None)
        ).scalar() or 0
        
        # Custo médio por manutenção
        custo_medio = custo_total / max(total_manutencoes, 1)
        
        # Taxa de manutenção preventiva
        manutencoes_preventivas = ManutencaoVeiculo.query.filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim,
            ManutencaoVeiculo.tipo == 'Preventiva'
        ).count()
        
        taxa_preventiva = (manutencoes_preventivas / max(total_manutencoes, 1)) * 100
        
        return {
            'total_manutencoes': total_manutencoes,
            'custo_total': float(custo_total),
            'veiculos_manutencao': veiculos_manutencao,
            'manutencoes_vencidas': manutencoes_vencidas,
            'tempo_medio': round(float(tempo_medio), 1),
            'custo_medio': round(custo_medio, 2),
            'taxa_preventiva': round(taxa_preventiva, 1),
            'manutencoes_preventivas': manutencoes_preventivas
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular KPIs manutenção: {e}")
        return {}

def analisar_manutencoes_por_status(admin_id):
    """Analisa distribuição de manutenções por status"""
    try:
        # Status das próximas manutenções
        hoje = date.today()
        
        # Vencidas
        vencidas = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao < hoje
        ).count()
        
        # Próximas (próximos 30 dias)
        data_limite = hoje + timedelta(days=30)
        proximas = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao >= hoje,
            Veiculo.data_proxima_manutencao <= data_limite
        ).count()
        
        # Em dia
        em_dia = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao > data_limite
        ).count()
        
        # Sem data definida
        sem_data = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao.is_(None)
        ).count()
        
        return {
            'vencidas': vencidas,
            'proximas': proximas,
            'em_dia': em_dia,
            'sem_data': sem_data,
            'total': vencidas + proximas + em_dia + sem_data
        }
        
    except Exception as e:
        logger.error(f"Erro na análise por status: {e}")
        return {}

def analisar_evolucao_manutencoes(admin_id, data_inicio, data_fim):
    """Analisa evolução temporal das manutenções"""
    try:
        # Manutenções por mês
        manutencoes_mensais = db.session.query(
            extract('year', ManutencaoVeiculo.data_manutencao).label('ano'),
            extract('month', ManutencaoVeiculo.data_manutencao).label('mes'),
            func.count(ManutencaoVeiculo.id).label('total'),
            func.sum(ManutencaoVeiculo.valor_total).label('custo_total'),
            func.count(case([(ManutencaoVeiculo.tipo == 'Preventiva', 1)])).label('preventivas'),
            func.count(case([(ManutencaoVeiculo.tipo == 'Corretiva', 1)])).label('corretivas')
        ).filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim
        ).group_by('ano', 'mes').order_by('ano', 'mes').all()
        
        evolucao = []
        for d in manutencoes_mensais:
            evolucao.append({
                'periodo': f"{int(d.ano)}-{int(d.mes):02d}",
                'total': d.total,
                'custo_total': float(d.custo_total or 0),
                'preventivas': d.preventivas,
                'corretivas': d.corretivas,
                'taxa_preventiva': (d.preventivas / max(d.total, 1)) * 100
            })
        
        return evolucao
        
    except Exception as e:
        logger.error(f"Erro na evolução de manutenções: {e}")
        return []

def analisar_custos_manutencao(admin_id, data_inicio, data_fim):
    """Analisa custos detalhados de manutenção"""
    try:
        # Custos por categoria
        custos_categoria = db.session.query(
            ManutencaoVeiculo.categoria,
            func.count(ManutencaoVeiculo.id).label('total'),
            func.sum(ManutencaoVeiculo.valor_total).label('custo_total'),
            func.avg(ManutencaoVeiculo.valor_total).label('custo_medio')
        ).filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim
        ).group_by(ManutencaoVeiculo.categoria).all()
        
        # Custos por veículo (top 10)
        custos_veiculo = db.session.query(
            Veiculo.placa,
            func.count(ManutencaoVeiculo.id).label('total'),
            func.sum(ManutencaoVeiculo.valor_total).label('custo_total')
        ).join(ManutencaoVeiculo)\
        .filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= data_inicio,
            ManutencaoVeiculo.data_manutencao <= data_fim
        ).group_by(Veiculo.placa)\
        .order_by(desc('custo_total')).limit(10).all()
        
        return {
            'por_categoria': [{
                'categoria': c.categoria,
                'total': c.total,
                'custo_total': float(c.custo_total or 0),
                'custo_medio': float(c.custo_medio or 0)
            } for c in custos_categoria],
            'por_veiculo': [{
                'placa': c.placa,
                'total': c.total,
                'custo_total': float(c.custo_total or 0)
            } for c in custos_veiculo]
        }
        
    except Exception as e:
        logger.error(f"Erro na análise de custos: {e}")
        return {}

# ===== DASHBOARD DE COMBUSTÍVEL =====

@dashboards_bp.route('/combustivel')
@login_required
@admin_required
def dashboard_combustivel():
    """Dashboard especializado em combustível"""
    admin_id = get_admin_id()
    
    # Período padrão (últimos 3 meses)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=90)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    veiculo_id = request.args.get('veiculo_id', type=int)
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # === KPIs DE COMBUSTÍVEL ===
        kpis_combustivel = calcular_kpis_combustivel(admin_id, data_inicio, data_fim)
        
        # === EFICIÊNCIA POR VEÍCULO ===
        eficiencia_veiculos = analisar_eficiencia_combustivel(admin_id, data_inicio, data_fim)
        
        # === EVOLUÇÃO DE CONSUMO ===
        evolucao_consumo = analisar_evolucao_consumo(admin_id, data_inicio, data_fim)
        
        # === RANKING DE EFICIÊNCIA ===
        ranking_eficiencia = calcular_ranking_eficiencia(admin_id, data_inicio, data_fim)
        
        # === ANÁLISE DE CUSTOS ===
        analise_custos_combustivel = analisar_custos_combustivel(admin_id, data_inicio, data_fim)
        
        # === ALERTAS DE CONSUMO ===
        alertas_consumo = identificar_alertas_consumo(admin_id, data_inicio, data_fim)
        
        # === DADOS PARA FILTROS ===
        veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        return render_template('dashboards/especificos/combustivel.html',
                             kpis_combustivel=kpis_combustivel,
                             eficiencia_veiculos=eficiencia_veiculos,
                             evolucao_consumo=evolucao_consumo,
                             ranking_eficiencia=ranking_eficiencia,
                             analise_custos_combustivel=analise_custos_combustivel,
                             alertas_consumo=alertas_consumo,
                             veiculos=veiculos,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             filtros={'veiculo_id': veiculo_id})
        
    except Exception as e:
        logger.error(f"Erro no dashboard de combustível: {e}")
        flash('Erro ao carregar dashboard de combustível', 'danger')
        return redirect(url_for('main.dashboard'))

def calcular_kpis_combustivel(admin_id, data_inicio, data_fim):
    """Calcula KPIs de combustível"""
    try:
        # Custos de combustível
        custo_combustivel = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.tipo_custo == 'combustivel',
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).scalar() or 0
        
        # KM rodados
        km_total = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).scalar() or 0
        
        # Número de abastecimentos
        abastecimentos = CustoVeiculo.query.filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.tipo_custo == 'combustivel',
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).count()
        
        # Veículos que abasteceram
        veiculos_abasteceram = db.session.query(
            func.count(func.distinct(CustoVeiculo.veiculo_id))
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.tipo_custo == 'combustivel',
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).scalar() or 0
        
        # Médias
        custo_por_km = custo_combustivel / max(float(km_total), 1) if km_total > 0 else 0
        custo_medio_abastecimento = custo_combustivel / max(abastecimentos, 1)
        km_por_abastecimento = float(km_total) / max(abastecimentos, 1) if abastecimentos > 0 else 0
        
        return {
            'custo_combustivel': float(custo_combustivel),
            'km_total': float(km_total),
            'abastecimentos': abastecimentos,
            'veiculos_abasteceram': veiculos_abasteceram,
            'custo_por_km': round(custo_por_km, 3),
            'custo_medio_abastecimento': round(custo_medio_abastecimento, 2),
            'km_por_abastecimento': round(km_por_abastecimento, 1)
        }
        
    except Exception as e:
        logger.error(f"Erro nos KPIs de combustível: {e}")
        return {}

def analisar_eficiencia_combustivel(admin_id, data_inicio, data_fim):
    """Analisa eficiência de combustível por veículo"""
    try:
        dados = db.session.query(
            Veiculo.id,
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            func.sum(case([(CustoVeiculo.tipo_custo == 'combustivel', CustoVeiculo.valor)], else_=0)).label('custo_combustivel'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(case([(CustoVeiculo.tipo_custo == 'combustivel', 1)])).label('abastecimentos')
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
        .group_by(Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo)\
        .having(func.sum(UsoVeiculo.km_rodado) > 0).all()
        
        eficiencia = []
        for d in dados:
            custo_combustivel = float(d.custo_combustivel or 0)
            km_total = float(d.km_total or 0)
            
            if km_total > 0 and custo_combustivel > 0:
                custo_por_km = custo_combustivel / km_total
                km_por_real = km_total / custo_combustivel
                
                eficiencia.append({
                    'veiculo_id': d.id,
                    'placa': d.placa,
                    'marca': d.marca,
                    'modelo': d.modelo,
                    'custo_combustivel': custo_combustivel,
                    'km_total': km_total,
                    'abastecimentos': d.abastecimentos,
                    'custo_por_km': round(custo_por_km, 3),
                    'km_por_real': round(km_por_real, 2)
                })
        
        return sorted(eficiencia, key=lambda x: x['custo_por_km'])
        
    except Exception as e:
        logger.error(f"Erro na análise de eficiência: {e}")
        return []

# ===== DASHBOARD DE OBRAS =====

@dashboards_bp.route('/obras')
@login_required
@admin_required
def dashboard_obras():
    """Dashboard especializado em obras"""
    admin_id = get_admin_id()
    
    # Período padrão (últimos 6 meses)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=180)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    obra_id = request.args.get('obra_id', type=int)
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # === KPIs DE OBRAS ===
        kpis_obras = calcular_kpis_obras(admin_id, data_inicio, data_fim)
        
        # === VEÍCULOS POR OBRA ===
        veiculos_por_obra = analisar_veiculos_por_obra(admin_id)
        
        # === CUSTOS POR OBRA ===
        custos_por_obra = analisar_custos_por_obra(admin_id, data_inicio, data_fim)
        
        # === EFICIÊNCIA POR OBRA ===
        eficiencia_obras = calcular_eficiencia_obras(admin_id, data_inicio, data_fim)
        
        # === UTILIZAÇÃO DE FROTA ===
        utilizacao_frota = analisar_utilizacao_frota_obras(admin_id, data_inicio, data_fim)
        
        # === ALERTAS DE OBRAS ===
        alertas_obras = identificar_alertas_obras(admin_id)
        
        # === DADOS PARA FILTROS ===
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        return render_template('dashboards/especificos/obras.html',
                             kpis_obras=kpis_obras,
                             veiculos_por_obra=veiculos_por_obra,
                             custos_por_obra=custos_por_obra,
                             eficiencia_obras=eficiencia_obras,
                             utilizacao_frota=utilizacao_frota,
                             alertas_obras=alertas_obras,
                             obras=obras,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             filtros={'obra_id': obra_id})
        
    except Exception as e:
        logger.error(f"Erro no dashboard de obras: {e}")
        flash('Erro ao carregar dashboard de obras', 'danger')
        return redirect(url_for('main.dashboard'))

# ===== DASHBOARD DE FROTA =====

@dashboards_bp.route('/frota')
@login_required
@admin_required
def dashboard_frota():
    """Dashboard geral da frota"""
    admin_id = get_admin_id()
    
    try:
        # === STATUS DA FROTA ===
        status_frota = obter_status_frota_detalhado(admin_id)
        
        # === DISTRIBUIÇÃO POR TIPO ===
        distribuicao_tipo = analisar_distribuicao_por_tipo(admin_id)
        
        # === IDADE DA FROTA ===
        idade_frota = analisar_idade_frota(admin_id)
        
        # === DISPONIBILIDADE ===
        disponibilidade_frota = calcular_disponibilidade_frota(admin_id)
        
        # === VEÍCULOS CRÍTICOS ===
        veiculos_criticos = identificar_veiculos_criticos_frota(admin_id)
        
        # === ESTATÍSTICAS GERAIS ===
        estatisticas_gerais = calcular_estatisticas_gerais_frota(admin_id)
        
        return render_template('dashboards/especificos/frota.html',
                             status_frota=status_frota,
                             distribuicao_tipo=distribuicao_tipo,
                             idade_frota=idade_frota,
                             disponibilidade_frota=disponibilidade_frota,
                             veiculos_criticos=veiculos_criticos,
                             estatisticas_gerais=estatisticas_gerais)
        
    except Exception as e:
        logger.error(f"Erro no dashboard de frota: {e}")
        flash('Erro ao carregar dashboard de frota', 'danger')
        return redirect(url_for('main.dashboard'))

# ===== FUNÇÕES DE APOIO ===

def calcular_eficiencia_manutencao(admin_id, data_inicio, data_fim):
    """Calcula eficiência de manutenção"""
    # Implementação detalhada aqui
    return {}

def obter_proximas_manutencoes(admin_id):
    """Obtém próximas manutenções programadas"""
    try:
        hoje = date.today()
        proximas = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao >= hoje
        ).order_by(Veiculo.data_proxima_manutencao).limit(10).all()
        
        return [{
            'veiculo_id': v.id,
            'placa': v.placa,
            'marca': v.marca,
            'modelo': v.modelo,
            'data_proxima': v.data_proxima_manutencao.strftime('%d/%m/%Y') if v.data_proxima_manutencao else '',
            'dias_restantes': (v.data_proxima_manutencao - hoje).days if v.data_proxima_manutencao else 0
        } for v in proximas]
        
    except Exception as e:
        logger.error(f"Erro ao obter próximas manutenções: {e}")
        return []

def identificar_manutencoes_criticas(admin_id):
    """Identifica manutenções críticas"""
    try:
        hoje = date.today()
        criticas = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao < hoje
        ).order_by(Veiculo.data_proxima_manutencao).all()
        
        return [{
            'veiculo_id': v.id,
            'placa': v.placa,
            'marca': v.marca,
            'modelo': v.modelo,
            'data_vencimento': v.data_proxima_manutencao.strftime('%d/%m/%Y') if v.data_proxima_manutencao else '',
            'dias_vencido': (hoje - v.data_proxima_manutencao).days if v.data_proxima_manutencao else 0,
            'criticidade': 'Alta' if (hoje - v.data_proxima_manutencao).days > 30 else 'Média'
        } for v in criticas]
        
    except Exception as e:
        logger.error(f"Erro ao identificar manutenções críticas: {e}")
        return []

def analisar_manutencao_por_categoria(admin_id, data_inicio, data_fim):
    """Analisa manutenções por categoria"""
    # Implementação detalhada aqui
    return {}

def obter_categorias_manutencao(admin_id):
    """Obtém categorias de manutenção únicas"""
    try:
        categorias = db.session.query(ManutencaoVeiculo.categoria)\
        .filter(ManutencaoVeiculo.admin_id == admin_id)\
        .distinct().all()
        
        return [c.categoria for c in categorias if c.categoria]
        
    except Exception as e:
        logger.error(f"Erro ao obter categorias: {e}")
        return []

# Implementar outras funções de apoio conforme necessário...

# ===== APIS =====

@dashboards_bp.route('/api/dados-especificos')
@login_required
@admin_required
def api_dados_especificos():
    """API para dados específicos via AJAX"""
    admin_id = get_admin_id()
    
    dashboard = request.args.get('dashboard')
    tipo = request.args.get('tipo')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        if dashboard == 'manutencao':
            if tipo == 'kpis':
                dados = calcular_kpis_manutencao(admin_id, data_inicio_obj, data_fim_obj)
            elif tipo == 'evolucao':
                dados = analisar_evolucao_manutencoes(admin_id, data_inicio_obj, data_fim_obj)
            else:
                dados = {}
        elif dashboard == 'combustivel':
            if tipo == 'kpis':
                dados = calcular_kpis_combustivel(admin_id, data_inicio_obj, data_fim_obj)
            elif tipo == 'eficiencia':
                dados = analisar_eficiencia_combustivel(admin_id, data_inicio_obj, data_fim_obj)
            else:
                dados = {}
        else:
            dados = {}
        
        return jsonify({
            'success': True,
            'dados': dados
        })
        
    except Exception as e:
        logger.error(f"Erro na API específica: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Placeholder para outras funções específicas dos dashboards...
def analisar_evolucao_consumo(admin_id, data_inicio, data_fim):
    return []

def calcular_ranking_eficiencia(admin_id, data_inicio, data_fim):
    return []

def analisar_custos_combustivel(admin_id, data_inicio, data_fim):
    return {}

def identificar_alertas_consumo(admin_id, data_inicio, data_fim):
    return []

def calcular_kpis_obras(admin_id, data_inicio, data_fim):
    return {}

def analisar_veiculos_por_obra(admin_id):
    return []

def analisar_custos_por_obra(admin_id, data_inicio, data_fim):
    return []

def calcular_eficiencia_obras(admin_id, data_inicio, data_fim):
    return []

def analisar_utilizacao_frota_obras(admin_id, data_inicio, data_fim):
    return []

def identificar_alertas_obras(admin_id):
    return []

def obter_status_frota_detalhado(admin_id):
    return {}

def analisar_distribuicao_por_tipo(admin_id):
    return []

def analisar_idade_frota(admin_id):
    return []

def calcular_disponibilidade_frota(admin_id):
    return {}

def identificar_veiculos_criticos_frota(admin_id):
    return []

def calcular_estatisticas_gerais_frota(admin_id):
    return {}