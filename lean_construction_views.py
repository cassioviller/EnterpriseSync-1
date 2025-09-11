# LEAN CONSTRUCTION VIEWS - SIGE v10.0 
# Módulo de Gestão de Equipe baseado em Last Planner System

import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import db, LeanTask, WeeklyPlan, DailyHuddle, Constraint, TaskDependency, PPCMetric, VariationAnalysis, DailyCommitment, Obra, Funcionario, Usuario
from multitenant_helper import get_admin_id
import json
from sqlalchemy import func, desc, asc

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprint para módulo Lean Construction
lean_bp = Blueprint('lean', __name__, url_prefix='/equipe')

# ===== VIEWS PRINCIPAIS =====

@lean_bp.route('/')
@login_required
def dashboard():
    """Dashboard principal do módulo Lean Construction"""
    try:
        admin_id = get_admin_id()
        
        # Buscar obras ativas
        obras = Obra.query.filter_by(admin_id=admin_id, status='Em andamento').all()
        
        # KPIs gerais
        total_tasks = LeanTask.query.filter_by(admin_id=admin_id).count()
        tasks_concluidas = LeanTask.query.filter_by(admin_id=admin_id, status='Concluído').count()
        constraints_ativas = Constraint.query.filter_by(admin_id=admin_id, status='Identificada').count()
        
        # PPC médio das últimas 4 semanas
        data_limite = date.today() - timedelta(days=28)
        ppc_medio = db.session.query(func.avg(PPCMetric.ppc_percentage)).filter(
            PPCMetric.admin_id == admin_id,
            PPCMetric.semana_inicio >= data_limite
        ).scalar() or 0
        
        # Dados para gráficos
        # Trend PPC últimas 8 semanas
        data_inicio = date.today() - timedelta(days=56)
        ppc_trend = PPCMetric.query.filter(
            PPCMetric.admin_id == admin_id,
            PPCMetric.semana_inicio >= data_inicio
        ).order_by(PPCMetric.semana_inicio).all()
        
        # Top 5 tipos de restrições
        constraint_stats = db.session.query(
            Constraint.tipo,
            func.count(Constraint.id).label('count')
        ).filter(
            Constraint.admin_id == admin_id,
            Constraint.status != 'Resolvida'
        ).group_by(Constraint.tipo).order_by(desc('count')).limit(5).all()
        
        return render_template('lean/dashboard.html',
                               obras=obras,
                               total_tasks=total_tasks,
                               tasks_concluidas=tasks_concluidas,
                               constraints_ativas=constraints_ativas,
                               ppc_medio=round(ppc_medio, 1),
                               ppc_trend=ppc_trend,
                               constraint_stats=constraint_stats)
    except Exception as e:
        logger.error(f"Erro no dashboard Lean: {str(e)}")
        flash('Erro ao carregar dashboard. Tente novamente.', 'error')
        return redirect(url_for('main.dashboard'))

@lean_bp.route('/kanban')
@login_required
def kanban():
    """Quadro Kanban interativo"""
    try:
        admin_id = get_admin_id()
        obra_id = request.args.get('obra_id', type=int)
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id, status='Em andamento').all()
        
        # Se nenhuma obra especificada, pegar a primeira
        if not obra_id and obras:
            obra_id = obras[0].id
        
        # Buscar tarefas da obra
        tasks = []
        if obra_id:
            tasks = LeanTask.query.filter_by(
                admin_id=admin_id,
                obra_id=obra_id
            ).order_by(LeanTask.prioridade.desc(), LeanTask.created_at).all()
        
        # Agrupar tarefas por status
        tasks_by_status = {
            'A Fazer': [t for t in tasks if t.status == 'A Fazer'],
            'Em Andamento': [t for t in tasks if t.status == 'Em Andamento'],
            'Concluído': [t for t in tasks if t.status == 'Concluído'],
            'Impedimento': [t for t in tasks if t.status == 'Impedimento']
        }
        
        return render_template('lean/kanban.html',
                               obras=obras,
                               obra_selecionada=obra_id,
                               tasks_by_status=tasks_by_status)
    except Exception as e:
        logger.error(f"Erro no Kanban: {str(e)}")
        flash('Erro ao carregar Kanban. Tente novamente.', 'error')
        return redirect(url_for('lean.dashboard'))

