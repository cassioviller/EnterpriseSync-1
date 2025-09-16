"""
RELATÓRIOS GERENCIAIS - INTEGRAÇÃO VEÍCULOS-OBRAS - SIGE v8.0
Relatórios avançados para análise de custos, eficiência e ROI
"""

from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_, text, extract
from io import BytesIO
import csv
import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Importar modelos
from models import (
    db, Veiculo, AlocacaoVeiculo, EquipeVeiculo, TransferenciaVeiculo,
    UsoVeiculo, CustoVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required

# Criação do Blueprint
relatorios_bp = Blueprint('veiculos_relatorios', __name__, url_prefix='/relatorios/veiculos-obra')

def get_admin_id():
    """Obtém admin_id do usuário atual"""
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario.value == 'admin':
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return current_user.id

# ===== RELATÓRIOS PRINCIPAIS =====

@relatorios_bp.route('/')
@login_required
@admin_required
def index_relatorios():
    """Página inicial dos relatórios"""
    admin_id = get_admin_id()
    
    # Estatísticas resumidas para a página inicial
    stats = {
        'veiculos_total': Veiculo.query.filter_by(admin_id=admin_id, ativo=True).count(),
        'obras_com_veiculos': db.session.query(func.count(func.distinct(AlocacaoVeiculo.obra_id))).filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).scalar(),
        'alocacoes_ativas': AlocacaoVeiculo.query.filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).count(),
        'custo_mes_atual': 0
    }
    
    # Custo do mês atual
    mes_atual = date.today().replace(day=1)
    proximo_mes = (mes_atual + timedelta(days=32)).replace(day=1)
    
    custo_mes = db.session.query(func.sum(CustoVeiculo.valor)).filter(
        CustoVeiculo.admin_id == admin_id,
        CustoVeiculo.data_custo >= mes_atual,
        CustoVeiculo.data_custo < proximo_mes
    ).scalar()
    
    stats['custo_mes_atual'] = custo_mes or 0
    
    return render_template('veiculos_obra/relatorios/index.html', stats=stats)

@relatorios_bp.route('/custo-por-obra')
@login_required
@admin_required
def relatorio_custo_obra():
    """Relatório de custos de veículos por obra"""
    admin_id = get_admin_id()
    
    # Parâmetros de filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    obra_id = request.args.get('obra_id', type=int)
    
    # Definir período padrão (último mês)
    if not data_inicio:
        data_inicio = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not data_fim:
        data_fim = date.today().strftime('%Y-%m-%d')
    
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Query base para custos por obra
    query = db.session.query(
        Obra.nome.label('obra_nome'),
        Obra.id.label('obra_id'),
        Veiculo.placa.label('veiculo_placa'),
        Veiculo.marca.label('veiculo_marca'),
        Veiculo.modelo.label('veiculo_modelo'),
        func.sum(CustoVeiculo.valor).label('custo_total'),
        func.count(CustoVeiculo.id).label('total_registros'),
        func.sum(func.case([(CustoVeiculo.tipo_custo == 'combustivel', CustoVeiculo.valor)], else_=0)).label('custo_combustivel'),
        func.sum(func.case([(CustoVeiculo.tipo_custo == 'manutencao', CustoVeiculo.valor)], else_=0)).label('custo_manutencao'),
        func.sum(func.case([(CustoVeiculo.tipo_custo == 'outros', CustoVeiculo.valor)], else_=0)).label('custo_outros')
    ).select_from(CustoVeiculo)\
    .join(Veiculo, CustoVeiculo.veiculo_id == Veiculo.id)\
    .join(Obra, CustoVeiculo.obra_id == Obra.id)\
    .filter(
        CustoVeiculo.admin_id == admin_id,
        CustoVeiculo.data_custo >= data_inicio_obj,
        CustoVeiculo.data_custo <= data_fim_obj
    )
    
    # Aplicar filtro de obra se especificado
    if obra_id:
        query = query.filter(Obra.id == obra_id)
    
    # Agrupar por obra e veículo
    custos_detalhados = query.group_by(
        Obra.nome, Obra.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo
    ).order_by(Obra.nome, Veiculo.placa).all()
    
    # Resumo por obra
    resumo_obras = db.session.query(
        Obra.nome.label('obra_nome'),
        Obra.id.label('obra_id'),
        func.sum(CustoVeiculo.valor).label('custo_total'),
        func.count(func.distinct(CustoVeiculo.veiculo_id)).label('total_veiculos'),
        func.avg(CustoVeiculo.valor).label('custo_medio')
    ).select_from(CustoVeiculo)\
    .join(Obra, CustoVeiculo.obra_id == Obra.id)\
    .filter(
        CustoVeiculo.admin_id == admin_id,
        CustoVeiculo.data_custo >= data_inicio_obj,
        CustoVeiculo.data_custo <= data_fim_obj
    ).group_by(Obra.nome, Obra.id)\
    .order_by(desc('custo_total')).all()
    
    # Lista de obras para filtro
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template('veiculos_obra/relatorios/custo_obra.html',
                         custos_detalhados=custos_detalhados,
                         resumo_obras=resumo_obras,
                         obras=obras,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         obra_id=obra_id)

