from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from app import limiter
from models import db, Usuario, TipoUsuario
from sqlalchemy import or_
import logging

from views import main_bp

logger = logging.getLogger(__name__)

@main_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def login():
    if request.method == 'POST':
        login_field = request.form.get('email') or request.form.get('username')
        password = request.form.get('password')
        
        user = Usuario.query.filter(
            or_(Usuario.email == login_field, Usuario.username == login_field),
            Usuario.ativo == True
        ).first()
        
        if user and password and check_password_hash(user.password_hash, password):
            login_user(user)
            
            if user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
                return redirect(url_for('main.super_admin_dashboard'))
            elif user.tipo_usuario == TipoUsuario.ADMIN:
                return redirect(url_for('main.dashboard'))
            else:
                return redirect(url_for('main.funcionario_rdo_consolidado'))
        else:
            flash('Email/Username ou senha inválidos.', 'danger')
    
    return render_template('login.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('main.login'))

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            logger.debug(f"DEBUG INDEX: Funcionário {current_user.email} redirecionado para RDO consolidado")
            return redirect(url_for('main.funcionario_rdo_consolidado'))
        elif current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            return redirect(url_for('main.super_admin_dashboard'))
        else:
            return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))