@lean_bp.route('/daily-huddle')
@login_required
def daily_huddle():
    """Interface para Daily Huddles"""
    try:
        admin_id = get_admin_id()
        obra_id = request.args.get('obra_id', type=int)
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id, status='Em andamento').all()
        
        # Se nenhuma obra especificada, pegar a primeira
        if not obra_id and obras:
            obra_id = obras[0].id
        
        # Huddle de hoje
        hoje = date.today()
        huddle_hoje = DailyHuddle.query.filter_by(
            admin_id=admin_id,
            obra_id=obra_id,
            data_reuniao=hoje
        ).first()
        
        # Funcionários da obra (através de tarefas ativas)
        funcionarios_obra = db.session.query(Funcionario).join(
            LeanTask, Funcionario.id == LeanTask.responsavel_id
        ).filter(
            LeanTask.admin_id == admin_id,
            LeanTask.obra_id == obra_id,
            LeanTask.status.in_(['A Fazer', 'Em Andamento'])
        ).distinct().all()
        
        # Tarefas do dia
        tasks_hoje = LeanTask.query.filter(
            LeanTask.admin_id == admin_id,
            LeanTask.obra_id == obra_id,
            LeanTask.data_planejada == hoje
        ).all()
        
        # Impedimentos ativos
        impedimentos = Constraint.query.filter(
            Constraint.admin_id == admin_id,
            Constraint.obra_id == obra_id,
            Constraint.status.in_(['Identificada', 'Em Resolução'])
        ).order_by(Constraint.severidade.desc()).all()
        
        return render_template('lean/daily_huddle.html',
                               obras=obras,
                               obra_selecionada=obra_id,
                               huddle_hoje=huddle_hoje,
                               funcionarios_obra=funcionarios_obra,
                               tasks_hoje=tasks_hoje,
                               impedimentos=impedimentos)
    except Exception as e:
        logger.error(f"Erro no Daily Huddle: {str(e)}")
        flash('Erro ao carregar Daily Huddle. Tente novamente.', 'error')
        return redirect(url_for('lean.dashboard'))

@lean_bp.route('/weekly-planning')
@login_required
def weekly_planning():
    """Planejamento semanal colaborativo"""
    try:
        admin_id = get_admin_id()
        obra_id = request.args.get('obra_id', type=int)
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id, status='Em andamento').all()
        
        # Se nenhuma obra especificada, pegar a primeira
        if not obra_id and obras:
            obra_id = obras[0].id
        
        # Plano da semana atual
        hoje = date.today()
        inicio_semana = hoje - timedelta(days=hoje.weekday())  # Segunda-feira
        fim_semana = inicio_semana + timedelta(days=6)  # Domingo
        
        plano_atual = WeeklyPlan.query.filter(
            WeeklyPlan.admin_id == admin_id,
            WeeklyPlan.obra_id == obra_id,
            WeeklyPlan.semana_inicio == inicio_semana
        ).first()
        
        # Tarefas da semana
        tasks_semana = LeanTask.query.filter(
            LeanTask.admin_id == admin_id,
            LeanTask.obra_id == obra_id,
            LeanTask.data_planejada.between(inicio_semana, fim_semana)
        ).order_by(LeanTask.data_planejada, LeanTask.prioridade.desc()).all()
        
        # Próximas semanas (4 semanas à frente)
        proximas_semanas = []
        for i in range(1, 5):
            semana_inicio = inicio_semana + timedelta(weeks=i)
            semana_fim = semana_inicio + timedelta(days=6)
            proximas_semanas.append({
                'inicio': semana_inicio,
                'fim': semana_fim,
                'tasks': LeanTask.query.filter(
                    LeanTask.admin_id == admin_id,
                    LeanTask.obra_id == obra_id,
                    LeanTask.data_planejada.between(semana_inicio, semana_fim)
                ).count()
            })
        
        return render_template('lean/weekly_planning.html',
                               obras=obras,
                               obra_selecionada=obra_id,
                               plano_atual=plano_atual,
                               semana_atual={'inicio': inicio_semana, 'fim': fim_semana},
                               tasks_semana=tasks_semana,
                               proximas_semanas=proximas_semanas)
    except Exception as e:
        logger.error(f"Erro no Weekly Planning: {str(e)}")
        flash('Erro ao carregar Weekly Planning. Tente novamente.', 'error')
        return redirect(url_for('lean.dashboard'))

