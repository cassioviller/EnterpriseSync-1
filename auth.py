from functools import wraps
from flask import redirect, url_for, flash
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

# Onda 2 (25/08) — `get_tenant_filter` e `can_access_data` foram removidos.
# Tinham ZERO consumidores (censo de 25/08), a mesma condição que justificou
# remover `almoxarife_required` e irmãos na Fase 1. E eram armadilha:
# `get_tenant_filter` devolvia None tanto para "super admin vê tudo" quanto
# para "não autenticado", então o idiomático
# `if f: query.filter_by(admin_id=f)` serviria as linhas de TODO tenant a um
# chamador anônimo. Quem precisa de tenant usa `utils.tenant.require_tenant`.

# Fase 1 — `almoxarife_required`, `pode_gerenciar_almoxarifado` e
# `pode_lancar_materiais` foram removidos. Tinham ZERO consumidores no
# censo de 2026-07-21 (0 rotas, 0 templates, 0 testes): o módulo de
# almoxarifado inteiro roda com @login_required puro. Mantê-los sugeria
# um controle de acesso que não existe. Se o almoxarifado precisar de
# papel próprio, ele entra como PapelObra na Fase 3 (compras), com rota
# que o consuma.
