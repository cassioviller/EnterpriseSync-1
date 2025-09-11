"""
EQUIPE VIEWS - SISTEMA SIMPLIFICADO
===================================
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from auth import admin_required
from datetime import datetime, date, timedelta, time
from app import db
from models import Allocation, AllocationEmployee, Funcionario, Obra, Servico, Usuario, TipoUsuario
import logging

equipe_bp = Blueprint('equipe', __name__, url_prefix='/equipe')

def get_admin_id():
    """Admin ID dinâmico"""
    if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return 10

def get_monday_of_week(target_date):
    """Retorna segunda-feira da semana"""
    days_since_monday = target_date.weekday()
    monday = target_date - timedelta(days=days_since_monday)
    return monday

@equipe_bp.route('/')
@equipe_bp.route('/alocacao')
@login_required
@admin_required
def alocacao_semanal():
    """Tela principal - Grid semanal"""
    try:
        admin_id = get_admin_id()
        
        # Semana atual
        today = date.today()
        week_param = request.args.get('week')
        if week_param:
            try:
                today = datetime.strptime(week_param, '%Y-%m-%d').date()
            except:
                pass
        
        monday = get_monday_of_week(today)
        friday = monday + timedelta(days=4)
        
        # Datas da semana
        week_dates = [monday + timedelta(days=i) for i in range(5)]
        
        # Obras ativas
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.codigo).all()
        
        # Alocações da semana
        allocations = Allocation.query.filter(
            Allocation.admin_id == admin_id,
            Allocation.data_alocacao.between(monday, friday)
        ).all()
        
        # Organizar por data
        week_grid = {}
        for allocation in allocations:
            date_key = allocation.data_alocacao.strftime('%Y-%m-%d')
            if date_key not in week_grid:
                week_grid[date_key] = []
            week_grid[date_key].append(allocation)
        
        # Estatísticas
        stats = {
            'total_obras': len(obras),
            'total_alocacoes_semana': len(allocations),
            'funcionarios_alocados': len(set(ae.funcionario_id for a in allocations 
                                           for ae in a.funcionarios_alocados if hasattr(a, 'funcionarios_alocados')))
        }
        
        logging.info(f"EQUIPE: Carregada semana {monday} - {len(allocations)} alocações")
        
        return render_template('equipe/alocacao_semanal.html',
                             obras=obras,
                             week_grid=week_grid,
                             monday=monday,
                             friday=friday,
                             week_dates=week_dates,
                             stats=stats)
        
    except Exception as e:
        logging.error(f"EQUIPE ERROR: {str(e)}")
        flash('Erro ao carregar gestão de equipe', 'error')
        return redirect(url_for('dashboard'))

@equipe_bp.route('/funcionarios/<int:allocation_id>')
@login_required
@admin_required
def allocation_funcionarios(allocation_id):
    """Drill-down funcionários"""
    try:
        admin_id = get_admin_id()
        
        # Buscar alocação
        allocation = Allocation.query.filter_by(id=allocation_id, admin_id=admin_id).first()
        if not allocation:
            flash('Alocação não encontrada', 'error')
            return redirect(url_for('equipe.alocacao_semanal'))
        
        # Funcionários disponíveis
        funcionarios_disponiveis = Funcionario.query.filter_by(
            admin_id=admin_id, 
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Funcionários já alocados
        funcionarios_alocados = []
        if hasattr(allocation, 'funcionarios_alocados'):
            funcionarios_alocados = allocation.funcionarios_alocados
        
        return render_template('equipe/allocation_funcionarios.html',
                             allocation=allocation,
                             funcionarios_disponiveis=funcionarios_disponiveis,
                             funcionarios_alocados=funcionarios_alocados)
        
    except Exception as e:
        logging.error(f"FUNCIONARIOS ERROR: {str(e)}")
        flash('Erro ao carregar funcionários', 'error')
        return redirect(url_for('equipe.alocacao_semanal'))

@equipe_bp.route('/api/allocations', methods=['POST'])
@login_required
@admin_required
def api_create_allocation():
    """API: Criar alocação"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        if not data or not data.get('obra_id') or not data.get('data_alocacao'):
            return jsonify({'error': 'Dados obrigatórios'}), 400
        
        # Verificar obra
        obra = Obra.query.filter_by(id=data['obra_id'], admin_id=admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        # Parse data
        data_alocacao = datetime.strptime(data['data_alocacao'], '%Y-%m-%d').date()
        
        # Criar alocação
        allocation = Allocation()
        allocation.admin_id = admin_id
        allocation.obra_id = data['obra_id']
        allocation.data_alocacao = data_alocacao
        allocation.turno_inicio = time(8, 0)
        allocation.turno_fim = time(17, 0)
        allocation.nota = data.get('nota', '')
        
        db.session.add(allocation)
        db.session.commit()
        
        return jsonify({
            'id': allocation.id,
            'message': 'Alocação criada'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API CREATE ERROR: {str(e)}")
        return jsonify({'error': 'Erro interno'}), 500

@equipe_bp.route('/api/allocations/<int:allocation_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_allocation(allocation_id):
    """API: Deletar alocação"""
    try:
        admin_id = get_admin_id()
        
        allocation = Allocation.query.filter_by(id=allocation_id, admin_id=admin_id).first()
        if not allocation:
            return jsonify({'error': 'Não encontrada'}), 404
        
        db.session.delete(allocation)
        db.session.commit()
        
        return jsonify({'message': 'Removida'})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API DELETE ERROR: {str(e)}")
        return jsonify({'error': 'Erro interno'}), 500