@lean_bp.route('/constraints')
@login_required
def constraints():
    """Gestão de restrições e impedimentos"""
    try:
        admin_id = get_admin_id()
        obra_id = request.args.get('obra_id', type=int)
        status = request.args.get('status', 'Identificada')
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id, status='Em andamento').all()
        
        # Filtros
        query = Constraint.query.filter_by(admin_id=admin_id)
        
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        
        if status and status != 'Todos':
            query = query.filter_by(status=status)
        
        constraints = query.order_by(
            Constraint.severidade.desc(),
            Constraint.data_identificacao.desc()
        ).all()
        
        # Estatísticas
        stats = {
            'total': Constraint.query.filter_by(admin_id=admin_id).count(),
            'identificadas': Constraint.query.filter_by(admin_id=admin_id, status='Identificada').count(),
            'em_resolucao': Constraint.query.filter_by(admin_id=admin_id, status='Em Resolução').count(),
            'resolvidas': Constraint.query.filter_by(admin_id=admin_id, status='Resolvida').count()
        }
        
        return render_template('lean/constraints.html',
                               obras=obras,
                               obra_selecionada=obra_id,
                               status_selecionado=status,
                               constraints=constraints,
                               stats=stats)
    except Exception as e:
        logger.error(f"Erro na gestão de restrições: {str(e)}")
        flash('Erro ao carregar gestão de restrições. Tente novamente.', 'error')
        return redirect(url_for('lean.dashboard'))

@lean_bp.route('/metrics')
@login_required
def metrics():
    """Dashboard de métricas e análise PPC"""
    try:
        admin_id = get_admin_id()
        obra_id = request.args.get('obra_id', type=int)
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id, status='Em andamento').all()
        
        # Métricas últimas 12 semanas
        data_inicio = date.today() - timedelta(days=84)  # 12 semanas
        
        query_metrics = PPCMetric.query.filter(
            PPCMetric.admin_id == admin_id,
            PPCMetric.semana_inicio >= data_inicio
        )
        
        if obra_id:
            query_metrics = query_metrics.filter_by(obra_id=obra_id)
        
        metrics_historicas = query_metrics.order_by(PPCMetric.semana_inicio).all()
        
        # Análise de variação últimas 4 semanas
        data_variacao = date.today() - timedelta(days=28)
        variacoes = VariationAnalysis.query.filter(
            VariationAnalysis.admin_id == admin_id,
            VariationAnalysis.created_at >= datetime.combine(data_variacao, datetime.min.time())
        )
        
        if obra_id:
            variacoes = variacoes.filter_by(obra_id=obra_id)
        
        variacoes = variacoes.all()
        
        # Estatísticas por categoria de falha
        categoria_stats = db.session.query(
            VariationAnalysis.failure_category,
            func.count(VariationAnalysis.id).label('count')
        ).filter(
            VariationAnalysis.admin_id == admin_id,
            VariationAnalysis.created_at >= datetime.combine(data_variacao, datetime.min.time())
        )
        
        if obra_id:
            categoria_stats = categoria_stats.filter_by(obra_id=obra_id)
        
        categoria_stats = categoria_stats.group_by(
            VariationAnalysis.failure_category
        ).order_by(desc('count')).all()
        
        # PPC médio geral
        ppc_medio = 0
        if metrics_historicas:
            ppc_medio = sum(m.ppc_percentage for m in metrics_historicas) / len(metrics_historicas)
        
        return render_template('lean/metrics.html',
                               obras=obras,
                               obra_selecionada=obra_id,
                               metrics_historicas=metrics_historicas,
                               variacoes=variacoes,
                               categoria_stats=categoria_stats,
                               ppc_medio=round(ppc_medio, 1))
    except Exception as e:
        logger.error(f"Erro nas métricas: {str(e)}")
        flash('Erro ao carregar métricas. Tente novamente.', 'error')
        return redirect(url_for('lean.dashboard'))

