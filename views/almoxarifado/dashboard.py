from flask import flash, redirect, render_template, url_for
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento, Funcionario
from . import almoxarifado_bp, get_admin_id


@almoxarifado_bp.route('/')
@login_required
def dashboard():
    """Dashboard principal do almoxarifado v3.0 - KPIs, alertas e movimentações"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # ========================================
    # KPI 1: Total de Itens Cadastrados
    # ========================================
    total_itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).count()
    
    # ========================================
    # KPI 2: Estoque Baixo
    # ========================================
    itens_estoque_baixo = []
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).all()
    
    for item in itens:
        if item.tipo_controle == 'SERIALIZADO':
            estoque_atual = AlmoxarifadoEstoque.query.filter_by(
                item_id=item.id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).count()
        else:
            estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                item_id=item.id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).scalar() or 0
        
        # Tratar estoque_minimo NULL (padronizar como 0)
        estoque_minimo = item.estoque_minimo if item.estoque_minimo is not None else 0
        if estoque_atual < estoque_minimo:
            itens_estoque_baixo.append({
                'item': item,
                'estoque_atual': estoque_atual,
                'estoque_minimo': estoque_minimo
            })
    
    estoque_baixo = len(itens_estoque_baixo)
    
    # ========================================
    # KPI 3: Movimentações Hoje
    # ========================================
    hoje = datetime.now().date()
    movimentos_hoje = AlmoxarifadoMovimento.query.filter(
        AlmoxarifadoMovimento.admin_id == admin_id,
        func.date(AlmoxarifadoMovimento.data_movimento) == hoje
    ).count()
    
    # ========================================
    # KPI 4: Valor Total em Estoque
    # ========================================
    valor_total = db.session.query(
        func.sum(AlmoxarifadoEstoque.valor_unitario * AlmoxarifadoEstoque.quantidade)
    ).filter_by(
        status='DISPONIVEL',
        admin_id=admin_id
    ).scalar() or 0
    
    # ========================================
    # ALERTAS
    # ========================================
    
    # Alerta 1: Itens Vencendo (30 dias)
    data_limite_vencimento = datetime.now().date() + timedelta(days=30)
    itens_vencendo = AlmoxarifadoEstoque.query.filter(
        AlmoxarifadoEstoque.admin_id == admin_id,
        AlmoxarifadoEstoque.status == 'DISPONIVEL',
        AlmoxarifadoEstoque.data_validade.isnot(None),
        AlmoxarifadoEstoque.data_validade <= data_limite_vencimento
    ).join(AlmoxarifadoItem).all()
    
    # Alerta 2: Itens em Manutenção
    itens_manutencao = AlmoxarifadoEstoque.query.filter_by(
        admin_id=admin_id,
        status='EM_MANUTENCAO'
    ).join(AlmoxarifadoItem).all()
    
    # ========================================
    # ÚLTIMAS 10 MOVIMENTAÇÕES
    # ========================================
    ultimas_movimentacoes = AlmoxarifadoMovimento.query.filter_by(
        admin_id=admin_id
    ).join(
        AlmoxarifadoItem
    ).outerjoin(
        Funcionario, AlmoxarifadoMovimento.funcionario_id == Funcionario.id
    ).order_by(
        AlmoxarifadoMovimento.data_movimento.desc()
    ).limit(10).all()
    
    return render_template('almoxarifado/dashboard.html',
                         total_itens=total_itens,
                         estoque_baixo=estoque_baixo,
                         movimentos_hoje=movimentos_hoje,
                         valor_total=valor_total,
                         itens_estoque_baixo=itens_estoque_baixo,
                         itens_vencendo=itens_vencendo,
                         itens_manutencao=itens_manutencao,
                         ultimas_movimentacoes=ultimas_movimentacoes)
