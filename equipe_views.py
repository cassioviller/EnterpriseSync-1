"""
EQUIPE VIEWS - SISTEMA LEAN PARA CANTEIRO DE OBRA
==================================================

FILOSOFIA: Interfaces que funcionam com tablet sujo e luvas.
- Zero gordura
- Drag & drop intuitivo  
- Mobile-first
- Performance crítica

Estrutura:
- Tela A: Alocação Obras→Dias (grade semanal)
- Tela B: Drill-down Pessoas→Obra (modal/página)
- APIs: REST simples e rápidas
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from auth import admin_required
from datetime import datetime, date, timedelta, time
from sqlalchemy import func, and_, or_
from app import db
from models import (
    Allocation, AllocationEmployee, WeeklyPlan, WeeklyPlanItem,
    Funcionario, Obra, Servico, Usuario, TipoUsuario
)
import json
import logging

# Blueprint enxuto
equipe_bp = Blueprint('equipe', __name__, url_prefix='/equipe')

def get_admin_id():
    """Admin ID dinâmico - compatível com sistema existente"""
    if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return 10  # Fallback desenvolvimento

def get_monday_of_week(target_date):
    """Retorna segunda-feira da semana da data informada"""
    days_since_monday = target_date.weekday()
    monday = target_date - timedelta(days=days_since_monday)
    return monday

def safe_db_operation(operation, default_value=None, error_message="Erro na operação"):
    """Executa operação DB com tratamento seguro - vital para estabilidade"""
    try:
        return operation()
    except Exception as e:
        logging.error(f"EQUIPE DB ERROR: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        flash(error_message, 'error')
        return default_value

# ================================
# TELA A: ALOCAÇÃO OBRAS → DIAS
# ================================

@equipe_bp.route('/')
@equipe_bp.route('/alocacao')
@login_required
@admin_required
def alocacao_semanal():
    """
    TELA A: Grade semanal drag & drop
    
    Layout otimizado:
    - Sidebar: Lista obras (cores fixas)
    - Grid: Seg-Sex com blocos de obra
    - Zero cliques desnecessários
    """
    try:
        admin_id = get_admin_id()
        
        # Data da semana (parâmetro ou atual)
        week_param = request.args.get('week')
        if week_param:
            try:
                target_date = datetime.strptime(week_param, '%Y-%m-%d').date()
            except:
                target_date = date.today()
        else:
            target_date = date.today()
        
        monday = get_monday_of_week(target_date)
        week_dates = [monday + timedelta(days=i) for i in range(5)]  # Seg-Sex
        
        # Obras ativas (fonte para drag)
        obras = safe_db_operation(
            lambda: Obra.query.filter_by(admin_id=admin_id, status='ativa').order_by(Obra.nome).all(),
            []
        )
        
        # Alocações da semana
        allocations = safe_db_operation(
            lambda: Allocation.query.filter(
                Allocation.admin_id == admin_id,
                Allocation.data_alocacao.between(monday, monday + timedelta(days=4))
            ).join(Obra).order_by(Obra.nome).all(),
            []
        )
        
        # Organizar por dia para o grid
        week_grid = {}
        for i, day_date in enumerate(week_dates):
            day_allocations = [a for a in allocations if a.data_alocacao == day_date]
            week_grid[i] = {
                'date': day_date,
                'allocations': day_allocations,
                'date_str': day_date.strftime('%d/%m')
            }
        
        # Stats rápidas (opcional)
        stats = {
            'total_obras': len(obras),
            'total_alocacoes_semana': len(allocations),
            'funcionarios_alocados': sum(a.funcionarios_count for a in allocations)
        }
        
        logging.info(f"EQUIPE: Carregada semana {monday} - {len(allocations)} alocações")
        
        # Calcular data final da semana para o template
        friday = monday + timedelta(days=4)
        
        return render_template('equipe/alocacao_semanal.html',
                             obras=obras,
                             week_grid=week_grid,
                             monday=monday,
                             friday=friday,
                             week_dates=week_dates,
                             stats=stats)
                             
    except Exception as e:
        logging.error(f"EQUIPE ALOCACAO ERROR: {str(e)}")
        flash('Erro ao carregar alocação semanal', 'error')
        return redirect(url_for('main.dashboard'))

# ================================
# TELA B: DRILL-DOWN PESSOAS → OBRA
# ================================

@equipe_bp.route('/funcionarios/<int:allocation_id>')
@login_required
@admin_required
def allocation_funcionarios(allocation_id):
    """
    TELA B: Lista funcionários para alocar em obra/dia
    
    Interface drill-down:
    - Esquerda: Funcionários disponíveis
    - Direita: Alocados nesta obra/dia
    - Drag & drop pessoas
    """
    try:
        admin_id = get_admin_id()
        
        # Buscar alocação
        allocation = safe_db_operation(
            lambda: Allocation.query.filter_by(id=allocation_id, admin_id=admin_id).first()
        )
        
        if not allocation:
            flash('Alocação não encontrada', 'error')
            return redirect(url_for('equipe.alocacao_semanal'))
        
        # Funcionários disponíveis (não alocados nesta data)
        funcionarios_disponiveis = safe_db_operation(
            lambda: db.session.query(Funcionario).filter(
                Funcionario.admin_id == admin_id,
                Funcionario.ativo == True,
                ~Funcionario.id.in_(
                    db.session.query(AllocationEmployee.funcionario_id)
                    .join(Allocation)
                    .filter(Allocation.data_alocacao == allocation.data_alocacao)
                )
            ).order_by(Funcionario.nome).all(),
            []
        )
        
        # Funcionários já alocados nesta obra/dia
        funcionarios_alocados = safe_db_operation(
            lambda: AllocationEmployee.query.filter_by(allocation_id=allocation_id)
            .join(Funcionario).order_by(Funcionario.nome).all(),
            []
        )
        
        logging.info(f"EQUIPE: Drill-down {allocation.obra.nome} - {len(funcionarios_disponiveis)} disponíveis")
        
        return render_template('equipe/allocation_funcionarios.html',
                             allocation=allocation,
                             funcionarios_disponiveis=funcionarios_disponiveis,
                             funcionarios_alocados=funcionarios_alocados)
                             
    except Exception as e:
        logging.error(f"EQUIPE FUNCIONARIOS ERROR: {str(e)}")
        flash('Erro ao carregar funcionários', 'error')
        return redirect(url_for('equipe.alocacao_semanal'))

# ================================
# APIS REST - ENXUTAS E RÁPIDAS
# ================================

@equipe_bp.route('/api/allocations', methods=['GET'])
@login_required
@admin_required
def api_get_allocations():
    """API: Buscar alocações de uma semana"""
    try:
        admin_id = get_admin_id()
        week_start = request.args.get('week_start')
        
        if not week_start:
            return jsonify({'error': 'Parâmetro week_start obrigatório'}), 400
        
        monday = datetime.strptime(week_start, '%Y-%m-%d').date()
        friday = monday + timedelta(days=4)
        
        allocations = Allocation.query.filter(
            Allocation.admin_id == admin_id,
            Allocation.data_alocacao.between(monday, friday)
        ).join(Obra).all()
        
        data = []
        for allocation in allocations:
            data.append({
                'id': allocation.id,
                'obra_id': allocation.obra_id,
                'obra_nome': allocation.obra.nome,
                'obra_codigo': allocation.obra.codigo,
                'data_alocacao': allocation.data_alocacao.isoformat(),
                'turno_inicio': allocation.turno_inicio.strftime('%H:%M') if allocation.turno_inicio else '08:00',
                'turno_fim': allocation.turno_fim.strftime('%H:%M') if allocation.turno_fim else '17:00',
                'nota': allocation.nota,
                'funcionarios_count': allocation.funcionarios_count
            })
        
        return jsonify(data)
        
    except Exception as e:
        logging.error(f"API GET ALLOCATIONS ERROR: {str(e)}")
        return jsonify({'error': 'Erro interno'}), 500

@equipe_bp.route('/api/allocations', methods=['POST'])
@login_required
@admin_required
def api_create_allocation():
    """API: Criar nova alocação obra→dia"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        if not data or not data.get('obra_id') or not data.get('data_alocacao'):
            return jsonify({'error': 'obra_id e data_alocacao obrigatórios'}), 400
        
        # Verificar se obra pertence ao admin
        obra = Obra.query.filter_by(id=data['obra_id'], admin_id=admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        # Parse da data
        data_alocacao = datetime.strptime(data['data_alocacao'], '%Y-%m-%d').date()
        
        # Verificar conflito (mesma obra no mesmo dia)
        existing = Allocation.query.filter_by(
            admin_id=admin_id,
            obra_id=data['obra_id'],
            data_alocacao=data_alocacao
        ).first()
        
        if existing:
            return jsonify({'error': 'Obra já alocada neste dia'}), 409
        
        # Parse turnos (opcional)
        turno_inicio = time(8, 0)  # Default
        turno_fim = time(17, 0)    # Default
        
        if data.get('turno_inicio'):
            turno_inicio = datetime.strptime(data['turno_inicio'], '%H:%M').time()
        if data.get('turno_fim'):
            turno_fim = datetime.strptime(data['turno_fim'], '%H:%M').time()
        
        # Criar alocação
        allocation = Allocation(
            admin_id=admin_id,
            obra_id=data['obra_id'],
            data_alocacao=data_alocacao,
            turno_inicio=turno_inicio,
            turno_fim=turno_fim,
            nota=data.get('nota', '')[:100]  # Limitar tamanho
        )
        
        db.session.add(allocation)
        db.session.commit()
        
        logging.info(f"EQUIPE: Nova alocação criada - {obra.nome} em {data_alocacao}")
        
        return jsonify({
            'id': allocation.id,
            'message': 'Alocação criada com sucesso'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API CREATE ALLOCATION ERROR: {str(e)}")
        return jsonify({'error': 'Erro ao criar alocação'}), 500

@equipe_bp.route('/api/allocations/<int:allocation_id>', methods=['PUT'])
@login_required
@admin_required
def api_update_allocation(allocation_id):
    """API: Atualizar alocação (mover dia, alterar turno)"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        allocation = Allocation.query.filter_by(id=allocation_id, admin_id=admin_id).first()
        if not allocation:
            return jsonify({'error': 'Alocação não encontrada'}), 404
        
        # Atualizar campos permitidos
        if 'data_alocacao' in data:
            nova_data = datetime.strptime(data['data_alocacao'], '%Y-%m-%d').date()
            # Verificar conflito na nova data
            conflict = Allocation.query.filter(
                Allocation.admin_id == admin_id,
                Allocation.obra_id == allocation.obra_id,
                Allocation.data_alocacao == nova_data,
                Allocation.id != allocation_id
            ).first()
            
            if conflict:
                return jsonify({'error': 'Conflito: obra já alocada na nova data'}), 409
                
            allocation.data_alocacao = nova_data
        
        if 'turno_inicio' in data:
            allocation.turno_inicio = datetime.strptime(data['turno_inicio'], '%H:%M').time()
        if 'turno_fim' in data:
            allocation.turno_fim = datetime.strptime(data['turno_fim'], '%H:%M').time()
        if 'nota' in data:
            allocation.nota = data['nota'][:100]
        
        db.session.commit()
        
        logging.info(f"EQUIPE: Alocação {allocation_id} atualizada")
        
        return jsonify({'message': 'Alocação atualizada com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API UPDATE ALLOCATION ERROR: {str(e)}")
        return jsonify({'error': 'Erro ao atualizar alocação'}), 500

@equipe_bp.route('/api/allocations/<int:allocation_id>', methods=['DELETE'])
@login_required
@admin_required  
def api_delete_allocation(allocation_id):
    """API: Remover alocação (e todos funcionários)"""
    try:
        admin_id = get_admin_id()
        
        allocation = Allocation.query.filter_by(id=allocation_id, admin_id=admin_id).first()
        if not allocation:
            return jsonify({'error': 'Alocação não encontrada'}), 404
        
        # Remover funcionários alocados (cascade já cuida, mas explícito é melhor)
        AllocationEmployee.query.filter_by(allocation_id=allocation_id).delete()
        
        # Remover alocação
        db.session.delete(allocation)
        db.session.commit()
        
        logging.info(f"EQUIPE: Alocação {allocation_id} removida")
        
        return jsonify({'message': 'Alocação removida com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API DELETE ALLOCATION ERROR: {str(e)}")
        return jsonify({'error': 'Erro ao remover alocação'}), 500

@equipe_bp.route('/api/allocation-employees', methods=['POST'])
@login_required
@admin_required
def api_create_allocation_employee():
    """API: Alocar funcionário em obra/dia"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        if not data or not data.get('allocation_id') or not data.get('funcionario_id'):
            return jsonify({'error': 'allocation_id e funcionario_id obrigatórios'}), 400
        
        # Verificar se allocation pertence ao admin
        allocation = Allocation.query.filter_by(id=data['allocation_id'], admin_id=admin_id).first()
        if not allocation:
            return jsonify({'error': 'Alocação não encontrada'}), 404
        
        # Verificar se funcionário pertence ao admin
        funcionario = Funcionario.query.filter_by(id=data['funcionario_id'], admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        # Verificar conflito (funcionário já alocado no mesmo dia)
        conflict = AllocationEmployee.query.join(Allocation).filter(
            AllocationEmployee.funcionario_id == data['funcionario_id'],
            Allocation.data_alocacao == allocation.data_alocacao
        ).first()
        
        if conflict:
            return jsonify({'error': f'Funcionário já alocado em {conflict.allocation.obra.nome} neste dia'}), 409
        
        # Parse turnos (herda da alocação se não especificado)
        turno_inicio = allocation.turno_inicio
        turno_fim = allocation.turno_fim
        
        if data.get('turno_inicio'):
            turno_inicio = datetime.strptime(data['turno_inicio'], '%H:%M').time()
        if data.get('turno_fim'):
            turno_fim = datetime.strptime(data['turno_fim'], '%H:%M').time()
        
        # Criar alocação de funcionário
        allocation_employee = AllocationEmployee(
            allocation_id=data['allocation_id'],
            funcionario_id=data['funcionario_id'],
            turno_inicio=turno_inicio,
            turno_fim=turno_fim,
            papel=data.get('papel', '')[:50],
            observacao=data.get('observacao', '')[:100]
        )
        
        db.session.add(allocation_employee)
        db.session.commit()
        
        logging.info(f"EQUIPE: {funcionario.nome} alocado em {allocation.obra.nome}")
        
        return jsonify({
            'id': allocation_employee.id,
            'message': 'Funcionário alocado com sucesso'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API CREATE ALLOCATION EMPLOYEE ERROR: {str(e)}")
        return jsonify({'error': 'Erro ao alocar funcionário'}), 500

@equipe_bp.route('/api/allocation-employees/<int:employee_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_allocation_employee(employee_id):
    """API: Remover funcionário da alocação"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se pertence ao admin (via allocation)
        allocation_employee = AllocationEmployee.query.join(Allocation).filter(
            AllocationEmployee.id == employee_id,
            Allocation.admin_id == admin_id
        ).first()
        
        if not allocation_employee:
            return jsonify({'error': 'Alocação de funcionário não encontrada'}), 404
        
        db.session.delete(allocation_employee)
        db.session.commit()
        
        logging.info(f"EQUIPE: Funcionário removido da alocação {employee_id}")
        
        return jsonify({'message': 'Funcionário removido com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API DELETE ALLOCATION EMPLOYEE ERROR: {str(e)}")
        return jsonify({'error': 'Erro ao remover funcionário'}), 500

# ================================
# UTILITÁRIOS PARA TEMPLATES
# ================================

@equipe_bp.route('/api/funcionarios/disponiveis')
@login_required
@admin_required
def api_funcionarios_disponiveis():
    """API: Lista funcionários disponíveis para uma data"""
    try:
        admin_id = get_admin_id()
        data_param = request.args.get('data')
        
        if not data_param:
            return jsonify({'error': 'Parâmetro data obrigatório'}), 400
        
        target_date = datetime.strptime(data_param, '%Y-%m-%d').date()
        
        # Funcionários não alocados nesta data
        funcionarios_ocupados = db.session.query(AllocationEmployee.funcionario_id).join(Allocation).filter(
            Allocation.data_alocacao == target_date
        ).subquery()
        
        funcionarios_disponiveis = Funcionario.query.filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            ~Funcionario.id.in_(funcionarios_ocupados)
        ).order_by(Funcionario.nome).all()
        
        data = []
        for f in funcionarios_disponiveis:
            data.append({
                'id': f.id,
                'nome': f.nome,
                'codigo': f.codigo,
                'funcao': f.funcao,
                'foto_base64': f.foto_base64 if hasattr(f, 'foto_base64') else None
            })
        
        return jsonify(data)
        
    except Exception as e:
        logging.error(f"API FUNCIONARIOS DISPONIVEIS ERROR: {str(e)}")
        return jsonify({'error': 'Erro interno'}), 500