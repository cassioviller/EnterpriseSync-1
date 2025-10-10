from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento
from models import Funcionario, Obra, Usuario
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import logging

logger = logging.getLogger(__name__)

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')

def get_admin_id():
    """Retorna admin_id do usuário atual"""
    if hasattr(current_user, 'perfil'):
        if current_user.perfil == 'admin':
            return current_user.id
        elif current_user.perfil == 'funcionario' and current_user.admin_id:
            return current_user.admin_id
    return None

@almoxarifado_bp.route('/')
@login_required
def dashboard():
    """Dashboard principal do almoxarifado - KPIs e ações rápidas"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('home'))
    
    # KPIs básicos (será expandido na FASE 5)
    total_itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).count()
    estoque_baixo = 0
    movimentos_hoje = 0
    valor_total = 0
    
    return render_template('almoxarifado/dashboard.html',
                         total_itens=total_itens,
                         estoque_baixo=estoque_baixo,
                         movimentos_hoje=movimentos_hoje,
                         valor_total=valor_total)

@almoxarifado_bp.route('/categorias')
@login_required
def categorias():
    """STUB - Será implementado na FASE 3"""
    flash('Módulo em desenvolvimento - FASE 3', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/itens')
@login_required
def itens():
    """STUB - Será implementado na FASE 3"""
    flash('Módulo em desenvolvimento - FASE 3', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/entrada')
@login_required
def entrada():
    """STUB - Será implementado na FASE 4"""
    flash('Módulo em desenvolvimento - FASE 4', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/saida')
@login_required
def saida():
    """STUB - Será implementado na FASE 4"""
    flash('Módulo em desenvolvimento - FASE 4', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/devolucao')
@login_required
def devolucao():
    """STUB - Será implementado na FASE 4"""
    flash('Módulo em desenvolvimento - FASE 4', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/movimentacoes')
@login_required
def movimentacoes():
    """STUB - Será implementado na FASE 5"""
    flash('Módulo em desenvolvimento - FASE 5', 'info')
    return redirect(url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/relatorios')
@login_required
def relatorios():
    """STUB - Será implementado na FASE 5"""
    flash('Módulo em desenvolvimento - FASE 5', 'info')
    return redirect(url_for('almoxarifado.dashboard'))
