from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, Usuario, TipoUsuario
from auth import admin_required
import logging

from views import main_bp

logger = logging.getLogger(__name__)

@main_bp.route('/usuarios')
@login_required
@admin_required  
def usuarios():
    """Lista usuários do sistema"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    
    usuarios = Usuario.query.filter(
        db.or_(
            Usuario.admin_id == admin_id,
            Usuario.id == admin_id
        )
    ).order_by(Usuario.nome).all()
    
    logger.debug(f"[USERS] USUÁRIOS: {len(usuarios)} encontrados para admin_id={admin_id}")
    
    return render_template('usuarios/listar_usuarios.html', usuarios=usuarios)

@main_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo_usuario():
    """Criar novo usuário"""
    if request.method == 'POST':
        try:
            from multitenant_helper import get_admin_id
            admin_id = get_admin_id()
            
            nome = request.form.get('nome') or request.form['username']
            email = request.form.get('email') or f"{request.form['username']}@sige.local"
            tipo_usuario = request.form.get('tipo_usuario') or 'FUNCIONARIO'
            
            usuario = Usuario(
                nome=nome,
                email=email,
                username=request.form['username'],
                password_hash=generate_password_hash(request.form['password']),
                tipo_usuario=TipoUsuario[tipo_usuario],
                admin_id=admin_id if tipo_usuario != 'ADMIN' else None
            )
            
            db.session.add(usuario)
            db.session.commit()
            
            flash(f'[OK] Usuário {usuario.nome} criado com sucesso!', 'success')
            return redirect(url_for('main.usuarios'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao criar usuário: {e}")
            flash('[ERROR] Erro ao criar usuário', 'danger')
    
    return render_template('usuarios/novo_usuario.html')

@main_bp.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(user_id):
    """Editar usuário"""
    usuario = Usuario.query.get_or_404(user_id)
    
    if request.method == 'POST':
        try:
            usuario.nome = request.form['nome']
            usuario.email = request.form['email']
            usuario.username = request.form['username']
            usuario.tipo_usuario = TipoUsuario[request.form['tipo_usuario']]
            usuario.ativo = 'ativo' in request.form
            
            if request.form.get('password'):
                usuario.password_hash = generate_password_hash(request.form['password'])
            
            db.session.commit()
            flash(f'[OK] Usuário {usuario.nome} atualizado!', 'success')
            return redirect(url_for('main.usuarios'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao editar usuário: {e}")
            flash('[ERROR] Erro ao editar usuário', 'danger')
    
    return render_template('usuarios/editar_usuario.html', usuario=usuario)
