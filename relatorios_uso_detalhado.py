"""
RELATÓRIOS DE USO DETALHADO - SIGE v8.0
Sistema completo de análise de uso de veículos

Funcionalidades:
- Histórico completo de uso por veículo
- Análise temporal (diário, semanal, mensal)
- Uso por funcionário/responsável
- Uso por obra/projeto
- Eficiência operacional
- Padrões de uso e sazonalidade
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
from io import BytesIO

# Importar modelos
from models import (
    db, Veiculo, UsoVeiculo, CustoVeiculo, AlocacaoVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
uso_detalhado_bp = Blueprint('relatorios_uso', __name__, url_prefix='/relatorios/uso')

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

# ===== DASHBOARD PRINCIPAL DE USO =====

@uso_detalhado_bp.route('/')
@login_required
@admin_required
def dashboard_uso():
    """Dashboard principal de uso de veículos"""
    admin_id = get_admin_id()
    
    # Período padrão (últimos 30 dias)
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=30)
    
    # Filtros do request
    data_inicio_str = request.args.get('data_inicio', data_inicio.strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', data_fim.strftime('%Y-%m-%d'))
    veiculo_id = request.args.get('veiculo_id', type=int)
    obra_id = request.args.get('obra_id', type=int)
    funcionario_id = request.args.get('funcionario_id', type=int)
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    try:
        # === MÉTRICAS GERAIS ===
        metricas_gerais = calcular_metricas_uso_geral(admin_id, data_inicio, data_fim)
        
        # === ANÁLISE TEMPORAL ===
        analise_temporal = analisar_uso_temporal(admin_id, data_inicio, data_fim)
        
        # === USO POR VEÍCULO ===
        uso_por_veiculo = analisar_uso_por_veiculo(admin_id, data_inicio, data_fim, veiculo_id)
        
        # === USO POR OBRA ===
        uso_por_obra = analisar_uso_por_obra(admin_id, data_inicio, data_fim, obra_id)
        
        # === USO POR FUNCIONÁRIO ===
        uso_por_funcionario = analisar_uso_por_funcionario(admin_id, data_inicio, data_fim, funcionario_id)
        
        # === PADRÕES E INSIGHTS ===
        padroes_uso = identificar_padroes_uso(admin_id, data_inicio, data_fim)
        
        # === DADOS PARA FILTROS ===
        veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        return render_template('relatorios/uso/dashboard.html',
                             metricas_gerais=metricas_gerais,
                             analise_temporal=analise_temporal,
                             uso_por_veiculo=uso_por_veiculo,
                             uso_por_obra=uso_por_obra,
                             uso_por_funcionario=uso_por_funcionario,
                             padroes_uso=padroes_uso,
                             veiculos=veiculos,
                             obras=obras,
                             funcionarios=funcionarios,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             filtros={
                                 'veiculo_id': veiculo_id,
                                 'obra_id': obra_id,
                                 'funcionario_id': funcionario_id
                             })
        
    except Exception as e:
        logger.error(f"Erro no dashboard de uso: {e}")
        flash('Erro ao carregar dashboard de uso', 'danger')
        return redirect(url_for('main.dashboard'))

def calcular_metricas_uso_geral(admin_id, data_inicio, data_fim):
    """Calcula métricas gerais de uso da frota"""
    
    try:
        # Query principal
        dados = db.session.query(
            func.count(UsoVeiculo.id).label('total_usos'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_ativos'),
            func.count(func.distinct(UsoVeiculo.funcionario_id)).label('funcionarios_ativos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio_uso'),
            func.max(UsoVeiculo.km_rodado).label('maior_viagem'),
            func.min(UsoVeiculo.km_rodado).label('menor_viagem')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        if not dados or dados.total_usos == 0:
            return {
                'total_usos': 0, 'veiculos_utilizados': 0, 'dias_ativos': 0,
                'funcionarios_ativos': 0, 'km_total': 0, 'horas_total': 0,
                'km_medio_uso': 0, 'maior_viagem': 0, 'menor_viagem': 0,
                'km_por_dia': 0, 'usos_por_dia': 0, 'eficiencia_temporal': 0
            }
        
        # Métricas derivadas
        dias_periodo = (data_fim - data_inicio).days + 1
        km_por_dia = float(dados.km_total) / max(dados.dias_ativos, 1)
        usos_por_dia = dados.total_usos / max(dados.dias_ativos, 1)
        eficiencia_temporal = float(dados.km_total) / max(float(dados.horas_total), 1)
        
        return {
            'total_usos': dados.total_usos,
            'veiculos_utilizados': dados.veiculos_utilizados,
            'dias_ativos': dados.dias_ativos,
            'funcionarios_ativos': dados.funcionarios_ativos,
            'km_total': float(dados.km_total or 0),
            'horas_total': float(dados.horas_total or 0),
            'km_medio_uso': round(float(dados.km_medio_uso or 0), 2),
            'maior_viagem': float(dados.maior_viagem or 0),
            'menor_viagem': float(dados.menor_viagem or 0),
            'km_por_dia': round(km_por_dia, 2),
            'usos_por_dia': round(usos_por_dia, 2),
            'eficiencia_temporal': round(eficiencia_temporal, 2),
            'dias_periodo': dias_periodo
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular métricas gerais: {e}")
        return {}

def analisar_uso_temporal(admin_id, data_inicio, data_fim):
    """Análise temporal do uso de veículos"""
    
    try:
        # Análise diária
        uso_diario = db.session.query(
            UsoVeiculo.data_uso,
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_dia'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_dia'),
            func.sum(UsoVeiculo.horas_uso).label('horas_dia')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(UsoVeiculo.data_uso)\
        .order_by(UsoVeiculo.data_uso).all()
        
        # Análise por dia da semana
        uso_semana = db.session.query(
            extract('dow', UsoVeiculo.data_uso).label('dia_semana'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio'),
            func.sum(UsoVeiculo.km_rodado).label('km_total')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(extract('dow', UsoVeiculo.data_uso))\
        .order_by('dia_semana').all()
        
        # Análise por horário
        uso_horario = db.session.query(
            extract('hour', UsoVeiculo.horario_saida).label('hora'),
            func.count(UsoVeiculo.id).label('total_usos'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.horario_saida.isnot(None)
        ).group_by(extract('hour', UsoVeiculo.horario_saida))\
        .order_by('hora').all()
        
        # Preparar dados
        nomes_dias = {0: 'Domingo', 1: 'Segunda', 2: 'Terça', 3: 'Quarta', 
                     4: 'Quinta', 5: 'Sexta', 6: 'Sábado'}
        
        temporal_diario = []
        for d in uso_diario:
            temporal_diario.append({
                'data': d.data_uso.strftime('%Y-%m-%d'),
                'total_usos': d.total_usos,
                'km_dia': float(d.km_dia or 0),
                'veiculos_dia': d.veiculos_dia,
                'horas_dia': float(d.horas_dia or 0)
            })
        
        temporal_semanal = []
        for d in uso_semana:
            temporal_semanal.append({
                'dia': nomes_dias.get(int(d.dia_semana), 'Desconhecido'),
                'total_usos': d.total_usos,
                'km_medio': round(float(d.km_medio or 0), 2),
                'km_total': float(d.km_total or 0)
            })
        
        temporal_horario = []
        for d in uso_horario:
            temporal_horario.append({
                'hora': int(d.hora),
                'total_usos': d.total_usos,
                'km_medio': round(float(d.km_medio or 0), 2)
            })
        
        return {
            'diario': temporal_diario,
            'semanal': temporal_semanal,
            'horario': temporal_horario
        }
        
    except Exception as e:
        logger.error(f"Erro na análise temporal: {e}")
        return {'diario': [], 'semanal': [], 'horario': []}

def analisar_uso_por_veiculo(admin_id, data_inicio, data_fim, veiculo_filtro=None):
    """Análise detalhada de uso por veículo"""
    
    try:
        query = db.session.query(
            Veiculo.id,
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            Veiculo.tipo,
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_ativo'),
            func.count(func.distinct(UsoVeiculo.funcionario_id)).label('funcionarios_distintos'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio_uso'),
            func.max(UsoVeiculo.km_rodado).label('maior_km_uso'),
            func.min(UsoVeiculo.km_rodado).label('menor_km_uso')
        ).select_from(Veiculo)\
        .outerjoin(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == Veiculo.id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .filter(Veiculo.admin_id == admin_id, Veiculo.ativo == True)
        
        if veiculo_filtro:
            query = query.filter(Veiculo.id == veiculo_filtro)
        
        dados = query.group_by(
            Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo, Veiculo.tipo
        ).all()
        
        uso_veiculos = []
        for d in dados:
            dias_periodo = (data_fim - data_inicio).days + 1
            utilizacao_periodo = (d.dias_ativo / dias_periodo) * 100 if d.dias_ativo and dias_periodo > 0 else 0
            km_por_dia = float(d.km_total or 0) / max(d.dias_ativo or 1, 1)
            
            uso_veiculos.append({
                'veiculo_id': d.id,
                'placa': d.placa,
                'marca': d.marca,
                'modelo': d.modelo,
                'tipo': d.tipo,
                'total_usos': d.total_usos or 0,
                'km_total': float(d.km_total or 0),
                'horas_total': float(d.horas_total or 0),
                'dias_ativo': d.dias_ativo or 0,
                'funcionarios_distintos': d.funcionarios_distintos or 0,
                'km_medio_uso': round(float(d.km_medio_uso or 0), 2),
                'maior_km_uso': float(d.maior_km_uso or 0),
                'menor_km_uso': float(d.menor_km_uso or 0),
                'utilizacao_periodo': round(utilizacao_periodo, 2),
                'km_por_dia': round(km_por_dia, 2)
            })
        
        return sorted(uso_veiculos, key=lambda x: x['km_total'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro na análise por veículo: {e}")
        return []

def analisar_uso_por_obra(admin_id, data_inicio, data_fim, obra_filtro=None):
    """Análise de uso por obra/projeto"""
    
    try:
        query = db.session.query(
            Obra.id,
            Obra.nome,
            Obra.codigo,
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados'),
            func.count(func.distinct(UsoVeiculo.funcionario_id)).label('funcionarios_ativos'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio_uso')
        ).select_from(Obra)\
        .join(AlocacaoVeiculo, AlocacaoVeiculo.obra_id == Obra.id)\
        .join(UsoVeiculo, and_(
            UsoVeiculo.veiculo_id == AlocacaoVeiculo.veiculo_id,
            UsoVeiculo.data_uso >= AlocacaoVeiculo.data_inicio,
            or_(
                AlocacaoVeiculo.data_fim.is_(None),
                UsoVeiculo.data_uso <= AlocacaoVeiculo.data_fim
            ),
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ))\
        .filter(Obra.admin_id == admin_id, Obra.ativo == True)
        
        if obra_filtro:
            query = query.filter(Obra.id == obra_filtro)
        
        dados = query.group_by(Obra.id, Obra.nome, Obra.codigo).all()
        
        uso_obras = []
        for d in dados:
            uso_obras.append({
                'obra_id': d.id,
                'nome': d.nome,
                'codigo': d.codigo,
                'total_usos': d.total_usos,
                'km_total': float(d.km_total or 0),
                'veiculos_utilizados': d.veiculos_utilizados,
                'funcionarios_ativos': d.funcionarios_ativos,
                'km_medio_uso': round(float(d.km_medio_uso or 0), 2)
            })
        
        return sorted(uso_obras, key=lambda x: x['km_total'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro na análise por obra: {e}")
        return []

def analisar_uso_por_funcionario(admin_id, data_inicio, data_fim, funcionario_filtro=None):
    """Análise de uso por funcionário"""
    
    try:
        query = db.session.query(
            Funcionario.id,
            Funcionario.nome,
            Funcionario.codigo,
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_utilizados'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_ativo'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio_uso'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total')
        ).select_from(Funcionario)\
        .join(UsoVeiculo, UsoVeiculo.funcionario_id == Funcionario.id)\
        .filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        )
        
        if funcionario_filtro:
            query = query.filter(Funcionario.id == funcionario_filtro)
        
        dados = query.group_by(
            Funcionario.id, Funcionario.nome, Funcionario.codigo
        ).all()
        
        uso_funcionarios = []
        for d in dados:
            km_por_dia = float(d.km_total or 0) / max(d.dias_ativo or 1, 1)
            
            uso_funcionarios.append({
                'funcionario_id': d.id,
                'nome': d.nome,
                'codigo': d.codigo,
                'total_usos': d.total_usos,
                'km_total': float(d.km_total or 0),
                'veiculos_utilizados': d.veiculos_utilizados,
                'dias_ativo': d.dias_ativo,
                'km_medio_uso': round(float(d.km_medio_uso or 0), 2),
                'horas_total': float(d.horas_total or 0),
                'km_por_dia': round(km_por_dia, 2)
            })
        
        return sorted(uso_funcionarios, key=lambda x: x['km_total'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro na análise por funcionário: {e}")
        return []

def identificar_padroes_uso(admin_id, data_inicio, data_fim):
    """Identifica padrões interessantes no uso da frota"""
    
    try:
        padroes = {}
        
        # Padrão 1: Veículos mais utilizados por período
        veiculos_periodo = db.session.query(
            extract('hour', UsoVeiculo.horario_saida).label('hora'),
            Veiculo.placa,
            func.count(UsoVeiculo.id).label('usos')
        ).join(Veiculo)\
        .filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.horario_saida.isnot(None)
        ).group_by(
            extract('hour', UsoVeiculo.horario_saida), Veiculo.placa
        ).having(func.count(UsoVeiculo.id) >= 3)\
        .order_by(desc('usos')).limit(10).all()
        
        # Padrão 2: Destinos mais frequentes
        destinos_frequentes = db.session.query(
            UsoVeiculo.destino,
            func.count(UsoVeiculo.id).label('frequencia'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio'),
            func.count(func.distinct(UsoVeiculo.veiculo_id)).label('veiculos_distintos')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.destino.isnot(None),
            UsoVeiculo.destino != ''
        ).group_by(UsoVeiculo.destino)\
        .having(func.count(UsoVeiculo.id) >= 3)\
        .order_by(desc('frequencia')).limit(15).all()
        
        # Padrão 3: Finalidades mais comuns
        finalidades_comuns = db.session.query(
            UsoVeiculo.finalidade,
            func.count(UsoVeiculo.id).label('total'),
            func.sum(UsoVeiculo.km_rodado).label('km_total')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.finalidade.isnot(None),
            UsoVeiculo.finalidade != ''
        ).group_by(UsoVeiculo.finalidade)\
        .order_by(desc('total')).limit(10).all()
        
        # Padrão 4: Sazonalidade semanal
        sazonalidade = db.session.query(
            extract('dow', UsoVeiculo.data_uso).label('dia_semana'),
            extract('hour', UsoVeiculo.horario_saida).label('hora'),
            func.count(UsoVeiculo.id).label('total_usos')
        ).filter(
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.horario_saida.isnot(None)
        ).group_by(
            extract('dow', UsoVeiculo.data_uso),
            extract('hour', UsoVeiculo.horario_saida)
        ).all()
        
        # Formatar dados
        padroes['veiculos_periodo'] = [{
            'hora': int(v.hora) if v.hora else 0,
            'placa': v.placa,
            'usos': v.usos
        } for v in veiculos_periodo]
        
        padroes['destinos_frequentes'] = [{
            'destino': d.destino,
            'frequencia': d.frequencia,
            'km_medio': round(float(d.km_medio or 0), 2),
            'veiculos_distintos': d.veiculos_distintos
        } for d in destinos_frequentes]
        
        padroes['finalidades_comuns'] = [{
            'finalidade': f.finalidade,
            'total': f.total,
            'km_total': float(f.km_total or 0)
        } for f in finalidades_comuns]
        
        # Criar mapa de calor de sazonalidade
        mapa_calor = defaultdict(lambda: defaultdict(int))
        for s in sazonalidade:
            dia = int(s.dia_semana) if s.dia_semana else 0
            hora = int(s.hora) if s.hora else 0
            mapa_calor[dia][hora] = s.total_usos
        
        padroes['sazonalidade'] = dict(mapa_calor)
        
        return padroes
        
    except Exception as e:
        logger.error(f"Erro ao identificar padrões: {e}")
        return {}

# ===== RELATÓRIOS ESPECÍFICOS =====

@uso_detalhado_bp.route('/veiculo/<int:veiculo_id>')
@login_required
@admin_required
def relatorio_veiculo_detalhado(veiculo_id):
    """Relatório detalhado de uso de um veículo específico"""
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
        # Histórico completo de uso
        historico_uso = obter_historico_uso_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Análise estatística
        analise_estatistica = analisar_estatisticas_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Padrões específicos do veículo
        padroes_veiculo = analisar_padroes_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        # Comparação com período anterior
        comparacao_periodo = comparar_periodo_anterior_veiculo(veiculo_id, admin_id, data_inicio, data_fim)
        
        return render_template('relatorios/uso/veiculo_detalhado.html',
                             veiculo=veiculo,
                             historico_uso=historico_uso,
                             analise_estatistica=analise_estatistica,
                             padroes_veiculo=padroes_veiculo,
                             comparacao_periodo=comparacao_periodo,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"Erro no relatório detalhado: {e}")
        flash('Erro ao carregar relatório detalhado', 'danger')
        return redirect(url_for('relatorios_uso.dashboard_uso'))

def obter_historico_uso_veiculo(veiculo_id, admin_id, data_inicio, data_fim):
    """Obtém histórico completo de uso do veículo"""
    
    try:
        historico = db.session.query(UsoVeiculo)\
        .options(joinedload(UsoVeiculo.funcionario_rel))\
        .filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).order_by(desc(UsoVeiculo.data_uso), desc(UsoVeiculo.horario_saida)).all()
        
        historico_formatado = []
        for uso in historico:
            historico_formatado.append({
                'id': uso.id,
                'data_uso': uso.data_uso.strftime('%d/%m/%Y'),
                'horario_saida': uso.horario_saida.strftime('%H:%M') if uso.horario_saida else '',
                'horario_chegada': uso.horario_chegada.strftime('%H:%M') if uso.horario_chegada else '',
                'km_inicial': uso.km_inicial,
                'km_final': uso.km_final,
                'km_rodado': uso.km_rodado,
                'horas_uso': float(uso.horas_uso or 0),
                'destino': uso.destino,
                'finalidade': uso.finalidade,
                'funcionario_nome': uso.funcionario_rel.nome if uso.funcionario_rel else 'N/A',
                'observacoes': uso.observacoes
            })
        
        return historico_formatado
        
    except Exception as e:
        logger.error(f"Erro ao obter histórico: {e}")
        return []

def analisar_estatisticas_veiculo(veiculo_id, admin_id, data_inicio, data_fim):
    """Análise estatística do uso do veículo"""
    
    try:
        # Estatísticas básicas
        stats = db.session.query(
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio'),
            func.min(UsoVeiculo.km_rodado).label('km_minimo'),
            func.max(UsoVeiculo.km_rodado).label('km_maximo'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total'),
            func.avg(UsoVeiculo.horas_uso).label('horas_media'),
            func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_ativo'),
            func.count(func.distinct(UsoVeiculo.funcionario_id)).label('funcionarios_distintos')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        if not stats or stats.total_usos == 0:
            return {'erro': 'Nenhum uso encontrado no período'}
        
        # Distribuição por faixas de KM
        distribuicao_km = db.session.query(
            case([
                (UsoVeiculo.km_rodado <= 50, '0-50 km'),
                (UsoVeiculo.km_rodado <= 100, '51-100 km'),
                (UsoVeiculo.km_rodado <= 200, '101-200 km'),
                (UsoVeiculo.km_rodado <= 500, '201-500 km')
            ], else_='500+ km').label('faixa'),
            func.count(UsoVeiculo.id).label('total')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by('faixa').all()
        
        dias_periodo = (data_fim - data_inicio).days + 1
        utilizacao_periodo = (stats.dias_ativo / dias_periodo) * 100
        
        return {
            'total_usos': stats.total_usos,
            'km_total': float(stats.km_total or 0),
            'km_medio': round(float(stats.km_medio or 0), 2),
            'km_minimo': float(stats.km_minimo or 0),
            'km_maximo': float(stats.km_maximo or 0),
            'horas_total': float(stats.horas_total or 0),
            'horas_media': round(float(stats.horas_media or 0), 2),
            'dias_ativo': stats.dias_ativo,
            'funcionarios_distintos': stats.funcionarios_distintos,
            'utilizacao_periodo': round(utilizacao_periodo, 2),
            'distribuicao_km': [{'faixa': d.faixa, 'total': d.total} for d in distribuicao_km]
        }
        
    except Exception as e:
        logger.error(f"Erro na análise estatística: {e}")
        return {'erro': 'Erro ao calcular estatísticas'}

def analisar_padroes_veiculo(veiculo_id, admin_id, data_inicio, data_fim):
    """Analisa padrões específicos do veículo"""
    
    try:
        padroes = {}
        
        # Horários preferidos
        horarios = db.session.query(
            extract('hour', UsoVeiculo.horario_saida).label('hora'),
            func.count(UsoVeiculo.id).label('total'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.horario_saida.isnot(None)
        ).group_by(extract('hour', UsoVeiculo.horario_saida))\
        .order_by('hora').all()
        
        # Funcionários que mais usam
        funcionarios = db.session.query(
            Funcionario.nome,
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total')
        ).join(UsoVeiculo)\
        .filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).group_by(Funcionario.nome)\
        .order_by(desc('total_usos')).limit(10).all()
        
        # Destinos mais frequentes
        destinos = db.session.query(
            UsoVeiculo.destino,
            func.count(UsoVeiculo.id).label('frequencia'),
            func.avg(UsoVeiculo.km_rodado).label('km_medio')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim,
            UsoVeiculo.destino.isnot(None),
            UsoVeiculo.destino != ''
        ).group_by(UsoVeiculo.destino)\
        .order_by(desc('frequencia')).limit(10).all()
        
        padroes['horarios_preferidos'] = [{
            'hora': int(h.hora) if h.hora else 0,
            'total': h.total,
            'km_medio': round(float(h.km_medio or 0), 2)
        } for h in horarios]
        
        padroes['funcionarios_frequentes'] = [{
            'nome': f.nome,
            'total_usos': f.total_usos,
            'km_total': float(f.km_total or 0)
        } for f in funcionarios]
        
        padroes['destinos_frequentes'] = [{
            'destino': d.destino,
            'frequencia': d.frequencia,
            'km_medio': round(float(d.km_medio or 0), 2)
        } for d in destinos]
        
        return padroes
        
    except Exception as e:
        logger.error(f"Erro na análise de padrões: {e}")
        return {}

def comparar_periodo_anterior_veiculo(veiculo_id, admin_id, data_inicio, data_fim):
    """Compara uso com período anterior"""
    
    try:
        dias_periodo = (data_fim - data_inicio).days + 1
        data_anterior_inicio = data_inicio - timedelta(days=dias_periodo)
        data_anterior_fim = data_inicio - timedelta(days=1)
        
        # Dados período atual
        atual = db.session.query(
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_inicio,
            UsoVeiculo.data_uso <= data_fim
        ).first()
        
        # Dados período anterior
        anterior = db.session.query(
            func.count(UsoVeiculo.id).label('total_usos'),
            func.sum(UsoVeiculo.km_rodado).label('km_total'),
            func.sum(UsoVeiculo.horas_uso).label('horas_total')
        ).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_anterior_inicio,
            UsoVeiculo.data_uso <= data_anterior_fim
        ).first()
        
        if not atual or not anterior:
            return {'erro': 'Dados insuficientes para comparação'}
        
        # Calcular variações
        def calcular_variacao(atual_val, anterior_val):
            if anterior_val and anterior_val > 0:
                return ((atual_val - anterior_val) / anterior_val) * 100
            return 0
        
        variacao_usos = calcular_variacao(atual.total_usos or 0, anterior.total_usos or 0)
        variacao_km = calcular_variacao(float(atual.km_total or 0), float(anterior.km_total or 0))
        variacao_horas = calcular_variacao(float(atual.horas_total or 0), float(anterior.horas_total or 0))
        
        return {
            'periodo_atual': {
                'total_usos': atual.total_usos or 0,
                'km_total': float(atual.km_total or 0),
                'horas_total': float(atual.horas_total or 0)
            },
            'periodo_anterior': {
                'total_usos': anterior.total_usos or 0,
                'km_total': float(anterior.km_total or 0),
                'horas_total': float(anterior.horas_total or 0)
            },
            'variacoes': {
                'usos': round(variacao_usos, 2),
                'km': round(variacao_km, 2),
                'horas': round(variacao_horas, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Erro na comparação: {e}")
        return {'erro': 'Erro ao comparar períodos'}

# ===== EXPORTAÇÃO =====

@uso_detalhado_bp.route('/exportar')
@login_required
@admin_required
def exportar_relatorio_uso():
    """Exporta relatório de uso para Excel"""
    admin_id = get_admin_id()
    
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    formato = request.args.get('formato', 'excel')
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        if formato == 'excel':
            return exportar_excel_uso(admin_id, data_inicio_obj, data_fim_obj)
        else:
            return exportar_csv_uso(admin_id, data_inicio_obj, data_fim_obj)
        
    except Exception as e:
        logger.error(f"Erro na exportação: {e}")
        flash('Erro ao exportar relatório', 'danger')
        return redirect(url_for('relatorios_uso.dashboard_uso'))

def exportar_excel_uso(admin_id, data_inicio, data_fim):
    """Exporta para Excel com múltiplas planilhas"""
    
    try:
        # Criar arquivo Excel em memória
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Planilha 1: Resumo geral
            metricas = calcular_metricas_uso_geral(admin_id, data_inicio, data_fim)
            df_resumo = pd.DataFrame([metricas])
            df_resumo.to_excel(writer, sheet_name='Resumo Geral', index=False)
            
            # Planilha 2: Uso por veículo
            uso_veiculos = analisar_uso_por_veiculo(admin_id, data_inicio, data_fim)
            df_veiculos = pd.DataFrame(uso_veiculos)
            df_veiculos.to_excel(writer, sheet_name='Uso por Veículo', index=False)
            
            # Planilha 3: Uso por obra
            uso_obras = analisar_uso_por_obra(admin_id, data_inicio, data_fim)
            df_obras = pd.DataFrame(uso_obras)
            df_obras.to_excel(writer, sheet_name='Uso por Obra', index=False)
            
            # Planilha 4: Uso por funcionário
            uso_funcionarios = analisar_uso_por_funcionario(admin_id, data_inicio, data_fim)
            df_funcionarios = pd.DataFrame(uso_funcionarios)
            df_funcionarios.to_excel(writer, sheet_name='Uso por Funcionário', index=False)
        
        output.seek(0)
        
        # Preparar resposta
        filename = f"relatorio_uso_{data_inicio}_{data_fim}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Erro ao exportar Excel: {e}")
        raise

# ===== APIS =====

@uso_detalhado_bp.route('/api/dados-uso')
@login_required
@admin_required
def api_dados_uso():
    """API para dados de uso via AJAX"""
    admin_id = get_admin_id()
    
    tipo = request.args.get('tipo', 'geral')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    veiculo_id = request.args.get('veiculo_id', type=int)
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        if tipo == 'temporal':
            dados = analisar_uso_temporal(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'veiculo':
            dados = analisar_uso_por_veiculo(admin_id, data_inicio_obj, data_fim_obj, veiculo_id)
        elif tipo == 'obra':
            dados = analisar_uso_por_obra(admin_id, data_inicio_obj, data_fim_obj)
        elif tipo == 'funcionario':
            dados = analisar_uso_por_funcionario(admin_id, data_inicio_obj, data_fim_obj)
        else:
            dados = calcular_metricas_uso_geral(admin_id, data_inicio_obj, data_fim_obj)
        
        return jsonify({
            'success': True,
            'dados': dados
        })
        
    except Exception as e:
        logger.error(f"Erro na API de uso: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500