from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import CustoObra, Obra, Funcionario, Vehicle, db
from sqlalchemy import func, desc, extract
from datetime import datetime, date

custos_bp = Blueprint('custos', __name__, url_prefix='/custos')

@custos_bp.route('/')
@login_required
def dashboard_custos():
    admin_id = current_user.id
    
    # KPIs principais
    total_custos = db.session.query(func.sum(CustoObra.valor)).filter_by(admin_id=admin_id).scalar() or 0
    
    # Custos por categoria (campo correto: 'tipo')
    custos_categoria = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=admin_id).group_by(CustoObra.tipo).all()
    
    # Custos por mês (últimos 6 meses) - PostgreSQL compatible
    custos_mensais = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=admin_id).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by(desc('mes')).limit(6).all()
    
    # Top 5 obras por custo
    top_obras = db.session.query(
        Obra.nome,
        Obra.id,
        func.sum(CustoObra.valor).label('total_custos')
    ).join(CustoObra).filter(
        CustoObra.admin_id == admin_id,
        Obra.admin_id == admin_id
    ).group_by(Obra.id, Obra.nome).order_by(
        desc('total_custos')
    ).limit(5).all()
    
    # Estatísticas gerais
    total_obras = Obra.query.filter_by(admin_id=admin_id).count()
    obras_com_custos = db.session.query(CustoObra.obra_id).filter_by(admin_id=admin_id).distinct().count()
    
    return render_template('custos/dashboard.html',
                         total_custos=total_custos,
                         custos_categoria=custos_categoria,
                         custos_mensais=custos_mensais,
                         top_obras=top_obras,
                         total_obras=total_obras,
                         obras_com_custos=obras_com_custos)

@custos_bp.route('/obra/<int:obra_id>')
@login_required
def custos_obra(obra_id):
    obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first_or_404()
    
    # Buscar todos os custos da obra
    custos = CustoObra.query.filter_by(
        obra_id=obra_id,
        admin_id=current_user.id
    ).order_by(desc(CustoObra.data)).all()
    
    # Agrupar custos por tipo
    custos_agrupados = {}
    total_geral = 0
    
    for custo in custos:
        tipo = custo.tipo
        if tipo not in custos_agrupados:
            custos_agrupados[tipo] = {
                'custos': [],
                'total': 0,
                'quantidade': 0
            }
        custos_agrupados[tipo]['custos'].append(custo)
        custos_agrupados[tipo]['total'] += custo.valor
        custos_agrupados[tipo]['quantidade'] += 1
        total_geral += custo.valor
    
    # Calcular margem
    margem_valor = 0
    margem_percentual = 0
    if obra.valor_contrato and obra.valor_contrato > 0:
        margem_valor = obra.valor_contrato - total_geral
        margem_percentual = (margem_valor / obra.valor_contrato) * 100
    
    # Custos por mês nesta obra
    custos_mensais_obra = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(
        obra_id=obra_id,
        admin_id=current_user.id
    ).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by('mes').all()
    
    return render_template('custos/obra.html',
                         obra=obra,
                         custos_agrupados=custos_agrupados,
                         total_geral=total_geral,
                         margem_valor=margem_valor,
                         margem_percentual=margem_percentual,
                         custos_mensais_obra=custos_mensais_obra,
                         total_custos=len(custos))

@custos_bp.route('/api/custos-categoria')
@login_required
def api_custos_categoria():
    custos = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=current_user.id).group_by(CustoObra.tipo).all()
    
    # Mapear nomes amigáveis
    nomes_tipos = {
        'mao_obra': 'Mão de Obra',
        'material': 'Material',
        'veiculo': 'Veículo',
        'servico': 'Serviço',
        'alimentacao': 'Alimentação'
    }
    
    return jsonify({
        'labels': [nomes_tipos.get(c[0], c[0]) for c in custos],
        'data': [float(c[1]) for c in custos],
        'colors': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']
    })

@custos_bp.route('/api/custos-mensais')
@login_required
def api_custos_mensais():
    custos = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=current_user.id).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by('mes').limit(12).all()
    
    return jsonify({
        'labels': [c[0] for c in custos],
        'data': [float(c[1]) for c in custos]
    })
