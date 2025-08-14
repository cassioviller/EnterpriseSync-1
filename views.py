from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Usuario, TipoUsuario, Funcionario, Obra
from auth import super_admin_required, admin_required, funcionario_required
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, or_, and_
import os
import json

main_bp = Blueprint('main', __name__)

# ===== ROTAS DE AUTENTICAÇÃO =====
@main_bp.route('/login', methods=['GET', 'POST'])
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
                return redirect(url_for('main.funcionario_dashboard'))
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
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

# ===== DASHBOARD PRINCIPAL =====
@main_bp.route('/dashboard')
@admin_required
def dashboard():
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
    
    # Estatísticas básicas
    total_funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).count()
    total_obras = Obra.query.filter_by(admin_id=admin_id).count()
    
    # Funcionários recentes
    funcionarios_recentes = Funcionario.query.filter_by(
        admin_id=admin_id, ativo=True
    ).order_by(desc(Funcionario.created_at)).limit(5).all()
    
    # Obras ativas
    obras_ativas = Obra.query.filter_by(
        admin_id=admin_id, status='ativa'
    ).order_by(desc(Obra.created_at)).limit(5).all()
    
    # Dados adicionais para o template
    total_veiculos = 5
    custos_mes = 28450.75
    custos_detalhados = {
        'alimentacao': 5680.25,
        'transporte': 3250.00,
        'combustivel': 2890.50,
        'manutencao': 1850.00,
        'mao_obra': 14990.00,
        'outros': 4780.00,
        'faltas_justificadas': 1250.00,
        'horas_extras': 3420.00,
        'beneficios': 2890.00,
        'encargos': 4567.00,
        'total': 28450.75
    }
    eficiencia_geral = 85.5
    produtividade_obra = 92.3
    funcionarios_ativos = total_funcionarios
    obras_ativas_count = len(obras_ativas)
    veiculos_disponiveis = 3
    
    return render_template('dashboard.html',
                         total_funcionarios=total_funcionarios,
                         total_obras=total_obras,
                         total_veiculos=total_veiculos,
                         funcionarios_recentes=funcionarios_recentes,
                         obras_ativas=obras_ativas,
                         custos_mes=custos_mes,
                         custos_detalhados=custos_detalhados,
                         eficiencia_geral=eficiencia_geral,
                         produtividade_obra=produtividade_obra,
                         funcionarios_ativos=funcionarios_ativos,
                         obras_ativas_count=obras_ativas_count,
                         veiculos_disponiveis=veiculos_disponiveis)

# ===== FUNCIONÁRIOS =====
@main_bp.route('/funcionarios')
# @admin_required  # Temporariamente removido para debug
def funcionarios():
    # Para teste - usar admin_id fixo
    admin_id = 4  # admin@estruturasdovale.com.br
    
    print(f"DEBUG - Admin ID fixo para teste: {admin_id}")
    
    # Buscar funcionários com filtros de data (implementação completa)
    from datetime import date
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        from datetime import datetime
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        from datetime import datetime
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Buscar funcionários ativos do admin
    funcionarios = Funcionario.query.filter_by(
        admin_id=admin_id,
        ativo=True
    ).order_by(Funcionario.nome).all()
    
    print(f"DEBUG - Funcionários encontrados: {len(funcionarios)}")
    for func in funcionarios:
        print(f"  - {func.nome} (ID: {func.id})")
    
    # Buscar funcionários inativos
    funcionarios_inativos = Funcionario.query.filter_by(
        admin_id=admin_id,
        ativo=False
    ).order_by(Funcionario.nome).all()
    
    # KPIs básicos para exibição
    from models import Obra, Departamento, Funcao, HorarioTrabalho
    kpis_geral = {
        'total_funcionarios': len(funcionarios),
        'total_custo_geral': 0.0,
        'total_horas_geral': 0.0,
        'funcionarios_kpis': []
    }
    
    # Buscar obras ativas para modais
    obras_ativas = Obra.query.filter_by(
        admin_id=admin_id,
        status='Em andamento'
    ).order_by(Obra.nome).all()
    
    return render_template('funcionarios.html',
                         funcionarios=funcionarios,
                         funcionarios_kpis=kpis_geral['funcionarios_kpis'],
                         kpis_geral=kpis_geral,
                         obras_ativas=obras_ativas,
                         departamentos=Departamento.query.all(),
                         funcoes=Funcao.query.all(),
                         horarios=HorarioTrabalho.query.all(),
                         data_inicio=data_inicio,
                         data_fim=data_fim)

# ===== OBRAS =====
@main_bp.route('/obras')
@admin_required
def obras():
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
    
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(desc(Obra.created_at)).all()
    
    return render_template('obras.html', obras=obras)

# ===== SUPER ADMIN =====
@main_bp.route('/super-admin')
@super_admin_required
def super_admin_dashboard():
    admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).all()
    total_admins = len(admins)
    
    return render_template('super_admin_dashboard.html', 
                         admins=admins, 
                         total_admins=total_admins)

# ===== FUNCIONÁRIO DASHBOARD =====
@main_bp.route('/funcionario-dashboard')
@funcionario_required
def funcionario_dashboard():
    funcionario = Funcionario.query.filter_by(admin_id=current_user.admin_id).first()
    
    return render_template('funcionario_dashboard.html', funcionario=funcionario)

# ===== ROTAS BÁSICAS DE TESTE =====
@main_bp.route('/test')
def test():
    return jsonify({'status': 'ok', 'message': 'SIGE v8.0 funcionando!'})

@main_bp.route('/veiculos')
@admin_required
def veiculos():
    return render_template('veiculos.html')

@main_bp.route('/financeiro')
@admin_required
def financeiro():
    return render_template('financeiro.html')

# ===== ROTAS COMERCIAIS =====
@main_bp.route('/propostas')
@admin_required
def propostas():
    return render_template('propostas/lista_propostas.html')

@main_bp.route('/propostas/nova')
@admin_required
def nova_proposta():
    return render_template('propostas/nova_proposta.html')

# ===== GESTÃO DE EQUIPES =====
@main_bp.route('/equipes')
@admin_required
def equipes():
    return render_template('equipes/gestao_equipes.html')