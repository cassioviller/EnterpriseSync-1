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
