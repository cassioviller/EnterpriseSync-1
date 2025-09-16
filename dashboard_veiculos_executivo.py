"""
DASHBOARD EXECUTIVO DE VEÍCULOS - SIGE v8.0
Sistema completo de KPIs, métricas e gráficos interativos para gestão da frota

Funcionalidades:
- KPIs principais: frota ativa, custos mensais, km rodados, alertas
- Gráficos interativos: uso por mês, custos por categoria, eficiência
- Status visual da frota: disponíveis, alocados, manutenção
- Alertas críticos: manutenções vencidas, custos altos
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

# Importar modelos
from models import (
    db, Veiculo, CustoVeiculo, UsoVeiculo, AlocacaoVeiculo, ManutencaoVeiculo,
    AlertaVeiculo, Obra, Funcionario, Usuario, TipoUsuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
dashboard_executive_bp = Blueprint('dashboard_executive', __name__, url_prefix='/dashboards/veiculos')

def get_admin_id():
    """Obtém admin_id do usuário atual com tratamento robusto"""
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

# ===== DASHBOARD EXECUTIVO PRINCIPAL =====

@dashboard_executive_bp.route('/executivo')
@login_required
@admin_required
def dashboard_executivo():
    """Dashboard executivo completo com KPIs e gráficos"""
    admin_id = get_admin_id()
    
    try:
        # Período de análise (último mês por padrão)
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=30)
        
        # === KPIs PRINCIPAIS ===
        kpis = calcular_kpis_principais(admin_id, data_inicio, data_fim)
        
        # === GRÁFICOS E DADOS ===
        graficos = {
            'uso_mensal': obter_dados_uso_mensal(admin_id),
            'custos_categoria': obter_dados_custos_categoria(admin_id, data_inicio, data_fim),
            'eficiencia_veiculos': obter_dados_eficiencia_veiculos(admin_id, data_inicio, data_fim),
            'evolucao_custos': obter_evolucao_custos_mensal(admin_id),
            'status_frota': obter_status_frota(admin_id),
            'top_veiculos_custo': obter_top_veiculos_custo(admin_id, data_inicio, data_fim),
            'utilizacao_diaria': obter_utilizacao_diaria(admin_id, data_inicio, data_fim)
        }
        
        # === ALERTAS CRÍTICOS ===
        alertas = obter_alertas_criticos(admin_id)
        
        # === ANÁLISES DE TENDÊNCIA ===
        tendencias = calcular_tendencias(admin_id)
        
        # === COMPARATIVO PERÍODO ANTERIOR ===
        comparativo = calcular_comparativo_periodo_anterior(admin_id, data_inicio, data_fim)
        
        return render_template('dashboards/veiculos/executivo.html',
                             kpis=kpis,
                             graficos=graficos,
                             alertas=alertas,
                             tendencias=tendencias,
                             comparativo=comparativo,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"Erro no dashboard executivo: {e}")
        flash('Erro ao carregar dashboard executivo', 'danger')
        return redirect(url_for('main.dashboard'))

def calcular_kpis_principais(admin_id, data_inicio, data_fim):
    """Calcula KPIs principais do dashboard"""
    
    def _get_frota_ativa():
        return Veiculo.query.filter_by(admin_id=admin_id, ativo=True).count()
    
    def _get_custo_mensal():
        return db.session.query(func.coalesce(func.sum(CustoVeiculo.valor), 0)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).scalar()
    
    def _get_km_rodados():
        return db.session.query(func.coalesce(func.sum(UsoVeiculo.km_rodado), 0)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).scalar()
    
    def _get_alertas_ativos():
        return AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True,
            AlertaVeiculo.data_visualizacao.is_(None)
        ).count()
    
    def _get_veiculos_alocados():
        return db.session.query(func.count(func.distinct(AlocacaoVeiculo.veiculo_id))).filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).scalar()
    
    def _get_obras_com_veiculos():
        return db.session.query(func.count(func.distinct(AlocacaoVeiculo.obra_id))).filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).scalar()
    
    def _get_utilizacao_media():
        # Calcula % de utilização baseado em dias com uso
        total_dias = (data_fim - data_inicio).days
        dias_com_uso = db.session.query(
            func.count(func.distinct(UsoVeiculo.data_uso))
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).scalar()
        
        return (dias_com_uso / max(total_dias, 1)) * 100 if total_dias > 0 else 0
    
    def _get_custo_por_km():
        total_custo = _get_custo_mensal()
        total_km = _get_km_rodados()
        return total_custo / max(total_km, 1) if total_km > 0 else 0
    
    return safe_db_operation(lambda: {
        'frota_ativa': _get_frota_ativa(),
        'custo_mensal': float(_get_custo_mensal() or 0),
        'km_rodados': int(_get_km_rodados() or 0),
        'alertas_ativos': _get_alertas_ativos(),
        'veiculos_alocados': _get_veiculos_alocados(),
        'obras_com_veiculos': _get_obras_com_veiculos(),
        'utilizacao_media': round(_get_utilizacao_media(), 2),
        'custo_por_km': round(_get_custo_por_km(), 2)
    }, {
        'frota_ativa': 0, 'custo_mensal': 0, 'km_rodados': 0, 'alertas_ativos': 0,
        'veiculos_alocados': 0, 'obras_com_veiculos': 0, 'utilizacao_media': 0, 'custo_por_km': 0
    })

def obter_dados_uso_mensal(admin_id):
    """Obtém dados de uso por mês para gráfico"""
    try:
        # Últimos 12 meses
        data_limite = date.today() - timedelta(days=365)
        
        dados = db.session.query(
            extract('year', UsoVeiculo.data_uso).label('ano'),
            extract('month', UsoVeiculo.data_uso).label('mes'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_limite
        ).group_by(
            extract('year', UsoVeiculo.data_uso),
            extract('month', UsoVeiculo.data_uso)
        ).order_by('ano', 'mes').all()
        
        return [{
            'periodo': f"{int(d.ano)}-{int(d.mes):02d}",
            'km_total': float(d.km_total or 0),
            'total_usos': int(d.total_usos or 0),
            'horas_total': float(d.horas_total or 0)
        } for d in dados]
        
    except Exception as e:
        logger.error(f"Erro ao obter uso mensal: {e}")
        return []

def obter_dados_custos_categoria(admin_id, data_inicio, data_fim):
    """Obtém distribuição de custos por categoria"""
    try:
        dados = db.session.query(
            CustoVeiculo.tipo_custo,
            func.sum(CustoVeiculo.valor).label('total')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(CustoVeiculo.tipo_custo).all()
        
        return [{
            'categoria': d.tipo_custo,
            'valor': float(d.total or 0),
            'cor': obter_cor_categoria(d.tipo_custo)
        } for d in dados]
        
    except Exception as e:
        logger.error(f"Erro ao obter custos por categoria: {e}")
        return []

def obter_dados_eficiencia_veiculos(admin_id, data_inicio, data_fim):
    """Calcula eficiência de cada veículo"""
    try:
        # Query complexa para calcular eficiência
        dados = db.session.query(
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            func.coalesce(func.sum(UsoVeiculo.km_rodado), 0).label('km_total'),
            func.coalesce(func.sum(CustoVeiculo.valor), 0).label('custo_total'),
            func.coalesce(func.sum(UsoVeiculo.horas_uso), 0).label('horas_total'),
            func.count(UsoVeiculo.id).label('total_usos')
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
        .group_by(Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo)\
        .all()
        
        eficiencia = []
        for d in dados:
            custo_por_km = float(d.custo_total) / max(float(d.km_total), 1) if d.km_total > 0 else 0
            km_por_uso = float(d.km_total) / max(d.total_usos, 1) if d.total_usos > 0 else 0
            
            # Score de eficiência (0-100) baseado em múltiplos fatores
            score_eficiencia = calcular_score_eficiencia(
                float(d.km_total), float(d.custo_total), 
                float(d.horas_total), d.total_usos
            )
            
            eficiencia.append({
                'veiculo': f"{d.placa} ({d.marca} {d.modelo})",
                'km_total': float(d.km_total),
                'custo_total': float(d.custo_total),
                'horas_total': float(d.horas_total),
                'total_usos': d.total_usos,
                'custo_por_km': round(custo_por_km, 2),
                'km_por_uso': round(km_por_uso, 2),
                'score_eficiencia': round(score_eficiencia, 1)
            })
        
        return sorted(eficiencia, key=lambda x: x['score_eficiencia'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro ao calcular eficiência: {e}")
        return []

def obter_evolucao_custos_mensal(admin_id):
    """Obtém evolução de custos mensais (últimos 12 meses)"""
    try:
        data_limite = date.today() - timedelta(days=365)
        
        dados = db.session.query(
            extract('year', CustoVeiculo.data_custo).label('ano'),
            extract('month', CustoVeiculo.data_custo).label('mes'),
            CustoVeiculo.tipo_custo,
            func.sum(CustoVeiculo.valor).label('total')
        ).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_limite
        ).group_by(
            extract('year', CustoVeiculo.data_custo),
            extract('month', CustoVeiculo.data_custo),
            CustoVeiculo.tipo_custo
        ).order_by('ano', 'mes').all()
        
        # Organizar dados por período e categoria
        evolucao = defaultdict(lambda: defaultdict(float))
        categorias = set()
        
        for d in dados:
            periodo = f"{int(d.ano)}-{int(d.mes):02d}"
            evolucao[periodo][d.tipo_custo] = float(d.total or 0)
            categorias.add(d.tipo_custo)
        
        # Converter para formato do gráfico
        resultado = []
        for periodo in sorted(evolucao.keys()):
            item = {'periodo': periodo}
            total_periodo = 0
            for categoria in categorias:
                valor = evolucao[periodo][categoria]
                item[categoria] = valor
                total_periodo += valor
            item['total'] = total_periodo
            resultado.append(item)
        
        return {
            'dados': resultado,
            'categorias': list(categorias)
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter evolução custos: {e}")
        return {'dados': [], 'categorias': []}

def obter_status_frota(admin_id):
    """Obtém status atual da frota"""
    try:
        # Veículos por status
        status_counts = db.session.query(
            Veiculo.status,
            func.count(Veiculo.id).label('total')
        ).filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True
        ).group_by(Veiculo.status).all()
        
        # Veículos alocados (independente do status)
        alocados = db.session.query(func.count(func.distinct(AlocacaoVeiculo.veiculo_id))).filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).scalar()
        
        status_data = {}
        for s in status_counts:
            status_data[s.status] = s.total
        
        return {
            'disponivel': status_data.get('Disponível', 0),
            'alocado': alocados or 0,
            'manutencao': status_data.get('Manutenção', 0),
            'inativo': status_data.get('Inativo', 0),
            'total': sum(status_data.values())
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter status frota: {e}")
        return {'disponivel': 0, 'alocado': 0, 'manutencao': 0, 'inativo': 0, 'total': 0}

def obter_top_veiculos_custo(admin_id, data_inicio, data_fim):
    """Obtém top 10 veículos com maior custo no período"""
    try:
        dados = db.session.query(
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            func.sum(CustoVeiculo.valor).label('custo_total')
        ).join(CustoVeiculo)\
        .filter(
            Veiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).group_by(Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo)\
        .order_by(desc('custo_total'))\
        .limit(10).all()
        
        return [{
            'veiculo': f"{d.placa} ({d.marca} {d.modelo})",
            'custo_total': float(d.custo_total or 0)
        } for d in dados]
        
    except Exception as e:
        logger.error(f"Erro ao obter top veículos custo: {e}")
        return []

def obter_utilizacao_diaria(admin_id, data_inicio, data_fim):
    """Obtém dados de utilização diária"""
    try:
        dados = db.session.query(
            UsoVeiculo.data_uso,
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(UsoVeiculo.data_uso)\
        .order_by(UsoVeiculo.data_uso).all()
        
        return [{
            'data': d.data_uso.strftime('%Y-%m-%d'),
            'veiculos_utilizados': d.veiculos_utilizados,
            'km_total': float(d.km_total or 0),
            'horas_total': float(d.horas_total or 0)
        } for d in dados]
        
    except Exception as e:
        logger.error(f"Erro ao obter utilização diária: {e}")
        return []

def obter_alertas_criticos(admin_id):
    """Obtém alertas críticos do sistema"""
    try:
        alertas = []
        
        # Alertas de banco de dados
        alertas_db = AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True,
            AlertaVeiculo.data_visualizacao.is_(None)
        ).order_by(AlertaVeiculo.nivel.desc(), AlertaVeiculo.created_at.desc()).limit(10).all()
        
        for alerta in alertas_db:
            alertas.append({
                'id': alerta.id,
                'tipo': alerta.tipo_alerta,
                'nivel': alerta.nivel,
                'titulo': alerta.titulo,
                'mensagem': alerta.mensagem,
                'data_criacao': alerta.created_at.strftime('%d/%m/%Y %H:%M'),
                'veiculo_placa': alerta.veiculo.placa if alerta.veiculo else None
            })
        
        # Alertas calculados em tempo real
        alertas.extend(calcular_alertas_tempo_real(admin_id))
        
        return sorted(alertas, key=lambda x: x.get('nivel', 0), reverse=True)
        
    except Exception as e:
        logger.error(f"Erro ao obter alertas: {e}")
        return []

def calcular_alertas_tempo_real(admin_id):
    """Calcula alertas em tempo real"""
    alertas = []
    
    try:
        # Alocações atrasadas
        alocacoes_atrasadas = AlocacaoVeiculo.query.filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None),
            AlocacaoVeiculo.data_prevista_retorno < date.today()
        ).all()
        
        for alocacao in alocacoes_atrasadas:
            dias_atraso = (date.today() - alocacao.data_prevista_retorno).days
            alertas.append({
                'tipo': 'alocacao_atrasada',
                'nivel': 3 if dias_atraso > 7 else 2,
                'titulo': 'Alocação Atrasada',
                'mensagem': f'Veículo {alocacao.veiculo.placa} atrasado há {dias_atraso} dias na obra {alocacao.obra.nome}',
                'veiculo_placa': alocacao.veiculo.placa
            })
        
        # Manutenções vencidas
        hoje = date.today()
        veiculos_manutencao_vencida = Veiculo.query.filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            Veiculo.data_proxima_manutencao < hoje
        ).all()
        
        for veiculo in veiculos_manutencao_vencida:
            dias_vencido = (hoje - veiculo.data_proxima_manutencao).days
            alertas.append({
                'tipo': 'manutencao_vencida',
                'nivel': 3 if dias_vencido > 30 else 2,
                'titulo': 'Manutenção Vencida',
                'mensagem': f'Veículo {veiculo.placa} com manutenção vencida há {dias_vencido} dias',
                'veiculo_placa': veiculo.placa
            })
        
    except Exception as e:
        logger.error(f"Erro ao calcular alertas tempo real: {e}")
    
    return alertas

def calcular_tendencias(admin_id):
    """Calcula tendências e insights"""
    try:
        # Tendência de custos (últimos 3 meses vs 3 meses anteriores)
        hoje = date.today()
        mes_atual = hoje.replace(day=1)
        tres_meses_atras = mes_atual - timedelta(days=90)
        seis_meses_atras = tres_meses_atras - timedelta(days=90)
        
        custo_recente = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= tres_meses_atras
        ).scalar() or 0
        
        custo_anterior = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= seis_meses_atras,
            CustoVeiculo.data_custo < tres_meses_atras
        ).scalar() or 0
        
        tendencia_custo = 0
        if custo_anterior > 0:
            tendencia_custo = ((custo_recente - custo_anterior) / custo_anterior) * 100
        
        # Tendência de uso
        uso_recente = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= tres_meses_atras
        ).scalar() or 0
        
        uso_anterior = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= seis_meses_atras,
            UsoVeiculo.data_uso < tres_meses_atras
        ).scalar() or 0
        
        tendencia_uso = 0
        if uso_anterior > 0:
            tendencia_uso = ((uso_recente - uso_anterior) / uso_anterior) * 100
        
        return {
            'custo_tendencia': round(tendencia_custo, 2),
            'uso_tendencia': round(tendencia_uso, 2),
            'custo_recente': float(custo_recente),
            'uso_recente': float(uso_recente)
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular tendências: {e}")
        return {'custo_tendencia': 0, 'uso_tendencia': 0, 'custo_recente': 0, 'uso_recente': 0}

def calcular_comparativo_periodo_anterior(admin_id, data_inicio, data_fim):
    """Calcula comparativo com período anterior"""
    try:
        dias_periodo = (data_fim - data_inicio).days
        periodo_anterior_fim = data_inicio - timedelta(days=1)
        periodo_anterior_inicio = periodo_anterior_fim - timedelta(days=dias_periodo)
        
        # Custos
        custo_atual = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_inicio,
            CustoVeiculo.data_custo <= data_fim
        ).scalar() or 0
        
        custo_anterior = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= periodo_anterior_inicio,
            CustoVeiculo.data_custo <= periodo_anterior_fim
        ).scalar() or 0
        
        variacao_custo = 0
        if custo_anterior > 0:
            variacao_custo = ((custo_atual - custo_anterior) / custo_anterior) * 100
        
        # KM rodados
        km_atual = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).scalar() or 0
        
        km_anterior = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= periodo_anterior_inicio,
            UsoVeiculo.data_uso <= periodo_anterior_fim
        ).scalar() or 0
        
        variacao_km = 0
        if km_anterior > 0:
            variacao_km = ((km_atual - km_anterior) / km_anterior) * 100
        
        return {
            'custo_atual': float(custo_atual),
            'custo_anterior': float(custo_anterior),
            'variacao_custo': round(variacao_custo, 2),
            'km_atual': float(km_atual),
            'km_anterior': float(km_anterior),
            'variacao_km': round(variacao_km, 2)
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular comparativo: {e}")
        return {
            'custo_atual': 0, 'custo_anterior': 0, 'variacao_custo': 0,
            'km_atual': 0, 'km_anterior': 0, 'variacao_km': 0
        }

# ===== UTILITÁRIOS =====

def calcular_score_eficiencia(km_total, custo_total, horas_total, total_usos):
    """Calcula score de eficiência (0-100) baseado em múltiplos fatores"""
    if km_total == 0:
        return 0
    
    # Fatores de eficiência
    custo_por_km = custo_total / max(km_total, 1)
    km_por_uso = km_total / max(total_usos, 1)
    horas_por_uso = horas_total / max(total_usos, 1)
    
    # Score baseado em benchmarks (valores arbitrários, podem ser ajustados)
    score_custo = max(0, 100 - (custo_por_km * 10))  # Menos custo = melhor
    score_uso = min(100, km_por_uso * 2)  # Mais km por uso = melhor
    score_tempo = min(100, horas_por_uso * 10)  # Mais horas por uso = melhor
    
    # Média ponderada
    score_final = (score_custo * 0.4 + score_uso * 0.4 + score_tempo * 0.2)
    return max(0, min(100, score_final))

def obter_cor_categoria(categoria):
    """Retorna cor para categoria de custo"""
    cores = {
        'combustivel': '#FF6384',
        'manutencao': '#36A2EB',
        'seguro': '#FFCE56',
        'ipva': '#4BC0C0',
        'multa': '#FF9F40',
        'outros': '#9966FF'
    }
    return cores.get(categoria, '#CCCCCC')

# ===== APIS PARA GRÁFICOS =====

@dashboard_executive_bp.route('/api/dados-graficos')
@login_required
@admin_required
def api_dados_graficos():
    """API para fornecer dados dos gráficos via AJAX"""
    admin_id = get_admin_id()
    tipo_grafico = request.args.get('tipo')
    data_inicio = request.args.get('data_inicio', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', date.today().strftime('%Y-%m-%d'))
    
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    try:
        if tipo_grafico == 'uso_mensal':
            dados = obter_dados_uso_mensal(admin_id)
        elif tipo_grafico == 'custos_categoria':
            dados = obter_dados_custos_categoria(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo_grafico == 'eficiencia_veiculos':
            dados = obter_dados_eficiencia_veiculos(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo_grafico == 'evolucao_custos':
            dados = obter_evolucao_custos_mensal(admin_id)
        elif tipo_grafico == 'utilizacao_diaria':
            dados = obter_utilizacao_diaria(admin_id, data_inicio_obj, data_fim_obj)
        else:
            dados = []
        
        return jsonify({
            'success': True,
            'dados': dados
        })
        
    except Exception as e:
        logger.error(f"Erro na API de gráficos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dashboard_executive_bp.route('/api/kpis-atualizados')
@login_required
@admin_required
def api_kpis_atualizados():
    """API para obter KPIs atualizados"""
    admin_id = get_admin_id()
    data_inicio = request.args.get('data_inicio', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', date.today().strftime('%Y-%m-%d'))
    
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    try:
        kpis = calcular_kpis_principais(admin_id, data_inicio_obj, data_fim_obj)
        return jsonify({
            'success': True,
            'kpis': kpis
        })
        
    except Exception as e:
        logger.error(f"Erro na API de KPIs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500