@relatorios_bp.route('/eficiencia-veiculos')
@login_required
@admin_required
def relatorio_eficiencia():
    """Relatório de eficiência de veículos por obra"""
    admin_id = get_admin_id()
    
    # Parâmetros de filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (último mês)
    if not data_inicio:
        data_inicio = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not data_fim:
        data_fim = date.today().strftime('%Y-%m-%d')
    
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Query para dados de eficiência
    eficiencia_data = db.session.query(
        Obra.nome.label('obra_nome'),
        Veiculo.placa.label('veiculo_placa'),
        Veiculo.marca.label('veiculo_marca'),
        Veiculo.modelo.label('veiculo_modelo'),
        func.sum(UsoVeiculo.km_percorrido).label('km_total'),
        func.sum(UsoVeiculo.horas_uso).label('horas_total'),
        func.count(UsoVeiculo.id).label('total_usos'),
        func.avg(UsoVeiculo.km_percorrido).label('km_medio_por_uso'),
        func.sum(CustoVeiculo.valor).label('custo_total')
    ).select_from(UsoVeiculo)\
    .join(Veiculo, UsoVeiculo.veiculo_id == Veiculo.id)\
    .join(Obra, UsoVeiculo.obra_id == Obra.id)\
    .outerjoin(CustoVeiculo, and_(
        CustoVeiculo.veiculo_id == UsoVeiculo.veiculo_id,
        CustoVeiculo.obra_id == UsoVeiculo.obra_id,
        CustoVeiculo.data_custo == UsoVeiculo.data_uso
    ))\
    .filter(
        UsoVeiculo.admin_id == admin_id,
        UsoVeiculo.data_uso >= data_inicio_obj,
        UsoVeiculo.data_uso <= data_fim_obj
    ).group_by(
        Obra.nome, Veiculo.placa, Veiculo.marca, Veiculo.modelo
    ).order_by(desc('km_total')).all()
    
    # Calcular métricas de eficiência
    eficiencia_processada = []
    for row in eficiencia_data:
        eficiencia = {
            'obra_nome': row.obra_nome,
            'veiculo_placa': row.veiculo_placa,
            'veiculo_marca': row.veiculo_marca,
            'veiculo_modelo': row.veiculo_modelo,
            'km_total': row.km_total or 0,
            'horas_total': row.horas_total or 0,
            'total_usos': row.total_usos or 0,
            'km_medio_por_uso': round(row.km_medio_por_uso or 0, 2),
            'custo_total': row.custo_total or 0,
            'custo_por_km': 0,
            'km_por_hora': 0,
            'eficiencia_score': 0
        }
        
        # Calcular métricas derivadas
        if eficiencia['km_total'] > 0:
            if eficiencia['custo_total'] > 0:
                eficiencia['custo_por_km'] = round(eficiencia['custo_total'] / eficiencia['km_total'], 2)
            if eficiencia['horas_total'] > 0:
                eficiencia['km_por_hora'] = round(eficiencia['km_total'] / eficiencia['horas_total'], 2)
        
        # Score de eficiência (baseado em KM/custo e utilização)
        if eficiencia['custo_total'] > 0 and eficiencia['km_total'] > 0:
            km_custo_ratio = eficiencia['km_total'] / eficiencia['custo_total']
            utilizacao = min(eficiencia['total_usos'] / 30, 1)  # Máximo 1 uso por dia
            eficiencia['eficiencia_score'] = round((km_custo_ratio * utilizacao) * 100, 1)
        
        eficiencia_processada.append(eficiencia)
    
    # Ranking de eficiência
    eficiencia_processada.sort(key=lambda x: x['eficiencia_score'], reverse=True)
    
    return render_template('veiculos_obra/relatorios/eficiencia.html',
                         dados_eficiencia=eficiencia_processada,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@relatorios_bp.route('/roi-veiculos')
@login_required
@admin_required
def relatorio_roi():
    """Relatório de ROI (Return on Investment) de veículos por projeto"""
    admin_id = get_admin_id()
    
    # Parâmetros de filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (últimos 3 meses)
    if not data_inicio:
        data_inicio = (date.today() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not data_fim:
        data_fim = date.today().strftime('%Y-%m-%d')
    
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Query para dados de ROI por obra
    roi_data = db.session.query(
        Obra.nome.label('obra_nome'),
        Obra.id.label('obra_id'),
        Obra.valor_contrato.label('valor_contrato'),
        func.sum(CustoVeiculo.valor).label('custo_veiculos_total'),
        func.count(func.distinct(AlocacaoVeiculo.veiculo_id)).label('veiculos_utilizados'),
        func.sum(AlocacaoVeiculo.dias_alocado).label('dias_alocacao_total'),
        func.avg(AlocacaoVeiculo.dias_alocado).label('dias_alocacao_medio')
    ).select_from(Obra)\
    .outerjoin(AlocacaoVeiculo, Obra.id == AlocacaoVeiculo.obra_id)\
    .outerjoin(CustoVeiculo, and_(
        CustoVeiculo.obra_id == Obra.id,
        CustoVeiculo.data_custo >= data_inicio_obj,
        CustoVeiculo.data_custo <= data_fim_obj
    ))\
    .filter(
        Obra.admin_id == admin_id,
        Obra.ativo == True
    ).group_by(
        Obra.nome, Obra.id, Obra.valor_contrato
    ).order_by(desc('custo_veiculos_total')).all()
    
    # Processar dados de ROI
    roi_processado = []
    for row in roi_data:
        roi = {
            'obra_nome': row.obra_nome,
            'obra_id': row.obra_id,
            'valor_contrato': row.valor_contrato or 0,
            'custo_veiculos_total': row.custo_veiculos_total or 0,
            'veiculos_utilizados': row.veiculos_utilizados or 0,
            'dias_alocacao_total': row.dias_alocacao_total or 0,
            'dias_alocacao_medio': round(row.dias_alocacao_medio or 0, 1),
            'percentual_custo_veiculo': 0,
            'custo_veiculo_por_dia': 0,
            'roi_veiculo': 0,
            'eficiencia_operacional': ''
        }
        
        # Calcular métricas derivadas
        if roi['valor_contrato'] > 0 and roi['custo_veiculos_total'] > 0:
            roi['percentual_custo_veiculo'] = round(
                (roi['custo_veiculos_total'] / roi['valor_contrato']) * 100, 2
            )
        
        if roi['dias_alocacao_total'] > 0 and roi['custo_veiculos_total'] > 0:
            roi['custo_veiculo_por_dia'] = round(
                roi['custo_veiculos_total'] / roi['dias_alocacao_total'], 2
            )
        
        # ROI simplificado (receita por real gasto em veículo)
        if roi['custo_veiculos_total'] > 0:
            roi['roi_veiculo'] = round(roi['valor_contrato'] / roi['custo_veiculos_total'], 2)
        
        # Classificação de eficiência operacional
        if roi['percentual_custo_veiculo'] <= 5:
            roi['eficiencia_operacional'] = 'Excelente'
        elif roi['percentual_custo_veiculo'] <= 10:
            roi['eficiencia_operacional'] = 'Boa'
        elif roi['percentual_custo_veiculo'] <= 15:
            roi['eficiencia_operacional'] = 'Regular'
        else:
            roi['eficiencia_operacional'] = 'Precisa melhorar'
        
        roi_processado.append(roi)
    
    # Ordenar por ROI
    roi_processado.sort(key=lambda x: x['roi_veiculo'], reverse=True)
    
    return render_template('veiculos_obra/relatorios/roi.html',
                         dados_roi=roi_processado,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@relatorios_bp.route('/utilizacao-veiculos')
@login_required
@admin_required
def relatorio_utilizacao():
    """Relatório de análise de utilização de veículos"""
    admin_id = get_admin_id()
    
    # Parâmetros de filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (último mês)
    if not data_inicio:
        data_inicio = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not data_fim:
        data_fim = date.today().strftime('%Y-%m-%d')
    
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    dias_periodo = (data_fim_obj - data_inicio_obj).days + 1
    
    # Query para análise de utilização
    utilizacao_data = db.session.query(
        Veiculo.id.label('veiculo_id'),
        Veiculo.placa.label('veiculo_placa'),
        Veiculo.marca.label('veiculo_marca'),
        Veiculo.modelo.label('veiculo_modelo'),
        Veiculo.tipo.label('veiculo_tipo'),
        func.count(func.distinct(AlocacaoVeiculo.id)).label('alocacoes_periodo'),
        func.sum(func.datediff(
            func.coalesce(AlocacaoVeiculo.data_fim, func.current_date()),
            AlocacaoVeiculo.data_inicio
        )).label('dias_alocado_total'),
        func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_com_uso'),
        func.sum(UsoVeiculo.km_percorrido).label('km_total'),
        func.count(UsoVeiculo.id).label('total_usos')
    ).select_from(Veiculo)\
    .outerjoin(AlocacaoVeiculo, and_(
        AlocacaoVeiculo.veiculo_id == Veiculo.id,
        AlocacaoVeiculo.data_inicio <= data_fim_obj,
        or_(AlocacaoVeiculo.data_fim >= data_inicio_obj, AlocacaoVeiculo.data_fim.is_(None))
    ))\
    .outerjoin(UsoVeiculo, and_(
        UsoVeiculo.veiculo_id == Veiculo.id,
        UsoVeiculo.data_uso >= data_inicio_obj,
        UsoVeiculo.data_uso <= data_fim_obj
    ))\
    .filter(
        Veiculo.admin_id == admin_id,
        Veiculo.ativo == True
    ).group_by(
        Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo, Veiculo.tipo
    ).order_by(Veiculo.placa).all()
    
    # Processar dados de utilização
    utilizacao_processada = []
    for row in utilizacao_data:
        utilizacao = {
            'veiculo_id': row.veiculo_id,
            'veiculo_placa': row.veiculo_placa,
            'veiculo_marca': row.veiculo_marca,
            'veiculo_modelo': row.veiculo_modelo,
            'veiculo_tipo': row.veiculo_tipo,
            'alocacoes_periodo': row.alocacoes_periodo or 0,
            'dias_alocado_total': row.dias_alocado_total or 0,
            'dias_com_uso': row.dias_com_uso or 0,
            'km_total': row.km_total or 0,
            'total_usos': row.total_usos or 0,
            'percentual_utilizacao': 0,
            'percentual_uso_efetivo': 0,
            'km_medio_por_dia': 0,
            'classificacao_utilizacao': ''
        }
        
        # Calcular métricas de utilização
        if dias_periodo > 0:
            utilizacao['percentual_utilizacao'] = round(
                (utilizacao['dias_alocado_total'] / dias_periodo) * 100, 1
            )
        
        if utilizacao['dias_alocado_total'] > 0:
            utilizacao['percentual_uso_efetivo'] = round(
                (utilizacao['dias_com_uso'] / utilizacao['dias_alocado_total']) * 100, 1
            )
        
        if utilizacao['dias_com_uso'] > 0:
            utilizacao['km_medio_por_dia'] = round(
                utilizacao['km_total'] / utilizacao['dias_com_uso'], 1
            )
        
        # Classificação da utilização
        if utilizacao['percentual_utilizacao'] >= 80:
            utilizacao['classificacao_utilizacao'] = 'Alta utilização'
        elif utilizacao['percentual_utilizacao'] >= 50:
            utilizacao['classificacao_utilizacao'] = 'Utilização moderada'
        elif utilizacao['percentual_utilizacao'] >= 20:
            utilizacao['classificacao_utilizacao'] = 'Baixa utilização'
        else:
            utilizacao['classificacao_utilizacao'] = 'Subutilizado'
        
        utilizacao_processada.append(utilizacao)
    
    # Estatísticas gerais
    stats_gerais = {
        'total_veiculos': len(utilizacao_processada),
        'veiculos_alta_utilizacao': len([v for v in utilizacao_processada if v['percentual_utilizacao'] >= 80]),
        'veiculos_subutilizados': len([v for v in utilizacao_processada if v['percentual_utilizacao'] < 20]),
        'utilizacao_media': round(sum([v['percentual_utilizacao'] for v in utilizacao_processada]) / len(utilizacao_processada), 1) if utilizacao_processada else 0
    }
    
    return render_template('veiculos_obra/relatorios/utilizacao.html',
                         dados_utilizacao=utilizacao_processada,
                         stats_gerais=stats_gerais,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         dias_periodo=dias_periodo)

# ===== EXPORTAÇÃO DE RELATÓRIOS =====

@relatorios_bp.route('/exportar/<tipo_relatorio>')
@login_required
@admin_required
def exportar_relatorio(tipo_relatorio):
    """Exportar relatórios em diferentes formatos"""
    admin_id = get_admin_id()
    formato = request.args.get('formato', 'csv')
    
    # Validar tipo de relatório
    tipos_validos = ['custo-obra', 'eficiencia', 'roi', 'utilizacao']
    if tipo_relatorio not in tipos_validos:
        flash('Tipo de relatório inválido', 'danger')
        return redirect(url_for('veiculos_relatorios.index_relatorios'))
    
    try:
        if formato == 'csv':
            return exportar_csv(tipo_relatorio, admin_id)
        elif formato == 'pdf':
            return exportar_pdf(tipo_relatorio, admin_id)
        else:
            flash('Formato de exportação inválido', 'danger')
            return redirect(url_for('veiculos_relatorios.index_relatorios'))
    
    except Exception as e:
        print(f"Erro ao exportar relatório: {e}")
        flash('Erro ao exportar relatório', 'danger')
        return redirect(url_for('veiculos_relatorios.index_relatorios'))

def exportar_csv(tipo_relatorio, admin_id):
    """Exportar relatório em formato CSV"""
    output = BytesIO()
    writer = csv.writer(output)
    
    # Headers específicos por tipo de relatório
    if tipo_relatorio == 'custo-obra':
        writer.writerow(['Obra', 'Veículo', 'Custo Total', 'Combustível', 'Manutenção', 'Outros'])
        # Implementar query específica
    elif tipo_relatorio == 'eficiencia':
        writer.writerow(['Obra', 'Veículo', 'KM Total', 'Horas Total', 'Custo/KM', 'Score Eficiência'])
        # Implementar query específica
    # ... outros tipos
    
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f'relatorio_{tipo_relatorio}_{date.today().strftime("%Y%m%d")}.csv',
        mimetype='text/csv'
    )

def exportar_pdf(tipo_relatorio, admin_id):
    """Exportar relatório em formato PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título do relatório
    titulo = f"Relatório de {tipo_relatorio.title().replace('-', ' ')}"
    elements.append(Paragraph(titulo, styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Data do relatório
    data_relatorio = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    elements.append(Paragraph(data_relatorio, styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Implementar conteúdo específico por tipo de relatório
    # ...
    
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'relatorio_{tipo_relatorio}_{date.today().strftime("%Y%m%d")}.pdf',
        mimetype='application/pdf'
    )

# ===== APIS PARA DASHBOARDS =====

@relatorios_bp.route('/api/dashboard-data')
@login_required
@admin_required
def api_dashboard_data():
    """API para dados do dashboard em formato JSON"""
    admin_id = get_admin_id()
    
    try:
        # Dados para gráficos
        data = {
            'custos_por_mes': obter_custos_por_mes(admin_id),
            'veiculos_por_obra': obter_veiculos_por_obra(admin_id),
            'eficiencia_mensal': obter_eficiencia_mensal(admin_id),
            'utilizacao_frota': obter_utilizacao_frota(admin_id)
        }
        
        return jsonify(data)
    
    except Exception as e:
        print(f"Erro na API de dashboard: {e}")
        return jsonify({'error': 'Erro ao carregar dados'}), 500

def obter_custos_por_mes(admin_id):
    """Obter custos de veículos por mês"""
    # Últimos 6 meses
    custos_mes = db.session.query(
        extract('month', CustoVeiculo.data_custo).label('mes'),
        extract('year', CustoVeiculo.data_custo).label('ano'),
        func.sum(CustoVeiculo.valor).label('total')
    ).filter(
        CustoVeiculo.admin_id == admin_id,
        CustoVeiculo.data_custo >= date.today() - timedelta(days=180)
    ).group_by(
        extract('year', CustoVeiculo.data_custo),
        extract('month', CustoVeiculo.data_custo)
    ).order_by('ano', 'mes').all()
    
    return [{'mes': f"{int(c.mes):02d}/{int(c.ano)}", 'valor': float(c.total or 0)} for c in custos_mes]

def obter_veiculos_por_obra(admin_id):
    """Obter quantidade de veículos por obra"""
    veiculos_obra = db.session.query(
        Obra.nome.label('obra'),
        func.count(AlocacaoVeiculo.id).label('total')
    ).join(AlocacaoVeiculo).filter(
        Obra.admin_id == admin_id,
        AlocacaoVeiculo.ativo == True,
        AlocacaoVeiculo.data_fim.is_(None)
    ).group_by(Obra.nome).order_by(desc('total')).limit(10).all()
    
    return [{'obra': v.obra, 'total': v.total} for v in veiculos_obra]

def obter_eficiencia_mensal(admin_id):
    """Obter dados de eficiência mensal"""
    # Implementar cálculo de eficiência por mês
    return []

def obter_utilizacao_frota(admin_id):
    """Obter dados de utilização da frota"""
    utilizacao = db.session.query(
        Veiculo.status.label('status'),
        func.count(Veiculo.id).label('total')
    ).filter(
        Veiculo.admin_id == admin_id,
        Veiculo.ativo == True
    ).group_by(Veiculo.status).all()
    
    return [{'status': u.status, 'total': u.total} for u in utilizacao]

print("✅ Sistema de relatórios gerenciais carregado com sucesso")