# ===== APIs RESTful =====

@lean_bp.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def api_tasks():
    """API para gestão de tarefas Lean"""
    admin_id = get_admin_id()
    
    if request.method == 'GET':
        obra_id = request.args.get('obra_id', type=int)
        status = request.args.get('status')
        
        query = LeanTask.query.filter_by(admin_id=admin_id)
        
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if status:
            query = query.filter_by(status=status)
        
        tasks = query.order_by(LeanTask.prioridade.desc(), LeanTask.created_at).all()
        
        return jsonify([{
            'id': task.id,
            'titulo': task.titulo,
            'descricao': task.descricao,
            'status': task.status,
            'prioridade': task.prioridade,
            'obra_id': task.obra_id,
            'obra_nome': task.obra.nome if task.obra else '',
            'responsavel_id': task.responsavel_id,
            'responsavel_nome': task.responsavel.nome if task.responsavel else '',
            'responsavel_foto': task.responsavel.foto if task.responsavel and task.responsavel.foto else '/static/images/default-avatar.png',
            'data_planejada': task.data_planejada.isoformat() if task.data_planejada else None,
            'data_conclusao_real': task.data_conclusao_real.isoformat() if task.data_conclusao_real else None,
            'percentual_conclusao': task.percentual_conclusao,
            'horas_estimadas': task.horas_estimadas,
            'horas_reais': task.horas_reais,
            'checklist': task.checklist or [],
            'comentarios': task.comentarios,
            'created_at': task.created_at.isoformat()
        } for task in tasks])
    
    elif request.method == 'POST':
        data = request.get_json()
        
        try:
            task = LeanTask(
                titulo=data['titulo'],
                descricao=data.get('descricao', ''),
                status=data.get('status', 'A Fazer'),
                prioridade=data.get('prioridade', 3),
                obra_id=data['obra_id'],
                responsavel_id=data['responsavel_id'],
                criado_por_id=current_user.id,
                admin_id=admin_id,
                data_planejada=datetime.strptime(data['data_planejada'], '%Y-%m-%d').date(),
                horas_estimadas=data.get('horas_estimadas', 8.0),
                percentual_conclusao=data.get('percentual_conclusao', 0.0),
                checklist=data.get('checklist', []),
                comentarios=data.get('comentarios', '')
            )
            
            db.session.add(task)
            db.session.commit()
            
            return jsonify({'message': 'Tarefa criada com sucesso!', 'id': task.id}), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar tarefa: {str(e)}")
            return jsonify({'error': 'Erro ao criar tarefa'}), 500

