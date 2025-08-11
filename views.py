from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from app import db
from models import *
from models import PropostaComercial, ServicoPropostaComercial
from forms import *
from utils import calcular_horas_trabalhadas, calcular_custo_real_obra, calcular_custos_mes
from kpis_engine import kpis_engine
from auth import super_admin_required, admin_required, funcionario_required, get_tenant_filter, can_access_data
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, or_, and_

import os
import json
from werkzeug.utils import secure_filename

main_bp = Blueprint('main', __name__)

# ===== ROTAS DE AUTENTICAÇÃO =====
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Suportar tanto email quanto username
        login_field = request.form.get('email') or request.form.get('username')
        password = request.form.get('password')
        
        # Buscar por email ou username
        user = Usuario.query.filter(
            or_(Usuario.email == login_field, Usuario.username == login_field),
            Usuario.ativo == True
        ).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            
            # Redirect baseado no tipo de usuário
            if user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
                return redirect(url_for('main.super_admin_dashboard'))
            elif user.tipo_usuario == TipoUsuario.ADMIN:
                return redirect(url_for('main.dashboard'))
            else:  # FUNCIONARIO
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

# ===== ROTAS SUPER ADMIN =====
@main_bp.route('/super-admin')
@super_admin_required
def super_admin_dashboard():
    # Super Admin só acessa dados de administradores
    admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).all()
    total_admins = len(admins)
    
    return render_template('super_admin_dashboard.html', 
                         admins=admins, 
                         total_admins=total_admins)

@main_bp.route('/super-admin/criar-admin', methods=['POST'])
@super_admin_required
def criar_admin():
    nome = request.form['nome']
    username = request.form['username']
    email = request.form['email']
    senha = request.form['senha']
    confirmar_senha = request.form['confirmar_senha']
    
    if senha != confirmar_senha:
        flash('Senhas não conferem.', 'danger')
        return redirect(url_for('main.super_admin_dashboard'))
    
    if Usuario.query.filter_by(username=username).first():
        flash('Username já existe.', 'danger')
        return redirect(url_for('main.super_admin_dashboard'))
    
    if Usuario.query.filter_by(email=email).first():
        flash('Email já existe.', 'danger')
        return redirect(url_for('main.super_admin_dashboard'))
    
    admin = Usuario(
        nome=nome,
        username=username,
        email=email,
        password_hash=generate_password_hash(senha),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True
    )
    
    db.session.add(admin)
    db.session.commit()
    
    flash(f'Admin {nome} criado com sucesso!', 'success')
    return redirect(url_for('main.super_admin_dashboard'))

