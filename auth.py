from functools import wraps
from flask import session, redirect, url_for, flash, abort
from flask_login import current_user
from models import TipoUsuario

def super_admin_required(f):
    """Decorator para rotas que requerem acesso de super admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acesso negado. Faça login primeiro.', 'danger')
            return redirect(url_for('main.login'))
        
        if current_user.tipo_usuario != TipoUsuario.SUPER_ADMIN:
            flash('Acesso negado. Apenas super admin pode acessar esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para rotas que requerem acesso de admin ou superior"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acesso negado. Faça login primeiro.', 'danger')
            return redirect(url_for('main.login'))
        
        if current_user.tipo_usuario not in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN]:
            flash('Acesso negado. Acesso restrito a administradores.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def funcionario_required(f):
    """Decorator para rotas que requerem autenticação básica"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acesso negado. Faça login primeiro.', 'danger')
            return redirect(url_for('main.login'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_tenant_filter():
    """Retorna filtro para isolar dados do tenant atual"""
    if current_user.is_authenticated:
        if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            return None  # Super admin vê tudo
        elif current_user.tipo_usuario == TipoUsuario.ADMIN:
            return current_user.id  # Admin vê seus dados
        else:  # FUNCIONARIO
            return current_user.admin_id  # Funcionário vê dados do seu admin
    return None

def can_access_data(admin_id):
    """Verifica se o usuário atual pode acessar dados de um determinado admin"""
    if not current_user.is_authenticated:
        return False
    
    if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        return True
    elif current_user.tipo_usuario == TipoUsuario.ADMIN:
        return current_user.id == admin_id
    else:  # FUNCIONARIO
        return current_user.admin_id == admin_id

def almoxarife_required(f):
    """Decorator para rotas que requerem acesso de almoxarife ou superior - MÓDULO 4"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acesso negado. Faça login primeiro.', 'danger')
            return redirect(url_for('main.login'))
        
        if current_user.tipo_usuario not in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN, TipoUsuario.ALMOXARIFE]:
            flash('Acesso negado. Apenas almoxarifes podem acessar esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def pode_gerenciar_almoxarifado():
    """Verificar se o usuário atual pode gerenciar almoxarifado"""
    if not current_user.is_authenticated:
        return False
    
    return current_user.tipo_usuario in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN, TipoUsuario.ALMOXARIFE]

def pode_lancar_materiais():
    """Verificar se o usuário atual pode lançar materiais"""
    if not current_user.is_authenticated:
        return False
    
    # Almoxarife pode lançar em qualquer RDO
    # Admin e Super Admin também podem
    return current_user.tipo_usuario in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN, TipoUsuario.ALMOXARIFE]