@lean_bp.route('/api/tasks/<int:task_id>/status', methods=['PUT'])
@login_required
def api_update_task_status(task_id):
    """API para atualizar status de tarefa (drag & drop)"""
    admin_id = get_admin_id()
    
    try:
        task = LeanTask.query.filter_by(id=task_id, admin_id=admin_id).first()
        if not task:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['A Fazer', 'Em Andamento', 'Concluído', 'Impedimento']:
            return jsonify({'error': 'Status inválido'}), 400
        
        task.status = new_status
        task.updated_at = datetime.utcnow()
        
        # Se concluída, marcar data de conclusão
        if new_status == 'Concluído':
            task.data_conclusao_real = date.today()
            task.percentual_conclusao = 100.0
        elif new_status == 'Em Andamento' and task.percentual_conclusao == 0:
            task.percentual_conclusao = 10.0  # Iniciada
        
        db.session.commit()
        
        return jsonify({'message': 'Status atualizado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar status da tarefa: {str(e)}")
        return jsonify({'error': 'Erro ao atualizar status'}), 500

@lean_bp.route('/api/daily-huddle', methods=['POST'])
@login_required
def api_create_daily_huddle():
    """API para criar/atualizar Daily Huddle"""
    admin_id = get_admin_id()
    
    try:
        data = request.get_json()
        
        # Verificar se já existe huddle hoje
        hoje = date.today()
        huddle = DailyHuddle.query.filter_by(
            admin_id=admin_id,
            obra_id=data['obra_id'],
            data_reuniao=hoje
        ).first()
        
        if not huddle:
            huddle = DailyHuddle(
                obra_id=data['obra_id'],
                admin_id=admin_id,
                data_reuniao=hoje,
                facilitador_id=data['facilitador_id'],
                duracao_minutos=data.get('duracao_minutos', 15)
            )
            db.session.add(huddle)
        
        # Atualizar dados da reunião
        huddle.compromissos = data.get('compromissos', [])
        huddle.impedimentos = data.get('impedimentos', [])
        huddle.acoes_definidas = data.get('acoes_definidas', [])
        huddle.participantes = data.get('participantes', [])
        huddle.observacoes = data.get('observacoes', '')
        
        db.session.commit()
        
        return jsonify({'message': 'Daily Huddle salvo com sucesso!', 'id': huddle.id})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar Daily Huddle: {str(e)}")
        return jsonify({'error': 'Erro ao salvar Daily Huddle'}), 500

@lean_bp.route('/api/constraints', methods=['GET', 'POST'])
@login_required
def api_constraints():
    """API para gestão de restrições"""
    admin_id = get_admin_id()
    
    if request.method == 'GET':
        obra_id = request.args.get('obra_id', type=int)
        status = request.args.get('status')
        
        query = Constraint.query.filter_by(admin_id=admin_id)
        
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if status:
            query = query.filter_by(status=status)
        
        constraints = query.order_by(Constraint.severidade.desc(), Constraint.data_identificacao.desc()).all()
        
        return jsonify([{
            'id': constraint.id,
            'titulo': constraint.titulo,
            'descricao': constraint.descricao,
            'tipo': constraint.tipo,
            'severidade': constraint.severidade,
            'status': constraint.status,
            'obra_id': constraint.obra_id,
            'obra_nome': constraint.obra.nome if constraint.obra else '',
            'responsavel_nome': constraint.responsavel.nome if constraint.responsavel else '',
            'data_identificacao': constraint.data_identificacao.isoformat(),
            'prazo_resolucao': constraint.prazo_resolucao.isoformat() if constraint.prazo_resolucao else None,
            'impacto_dias': constraint.impacto_dias,
            'custo_estimado': constraint.custo_estimado
        } for constraint in constraints])
    
    elif request.method == 'POST':
        data = request.get_json()
        
        try:
            constraint = Constraint(
                titulo=data['titulo'],
                descricao=data['descricao'],
                tipo=data['tipo'],
                severidade=data.get('severidade', 'Media'),
                obra_id=data['obra_id'],
                responsavel_resolucao_id=data['responsavel_resolucao_id'],
                criado_por_id=current_user.id,
                admin_id=admin_id,
                prazo_resolucao=datetime.strptime(data['prazo_resolucao'], '%Y-%m-%d').date() if data.get('prazo_resolucao') else None,
                impacto_dias=data.get('impacto_dias', 0),
                custo_estimado=data.get('custo_estimado', 0.0),
                acoes_propostas=data.get('acoes_propostas', '')
            )
            
            db.session.add(constraint)
            db.session.commit()
            
            return jsonify({'message': 'Restrição criada com sucesso!', 'id': constraint.id}), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar restrição: {str(e)}")
            return jsonify({'error': 'Erro ao criar restrição'}), 500

@lean_bp.route('/api/ppc/calculate/<int:obra_id>')
@login_required 
def api_calculate_ppc(obra_id):
    """API para calcular PPC de uma obra"""
    admin_id = get_admin_id()
    
    try:
        # Semana atual
        hoje = date.today()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        fim_semana = inicio_semana + timedelta(days=6)
        
        # Tarefas planejadas para a semana
        tasks_planejadas = LeanTask.query.filter(
            LeanTask.admin_id == admin_id,
            LeanTask.obra_id == obra_id,
            LeanTask.data_planejada.between(inicio_semana, fim_semana)
        ).all()
        
        # Calcular PPC
        total_planejadas = len(tasks_planejadas)
        total_concluidas = sum(1 for task in tasks_planejadas if task.status == 'Concluído')
        
        ppc_percentage = (total_concluidas / total_planejadas * 100) if total_planejadas > 0 else 0
        
        # Salvar métrica
        metric = PPCMetric.query.filter(
            PPCMetric.admin_id == admin_id,
            PPCMetric.obra_id == obra_id,
            PPCMetric.semana_inicio == inicio_semana
        ).first()
        
        if not metric:
            metric = PPCMetric(
                obra_id=obra_id,
                admin_id=admin_id,
                semana_inicio=inicio_semana,
                semana_fim=fim_semana
            )
            db.session.add(metric)
        
        metric.ppc_percentage = ppc_percentage
        metric.tasks_planned = total_planejadas
        metric.tasks_completed = total_concluidas
        metric.tasks_partial = sum(1 for task in tasks_planejadas if task.status == 'Em Andamento')
        metric.tasks_not_started = sum(1 for task in tasks_planejadas if task.status == 'A Fazer')
        metric.calculation_date = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'ppc_percentage': round(ppc_percentage, 1),
            'tasks_planned': total_planejadas,
            'tasks_completed': total_concluidas,
            'semana': f"{inicio_semana.strftime('%d/%m')} - {fim_semana.strftime('%d/%m')}"
        })
        
    except Exception as e:
        logger.error(f"Erro ao calcular PPC: {str(e)}")
        return jsonify({'error': 'Erro ao calcular PPC'}), 500

@lean_bp.route('/api/funcionarios/<int:obra_id>')
@login_required
def api_funcionarios_obra(obra_id):
    """API para buscar funcionários de uma obra"""
    admin_id = get_admin_id()
    
    try:
        # Funcionários que têm tarefas na obra
        funcionarios = db.session.query(Funcionario).join(
            LeanTask, Funcionario.id == LeanTask.responsavel_id
        ).filter(
            LeanTask.admin_id == admin_id,
            LeanTask.obra_id == obra_id
        ).distinct().all()
        
        return jsonify([{
            'id': funcionario.id,
            'nome': funcionario.nome,
            'codigo': funcionario.codigo,
            'foto': funcionario.foto if funcionario.foto else '/static/images/default-avatar.png',
            'funcao': funcionario.funcao_ref.nome if funcionario.funcao_ref else 'Não definida'
        } for funcionario in funcionarios])
        
    except Exception as e:
        logger.error(f"Erro ao buscar funcionários da obra: {str(e)}")
        return jsonify({'error': 'Erro ao buscar funcionários'}), 500

# ===== ERROR HANDLERS =====

@lean_bp.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@lean_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500