@main_bp.route('/super-admin/toggle-status/<int:admin_id>', methods=['POST'])
@super_admin_required
def toggle_admin_status(admin_id):
    try:
        data = request.get_json()
        ativo = data.get('ativo')
        
        admin = Usuario.query.get(admin_id)
        if not admin or admin.tipo_usuario != TipoUsuario.ADMIN:
            return jsonify({'success': False, 'message': 'Admin não encontrado'})
        
        admin.ativo = ativo
        db.session.commit()
        
        status = 'ativado' if ativo else 'desativado'
        return jsonify({'success': True, 'message': f'Admin {status} com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

# ===== ROTAS ADMIN =====
@main_bp.route('/admin/acessos')
@admin_required
def admin_acessos():
    funcionarios_acesso = Usuario.query.filter_by(
        tipo_usuario=TipoUsuario.FUNCIONARIO,
        admin_id=current_user.id
    ).all()
    
    total_funcionarios = len(funcionarios_acesso)
    funcionarios_ativos = len([f for f in funcionarios_acesso if f.ativo])
    
    return render_template('admin_acessos.html',
                         funcionarios_acesso=funcionarios_acesso,
                         total_funcionarios=total_funcionarios,
                         funcionarios_ativos=funcionarios_ativos)

@main_bp.route('/admin/criar-funcionario-acesso', methods=['POST'])
@admin_required
def criar_funcionario_acesso():
    nome = request.form['nome']
    username = request.form['username']
    email = request.form['email']
    senha = request.form['senha']
    
    if Usuario.query.filter_by(username=username).first():
        flash('Username já existe.', 'danger')
        return redirect(url_for('main.admin_acessos'))
    
    funcionario = Usuario(
        nome=nome,
        username=username,
        email=email,
        password_hash=generate_password_hash(senha),
        tipo_usuario=TipoUsuario.FUNCIONARIO,
        admin_id=current_user.id,
        ativo=True
    )
    
    db.session.add(funcionario)
    db.session.commit()
    
    flash(f'Acesso criado para {nome}!', 'success')
    return redirect(url_for('main.admin_acessos'))

@main_bp.route('/admin/funcionario-acesso/<int:funcionario_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_funcionario_acesso(funcionario_id):
    """Editar dados de funcionário com acesso"""
    funcionario = Usuario.query.filter_by(
        id=funcionario_id, 
        admin_id=current_user.id, 
        tipo_usuario=TipoUsuario.FUNCIONARIO
    ).first_or_404()
    
    if request.method == 'POST':
        # Atualizar dados básicos
        funcionario.nome = request.form['nome']
        funcionario.email = request.form['email']
        
        # Verificar se username mudou e se não existe
        novo_username = request.form['username']
        if novo_username != funcionario.username:
            if Usuario.query.filter_by(username=novo_username).first():
                flash('Username já existe.', 'danger')
                return redirect(url_for('main.editar_funcionario_acesso', funcionario_id=funcionario_id))
            funcionario.username = novo_username
        
        # Alterar senha se fornecida
        nova_senha = request.form.get('nova_senha')
        if nova_senha:
            funcionario.password_hash = generate_password_hash(nova_senha)
            flash('Senha alterada com sucesso!', 'success')
        
        # Status ativo/inativo
        funcionario.ativo = 'ativo' in request.form
        
        db.session.commit()
        flash(f'Dados de {funcionario.nome} atualizados!', 'success')
        return redirect(url_for('main.admin_acessos'))
    
    return render_template('editar_funcionario_acesso.html', funcionario=funcionario)

@main_bp.route('/admin/funcionario-acesso/<int:funcionario_id>/alterar-senha', methods=['POST'])
@admin_required
def alterar_senha_funcionario(funcionario_id):
    """Alterar senha específica de um funcionário"""
    try:
        funcionario = Usuario.query.filter_by(
            id=funcionario_id, 
            admin_id=current_user.id, 
            tipo_usuario=TipoUsuario.FUNCIONARIO
        ).first_or_404()
        
        nova_senha = request.form.get('nova_senha')
        if not nova_senha:
            return jsonify({'success': False, 'message': 'Nova senha é obrigatória'})
        
        funcionario.password_hash = generate_password_hash(nova_senha)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

@main_bp.route('/funcionario/<int:funcionario_id>/toggle-status', methods=['POST'])
@login_required
def toggle_funcionario_status(funcionario_id):
    """Ativar/desativar funcionário"""
    try:
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id, 
            admin_id=current_user.id
        ).first_or_404()
        
        data = request.get_json()
        ativo = data.get('ativo')
        
        funcionario.ativo = ativo
        db.session.commit()
        
        status = 'ativado' if ativo else 'desativado'
        return jsonify({'success': True, 'message': f'Funcionário {status} com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

@main_bp.route('/admin/funcionario-acesso/<int:funcionario_id>/excluir', methods=['POST'])
@admin_required
def excluir_funcionario_acesso(funcionario_id):
    """Excluir funcionário do sistema"""
    try:
        funcionario = Usuario.query.filter_by(
            id=funcionario_id, 
            admin_id=current_user.id, 
            tipo_usuario=TipoUsuario.FUNCIONARIO
        ).first_or_404()
        
        nome = funcionario.nome
        db.session.delete(funcionario)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Funcionário {nome} excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

# ===== DASHBOARD FUNCIONÁRIO =====
@main_bp.route('/funcionario-dashboard')
@funcionario_required
def funcionario_dashboard():
    # Funcionários só veem suas próprias ações
    if current_user.tipo_usuario != TipoUsuario.FUNCIONARIO:
        return redirect(url_for('main.dashboard'))
    
    # Mostrar apenas RDO e veículos - O funcionário logado é um Usuario do tipo FUNCIONARIO
    # Precisamos encontrar o Funcionario relacionado ou usar current_user.id diretamente
    rdos_recentes = RDO.query.filter_by(criado_por_id=current_user.id).order_by(RDO.data_relatorio.desc()).limit(5).all()
    
    return render_template('funcionario_dashboard.html', rdos_recentes=rdos_recentes)

# Rotas adicionais de veículos serão adicionadas diretamente aqui

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Super Admin deve ser redirecionado para sua própria página
    if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        return redirect(url_for('main.super_admin_dashboard'))
    
    # Funcionário deve ser redirecionado para sua própria página
    if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
        return redirect(url_for('main.funcionario_dashboard'))
    
    # Apenas Admin acessa o dashboard operacional
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return redirect(url_for('main.login'))
    
    # Filtros de data dos parâmetros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Usar sistema unificado de KPIs para garantir consistência
    from kpi_unificado import obter_kpi_dashboard
    
    admin_id = current_user.id
    kpis_dashboard = obter_kpi_dashboard(admin_id, data_inicio, data_fim)
    
    # Extrair valores do sistema unificado
    total_funcionarios = kpis_dashboard.get('funcionarios_ativos', 0)
    total_obras = kpis_dashboard.get('obras_ativas', 0)
    total_veiculos = kpis_dashboard.get('veiculos_ativos', 0)
    
    # Custos detalhados do sistema unificado
    custos_detalhados = kpis_dashboard.get('custos_detalhados', {})
    custo_alimentacao = custos_detalhados.get('alimentacao', 0)
    custo_transporte = custos_detalhados.get('transporte', 0)
    custo_mao_obra = custos_detalhados.get('mao_obra', 0)
    custo_outros = custos_detalhados.get('outros', 0)
    custo_faltas_justificadas = custos_detalhados.get('faltas_justificadas', 0)
    
    # Total dos custos do sistema unificado
    total_custos = kpis_dashboard.get('custos_periodo', 0)
    custos_mes = total_custos
    
    # Obras em andamento deste admin
    obras_andamento = Obra.query.filter(
        Obra.status == 'Em andamento',
        Obra.admin_id == admin_id
    ).limit(5).all()
    
    # Funcionários por departamento deste admin
    funcionarios_dept = db.session.query(
        Departamento.nome,
        func.count(Funcionario.id).label('total')
    ).join(Funcionario).filter(
        Funcionario.ativo == True,
        Funcionario.admin_id == admin_id
    ).group_by(Departamento.nome).all()
    
    # Usar dados corretos dos KPIs unificados
    obras_com_custos = kpis_dashboard.get('obras', [])
    custos_recentes = []
    
    # Converter formato para o template
    for obra in obras_com_custos:
        custos_recentes.append({
            'nome': obra['nome'],
            'total_custo': obra['custo_total']
        })
    
    # Garantir que custos_detalhados tenha as chaves esperadas pelo template
    custos_dashboard = {
        'alimentacao': custo_alimentacao,
        'transporte': custo_transporte,
        'mao_obra': custo_mao_obra,
        'outros': custo_outros,
        'faltas_justificadas': custo_faltas_justificadas,
        'total': custos_mes
    }
    
    return render_template('dashboard.html',
                         total_funcionarios=total_funcionarios,
                         total_obras=total_obras,
                         total_veiculos=total_veiculos,
                         custos_mes=custos_mes,
                         custos_detalhados=custos_dashboard,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         obras_andamento=obras_andamento,
                         funcionarios_dept=funcionarios_dept,
                         custos_recentes=custos_recentes)

@main_bp.route('/api/dashboard/dados')
@login_required
def api_dashboard_dados():
    """API para obter dados do dashboard via AJAX"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    data_inicio_param = request.args.get('data_inicio')
    data_fim_param = request.args.get('data_fim')
    
    try:
        data_inicio = datetime.strptime(data_inicio_param, '%Y-%m-%d').date() if data_inicio_param else date.today().replace(day=1)
        data_fim = datetime.strptime(data_fim_param, '%Y-%m-%d').date() if data_fim_param else date.today()
    except:
        data_inicio = date.today().replace(day=1)
        data_fim = date.today()
    
    # KPIs básicos atualizados - FILTRADOS POR ADMIN (MULTI-TENANT)
    funcionarios_ativos = Funcionario.query.filter_by(ativo=True, admin_id=current_user.id).count()
    obras_ativas = Obra.query.filter_by(status='Em andamento', admin_id=current_user.id).count()
    veiculos_ativos = Veiculo.query.filter_by(status='Ativo', admin_id=current_user.id).count()
    
    # Custos do período
    custos_periodo = db.session.query(func.sum(CustoObra.valor)).filter(
        CustoObra.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Horas trabalhadas do período
    horas_periodo = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
        RegistroPonto.data.between(data_inicio, data_fim)
    ).scalar() or 0
    
    # Dados para gráfico de custos por dia (últimos 30 dias)
    custos_timeline = db.session.query(
        CustoObra.data,
        func.sum(CustoObra.valor).label('total')
    ).filter(
        CustoObra.data >= (data_fim - timedelta(days=30))
    ).group_by(CustoObra.data).order_by(CustoObra.data).all()
    
    # Top 5 funcionários mais produtivos do período
    top_funcionarios = db.session.query(
        Funcionario.nome,
        Funcionario.codigo,
        func.sum(RegistroPonto.horas_trabalhadas).label('total_horas'),
        func.count(RegistroPonto.id).label('dias_trabalhados')
    ).join(RegistroPonto).filter(
        Funcionario.ativo == True,
        RegistroPonto.data.between(data_inicio, data_fim)
    ).group_by(Funcionario.id, Funcionario.nome, Funcionario.codigo).order_by(
        desc('total_horas')
    ).limit(5).all()
    
    # Obras com alertas (sem RDO há mais de 7 dias)
    data_limite_rdo = data_fim - timedelta(days=7)
    obras_sem_rdo = db.session.query(Obra).filter(
        Obra.status == 'Em andamento'
    ).outerjoin(RDO).group_by(Obra.id).having(
        or_(
            func.max(RDO.data) < data_limite_rdo,
            func.max(RDO.data).is_(None)
        )
    ).limit(5).all()
    
    dados_resposta = {
        'kpis': {
            'funcionarios_ativos': funcionarios_ativos,
            'obras_ativas': obras_ativas,
            'veiculos_ativos': veiculos_ativos,
            'custos_periodo': float(custos_periodo),
            'horas_periodo': float(horas_periodo),
            'alertas_obras': len(obras_sem_rdo)
        },
        'graficos': {
            'custos_timeline': {
                'labels': [c.data.strftime('%d/%m') for c in custos_timeline],
                'data': [float(c.total) for c in custos_timeline]
            }
        },
        'top_funcionarios': [
            {
                'nome': f.nome,
                'codigo': f.codigo,
                'horas': float(f.total_horas or 0),
                'dias': f.dias_trabalhados,
                'media_diaria': float(f.total_horas or 0) / f.dias_trabalhados if f.dias_trabalhados > 0 else 0
            } for f in top_funcionarios
        ],
        'obras_alerta': [
            {
                'nome': obra.nome,
                'status': obra.status,
                'ultimo_rdo': 'Nunca' if not hasattr(obra, 'ultimo_rdo') else 'Há mais de 7 dias'
            } for obra in obras_sem_rdo
        ],
        'periodo': {
            'data_inicio': data_inicio.strftime('%Y-%m-%d'),
            'data_fim': data_fim.strftime('%Y-%m-%d'),
            'dias': (data_fim - data_inicio).days
        },
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(dados_resposta)

@main_bp.route('/api/alertas/verificar')
@login_required
def api_verificar_alertas():
    """API para verificar alertas em tempo real"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        alertas = []
        hoje = date.today()
        
        # Verificar funcionários com problemas de produtividade (últimos 30 dias)
        funcionarios_problema = db.session.query(
            Funcionario.nome,
            func.avg(RegistroPonto.horas_trabalhadas).label('media_horas'),
            func.count(RegistroPonto.id).label('dias_trabalhados')
        ).join(RegistroPonto).filter(
            Funcionario.ativo == True,
            RegistroPonto.data >= (hoje - timedelta(days=30))
        ).group_by(Funcionario.id, Funcionario.nome).having(
            func.avg(RegistroPonto.horas_trabalhadas) < 6.0  # Menos de 6h/dia em média
        ).all()
        
        for func_problema in funcionarios_problema:
            alertas.append({
                'tipo': 'PRODUTIVIDADE_BAIXA',
                'prioridade': 'MEDIA',
                'titulo': f'Produtividade baixa: {func_problema.nome}',
                'descricao': f'Média de {func_problema.media_horas:.1f}h/dia nos últimos 30 dias',
                'categoria': 'RH',
                'data': datetime.now().isoformat()
            })
        
        # Verificar obras sem RDO
        obras_sem_rdo = db.session.query(Obra).filter(
            Obra.status == 'Em andamento'
        ).outerjoin(RDO).group_by(Obra.id).having(
            or_(
                func.max(RDO.data) < (hoje - timedelta(days=7)),
                func.max(RDO.data).is_(None)
            )
        ).limit(10).all()
        
        for obra in obras_sem_rdo:
            alertas.append({
                'tipo': 'OBRA_SEM_RDO',
                'prioridade': 'ALTA',
                'titulo': f'Obra sem RDO: {obra.nome}',
                'descricao': 'Sem relatório diário há mais de 7 dias',
                'categoria': 'OPERACIONAL',
                'data': datetime.now().isoformat()
            })
        
        # Verificar veículos com custos altos (últimos 30 dias)
        veiculos_custo_alto = db.session.query(
            Veiculo.modelo,
            Veiculo.placa,
            func.sum(CustoVeiculo.valor).label('custo_total')
        ).join(CustoVeiculo).filter(
            CustoVeiculo.data >= (hoje - timedelta(days=30))
        ).group_by(Veiculo.id, Veiculo.modelo, Veiculo.placa).having(
            func.sum(CustoVeiculo.valor) > 2000
        ).all()
        
        for veiculo in veiculos_custo_alto:
            alertas.append({
                'tipo': 'CUSTO_VEICULO_ALTO',
                'prioridade': 'BAIXA',
                'titulo': f'Custo alto: {veiculo.modelo}',
                'descricao': f'R$ {veiculo.custo_total:,.2f} nos últimos 30 dias',
                'categoria': 'FINANCEIRO',
                'data': datetime.now().isoformat()
            })
        
        # Organizar por prioridade
        alertas_organizados = {
            'ALTA': [a for a in alertas if a['prioridade'] == 'ALTA'],
            'MEDIA': [a for a in alertas if a['prioridade'] == 'MEDIA'],
            'BAIXA': [a for a in alertas if a['prioridade'] == 'BAIXA']
        }
        
        estatisticas = {
            'total': len(alertas),
            'criticos': len(alertas_organizados['ALTA']),
            'importantes': len(alertas_organizados['MEDIA']),
            'informativos': len(alertas_organizados['BAIXA'])
        }
        
        return jsonify({
            'success': True,
            'alertas': alertas_organizados,
            'estatisticas': estatisticas,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao verificar alertas: {str(e)}'
        }), 500

@main_bp.route('/api/dashboard/refresh')
@login_required
def api_dashboard_refresh():
    """API para refresh automático do dashboard"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    # Dados básicos para refresh rápido
    dados_refresh = {
        'funcionarios_online': Funcionario.query.filter_by(ativo=True).count(),
        'obras_ativas': Obra.query.filter_by(status='Em andamento').count(),
        'ultima_atualizacao': datetime.now().strftime('%H:%M:%S'),
        'alertas_pendentes': 0  # Implementar contagem rápida de alertas
    }
    
    return jsonify(dados_refresh)

# Integrar APIs de IA e Analytics
@main_bp.route('/api/ia/prever-custos', methods=['POST'])
@login_required
def api_ia_prever_custos():
    """API para predição de custos usando IA"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        data = request.get_json()
        orcamento = data.get('orcamento', 100000)
        funcionarios = data.get('funcionarios', 5)
        duracao = data.get('duracao', 30)
        
        from ai_analytics import prever_custo_obra_api
        resultado = prever_custo_obra_api(orcamento, funcionarios, duracao)
        
        return jsonify({
            'success': True,
            'predicao': resultado,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro na predição: {str(e)}'
        }), 500

@main_bp.route('/api/ia/detectar-anomalias', methods=['GET'])
@login_required
def api_ia_detectar_anomalias():
    """API para detecção de anomalias"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        dias = int(request.args.get('dias', 7))
        
        from ai_analytics import detectar_anomalias_api
        resultado = detectar_anomalias_api(dias)
        
        return jsonify({
            'success': True,
            'anomalias': resultado,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro na detecção: {str(e)}'
        }), 500

@main_bp.route('/api/ia/otimizar-recursos', methods=['GET'])
@login_required
def api_ia_otimizar_recursos():
    """API para otimização de recursos"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        from ai_analytics import otimizar_recursos_api
        resultado = otimizar_recursos_api()
        
        return jsonify({
            'success': True,
            'otimizacoes': resultado,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro na otimização: {str(e)}'
        }), 500

@main_bp.route('/api/ia/analisar-sentimentos', methods=['GET'])
@login_required
def api_ia_analisar_sentimentos():
    """API para análise de sentimentos"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        from ai_analytics import analisar_sentimentos_api
        resultado = analisar_sentimentos_api()
        
        return jsonify({
            'success': True,
            'sentimentos': resultado,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro na análise: {str(e)}'
        }), 500

@main_bp.route('/api/notificacoes/avancadas', methods=['GET'])
@login_required
def api_notificacoes_avancadas():
    """API para sistema de notificações avançado"""
    if current_user.tipo_usuario != TipoUsuario.ADMIN:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        from notification_system import executar_sistema_notificacoes
        resultado = executar_sistema_notificacoes()
        
        return jsonify({
            'success': True,
            'notificacoes': resultado,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro no sistema de notificações: {str(e)}'
        }), 500

# Funcionários
@main_bp.route('/funcionarios')
@login_required
def funcionarios():
    # Filtros de data dos parâmetros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Calcular KPIs gerais dos funcionários para o período com filtro por admin
    from utils import calcular_kpis_funcionarios_geral
    kpis_geral = calcular_kpis_funcionarios_geral(data_inicio, data_fim, current_user.id)
    
    # Buscar obras ativas do admin para o modal de lançamento múltiplo
    obras_ativas = Obra.query.filter_by(
        admin_id=current_user.id,
        status='Em andamento'  
    ).order_by(Obra.nome).all()
    
    # Buscar funcionários ativos do admin para o modal
    funcionarios = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).order_by(Funcionario.nome).all()
    
    # Buscar funcionários inativos também para exibir na lista
    funcionarios_inativos = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=False
    ).order_by(Funcionario.nome).all()
    
    # Calcular KPIs dos funcionários inativos (para exibir na interface)
    funcionarios_inativos_kpis = []
    for func in funcionarios_inativos:
        from utils import calcular_kpis_funcionario_periodo
        kpi = calcular_kpis_funcionario_periodo(func.id, data_inicio, data_fim)
        if kpi:
            funcionarios_inativos_kpis.append(kpi)
    
    # Combinar ativos e inativos para exibição
    todos_funcionarios_kpis = kpis_geral['funcionarios_kpis'] + funcionarios_inativos_kpis
    
    return render_template('funcionarios.html', 
                         funcionarios_kpis=todos_funcionarios_kpis,
                         funcionarios=funcionarios,
                         kpis_geral=kpis_geral,
                         obras_ativas=obras_ativas,
                         departamentos=Departamento.query.all(),
                         funcoes=Funcao.query.all(),
                         horarios=HorarioTrabalho.query.all(),
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@main_bp.route('/funcionarios/novo', methods=['GET', 'POST'])
@login_required
def novo_funcionario():
    form = FuncionarioForm()
    form.departamento_id.choices = [(0, 'Selecione...')] + [(d.id, d.nome) for d in Departamento.query.all()]
    form.funcao_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcao.query.all()]
    form.horario_trabalho_id.choices = [(0, 'Selecione...')] + [(h.id, h.nome) for h in HorarioTrabalho.query.all()]
    
    if form.validate_on_submit():
        try:
            # Validar CPF
            from utils import validar_cpf, gerar_codigo_funcionario, salvar_foto_funcionario
            if not validar_cpf(form.cpf.data):
                flash('CPF inválido. Verifique o número informado.', 'error')
                return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                                     departamentos=Departamento.query.all(),
                                     funcoes=Funcao.query.all(),
                                     horarios=HorarioTrabalho.query.all())
            
            # Verificar se CPF já existe
            cpf_existe = Funcionario.query.filter_by(cpf=form.cpf.data).first()
            if cpf_existe:
                flash('CPF já cadastrado para outro funcionário.', 'error')
                return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                                     departamentos=Departamento.query.all(),
                                     funcoes=Funcao.query.all(),
                                     horarios=HorarioTrabalho.query.all())
            
            funcionario = Funcionario(
                nome=form.nome.data,
                admin_id=current_user.id,  # Associar funcionário ao admin logado
                cpf=form.cpf.data,
                rg=form.rg.data,
                data_nascimento=form.data_nascimento.data,
                endereco=form.endereco.data,
                telefone=form.telefone.data,
                email=form.email.data,
                data_admissao=form.data_admissao.data,
                salario=form.salario.data or 0.0,
                departamento_id=form.departamento_id.data if form.departamento_id.data > 0 else None,
                funcao_id=form.funcao_id.data if form.funcao_id.data > 0 else None,
                horario_trabalho_id=form.horario_trabalho_id.data if form.horario_trabalho_id.data > 0 else None,
                ativo=form.ativo.data
            )
            
            # Gerar código único
            funcionario.codigo = gerar_codigo_funcionario()
            
            db.session.add(funcionario)
            db.session.flush()  # Para obter o ID antes do commit
            
            # Processar upload de foto
            if form.foto.data:
                foto_path, foto_base64 = salvar_foto_funcionario(form.foto.data, funcionario.codigo)
                if foto_path:
                    funcionario.foto = foto_path
                    funcionario.foto_base64 = foto_base64
            
            db.session.commit()
            flash('Funcionário cadastrado com sucesso!', 'success')
            return redirect(url_for('main.funcionarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar funcionário: {str(e)}', 'error')
            return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                                 departamentos=Departamento.query.all(),
                                 funcoes=Funcao.query.all(),
                                 horarios=HorarioTrabalho.query.all())
    
    return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                         departamentos=Departamento.query.all(),
                         funcoes=Funcao.query.all(),
                         horarios=HorarioTrabalho.query.all())

@main_bp.route('/funcionarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_funcionario(id):
    funcionario = Funcionario.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados do funcionário
            funcionario.nome = request.form.get('nome')
            funcionario.cpf = request.form.get('cpf')
            funcionario.rg = request.form.get('rg')
            funcionario.endereco = request.form.get('endereco')
            funcionario.telefone = request.form.get('telefone')
            funcionario.email = request.form.get('email')
            funcionario.salario = float(request.form.get('salario', 0) or 0)
            
            # Data de nascimento
            data_nascimento = request.form.get('data_nascimento')
            if data_nascimento:
                funcionario.data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
            
            # Data de admissão
            data_admissao = request.form.get('data_admissao')
            if data_admissao:
                funcionario.data_admissao = datetime.strptime(data_admissao, '%Y-%m-%d').date()
            
            # IDs opcionais
            departamento_id = request.form.get('departamento_id')
            funcionario.departamento_id = int(departamento_id) if departamento_id and departamento_id != '0' else None
            
            funcao_id = request.form.get('funcao_id')
            funcionario.funcao_id = int(funcao_id) if funcao_id and funcao_id != '0' else None
            
            horario_id = request.form.get('horario_trabalho_id')
            funcionario.horario_trabalho_id = int(horario_id) if horario_id and horario_id != '0' else None
            
            funcionario.ativo = bool(request.form.get('ativo'))
            
            # Processar upload de foto
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename:
                    from utils import salvar_foto_funcionario
                    foto_path, foto_base64 = salvar_foto_funcionario(foto, funcionario.codigo)
                    if foto_path:
                        funcionario.foto = foto_path
                        funcionario.foto_base64 = foto_base64
            
            db.session.commit()
            flash('Funcionário atualizado com sucesso!', 'success')
            return redirect(url_for('main.funcionario_perfil', id=funcionario.id))
            
        except Exception as e:
            flash(f'Erro ao atualizar funcionário: {str(e)}', 'error')
            return redirect(url_for('main.funcionario_perfil', id=id))
    
    # Para GET, redirecionar para a página de perfil com modo de edição
    return redirect(url_for('main.funcionario_perfil', id=id, edit=1))

@main_bp.route('/funcionarios/ponto/novo', methods=['POST'])
@main_bp.route('/novo-ponto', methods=['POST'])
@login_required
def novo_ponto():
    """Criar novo registro de ponto com suporte a tipos de lançamento e resposta JSON"""
    try:
        # Suporte para dados JSON ou form
        if request.is_json:
            data_source = request.json
        else:
            data_source = request.form
        
        funcionario_id = data_source.get('funcionario_id')
        data_str = data_source.get('data_ponto') or data_source.get('data')
        data = datetime.strptime(data_str, '%Y-%m-%d').date()
        tipo_lancamento = data_source.get('tipo_lancamento', 'trabalhado')
        obra_id = data_source.get('obra_id_ponto') or data_source.get('obra_id') or None
        percentual_extras = float(data_source.get('percentual_extras', 0)) if data_source.get('percentual_extras') else 0.0
        observacoes = data_source.get('observacoes_ponto') or data_source.get('observacoes', '')
        
        if obra_id == '':
            obra_id = None
        elif obra_id:
            obra_id = int(obra_id)
        
        # Verificar se já existe registro para esta data
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data
        ).first()
        
        if registro_existente:
            return jsonify({'error': 'Já existe um registro de ponto para esta data.'}), 400
        
        # Criar registro baseado no tipo de lançamento
        registro = RegistroPonto(
            funcionario_id=int(funcionario_id),
            obra_id=obra_id,
            data=data,
            observacoes=observacoes,
            tipo_registro=tipo_lancamento,
            percentual_extras=percentual_extras
        )
        
        # Adicionar horários se não for falta ou feriado
        if tipo_lancamento not in ['falta', 'falta_justificada', 'feriado']:
            entrada = data_source.get('hora_entrada_ponto') or data_source.get('hora_entrada')
            saida_almoco = data_source.get('hora_almoco_saida_ponto') or data_source.get('hora_almoco_saida')
            retorno_almoco = data_source.get('hora_almoco_retorno_ponto') or data_source.get('hora_almoco_retorno')
            saida = data_source.get('hora_saida_ponto') or data_source.get('hora_saida')
            
            if entrada:
                registro.hora_entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.hora_almoco_saida = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.hora_almoco_retorno = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.hora_saida = datetime.strptime(saida, '%H:%M').time()
        
        # Percentual de extras baseado no tipo
        if tipo_lancamento == 'sabado_horas_extras':
            registro.percentual_extras = 50.0
        elif tipo_lancamento in ['domingo_horas_extras', 'feriado_trabalhado']:
            registro.percentual_extras = 100.0
        
        db.session.add(registro)
        db.session.commit()
        
        # Aplicar lógica especial IMEDIATAMENTE para tipos específicos
        if tipo_lancamento in ['sabado_horas_extras', 'sabado_trabalhado']:
            print("✅ APLICANDO LÓGICA DE SÁBADO NO SALVAMENTO")
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            registro.horas_extras = registro.horas_trabalhadas or 0
            registro.percentual_extras = 50.0
            
        elif tipo_lancamento in ['domingo_horas_extras', 'domingo_trabalhado']:
            print("✅ APLICANDO LÓGICA DE DOMINGO NO SALVAMENTO")
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            registro.horas_extras = registro.horas_trabalhadas or 0
            registro.percentual_extras = 100.0
            
        elif tipo_lancamento == 'feriado_trabalhado':
            print("✅ APLICANDO LÓGICA DE FERIADO NO SALVAMENTO")
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
            registro.horas_extras = registro.horas_trabalhadas or 0
            registro.percentual_extras = 100.0
        
        # Salvar mudanças especiais
        db.session.commit()
        
        # Recalcular KPIs após inserção
        try:
            from kpis_engine import atualizar_calculos_ponto
            atualizar_calculos_ponto(registro.id)
        except ImportError:
            # KPIs engine não disponível, continuar sem erro
            pass
        
        return jsonify({'success': True, 'message': f'Registro de ponto ({tipo_lancamento}) criado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao criar registro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/funcionarios/<int:funcionario_id>/horario-padrao')
@login_required 
def horario_padrao_funcionario(funcionario_id):
    """Retorna o horário padrão do funcionário em JSON"""
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    # Buscar horário de trabalho do funcionário
    if funcionario.horario_trabalho_id:
        horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
        if horario:
            return jsonify({
                'success': True,
                'hora_entrada': horario.entrada.strftime('%H:%M') if horario.entrada else '08:00',
                'hora_saida': horario.saida.strftime('%H:%M') if horario.saida else '17:00',
                'hora_almoco_saida': horario.saida_almoco.strftime('%H:%M') if horario.saida_almoco else '12:00',
                'hora_almoco_retorno': horario.retorno_almoco.strftime('%H:%M') if horario.retorno_almoco else '13:00'
            })
    else:
        return jsonify({
            'success': False,
            'message': 'Funcionário não possui horário de trabalho configurado'
        })

@main_bp.route('/api/ponto/lancamento-multiplo', methods=['POST'])
@login_required
@admin_required
def lancamento_multiplo_ponto():
    """API para processar lançamento múltiplo de ponto"""
    try:
        data = request.get_json()
        
        # Log de debug
        print(f"🔍 DEBUG - Lançamento múltiplo recebido:")
        print(f"   User ID: {current_user.id}")
        print(f"   Dados: {data}")
        
        # Validações básicas
        periodo_inicio = datetime.strptime(data.get('periodo_inicio'), '%Y-%m-%d').date()
        periodo_fim = datetime.strptime(data.get('periodo_fim'), '%Y-%m-%d').date()
        tipo_lancamento = data.get('tipo_lancamento')
        obra_id = data.get('obra_id')
        funcionarios_ids = data.get('funcionarios', [])
        observacoes = data.get('observacoes', '')
        
        if not all([periodo_inicio, periodo_fim, tipo_lancamento, obra_id, funcionarios_ids]):
            return jsonify({'success': False, 'message': 'Dados obrigatórios não informados'})
        
        # Verificar se obra existe e pertence ao tenant
        obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first()
        if not obra:
            # Debug adicional para problemas de tenant
            obra_qualquer = Obra.query.get(obra_id)
            if obra_qualquer:
                print(f"❌ DEBUG - Obra {obra_id} existe mas pertence ao admin {obra_qualquer.admin_id}, user atual: {current_user.id}")
                return jsonify({'success': False, 'message': f'Obra não encontrada ou não autorizada (Obra pertence ao admin {obra_qualquer.admin_id})'})
            else:
                print(f"❌ DEBUG - Obra {obra_id} não existe no banco")
                return jsonify({'success': False, 'message': f'Obra ID {obra_id} não existe no sistema'})
        
        # Configurar horários baseados no tipo de lançamento
        hora_entrada = None
        hora_saida = None
        hora_almoco_inicio = None
        hora_almoco_fim = None
        percentual_extras = 0
        
        if tipo_lancamento == 'trabalho_normal':
            hora_entrada = datetime.strptime(data.get('hora_entrada', '07:12'), '%H:%M').time()
            hora_saida = datetime.strptime(data.get('hora_saida', '17:00'), '%H:%M').time()
            if not data.get('sem_intervalo', False):
                hora_almoco_inicio = datetime.strptime(data.get('hora_almoco_inicio', '12:00'), '%H:%M').time()
                hora_almoco_fim = datetime.strptime(data.get('hora_almoco_fim', '13:00'), '%H:%M').time()
        
        elif tipo_lancamento in ['sabado_horas_extras', 'domingo_horas_extras', 'sabado_trabalhado', 'domingo_trabalhado']:
            # Para fins de semana, usar horários específicos
            hora_entrada = datetime.strptime(data.get('hora_entrada', '07:00'), '%H:%M').time()
            hora_saida = datetime.strptime(data.get('hora_saida', '17:00'), '%H:%M').time()
            
            # Intervalos de almoço para fins de semana também
            if not data.get('sem_intervalo', False):
                hora_almoco_inicio = datetime.strptime(data.get('hora_almoco_inicio', '12:00'), '%H:%M').time()
                hora_almoco_fim = datetime.strptime(data.get('hora_almoco_fim', '13:00'), '%H:%M').time()
            
            # Configurar percentual baseado no tipo
            if 'sabado' in tipo_lancamento:
                percentual_extras = int(data.get('percentual_extras', 50))
            else:  # domingo
                percentual_extras = int(data.get('percentual_extras', 100))
        
        elif tipo_lancamento == 'feriado_trabalhado':
            hora_entrada = datetime.strptime(data.get('hora_entrada', '07:12'), '%H:%M').time()
            hora_saida = datetime.strptime(data.get('hora_saida', '17:00'), '%H:%M').time()
            if not data.get('sem_intervalo', False):
                hora_almoco_inicio = datetime.strptime(data.get('hora_almoco_inicio', '12:00'), '%H:%M').time()
                hora_almoco_fim = datetime.strptime(data.get('hora_almoco_fim', '13:00'), '%H:%M').time()
            percentual_extras = 100
        
        elif tipo_lancamento == 'meio_periodo':
            hora_entrada = datetime.strptime(data.get('hora_entrada', '07:12'), '%H:%M').time()
            hora_saida = datetime.strptime(data.get('hora_saida', '11:12'), '%H:%M').time()
        
        # Processar lançamentos para cada funcionário em cada dia do período
        total_lancamentos = 0
        current_date = periodo_inicio
        
        # Buscar funcionários com isolamento de tenant
        funcionarios = Funcionario.query.filter(
            Funcionario.id.in_(funcionarios_ids),
            Funcionario.admin_id == current_user.id
        ).all()
        
        if len(funcionarios) != len(funcionarios_ids):
            return jsonify({'success': False, 'message': 'Alguns funcionários não foram encontrados'})
        
        while current_date <= periodo_fim:
            for funcionario in funcionarios:
                # Verificar se já existe registro para este funcionário nesta data
                registro_existente = RegistroPonto.query.filter(
                    and_(
                        RegistroPonto.funcionario_id == funcionario.id,
                        RegistroPonto.data == current_date
                    )
                ).first()
                
                if registro_existente:
                    continue  # Pular se já existe registro
                
                # Verificar se o funcionário deve trabalhar neste dia da semana
                deve_trabalhar_hoje = False
                if funcionario.horario_trabalho_id:
                    horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
                    if horario and horario.dias_semana:
                        # Converter dia da semana (Monday=0, Sunday=6) para formato brasileiro (Monday=1, Sunday=7)
                        dia_semana_br = current_date.weekday() + 1
                        if dia_semana_br == 7:  # Domingo
                            dia_semana_br = 7
                        
                        # Verificar se este dia está nos dias de trabalho
                        dias_trabalho = [int(d.strip()) for d in horario.dias_semana.split(',') if d.strip()]
                        deve_trabalhar_hoje = dia_semana_br in dias_trabalho
                else:
                    # Se não tem horário configurado, assumir segunda a sexta (padrão)
                    dia_semana_br = current_date.weekday() + 1
                    deve_trabalhar_hoje = dia_semana_br <= 5  # Segunda a sexta
                
                # Para tipos especiais (sábado/domingo extras), forçar criação independente do horário
                if tipo_lancamento in ['sabado_horas_extras', 'domingo_horas_extras', 'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
                    deve_trabalhar_hoje = True
                
                # Pular este dia se o funcionário não deve trabalhar
                if not deve_trabalhar_hoje:
                    continue
                
                # Usar horários do funcionário se disponível
                horario_funcionario = None
                if funcionario.horario_trabalho_id:
                    horario_funcionario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
                
                # Configurar horários baseados no horário do funcionário ou padrões
                if tipo_lancamento == 'trabalho_normal' and horario_funcionario:
                    hora_entrada = horario_funcionario.entrada
                    hora_saida = horario_funcionario.saida
                    hora_almoco_inicio = horario_funcionario.saida_almoco if not data.get('sem_intervalo', False) else None
                    hora_almoco_fim = horario_funcionario.retorno_almoco if not data.get('sem_intervalo', False) else None
                elif tipo_lancamento == 'trabalho_normal':
                    # Usar horários do formulário se não há horário configurado
                    hora_entrada = datetime.strptime(data.get('hora_entrada', '07:12'), '%H:%M').time()
                    hora_saida = datetime.strptime(data.get('hora_saida', '17:00'), '%H:%M').time()
                    if not data.get('sem_intervalo', False):
                        hora_almoco_inicio = datetime.strptime(data.get('hora_almoco_inicio', '12:00'), '%H:%M').time()
                        hora_almoco_fim = datetime.strptime(data.get('hora_almoco_fim', '13:00'), '%H:%M').time()
                
                # Criar novo registro
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    obra_id=obra_id,
                    data=current_date,
                    tipo_registro=tipo_lancamento
                )
                
                # Configurar campos baseados no tipo
                if tipo_lancamento not in ['falta', 'falta_justificada']:
                    registro.hora_entrada = hora_entrada
                    registro.hora_saida = hora_saida
                    registro.hora_almoco_saida = hora_almoco_inicio
                    registro.hora_almoco_retorno = hora_almoco_fim
                    
                    if percentual_extras > 0:
                        registro.percentual_extras = percentual_extras
                        
                        # Calcular horas extras baseado no tipo
                        if hora_entrada and hora_saida:
                            # Calcular horas trabalhadas
                            entrada_dt = datetime.combine(current_date, hora_entrada)
                            saida_dt = datetime.combine(current_date, hora_saida)
                            
                            # Subtrair almoço se houver
                            horas_trabalhadas = (saida_dt - entrada_dt).total_seconds() / 3600
                            if hora_almoco_inicio and hora_almoco_fim:
                                almoco_inicio_dt = datetime.combine(current_date, hora_almoco_inicio)
                                almoco_fim_dt = datetime.combine(current_date, hora_almoco_fim)
                                intervalo_almoco = (almoco_fim_dt - almoco_inicio_dt).total_seconds() / 3600
                                horas_trabalhadas -= intervalo_almoco
                            
                            registro.horas_extras = horas_trabalhadas
                    
                    # Para trabalho normal, calcular horas trabalhadas também
                    if tipo_lancamento == 'trabalho_normal' and hora_entrada and hora_saida:
                        entrada_dt = datetime.combine(current_date, hora_entrada)
                        saida_dt = datetime.combine(current_date, hora_saida)
                        
                        horas_totais = (saida_dt - entrada_dt).total_seconds() / 3600
                        if hora_almoco_inicio and hora_almoco_fim:
                            almoco_inicio_dt = datetime.combine(current_date, hora_almoco_inicio)
                            almoco_fim_dt = datetime.combine(current_date, hora_almoco_fim)
                            intervalo_almoco = (almoco_fim_dt - almoco_inicio_dt).total_seconds() / 3600
                            horas_totais -= intervalo_almoco
                        
                        registro.horas_trabalhadas = horas_totais
                        
                        # Verificar se há horas extras (acima das horas diárias do funcionário)
                        if horario_funcionario and horas_totais > horario_funcionario.horas_diarias:
                            registro.horas_extras = horas_totais - horario_funcionario.horas_diarias
                
                # Adicionar observações específicas do tipo
                if observacoes:
                    registro.observacoes = f"{tipo_lancamento.upper()}: {observacoes}"
                else:
                    nome_tipo = tipo_lancamento.replace('_', ' ').title()
                    registro.observacoes = f"Lançamento múltiplo - {nome_tipo} (Respeitando horário: {horario_funcionario.nome if horario_funcionario else 'Padrão'})"
                
                db.session.add(registro)
                total_lancamentos += 1
            
            # Próximo dia
            current_date += timedelta(days=1)
        
        # Commit de todos os registros
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Lançamentos processados com sucesso!',
            'total_lancamentos': total_lancamentos,
            'funcionarios_processados': len(funcionarios),
            'dias_processados': (periodo_fim - periodo_inicio).days + 1
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'Erro ao processar lançamentos: {str(e)}'
        })

@main_bp.route('/funcionarios/modal', methods=['POST'])
@login_required
def funcionario_modal():
    """Rota específica para processamento do modal de funcionários"""
    try:
        # Validar CPF
        from utils import validar_cpf, gerar_codigo_funcionario, salvar_foto_funcionario
        
        cpf = request.form.get('cpf')
        if not validar_cpf(cpf):
            flash('CPF inválido. Verifique o número informado.', 'error')
            return redirect(url_for('main.funcionarios'))
        
        # Verificar se CPF já existe
        cpf_existe = Funcionario.query.filter_by(cpf=cpf).first()
        if cpf_existe:
            flash('CPF já cadastrado para outro funcionário.', 'error')
            return redirect(url_for('main.funcionarios'))
        
        funcionario = Funcionario(
            nome=request.form.get('nome'),
            cpf=cpf,
            rg=request.form.get('rg'),
            endereco=request.form.get('endereco'),
            telefone=request.form.get('telefone'),
            email=request.form.get('email'),
            salario=float(request.form.get('salario', 0) or 0),
            ativo=bool(request.form.get('ativo'))
        )
        
        # Datas opcionais
        data_nascimento = request.form.get('data_nascimento')
        if data_nascimento:
            funcionario.data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
        
        data_admissao = request.form.get('data_admissao')
        if data_admissao:
            funcionario.data_admissao = datetime.strptime(data_admissao, '%Y-%m-%d').date()
        else:
            funcionario.data_admissao = date.today()  # Padrão para hoje
        
        # IDs opcionais
        departamento_id = request.form.get('departamento_id')
        funcionario.departamento_id = int(departamento_id) if departamento_id and departamento_id != '0' else None
        
        funcao_id = request.form.get('funcao_id')
        funcionario.funcao_id = int(funcao_id) if funcao_id and funcao_id != '0' else None
        
        horario_id = request.form.get('horario_trabalho_id')
        funcionario.horario_trabalho_id = int(horario_id) if horario_id and horario_id != '0' else None
        
        # Gerar código único
        funcionario.codigo = gerar_codigo_funcionario()
        
        db.session.add(funcionario)
        db.session.flush()  # Para obter o ID antes do commit
        
        # Processar upload de foto
        if 'foto' in request.files:
            foto = request.files['foto']
            if foto and foto.filename:
                foto_path, foto_base64 = salvar_foto_funcionario(foto, funcionario.codigo)
                if foto_path:
                    funcionario.foto = foto_path
                    funcionario.foto_base64 = foto_base64
        
        db.session.commit()
        flash('Funcionário cadastrado com sucesso!', 'success')
        return redirect(url_for('main.funcionarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cadastrar funcionário: {str(e)}', 'error')
        return redirect(url_for('main.funcionarios'))

def calcular_kpis_funcionario(funcionario_id):
    """Calcula KPIs individuais do funcionário para o mês atual"""
    hoje = date.today()
    primeiro_dia_mes = hoje.replace(day=1)
    
    # Buscar registros de ponto do mês atual
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= primeiro_dia_mes,
        RegistroPonto.data <= hoje
    ).all()
    
    # Calcular KPIs
    horas_trabalhadas = sum(r.horas_trabalhadas or 0 for r in registros_ponto)
    horas_extras = sum(r.horas_extras or 0 for r in registros_ponto)
    
    # Contar dias úteis no mês (aproximação: 22 dias úteis)
    dias_uteis_mes = 22
    dias_com_registro = len([r for r in registros_ponto if r.hora_entrada])
    
    # Calcular faltas e atrasos
    faltas = max(0, dias_uteis_mes - dias_com_registro)
    atrasos = len([r for r in registros_ponto if r.hora_entrada and r.hora_entrada.hour > 8])
    
    # Calcular absenteísmo
    absenteismo = (faltas / dias_uteis_mes) * 100 if dias_uteis_mes > 0 else 0
    
    # Calcular média de horas diárias
    media_horas_diarias = horas_trabalhadas / dias_com_registro if dias_com_registro > 0 else 0
    
    return {
        'horas_trabalhadas': horas_trabalhadas,
        'horas_extras': horas_extras,
        'faltas': faltas,
        'atrasos': atrasos,
        'absenteismo': absenteismo,
        'media_horas_diarias': media_horas_diarias
    }

def obter_dados_graficos_funcionario(funcionario_id):
    """Obtém dados para gráficos de desempenho do funcionário"""
    # Últimos 6 meses
    meses = []
    horas_trabalhadas = []
    absenteismo = []
    
    hoje = date.today()
    
    for i in range(6):
        # Calcular mês
        mes = hoje.month - i
        ano = hoje.year
        if mes <= 0:
            mes += 12
            ano -= 1
        
        primeiro_dia = date(ano, mes, 1)
        if mes == 12:
            ultimo_dia = date(ano + 1, 1, 1)
        else:
            ultimo_dia = date(ano, mes + 1, 1)
        
        # Buscar registros do mês
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= primeiro_dia,
            RegistroPonto.data < ultimo_dia
        ).all()
        
        # Calcular totais
        horas_mes = sum(r.horas_trabalhadas or 0 for r in registros)
        dias_com_registro = len([r for r in registros if r.hora_entrada])
        
        # Nome do mês
        nomes_meses = [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ]
        nome_mes = nomes_meses[mes - 1]
        
        meses.insert(0, nome_mes)
        horas_trabalhadas.insert(0, horas_mes)
        
        # Calcular absenteísmo (aproximação: 22 dias úteis)
        absenteismo_mes = ((22 - dias_com_registro) / 22) * 100 if dias_com_registro < 22 else 0
        absenteismo.insert(0, absenteismo_mes)
    
    return {
        'meses': meses,
        'horas_trabalhadas': horas_trabalhadas,
        'absenteismo': absenteismo
    }

@main_bp.route('/funcionarios/<int:id>/perfil')
@login_required
def funcionario_perfil(id):
    funcionario = Funcionario.query.get_or_404(id)
    
    # Filtros de data dos parâmetros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    obra_filtro = request.args.get('obra')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Calcular KPIs individuais para o período (usando utils)
    from utils import calcular_kpis_funcionario_periodo
    kpis = calcular_kpis_funcionario_periodo(id, data_inicio, data_fim)
    
    # Buscar registros de ponto com filtros e identificação de faltas
    
    if obra_filtro:
        # Se há filtro de obra, usar query tradicional
        query_ponto = RegistroPonto.query.filter_by(funcionario_id=id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.obra_id == obra_filtro
        )
        registros_ponto = query_ponto.order_by(RegistroPonto.data.desc()).all()
        
        # Usar novo engine de KPIs
        faltas = []  # Lista vazia por enquanto - será implementada se necessário
        
        # Lista de feriados 2025
        feriados_2025 = {
            date(2025, 1, 1),   # Ano Novo
            date(2025, 2, 17),  # Carnaval (Segunda-feira)
            date(2025, 2, 18),  # Carnaval (Terça-feira)
            date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
            date(2025, 4, 21),  # Tiradentes
            date(2025, 5, 1),   # Dia do Trabalhador
            date(2025, 6, 19),  # Corpus Christi
            date(2025, 9, 7),   # Independência
            date(2025, 10, 12), # Nossa Senhora Aparecida
            date(2025, 11, 2),  # Finados
            date(2025, 11, 15), # Proclamação da República
            date(2025, 12, 25)  # Natal
        }
        
        for registro in registros_ponto:
            # Adicionar informações sobre faltas e feriados baseado no tipo_registro
            registro.is_falta = (registro.tipo_registro in ['falta', 'falta_justificada'])
            registro.is_feriado = (registro.tipo_registro in ['feriado', 'feriado_trabalhado'])
    else:
        # Usar registros de ponto simples
        registros_ponto = RegistroPonto.query.filter_by(funcionario_id=id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(RegistroPonto.data.desc()).all()
        faltas = []  # Lista vazia por enquanto - será implementada se necessário
        
        # Adicionar informação de feriado e faltas para todos os registros
        for registro in registros_ponto:
            registro.is_falta = (registro.tipo_registro in ['falta', 'falta_justificada'])
            registro.is_feriado = (registro.tipo_registro in ['feriado', 'feriado_trabalhado'])
    
    # Lista de feriados 2025 
    feriados_2025 = {
        date(2025, 1, 1),   # Ano Novo
        date(2025, 2, 17),  # Carnaval (Segunda-feira)
        date(2025, 2, 18),  # Carnaval (Terça-feira)
        date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
        date(2025, 4, 21),  # Tiradentes
        date(2025, 5, 1),   # Dia do Trabalhador
        date(2025, 6, 19),  # Corpus Christi
        date(2025, 9, 7),   # Independência
        date(2025, 10, 12), # Nossa Senhora Aparecida
        date(2025, 11, 2),  # Finados
        date(2025, 11, 15), # Proclamação da República
        date(2025, 12, 25)  # Natal
    }
    
    # Buscar ocorrências (sem filtro de data por enquanto)
    ocorrencias = Ocorrencia.query.filter_by(funcionario_id=id).order_by(Ocorrencia.data_inicio.desc()).all()
    
    # Buscar registros de alimentação com filtros
    query_alimentacao = RegistroAlimentacao.query.filter_by(funcionario_id=id).filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    )
    
    if obra_filtro:
        query_alimentacao = query_alimentacao.filter_by(obra_id=obra_filtro)
    
    registros_alimentacao = query_alimentacao.order_by(RegistroAlimentacao.data.desc()).all()
    
    # Buscar outros custos com filtros
    query_outros_custos = OutroCusto.query.filter_by(funcionario_id=id).filter(
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    )
    
    if obra_filtro:
        query_outros_custos = query_outros_custos.filter_by(obra_id=obra_filtro)
    
    outros_custos = query_outros_custos.order_by(OutroCusto.data.desc()).all()
    
    # Buscar obras para os dropdowns
    obras = Obra.query.filter_by(status='Em andamento').all()
    
    # Obter dados para gráficos
    graficos = obter_dados_graficos_funcionario(id)
    
    # Criar objeto para KPIs (simular uma estrutura)
    class KPIData:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
    
    # CORRIGIDO: Usar kpi_associado e valores já têm sinais corretos
    total_outros_custos = sum(
        c.valor
        for c in outros_custos 
        if c.kpi_associado == 'outros_custos'
    )
    
    if kpis:
        # Corrigir horas perdidas: (faltas * 8) + atrasos
        kpis['horas_perdidas_total'] = (kpis.get('faltas', 0) * 8) + kpis.get('atrasos', 0)
        kpis['outros_custos'] = total_outros_custos
        kpis_obj = KPIData(kpis)
    else:
        kpis_obj = KPIData({
            'horas_trabalhadas': 0,
            'horas_extras': 0,
            'faltas': 0,
            'atrasos': 0,
            'absenteismo': 0,
            'horas_extras_valor': 0,
            'media_horas_diarias': 0,
            'total_atrasos': 0,
            'pontualidade': 100,
            'custo_total': 0,
            'custo_mao_obra': 0,
            'custo_alimentacao': 0,
            'custo_transporte': 0,
            'dias_trabalhados': 0,
            'dias_uteis': 0,
            'horas_perdidas_total': 0,
            'outros_custos': total_outros_custos
        })
    
    # Buscar dados adicionais para o modal de edição
    departamentos = Departamento.query.all()
    funcoes = Funcao.query.all()
    horarios = HorarioTrabalho.query.all()
    
    return render_template('funcionario_perfil.html',
                         funcionario=funcionario,
                         kpis=kpis_obj,
                         registros_ponto=registros_ponto,
                         ocorrencias=ocorrencias,
                         registros_alimentacao=registros_alimentacao,
                         outros_custos=outros_custos,
                         obras=obras,
                         graficos=graficos,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         obra_filtro=obra_filtro,
                         departamentos=departamentos,
                         funcoes=funcoes,
                         horarios=horarios)

@main_bp.route('/funcionarios/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_funcionario(id):
    funcionario = Funcionario.query.get_or_404(id)
    db.session.delete(funcionario)
    db.session.commit()
    flash('Funcionário excluído com sucesso!', 'success')
    return redirect(url_for('main.funcionarios'))

@main_bp.route('/funcionarios/<int:funcionario_id>/outros-custos', methods=['POST'])
@login_required
def criar_outro_custo(funcionario_id):
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    try:
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        
        # Obter KPI associado ou determinar automaticamente baseado no tipo
        kpi_associado = request.form.get('kpi_associado')
        
        # Se não foi especificado, determinar automaticamente baseado no tipo
        if not kpi_associado or kpi_associado == 'outros_custos':
            tipo = request.form['tipo'].lower()
            
            # Lógica inteligente de associação por tipo
            if 'transporte' in tipo or 'vale transporte' in tipo or tipo in ['vt', 'vale_transporte']:
                kpi_associado = 'custo_transporte'
            elif 'alimenta' in tipo or 'vale alimenta' in tipo or tipo in ['va', 'vale_alimentacao', 'refeicao']:
                kpi_associado = 'custo_alimentacao'
            elif 'semana viagem' in tipo or 'viagem' in tipo:
                kpi_associado = 'custo_alimentacao'  # Semana viagem geralmente é alimentação
            else:
                kpi_associado = 'outros_custos'
        
        outro_custo = OutroCusto(
            funcionario_id=funcionario_id,
            data=data,
            tipo=request.form['tipo'],
            categoria=request.form['categoria'],
            valor=float(request.form['valor']),
            descricao=request.form.get('descricao'),
            kpi_associado=kpi_associado  # NOVA FUNCIONALIDADE: Associação com KPI específico
        )
        
        db.session.add(outro_custo)
        db.session.commit()
        
        flash('Outro custo registrado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar outro custo: {str(e)}', 'error')
    
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

@main_bp.route('/funcionarios/<int:funcionario_id>/outros-custos/<int:custo_id>', methods=['DELETE'])
@login_required
def excluir_outro_custo(funcionario_id, custo_id):
    custo = OutroCusto.query.get_or_404(custo_id)
    
    # Verificar se o custo pertence ao funcionário
    if custo.funcionario_id != funcionario_id:
        return jsonify({'success': False, 'message': 'Registro não encontrado'}), 404
    
    try:
        db.session.delete(custo)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Registro excluído com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Departamentos
@main_bp.route('/departamentos')
@login_required
def departamentos():
    departamentos = Departamento.query.all()
    return render_template('departamentos.html', departamentos=departamentos)

@main_bp.route('/departamentos/novo', methods=['GET', 'POST'])
@login_required
def novo_departamento():
    form = DepartamentoForm()
    if form.validate_on_submit():
        departamento = Departamento(
            nome=form.nome.data,
            descricao=form.descricao.data
        )
        db.session.add(departamento)
        db.session.commit()
        flash('Departamento cadastrado com sucesso!', 'success')
        return redirect(url_for('main.departamentos'))
    
    return render_template('departamentos.html', form=form, departamentos=Departamento.query.all())

@main_bp.route('/departamentos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_departamento(id):
    departamento = Departamento.query.get_or_404(id)
    form = DepartamentoForm(obj=departamento)
    
    if form.validate_on_submit():
        departamento.nome = form.nome.data
        departamento.descricao = form.descricao.data
        db.session.commit()
        flash('Departamento atualizado com sucesso!', 'success')
        return redirect(url_for('main.departamentos'))
    
    return render_template('departamentos.html', form=form, departamento=departamento, departamentos=Departamento.query.all())

@main_bp.route('/departamentos/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_departamento(id):
    departamento = Departamento.query.get_or_404(id)
    db.session.delete(departamento)
    db.session.commit()
    flash('Departamento excluído com sucesso!', 'success')
    return redirect(url_for('main.departamentos'))

# Funções
@main_bp.route('/funcoes')
@login_required
def funcoes():
    funcoes = Funcao.query.all()
    return render_template('funcoes.html', funcoes=funcoes)

@main_bp.route('/funcoes/nova', methods=['GET', 'POST'])
@main_bp.route('/funcoes/novo', methods=['GET', 'POST'])
@login_required
def nova_funcao():
    form = FuncaoForm()
    if form.validate_on_submit():
        funcao = Funcao(
            nome=form.nome.data,
            descricao=form.descricao.data,
            salario_base=form.salario_base.data or 0.0
        )
        db.session.add(funcao)
        db.session.commit()
        flash('Função cadastrada com sucesso!', 'success')
        return redirect(url_for('main.funcoes'))
    
    return render_template('funcoes.html', form=form, funcoes=Funcao.query.all())

@main_bp.route('/funcoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_funcao(id):
    funcao = Funcao.query.get_or_404(id)
    form = FuncaoForm(obj=funcao)
    
    if form.validate_on_submit():
        funcao.nome = form.nome.data
        funcao.descricao = form.descricao.data
        funcao.salario_base = form.salario_base.data or 0.0
        db.session.commit()
        flash('Função atualizada com sucesso!', 'success')
        return redirect(url_for('main.funcoes'))
    
    return render_template('funcoes.html', form=form, funcao=funcao, funcoes=Funcao.query.all())

@main_bp.route('/funcoes/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_funcao(id):
    funcao = Funcao.query.get_or_404(id)
    db.session.delete(funcao)
    db.session.commit()
    flash('Função excluída com sucesso!', 'success')
    return redirect(url_for('main.funcoes'))

# Obras
@main_bp.route('/obras')
@login_required
def obras():
    from datetime import date, timedelta
    from sqlalchemy import func
    
    # Filtros
    nome_filtro = request.args.get('nome', '').strip()
    status_filtro = request.args.get('status', '')
    data_inicio_filtro = request.args.get('data_inicio')
    data_fim_filtro = request.args.get('data_fim')
    
    # Query base com filtro multi-tenant
    query = Obra.query.filter(Obra.admin_id == current_user.id)
    
    # Aplicar filtros
    if nome_filtro:
        query = query.filter(Obra.nome.ilike(f'%{nome_filtro}%'))
    if status_filtro:
        query = query.filter(Obra.status == status_filtro)
    
    obras = query.all()
    
    # Período para KPIs (EXATAMENTE IGUAL À PÁGINA DE DETALHES)
    if data_fim_filtro:
        data_fim = datetime.strptime(data_fim_filtro, '%Y-%m-%d').date()
    else:
        data_fim = date.today()
        
    if data_inicio_filtro:
        data_inicio = datetime.strptime(data_inicio_filtro, '%Y-%m-%d').date()
    else:
        # Período padrão (mês atual) - IGUAL À PÁGINA DE DETALHES
        data_inicio = date.today().replace(day=1)
    
    # Calcular KPIs das obras usando a MESMA LÓGICA da página de detalhes
    for obra in obras:
        # ===== MESMO CÁLCULO DA PÁGINA DE DETALHES =====
        
        # 1. Custos de Transporte (Veículos) - apenas desta obra específica
        custo_transporte = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.obra_id == obra.id,
            CustoVeiculo.data_custo.between(data_inicio, data_fim)
        ).scalar() or 0.0
        
        # 2. Custos de Alimentação
        custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.obra_id == obra.id,
            RegistroAlimentacao.data.between(data_inicio, data_fim)
        ).scalar() or 0.0
        
        # 3. Custos de Mão de Obra
        # Buscar registros de ponto da obra no período
        registros_ponto = db.session.query(RegistroPonto).join(Funcionario).filter(
            RegistroPonto.obra_id == obra.id,
            RegistroPonto.data.between(data_inicio, data_fim),
            RegistroPonto.hora_entrada.isnot(None)  # Só dias trabalhados
        ).all()
        
        custo_mao_obra = 0.0
        total_horas = 0.0
        dias_trabalhados = len(set(rp.data for rp in registros_ponto))
        
        for registro in registros_ponto:
            if registro.hora_entrada and registro.hora_saida:
                # Calcular horas trabalhadas
                entrada = datetime.combine(registro.data, registro.hora_entrada)
                saida = datetime.combine(registro.data, registro.hora_saida)
                
                # Subtrair tempo de almoço (1 hora padrão)
                horas_dia = (saida - entrada).total_seconds() / 3600 - 1
                horas_dia = max(0, horas_dia)  # Não pode ser negativo
                total_horas += horas_dia
                
                # Calcular custo baseado no salário do funcionário
                if registro.funcionario_ref.salario:
                    valor_hora = registro.funcionario_ref.salario / 220  # 220 horas/mês aprox
                    custo_mao_obra += horas_dia * valor_hora
        
        # 4. Custo Total da Obra (EXATAMENTE IGUAL À PÁGINA DE DETALHES)
        custo_obra_total = custo_transporte + custo_alimentacao + custo_mao_obra
        
        # Calcular RDOs e funcionários únicos
        total_rdos = RDO.query.filter_by(obra_id=obra.id).count()
        funcionarios_periodo = db.session.query(Funcionario).join(RegistroPonto).filter(
            RegistroPonto.obra_id == obra.id,
            RegistroPonto.data.between(data_inicio, data_fim),
            RegistroPonto.hora_entrada.isnot(None)
        ).distinct().count()
        
        obra.kpis = type('KPIs', (), {
            'total_rdos': total_rdos,
            'dias_trabalhados': dias_trabalhados,
            'custo_total': custo_obra_total,
            'total_horas': total_horas,
            'funcionarios_periodo': funcionarios_periodo
        })()
    
    # Status disponíveis para filtro
    status_options = ['Em andamento', 'Concluída', 'Pausada', 'Cancelada']
    
    return render_template('obras.html', 
                         obras=obras,
                         filtros={
                             'nome': nome_filtro,
                             'status': status_filtro,
                             'data_inicio': data_inicio_filtro or data_inicio.strftime('%Y-%m-%d'),
                             'data_fim': data_fim_filtro or data_fim.strftime('%Y-%m-%d')
                         },
                         status_options=status_options)

@main_bp.route('/obras/novo', methods=['GET', 'POST'])
@login_required
def nova_obra():
    from models import Servico, ServicoObra, CategoriaServico
    import json
    import logging
    
    # Log para debug em produção
    logging.info(f"[NOVA_OBRA] Usuário {current_user.id} acessando criação de obra")
    
    form = ObraForm()
    
    try:
        # Buscar funcionários com tratamento de erro
        funcionarios = Funcionario.query.filter_by(ativo=True, admin_id=current_user.id).order_by(Funcionario.nome).all()
        form.responsavel_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in funcionarios]
        logging.info(f"[NOVA_OBRA] {len(funcionarios)} funcionários carregados")
    except Exception as e:
        logging.error(f"[NOVA_OBRA] Erro ao carregar funcionários: {e}")
        form.responsavel_id.choices = [(0, 'Selecione...')]
    
    if request.method == 'POST':
        logging.info(f"[NOVA_OBRA] Recebido POST para criação de obra")
        
        if form.validate_on_submit():
            try:
                # Criar obra com tratamento de erro robusto
                obra = Obra(
                    nome=form.nome.data,
                    endereco=form.endereco.data,
                    data_inicio=form.data_inicio.data,
                    data_previsao_fim=form.data_previsao_fim.data,
                    orcamento=float(form.orcamento.data) if form.orcamento.data else 0.0,
                    status=form.status.data,
                    responsavel_id=form.responsavel_id.data if form.responsavel_id.data and form.responsavel_id.data > 0 else None,
                    admin_id=current_user.id
                )
                
                logging.info(f"[NOVA_OBRA] Criando obra: {obra.nome}")
                db.session.add(obra)
                db.session.flush()  # Para obter o ID
                logging.info(f"[NOVA_OBRA] Obra criada com ID: {obra.id}")
                
                # Processar serviços da obra
                servicos_data = request.form.get('servicos_data')
                if servicos_data:
                    try:
                        servicos_list = json.loads(servicos_data)
                        logging.info(f"[NOVA_OBRA] Processando {len(servicos_list)} serviços")
                        
                        for i, servico_item in enumerate(servicos_list):
                            if servico_item.get('servico_id') and servico_item.get('quantidade'):
                                servico_obra = ServicoObra(
                                    obra_id=obra.id,
                                    servico_id=int(servico_item['servico_id']),
                                    quantidade_planejada=float(servico_item['quantidade']),
                                    observacoes=servico_item.get('observacoes', '')
                                )
                                db.session.add(servico_obra)
                                logging.info(f"[NOVA_OBRA] Serviço {i+1} adicionado: ID {servico_item['servico_id']}")
                    except (json.JSONDecodeError, ValueError) as e:
                        logging.error(f"[NOVA_OBRA] Erro ao processar serviços: {e}")
                        flash(f'Erro ao processar serviços: {str(e)}', 'warning')
                        db.session.rollback()
                        return render_template('obra_form.html', form=form, servicos=[], categorias=[])
                
                db.session.commit()
                logging.info(f"[NOVA_OBRA] Obra {obra.nome} criada com sucesso - ID: {obra.id}")
                flash('Obra cadastrada com sucesso!', 'success')
                return redirect(url_for('main.obras'))
                
            except Exception as e:
                db.session.rollback()
                logging.error(f"[NOVA_OBRA] Erro ao criar obra: {e}")
                import traceback
                logging.error(f"[NOVA_OBRA] Traceback: {traceback.format_exc()}")
                flash(f'Erro ao criar obra: {str(e)}', 'error')
        else:
            logging.warning(f"[NOVA_OBRA] Formulário inválido: {form.errors}")
            flash('Por favor, corrija os erros no formulário.', 'warning')
    
    # Buscar dados para o formulário com tratamento de erro
    try:
        servicos_data = db.session.query(
            Servico.id,
            Servico.nome,
            Servico.categoria,
            Servico.unidade_medida,
            Servico.unidade_simbolo,
            Servico.custo_unitario
        ).filter(Servico.ativo == True).order_by(Servico.categoria, Servico.nome).all()
        
        # Converter para objetos acessíveis no template
        servicos = []
        for row in servicos_data:
            servico_obj = type('Servico', (), {
                'id': row.id,
                'nome': row.nome,
                'categoria': row.categoria,
                'unidade_medida': row.unidade_medida,
                'unidade_simbolo': row.unidade_simbolo,
                'custo_unitario': row.custo_unitario
            })()
            servicos.append(servico_obj)
            
        categorias = CategoriaServico.query.filter_by(ativo=True).order_by(CategoriaServico.ordem, CategoriaServico.nome).all()
        logging.info(f"[NOVA_OBRA] {len(servicos)} serviços e {len(categorias)} categorias carregados")
        
    except Exception as e:
        logging.error(f"[NOVA_OBRA] Erro ao carregar dados: {e}")
        servicos = []
        categorias = []
    
    return render_template('obra_form.html', form=form)


# API para buscar serviços (para JavaScript)
@main_bp.route('/api/servicos')
@login_required
def api_servicos():
    from models import Servico
    # Query específica para evitar erro categoria_id
    servicos_data = db.session.query(
        Servico.id,
        Servico.nome,
        Servico.categoria,
        Servico.unidade_medida,
        Servico.unidade_simbolo,
        Servico.custo_unitario
    ).filter(Servico.ativo == True).order_by(Servico.categoria, Servico.nome).all()
    
    return jsonify([{
        'id': row.id,
        'nome': row.nome,
        'categoria': row.categoria,
        'unidade_medida': row.unidade_medida,
        'unidade_simbolo': row.unidade_simbolo or row.unidade_medida,
        'custo_unitario': float(row.custo_unitario or 0)
    } for row in servicos_data])

# API removida - função duplicada

@main_bp.route('/obras/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_obra(id):
    # Verificar se a obra pertence ao admin logado
    obra = Obra.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    form = ObraForm(obj=obra)
    form.responsavel_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True, admin_id=current_user.id).order_by(Funcionario.nome).all()]
    
    if form.validate_on_submit():
        obra.nome = form.nome.data
        obra.endereco = form.endereco.data
        obra.data_inicio = form.data_inicio.data
        obra.data_previsao_fim = form.data_previsao_fim.data
        obra.orcamento = form.orcamento.data or 0.0
        obra.status = form.status.data
        obra.responsavel_id = form.responsavel_id.data if form.responsavel_id.data > 0 else None
        
        db.session.commit()
        flash('Obra atualizada com sucesso!', 'success')
        return redirect(url_for('main.obras'))
    
    return render_template('obra_form.html', form=form, obra=obra)

@main_bp.route('/obra/<int:id>')
@login_required
def detalhes_obra(id):
    from datetime import datetime, date, timedelta
    from sqlalchemy import func
    from models import ServicoObra, Servico
    
    # Verificar se a obra pertence ao admin logado
    obra = Obra.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    
    # Buscar serviços da obra
    servicos_obra = db.session.query(ServicoObra, Servico).join(
        Servico, ServicoObra.servico_id == Servico.id
    ).filter(
        ServicoObra.obra_id == id,
        ServicoObra.ativo == True
    ).order_by(Servico.categoria, Servico.nome).all()
    
    # Obter filtros de data da query string
    data_inicio_filtro = request.args.get('data_inicio')
    data_fim_filtro = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio_filtro:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio_filtro, '%Y-%m-%d').date()
    
    if not data_fim_filtro:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim_filtro, '%Y-%m-%d').date()
    
    # ===== CÁLCULO DOS KPIS =====
    
    # 1. Custos de Transporte (Veículos) - apenas desta obra específica
    custo_transporte = db.session.query(func.sum(CustoVeiculo.valor)).filter(
        CustoVeiculo.obra_id == id,
        CustoVeiculo.data_custo.between(data_inicio, data_fim)
    ).scalar() or 0.0
    
    # 2. Custos de Alimentação
    custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.obra_id == id,
        RegistroAlimentacao.data.between(data_inicio, data_fim)
    ).scalar() or 0.0
    
    # 3. Custos de Mão de Obra
    # Buscar registros de ponto da obra no período
    registros_ponto = db.session.query(RegistroPonto).join(Funcionario).filter(
        RegistroPonto.obra_id == id,
        RegistroPonto.data.between(data_inicio, data_fim),
        RegistroPonto.hora_entrada.isnot(None)  # Só dias trabalhados
    ).all()
    
    custo_mao_obra = 0.0
    total_horas = 0.0
    dias_trabalhados = len(set(rp.data for rp in registros_ponto))
    
    for registro in registros_ponto:
        if registro.hora_entrada and registro.hora_saida:
            # Calcular horas trabalhadas
            entrada = datetime.combine(registro.data, registro.hora_entrada)
            saida = datetime.combine(registro.data, registro.hora_saida)
            
            # Subtrair tempo de almoço (1 hora padrão)
            horas_dia = (saida - entrada).total_seconds() / 3600 - 1
            horas_dia = max(0, horas_dia)  # Não pode ser negativo
            total_horas += horas_dia
            
            # Calcular custo baseado no salário do funcionário
            if registro.funcionario_ref.salario:
                valor_hora = registro.funcionario_ref.salario / 220  # 220 horas/mês aprox
                custo_mao_obra += horas_dia * valor_hora
    
    # 4. Custo Total da Obra (removendo custos_diretos duplicados)
    custo_total = custo_transporte + custo_alimentacao + custo_mao_obra
    
    # ===== RDOs =====
    rdos_periodo = RDO.query.filter(
        RDO.obra_id == id,
        RDO.data_relatorio.between(data_inicio, data_fim)
    ).order_by(RDO.data_relatorio.desc()).all()
    
    rdos_recentes = RDO.query.filter_by(obra_id=id).order_by(RDO.data_relatorio.desc()).limit(5).all()
    total_rdos = RDO.query.filter_by(obra_id=id).count()
    rdos_finalizados = RDO.query.filter_by(obra_id=id, status='Finalizado').count()
    
    # ===== MÉTRICAS ADICIONAIS =====
    
    # Progresso da obra
    progresso_obra = 0
    if total_rdos > 0:
        progresso_obra = min(100, (rdos_finalizados / total_rdos) * 100)
    
    # Calcular dias da obra
    hoje = date.today()
    dias_decorridos = (hoje - obra.data_inicio).days if obra.data_inicio else 0
    dias_restantes = 0
    if obra.data_previsao_fim:
        dias_restantes = max(0, (obra.data_previsao_fim - hoje).days)
    
    # Funcionários únicos que trabalharam na obra no período
    funcionarios_periodo = db.session.query(Funcionario).join(RegistroPonto).filter(
        RegistroPonto.obra_id == id,
        RegistroPonto.data.between(data_inicio, data_fim),
        RegistroPonto.hora_entrada.isnot(None)
    ).distinct().all()
    
    # Custos da obra no período
    custos_obra = CustoObra.query.filter(
        CustoObra.obra_id == id,
        CustoObra.data.between(data_inicio, data_fim)
    ).order_by(CustoObra.data.desc()).all()
    
    # ===== CUSTOS DE TRANSPORTE DETALHADOS =====
    custos_transporte = db.session.query(CustoVeiculo).filter(
        CustoVeiculo.obra_id == id,
        CustoVeiculo.data_custo.between(data_inicio, data_fim)
    ).order_by(CustoVeiculo.data_custo.desc()).all()
    
    custos_transporte_total = sum(c.valor for c in custos_transporte)
    
    # ===== CUSTOS DE MÃO DE OBRA DETALHADOS =====
    custos_mao_obra_detalhados = []
    for registro in registros_ponto:
        if registro.hora_entrada and registro.hora_saida:
            # Calcular horas trabalhadas
            entrada = datetime.combine(registro.data, registro.hora_entrada)
            saida = datetime.combine(registro.data, registro.hora_saida)
            
            # Subtrair tempo de almoço (1 hora padrão)
            horas_dia = (saida - entrada).total_seconds() / 3600 - 1
            horas_dia = max(0, horas_dia)  # Não pode ser negativo
            
            # Calcular custo baseado no salário do funcionário
            if registro.funcionario_ref.salario:
                valor_hora = registro.funcionario_ref.salario / 220  # 220 horas/mês aprox
                total_dia = horas_dia * valor_hora
                
                custos_mao_obra_detalhados.append({
                    'data': registro.data,
                    'funcionario_nome': registro.funcionario_ref.nome,
                    'horas_trabalhadas': horas_dia,
                    'salario_hora': valor_hora,
                    'total_dia': total_dia
                })
    
    # KPIs organizados
    kpis = {
        'custo_transporte': custo_transporte,
        'custo_alimentacao': custo_alimentacao,
        'custo_mao_obra': custo_mao_obra,
        'custo_total': custo_total,
        'dias_trabalhados': dias_trabalhados,
        'total_horas': round(total_horas, 1),
        'funcionarios_periodo': len(funcionarios_periodo),
        'rdos_periodo': len(rdos_periodo)
    }
    
    return render_template('obras/detalhes_obra.html', 
                         obra=obra,
                         servicos_obra=servicos_obra,
                         kpis=kpis,
                         custos_obra=custos_obra,
                         custos_transporte=custos_transporte,
                         custos_transporte_total=custos_transporte_total,
                         custos_mao_obra=custos_mao_obra_detalhados,
                         rdos_periodo=rdos_periodo,
                         rdos_recentes=rdos_recentes,
                         total_rdos=total_rdos,
                         rdos_finalizados=rdos_finalizados,
                         progresso_obra=int(progresso_obra),
                         dias_decorridos=dias_decorridos,
                         dias_restantes=dias_restantes,
                         funcionarios_periodo=funcionarios_periodo,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@main_bp.route('/obras/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_obra(id):
    obra = Obra.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    db.session.delete(obra)
    db.session.commit()
    flash('Obra excluída com sucesso!', 'success')
    return redirect(url_for('main.obras'))

# ===== ROTAS PARA GERENCIAR SERVIÇOS DA OBRA =====
@main_bp.route('/obras/<int:obra_id>/servicos', methods=['POST'])
@login_required
@admin_required
def adicionar_servico_obra(obra_id):
    """Adicionar serviço à obra"""
    try:
        # Verificar acesso à obra
        obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first_or_404()
        
        data = request.get_json()
        servico_id = data.get('servico_id')
        quantidade_planejada = data.get('quantidade_planejada')
        observacoes = data.get('observacoes', '')
        
        # Verificar se o serviço já existe na obra
        servico_existente = ServicoObra.query.filter_by(
            obra_id=obra_id, 
            servico_id=servico_id,
            ativo=True
        ).first()
        
        if servico_existente:
            return jsonify({'success': False, 'message': 'Serviço já está associado a esta obra'})
        
        # Criar nova associação
        servico_obra = ServicoObra(
            obra_id=obra_id,
            servico_id=servico_id,
            quantidade_planejada=quantidade_planejada,
            quantidade_executada=0.0,
            observacoes=observacoes,
            ativo=True
        )
        
        db.session.add(servico_obra)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Serviço adicionado com sucesso'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao adicionar serviço: {str(e)}'})

@main_bp.route('/obras/<int:obra_id>/servicos/<int:servico_id>', methods=['DELETE'])
@login_required
@admin_required
def remover_servico_obra(obra_id, servico_id):
    """Remover serviço da obra"""
    try:
        # Verificar acesso à obra
        obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first_or_404()
        
        # Buscar associação
        servico_obra = ServicoObra.query.filter_by(
            obra_id=obra_id,
            servico_id=servico_id,
            ativo=True
        ).first()
        
        if not servico_obra:
            return jsonify({'success': False, 'message': 'Serviço não encontrado na obra'})
        
        # Marcar como inativo ao invés de excluir
        servico_obra.ativo = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Serviço removido com sucesso'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao remover serviço: {str(e)}'})

@main_bp.route('/api/obras/<int:obra_id>/servicos')
@login_required
def api_servicos_obra_especifica(obra_id):
    """API para carregar serviços de uma obra específica"""
    try:
        # Verificar acesso à obra
        obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first_or_404()
        
        servicos_obra = db.session.query(
            ServicoObra.id,
            Servico.nome,
            Servico.categoria,
            Servico.unidade_medida,
            Servico.unidade_simbolo,
            ServicoObra.quantidade_planejada,
            ServicoObra.quantidade_executada,
            ServicoObra.observacoes
        ).join(
            Servico, ServicoObra.servico_id == Servico.id
        ).filter(
            ServicoObra.obra_id == obra_id,
            ServicoObra.ativo == True
        ).order_by(Servico.nome).all()
        
        return jsonify([{
            'id': row.id,
            'nome': row.nome,
            'categoria': row.categoria,
            'unidade_medida': row.unidade_medida,
            'unidade_simbolo': row.unidade_simbolo or row.unidade_medida,
            'quantidade_planejada': float(row.quantidade_planejada or 0),
            'quantidade_executada': float(row.quantidade_executada or 0),
            'observacoes': row.observacoes or ''
        } for row in servicos_obra])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== NOVOS KPIs FINANCEIROS =====
@main_bp.route('/api/obras/<int:obra_id>/kpis-financeiros')
@login_required
def kpis_financeiros_obra(obra_id):
    """API para obter KPIs financeiros avançados de uma obra"""
    try:
        # Verificar acesso
        obra = Obra.query.get_or_404(obra_id)
        if not can_access_data(current_user, obra.admin_id):
            return jsonify({'erro': 'Acesso negado'}), 403
        
        # Obter parâmetros de período
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Imports dinâmicos para evitar circular import
        from kpis_financeiros import KPIsFinanceiros, KPIsOperacionais
        
        # Calcular KPIs financeiros
        custo_por_m2 = KPIsFinanceiros.custo_por_m2(obra_id, data_inicio, data_fim)
        margem_lucro = KPIsFinanceiros.margem_lucro_realizada(obra_id, data_inicio, data_fim)
        desvio_orcamentario = KPIsFinanceiros.desvio_orcamentario(obra_id, data_inicio, data_fim)
        roi_projetado = KPIsFinanceiros.roi_projetado(obra_id, data_inicio, data_fim)
        velocidade_queima = KPIsFinanceiros.velocidade_queima_orcamento(obra_id, data_inicio, data_fim)
        
        # KPIs operacionais complementares
        produtividade_obra = KPIsOperacionais.indice_produtividade_obra(obra_id, data_inicio, data_fim)
        
        return jsonify({
            'obra_id': obra_id,
            'obra_nome': obra.nome,
            'periodo': {
                'inicio': data_inicio.isoformat() if data_inicio else None,
                'fim': data_fim.isoformat() if data_fim else None
            },
            'kpis_financeiros': {
                'custo_por_m2': custo_por_m2,
                'margem_lucro': margem_lucro,
                'desvio_orcamentario': desvio_orcamentario,
                'roi_projetado': roi_projetado,
                'velocidade_queima': velocidade_queima
            },
            'kpis_operacionais': {
                'produtividade_obra': produtividade_obra
            }
        })
        
    except Exception as e:
        return jsonify({
            'erro': f'Erro ao calcular KPIs: {str(e)}'
        }), 500

@main_bp.route('/obras/<int:obra_id>/dashboard-executivo')
@login_required
def dashboard_executivo_obra(obra_id):
    """Dashboard executivo com KPIs avançados"""
    try:
        obra = Obra.query.get_or_404(obra_id)
        if not can_access_data(current_user, obra.admin_id):
            flash('Acesso negado', 'danger')
            return redirect(url_for('main.obras'))
        
        # Obter filtros de período
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        # Definir período padrão (mês atual)
        if not data_inicio:
            data_inicio = date.today().replace(day=1)
        else:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        
        if not data_fim:
            data_fim = date.today()
        else:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Imports dinâmicos para evitar circular import
        from calculadora_obra import CalculadoraObra
        from kpis_financeiros import KPIsFinanceiros, KPIsOperacionais
        
        # Usar calculadora unificada
        calculadora = CalculadoraObra(obra_id, data_inicio, data_fim)
        custos_detalhados = calculadora.calcular_custo_total()
        estatisticas = calculadora.obter_estatisticas_periodo()
        
        # Calcular KPIs avançados
        kpis_financeiros = {
            'custo_por_m2': KPIsFinanceiros.custo_por_m2(obra_id, data_inicio, data_fim),
            'margem_lucro': KPIsFinanceiros.margem_lucro_realizada(obra_id, data_inicio, data_fim),
            'desvio_orcamentario': KPIsFinanceiros.desvio_orcamentario(obra_id, data_inicio, data_fim),
            'roi_projetado': KPIsFinanceiros.roi_projetado(obra_id, data_inicio, data_fim),
            'velocidade_queima': KPIsFinanceiros.velocidade_queima_orcamento(obra_id, data_inicio, data_fim)
        }
        
        kpis_operacionais = {
            'produtividade_obra': KPIsOperacionais.indice_produtividade_obra(obra_id, data_inicio, data_fim)
        }
        
        return render_template('dashboard_executivo_obra.html',
                             obra=obra,
                             custos=custos_detalhados,
                             estatisticas=estatisticas,
                             kpis_financeiros=kpis_financeiros,
                             kpis_operacionais=kpis_operacionais,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        flash(f'Erro ao gerar dashboard executivo: {str(e)}', 'danger')
        return redirect(url_for('main.obras'))

@main_bp.route('/api/obras/<int:obra_id>/custo-calculadora')
@login_required
def custo_calculadora_api(obra_id):
    """API para obter custos usando a calculadora unificada"""
    try:
        obra = Obra.query.get_or_404(obra_id)
        if not can_access_data(current_user, obra.admin_id):
            return jsonify({'erro': 'Acesso negado'}), 403
        
        # Obter parâmetros de período
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Import dinâmico para evitar circular import
        from calculadora_obra import CalculadoraObra
        
        # Usar calculadora unificada
        calculadora = CalculadoraObra(obra_id, data_inicio, data_fim)
        custos = calculadora.calcular_custo_total()
        estatisticas = calculadora.obter_estatisticas_periodo()
        
        return jsonify({
            'obra_id': obra_id,
            'custos': custos,
            'estatisticas': estatisticas,
            'metodo': 'calculadora_unificada',
            'periodo': {
                'inicio': data_inicio.isoformat() if data_inicio else None,
                'fim': data_fim.isoformat() if data_fim else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'erro': f'Erro ao calcular custos: {str(e)}'
        }), 500

# Veículos
@main_bp.route('/veiculos')
@login_required
def veiculos():
    # Filtrar por admin_id para multi-tenant
    veiculos = Veiculo.query.filter(Veiculo.admin_id == current_user.id).all()
    funcionarios = Funcionario.query.filter_by(ativo=True, admin_id=current_user.id).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(status='Em andamento', admin_id=current_user.id).all()
    return render_template('veiculos.html', 
                         veiculos=veiculos, 
                         funcionarios=funcionarios, 
                         obras=obras)

@main_bp.route('/veiculos/novo', methods=['GET', 'POST'])
@login_required
def novo_veiculo():
    form = VeiculoForm()
    if form.validate_on_submit():
        veiculo = Veiculo(
            placa=form.placa.data,
            marca=form.marca.data,
            modelo=form.modelo.data,
            ano=form.ano.data,
            tipo=form.tipo.data,
            status=form.status.data,
            km_atual=form.km_atual.data or 0,
            data_ultima_manutencao=form.data_ultima_manutencao.data,
            data_proxima_manutencao=form.data_proxima_manutencao.data,
            admin_id=current_user.id  # Associar veículo ao admin logado
        )
        db.session.add(veiculo)
        db.session.commit()
        flash('Veículo cadastrado com sucesso!', 'success')
        return redirect(url_for('main.veiculos'))
    
    return render_template('veiculos.html', form=form, veiculos=Veiculo.query.all())

@main_bp.route('/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    form = VeiculoForm(obj=veiculo)
    
    if form.validate_on_submit():
        veiculo.placa = form.placa.data
        veiculo.marca = form.marca.data
        veiculo.modelo = form.modelo.data
        veiculo.ano = form.ano.data
        veiculo.tipo = form.tipo.data
        veiculo.status = form.status.data
        veiculo.km_atual = form.km_atual.data or 0
        veiculo.data_ultima_manutencao = form.data_ultima_manutencao.data
        veiculo.data_proxima_manutencao = form.data_proxima_manutencao.data
        
        db.session.commit()
        flash('Veículo atualizado com sucesso!', 'success')
        return redirect(url_for('main.veiculos'))
    
    return render_template('veiculos.html', form=form, veiculo=veiculo, veiculos=Veiculo.query.all())

@main_bp.route('/veiculos/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    db.session.delete(veiculo)
    db.session.commit()
    flash('Veículo excluído com sucesso!', 'success')
    return redirect(url_for('main.veiculos'))

@main_bp.route('/veiculos/<int:id>/detalhes')
@login_required
def detalhes_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    
    # Buscar registros de uso
    usos = UsoVeiculo.query.filter_by(veiculo_id=id).order_by(UsoVeiculo.data_uso.desc()).all()
    
    # Buscar registros de custo
    custos = CustoVeiculo.query.filter_by(veiculo_id=id).order_by(CustoVeiculo.data_custo.desc()).all()
    
    # Dados para os formulários
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter(Obra.status.in_(['Em andamento', 'Pausada'])).order_by(Obra.nome).all()
    
    # KPIs do veículo
    custo_total = sum(custo.valor for custo in custos)
    
    # Calcular média de KM por uso
    km_total = 0
    usos_com_km = 0
    for uso in usos:
        if uso.km_inicial and uso.km_final and uso.km_final > uso.km_inicial:
            km_total += (uso.km_final - uso.km_inicial)
            usos_com_km += 1
    
    media_km = km_total / usos_com_km if usos_com_km > 0 else 0
    
    kpis = {
        'custo_total': custo_total,
        'total_usos': len(usos),
        'total_custos': len(custos),
        'media_km': media_km
    }
    
    # Dados para gráfico de uso por obra
    from sqlalchemy import func
    uso_por_obra = db.session.query(
        Obra.nome,
        func.count(UsoVeiculo.id).label('total_usos')
    ).join(UsoVeiculo, Obra.id == UsoVeiculo.obra_id).filter(
        UsoVeiculo.veiculo_id == id
    ).group_by(Obra.id, Obra.nome).all()
    
    # Preparar dados para o gráfico de pizza
    grafico_uso_obras = {
        'labels': [uso[0] for uso in uso_por_obra],
        'data': [uso[1] for uso in uso_por_obra],
        'total': sum([uso[1] for uso in uso_por_obra])
    }
    
    return render_template('veiculos/detalhes_veiculo.html', 
                         veiculo=veiculo, 
                         usos=usos, 
                         custos=custos,
                         kpis=kpis,
                         funcionarios=funcionarios,
                         obras=obras,
                         grafico_uso_obras=grafico_uso_obras)

@main_bp.route('/veiculos/uso', methods=['POST'])
@login_required
def novo_uso_veiculo_lista():
    """Registra novo uso de veículo a partir da lista principal"""
    try:
        veiculo_id = request.form.get('veiculo_id')
        funcionario_id = request.form.get('funcionario_id')
        obra_id = request.form.get('obra_id')
        data_uso = datetime.strptime(request.form.get('data_uso'), '%Y-%m-%d').date()
        km_inicial = int(request.form.get('km_inicial')) if request.form.get('km_inicial') else None
        km_final = int(request.form.get('km_final')) if request.form.get('km_final') else None
        horario_saida = datetime.strptime(request.form.get('horario_saida'), '%H:%M').time() if request.form.get('horario_saida') else None
        horario_chegada = datetime.strptime(request.form.get('horario_chegada'), '%H:%M').time() if request.form.get('horario_chegada') else None
        finalidade = request.form.get('finalidade')
        observacoes = request.form.get('observacoes')
        
        if not funcionario_id:
            flash('Funcionário é obrigatório para registrar uso do veículo!', 'error')
            return redirect(url_for('main.veiculos'))
        
        novo_uso = UsoVeiculo(
            veiculo_id=veiculo_id,
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            data_uso=data_uso,
            km_inicial=km_inicial,
            km_final=km_final,
            horario_saida=horario_saida,
            horario_chegada=horario_chegada,
            finalidade=finalidade,
            observacoes=observacoes
        )
        
        db.session.add(novo_uso)
        
        # Atualizar KM do veículo se fornecido
        if km_final:
            veiculo = Veiculo.query.get(veiculo_id)
            if veiculo:
                veiculo.km_atual = km_final
        
        db.session.commit()
        
        flash('Uso do veículo registrado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar uso: {str(e)}', 'error')
    
    return redirect(url_for('main.veiculos'))

@main_bp.route('/veiculos/custo', methods=['POST'])
@login_required
def novo_custo_veiculo_lista():
    """Registra novo custo de veículo a partir da lista principal"""
    try:
        veiculo_id = request.form.get('veiculo_id')
        data_custo = datetime.strptime(request.form.get('data_custo'), '%Y-%m-%d').date()
        valor = float(request.form.get('valor'))
        tipo_custo = request.form.get('tipo_custo')
        fornecedor = request.form.get('fornecedor')
        descricao = request.form.get('descricao')
        km_atual = int(request.form.get('km_atual')) if request.form.get('km_atual') else None
        
        novo_custo = CustoVeiculo(
            veiculo_id=veiculo_id,
            data_custo=data_custo,
            valor=valor,
            tipo_custo=tipo_custo,
            descricao=descricao,
            km_atual=km_atual,
            fornecedor=fornecedor
        )
        
        db.session.add(novo_custo)
        
        # Atualizar KM do veículo se fornecido
        if km_atual:
            veiculo = Veiculo.query.get(veiculo_id)
            if veiculo:
                veiculo.km_atual = km_atual
        
        db.session.commit()
        
        flash('Custo de veículo registrado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar custo do veículo: {str(e)}', 'error')
    
    return redirect(url_for('main.veiculos'))

@main_bp.route('/veiculos/<int:id>/dados')
@login_required
def dados_veiculo(id):
    """Retorna dados do veículo em JSON para edição via AJAX"""
    veiculo = Veiculo.query.get_or_404(id)
    return jsonify({
        'id': veiculo.id,
        'placa': veiculo.placa,
        'marca': veiculo.marca,
        'modelo': veiculo.modelo,
        'ano': veiculo.ano,
        'tipo': veiculo.tipo,
        'km_atual': veiculo.km_atual,
        'status': veiculo.status,
        'data_ultima_manutencao': veiculo.data_ultima_manutencao.strftime('%Y-%m-%d') if veiculo.data_ultima_manutencao else '',
        'data_proxima_manutencao': veiculo.data_proxima_manutencao.strftime('%Y-%m-%d') if veiculo.data_proxima_manutencao else ''
    })

@main_bp.route('/veiculos/<int:id>/novo-uso', methods=['GET', 'POST'])
@login_required
def novo_uso_veiculo(id):
    """Página e processamento de novo uso de veículo"""
    veiculo = Veiculo.query.get_or_404(id)
    form = UsoVeiculoForm()
    
    # Preencher choices dinamicamente
    form.funcionario_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()]
    form.obra_id.choices = [(0, 'Selecione...')] + [(o.id, o.nome) for o in Obra.query.filter(Obra.status.in_(['Em andamento', 'Pausada'])).all()]
    
    # Definir veiculo_id no formulário
    form.veiculo_id.data = id
    
    if request.method == 'GET':
        return render_template('veiculos/novo_uso.html', form=form, veiculo=veiculo)
    
    if form.validate_on_submit():
        try:
            uso = UsoVeiculo(
                veiculo_id=id,
                funcionario_id=form.funcionario_id.data,
                obra_id=form.obra_id.data if form.obra_id.data and form.obra_id.data != 0 else None,
                data_uso=form.data_uso.data,
                km_inicial=form.km_inicial.data,
                km_final=form.km_final.data,
                horario_saida=form.horario_saida.data,
                horario_chegada=form.horario_chegada.data,
                finalidade=form.finalidade.data,
                observacoes=form.observacoes.data
            )
            db.session.add(uso)
            
            # Atualizar KM do veículo se fornecido
            if form.km_final.data:
                veiculo.km_atual = form.km_final.data
            
            db.session.commit()
            flash('Uso de veículo registrado com sucesso!', 'success')
            return redirect(url_for('main.detalhes_veiculo', id=id))
        except Exception as e:
            flash(f'Erro ao registrar uso: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return render_template('veiculos/novo_uso.html', form=form, veiculo=veiculo)

@main_bp.route('/veiculos/<int:id>/novo-custo', methods=['GET', 'POST'])
@login_required
def novo_custo_veiculo_form(id):
    """Página e processamento de novo custo de veículo"""
    veiculo = Veiculo.query.get_or_404(id)
    
    # Carregar obras do admin
    obras = Obra.query.filter(
        Obra.admin_id == current_user.id
    ).order_by(Obra.nome).all()
    
    if request.method == 'POST':
        # Obter dados do formulário
        obra_id = request.form.get('obra_id')
        data_custo = request.form.get('data_custo')
        valor = request.form.get('valor')
        tipo_custo = request.form.get('tipo_custo')
        descricao = request.form.get('descricao', '')
        km_atual = request.form.get('km_atual')
        fornecedor = request.form.get('fornecedor', '')
        
        # Validações
        erros = []
        if not obra_id:
            erros.append('Obra é obrigatória')
        if not data_custo:
            erros.append('Data é obrigatória')
        if not valor:
            erros.append('Valor é obrigatório')
        if not tipo_custo:
            erros.append('Tipo de custo é obrigatório')
        
        if erros:
            for erro in erros:
                flash(erro, 'error')
            return render_template('veiculos/novo_custo.html', veiculo=veiculo, obras=obras,
                                 form_data=request.form)
        
        try:
            # Criar o custo
            custo = CustoVeiculo(
                veiculo_id=id,
                obra_id=int(obra_id),
                data_custo=datetime.strptime(data_custo, '%Y-%m-%d').date(),
                valor=float(valor),
                tipo_custo=tipo_custo,
                descricao=descricao,
                km_atual=int(km_atual) if km_atual else None,
                fornecedor=fornecedor
            )
            db.session.add(custo)
            
            # Atualizar KM do veículo se fornecido
            if km_atual:
                veiculo.km_atual = int(km_atual)
            
            db.session.commit()
            flash('Custo de veículo registrado com sucesso!', 'success')
            return redirect(url_for('main.detalhes_veiculo', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar custo: {str(e)}', 'error')
    
    return render_template('veiculos/novo_custo.html', veiculo=veiculo, obras=obras, 
                         form_data={}, today=date.today().strftime('%Y-%m-%d'))

# ============================================================================
# MÓDULO DE SERVIÇOS - SIGE v6.3
# Sistema de cadastro de serviços para coleta de dados reais via RDO
# ============================================================================

@main_bp.route('/servicos')
@login_required
@admin_required
def servicos():
    """Página de listagem de serviços com filtros"""
    try:
        # Filtros
        categoria = request.args.get('categoria')
        ativo = request.args.get('ativo')
        
        # Query específica para evitar erro categoria_id
        servicos_data = db.session.query(
            Servico.id,
            Servico.nome,
            Servico.descricao,
            Servico.categoria,
            Servico.unidade_medida,
            Servico.unidade_simbolo,
            Servico.custo_unitario,
            Servico.complexidade,
            Servico.requer_especializacao,
            Servico.ativo,
            Servico.created_at,
            Servico.updated_at
        )
        
        # Aplicar filtros de pesquisa
        if categoria:
            servicos_data = servicos_data.filter(Servico.categoria == categoria)
        if ativo:
            servicos_data = servicos_data.filter(Servico.ativo == (ativo == 'true'))
        
        # Executar query e converter para objetos com subatividades
        servicos_raw = servicos_data.order_by(Servico.nome).all()
        servicos = []
        for row in servicos_raw:
            # Buscar subatividades para este serviço (ou lista vazia se não existir)
            try:
                subatividades = SubAtividade.query.filter_by(servico_id=row.id).all()
            except:
                subatividades = []
            
            # Criar objeto compatível com template
            servico_obj = type('Servico', (), {
                'id': row.id,
                'nome': row.nome,
                'descricao': row.descricao,
                'categoria': row.categoria,
                'unidade_medida': row.unidade_medida,
                'unidade_simbolo': row.unidade_simbolo,
                'custo_unitario': row.custo_unitario,
                'complexidade': row.complexidade,
                'requer_especializacao': row.requer_especializacao,
                'ativo': row.ativo,
                'created_at': row.created_at,
                'updated_at': row.updated_at,
                'subatividades': subatividades or []
            })()
            servicos.append(servico_obj)
        
        # Dados para filtros - buscar categorias distintas do campo categoria (string)
        categorias_query = db.session.query(Servico.categoria).distinct().filter(Servico.categoria.isnot(None)).all()
        categorias = [cat[0] for cat in categorias_query if cat[0]]
        
        return render_template('servicos.html', 
                             servicos=servicos, 
                             categorias=categorias,
                             filtros={'categoria': categoria, 'ativo': ativo})
                             
    except Exception as e:
        flash(f'Erro ao carregar serviços: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main_bp.route('/api/servicos', methods=['POST'])
@login_required
def api_criar_servico():
    """API para criar serviço com subatividades"""
    try:
        dados = request.get_json()
        
        # Validar dados obrigatórios
        if not dados.get('nome') or not dados.get('categoria') or not dados.get('unidade_medida'):
            return jsonify({'success': False, 'message': 'Campos obrigatórios não preenchidos'})
        
        # Verificar se já existe serviço com mesmo nome
        servico_existente = db.session.query(Servico.id).filter(Servico.nome == dados['nome']).first()
        if servico_existente:
            return jsonify({'success': False, 'message': 'Já existe um serviço com este nome'})
        
        # Criar serviço
        servico = Servico(
            nome=dados['nome'],
            descricao=dados.get('descricao', ''),
            categoria=dados['categoria'],
            unidade_medida=dados['unidade_medida'],
            complexidade=int(dados.get('complexidade', 3)),
            requer_especializacao=dados.get('requer_especializacao', False),
            ativo=True
        )
        
        db.session.add(servico)
        db.session.flush()  # Para obter o ID do serviço
        
        # Criar subatividades
        for i, sub_dados in enumerate(dados.get('subatividades', [])):
            if sub_dados.get('nome'):
                subatividade = SubAtividade(
                    servico_id=servico.id,
                    nome=sub_dados['nome'],
                    descricao=sub_dados.get('descricao', ''),
                    ordem_execucao=i + 1,
                    ferramentas_necessarias=sub_dados.get('ferramentas_necessarias', ''),
                    materiais_principais=sub_dados.get('materiais_principais', ''),
                    requer_aprovacao=sub_dados.get('requer_aprovacao', False),
                    pode_executar_paralelo=sub_dados.get('pode_executar_paralelo', True),
                    qualificacao_minima=sub_dados.get('qualificacao_minima', ''),
                    ativo=True
                )
                db.session.add(subatividade)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Serviço criado com sucesso!',
            'servico_id': servico.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>', methods=['GET'])
@login_required
def api_obter_servico(id):
    """API para obter dados de um serviço com subatividades"""
    try:
        servico = Servico.query.get_or_404(id)
        
        # Buscar subatividades
        subatividades = SubAtividade.query.filter_by(servico_id=id).order_by(SubAtividade.ordem_execucao).all()
        
        dados = {
            'id': servico.id,
            'nome': servico.nome,
            'descricao': servico.descricao,
            'categoria': servico.categoria,
            'unidade_medida': servico.unidade_medida,
            'complexidade': servico.complexidade,
            'requer_especializacao': servico.requer_especializacao,
            'ativo': servico.ativo,
            'subatividades': []
        }
        
        for sub in subatividades:
            dados['subatividades'].append({
                'id': sub.id,
                'nome': sub.nome,
                'descricao': sub.descricao,
                'ordem_execucao': sub.ordem_execucao,
                'ferramentas_necessarias': sub.ferramentas_necessarias,
                'materiais_principais': sub.materiais_principais,
                'requer_aprovacao': sub.requer_aprovacao,
                'pode_executar_paralelo': sub.pode_executar_paralelo,
                'qualificacao_minima': sub.qualificacao_minima
            })
        
        return jsonify({'success': True, 'dados': dados})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao obter serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>', methods=['PUT'])
@login_required
def api_atualizar_servico(id):
    """API para atualizar serviço com subatividades"""
    try:
        servico = Servico.query.get_or_404(id)
        dados = request.get_json()
        
        # Validar dados obrigatórios
        if not dados.get('nome') or not dados.get('categoria') or not dados.get('unidade_medida'):
            return jsonify({'success': False, 'message': 'Campos obrigatórios não preenchidos'})
        
        # Verificar se já existe outro serviço com mesmo nome
        servico_existente = db.session.query(Servico.id).filter(
            and_(Servico.nome == dados['nome'], Servico.id != id)
        ).first()
        if servico_existente:
            return jsonify({'success': False, 'message': 'Já existe um serviço com este nome'})
        
        # Atualizar serviço
        servico.nome = dados['nome']
        servico.descricao = dados.get('descricao', '')
        servico.categoria = dados['categoria']
        servico.unidade_medida = dados['unidade_medida']
        servico.complexidade = int(dados.get('complexidade', 3))
        servico.requer_especializacao = dados.get('requer_especializacao', False)
        servico.updated_at = datetime.utcnow()
        
        # Remover subatividades antigas
        SubAtividade.query.filter_by(servico_id=id).delete()
        
        # Criar novas subatividades
        for i, sub_dados in enumerate(dados.get('subatividades', [])):
            if sub_dados.get('nome'):
                subatividade = SubAtividade(
                    servico_id=servico.id,
                    nome=sub_dados['nome'],
                    descricao=sub_dados.get('descricao', ''),
                    ordem_execucao=i + 1,
                    ferramentas_necessarias=sub_dados.get('ferramentas_necessarias', ''),
                    materiais_principais=sub_dados.get('materiais_principais', ''),
                    requer_aprovacao=sub_dados.get('requer_aprovacao', False),
                    pode_executar_paralelo=sub_dados.get('pode_executar_paralelo', True),
                    qualificacao_minima=sub_dados.get('qualificacao_minima', ''),
                    ativo=True
                )
                db.session.add(subatividade)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Serviço atualizado com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>', methods=['DELETE'])
@login_required
def api_excluir_servico(id):
    """API para excluir serviço"""
    try:
        servico = Servico.query.get_or_404(id)
        
        # Verificar se há histórico de produtividade
        historico_count = HistoricoProdutividadeServico.query.filter_by(servico_id=id).count()
        if historico_count > 0:
            return jsonify({
                'success': False, 
                'message': f'Não é possível excluir. Existem {historico_count} registros de produtividade vinculados a este serviço.'
            })
        
        db.session.delete(servico)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Serviço excluído com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao excluir serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>/toggle-ativo', methods=['POST'])
@login_required
def api_toggle_ativo_servico(id):
    """API para ativar/desativar serviço"""
    try:
        servico = Servico.query.get_or_404(id)
        servico.ativo = not servico.ativo
        servico.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        status = 'ativado' if servico.ativo else 'desativado'
        return jsonify({
            'success': True, 
            'message': f'Serviço {status} com sucesso!',
            'ativo': servico.ativo
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao alterar status: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>/produtividade', methods=['GET'])
@login_required
def api_produtividade_servico(id):
    """API para obter dados de produtividade do serviço"""
    try:
        servico = Servico.query.get_or_404(id)
        
        # Buscar histórico de produtividade
        historicos = HistoricoProdutividadeServico.query.filter_by(servico_id=id).all()
        
        if not historicos:
            return jsonify({
                'success': True,
                'dados': {
                    'servico': servico.nome,
                    'unidade_medida': servico.unidade_medida,
                    'total_execucoes': 0,
                    'estimativas': None,
                    'historico': []
                }
            })
        
        # Calcular estimativas
        tempo_medio = sum(float(h.tempo_execucao_horas) for h in historicos) / len(historicos)
        custo_medio = sum(float(h.custo_mao_obra_real) for h in historicos) / len(historicos)
        produtividade_media = sum(float(h.produtividade_hora) for h in historicos) / len(historicos)
        
        dados = {
            'servico': servico.nome,
            'unidade_medida': servico.unidade_medida,
            'total_execucoes': len(historicos),
            'estimativas': {
                'tempo_medio_por_unidade': round(tempo_medio, 2),
                'custo_medio_por_unidade': round(custo_medio, 2),
                'produtividade_media': round(produtividade_media, 4)
            },
            'historico': []
        }
        
        # Histórico detalhado
        for h in historicos[-10:]:  # Últimos 10 registros
            dados['historico'].append({
                'data': h.data_execucao.strftime('%d/%m/%Y'),
                'obra': h.obra.nome,
                'funcionario': h.funcionario.nome,
                'quantidade': float(h.quantidade_executada),
                'tempo_horas': float(h.tempo_execucao_horas),
                'custo_real': float(h.custo_mao_obra_real),
                'produtividade': float(h.produtividade_hora)
            })
        
        return jsonify({'success': True, 'dados': dados})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao obter produtividade: {str(e)}'})

# ============================================================================
# ROTAS PARA GERENCIAR CATEGORIAS DE SERVIÇOS
# ============================================================================

@main_bp.route('/api/categorias', methods=['GET'])
@login_required
@admin_required
def listar_categorias():
    """API para listar categorias ativas"""
    try:
        categorias = CategoriaServico.query.filter_by(
            ativo=True,
            admin_id=current_user.id
        ).order_by(CategoriaServico.ordem, CategoriaServico.nome).all()
        
        return jsonify([{
            'id': cat.id,
            'nome': cat.nome,
            'descricao': cat.descricao,
            'cor': cat.cor,
            'icone': cat.icone,
            'ordem': cat.ordem
        } for cat in categorias])
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao listar categorias: {str(e)}'})

@main_bp.route('/api/categorias', methods=['POST'])
@login_required
@admin_required
def criar_categoria():
    """API para criar nova categoria"""
    try:
        data = request.get_json()
        
        # Verificar se já existe categoria com mesmo nome
        categoria_existente = CategoriaServico.query.filter_by(
            nome=data.get('nome'),
            admin_id=current_user.id
        ).first()
        
        if categoria_existente:
            return jsonify({'success': False, 'message': 'Já existe uma categoria com este nome'})
        
        # Criar nova categoria
        categoria = CategoriaServico(
            nome=data.get('nome'),
            descricao=data.get('descricao', ''),
            cor=data.get('cor', '#6c757d'),
            icone=data.get('icone', 'fas fa-wrench'),
            ordem=data.get('ordem', 0),
            admin_id=current_user.id
        )
        
        db.session.add(categoria)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Categoria criada com sucesso!',
            'categoria': {
                'id': categoria.id,
                'nome': categoria.nome,
                'descricao': categoria.descricao,
                'cor': categoria.cor,
                'icone': categoria.icone,
                'ordem': categoria.ordem
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar categoria: {str(e)}'})

@main_bp.route('/api/categorias/<int:categoria_id>', methods=['PUT'])
@login_required
@admin_required
def editar_categoria(categoria_id):
    """API para editar categoria existente"""
    try:
        categoria = CategoriaServico.query.filter_by(
            id=categoria_id,
            admin_id=current_user.id
        ).first()
        
        if not categoria:
            return jsonify({'success': False, 'message': 'Categoria não encontrada'})
        
        data = request.get_json()
        
        # Verificar se nome já existe em outra categoria
        categoria_nome_existente = CategoriaServico.query.filter(
            CategoriaServico.nome == data.get('nome'),
            CategoriaServico.id != categoria_id,
            CategoriaServico.admin_id == current_user.id
        ).first()
        
        if categoria_nome_existente:
            return jsonify({'success': False, 'message': 'Já existe uma categoria com este nome'})
        
        # Atualizar categoria
        categoria.nome = data.get('nome', categoria.nome)
        categoria.descricao = data.get('descricao', categoria.descricao)
        categoria.cor = data.get('cor', categoria.cor)
        categoria.icone = data.get('icone', categoria.icone)
        categoria.ordem = data.get('ordem', categoria.ordem)
        categoria.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Categoria atualizada com sucesso!',
            'categoria': {
                'id': categoria.id,
                'nome': categoria.nome,
                'descricao': categoria.descricao,
                'cor': categoria.cor,
                'icone': categoria.icone,
                'ordem': categoria.ordem
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao editar categoria: {str(e)}'})

@main_bp.route('/api/categorias/<int:categoria_id>', methods=['DELETE'])
@login_required
@admin_required
def excluir_categoria(categoria_id):
    """API para excluir categoria"""
    try:
        categoria = CategoriaServico.query.filter_by(
            id=categoria_id,
            admin_id=current_user.id
        ).first()
        
        if not categoria:
            return jsonify({'success': False, 'message': 'Categoria não encontrada'})
        
        # Verificar se há serviços usando esta categoria (usar campo categoria string)
        servicos_usando = db.session.query(Servico).filter(
            Servico.categoria == categoria.nome
        ).count()
        
        if servicos_usando > 0:
            return jsonify({
                'success': False, 
                'message': f'Não é possível excluir. Existem {servicos_usando} serviços usando esta categoria.'
            })
        
        # Marcar como inativo ao invés de excluir
        categoria.ativo = False
        categoria.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Categoria removida com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao excluir categoria: {str(e)}'})

# ================================
# ROTAS DO SISTEMA DE PROPOSTAS
# ================================

@main_bp.route('/propostas')
@login_required
@admin_required
def lista_propostas():
    """Lista todas as propostas do admin atual"""
    propostas = PropostaComercial.query.filter_by(admin_id=current_user.id).order_by(desc(PropostaComercial.created_at)).all()
    return render_template('propostas/lista_propostas.html', propostas=propostas)

@main_bp.route('/propostas/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_proposta():
    """Cria uma nova proposta comercial"""
    if request.method == 'POST':
        try:
            # Gerar número da proposta
            ultimo_numero = db.session.query(func.max(PropostaComercial.id)).scalar() or 0
            numero_proposta = f"PROP-{datetime.now().year}-{ultimo_numero + 1:03d}"
            
            # Criar proposta
            proposta = PropostaComercial(
                numero_proposta=numero_proposta,
                cliente_nome=request.form['cliente_nome'],
                cliente_email=request.form['cliente_email'],
                cliente_telefone=request.form.get('cliente_telefone'),
                cliente_cpf_cnpj=request.form.get('cliente_cpf_cnpj'),
                endereco_obra=request.form['endereco_obra'],
                descricao_obra=request.form['descricao_obra'],
                area_total_m2=float(request.form['area_total_m2']) if request.form.get('area_total_m2') else None,
                valor_proposta=float(request.form['valor_proposta']),
                prazo_execucao=int(request.form['prazo_execucao']) if request.form.get('prazo_execucao') else None,
                admin_id=current_user.id,
                criado_por_id=current_user.id
            )
            
            db.session.add(proposta)
            db.session.flush()  # Para obter o ID da proposta
            
            # Adicionar serviços
            servicos_data = request.form.getlist('servicos')
            for i, servico_json in enumerate(servicos_data):
                servico = json.loads(servico_json)
                servico_obj = ServicoPropostaComercial(
                    proposta_id=proposta.id,
                    descricao_servico=servico['descricao'],
                    quantidade=servico['quantidade'],
                    unidade=servico['unidade'],
                    valor_unitario=servico['valor_unitario'],
                    valor_total=servico['valor_total'],
                    observacoes=servico.get('observacoes'),
                    ordem=i + 1
                )
                db.session.add(servico_obj)
            
            db.session.commit()
            flash('Proposta criada com sucesso!', 'success')
            return redirect(url_for('main.detalhes_proposta', id=proposta.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar proposta: {str(e)}', 'danger')
            return redirect(url_for('main.nova_proposta'))
    
    return render_template('propostas/nova_proposta.html')

@main_bp.route('/propostas/<int:id>')
@login_required
@admin_required
def detalhes_proposta(id):
    """Exibe os detalhes de uma proposta"""
    proposta = PropostaComercial.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    return render_template('propostas/detalhes_proposta.html', proposta=proposta)

@main_bp.route('/propostas/<int:id>/enviar', methods=['POST'])
@login_required
@admin_required
def enviar_proposta(id):
    """Envia a proposta para o cliente"""
    try:
        proposta = PropostaComercial.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
        
        # Gerar token de acesso único
        import secrets
        token = secrets.token_urlsafe(32)
        
        proposta.token_acesso = token
        proposta.data_envio = datetime.utcnow()
        proposta.data_expiracao = datetime.utcnow() + timedelta(days=30)
        proposta.status = 'Enviada'
        
        db.session.commit()
        
        flash(f'Proposta enviada! Link do cliente: {request.url_root}cliente/proposta/{token}', 'success')
        return redirect(url_for('main.lista_propostas'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao enviar proposta: {str(e)}', 'danger')
        return redirect(url_for('main.lista_propostas'))

@main_bp.route('/cliente/proposta/<token>')
def cliente_proposta(token):
    """Portal do cliente para visualizar proposta"""
    proposta = PropostaComercial.query.filter_by(token_acesso=token).first_or_404()
    
    # Verificar se a proposta não expirou
    if proposta.data_expiracao and datetime.utcnow() > proposta.data_expiracao:
        proposta.status = 'Expirada'
        db.session.commit()
    
    return render_template('cliente/proposta_detalhes.html', proposta=proposta)

@main_bp.route('/cliente/proposta/<token>/aprovar', methods=['POST'])
def cliente_aprovar_proposta(token):
    """Cliente aprova a proposta"""
    try:
        proposta = PropostaComercial.query.filter_by(token_acesso=token).first_or_404()
        
        if proposta.status != 'Enviada':
            flash('Esta proposta não pode mais ser aprovada.', 'warning')
            return redirect(url_for('main.cliente_proposta', token=token))
        
        proposta.status = 'Aprovada'
        proposta.data_resposta = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get('observacoes')
        proposta.ip_assinatura = request.remote_addr
        proposta.user_agent_assinatura = request.headers.get('User-Agent')
        
        db.session.commit()
        
        flash('Proposta aprovada com sucesso! Entraremos em contato em breve.', 'success')
        return redirect(url_for('main.cliente_proposta', token=token))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar proposta: {str(e)}', 'danger')
        return redirect(url_for('main.cliente_proposta', token=token))

@main_bp.route('/cliente/proposta/<token>/rejeitar', methods=['POST'])
def cliente_rejeitar_proposta(token):
    """Cliente rejeita a proposta"""
    try:
        proposta = PropostaComercial.query.filter_by(token_acesso=token).first_or_404()
        
        if proposta.status != 'Enviada':
            flash('Esta proposta não pode mais ser rejeitada.', 'warning')
            return redirect(url_for('main.cliente_proposta', token=token))
        
        proposta.status = 'Rejeitada'
        proposta.data_resposta = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get('observacoes')
        proposta.ip_assinatura = request.remote_addr
        proposta.user_agent_assinatura = request.headers.get('User-Agent')
        
        db.session.commit()
        
        flash('Resposta registrada. Obrigado pelo seu tempo.', 'info')
        return redirect(url_for('main.cliente_proposta', token=token))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao rejeitar proposta: {str(e)}', 'danger')
        return redirect(url_for('main.cliente_proposta', token=token))

# ============================================================================
# API ENDPOINTS PARA DROPDOWNS INTELIGENTES - RDO OPERACIONAL
# ============================================================================

@main_bp.route('/api/obras/autocomplete')
@login_required
def obras_autocomplete():
    """API para autocomplete de obras"""
    q = request.args.get('q', '')
    obras = Obra.query.filter(
        or_(
            Obra.nome.ilike(f'%{q}%'),
            Obra.codigo.ilike(f'%{q}%'),
            Obra.endereco.ilike(f'%{q}%')
        )
    ).filter(Obra.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': obra.id,
        'nome': obra.nome,
        'codigo': obra.codigo,
        'endereco': obra.endereco,
        'area_total_m2': float(obra.area_total_m2) if obra.area_total_m2 else 0
    } for obra in obras])

# REMOVIDO: Função duplicada, usando api_servicos_autocomplete abaixo

@main_bp.route('/api/servicos/<int:servico_id>/subatividades')
@login_required
def api_subatividades_servico(servico_id):
    """API para buscar subatividades de um serviço com status real baseado em RDOs"""
    subatividades = SubAtividade.query.filter_by(servico_id=servico_id, ativo=True).order_by(SubAtividade.ordem_execucao).all()
    
    result = []
    for sub in subatividades:
        # Calcular status real baseado em RDOs
        # Buscar RDO_Subatividades relacionadas
        try:
            rdo_subatividades = db.session.query(RDO_Subatividade).filter_by(
                subatividade_id=sub.id
            ).all()
            
            # Calcular percentual médio de conclusão
            total_percentual = 0
            count_rdos = len(rdo_subatividades)
            
            if count_rdos > 0:
                for rdo_sub in rdo_subatividades:
                    total_percentual += rdo_sub.percentual_concluido or 0
                percentual_medio = total_percentual / count_rdos
            else:
                percentual_medio = 0
                
        except Exception:
            # Se não existe a tabela RDO_Subatividade, usar 0
            percentual_medio = 0
            count_rdos = 0
        
        # Determinar status baseado no percentual real
        if percentual_medio >= 100:
            status = 'Concluída'
            status_class = 'success'
        elif percentual_medio >= 50:
            status = 'Em andamento'
            status_class = 'warning' 
        elif percentual_medio > 0:
            status = 'Iniciada'
            status_class = 'info'
        else:
            status = 'Pendente'
            status_class = 'secondary'
        
        result.append({
            'id': sub.id,
            'nome': sub.nome,
            'descricao': sub.descricao,
            'ordem_execucao': sub.ordem_execucao,
            'ferramentas_necessarias': sub.ferramentas_necessarias,
            'materiais_principais': sub.materiais_principais,
            'requer_aprovacao': sub.requer_aprovacao,
            'pode_executar_paralelo': sub.pode_executar_paralelo,
            'qualificacao_minima': sub.qualificacao_minima,
            'status': status,
            'status_class': status_class,
            'percentual_concluido': round(percentual_medio, 1),
            'rdos_count': count_rdos
        })
    
    return jsonify({
        'success': True,
        'subatividades': result
    })

@main_bp.route('/api/funcionarios/autocomplete')
@login_required
def funcionarios_autocomplete():
    """API para autocomplete de funcionários"""
    q = request.args.get('q', '')
    funcionarios = Funcionario.query.filter(
        or_(
            Funcionario.nome.ilike(f'%{q}%'),
            Funcionario.codigo.ilike(f'%{q}%')
        )
    ).filter(Funcionario.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': funcionario.id,
        'nome': funcionario.nome,
        'codigo': funcionario.codigo,
        'funcao': funcionario.funcao_ref.nome if funcionario.funcao_ref else 'Sem função',
        'entrada': funcionario.horario_trabalho.entrada.strftime('%H:%M') if funcionario.horario_trabalho else '07:00',
        'saida': funcionario.horario_trabalho.saida.strftime('%H:%M') if funcionario.horario_trabalho else '17:00'
    } for funcionario in funcionarios])

@main_bp.route('/api/equipamentos/autocomplete')
@login_required
def equipamentos_autocomplete():
    """API para autocomplete de equipamentos/veículos"""
    q = request.args.get('q', '')
    veiculos = Veiculo.query.filter(
        or_(
            Veiculo.nome.ilike(f'%{q}%'),
            Veiculo.placa.ilike(f'%{q}%'),
            Veiculo.tipo.ilike(f'%{q}%')
        )
    ).filter(Veiculo.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': veiculo.id,
        'nome': veiculo.nome,
        'placa': veiculo.placa,
        'tipo': veiculo.tipo,
        'status': veiculo.status
    } for veiculo in veiculos])

@main_bp.route('/api/servicos/<int:servico_id>')
@login_required
def servico_detalhes(servico_id):
    """API para obter detalhes de um serviço com subatividades"""
    servico = Servico.query.get_or_404(servico_id)
    subatividades = SubAtividade.query.filter_by(
        servico_id=servico_id, 
        ativo=True
    ).order_by(SubAtividade.ordem_execucao).all()
    
    return jsonify({
        'id': servico.id,
        'nome': servico.nome,
        'unidade_medida': servico.unidade_medida,
        'unidade_simbolo': get_simbolo_unidade(servico.unidade_medida),
        'subatividades': [{
            'id': sub.id,
            'nome': sub.nome,
            'descricao': sub.descricao,
            'ordem_execucao': sub.ordem_execucao
        } for sub in subatividades]
    })

@main_bp.route('/api/rdo/salvar', methods=['POST'])
@login_required
def salvar_rdo():
    """API para salvar RDO como rascunho"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get('data_relatorio') or not dados.get('obra_id'):
            return jsonify({'success': False, 'message': 'Data e obra são obrigatórias'})
        
        # Verificar se já existe RDO para esta data/obra
        rdo_existente = RDO.query.filter_by(
            data_relatorio=datetime.strptime(dados['data_relatorio'], '%Y-%m-%d').date(),
            obra_id=dados['obra_id'],
            funcionario_id=current_user.id
        ).first()
        
        if rdo_existente:
            # Atualizar RDO existente
            rdo = rdo_existente
        else:
            # Criar novo RDO
            rdo = RDO(
                data_relatorio=datetime.strptime(dados['data_relatorio'], '%Y-%m-%d').date(),
                obra_id=dados['obra_id'],
                funcionario_id=current_user.id
            )
        
        # Atualizar dados do RDO
        rdo.tempo_manha = dados.get('tempo_manha', '')
        rdo.tempo_tarde = dados.get('tempo_tarde', '')
        rdo.tempo_noite = dados.get('tempo_noite', '')
        rdo.observacoes_meteorologicas = dados.get('observacoes_meteorologicas', '')
        rdo.comentario_geral = dados.get('comentario_geral', '')
        rdo.status = dados.get('status', 'Rascunho')
        
        db.session.add(rdo)
        db.session.flush()
        
        # Salvar dados das seções (JSON por simplicidade)
        rdo.dados_funcionarios = json.dumps(dados.get('funcionarios', []))
        rdo.dados_atividades = json.dumps(dados.get('atividades', []))
        rdo.dados_equipamentos = json.dumps(dados.get('equipamentos', []))
        rdo.dados_ocorrencias = json.dumps(dados.get('ocorrencias', []))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'RDO salvo com sucesso!',
            'rdo_id': rdo.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao salvar RDO: {str(e)}'})

@main_bp.route('/api/rdo/finalizar', methods=['POST'])
@login_required
def finalizar_rdo():
    """API para finalizar RDO"""
    try:
        dados = request.get_json()
        
        # Primeiro salvar como rascunho
        resultado_salvar = salvar_rdo()
        if not resultado_salvar.get_json()['success']:
            return resultado_salvar
        
        # Buscar RDO salvo
        rdo = RDO.query.filter_by(
            data_relatorio=datetime.strptime(dados['data_relatorio'], '%Y-%m-%d').date(),
            obra_id=dados['obra_id'],
            funcionario_id=current_user.id
        ).first()
        
        if not rdo:
            return jsonify({'success': False, 'message': 'RDO não encontrado'})
        
        # Atualizar status
        rdo.status = 'Finalizado'
        
        # Processar dados de produtividade
        processar_dados_produtividade(rdo.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'RDO finalizado com sucesso!',
            'rdo_id': rdo.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao finalizar RDO: {str(e)}'})

# Função auxiliar para processar dados de produtividade (chamada pelos RDOs)
def processar_dados_produtividade(rdo_id):
    """Processa dados do RDO e gera histórico de produtividade"""
    try:
        rdo = RDO.query.get(rdo_id)
        if not rdo:
            return
        
        # Processar dados de atividades
        if rdo.dados_atividades:
            atividades = json.loads(rdo.dados_atividades)
            
            for atividade in atividades:
                if atividade.get('servico_id') and atividade.get('quantidade'):
                    # Calcular custo baseado nos funcionários que trabalharam
                    custo_total = 0
                    if rdo.dados_funcionarios:
                        funcionarios = json.loads(rdo.dados_funcionarios)
                        for func in funcionarios:
                            if func.get('funcionario_id') and func.get('horas'):
                                funcionario = Funcionario.query.get(func['funcionario_id'])
                                if funcionario:
                                    custo_hora = float(funcionario.salario) / 220  # 220 horas/mês
                                    custo_total += custo_hora * float(func['horas'])
                    
                    # Criar registro de produtividade
                    historico = HistoricoProdutividadeServico(
                        servico_id=atividade['servico_id'],
                        obra_id=rdo.obra_id,
                        funcionario_id=rdo.funcionario_id,
                        data_execucao=rdo.data_relatorio,
                        quantidade_executada=float(atividade['quantidade']),
                        tempo_execucao_horas=float(atividade.get('tempo', 0)),
                        custo_mao_obra_real=custo_total,
                        produtividade_hora=float(atividade['quantidade']) / max(float(atividade.get('tempo', 1)), 1)
                    )
                    
                    db.session.add(historico)
        
        db.session.commit()
        
    except Exception as e:
        print(f"Erro ao processar dados de produtividade: {str(e)}")

def get_simbolo_unidade(unidade_medida):
    """Retorna o símbolo da unidade de medida"""
    simbolos = {
        'm2': 'm²',
        'm3': 'm³',
        'kg': 'kg',
        'ton': 'ton',
        'un': 'un',
        'm': 'm',
        'h': 'h'
    }
    return simbolos.get(unidade_medida, unidade_medida)

# Ponto
@main_bp.route('/ponto')
@login_required
def ponto():
    # Obter funcionários do admin para filtrar registros de ponto
    funcionarios_admin = Funcionario.query.filter_by(admin_id=current_user.id).order_by(Funcionario.nome).all()
    funcionarios_ids = [f.id for f in funcionarios_admin]
    
    if funcionarios_ids:
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(funcionarios_ids)
        ).order_by(RegistroPonto.data.desc()).limit(50).all()
    else:
        registros = []
    
    return render_template('ponto.html', registros=registros)

@main_bp.route('/ponto/novo', methods=['GET', 'POST'])
@login_required
def novo_ponto_lista():
    form = RegistroPontoForm()
    # Filtrar por admin_id para multi-tenant
    form.funcionario_id.choices = [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True, admin_id=current_user.id).order_by(Funcionario.nome).all()]
    form.obra_id.choices = [(0, 'Selecione...')] + [(o.id, o.nome) for o in Obra.query.filter_by(status='Em andamento', admin_id=current_user.id).all()]
    
    if form.validate_on_submit():
        registro = RegistroPonto(
            funcionario_id=form.funcionario_id.data,
            obra_id=form.obra_id.data if form.obra_id.data > 0 else None,
            data=form.data.data,
            hora_entrada=form.hora_entrada.data,
            hora_saida=form.hora_saida.data,
            hora_almoco_saida=form.hora_almoco_saida.data,
            hora_almoco_retorno=form.hora_almoco_retorno.data,
            observacoes=form.observacoes.data
        )
        
        # Calcular horas trabalhadas
        if registro.hora_entrada and registro.hora_saida:
            horas_trabalhadas = calcular_horas_trabalhadas(
                registro.hora_entrada, registro.hora_saida,
                registro.hora_almoco_saida, registro.hora_almoco_retorno,
                registro.data
            )
            registro.horas_trabalhadas = horas_trabalhadas['total']
            registro.horas_extras = horas_trabalhadas['extras']
        
        db.session.add(registro)
        db.session.commit()
        
        # Atualizar cálculos automáticos do registro
        from kpis_engine import atualizar_calculos_ponto
        atualizar_calculos_ponto(registro.id)
        
        flash('Registro de ponto adicionado com sucesso!', 'success')
        return redirect(url_for('main.ponto'))
    
    # Obter funcionários do admin para filtrar registros de ponto
    funcionarios_admin = Funcionario.query.filter_by(admin_id=current_user.id).order_by(Funcionario.nome).all()
    funcionarios_ids = [f.id for f in funcionarios_admin]
    
    if funcionarios_ids:
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(funcionarios_ids)
        ).order_by(RegistroPonto.data.desc()).limit(50).all()
    else:
        registros = []
    
    return render_template('ponto.html', form=form, registros=registros)

# Funções duplicadas removidas

# Função duplicada removida - implementação única mantida nas linhas posteriores

# ===== ROTAS DE RESTAURANTES =====
@main_bp.route('/restaurantes')
@admin_required
def lista_restaurantes():
    """Lista restaurantes - VERSÃO SIMPLES E FUNCIONAL"""
    try:
        # Determinar admin_id
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Query direta
        restaurantes = Restaurante.query.filter_by(admin_id=admin_id).all()
        
        return render_template('restaurantes.html', restaurantes=restaurantes)
        
    except Exception as e:
        return render_template('error_debug.html',
                             error_title="Erro no Módulo de Restaurantes",
                             error_message=f"ERRO: {str(e)}",
                             solution="Verificar schema da tabela restaurante")

@main_bp.route('/restaurantes/novo', methods=['GET', 'POST'])
@admin_required
def novo_restaurante():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', '').strip()
            endereco = request.form.get('endereco', '').strip()
            telefone = request.form.get('telefone', '').strip()
            responsavel = request.form.get('responsavel', '').strip()
            preco_almoco = float(request.form.get('preco_almoco', 0))
            preco_jantar = float(request.form.get('preco_jantar', 0))
            preco_lanche = float(request.form.get('preco_lanche', 0))
            
            if not nome:
                flash('Nome é obrigatório.', 'danger')
                return redirect(url_for('main.novo_restaurante'))
            
            # Verificar duplicatas
            admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
            existing = Restaurante.query.filter_by(nome=nome, admin_id=admin_id).first()
            
            if existing:
                flash(f'Já existe um restaurante com o nome "{nome}".', 'danger')
                return redirect(url_for('main.novo_restaurante'))
            
            restaurante = Restaurante(
                nome=nome,
                endereco=endereco,
                telefone=telefone,
                responsavel=responsavel,
                preco_almoco=preco_almoco,
                preco_jantar=preco_jantar,
                preco_lanche=preco_lanche,
                admin_id=current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
            )
            
            db.session.add(restaurante)
            db.session.commit()
            
            flash(f'Restaurante "{nome}" criado com sucesso!', 'success')
            return redirect(url_for('main.lista_restaurantes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar restaurante: {str(e)}', 'danger')
            return redirect(url_for('main.novo_restaurante'))
    
    return render_template('restaurante_form.html', 
                         titulo="Novo Restaurante",
                         acao="Criar")

@main_bp.route('/restaurantes/<int:id>')
@admin_required
def detalhes_restaurante(id):
    # Filtro multi-tenant
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
    restaurante = Restaurante.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Buscar estatísticas do restaurante
    from datetime import datetime, timedelta
    hoje = datetime.now().date()
    inicio_mes = hoje.replace(day=1)
    
    # Total de registros de alimentação no mês
    registros_mes = RegistroAlimentacao.query.filter(
        and_(
            RegistroAlimentacao.restaurante_id == id,
            RegistroAlimentacao.data >= inicio_mes,
            RegistroAlimentacao.data <= hoje
        )
    ).count()
    
    # Valor total no mês
    valor_total_mes = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        and_(
            RegistroAlimentacao.restaurante_id == id,
            RegistroAlimentacao.data >= inicio_mes,
            RegistroAlimentacao.data <= hoje
        )
    ).scalar() or 0
    
    # Últimos registros
    ultimos_registros = db.session.query(
        RegistroAlimentacao.data,
        RegistroAlimentacao.tipo,
        RegistroAlimentacao.valor,
        Funcionario.nome.label('funcionario_nome')
    ).join(
        Funcionario, RegistroAlimentacao.funcionario_id == Funcionario.id
    ).filter(
        RegistroAlimentacao.restaurante_id == id
    ).order_by(
        RegistroAlimentacao.data.desc(),
        RegistroAlimentacao.id.desc()
    ).limit(10).all()
    
    return render_template('restaurante_detalhes.html',
                         restaurante=restaurante,
                         registros_mes=registros_mes,
                         valor_total_mes=valor_total_mes,
                         ultimos_registros=ultimos_registros,
                         titulo=f"Restaurante: {restaurante.nome}")

@main_bp.route('/restaurantes/<int:id>/editar', methods=['GET', 'POST'])
@admin_required  
def editar_restaurante(id):
    # Filtro multi-tenant
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
    restaurante = Restaurante.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', '').strip()
            endereco = request.form.get('endereco', '').strip()
            telefone = request.form.get('telefone', '').strip()
            responsavel = request.form.get('responsavel', '').strip()
            preco_almoco = float(request.form.get('preco_almoco', 0))
            preco_jantar = float(request.form.get('preco_jantar', 0))
            preco_lanche = float(request.form.get('preco_lanche', 0))
            ativo = request.form.get('ativo') == 'on'
            
            if not nome:
                flash('Nome é obrigatório.', 'danger')
                return redirect(url_for('main.editar_restaurante', id=id))
            
            # Verificar duplicatas (exceto o próprio)
            admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
            existing = Restaurante.query.filter(
                Restaurante.nome == nome,
                Restaurante.id != id,
                Restaurante.admin_id == admin_id
            ).first()
            
            if existing:
                flash(f'Já existe outro restaurante com o nome "{nome}".', 'danger')
                return redirect(url_for('main.editar_restaurante', id=id))
            
            # Atualizar dados
            restaurante.nome = nome
            restaurante.endereco = endereco
            restaurante.telefone = telefone
            restaurante.responsavel = responsavel  
            restaurante.preco_almoco = preco_almoco
            restaurante.preco_jantar = preco_jantar
            restaurante.preco_lanche = preco_lanche
            restaurante.ativo = ativo
            
            db.session.commit()
            
            flash(f'Restaurante "{nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('main.detalhes_restaurante', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar restaurante: {str(e)}', 'danger')
            return redirect(url_for('main.editar_restaurante', id=id))
    
    return render_template('restaurante_form.html',
                         restaurante=restaurante,
                         titulo="Editar Restaurante",
                         acao="Atualizar")

@main_bp.route('/restaurantes/<int:id>/excluir', methods=['POST'])
@admin_required
def excluir_restaurante(id):
    # Filtro multi-tenant
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
    restaurante = Restaurante.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    try:
        # Verificar se tem registros de alimentação associados
        registros_count = RegistroAlimentacao.query.filter_by(restaurante_id=id).count()
        
        if registros_count > 0:
            # Só desativar se tem registros
            restaurante.ativo = False
            db.session.commit()
            flash(f'Restaurante "{restaurante.nome}" foi desativado (possui {registros_count} registros de alimentação).', 'warning')
        else:
            # Excluir completamente se não tem registros
            nome = restaurante.nome
            db.session.delete(restaurante)
            db.session.commit()
            flash(f'Restaurante "{nome}" excluído com sucesso!', 'success')
        
        return redirect(url_for('main.lista_restaurantes'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir restaurante: {str(e)}', 'danger')
        return redirect(url_for('main.detalhes_restaurante', id=id))

# ===== ROTAS DE ALIMENTAÇÃO =====
@main_bp.route('/alimentacao')
@login_required
def alimentacao():
    """Registros de alimentação com tratamento de erro detalhado"""
    try:
        from datetime import date
        from sqlalchemy import inspect
        
        # Verificar se tabelas necessárias existem
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        missing_tables = []
        required_tables = ['registro_alimentacao', 'restaurante', 'funcionario', 'obra']
        
        for table in required_tables:
            if table not in tables:
                missing_tables.append(table)
        
        if missing_tables:
            error_msg = f"❌ ERRO CRÍTICO: Tabelas faltantes: {', '.join(missing_tables)}"
            solution = f"Execute migração completa: flask db upgrade"
            return render_template('error_debug.html',
                                 error_title="Erro de Schema - Tabelas Faltantes",
                                 error_message=error_msg,
                                 solution=solution,
                                 all_columns=tables,
                                 required_columns=required_tables)
        
        # Verificar schema da tabela restaurante especificamente
        if 'restaurante' in tables:
            rest_columns = inspector.get_columns('restaurante')
            rest_column_names = [col['name'] for col in rest_columns]
            
            # Verificar coluna duplicada problemática
            if 'contato_responsavel' in rest_column_names and 'responsavel' in rest_column_names:
                error_msg = "❌ ERRO DE SCHEMA: Tabela restaurante tem coluna 'contato_responsavel' duplicada"
                solution = "Execute: ALTER TABLE restaurante DROP COLUMN contato_responsavel;"
                return render_template('error_debug.html',
                                     error_title="Erro no Módulo Alimentação - Schema Restaurante",
                                     error_message=error_msg,
                                     solution=solution,
                                     all_columns=rest_column_names)
        
        # Obter funcionários do admin atual
        funcionarios_admin = Funcionario.query.filter_by(ativo=True, admin_id=current_user.id).order_by(Funcionario.nome).all()
        funcionarios_ids = [f.id for f in funcionarios_admin]
        
        # Filtrar registros pelos funcionários do admin + filtros da URL
        if funcionarios_ids:
            query = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.funcionario_id.in_(funcionarios_ids)
            )
            
            # Aplicar filtros da URL
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            funcionario_id = request.args.get('funcionario_id')
            
            if data_inicio:
                from datetime import datetime
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                query = query.filter(RegistroAlimentacao.data >= data_inicio_obj)
                
            if data_fim:
                from datetime import datetime
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                query = query.filter(RegistroAlimentacao.data <= data_fim_obj)
                
            if funcionario_id:
                query = query.filter(RegistroAlimentacao.funcionario_id == int(funcionario_id))
            
            registros = query.order_by(RegistroAlimentacao.data.desc()).limit(100).all()
        else:
            registros = []
        
        funcionarios = funcionarios_admin
        obras = Obra.query.filter_by(status='Em andamento', admin_id=current_user.id).order_by(Obra.nome).all()
        
        # Tentar buscar restaurantes com filtro por admin
        try:
            restaurantes = Restaurante.query.filter_by(ativo=True, admin_id=current_user.id).order_by(Restaurante.nome).all()
        except Exception as rest_error:
            # Se falhar na query de restaurantes, mostrar erro específico
            error_msg = f"❌ ERRO NA QUERY DE RESTAURANTES: {str(rest_error)}"
            solution = "Verifique o schema da tabela restaurante e execute fix_restaurante_schema_production.py"
            return render_template('error_debug.html',
                                 error_title="Erro na Query de Restaurantes",
                                 error_message=error_msg,
                                 solution=solution,
                                 error_details=str(rest_error))
    
    except Exception as e:
        # Capturar qualquer outro erro e mostrar detalhes
        import traceback
        error_details = traceback.format_exc()
        
        return render_template('error_debug.html',
                             error_title="Erro no Módulo de Alimentação",
                             error_message=f"❌ ERRO: {str(e)}",
                             error_details=error_details,
                             solution="Verifique o schema das tabelas e aplique as correções necessárias")
    
    return render_template('alimentacao.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         obras=obras,
                         restaurantes=restaurantes,
                         date=date)

@main_bp.route('/alimentacao/novo', methods=['POST'])
@login_required
def nova_alimentacao():
    """Criar registros de alimentação para múltiplos funcionários (data única ou período)"""
    try:
        # Detectar se é lançamento por período
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        data_unica = request.form.get('data')
        
        # Determinar datas para processar
        datas_processamento = []
        
        if data_inicio and data_fim:
            # Lançamento por período
            inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            
            # Gerar lista de datas do período
            data_atual = inicio
            while data_atual <= fim:
                datas_processamento.append(data_atual)
                data_atual += timedelta(days=1)
        elif data_unica:
            # Lançamento de data única - ADICIONAR DEBUG
            print(f"   📅 LANÇAMENTO INDIVIDUAL - data_unica: '{data_unica}'")
            data_convertida = datetime.strptime(data_unica, '%Y-%m-%d').date()
            print(f"   📅 Data convertida: {data_convertida} (mês {data_convertida.month})")
            
            # VERIFICAR SE ESTÁ SENDO ALTERADA PARA O MÊS ATUAL
            if data_convertida.month == 8:  # Agosto (mês atual)
                print(f"   🚨 PROBLEMA DETECTADO: Data convertida está em agosto!")
                print(f"   Original string: '{data_unica}'")
                print(f"   Resultado conversão: {data_convertida}")
            
            datas_processamento.append(data_convertida)
        else:
            return jsonify({'success': False, 'message': 'Data é obrigatória'}), 400
        
        # DEBUG CRÍTICO: Log completo dos dados
        print(f"🔍 DEBUG CRÍTICO - Dados do formulário:")
        print(f"   data_inicio: '{data_inicio}' (tipo: {type(data_inicio)})")
        print(f"   data_fim: '{data_fim}' (tipo: {type(data_fim)})")
        print(f"   data_unica: '{data_unica}' (tipo: {type(data_unica)})")
        
        # Log de todos os campos do formulário para debug
        print(f"   Todos os campos form: {dict(request.form)}")
        
        if data_inicio and data_fim:
            print(f"   🔄 Convertendo datas do período...")
            print(f"   inicio str: '{data_inicio}' → convertido: {inicio} (mês {inicio.month})")
            print(f"   fim str: '{data_fim}' → convertido: {fim} (mês {fim.month})")
            
            # Verificar se as datas estão no mês correto
            if inicio.month != 7 or fim.month != 7:
                print(f"   ⚠️ ALERTA: Datas não estão em julho!")
                print(f"   início mês: {inicio.month}, fim mês: {fim.month}")
                
        elif data_unica:
            data_convertida = datetime.strptime(data_unica, '%Y-%m-%d').date()
            print(f"   Data única: '{data_unica}' → convertida: {data_convertida} (mês {data_convertida.month})")
            if data_convertida.month != 7:
                print(f"   ⚠️ ALERTA: Data única não está em julho! Mês: {data_convertida.month}")
        
        print(f"   📅 Datas para processamento: {datas_processamento}")
        
        # Verificar cada data individualmente
        for i, data in enumerate(datas_processamento):
            if data.month != 7:
                print(f"   ❌ ERRO: Data {i+1}: {data} está no mês {data.month}, não julho!")
        
        # Dados básicos do formulário
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        obra_id = request.form.get('obra_id')
        restaurante_id = request.form.get('restaurante_id')
        observacoes = request.form.get('observacoes')
        
        # Validar campos obrigatórios
        if not obra_id:
            return jsonify({'success': False, 'message': 'Obra é obrigatória para controle de custos e KPIs'}), 400
        if not restaurante_id:
            return jsonify({'success': False, 'message': 'Restaurante é obrigatório para identificação do fornecedor'}), 400
        
        # Lista de funcionários selecionados (checkboxes no modal)
        funcionarios_ids = request.form.getlist('funcionarios_ids[]')
        
        # DEBUG: Verificar se os funcionários estão chegando
        if not funcionarios_ids:
            # Tentar outras formas de pegar os funcionários
            funcionarios_ids = request.form.getlist('funcionarios_ids')
            if not funcionarios_ids:
                funcionarios_ids = request.form.getlist('funcionario_id')
                if not funcionarios_ids:
                    # Lista todos os campos do form para debug
                    form_fields = list(request.form.keys())
                    return jsonify({
                        'success': False, 
                        'message': f'Nenhum funcionário selecionado. Campos recebidos: {form_fields}'
                    }), 400
        
        registros_criados = []
        total_dias = len(datas_processamento)
        
        # Criar registros para cada funcionário em cada data
        for data in datas_processamento:
            for funcionario_id in funcionarios_ids:
                funcionario = Funcionario.query.get(funcionario_id)
                if not funcionario:
                    continue
                
                # Verificar se já existe registro para este funcionário nesta data e tipo
                registro_existente = RegistroAlimentacao.query.filter_by(
                    funcionario_id=int(funcionario_id),
                    data=data,
                    tipo=tipo
                ).first()
                
                if registro_existente:
                    continue  # Pular se já existe
                    
                # DEBUG: Log antes de criar registro
                print(f"   🔨 Criando registro para {funcionario.nome}:")
                print(f"      Data sendo salva: {data} (mês {data.month})")
                print(f"      Tipo: {tipo}, Valor: R$ {valor}")
                
                registro = RegistroAlimentacao(
                    funcionario_id=int(funcionario_id),
                    obra_id=int(obra_id),
                    restaurante_id=int(restaurante_id),
                    data=data,
                    tipo=tipo,
                    valor=valor,
                    observacoes=observacoes
                )
                
                # DEBUG: Verificar se a data do objeto está correta
                print(f"      Objeto registro.data: {registro.data} (mês {registro.data.month})")
                
                db.session.add(registro)
                registros_criados.append(f"{funcionario.nome} - {tipo} - {data.strftime('%d/%m/%Y')}")
                
                # Adicionar custo à obra (sempre, pois é obrigatório)
                custo = CustoObra(
                    obra_id=int(obra_id),
                    tipo='alimentacao',
                    descricao=f'Alimentação - {tipo} - {funcionario.nome} - {data.strftime("%d/%m/%Y")}',
                    valor=valor,
                    data=data
                )
                db.session.add(custo)
        
        db.session.commit()
        
        total_registros = len(registros_criados)
        valor_total = total_registros * valor
        
        if total_dias > 1:
            message = f'{total_registros} registros criados para {total_dias} dias! Valor total: R$ {valor_total:.2f}'
        else:
            message = f'{total_registros} registros criados com sucesso! Valor total: R$ {valor_total:.2f}'
        
        return jsonify({
            'success': True, 
            'message': message,
            'registros': registros_criados[:10],  # Limitar para não sobrecarregar
            'total_dias': total_dias,
            'total_registros': total_registros
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar registros: {str(e)}'}), 500

@main_bp.route('/alimentacao/excluir_massa', methods=['POST'])
@login_required
def excluir_alimentacao_massa():
    """Excluir registros de alimentação em massa (para corrigir registros com data incorreta)"""
    try:
        data_inicio = request.form.get('data_inicio_exclusao')
        data_fim = request.form.get('data_fim_exclusao')
        
        if not data_inicio or not data_fim:
            return jsonify({'success': False, 'message': 'Datas são obrigatórias'}), 400
        
        # Converter datas
        inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Buscar registros no período especificado
        registros = RegistroAlimentacao.query.filter(
            and_(
                RegistroAlimentacao.data >= inicio,
                RegistroAlimentacao.data <= fim
            )
        ).all()
        
        if not registros:
            return jsonify({'success': False, 'message': 'Nenhum registro encontrado no período'}), 400
        
        # Filtrar apenas registros do admin atual
        registros_admin = []
        for registro in registros:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            if funcionario and funcionario.admin_id == current_user.id:
                registros_admin.append(registro)
        
        if not registros_admin:
            return jsonify({'success': False, 'message': 'Nenhum registro encontrado para sua empresa'}), 400
        
        # Log para auditoria
        print(f"🗑️ EXCLUSÃO EM MASSA: {len(registros_admin)} registros de {inicio} a {fim}")
        print(f"   Usuário: {current_user.username}")
        
        # Excluir registros
        count = len(registros_admin)
        for registro in registros_admin:
            # Remover custos relacionados também
            custos_relacionados = CustoObra.query.filter(
                and_(
                    CustoObra.tipo == 'alimentacao',
                    CustoObra.data == registro.data,
                    CustoObra.descricao.contains(registro.funcionario_ref.nome)
                )
            ).all()
            
            for custo in custos_relacionados:
                db.session.delete(custo)
            
            db.session.delete(registro)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{count} registros excluídos com sucesso',
            'count': count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro na exclusão em massa: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

@main_bp.route('/alimentacao/<int:id>/editar', methods=['POST'])
@login_required
def editar_alimentacao(id):
    """Editar registro de alimentação via AJAX (inline)"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(id)
        
        # Verificar se o funcionário pertence ao admin atual
        if registro.funcionario_ref.admin_id != current_user.id:
            return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
        
        # Dados do FormData
        data_str = request.form.get('data')
        tipo = request.form.get('tipo')
        valor_str = request.form.get('valor')
        observacoes = request.form.get('observacoes')
        
        # Validações e conversões
        if data_str:
            registro.data = datetime.strptime(data_str, '%Y-%m-%d').date()
            
        if tipo:
            registro.tipo = tipo
            
        if valor_str:
            registro.valor = float(valor_str)
            
        if observacoes is not None:  # Permitir string vazia
            registro.observacoes = observacoes.strip() if observacoes.strip() else None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Registro atualizado com sucesso!'
        })
        
    except ValueError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Dados inválidos: {str(e)}'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        }), 500

@main_bp.route('/alimentacao/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_alimentacao(id):
    """Excluir registro de alimentação com validações aprimoradas"""
    try:
        # Log para debug
        print(f"🗑️ EXCLUSÃO SOLICITADA: ID {id}")
        
        registro = RegistroAlimentacao.query.get_or_404(id)
        
        # Verificar se o funcionário pertence ao admin atual
        if registro.funcionario_ref.admin_id != current_user.id:
            print(f"❌ ACESSO NEGADO: Admin {current_user.id} tentou excluir registro do admin {registro.funcionario_ref.admin_id}")
            return jsonify({'success': False, 'message': 'Acesso negado. Registro não pertence ao seu escopo.'}), 403
        
        # Dados para log antes da exclusão
        funcionario_nome = registro.funcionario_ref.nome
        tipo = registro.tipo
        data = registro.data
        valor = registro.valor
        obra_nome = registro.obra_ref.nome if registro.obra_ref else 'N/A'
        
        print(f"🗑️ EXCLUINDO: {funcionario_nome} - {data} - {tipo} - R$ {valor} - Obra: {obra_nome}")
        
        # Remover custo associado na obra (se existir) - busca mais flexível
        custos_obra = CustoObra.query.filter(
            CustoObra.obra_id == registro.obra_id,
            CustoObra.tipo == 'alimentacao',
            CustoObra.data == registro.data,
            CustoObra.valor == registro.valor
        ).all()
        
        # Filtrar por nome do funcionário na descrição
        custos_relacionados = [
            custo for custo in custos_obra 
            if custo.descricao and funcionario_nome.lower() in custo.descricao.lower()
        ]
        
        if custos_relacionados:
            print(f"🗑️ Removendo {len(custos_relacionados)} custo(s) associado(s) na obra")
            for custo in custos_relacionados:
                db.session.delete(custo)
        else:
            print(f"ℹ️ Nenhum custo associado encontrado na obra")
        
        # Excluir registro principal
        db.session.delete(registro)
        db.session.commit()
        
        print(f"✅ EXCLUSÃO CONCLUÍDA: {funcionario_nome} - {tipo}")
        
        return jsonify({
            'success': True, 
            'message': f'Registro de {tipo} de {funcionario_nome} ({data.strftime("%d/%m/%Y")}) excluído com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ ERRO NA EXCLUSÃO: {error_details}")
        
        return jsonify({
            'success': False, 
            'message': f'Erro interno ao excluir registro: {str(e)}'
        }), 500

# ================================
# CRUD COMPLETO DE CUSTOS DE VEÍCULOS
# ================================

@main_bp.route('/veiculos/<int:id>/custos')
@login_required
def lista_custos_veiculo(id):
    """Listar todos os custos de um veículo"""
    veiculo = Veiculo.query.get_or_404(id)
    
    # Verificar acesso multi-tenant
    if veiculo.admin_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.veiculos'))
    
    # Filtros da URL
    page = request.args.get('page', 1, type=int)
    tipo_filtro = request.args.get('tipo', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = CustoVeiculo.query.filter_by(veiculo_id=id)
    
    # Aplicar filtros
    if tipo_filtro:
        query = query.filter(CustoVeiculo.tipo_custo == tipo_filtro)
    if data_inicio:
        query = query.filter(CustoVeiculo.data_custo >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(CustoVeiculo.data_custo <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    # Paginar resultados
    custos = query.order_by(CustoVeiculo.data_custo.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Estatísticas
    total_gasto = db.session.query(db.func.sum(CustoVeiculo.valor)).filter_by(veiculo_id=id).scalar() or 0
    custo_mes = db.session.query(db.func.sum(CustoVeiculo.valor)).filter(
        CustoVeiculo.veiculo_id == id,
        CustoVeiculo.data_custo >= date.today().replace(day=1)
    ).scalar() or 0
    
    return render_template('veiculos/lista_custos.html',
                         veiculo=veiculo,
                         custos=custos,
                         total_gasto=total_gasto,
                         custo_mes=custo_mes,
                         filtros={
                             'tipo': tipo_filtro,
                             'data_inicio': data_inicio,
                             'data_fim': data_fim
                         })

@main_bp.route('/veiculos/<int:id>/custos/novo', methods=['GET', 'POST'])
@login_required
def novo_custo_veiculo(id):
    """Criar novo custo para veículo"""
    veiculo = Veiculo.query.get_or_404(id)
    
    # Verificar acesso multi-tenant
    if veiculo.admin_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.veiculos'))
    
    if request.method == 'POST':
        try:
            # Capturar dados do formulário
            data_custo = datetime.strptime(request.form['data_custo'], '%Y-%m-%d').date()
            obra_id = int(request.form['obra_id'])
            valor = float(request.form['valor'])
            tipo_custo = request.form['tipo_custo']
            descricao = request.form.get('descricao', '').strip()
            km_atual = request.form.get('km_atual')
            fornecedor = request.form.get('fornecedor', '').strip()
            
            # Validações
            if valor <= 0:
                flash('O valor deve ser maior que zero.', 'error')
                raise ValueError('Valor inválido')
                
            # Verificar se a obra pertence ao admin atual
            obra = Obra.query.get_or_404(obra_id)
            if obra.admin_id != current_user.id:
                flash('Obra não encontrada ou acesso negado.', 'error')
                raise ValueError('Obra inválida')
            
            # Criar novo custo
            custo = CustoVeiculo(
                veiculo_id=id,
                obra_id=obra_id,
                data_custo=data_custo,
                valor=valor,
                tipo_custo=tipo_custo,
                descricao=descricao if descricao else None,
                km_atual=int(km_atual) if km_atual else None,
                fornecedor=fornecedor if fornecedor else None
            )
            
            db.session.add(custo)
            
            # Atualizar KM do veículo se fornecido
            if km_atual and int(km_atual) > (veiculo.km_atual or 0):
                veiculo.km_atual = int(km_atual)
            
            # Registrar custo na obra
            custo_obra = CustoObra(
                obra_id=obra_id,
                tipo='veiculo',
                descricao=f"Veículo {veiculo.placa} - {tipo_custo.title()}: {descricao or 'Sem descrição'}",
                valor=valor,
                data=data_custo
            )
            db.session.add(custo_obra)
            
            db.session.commit()
            
            flash(f'Custo de {tipo_custo} registrado com sucesso!', 'success')
            return redirect(url_for('main.lista_custos_veiculo', id=id))
            
        except ValueError:
            # Erro já tratado com flash
            pass
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar custo: {str(e)}', 'error')
    
    # GET: mostrar formulário
    obras = Obra.query.filter_by(admin_id=current_user.id, ativo=True).all()
    return render_template('veiculos/novo_custo.html',
                         veiculo=veiculo,
                         obras=obras,
                         today=date.today().strftime('%Y-%m-%d'),
                         form_data=request.form)

@main_bp.route('/api/custos-veiculo/<int:id>', methods=['GET'])
@login_required
def api_obter_custo_veiculo(id):
    """API para obter dados de um custo para edição"""
    try:
        custo = CustoVeiculo.query.get_or_404(id)
        
        # Verificar acesso multi-tenant
        if custo.veiculo.admin_id != current_user.id:
            return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
        
        return jsonify({
            'success': True,
            'dados': {
                'id': custo.id,
                'data_custo': custo.data_custo.strftime('%Y-%m-%d'),
                'obra_id': custo.obra_id,
                'valor': custo.valor,
                'tipo_custo': custo.tipo_custo,
                'descricao': custo.descricao or '',
                'km_atual': custo.km_atual,
                'fornecedor': custo.fornecedor or '',
                'veiculo_placa': custo.veiculo.placa,
                'obra_nome': custo.obra.nome
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

@main_bp.route('/api/custos-veiculo/<int:id>', methods=['PUT'])
@login_required
def api_editar_custo_veiculo(id):
    """API para editar custo de veículo"""
    try:
        custo = CustoVeiculo.query.get_or_404(id)
        
        # Verificar acesso multi-tenant
        if custo.veiculo.admin_id != current_user.id:
            return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
        
        dados = request.get_json()
        
        # Validações
        if not dados.get('data_custo') or not dados.get('obra_id') or not dados.get('valor') or not dados.get('tipo_custo'):
            return jsonify({'success': False, 'message': 'Campos obrigatórios não preenchidos.'}), 400
        
        valor = float(dados['valor'])
        if valor <= 0:
            return jsonify({'success': False, 'message': 'O valor deve ser maior que zero.'}), 400
        
        # Verificar obra
        obra = Obra.query.get(dados['obra_id'])
        if not obra or obra.admin_id != current_user.id:
            return jsonify({'success': False, 'message': 'Obra inválida.'}), 400
        
        # Salvar valores antigos para atualizar CustoObra relacionado
        valor_antigo = custo.valor
        data_antiga = custo.data_custo
        obra_antiga_id = custo.obra_id
        
        # Atualizar custo
        custo.data_custo = datetime.strptime(dados['data_custo'], '%Y-%m-%d').date()
        custo.obra_id = dados['obra_id']
        custo.valor = valor
        custo.tipo_custo = dados['tipo_custo']
        custo.descricao = dados.get('descricao', '').strip() or None
        custo.km_atual = int(dados['km_atual']) if dados.get('km_atual') else None
        custo.fornecedor = dados.get('fornecedor', '').strip() or None
        
        # Atualizar KM do veículo se fornecido e maior
        if custo.km_atual and custo.km_atual > (custo.veiculo.km_atual or 0):
            custo.veiculo.km_atual = custo.km_atual
        
        # Atualizar CustoObra relacionado
        custo_obra = CustoObra.query.filter(
            CustoObra.obra_id == obra_antiga_id,
            CustoObra.tipo == 'veiculo',
            CustoObra.valor == valor_antigo,
            CustoObra.data == data_antiga,
            CustoObra.descricao.contains(custo.veiculo.placa)
        ).first()
        
        if custo_obra:
            custo_obra.obra_id = custo.obra_id
            custo_obra.valor = custo.valor
            custo_obra.data = custo.data_custo
            custo_obra.descricao = f"Veículo {custo.veiculo.placa} - {custo.tipo_custo.title()}: {custo.descricao or 'Sem descrição'}"
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Custo atualizado com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

@main_bp.route('/api/custos-veiculo/<int:id>', methods=['DELETE'])
@login_required
def api_excluir_custo_veiculo(id):
    """API para excluir custo de veículo"""
    try:
        custo = CustoVeiculo.query.get_or_404(id)
        
        # Verificar acesso multi-tenant
        if custo.veiculo.admin_id != current_user.id:
            return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
        
        # Dados para log
        veiculo_placa = custo.veiculo.placa
        tipo_custo = custo.tipo_custo
        valor = custo.valor
        data = custo.data_custo
        
        # Remover CustoObra relacionado
        custo_obra = CustoObra.query.filter(
            CustoObra.obra_id == custo.obra_id,
            CustoObra.tipo == 'veiculo',
            CustoObra.valor == custo.valor,
            CustoObra.data == custo.data_custo,
            CustoObra.descricao.contains(custo.veiculo.placa)
        ).first()
        
        if custo_obra:
            db.session.delete(custo_obra)
        
        # Excluir custo
        db.session.delete(custo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Custo de {tipo_custo} do veículo {veiculo_placa} (R$ {valor:.2f}) excluído com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

@main_bp.route('/api/obras-disponiveis')
@login_required
def api_obras_disponiveis():
    """API para obter obras do admin atual (para dropdowns)"""
    try:
        obras = Obra.query.filter_by(admin_id=current_user.id, ativo=True).all()
        
        return jsonify({
            'success': True,
            'obras': [{
                'id': obra.id,
                'nome': obra.nome
            } for obra in obras]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

# Relatórios
@main_bp.route('/relatorios')
@login_required
def relatorios():
    # Buscar dados para filtros
    obras = Obra.query.all()
    departamentos = Departamento.query.all()
    
    return render_template('relatorios.html', obras=obras, departamentos=departamentos)

@main_bp.route('/relatorios/dados-graficos', methods=['POST'])
@login_required
def dados_graficos():
    from datetime import datetime, timedelta
    import json
    from sqlalchemy import func, extract
    
    filtros = request.get_json()
    
    # Processar filtros de data
    data_inicio = datetime.strptime(filtros.get('dataInicio', ''), '%Y-%m-%d').date() if filtros.get('dataInicio') else None
    data_fim = datetime.strptime(filtros.get('dataFim', ''), '%Y-%m-%d').date() if filtros.get('dataFim') else None
    obra_id = filtros.get('obra') if filtros.get('obra') else None
    departamento_id = filtros.get('departamento') if filtros.get('departamento') else None
    
    # Data padrão (últimos 6 meses)
    if not data_inicio or not data_fim:
        hoje = date.today()
        data_fim = hoje
        data_inicio = date(hoje.year, hoje.month - 5 if hoje.month > 5 else hoje.month + 7, 1)
        if hoje.month <= 5:
            data_inicio = data_inicio.replace(year=hoje.year - 1)
    
    # 1. Evolução de Custos
    custos_query = db.session.query(
        extract('month', CustoObra.data).label('mes'),
        extract('year', CustoObra.data).label('ano'),
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter(
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    )
    
    if obra_id:
        custos_query = custos_query.filter(CustoObra.obra_id == obra_id)
    
    custos_dados = custos_query.group_by(
        extract('year', CustoObra.data),
        extract('month', CustoObra.data),
        CustoObra.tipo
    ).all()
    
    # Processar dados de custos
    meses_labels = []
    mao_obra_dados = []
    alimentacao_dados = []
    veiculos_dados = []
    
    # Gerar lista de meses
    current_date = data_inicio.replace(day=1)
    while current_date <= data_fim:
        mes_nome = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][current_date.month - 1]
        meses_labels.append(f"{mes_nome}/{current_date.year}")
        
        # Buscar dados do mês
        mao_obra_mes = sum(d.total for d in custos_dados if d.mes == current_date.month and d.ano == current_date.year and d.tipo == 'mao_obra')
        alimentacao_mes = sum(d.total for d in custos_dados if d.mes == current_date.month and d.ano == current_date.year and d.tipo == 'alimentacao')
        veiculos_mes = sum(d.total for d in custos_dados if d.mes == current_date.month and d.ano == current_date.year and d.tipo == 'veiculo')
        
        mao_obra_dados.append(float(mao_obra_mes))
        alimentacao_dados.append(float(alimentacao_mes))
        veiculos_dados.append(float(veiculos_mes))
        
        # Próximo mês
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    # 2. Produtividade por Departamento
    produtividade_query = db.session.query(
        Departamento.nome,
        func.avg(RegistroPonto.horas_trabalhadas).label('media_horas')
    ).join(
        Funcionario, Departamento.id == Funcionario.departamento_id
    ).join(
        RegistroPonto, Funcionario.id == RegistroPonto.funcionario_id
    ).filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    )
    
    if departamento_id:
        produtividade_query = produtividade_query.filter(Departamento.id == departamento_id)
    
    produtividade_dados = produtividade_query.group_by(Departamento.nome).all()
    
    # 3. Distribuição de Custos
    distribuicao_dados = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter(
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    )
    
    if obra_id:
        distribuicao_dados = distribuicao_dados.filter(CustoObra.obra_id == obra_id)
    
    distribuicao_dados = distribuicao_dados.group_by(CustoObra.tipo).all()
    
    # 4. Horas Trabalhadas vs Extras
    horas_query = db.session.query(
        extract('month', RegistroPonto.data).label('mes'),
        extract('year', RegistroPonto.data).label('ano'),
        func.sum(RegistroPonto.horas_trabalhadas).label('horas_normais'),
        func.sum(RegistroPonto.horas_extras).label('horas_extras')
    ).filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    )
    
    if departamento_id:
        horas_query = horas_query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
    
    horas_dados = horas_query.group_by(
        extract('year', RegistroPonto.data),
        extract('month', RegistroPonto.data)
    ).all()
    
    # Processar dados de horas
    horas_normais_dados = []
    horas_extras_dados = []
    
    current_date = data_inicio.replace(day=1)
    while current_date <= data_fim:
        horas_mes = next((h for h in horas_dados if h.mes == current_date.month and h.ano == current_date.year), None)
        
        horas_normais_dados.append(float(horas_mes.horas_normais or 0) if horas_mes else 0)
        horas_extras_dados.append(float(horas_mes.horas_extras or 0) if horas_mes else 0)
        
        # Próximo mês
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    return jsonify({
        'evolucao': {
            'labels': meses_labels,
            'mao_obra': mao_obra_dados,
            'alimentacao': alimentacao_dados,
            'veiculos': veiculos_dados
        },
        'produtividade': {
            'labels': [p.nome for p in produtividade_dados],
            'valores': [float(p.media_horas or 0) for p in produtividade_dados]
        },
        'distribuicao': {
            'valores': [float(d.total) for d in distribuicao_dados]
        },
        'horas': {
            'labels': meses_labels,
            'normais': horas_normais_dados,
            'extras': horas_extras_dados
        }
    })

@main_bp.route('/relatorios/gerar/<tipo>', methods=['GET', 'POST'])
@login_required
def gerar_relatorio(tipo):
    # Processar filtros de GET ou POST
    if request.method == 'POST':
        filtros = request.get_json() or {}
    else:
        filtros = request.args.to_dict()
    
    # Processar filtros
    data_inicio = datetime.strptime(filtros.get('dataInicio', ''), '%Y-%m-%d').date() if filtros.get('dataInicio') else None
    data_fim = datetime.strptime(filtros.get('dataFim', ''), '%Y-%m-%d').date() if filtros.get('dataFim') else None
    obra_id = int(filtros.get('obra')) if filtros.get('obra') else None
    departamento_id = int(filtros.get('departamento')) if filtros.get('departamento') else None
    
    if tipo == 'funcionarios':
        query = Funcionario.query
        if departamento_id:
            query = query.filter_by(departamento_id=departamento_id)
        funcionarios = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Código</th><th>Nome</th><th>CPF</th><th>Departamento</th><th>Função</th><th>Data Admissão</th><th>Salário</th><th>Status</th></tr></thead><tbody>'
        
        for f in funcionarios:
            status_badge = '<span class="badge bg-success">Ativo</span>' if f.ativo else '<span class="badge bg-danger">Inativo</span>'
            html += f'<tr><td>{f.codigo or "-"}</td><td>{f.nome}</td><td>{f.cpf}</td><td>{f.departamento_ref.nome if f.departamento_ref else "-"}</td>'
            html += f'<td>{f.funcao_ref.nome if f.funcao_ref else "-"}</td><td>{f.data_admissao.strftime("%d/%m/%Y") if f.data_admissao else "-"}</td>'
            html += f'<td>R$ {f.salario:,.2f}</td><td>{status_badge}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Lista de Funcionários ({len(funcionarios)} registros)',
            'html': html
        })
    
    elif tipo == 'ponto':
        query = RegistroPonto.query
        if data_inicio:
            query = query.filter(RegistroPonto.data >= data_inicio)
        if data_fim:
            query = query.filter(RegistroPonto.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if departamento_id:
            query = query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
        
        registros = query.options(joinedload(RegistroPonto.funcionario_ref), joinedload(RegistroPonto.obra_ref)).order_by(RegistroPonto.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Funcionário</th><th>Obra</th><th>Entrada</th><th>Saída</th><th>Horas Trabalhadas</th><th>Horas Extras</th><th>Atrasos</th></tr></thead><tbody>'
        
        for r in registros:
            html += f'<tr><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.funcionario_ref.nome if r.funcionario_ref else "-"}</td>'
            html += f'<td>{r.obra_ref.nome if r.obra_ref else "-"}</td>'
            html += f'<td>{r.hora_entrada.strftime("%H:%M") if r.hora_entrada else "-"}</td>'
            html += f'<td>{r.hora_saida.strftime("%H:%M") if r.hora_saida else "-"}</td>'
            html += f'<td>{r.horas_trabalhadas:.2f}h</td>'
            html += f'<td>{r.horas_extras:.2f}h</td>'
            html += f'<td>{r.total_atraso_minutos or 0} min</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Ponto ({len(registros)} registros)',
            'html': html
        })
    
    elif tipo == 'horas-extras':
        query = RegistroPonto.query.filter(RegistroPonto.horas_extras > 0)
        if data_inicio:
            query = query.filter(RegistroPonto.data >= data_inicio)
        if data_fim:
            query = query.filter(RegistroPonto.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if departamento_id:
            query = query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
        
        registros = query.options(joinedload(RegistroPonto.funcionario_ref), joinedload(RegistroPonto.obra_ref)).order_by(RegistroPonto.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Funcionário</th><th>Obra</th><th>Horas Extras</th><th>Valor Estimado</th></tr></thead><tbody>'
        
        total_horas = 0
        total_valor = 0
        
        for r in registros:
            # Usar cálculo corrigido conforme legislação brasileira
            horario = r.funcionario.horario_trabalho
            if horario and horario.horas_diarias:
                horas_mensais = horario.horas_diarias * 22  # 22 dias úteis
            else:
                horas_mensais = 176  # 8h × 22 dias (não 220h!)
            
            valor_hora_normal = r.funcionario.salario / horas_mensais if r.funcionario.salario else 0
            
            # Multiplicador conforme tipo de registro
            if r.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                multiplicador = 2.0  # 100% adicional
            else:
                multiplicador = 1.5  # 50% adicional padrão
            
            valor_extras = r.horas_extras * valor_hora_normal * multiplicador
            total_horas += r.horas_extras
            total_valor += valor_extras
            
            html += f'<tr><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.funcionario.nome}</td>'
            html += f'<td>{r.obra.nome if r.obra else "-"}</td>'
            html += f'<td>{r.horas_extras:.2f}h</td>'
            html += f'<td>R$ {valor_extras:.2f}</td></tr>'
        
        html += f'<tr class="table-info"><td colspan="3"><strong>TOTAL</strong></td><td><strong>{total_horas:.2f}h</strong></td><td><strong>R$ {total_valor:.2f}</strong></td></tr>'
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Horas Extras ({len(registros)} registros)',
            'html': html
        })
    
    elif tipo == 'alimentacao':
        query = RegistroAlimentacao.query
        if data_inicio:
            query = query.filter(RegistroAlimentacao.data >= data_inicio)
        if data_fim:
            query = query.filter(RegistroAlimentacao.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if departamento_id:
            query = query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
        
        registros = query.join(Funcionario).order_by(RegistroAlimentacao.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Funcionário</th><th>Tipo</th><th>Restaurante</th><th>Obra</th><th>Valor</th></tr></thead><tbody>'
        
        total_valor = 0
        
        for r in registros:
            total_valor += r.valor
            html += f'<tr><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.funcionario.nome}</td>'
            html += f'<td>{r.tipo.title()}</td>'
            html += f'<td>{r.restaurante.nome if r.restaurante else "-"}</td>'
            html += f'<td>{r.obra.nome if r.obra else "-"}</td>'
            html += f'<td>R$ {r.valor:.2f}</td></tr>'
        
        html += f'<tr class="table-info"><td colspan="5"><strong>TOTAL</strong></td><td><strong>R$ {total_valor:.2f}</strong></td></tr>'
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Alimentação ({len(registros)} registros)',
            'html': html
        })
    
    elif tipo == 'obras':
        query = Obra.query
        if obra_id:
            query = query.filter_by(id=obra_id)
        
        obras = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Nome</th><th>Responsável</th><th>Data Início</th><th>Previsão Fim</th><th>Orçamento</th><th>Status</th><th>Funcionários</th></tr></thead><tbody>'
        
        for obra in obras:
            funcionarios_obra = db.session.query(func.count(FuncionarioObra.id)).filter_by(obra_id=obra.id).scalar()
            
            html += f'<tr><td>{obra.nome}</td>'
            html += f'<td>{obra.responsavel.nome if obra.responsavel else "-"}</td>'
            html += f'<td>{obra.data_inicio.strftime("%d/%m/%Y") if obra.data_inicio else "-"}</td>'
            html += f'<td>{obra.data_previsao_fim.strftime("%d/%m/%Y") if obra.data_previsao_fim else "-"}</td>'
            html += f'<td>R$ {obra.orcamento:,.2f}</td>'
            html += f'<td><span class="badge bg-primary">{obra.status}</span></td>'
            html += f'<td>{funcionarios_obra}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Lista de Obras ({len(obras)} registros)',
            'html': html
        })
    
    elif tipo == 'custos-obra':
        query = CustoObra.query
        if data_inicio:
            query = query.filter(CustoObra.data >= data_inicio)
        if data_fim:
            query = query.filter(CustoObra.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        
        custos = query.join(Obra).order_by(CustoObra.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Obra</th><th>Tipo</th><th>Descrição</th><th>Valor</th></tr></thead><tbody>'
        
        total_custos = 0
        
        for custo in custos:
            total_custos += custo.valor
            html += f'<tr><td>{custo.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{custo.obra.nome}</td>'
            html += f'<td>{custo.tipo.title()}</td>'
            html += f'<td>{custo.descricao or "-"}</td>'
            html += f'<td>R$ {custo.valor:.2f}</td></tr>'
        
        html += f'<tr class="table-info"><td colspan="4"><strong>TOTAL</strong></td><td><strong>R$ {total_custos:.2f}</strong></td></tr>'
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Custos por Obra ({len(custos)} registros)',
            'html': html
        })
    
    elif tipo == 'veiculos':
        # CORRIGIDO: Filtrar veículos por admin_id (multi-tenant)
        admin_id = current_user.id if hasattr(current_user, 'id') else None
        query = Veiculo.query.filter_by(admin_id=admin_id)
        veiculos = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Placa</th><th>Marca/Modelo</th><th>Ano</th><th>Tipo</th><th>KM Atual</th><th>Status</th><th>Próxima Manutenção</th></tr></thead><tbody>'
        
        for veiculo in veiculos:
            html += f'<tr><td>{veiculo.placa}</td>'
            html += f'<td>{veiculo.marca} {veiculo.modelo}</td>'
            html += f'<td>{veiculo.ano or "-"}</td>'
            html += f'<td>{veiculo.tipo}</td>'
            html += f'<td>{veiculo.km_atual or 0:,} km</td>'
            html += f'<td><span class="badge bg-info">{veiculo.status}</span></td>'
            html += f'<td>{veiculo.data_proxima_manutencao.strftime("%d/%m/%Y") if veiculo.data_proxima_manutencao else "-"}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Veículos ({len(veiculos)} registros)',
            'html': html
        })
    
    elif tipo == 'dashboard-executivo':
        # Dados consolidados para dashboard executivo - CORRIGIDO: Filtrar por admin_id
        admin_id = current_user.id if hasattr(current_user, 'id') else None
        total_funcionarios = Funcionario.query.filter_by(ativo=True, admin_id=admin_id).count()
        total_obras = Obra.query.filter_by(status='Em andamento', admin_id=admin_id).count()
        total_veiculos = Veiculo.query.filter_by(ativo=True, admin_id=admin_id).count()
        
        # Custos do mês atual
        hoje = date.today()
        primeiro_dia_mes = hoje.replace(day=1)
        
        custos_mes = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.data >= primeiro_dia_mes,
            CustoObra.data <= hoje
        ).scalar() or 0
        
        # Horas trabalhadas do mês
        horas_mes = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
            RegistroPonto.data >= primeiro_dia_mes,
            RegistroPonto.data <= hoje
        ).scalar() or 0
        
        # Alimentação do mês
        alimentacao_mes = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.data >= primeiro_dia_mes,
            RegistroAlimentacao.data <= hoje
        ).scalar() or 0
        
        html = '<div class="row">'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-primary">{total_funcionarios}</h2><p>Funcionários Ativos</p></div></div></div>'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-success">{total_obras}</h2><p>Obras em Andamento</p></div></div></div>'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-warning">{total_veiculos}</h2><p>Veículos</p></div></div></div>'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-info">R$ {custos_mes:,.0f}</h2><p>Custos do Mês</p></div></div></div>'
        html += '</div>'
        
        html += '<div class="row mt-4">'
        html += f'<div class="col-md-6"><div class="card"><div class="card-body"><h5>Resumo Mensal</h5><p><strong>Horas Trabalhadas:</strong> {horas_mes:.0f}h</p><p><strong>Custo por Hora:</strong> R$ {(custos_mes/horas_mes if horas_mes > 0 else 0):.2f}</p></div></div></div>'
        html += f'<div class="col-md-6"><div class="card"><div class="card-body"><h5>Alimentação</h5><p><strong>Gasto Mensal:</strong> R$ {alimentacao_mes:,.2f}</p><p><strong>Média por Funcionário:</strong> R$ {(alimentacao_mes/total_funcionarios if total_funcionarios > 0 else 0):.2f}</p></div></div></div>'
        html += '</div>'
        
        return jsonify({
            'titulo': 'Dashboard Executivo',
            'html': html
        })
    
    elif tipo == 'progresso-obras':
        obras = Obra.query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Obra</th><th>Progresso</th><th>Orçamento</th><th>Gasto Atual</th><th>Saldo</th><th>% Utilizado</th></tr></thead><tbody>'
        
        for obra in obras:
            gasto_atual = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
            saldo = obra.orcamento - gasto_atual
            percentual = (gasto_atual / obra.orcamento * 100) if obra.orcamento > 0 else 0
            
            cor_saldo = 'text-success' if saldo > 0 else 'text-danger'
            
            html += f'<tr><td>{obra.nome}</td>'
            html += f'<td><span class="badge bg-info">{obra.status}</span></td>'
            html += f'<td>R$ {obra.orcamento:,.2f}</td>'
            html += f'<td>R$ {gasto_atual:,.2f}</td>'
            html += f'<td class="{cor_saldo}">R$ {saldo:,.2f}</td>'
            html += f'<td>{percentual:.1f}%</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Progresso das Obras ({len(obras)} registros)',
            'html': html
        })
    
    elif tipo == 'rentabilidade':
        # Análise de rentabilidade por obra
        obras = Obra.query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Obra</th><th>Receita Prevista</th><th>Custos</th><th>Margem</th><th>% Margem</th><th>Status</th></tr></thead><tbody>'
        
        for obra in obras:
            custos_obra = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
            receita_prevista = obra.orcamento * 1.3  # Assumindo 30% de margem padrão
            margem = receita_prevista - custos_obra
            percentual_margem = (margem / receita_prevista * 100) if receita_prevista > 0 else 0
            
            cor_margem = 'text-success' if margem > 0 else 'text-danger'
            
            html += f'<tr><td>{obra.nome}</td>'
            html += f'<td>R$ {receita_prevista:,.2f}</td>'
            html += f'<td>R$ {custos_obra:,.2f}</td>'
            html += f'<td class="{cor_margem}">R$ {margem:,.2f}</td>'
            html += f'<td class="{cor_margem}">{percentual_margem:.1f}%</td>'
            html += f'<td><span class="badge bg-primary">{obra.status}</span></td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Análise de Rentabilidade ({len(obras)} obras)',
            'html': html
        })
    
    else:
        return jsonify({
            'titulo': 'Relatório não implementado',
            'html': '<div class="alert alert-info">Este tipo de relatório ainda não foi implementado.</div>'
        })

@main_bp.route('/relatorios/exportar/<tipo>', methods=['GET', 'POST'])
@login_required
def exportar_relatorio(tipo):
    """Exporta relatório em formato específico"""
    from relatorios_funcionais import gerar_relatorio_funcional
    
    # Processar filtros e formato
    if request.method == 'POST':
        filtros = request.get_json() or {}
        formato = filtros.get('formato', 'csv')
    else:
        filtros = request.args.to_dict()
        formato = filtros.get('formato', 'csv')
    
    try:
        return gerar_relatorio_funcional(tipo, formato, filtros)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@main_bp.route('/funcionarios/<int:funcionario_id>/ocorrencias/nova', methods=['POST'])
@login_required
def nova_ocorrencia(funcionario_id):
    """Cria nova ocorrência para funcionário"""
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    try:
        # Criar ocorrência baseada no modelo existente
        ocorrencia = Ocorrencia(
            funcionario_id=funcionario_id,
            tipo=request.form.get('tipo'),
            data_inicio=datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date(),
            data_fim=datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date() if request.form.get('data_fim') else None,
            status=request.form.get('status', 'Pendente'),
            descricao=request.form.get('descricao', '')
        )
        
        db.session.add(ocorrencia)
        db.session.commit()
        
        flash('Ocorrência registrada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar ocorrência: {str(e)}', 'error')
        
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

@main_bp.route('/funcionarios/ocorrencias/<int:ocorrencia_id>/editar', methods=['POST'])
@login_required
def editar_ocorrencia(ocorrencia_id):
    """Edita ocorrência existente"""
    ocorrencia = Ocorrencia.query.get_or_404(ocorrencia_id)
    
    try:
        ocorrencia.tipo = request.form.get('tipo')
        ocorrencia.data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
        ocorrencia.data_fim = datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date() if request.form.get('data_fim') else None
        ocorrencia.status = request.form.get('status')
        ocorrencia.descricao = request.form.get('descricao', '')
        
        db.session.commit()
        flash('Ocorrência atualizada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar ocorrência: {str(e)}', 'error')
        
    return redirect(url_for('main.funcionario_perfil', id=ocorrencia.funcionario_id))

@main_bp.route('/funcionarios/ocorrencias/<int:ocorrencia_id>/excluir', methods=['POST'])
@login_required
def excluir_ocorrencia(ocorrencia_id):
    """Exclui ocorrência"""
    ocorrencia = Ocorrencia.query.get_or_404(ocorrencia_id)
    funcionario_id = ocorrencia.funcionario_id
    
    try:
        db.session.delete(ocorrencia)
        db.session.commit()
        flash('Ocorrência excluída com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir ocorrência: {str(e)}', 'error')
        
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

# === ROTAS FINANCEIRAS ===

@main_bp.route('/financeiro')
@login_required
def financeiro_dashboard():
    """Dashboard principal do módulo financeiro"""
    # Filtros de data
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Importar módulo financeiro
    from financeiro import obter_kpis_financeiros, calcular_fluxo_caixa_periodo
    
    # KPIs financeiros
    kpis = obter_kpis_financeiros(data_inicio, data_fim)
    
    # Fluxo de caixa detalhado
    fluxo = calcular_fluxo_caixa_periodo(data_inicio, data_fim)
    
    # Receitas recentes
    receitas_recentes = Receita.query.filter(
        Receita.data_receita >= data_inicio,
        Receita.data_receita <= data_fim
    ).order_by(Receita.data_receita.desc()).limit(10).all()
    
    # Centros de custo ativos
    centros_custo = CentroCusto.query.filter_by(ativo=True).all()
    
    return render_template('financeiro/dashboard.html',
                         kpis=kpis,
                         fluxo=fluxo,
                         receitas_recentes=receitas_recentes,
                         centros_custo=centros_custo,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@main_bp.route('/financeiro/receitas')
@login_required
def receitas():
    """Página de gestão de receitas"""
    # Filtros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    status_filtro = request.args.get('status', '')
    obra_filtro = request.args.get('obra_id', '')
    
    query = Receita.query
    
    if data_inicio:
        query = query.filter(Receita.data_receita >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(Receita.data_receita <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    if status_filtro:
        query = query.filter(Receita.status == status_filtro)
    if obra_filtro:
        query = query.filter(Receita.obra_id == int(obra_filtro))
    
    receitas = query.order_by(Receita.data_receita.desc()).all()
    
    # Dados para formulários
    obras = Obra.query.filter_by(status='Em andamento').all()
    centros_custo = CentroCusto.query.filter_by(ativo=True).all()
    
    return render_template('financeiro/receitas.html',
                         receitas=receitas,
                         obras=obras,
                         centros_custo=centros_custo,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         status_filtro=status_filtro,
                         obra_filtro=obra_filtro)

@main_bp.route('/financeiro/fluxo-caixa')
@login_required
def fluxo_caixa():
    """Página de fluxo de caixa"""
    from financeiro import calcular_fluxo_caixa_periodo
    
    # Filtros padrão
    data_inicio = request.args.get('data_inicio', date.today().replace(day=1).strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', date.today().strftime('%Y-%m-%d'))
    obra_id = request.args.get('obra_id', 0, type=int)
    centro_custo_id = request.args.get('centro_custo_id', 0, type=int)
    tipo_movimento = request.args.get('tipo_movimento', '')
    categoria = request.args.get('categoria', '')
    
    # Converter datas
    data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Calcular fluxo
    fluxo = calcular_fluxo_caixa_periodo(
        data_inicio_dt, 
        data_fim_dt,
        obra_id if obra_id != 0 else None,
        centro_custo_id if centro_custo_id != 0 else None
    )
    
    # Filtrar movimentos adicionalmente
    movimentos_filtrados = fluxo['movimentos']
    if tipo_movimento:
        movimentos_filtrados = [m for m in movimentos_filtrados if m.tipo_movimento == tipo_movimento]
    if categoria:
        movimentos_filtrados = [m for m in movimentos_filtrados if m.categoria == categoria]
    
    # Dados para formulários
    obras = Obra.query.all()
    centros_custo = CentroCusto.query.filter_by(ativo=True).all()
    
    return render_template('financeiro/fluxo_caixa.html',
                         fluxo=fluxo,
                         movimentos=movimentos_filtrados,
                         obras=obras,
                         centros_custo=centros_custo,
                         filtros={
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'obra_id': obra_id,
                             'centro_custo_id': centro_custo_id,
                             'tipo_movimento': tipo_movimento,
                             'categoria': categoria
                         })

@main_bp.route('/financeiro/centros-custo')
@login_required
def centros_custo():
    """Página de gestão de centros de custo"""
    centros = CentroCusto.query.all()
    return render_template('financeiro/centros_custo.html', centros=centros)

# ============================================================================
# ROTAS RDO (RELATÓRIO DIÁRIO DE OBRA)
# ============================================================================

@main_bp.route('/rdo')
@login_required
def lista_rdos():
    """Lista todos os RDOs com filtros"""
    page = request.args.get('page', 1, type=int)
    
    # Filtros
    obra_id = request.args.get('obra_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    status = request.args.get('status')
    
    # Query base
    query = RDO.query
    
    # Aplicar filtros
    if obra_id:
        query = query.filter(RDO.obra_id == obra_id)
    if data_inicio:
        query = query.filter(RDO.data_relatorio >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(RDO.data_relatorio <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    if status:
        query = query.filter(RDO.status == status)
    
    # Ordenação e paginação
    rdos = query.order_by(RDO.data_relatorio.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Dados para filtros
    obras = Obra.query.all()
    
    return render_template('rdo/lista_rdos.html', 
                         rdos=rdos, 
                         obras=obras,
                         filtros={
                             'obra_id': obra_id,
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'status': status
                         })

@main_bp.route('/rdo/novo')
@login_required
def novo_rdo():
    """Formulário para criar novo RDO"""
    from models import ServicoObra
    
    # Dados para template
    obras = Obra.query.filter_by(ativo=True).all()
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    # Query específica para evitar erro categoria_id
    servicos_data = db.session.query(
        Servico.id,
        Servico.nome,
        Servico.categoria,
        Servico.unidade_medida,
        Servico.unidade_simbolo,
        Servico.custo_unitario
    ).filter(Servico.ativo == True).all()
    
    # Converter para objetos acessíveis no template
    servicos = []
    for row in servicos_data:
        servico_obj = type('Servico', (), {
            'id': row.id,
            'nome': row.nome,
            'categoria': row.categoria,
            'unidade_medida': row.unidade_medida,
            'unidade_simbolo': row.unidade_simbolo,
            'custo_unitario': row.custo_unitario
        })()
        servicos.append(servico_obj)
    
    # Obter obra pré-selecionada se houver
    obra_id = request.args.get('obra_id')
    servicos_obra = []
    if obra_id:
        servicos_obra = db.session.query(ServicoObra, Servico).join(
            Servico, ServicoObra.servico_id == Servico.id
        ).filter(
            ServicoObra.obra_id == obra_id,
            ServicoObra.ativo == True
        ).all()
    
    # Buscar atividades da RDO anterior para auto-preenchimento
    atividades_anteriores = []
    if obra_id:
        rdo_anterior = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
        if rdo_anterior and rdo_anterior.atividades:
            atividades_anteriores = [{
                'descricao': atividade.descricao_atividade,
                'percentual': atividade.percentual_conclusao,
                'observacoes': atividade.observacoes_tecnicas or ''
            } for atividade in rdo_anterior.atividades]
    
    return render_template('rdo/formulario_rdo.html',
                         modo='novo', 
                         obras=obras,
                         funcionarios=funcionarios,
                         servicos=servicos,
                         servicos_obra=servicos_obra,
                         obra_id=obra_id,
                         atividades_anteriores=atividades_anteriores,
                         funcionarios_json=json.dumps([{'id': f.id, 'nome': f.nome} for f in funcionarios]),
                         obras_json=json.dumps([{'id': o.id, 'nome': o.nome} for o in obras]),
                         data_hoje=datetime.now().strftime('%Y-%m-%d'))

@main_bp.route('/rdo/criar', methods=['POST'])
@login_required
def criar_rdo():
    """Processar criação de novo RDO"""
    try:
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(request.form.get('data_relatorio'), '%Y-%m-%d').date(),
            obra_id=request.form.get('obra_id'),
            criado_por_id=current_user.id,
            tempo_manha=request.form.get('tempo_manha', ''),
            tempo_tarde=request.form.get('tempo_tarde', ''),
            tempo_noite=request.form.get('tempo_noite', ''),
            observacoes_meteorologicas=request.form.get('observacoes_meteorologicas', ''),
            comentario_geral=request.form.get('comentario_geral', ''),
            status=request.form.get('status', 'Rascunho')
        )
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID
        
        # Processar atividades do formulário
        import re
        for key in request.form:
            if key.startswith('atividade_descricao_'):
                match = re.match(r'atividade_descricao_(\d+)', key)
                if match:
                    contador = match.group(1)
                    descricao = request.form.get(f'atividade_descricao_{contador}')
                    percentual = request.form.get(f'atividade_percentual_{contador}')
                    observacoes = request.form.get(f'atividade_observacoes_{contador}', '')
                    
                    if descricao and percentual:
                        from models import RDOAtividade
                        atividade = RDOAtividade(
                            rdo_id=rdo.id,
                            descricao_atividade=descricao,
                            percentual_conclusao=float(percentual),
                            observacoes_tecnicas=observacoes if observacoes else None
                        )
                        db.session.add(atividade)
        
        db.session.commit()
        
        flash('RDO criado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=rdo.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar RDO: {str(e)}', 'error')
        return redirect(url_for('main.novo_rdo'))

@main_bp.route('/rdo/<int:id>')
@login_required
def visualizar_rdo(id):
    """Visualizar detalhes de um RDO"""
    rdo = RDO.query.get_or_404(id)
    return render_template('rdo/visualizar_rdo.html', rdo=rdo)

@main_bp.route('/rdo/<int:id>/editar')
@login_required
def editar_rdo(id):
    """Formulário para editar RDO"""
    rdo = RDO.query.get_or_404(id)
    obras = Obra.query.all()
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('rdo/formulario_rdo.html', 
                         rdo=rdo,
                         obras=obras,
                         funcionarios=funcionarios,
                         modo='editar')

@main_bp.route('/api/rdo/atividades-anteriores/<int:obra_id>')
@login_required
def api_atividades_anteriores(obra_id):
    """API para buscar atividades da RDO anterior de uma obra"""
    try:
        # Buscar RDO mais recente da obra (excluindo a data atual)
        data_hoje = request.args.get('data_atual')
        query = RDO.query.filter_by(obra_id=obra_id)
        
        # Excluir a data atual se fornecida
        if data_hoje:
            query = query.filter(RDO.data_relatorio < datetime.strptime(data_hoje, '%Y-%m-%d').date())
        
        rdo_anterior = query.order_by(RDO.data_relatorio.desc()).first()
        
        if not rdo_anterior or not rdo_anterior.atividades:
            return jsonify({
                'success': True,
                'atividades': [],
                'message': 'Nenhuma atividade anterior encontrada'
            })
        
        atividades = [{
            'descricao': atividade.descricao_atividade,
            'percentual': atividade.percentual_conclusao,
            'observacoes': atividade.observacoes_tecnicas or '',
            'rdo_anterior': rdo_anterior.numero_rdo,
            'data_anterior': rdo_anterior.data_relatorio.strftime('%d/%m/%Y')
        } for atividade in rdo_anterior.atividades]
        
        return jsonify({
            'success': True,
            'atividades': atividades,
            'rdo_anterior': rdo_anterior.numero_rdo,
            'data_anterior': rdo_anterior.data_relatorio.strftime('%d/%m/%Y'),
            'message': f'{len(atividades)} atividades encontradas do RDO {rdo_anterior.numero_rdo}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar atividades anteriores: {str(e)}'
        }), 500

@main_bp.route('/rdo/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_rdo(id):
    """Excluir RDO"""
    try:
        rdo = RDO.query.get_or_404(id)
        db.session.delete(rdo)
        db.session.commit()
        
        flash('RDO excluído com sucesso!', 'success')
        return redirect(url_for('main.lista_rdos'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir RDO: {str(e)}', 'error')
        return redirect(url_for('main.lista_rdos'))

@main_bp.route('/financeiro/centros-custo/novo', methods=['GET', 'POST'])
@login_required
def novo_centro_custo():
    """Criar novo centro de custo"""
    from financeiro import gerar_codigo_centro_custo
    
    if request.method == 'POST':
        try:
            centro = CentroCusto(
                codigo=request.form.get('codigo'),
                nome=request.form.get('nome'),
                descricao=request.form.get('descricao'),
                tipo=request.form.get('tipo'),
                obra_id=int(request.form.get('obra_id')) if request.form.get('obra_id') != '0' else None,
                departamento_id=int(request.form.get('departamento_id')) if request.form.get('departamento_id') != '0' else None,
                ativo=bool(request.form.get('ativo'))
            )
            
            db.session.add(centro)
            db.session.commit()
            flash('Centro de custo cadastrado com sucesso!', 'success')
            return redirect(url_for('main.centros_custo'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar centro de custo: {str(e)}', 'error')
    
    # Dados para formulário
    obras = Obra.query.all()
    departamentos = Departamento.query.all()
    codigo_padrao = gerar_codigo_centro_custo()
    
    return render_template('financeiro/centro_custo_form.html', 
                         titulo='Novo Centro de Custo',
                         codigo_padrao=codigo_padrao,
                         obras=obras,
                         departamentos=departamentos)

@main_bp.route('/financeiro/sincronizar-fluxo', methods=['POST'])
@login_required
def sincronizar_fluxo():
    """Sincronizar dados do fluxo de caixa"""
    try:
        from financeiro import sincronizar_fluxo_caixa
        sincronizar_fluxo_caixa()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Fluxo de caixa sincronizado com sucesso!'})
        else:
            flash('Fluxo de caixa sincronizado com sucesso!', 'success')
            return redirect(url_for('main.fluxo_caixa'))
    except Exception as e:
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)})
        else:
            flash(f'Erro ao sincronizar fluxo de caixa: {str(e)}', 'error')
            return redirect(url_for('main.fluxo_caixa'))

@main_bp.route('/horarios')
@login_required
def horarios():
    """Página de gestão de horários de trabalho"""
    horarios = HorarioTrabalho.query.all()
    return render_template('horarios.html', horarios=horarios)

@main_bp.route('/horarios/novo', methods=['POST'])
@login_required
def novo_horario():
    """Criar novo horário de trabalho"""
    try:
        nome = request.form.get('nome')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        retorno_almoco = request.form.get('retorno_almoco')
        saida = request.form.get('saida')
        dias_semana = request.form.get('dias_semana')
        
        # Verificar se já existe horário com o mesmo nome
        horario_existente = HorarioTrabalho.query.filter_by(nome=nome).first()
        if horario_existente:
            flash('Já existe um horário com este nome!', 'error')
            return redirect(url_for('main.horarios'))
        
        # Calcular horas diárias
        entrada_time = datetime.strptime(entrada, '%H:%M').time()
        saida_almoco_time = datetime.strptime(saida_almoco, '%H:%M').time()
        retorno_almoco_time = datetime.strptime(retorno_almoco, '%H:%M').time()
        saida_time = datetime.strptime(saida, '%H:%M').time()
        
        # Calcular horas trabalhadas (manhã + tarde)
        manha_inicio = datetime.combine(date.today(), entrada_time)
        manha_fim = datetime.combine(date.today(), saida_almoco_time)
        tarde_inicio = datetime.combine(date.today(), retorno_almoco_time)
        tarde_fim = datetime.combine(date.today(), saida_time)
        
        horas_manha = (manha_fim - manha_inicio).total_seconds() / 3600
        horas_tarde = (tarde_fim - tarde_inicio).total_seconds() / 3600
        horas_diarias = horas_manha + horas_tarde
        
        # Calcular valor da hora (baseado no salário mínimo padrão)
        valor_hora = 12.00  # Valor padrão, pode ser ajustado
        
        # Criar horário
        horario = HorarioTrabalho(
            nome=nome,
            entrada=entrada_time,
            saida_almoco=saida_almoco_time,
            retorno_almoco=retorno_almoco_time,
            saida=saida_time,
            dias_semana=dias_semana,
            horas_diarias=horas_diarias,
            valor_hora=valor_hora
        )
        
        db.session.add(horario)
        db.session.commit()
        
        flash('Horário de trabalho criado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

@main_bp.route('/horarios/editar/<int:id>', methods=['POST'])
@login_required
def editar_horario(id):
    """Editar horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        
        nome = request.form.get('nome')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        retorno_almoco = request.form.get('retorno_almoco')
        saida = request.form.get('saida')
        dias_semana = request.form.get('dias_semana')
        
        # Verificar se já existe outro horário com o mesmo nome
        horario_existente = HorarioTrabalho.query.filter(
            HorarioTrabalho.nome == nome,
            HorarioTrabalho.id != id
        ).first()
        if horario_existente:
            flash('Já existe um horário com este nome!', 'error')
            return redirect(url_for('main.horarios'))
        
        # Calcular horas diárias
        entrada_time = datetime.strptime(entrada, '%H:%M').time()
        saida_almoco_time = datetime.strptime(saida_almoco, '%H:%M').time()
        retorno_almoco_time = datetime.strptime(retorno_almoco, '%H:%M').time()
        saida_time = datetime.strptime(saida, '%H:%M').time()
        
        # Calcular horas trabalhadas (manhã + tarde)
        manha_inicio = datetime.combine(date.today(), entrada_time)
        manha_fim = datetime.combine(date.today(), saida_almoco_time)
        tarde_inicio = datetime.combine(date.today(), retorno_almoco_time)
        tarde_fim = datetime.combine(date.today(), saida_time)
        
        horas_manha = (manha_fim - manha_inicio).total_seconds() / 3600
        horas_tarde = (tarde_fim - tarde_inicio).total_seconds() / 3600
        horas_diarias = horas_manha + horas_tarde
        
        # Atualizar horário
        horario.nome = nome
        horario.entrada = entrada_time
        horario.saida_almoco = saida_almoco_time
        horario.retorno_almoco = retorno_almoco_time
        horario.saida = saida_time
        horario.dias_semana = dias_semana
        horario.horas_diarias = horas_diarias
        
        db.session.commit()
        
        flash('Horário de trabalho atualizado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

@main_bp.route('/horarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_horario(id):
    """Excluir horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        
        # Verificar se há funcionários usando este horário
        funcionarios_usando = Funcionario.query.filter_by(horario_trabalho_id=id).count()
        if funcionarios_usando > 0:
            flash(f'Não é possível excluir. Existem {funcionarios_usando} funcionários usando este horário.', 'error')
            return redirect(url_for('main.horarios'))
        
        db.session.delete(horario)
        db.session.commit()
        
        flash('Horário de trabalho excluído com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

# ==========================================
# MÓDULOS CRUD - CONTROLE DE PONTO, OUTROS CUSTOS E ALIMENTAÇÃO
# ==========================================

@main_bp.route('/controle-ponto')
@login_required
def controle_ponto():
    """Página principal do controle de ponto"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_registro = request.args.get('tipo_registro')
    
    # Query base com filtro de tenant - CORREÇÃO CRÍTICA para multi-tenancy
    query = RegistroPonto.query.join(Funcionario).filter(
        Funcionario.admin_id == current_user.id
    )
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
    
    if data_inicio:
        query = query.filter(RegistroPonto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroPonto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo_registro:
        query = query.filter(RegistroPonto.tipo_registro == tipo_registro)
    
    # Buscar registros com joins
    registros = query.options(
        joinedload(RegistroPonto.funcionario),
        joinedload(RegistroPonto.obra)
    ).order_by(RegistroPonto.data.desc()).all()
    
    # Dados para formulário - também com filtro de tenant
    funcionarios = Funcionario.query.filter_by(
        admin_id=current_user.id, 
        ativo=True
    ).order_by(Funcionario.nome).all()
    
    obras = Obra.query.filter_by(
        admin_id=current_user.id,
        status='Em andamento'
    ).order_by(Obra.nome).all()
    
    # Calcular valor total das horas extras com base na legislação brasileira
    from calendar import monthrange
    total_valor_extras = 0.0
    
    for registro in registros:
        if registro.horas_extras and registro.horas_extras > 0 and registro.funcionario:
            funcionario = registro.funcionario
            
            if funcionario.salario:
                # Calcular dias úteis reais do mês do registro
                ano = registro.data.year
                mes = registro.data.month
                
                # Contar dias úteis (seg-sex) no mês específico
                import calendar
                dias_uteis = 0
                primeiro_dia, ultimo_dia = monthrange(ano, mes)
                
                for dia in range(1, ultimo_dia + 1):
                    data_check = registro.data.replace(day=dia)
                    # 0=segunda, 1=terça, ..., 6=domingo
                    if data_check.weekday() < 5:  # Segunda a sexta
                        dias_uteis += 1
                
                # Usar horário específico do funcionário
                if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
                    horas_diarias = funcionario.horario_trabalho.horas_diarias
                else:
                    horas_diarias = 8.8  # Padrão Carlos Alberto
                
                # Horas mensais = horas/dia × dias úteis do mês
                horas_mensais = horas_diarias * dias_uteis
                valor_hora_normal = funcionario.salario / horas_mensais
                
                # Multiplicador conforme legislação brasileira (CLT)
                if registro.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                    multiplicador = 2.0  # 100% adicional
                else:
                    multiplicador = 1.5  # 50% adicional padrão
                
                valor_extras_registro = registro.horas_extras * valor_hora_normal * multiplicador
                total_valor_extras += valor_extras_registro
    
    return render_template('controle_ponto.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         obras=obras,
                         total_valor_extras=total_valor_extras)

@main_bp.route('/ponto/registro', methods=['POST'])
@login_required
def criar_registro_ponto():
    """Criar novo registro de ponto com suporte completo a fins de semana"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_registro = request.form.get('tipo_registro', 'trabalho_normal')
        obra_id = request.form.get('obra_id') or None
        
        # ✅ PERMITIR LANÇAMENTOS EM QUALQUER DIA DA SEMANA
        # Verificar se já existe registro para esta data e funcionário
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data
        ).first()
        
        if registro_existente:
            return jsonify({'error': 'Já existe um registro de ponto para esta data.'}), 400
        
        print(f"🎯 Criando registro para {data.strftime('%d/%m/%Y')} - Tipo: {tipo_registro}")
        
        # Criar registro
        registro = RegistroPonto(
            funcionario_id=funcionario_id,
            data=data,
            tipo_registro=tipo_registro,
            obra_id=obra_id
        )
        
        # Adicionar horários se não for falta
        if tipo_registro not in ['falta', 'falta_justificada']:
            entrada = request.form.get('entrada')
            saida_almoco = request.form.get('saida_almoco')
            retorno_almoco = request.form.get('retorno_almoco')
            saida = request.form.get('saida')
            
            if entrada:
                registro.hora_entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.hora_almoco_saida = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.hora_almoco_retorno = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.hora_saida = datetime.strptime(saida, '%H:%M').time()
        
        # Percentual de extras baseado no tipo
        if tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
            registro.percentual_extras = 50.0
        elif tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
            registro.percentual_extras = 100.0
        else:
            percentual_extras = request.form.get('percentual_extras')
            registro.percentual_extras = float(percentual_extras) if percentual_extras else 0.0
        
        # Observações
        registro.observacoes = request.form.get('observacoes')
        
        # ✅ APLICAR LÓGICA ESPECIAL PARA FINS DE SEMANA
        dia_semana = data.weekday()  # 0=segunda, 5=sábado, 6=domingo
        
        if dia_semana == 5 and tipo_registro in ['trabalho_normal', 'sabado_trabalhado']:
            # Sábado trabalhado
            print("✅ CONFIGURANDO SÁBADO TRABALHADO")
            registro.tipo_registro = 'sabado_trabalhado'
            registro.percentual_extras = 50.0
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            
        elif dia_semana == 6 and tipo_registro in ['trabalho_normal', 'domingo_trabalhado']:
            # Domingo trabalhado
            print("✅ CONFIGURANDO DOMINGO TRABALHADO")
            registro.tipo_registro = 'domingo_trabalhado'
            registro.percentual_extras = 100.0
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
        
        db.session.add(registro)
        db.session.commit()
        
        print(f"✅ Registro criado com sucesso: {registro.id} - {tipo_registro}")
        
        return jsonify({
            'success': True,
            'message': f'Registro de ponto criado para {data.strftime("%d/%m/%Y")}',
            'registro_id': registro.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['GET', 'PUT'])
@login_required
def editar_registro_ponto(registro_id):
    """Sistema completo de edição de registros de ponto"""
    try:
        registro = RegistroPonto.query.get_or_404(registro_id)
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        # Verificar permissões
        if not verificar_permissao_edicao_ponto(registro, current_user):
            print(f"❌ Permissão negada para {current_user.email} editar registro {registro_id}")
            return jsonify({'error': 'Sem permissão para editar este registro'}), 403
        
        if request.method == 'GET':
            # Retornar dados para edição
            return jsonify({
                'success': True,
                'registro': serializar_registro_completo(registro, funcionario),
                'obras_disponiveis': obter_obras_usuario(current_user),
                'tipos_registro': obter_tipos_registro_validos()
            })
            
        elif request.method == 'PUT':
            # Processar edição
            dados = request.get_json()
            
            # Validar dados de entrada
            validacao = validar_dados_edicao_ponto(dados, registro)
            if not validacao['valido']:
                return jsonify({'success': False, 'error': validacao['erro']})
            
            # Aplicar alterações
            aplicar_edicao_registro(registro, dados)
            
            # Recalcular valores baseado no tipo
            recalcular_registro_automatico(registro)
            
            # Salvar alterações
            db.session.commit()
            
            print(f"✅ Registro {registro_id} editado por {current_user.email}")
            
            return jsonify({
                'success': True,
                'message': 'Registro atualizado com sucesso!',
                'registro': serializar_registro_completo(registro, funcionario)
            })
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao editar registro {registro_id}: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

def verificar_permissao_edicao_ponto(registro, usuario):
    """Verifica permissões para editar registro"""
    print(f"🔍 Verificando permissão: usuário {usuario.email} ({usuario.tipo_usuario})")
    
    # Usar o enum corretamente
    from models import TipoUsuario
    
    if usuario.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        print("✅ Permissão concedida: SUPER_ADMIN")
        return True
    elif usuario.tipo_usuario == TipoUsuario.ADMIN:
        # Admin pode editar registros de funcionários sob sua gestão
        funcionario = Funcionario.query.get(registro.funcionario_id)
        if funcionario:
            pode_editar = funcionario.admin_id == usuario.id
            print(f"🔍 Admin {usuario.id} vs Funcionário admin_id {funcionario.admin_id}: {'✅' if pode_editar else '❌'}")
            return pode_editar
        else:
            print("❌ Funcionário não encontrado")
            return False
    else:
        print(f"❌ Tipo de usuário {usuario.tipo_usuario} não pode editar")
        return False

def serializar_registro_completo(registro, funcionario):
    """Serializa registro completo para frontend"""
    # Mapear tipos do banco para frontend
    tipo_frontend = mapear_tipo_para_frontend(registro.tipo_registro)
    
    return {
        'id': registro.id,
        'funcionario': {
            'id': funcionario.id,
            'nome': funcionario.nome,
            'codigo': funcionario.codigo
        },
        'data': registro.data.strftime('%Y-%m-%d'),
        'data_formatada': registro.data.strftime('%d/%m/%Y'),
        'dia_semana': registro.data.strftime('%A'),
        'tipo_registro': tipo_frontend,
        'horarios': {
            'entrada': registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else '',
            'almoco_saida': registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else '',
            'almoco_retorno': registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else '',
            'saida': registro.hora_saida.strftime('%H:%M') if registro.hora_saida else ''
        },
        'valores_calculados': {
            'horas_trabalhadas': float(registro.horas_trabalhadas or 0),
            'horas_extras': float(registro.horas_extras or 0),
            'percentual_extras': float(registro.percentual_extras or 0),
            'total_atraso_horas': float(registro.total_atraso_horas or 0),
            'total_atraso_minutos': int(registro.total_atraso_minutos or 0)
        },
        'obra_id': registro.obra_id,
        'observacoes': registro.observacoes or '',
        'horario_padrao': obter_horario_padrao_funcionario(funcionario)
    }

def mapear_tipo_para_frontend(tipo_banco):
    """Mapeia tipos do banco para o frontend"""
    mapeamento = {
        'trabalhado': 'trabalho_normal',
        'sabado_horas_extras': 'sabado_trabalhado',
        'domingo_horas_extras': 'domingo_trabalhado',
        'feriado': 'feriado_folga',
        'feriado_trabalhado': 'feriado_trabalhado',
        'falta_justificada': 'falta_justificada',
        'falta': 'falta',
        'ferias': 'ferias'
    }
    return mapeamento.get(tipo_banco, tipo_banco)

def mapear_tipo_para_banco(tipo_frontend):
    """Mapeia tipos do frontend para o banco"""
    mapeamento = {
        'trabalho_normal': 'trabalhado',
        'sabado_trabalhado': 'sabado_horas_extras',
        'domingo_trabalhado': 'domingo_horas_extras',
        'feriado_folga': 'feriado',
        'feriado_trabalhado': 'feriado_trabalhado',
        'falta_justificada': 'falta_justificada',
        'falta': 'falta',
        'ferias': 'ferias'
    }
    return mapeamento.get(tipo_frontend, tipo_frontend)

def obter_horario_padrao_funcionario(funcionario):
    """Retorna horário padrão do funcionário"""
    if funcionario.horario_trabalho_id:
        horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
        if horario:
            return {
                'entrada': horario.entrada.strftime('%H:%M') if horario.entrada else '08:00',
                'saida': horario.saida.strftime('%H:%M') if horario.saida else '17:00',
                'almoco_saida': horario.saida_almoco.strftime('%H:%M') if horario.saida_almoco else '12:00',
                'almoco_retorno': horario.retorno_almoco.strftime('%H:%M') if horario.retorno_almoco else '13:00'
            }
    return {
        'entrada': '08:00',
        'saida': '17:00', 
        'almoco_saida': '12:00',
        'almoco_retorno': '13:00'
    }

# ===== EXCLUSÃO EM LOTE =====
@main_bp.route('/ponto/preview-exclusao', methods=['POST'])
@login_required
def preview_exclusao_periodo():
    """Preview dos registros que serão excluídos"""
    try:
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        funcionario_id = request.form.get('funcionario_id')
        
        if not data_inicio or not data_fim:
            return jsonify({'success': False, 'message': 'Datas são obrigatórias'})
        
        # Converter datas
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Query com filtro de tenant
        query = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == current_user.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        )
        
        # Filtro adicional por funcionário se especificado
        if funcionario_id:
            query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
            funcionario = Funcionario.query.get(funcionario_id)
            nome_funcionario = funcionario.nome if funcionario else 'Funcionário não encontrado'
        else:
            nome_funcionario = None
        
        registros = query.all()
        
        # Tipos de registro encontrados
        tipos_registro = list(set([r.tipo_registro for r in registros]))
        
        return jsonify({
            'success': True,
            'data_inicio': data_inicio.strftime('%d/%m/%Y'),
            'data_fim': data_fim.strftime('%d/%m/%Y'),
            'funcionario': nome_funcionario,
            'total_registros': len(registros),
            'tipos_registro': tipos_registro
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

@main_bp.route('/ponto/excluir-periodo', methods=['POST'])
@login_required
def excluir_registros_periodo():
    """Excluir registros de ponto por período"""
    try:
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        funcionario_id = request.form.get('funcionario_id')
        
        if not data_inicio or not data_fim:
            return jsonify({'success': False, 'message': 'Datas são obrigatórias'})
        
        # Converter datas
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Query com filtro de tenant
        query = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == current_user.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        )
        
        # Filtro adicional por funcionário se especificado
        if funcionario_id:
            query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
        
        # Buscar registros para excluir
        registros = query.all()
        total_registros = len(registros)
        
        # Excluir registros
        for registro in registros:
            db.session.delete(registro)
        
        db.session.commit()
        
        print(f"✅ {total_registros} registros excluídos por {current_user.email} (período: {data_inicio} a {data_fim})")
        
        return jsonify({
            'success': True,
            'message': f'{total_registros} registros excluídos com sucesso',
            'registros_excluidos': total_registros
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao excluir registros: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

# ===== SCRIPT DE MIGRAÇÃO PARA PRODUÇÃO =====

def obter_obras_usuario(usuario):
    """Retorna obras disponíveis para o usuário"""
    from models import TipoUsuario
    
    if usuario.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        obras = Obra.query.filter_by(ativo=True).all()
    else:
        obras = Obra.query.filter_by(admin_id=usuario.id, ativo=True).all()
    
    return [{'id': obra.id, 'nome': obra.nome} for obra in obras]

def obter_tipos_registro_validos():
    """Retorna tipos de registro válidos"""
    return [
        {'valor': 'trabalho_normal', 'nome': 'Trabalho Normal'},
        {'valor': 'sabado_trabalhado', 'nome': 'Sábado - Horas Extras'},
        {'valor': 'domingo_trabalhado', 'nome': 'Domingo - Horas Extras'},
        {'valor': 'feriado_trabalhado', 'nome': 'Feriado Trabalhado'},
        {'valor': 'meio_periodo', 'nome': 'Meio Período'},
        {'valor': 'falta', 'nome': 'Falta'},
        {'valor': 'falta_justificada', 'nome': 'Falta Justificada'},
        {'valor': 'ferias', 'nome': 'Férias'},
        {'valor': 'feriado_folga', 'nome': 'Feriado Normal'},
        {'valor': 'sabado_folga', 'nome': 'Sábado - Folga'},
        {'valor': 'domingo_folga', 'nome': 'Domingo - Folga'}
    ]

def validar_dados_edicao_ponto(dados, registro):
    """Valida dados de edição com regras robustas"""
    erros = []
    
    # Validar tipo de registro (pode vir como tipo_lancamento ou tipo_registro)
    tipos_validos = [t['valor'] for t in obter_tipos_registro_validos()]
    tipo_recebido = dados.get('tipo_lancamento') or dados.get('tipo_registro')
    
    print(f"🔍 Validando tipo: recebido='{tipo_recebido}', válidos={tipos_validos}")
    
    if tipo_recebido not in tipos_validos:
        erros.append(f'Tipo de registro inválido: {tipo_recebido}')
    
    # Validar horários para tipos que trabalham
    tipos_trabalhados = ['trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado', 'meio_periodo']
    
    if tipo_recebido in tipos_trabalhados:
        if not dados.get('hora_entrada') or not dados.get('hora_saida'):
            erros.append('Horários de entrada e saída são obrigatórios')
        
        # Validar formato de horários
        for campo in ['hora_entrada', 'hora_saida', 'hora_almoco_saida', 'hora_almoco_retorno']:
            valor = dados.get(campo)
            if valor and not validar_formato_hora(valor):
                erros.append(f'Formato inválido para {campo}')
        
        # Validar sequência lógica
        if dados.get('hora_entrada') and dados.get('hora_saida'):
            if not validar_sequencia_horarios_edicao(dados):
                erros.append('Sequência de horários inválida')
    
    return {
        'valido': len(erros) == 0,
        'erro': '; '.join(erros) if erros else None
    }

def validar_formato_hora(hora_str):
    """Valida formato HH:MM"""
    try:
        datetime.strptime(hora_str, '%H:%M')
        return True
    except ValueError:
        return False

def validar_sequencia_horarios_edicao(dados):
    """Valida se horários estão em sequência lógica"""
    try:
        horarios = []
        
        for campo in ['hora_entrada', 'hora_almoco_saida', 'hora_almoco_retorno', 'hora_saida']:
            valor = dados.get(campo)
            if valor:
                horarios.append(datetime.strptime(valor, '%H:%M').time())
        
        # Verificar ordem crescente
        for i in range(1, len(horarios)):
            if horarios[i] <= horarios[i-1]:
                return False
        
        return True
    except ValueError:
        return False

def aplicar_edicao_registro(registro, dados):
    """Aplica edições ao registro"""
    # Mapear tipo para banco (pode vir como tipo_lancamento ou tipo_registro)
    tipo_recebido = dados.get('tipo_lancamento') or dados.get('tipo_registro')
    tipo_banco = mapear_tipo_para_banco(tipo_recebido)
    registro.tipo_registro = tipo_banco
    
    print(f"🔄 Aplicando edição: tipo '{tipo_recebido}' → banco '{tipo_banco}'")
    
    # Atualizar horários
    for campo_front, campo_banco in [
        ('hora_entrada', 'hora_entrada'),
        ('hora_almoco_saida', 'hora_almoco_saida'),
        ('hora_almoco_retorno', 'hora_almoco_retorno'),
        ('hora_saida', 'hora_saida')
    ]:
        valor = dados.get(campo_front)
        if valor:
            setattr(registro, campo_banco, datetime.strptime(valor, '%H:%M').time())
        else:
            setattr(registro, campo_banco, None)
    
    # Atualizar outros campos
    registro.obra_id = dados.get('obra_id')
    registro.observacoes = dados.get('observacoes', '')

def recalcular_registro_automatico(registro):
    """Recalcula registro com lógica automática baseada no tipo"""
    tipo = registro.tipo_registro
    
    # Resetar valores
    registro.horas_trabalhadas = 0.0
    registro.horas_extras = 0.0
    registro.total_atraso_horas = 0.0
    registro.total_atraso_minutos = 0
    registro.minutos_atraso_entrada = 0
    registro.minutos_atraso_saida = 0
    registro.percentual_extras = 0.0
    
    # Tipos sem trabalho
    tipos_sem_trabalho = ['falta', 'sabado_folga', 'domingo_folga', 'feriado']
    if tipo in tipos_sem_trabalho:
        return
    
    # Tipos especiais sem horários
    if tipo in ['falta_justificada', 'ferias']:
        registro.horas_trabalhadas = 8.0
        return
    
    # Calcular para tipos com horários
    if not registro.hora_entrada or not registro.hora_saida:
        return
    
    # Calcular horas trabalhadas
    horas = calcular_horas_trabalhadas_edicao(registro)
    registro.horas_trabalhadas = horas
    
    # Aplicar lógica por tipo
    if tipo == 'sabado_horas_extras':
        # Sábado: todas as horas são extras (50%)
        registro.horas_extras = horas
        registro.percentual_extras = 50.0
        # Sem atrasos
        
    elif tipo in ['domingo_horas_extras', 'feriado_trabalhado']:
        # Domingo/Feriado: todas as horas são extras (100%)
        registro.horas_extras = horas
        registro.percentual_extras = 100.0
        # Sem atrasos
        
    elif tipo == 'trabalhado':
        # Trabalho normal: calcular extras baseado no horário padrão
        calcular_horas_extras_baseado_horario_padrao(registro)
        
        # Calcular atrasos apenas em dias normais
        calcular_atrasos_trabalho_normal(registro)

def calcular_horas_trabalhadas_edicao(registro):
    """Calcula horas trabalhadas considerando almoço"""
    entrada = datetime.combine(registro.data, registro.hora_entrada)
    saida = datetime.combine(registro.data, registro.hora_saida)
    
    total_minutos = (saida - entrada).total_seconds() / 60
    
    # Subtrair almoço se definido
    if registro.hora_almoco_saida and registro.hora_almoco_retorno:
        almoco_saida = datetime.combine(registro.data, registro.hora_almoco_saida)
        almoco_retorno = datetime.combine(registro.data, registro.hora_almoco_retorno)
        minutos_almoco = (almoco_retorno - almoco_saida).total_seconds() / 60
        total_minutos -= minutos_almoco
    
    return total_minutos / 60.0

def calcular_atrasos_trabalho_normal(registro):
    """Calcula atrasos apenas para trabalho normal"""
    funcionario = Funcionario.query.get(registro.funcionario_id)
    if not funcionario or not funcionario.horario_trabalho_id:
        return
    
    horario_padrao = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
    if not horario_padrao:
        return
    
    # Calcular atraso de entrada
    if registro.hora_entrada and horario_padrao.entrada:
        entrada_esperada = datetime.combine(registro.data, horario_padrao.entrada)
        entrada_real = datetime.combine(registro.data, registro.hora_entrada)
        
        if entrada_real > entrada_esperada:
            minutos_atraso = (entrada_real - entrada_esperada).total_seconds() / 60
            registro.minutos_atraso_entrada = int(minutos_atraso)
            registro.total_atraso_minutos += int(minutos_atraso)
    
    # Converter total para horas
    registro.total_atraso_horas = registro.total_atraso_minutos / 60.0

def calcular_horas_extras_baseado_horario_padrao(registro):
    """Calcula horas extras baseado no horário padrão do funcionário"""
    funcionario = Funcionario.query.get(registro.funcionario_id)
    if not funcionario or not funcionario.horario_trabalho_id:
        # Sem horário padrão, usar 8h como base
        if registro.horas_trabalhadas > 8:
            registro.horas_extras = registro.horas_trabalhadas - 8
            registro.percentual_extras = 50.0
        return
    
    horario_padrao = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
    if not horario_padrao:
        # Sem horário padrão, usar 8h como base
        if registro.horas_trabalhadas > 8:
            registro.horas_extras = registro.horas_trabalhadas - 8
            registro.percentual_extras = 50.0
        return
    
    # Calcular horas padrão baseado no horário
    if horario_padrao.entrada and horario_padrao.saida:
        entrada_padrao = datetime.combine(registro.data, horario_padrao.entrada)
        saida_padrao = datetime.combine(registro.data, horario_padrao.saida)
        
        # Subtrair almoço padrão
        minutos_padrao = (saida_padrao - entrada_padrao).total_seconds() / 60
        if horario_padrao.saida_almoco and horario_padrao.retorno_almoco:
            almoco_saida_padrao = datetime.combine(registro.data, horario_padrao.saida_almoco)
            almoco_retorno_padrao = datetime.combine(registro.data, horario_padrao.retorno_almoco)
            minutos_almoco = (almoco_retorno_padrao - almoco_saida_padrao).total_seconds() / 60
            minutos_padrao -= minutos_almoco
        
        horas_padrao = minutos_padrao / 60.0
        
        # Calcular extras apenas se trabalhou mais que o padrão
        if registro.horas_trabalhadas > horas_padrao:
            registro.horas_extras = registro.horas_trabalhadas - horas_padrao
            registro.percentual_extras = 50.0
    else:
        # Fallback para 8h se não conseguir calcular
        if registro.horas_trabalhadas > 8:
            registro.horas_extras = registro.horas_trabalhadas - 8
            registro.percentual_extras = 50.0

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['GET'])
@login_required  
def obter_registro_ponto(registro_id):
    """Método GET separado para compatibilidade"""
    return editar_registro_ponto(registro_id)

@main_bp.route('/ponto/registro/<int:registro_id>/legacy', methods=['PUT', 'POST'])
@login_required
def atualizar_registro_ponto_legacy(registro_id):
    """Atualizar um registro de ponto individual"""
    try:
        print(f"✏️ Atualizando registro {registro_id}")
        
        # Buscar registro específico
        registro = RegistroPonto.query.get_or_404(registro_id)
        
        # Buscar funcionário
        funcionario = Funcionario.query.get(registro.funcionario_id)
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        # Obter dados do request
        if request.is_json:
            data_source = request.json
        else:
            data_source = request.form
        
        print(f"📝 Dados recebidos: {data_source}")
        
        # Validar e processar dados básicos
        data_str = data_source.get('data')
        if not data_str:
            return jsonify({'error': 'Data é obrigatória'}), 400
            
        data = datetime.strptime(data_str, '%Y-%m-%d').date()
        tipo_frontend = data_source.get('tipo_registro', 'trabalho_normal')
        obra_id = data_source.get('obra_id') or None
        observacoes = data_source.get('observacoes', '')
        
        # Converter tipo frontend para banco
        tipo_banco = tipo_frontend
        if tipo_frontend == 'trabalho_normal':
            tipo_banco = 'trabalhado'
        elif tipo_frontend == 'sabado_trabalhado':
            tipo_banco = 'sabado_horas_extras'
        elif tipo_frontend == 'domingo_trabalhado':
            tipo_banco = 'domingo_horas_extras'
        elif tipo_frontend == 'feriado_folga':
            tipo_banco = 'feriado'
        
        # Processar horários baseado no tipo
        if tipo_frontend in ['trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
            # Tipos que requerem horários
            entrada_str = data_source.get('hora_entrada', '')
            saida_almoco_str = data_source.get('hora_almoco_saida', '')
            retorno_almoco_str = data_source.get('hora_almoco_retorno', '')
            saida_str = data_source.get('hora_saida', '')
            
            # Converter horários
            hora_entrada = datetime.strptime(entrada_str, '%H:%M').time() if entrada_str else None
            hora_almoco_saida = datetime.strptime(saida_almoco_str, '%H:%M').time() if saida_almoco_str else None
            hora_almoco_retorno = datetime.strptime(retorno_almoco_str, '%H:%M').time() if retorno_almoco_str else None
            hora_saida = datetime.strptime(saida_str, '%H:%M').time() if saida_str else None
            
            # Calcular horas trabalhadas
            horas_trabalhadas = 0.0
            if hora_entrada and hora_saida:
                # Calcular total de horas
                entrada_minutos = hora_entrada.hour * 60 + hora_entrada.minute
                saida_minutos = hora_saida.hour * 60 + hora_saida.minute
                
                # Ajustar se passou da meia-noite
                if saida_minutos < entrada_minutos:
                    saida_minutos += 24 * 60
                
                total_minutos = saida_minutos - entrada_minutos
                
                # Subtrair almoço se ambos horários estiverem definidos
                if hora_almoco_saida and hora_almoco_retorno:
                    almoco_saida_min = hora_almoco_saida.hour * 60 + hora_almoco_saida.minute
                    almoco_retorno_min = hora_almoco_retorno.hour * 60 + hora_almoco_retorno.minute
                    
                    if almoco_retorno_min > almoco_saida_min:
                        total_minutos -= (almoco_retorno_min - almoco_saida_min)
                
                horas_trabalhadas = total_minutos / 60.0
            
            # Calcular horas extras baseado no tipo
            horas_extras = 0.0
            percentual_extras = 0.0
            
            if tipo_frontend in ['sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
                # Para fim de semana/feriado: TODAS as horas são extras
                horas_extras = horas_trabalhadas
                if tipo_frontend == 'sabado_trabalhado':
                    percentual_extras = 50.0
                else:  # domingo_trabalhado, feriado_trabalhado
                    percentual_extras = 100.0
            elif tipo_frontend == 'trabalho_normal' and horas_trabalhadas > 0:
                # Para trabalho normal: apenas horas acima da jornada
                horas_jornada = funcionario.horario_trabalho.horas_diarias if funcionario.horario_trabalho else 8.0
                horas_extras = max(0, horas_trabalhadas - horas_jornada)
                if horas_extras > 0:
                    percentual_extras = 50.0
            
        else:
            # Tipos sem horários (faltas, férias, etc.)
            hora_entrada = None
            hora_almoco_saida = None
            hora_almoco_retorno = None
            hora_saida = None
            horas_trabalhadas = 0.0
            horas_extras = 0.0
            percentual_extras = 0.0
        
        # Atualizar registro
        registro.data = data
        registro.tipo_registro = tipo_banco
        registro.obra_id = int(obra_id) if obra_id else None
        registro.hora_entrada = hora_entrada
        registro.hora_almoco_saida = hora_almoco_saida
        registro.hora_almoco_retorno = hora_almoco_retorno
        registro.hora_saida = hora_saida
        registro.horas_trabalhadas = horas_trabalhadas
        registro.horas_extras = horas_extras
        registro.percentual_extras = percentual_extras
        registro.observacoes = observacoes
        
        db.session.commit()
        
        print(f"✅ Registro {registro_id} atualizado: {tipo_banco}, {horas_trabalhadas}h, {horas_extras}h extras")
        
        return jsonify({
            'success': True,
            'message': 'Registro atualizado com sucesso',
            'registro': {
                'id': registro.id,
                'tipo_registro': tipo_banco,
                'horas_trabalhadas': horas_trabalhadas,
                'horas_extras': horas_extras,
                'percentual_extras': percentual_extras
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao atualizar registro {registro_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao salvar: {str(e)}'}), 500
        
        if obra_id == '':
            obra_id = None
        elif obra_id:
            obra_id = int(obra_id)
        
        # Atualizar dados básicos
        registro.data = data
        registro.tipo_registro = tipo_registro
        registro.obra_id = obra_id
        
        # Limpar horários primeiro
        registro.hora_entrada = None
        registro.hora_almoco_saida = None
        registro.hora_almoco_retorno = None
        registro.hora_saida = None
        registro.horas_trabalhadas = 0
        registro.horas_extras = 0
        
        # Adicionar horários se não for falta ou feriado
        if tipo_registro not in ['falta', 'falta_justificada', 'feriado']:
            entrada = data_source.get('hora_entrada') or data_source.get('hora_entrada_ponto')
            saida_almoco = data_source.get('hora_almoco_saida') or data_source.get('hora_almoco_saida_ponto')
            retorno_almoco = data_source.get('hora_almoco_retorno') or data_source.get('hora_almoco_retorno_ponto')
            saida = data_source.get('hora_saida') or data_source.get('hora_saida_ponto')
            
            if entrada:
                registro.hora_entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.hora_almoco_saida = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.hora_almoco_retorno = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.hora_saida = datetime.strptime(saida, '%H:%M').time()
                
        # Percentual de extras baseado no tipo
        if tipo_registro == 'sabado_horas_extras':
            registro.percentual_extras = 50.0
        elif tipo_registro in ['domingo_horas_extras', 'feriado_trabalhado']:
            registro.percentual_extras = 100.0
        else:
            percentual_extras = data_source.get('percentual_extras')
            registro.percentual_extras = float(percentual_extras) if percentual_extras else 0.0
        
        # Observações
        registro.observacoes = data_source.get('observacoes') or data_source.get('observacoes_ponto', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Registro atualizado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_ponto(registro_id):
    """Excluir um registro de ponto"""
    try:
        registro = RegistroPonto.query.get_or_404(registro_id)
        
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Registro excluído com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos')
@login_required
def controle_outros_custos():
    """Página principal do controle de outros custos"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')
    
    # Query base
    query = OutroCusto.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(OutroCusto.funcionario_id == funcionario_id)
    
    if data_inicio:
        query = query.filter(OutroCusto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(OutroCusto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo:
        query = query.filter(OutroCusto.tipo == tipo)
    
    # Buscar registros com joins
    custos = query.options(
        joinedload(OutroCusto.funcionario)
    ).order_by(OutroCusto.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('controle_outros_custos.html',
                         custos=custos,
                         funcionarios=funcionarios)

@main_bp.route('/outros-custos/custo', methods=['POST'])
@login_required
def criar_outro_custo_crud():
    """Criar novo custo"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        descricao = request.form.get('descricao')
        
        # Criar custo
        custo = OutroCusto(
            funcionario_id=funcionario_id,
            data=data,
            tipo=tipo,
            valor=valor,
            descricao=descricao
        )
        
        db.session.add(custo)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['GET'])
@login_required
def obter_outro_custo_crud(custo_id):
    """Obter dados de um custo"""
    custo = OutroCusto.query.get_or_404(custo_id)
    
    return jsonify({
        'id': custo.id,
        'funcionario_id': custo.funcionario_id,
        'data': custo.data.isoformat(),
        'tipo': custo.tipo,
        'valor': custo.valor,
        'descricao': custo.descricao
    })

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['PUT'])
@login_required
def atualizar_outro_custo_crud(custo_id):
    """Atualizar custo"""
    try:
        custo = OutroCusto.query.get_or_404(custo_id)
        
        custo.funcionario_id = request.form.get('funcionario_id')
        custo.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        custo.tipo = request.form.get('tipo')
        custo.valor = float(request.form.get('valor'))
        custo.descricao = request.form.get('descricao')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['DELETE'])
@login_required
def excluir_outro_custo_crud(custo_id):
    """Excluir custo"""
    try:
        custo = OutroCusto.query.get_or_404(custo_id)
        db.session.delete(custo)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao')
@login_required
def controle_alimentacao():
    """Página principal do controle de alimentação"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    restaurante_id = request.args.get('restaurante_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_refeicao = request.args.get('tipo_refeicao')
    
    # Query base
    query = RegistroAlimentacao.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(RegistroAlimentacao.funcionario_id == funcionario_id)
    
    if restaurante_id:
        query = query.filter(RegistroAlimentacao.restaurante_id == restaurante_id)
    
    if data_inicio:
        query = query.filter(RegistroAlimentacao.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroAlimentacao.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo_refeicao:
        query = query.filter(RegistroAlimentacao.tipo_refeicao == tipo_refeicao)
    
    # Buscar registros com joins
    registros = query.options(
        joinedload(RegistroAlimentacao.funcionario),
        joinedload(RegistroAlimentacao.restaurante)
    ).order_by(RegistroAlimentacao.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    restaurantes = Restaurante.query.filter_by(ativo=True).order_by(Restaurante.nome).all()
    
    return render_template('controle_alimentacao.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         restaurantes=restaurantes)

@main_bp.route('/alimentacao/registro', methods=['POST'])
@login_required
def criar_registro_alimentacao():
    """Criar novo registro de alimentação"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        restaurante_id = request.form.get('restaurante_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_refeicao = request.form.get('tipo_refeicao')
        valor = float(request.form.get('valor'))
        quantidade = int(request.form.get('quantidade', 1))
        observacoes = request.form.get('observacoes')
        
        # Criar registro
        registro = RegistroAlimentacao(
            funcionario_id=funcionario_id,
            restaurante_id=restaurante_id,
            data=data,
            tipo_refeicao=tipo_refeicao,
            valor=valor,
            quantidade=quantidade,
            observacoes=observacoes
        )
        
        db.session.add(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['GET'])
@login_required
def obter_registro_alimentacao(registro_id):
    """Obter dados de um registro de alimentação"""
    registro = RegistroAlimentacao.query.get_or_404(registro_id)
    
    return jsonify({
        'id': registro.id,
        'funcionario_id': registro.funcionario_id,
        'restaurante_id': registro.restaurante_id,
        'data': registro.data.isoformat(),
        'tipo_refeicao': registro.tipo_refeicao,
        'valor': registro.valor,
        'quantidade': registro.quantidade,
        'observacoes': registro.observacoes
    })

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['PUT'])
@login_required
def atualizar_registro_alimentacao(registro_id):
    """Atualizar registro de alimentação"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(registro_id)
        
        registro.funcionario_id = request.form.get('funcionario_id')
        registro.restaurante_id = request.form.get('restaurante_id')
        registro.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        registro.tipo_refeicao = request.form.get('tipo_refeicao')
        registro.valor = float(request.form.get('valor'))
        registro.quantidade = int(request.form.get('quantidade', 1))
        registro.observacoes = request.form.get('observacoes')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_alimentacao(registro_id):
    """Excluir registro de alimentação"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(registro_id)
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500



# API Endpoints para RDO
@main_bp.route("/api/obras/autocomplete")
@login_required
def api_obras_autocomplete():
    """API para autocomplete de obras"""
    try:
        q = request.args.get("q", "").strip()
        
        # Query base - obras ativas
        query = Obra.query.filter(Obra.ativo == True)
        
        # Se tem termo de busca, filtrar
        if q:
            query = query.filter(
                or_(
                    Obra.nome.ilike(f"%{q}%"),
                    Obra.codigo.ilike(f"%{q}%"),
                    Obra.endereco.ilike(f"%{q}%")
                )
            )
        
        # Limitar resultados e ordenar
        obras = query.order_by(Obra.nome).limit(20).all()
        
        # Debug - log para verificar
        print(f"Buscando obras com termo: '{q}' - Encontradas: {len(obras)}")
        
        resultado = []
        for obra in obras:
            resultado.append({
                "id": obra.id,
                "nome": obra.nome,
                "codigo": obra.codigo or "S/C",
                "endereco": obra.endereco or "Endereço não informado",
                "area_total_m2": float(obra.area_total_m2) if obra.area_total_m2 else 0,
                "status": obra.status or "Em andamento"
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint obras_autocomplete: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/obras/todas")
@login_required
def api_obras_todas():
    """API para carregar todas as obras (fallback)"""
    try:
        obras = Obra.query.filter(Obra.ativo == True).order_by(Obra.nome).all()
        
        return jsonify([{
            "id": obra.id,
            "nome": obra.nome,
            "codigo": obra.codigo or "S/C",
            "endereco": obra.endereco or "Endereço não informado"
        } for obra in obras])
        
    except Exception as e:
        print(f"Erro ao carregar todas as obras: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/funcionarios/rdo-autocomplete")
@login_required
def api_funcionarios_rdo_autocomplete():
    """API para autocomplete de funcionários com dados de ponto"""
    try:
        q = request.args.get("q", "").strip()
        data_rdo = request.args.get("data_rdo")
        
        # Query base - funcionários ativos
        query = Funcionario.query.filter(Funcionario.ativo == True)
        
        # Se tem termo de busca
        if q:
            query = query.filter(
                or_(
                    Funcionario.nome.ilike(f"%{q}%"),
                    Funcionario.codigo.ilike(f"%{q}%"),
                    Funcionario.cpf.ilike(f"%{q}%")
                )
            )
        
        funcionarios = query.order_by(Funcionario.nome).limit(20).all()
        
        print(f"Buscando funcionários: '{q}' - Encontrados: {len(funcionarios)}")
        
        resultado = []
        for func in funcionarios:
            # Buscar dados do ponto para a data
            presente_hoje = False
            horas_trabalhadas = 0
            
            if data_rdo:
                try:
                    data_consulta = datetime.strptime(data_rdo, "%Y-%m-%d").date()
                    registro_ponto = RegistroPonto.query.filter_by(
                        funcionario_id=func.id,
                        data=data_consulta
                    ).first()
                    
                    if registro_ponto:
                        presente_hoje = bool(registro_ponto.hora_entrada)
                        horas_trabalhadas = registro_ponto.horas_trabalhadas or 0
                except:
                    pass
            
            resultado.append({
                "id": func.id,
                "nome": func.nome,
                "codigo": func.codigo or f"F{func.id:03d}",
                "funcao": func.funcao.nome if func.funcao else "Não definida",
                "salario": float(func.salario) if func.salario else 0,
                "presente_hoje": presente_hoje,
                "horas_trabalhadas": horas_trabalhadas
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint funcionarios_rdo_autocomplete: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/funcionarios/todos")
@login_required
def api_funcionarios_todos():
    """API para carregar todos os funcionários (fallback)"""
    try:
        funcionarios = Funcionario.query.filter(Funcionario.ativo == True).order_by(Funcionario.nome).all()
        
        return jsonify([{
            "id": func.id,
            "nome": func.nome,
            "codigo": func.codigo or f"F{func.id:03d}",
            "funcao": func.funcao.nome if func.funcao else "Não definida"
        } for func in funcionarios])
        
    except Exception as e:
        print(f"Erro ao carregar funcionários: {str(e)}")
        return jsonify([]), 500

@main_bp.route('/api/servicos/autocomplete')
@login_required  
def api_servicos_autocomplete():
    """API para autocomplete de serviços"""
    q = request.args.get("q", "")
    ativo = request.args.get("ativo", "true").lower() == "true"
    
    # Query específica para evitar erro categoria_id
    query = db.session.query(
        Servico.id,
        Servico.nome,
        Servico.categoria,
        Servico.unidade_medida,
        Servico.unidade_simbolo,
        Servico.custo_unitario
    ).filter(Servico.ativo == ativo)
    
    if q:
        query = query.filter(
            or_(
                Servico.nome.ilike(f"%{q}%"),
                Servico.categoria.ilike(f"%{q}%")
            )
        )
    
    servicos_data = query.limit(10).all()
    
    return jsonify([{
        "id": row.id,
        "nome": row.nome,
        "categoria": row.categoria,
        "unidade_medida": row.unidade_medida,
        "unidade_simbolo": row.unidade_simbolo,
        "custo_unitario": float(row.custo_unitario) if row.custo_unitario else 0
    } for row in servicos_data])

@main_bp.route("/api/servicos/<int:servico_id>")
@login_required
def api_servico_detalhes(servico_id):
    """API para detalhes de um serviço específico com subatividades"""
    servico = Servico.query.get_or_404(servico_id)
    
    subatividades = SubAtividade.query.filter_by(servico_id=servico_id).all()
    
    return jsonify({
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
        "unidade_medida": servico.unidade_medida,
        "unidade_simbolo": servico.unidade_simbolo,
        "custo_unitario": float(servico.custo_unitario) if servico.custo_unitario else 0,
        "subatividades": [{
            "id": sub.id,
            "nome": sub.nome,
            "descricao": sub.descricao
        } for sub in subatividades]
    })

@main_bp.route("/api/equipamentos/autocomplete")
@login_required
def api_equipamentos_autocomplete():
    """API para autocomplete de equipamentos/veículos"""
    q = request.args.get("q", "")
    ativo = request.args.get("ativo", "true").lower() == "true"
    
    query = Veiculo.query.filter(Veiculo.ativo == ativo)
    
    if q:
        query = query.filter(
            or_(
                Veiculo.marca.ilike(f"%{q}%"),
                Veiculo.modelo.ilike(f"%{q}%"),
                Veiculo.placa.ilike(f"%{q}%"),
                Veiculo.tipo.ilike(f"%{q}%")
            )
        )
    
    veiculos = query.limit(10).all()
    
    return jsonify([{
        "id": veiculo.id,
        "nome": f"{veiculo.marca} {veiculo.modelo}",
        "placa": veiculo.placa,
        "tipo": veiculo.tipo,
        "status": veiculo.status
    } for veiculo in veiculos])

@main_bp.route("/api/ponto/funcionario/<int:funcionario_id>/data/<string:data>")
@login_required
def api_ponto_funcionario_data(funcionario_id, data):
    """API para buscar dados de ponto de um funcionário em uma data específica"""
    try:
        funcionario = Funcionario.query.get_or_404(funcionario_id)
        data_consulta = datetime.strptime(data, "%Y-%m-%d").date()
        
        registro_ponto = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data_consulta
        ).first()
        
        if registro_ponto:
            return jsonify({
                "success": True,
                "funcionario": {
                    "id": funcionario.id,
                    "nome": funcionario.nome,
                    "codigo": funcionario.codigo,
                    "funcao": funcionario.funcao.nome if funcionario.funcao else "Sem função"
                },
                "registro_ponto": {
                    "hora_entrada": registro_ponto.hora_entrada.strftime("%H:%M") if registro_ponto.hora_entrada else None,
                    "hora_saida": registro_ponto.hora_saida.strftime("%H:%M") if registro_ponto.hora_saida else None,
                    "horas_trabalhadas": registro_ponto.horas_trabalhadas or 0,
                    "tipo_registro": registro_ponto.tipo_registro
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": "Nenhum registro de ponto encontrado para esta data"
            })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erro ao buscar dados: {str(e)}"
        }), 500

@main_bp.route("/api/rdo/salvar", methods=["POST"])
@login_required
def api_rdo_salvar():
    """API para salvar RDO como rascunho"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get("data_relatorio") or not dados.get("obra_id"):
            return jsonify({
                "success": False,
                "message": "Data do relatório e obra são obrigatórios"
            }), 400
        
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(dados["data_relatorio"], "%Y-%m-%d").date(),
            obra_id=dados["obra_id"],
            criado_por_id=current_user.id,
            tempo_manha=dados.get("tempo_manha", ""),
            tempo_tarde=dados.get("tempo_tarde", ""),
            tempo_noite=dados.get("tempo_noite", ""),
            observacoes_meteorologicas=dados.get("observacoes_meteorologicas", ""),
            comentario_geral=dados.get("comentario_geral", ""),
            status="Rascunho"
        )
        
        db.session.add(rdo)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "RDO salvo como rascunho com sucesso",
            "rdo_id": rdo.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Erro ao salvar RDO: {str(e)}"
        }), 500

@main_bp.route("/api/rdo/finalizar", methods=["POST"])
@login_required
def api_rdo_finalizar():
    """API para finalizar RDO"""
    try:
        dados = request.get_json()
        
        # Validações obrigatórias
        if not dados.get("data_relatorio") or not dados.get("obra_id"):
            return jsonify({
                "success": False,
                "message": "Data do relatório e obra são obrigatórios"
            }), 400
        
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(dados["data_relatorio"], "%Y-%m-%d").date(),
            obra_id=dados["obra_id"],
            criado_por_id=current_user.id,
            tempo_manha=dados.get("tempo_manha", ""),
            tempo_tarde=dados.get("tempo_tarde", ""),
            tempo_noite=dados.get("tempo_noite", ""),
            observacoes_meteorologicas=dados.get("observacoes_meteorologicas", ""),
            comentario_geral=dados.get("comentario_geral", ""),
            status="Finalizado"
        )
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID do RDO
        
        # Salvar dados de mão de obra
        for func_data in dados.get("funcionarios", []):
            if func_data.get("funcionario_id"):
                rdo_mao_obra = RDOMaoObra(
                    rdo_id=rdo.id,
                    funcionario_id=func_data["funcionario_id"],
                    horas_trabalhadas=float(func_data.get("horas", 0)),
                    funcao_exercida=func_data.get("funcao_exercida", ""),
                    presente=func_data.get("presente", True)
                )
                db.session.add(rdo_mao_obra)
        
        # Salvar atividades
        for ativ_data in dados.get("atividades", []):
            if ativ_data.get("servico_id"):
                rdo_atividade = RDOAtividade(
                    rdo_id=rdo.id,
                    servico_id=ativ_data["servico_id"],
                    quantidade=float(ativ_data.get("quantidade", 0)),
                    tempo_execucao=float(ativ_data.get("tempo", 0)),
                    observacoes=ativ_data.get("observacoes", "")
                )
                db.session.add(rdo_atividade)
        
        # Salvar equipamentos
        for equip_data in dados.get("equipamentos", []):
            if equip_data.get("equipamento_id"):
                rdo_equipamento = RDOEquipamento(
                    rdo_id=rdo.id,
                    veiculo_id=equip_data["equipamento_id"],
                    horas_uso=float(equip_data.get("horas_uso", 0)),
                    status=equip_data.get("status", "operando"),
                    observacoes=equip_data.get("observacoes", "")
                )
                db.session.add(rdo_equipamento)
        
        # Salvar ocorrências
        for ocorr_data in dados.get("ocorrencias", []):
            if ocorr_data.get("tipo") and ocorr_data.get("descricao"):
                rdo_ocorrencia = RDOOcorrencia(
                    rdo_id=rdo.id,
                    tipo=ocorr_data["tipo"],
                    gravidade=ocorr_data.get("gravidade", "media"),
                    descricao=ocorr_data["descricao"]
                )
                db.session.add(rdo_ocorrencia)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "RDO finalizado com sucesso",
            "rdo_id": rdo.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Erro ao finalizar RDO: {str(e)}"
        }), 500

# API para carregar serviços de uma obra específica
@main_bp.route('/api/obras/<int:obra_id>/servicos')
@login_required
def api_servicos_obra(obra_id):
    """API para carregar serviços associados a uma obra"""
    try:
        servicos_obra = db.session.query(
            Servico.id,
            Servico.nome,
            Servico.categoria,
            Servico.unidade_medida,
            ServicoObra.quantidade_planejada,
            ServicoObra.observacoes
        ).join(
            ServicoObra, Servico.id == ServicoObra.servico_id
        ).filter(
            ServicoObra.obra_id == obra_id,
            Servico.ativo == True
        ).order_by(Servico.nome).all()
        
        servicos_data = []
        for servico in servicos_obra:
            servicos_data.append({
                'id': servico.id,
                'nome': servico.nome,
                'categoria': servico.categoria,
                'unidade_medida': servico.unidade_medida,
                'unidade_simbolo': get_simbolo_unidade(servico.unidade_medida),
                'quantidade_planejada': float(servico.quantidade_planejada) if servico.quantidade_planejada else 0,
                'observacoes': servico.observacoes
            })
        
        return jsonify({
            'success': True,
            'servicos': servicos_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API para buscar último RDO de uma obra
@main_bp.route('/api/obras/<int:obra_id>/ultimo-rdo')
@login_required
def api_ultimo_rdo_obra(obra_id):
    """API para buscar o último RDO de uma obra para pré-popular valores"""
    try:
        # Buscar o RDO mais recente desta obra
        ultimo_rdo = RDO.query.filter_by(
            obra_id=obra_id
        ).order_by(RDO.data.desc()).first()
        
        if not ultimo_rdo:
            return jsonify({
                'success': False,
                'message': 'Nenhum RDO anterior encontrado'
            })
        
        # Extrair atividades do JSON armazenado
        atividades = {}
        if ultimo_rdo.dados_atividades:
            try:
                atividades_json = json.loads(ultimo_rdo.dados_atividades)
                for atividade in atividades_json:
                    if atividade.get('servico_id'):
                        atividades[str(atividade['servico_id'])] = {
                            'quantidade': atividade.get('quantidade', 0),
                            'percentual': atividade.get('percentual', 0),
                            'observacoes': atividade.get('observacoes', ''),
                            'tempo': atividade.get('tempo', 0)
                        }
            except json.JSONDecodeError:
                pass
        
        return jsonify({
            'success': True,
            'rdo_id': ultimo_rdo.id,
            'data_relatorio': ultimo_rdo.data_relatorio.isoformat(),
            'atividades': atividades
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500







# ================================
# MÓDULO 2: PORTAL DO CLIENTE
# ================================

@main_bp.route("/cliente/obra/<token>")
def cliente_obra_dashboard(token):
    """Portal do cliente para acompanhar progresso da obra"""
    try:
        obra = Obra.query.filter_by(token_cliente=token).first()
        if not obra:
            return "Token inválido", 404
        
        rdos = RDO.query.filter_by(obra_id=obra.id).count()
        progresso = min(100, (rdos * 10))
        
        return f"""
        <h1>Obra: {obra.nome}</h1>
        <p>Endereço: {obra.endereco}</p>
        <p>Progresso: {progresso}%</p>
        <p>RDOs executados: {rdos}</p>
        """
    except Exception as e:
        return f"Erro: {str(e)}", 500

@main_bp.route("/cliente/proposta/<token>/aprovar", methods=["POST"])
def cliente_aprovar_proposta_v2(token):
    """Cliente aprova proposta e gera obra"""
    try:
        proposta = PropostaComercial.query.filter_by(token_acesso=token).first()
        if not proposta:
            return jsonify({"success": False, "message": "Proposta não encontrada"}), 404
        
        proposta.status = StatusProposta.APROVADA
        
        import secrets
        obra_codigo = f"OBR-{datetime.now().year}-{Obra.query.count() + 1:03d}"
        cliente_token = secrets.token_urlsafe(16)
        
        nova_obra = Obra(
            nome=f"Obra - {proposta.titulo_projeto}",
            codigo=obra_codigo,
            endereco=proposta.endereco_execucao or "Não informado",
            data_inicio=datetime.now().date(),
            orcamento=proposta.valor_total,
            valor_contrato=proposta.valor_total,
            status="Planejamento",
            cliente_nome=proposta.cliente_nome,
            token_cliente=cliente_token,
            proposta_origem_id=proposta.id,
            admin_id=proposta.admin_id
        )
        
        db.session.add(nova_obra)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Obra {obra_codigo} criada!",
            "cliente_token": cliente_token
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# ================================
# MÓDULO 3: GESTÃO DE EQUIPES
# ================================

@main_bp.route("/equipes")
@login_required
@admin_required
def gestao_equipes():
    """Interface para gestão de equipes"""
    try:
        funcionarios = Funcionario.query.filter_by(
            ativo=True,
            admin_id=current_user.id
        ).all()
        
        obras = Obra.query.filter_by(
            ativo=True,
            admin_id=current_user.id
        ).all()
        
        alocacoes = AlocacaoEquipe.query.filter_by(
            admin_id=current_user.id
        ).order_by(AlocacaoEquipe.data_alocacao.desc()).limit(20).all()
        
        return render_template("equipes/gestao_equipes.html",
                             funcionarios=funcionarios,
                             obras=obras,
                             alocacoes=alocacoes)
        
    except Exception as e:
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/equipes/alocar", methods=["POST"])
@login_required
@admin_required
def alocar_funcionario():
    """Alocar funcionário em obra"""
    try:
        funcionario_id = request.form["funcionario_id"]
        obra_id = request.form["obra_id"]
        data_alocacao = datetime.strptime(request.form["data_alocacao"], "%Y-%m-%d").date()
        local_trabalho = request.form.get("local_trabalho", "campo")
        
        nova_alocacao = AlocacaoEquipe(
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            data_alocacao=data_alocacao,
            local_trabalho=local_trabalho,
            admin_id=current_user.id
        )
        
        db.session.add(nova_alocacao)
        db.session.commit()
        
        flash("Funcionário alocado com sucesso!", "success")
        return redirect(url_for("main.gestao_equipes"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for("main.gestao_equipes"))



# ================================
# MÓDULO 4: ALMOXARIFADO COMPLETO
# ================================

@main_bp.route("/materiais")
@login_required
@admin_required
def lista_materiais():
    """Lista todos os materiais do almoxarifado"""
    try:
        materiais = Material.query.filter_by(
            admin_id=current_user.id,
            ativo=True
        ).order_by(Material.descricao).all()
        
        return render_template("almoxarifado/lista_materiais.html",
                             materiais=materiais)
        
    except Exception as e:
        flash(f"Erro ao carregar materiais: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/materiais/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_material():
    """Cadastrar novo material"""
    if request.method == "POST":
        try:
            novo_material = Material(
                descricao=request.form["descricao"],
                categoria=request.form["categoria"],
                unidade_medida=request.form["unidade_medida"],
                estoque_minimo=float(request.form.get("estoque_minimo", 0)),
                localizacao=request.form.get("localizacao", ""),
                codigo_barras=request.form.get("codigo_barras", ""),
                admin_id=current_user.id
            )
            
            db.session.add(novo_material)
            db.session.commit()
            
            flash("Material cadastrado com sucesso!", "success")
            return redirect(url_for("main.lista_materiais"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar material: {str(e)}", "danger")
    
    return render_template("almoxarifado/material_form.html")

@main_bp.route("/movimentacoes-material")
@login_required
@admin_required
def movimentacoes_material():
    """Lista movimentações de materiais"""
    try:
        movimentacoes = MovimentacaoMaterial.query.filter_by(
            admin_id=current_user.id
        ).order_by(MovimentacaoMaterial.created_at.desc()).limit(50).all()
        
        return render_template("almoxarifado/movimentacoes.html",
                             movimentacoes=movimentacoes)
        
    except Exception as e:
        flash(f"Erro ao carregar movimentações: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/movimentacoes-material/nova", methods=["POST"])
@login_required
@admin_required
def nova_movimentacao():
    """Registrar nova movimentação de material"""
    try:
        nova_mov = MovimentacaoMaterial(
            material_id=request.form["material_id"],
            tipo_movimento=request.form["tipo_movimento"],
            quantidade=float(request.form["quantidade"]),
            valor_unitario=float(request.form.get("valor_unitario", 0)),
            data_movimento=datetime.strptime(request.form["data_movimento"], "%Y-%m-%d").date(),
            observacoes=request.form.get("observacoes", ""),
            admin_id=current_user.id
        )
        
        # Calcular valor total
        nova_mov.valor_total = nova_mov.quantidade * nova_mov.valor_unitario
        
        # Atualizar estoque do material
        material = Material.query.get(nova_mov.material_id)
        if nova_mov.tipo_movimento == "entrada":
            material.estoque_atual += nova_mov.quantidade
        elif nova_mov.tipo_movimento == "saida":
            material.estoque_atual -= nova_mov.quantidade
        
        db.session.add(nova_mov)
        db.session.commit()
        
        flash("Movimentação registrada com sucesso!", "success")
        return redirect(url_for("main.movimentacoes_material"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao registrar movimentação: {str(e)}", "danger")
        return redirect(url_for("main.movimentacoes_material"))

