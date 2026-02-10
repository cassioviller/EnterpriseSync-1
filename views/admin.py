from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, Usuario, TipoUsuario, Funcionario, Obra, RegistroPonto
from auth import super_admin_required
from utils.tenant import get_tenant_admin_id
from datetime import datetime
from sqlalchemy import text
import logging
import traceback

from views import main_bp

logger = logging.getLogger(__name__)

@main_bp.route('/super-admin')
@super_admin_required
def super_admin_dashboard():
    admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).all()
    total_admins = len(admins)
    
    return render_template('super_admin_dashboard.html', 
                         admins=admins, 
                         total_admins=total_admins)

@main_bp.route('/super-admin/criar-admin', methods=['POST'])
@super_admin_required
def criar_admin():
    """Cria novo administrador (apenas superadmin pode criar)"""
    try:
        nome = request.form.get('nome')
        username = request.form.get('username')
        email = request.form.get('email')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not all([nome, username, email, senha, confirmar_senha]):
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        if Usuario.query.filter_by(email=email).first():
            flash(f'Email {email} já está cadastrado.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        if Usuario.query.filter_by(username=username).first():
            flash(f'Username {username} já está cadastrado.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        novo_admin = Usuario(
            nome=nome,
            username=username,
            email=email,
            password_hash=generate_password_hash(senha),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True
        )
        
        db.session.add(novo_admin)
        db.session.commit()
        
        flash(f'Administrador {nome} criado com sucesso!', 'success')
        logger.info(f"[OK] SUPER ADMIN: Novo admin criado - {nome} ({email})")
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar administrador: {str(e)}', 'danger')
        logger.error(f"[ERROR] ERRO criar_admin: {e}")
    
    return redirect(url_for('main.super_admin_dashboard'))

@main_bp.route('/novo_ponto', methods=['POST'])
@login_required
def novo_ponto():
    """Cria novo registro de ponto"""
    try:
        data = request.form.to_dict()
        logger.debug(f"[CONFIG] DEBUG novo_ponto: Dados recebidos: {data}")
        
        funcionario_id = data.get('funcionario_id')
        if not funcionario_id:
            logger.error(f"[ERROR] DEBUG novo_ponto: funcionario_id não informado")
            return jsonify({'success': False, 'message': 'Funcionário não informado'}), 400
        
        admin_id = get_tenant_admin_id()
        if not admin_id:
            logger.error(f"[ERROR] DEBUG novo_ponto: admin_id não identificado")
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        logger.debug(f"[CONFIG] DEBUG novo_ponto: admin_id={admin_id}, funcionario_id={funcionario_id}")
        
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            logger.error(f"[ERROR] DEBUG novo_ponto: funcionario não encontrado para id={funcionario_id}, admin_id={admin_id}")
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        obra_id = data.get('obra_id')
        if obra_id and obra_id.strip():
            obra_id = int(obra_id)
        else:
            obra_id = None
        
        def parse_time(time_str):
            if not time_str:
                return None
            time_str = time_str.strip()
            for fmt in ['%H:%M', '%I:%M %p', '%I:%M%p']:
                try:
                    return datetime.strptime(time_str, fmt).time()
                except ValueError:
                    continue
            logger.warning(f"[WARN] DEBUG novo_ponto: Formato de hora inválido: {time_str}")
            return None
        
        logger.debug(f"[CONFIG] DEBUG novo_ponto: Processando horários...")
        hora_entrada = parse_time(data.get('hora_entrada'))
        hora_saida = parse_time(data.get('hora_saida'))
        hora_almoco_saida = parse_time(data.get('hora_almoco_saida'))
        hora_almoco_retorno = parse_time(data.get('hora_almoco_retorno'))
        
        logger.debug(f"[CONFIG] DEBUG novo_ponto: hora_entrada={hora_entrada}, hora_saida={hora_saida}")
        logger.debug(f"[CONFIG] DEBUG novo_ponto: hora_almoco_saida={hora_almoco_saida}, hora_almoco_retorno={hora_almoco_retorno}")
        
        registro = RegistroPonto(
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            data=datetime.strptime(data.get('data'), '%Y-%m-%d').date(),
            hora_entrada=hora_entrada,
            hora_saida=hora_saida,
            hora_almoco_saida=hora_almoco_saida,
            hora_almoco_retorno=hora_almoco_retorno,
            observacoes=data.get('observacoes', ''),
            tipo_registro=data.get('tipo_lancamento', 'trabalho_normal'),
            admin_id=admin_id
        )
        
        if registro.hora_entrada and registro.hora_saida:
            from utils import calcular_horas_trabalhadas
            horas_calc = calcular_horas_trabalhadas(
                registro.hora_entrada,
                registro.hora_saida,
                registro.hora_almoco_saida,
                registro.hora_almoco_retorno,
                registro.data
            )
            registro.horas_trabalhadas = horas_calc['total']
            registro.horas_extras = horas_calc['extras']
        
        db.session.add(registro)
        db.session.commit()
        
        logger.debug(f"[OK] DEBUG novo_ponto: Registro criado com sucesso, id={registro.id}")
        
        return jsonify({
            'success': True,
            'message': 'Registro de ponto criado com sucesso!',
            'registro_id': registro.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] DEBUG novo_ponto: ERRO: {str(e)}")
        logger.error(f"[ERROR] DEBUG novo_ponto: Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

@main_bp.route('/admin/database-diagnostics')
@super_admin_required
def database_diagnostics():
    """
    Painel de diagnóstico de banco de dados - apenas para super_admin
    Mostra status da migração 48 e permite verificar estrutura de tabelas
    """
    try:
        from utils.database_diagnostics import DatabaseDiagnostics
        
        diagnostics = DatabaseDiagnostics()
        
        migration_status = diagnostics.check_migration_48_status()
        recent_errors = diagnostics.read_recent_diagnostics(max_entries=10)
        all_tables = diagnostics.get_all_tables()
        
        table_to_check = request.args.get('table')
        table_structure = None
        table_health = None
        
        if table_to_check:
            from utils.database_diagnostics import get_table_structure
            table_structure = get_table_structure(table_to_check)
            table_health = diagnostics.check_table_health(table_to_check)
        
        return render_template('admin/database_diagnostics.html',
                             migration_status=migration_status,
                             recent_errors=recent_errors,
                             all_tables=all_tables,
                             table_to_check=table_to_check,
                             table_structure=table_structure,
                             table_health=table_health)
    
    except Exception as e:
        logger.error(f"Erro no painel de diagnóstico: {e}")
        flash(f'Erro ao carregar diagnóstico: {str(e)}', 'danger')
        return redirect(url_for('main.dashboard'))


@main_bp.route('/admin/database-diagnostics/check-table', methods=['POST'])
@super_admin_required
def check_table_structure():
    """API para verificar estrutura de uma tabela específica"""
    try:
        table_name = request.form.get('table_name', '').strip()
        
        if not table_name:
            flash('Nome da tabela é obrigatório', 'warning')
            return redirect(url_for('main.database_diagnostics'))
        
        return redirect(url_for('main.database_diagnostics', table=table_name))
    
    except Exception as e:
        logger.error(f"Erro ao verificar tabela: {e}")
        flash(f'Erro ao verificar tabela: {str(e)}', 'danger')
        return redirect(url_for('main.database_diagnostics'))
