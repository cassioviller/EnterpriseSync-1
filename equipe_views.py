"""
EQUIPE VIEWS - SISTEMA SIMPLIFICADO
===================================
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from auth import admin_required
from datetime import datetime, date, timedelta, time
from app import db
from models import Allocation, AllocationEmployee, Funcionario, Obra, Servico, Usuario, TipoUsuario, WeeklyPlan
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
    """Redirecionar para teste FASE 1"""
    return redirect(url_for('equipe.alocacao_teste_fase1'))

@equipe_bp.route('/teste-fase1')
@login_required
@admin_required
def alocacao_teste_fase1():
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
        
        # FASE 1: Renderizar template simplificado
        return render_template('equipe/alocacao_simples.html',
                             debug={'admin_id': admin_id, 'total_obras': len(obras)})
        
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

# ===================================  
# FASE 1: APIs ULTRA SIMPLES - TESTE
# SEGUINDO PLANO REALISTA EXATAMENTE
# ===================================

def get_current_admin_id():
    """Descubra como funciona no NOSSO sistema - FASE 1"""
    # TESTE PRIMEIRO - adapte conforme necessário
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        return current_user.admin_id
    return current_user.id  # Fallback

@equipe_bp.route('/api/test', methods=['GET'])
@login_required
def test_api():
    """API de teste para validar integração - FASE 1"""
    try:
        return jsonify({
            'status': 'ok',
            'user_id': current_user.id,
            'admin_id': get_current_admin_id(),
            'user_type': str(type(current_user)),
            'user_tipo_usuario': str(current_user.tipo_usuario) if hasattr(current_user, 'tipo_usuario') else 'N/A',
            'timestamp': datetime.now().isoformat(),
            'message': 'FASE 1: API funcionando!'
        })
    except Exception as e:
        print(f"ERRO API TEST: {e}")  # Debug simples
        return jsonify({'status': 'error', 'error': str(e)})

@equipe_bp.route('/api/obras-simples', methods=['GET'])
@login_required
def get_obras_simples():
    """Lista obras - VERSÃO SIMPLES FASE 1"""
    try:
        # Use a query que você já conhece
        admin_id = get_current_admin_id()
        print(f"=== DEBUG OBRAS: admin_id={admin_id} ===")
        
        # ADAPTE conforme seu modelo Obra atual
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.codigo).all()
        print(f"=== DEBUG: Encontradas {len(obras)} obras ===")
        
        result = []
        for obra in obras:
            result.append({
                'id': obra.id,
                'codigo': obra.codigo,
                'nome': obra.nome[:50] + ('...' if len(obra.nome) > 50 else '')  # Truncar nome longo
            })
        
        return jsonify({
            'success': True, 
            'data': result, 
            'count': len(result),
            'admin_id': admin_id,
            'message': 'FASE 1: Obras carregadas!'
        })
        
    except Exception as e:
        print(f"ERRO API OBRAS: {e}")  # Debug simples
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@equipe_bp.route('/api/allocations-simples', methods=['GET'])
@login_required
def get_allocations_simples():
    """Lista alocações - VERSÃO SIMPLES FASE 1"""
    try:
        admin_id = get_current_admin_id()
        week_start = request.args.get('week_start')
        
        print(f"=== DEBUG ALLOCATIONS: admin_id={admin_id}, week_start={week_start} ===")
        
        # Parse da data ou usa semana atual
        if week_start:
            start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
        else:
            today = date.today()
            start_date = get_monday_of_week(today)
        
        end_date = start_date + timedelta(days=4)  # Sexta-feira
        
        # Query simples
        allocations = Allocation.query.filter(
            Allocation.admin_id == admin_id,
            Allocation.data_alocacao >= start_date,
            Allocation.data_alocacao <= end_date
        ).all()
        
        print(f"=== DEBUG: Encontradas {len(allocations)} alocações ===")
        
        result = []
        for alloc in allocations:
            # Buscar obra (sem relacionamento por enquanto)
            obra = Obra.query.get(alloc.obra_id)
            obra_nome = obra.nome if obra else f"Obra ID {alloc.obra_id}"
            obra_codigo = obra.codigo if obra else f"#{alloc.obra_id}"
            
            result.append({
                'id': alloc.id,
                'obra_id': alloc.obra_id,
                'obra_codigo': obra_codigo,
                'obra_nome': obra_nome,
                'data_alocacao': alloc.data_alocacao.isoformat(),
                'day_of_week': alloc.data_alocacao.weekday(),  # 0=Segunda
                'turno_inicio': alloc.turno_inicio.strftime('%H:%M') if alloc.turno_inicio else '08:00',
                'turno_fim': alloc.turno_fim.strftime('%H:%M') if alloc.turno_fim else '17:00'
            })
        
        return jsonify({
            'success': True,
            'data': result,
            'count': len(result),
            'week_start': start_date.isoformat(),
            'week_end': end_date.isoformat(),
            'message': 'FASE 1: Alocações carregadas!'
        })
        
    except Exception as e:
        print(f"ERRO API ALLOCATIONS: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})