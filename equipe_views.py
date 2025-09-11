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
def alocacao_teste_fase1():
    """Rota principal com debug detalhado - FASE 2"""
    try:
        # Debug de usuário
        user_info = {
            'id': current_user.id,
            'admin_id': get_current_admin_id(),
            'type': str(type(current_user)),
            'authenticated': current_user.is_authenticated
        }
        
        print("=== DEBUG TESTE-FASE1 FASE 2 ===")
        print(f"User info: {user_info}")
        
        # Teste básico de obras
        obras_count = 0
        try:
            from models import Obra
            admin_id = get_current_admin_id() 
            obras_count = Obra.query.filter_by(admin_id=admin_id, ativo=True).count()
            print(f"Obras encontradas: {obras_count}")
        except Exception as e:
            print(f"ERRO ao contar obras: {e}")
        
        # Teste de template
        return render_template('equipe/alocacao_simples.html', 
                             debug_info=user_info,
                             obras_count=obras_count)
        
    except Exception as e:
        print(f"ERRO COMPLETO FASE 2: {e}")
        import traceback
        traceback.print_exc()
        
        # Retorna erro detalhado
        return f"""
        <div class="container mt-5">
            <div class="alert alert-danger">
                <h3>❌ ERRO NA FASE 2</h3>
                <p><strong>Erro:</strong> {e}</p>
                <pre>{traceback.format_exc()}</pre>
                <hr>
                <a href="/equipe/teste-sem-auth" class="btn btn-primary">← Voltar ao teste básico</a>
                <a href="/equipe/debug/test-direct" class="btn btn-info">Testar API Direta</a>
            </div>
        </div>
        """

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

# ===================================  
# FASE 2: TESTES E DEBUG - IMPLEMENTAÇÃO
# SEGUINDO PLANO EXATO DO PROMPT
# ===================================

@equipe_bp.route('/teste-sem-auth')
def teste_sem_auth():
    """Teste básico - sem autenticação"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste Fase 2</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="alert alert-success">
                <h1>🎯 FASE 2 - TESTE BÁSICO</h1>
                <p><strong>✅ Rota funcionando!</strong></p>
                <p>Blueprint registrado corretamente.</p>
                <hr>
                <h3>Próximos testes:</h3>
                <a href="/equipe/debug/test-direct" class="btn btn-info me-2">Teste API Direta</a>
                <a href="/equipe/teste-fase1" class="btn btn-warning">Teste com Auth</a>
            </div>
        </div>
    </body>
    </html>
    """

@equipe_bp.route('/debug/test-direct')
def debug_test_direct():
    """API de teste - sem autenticação"""
    import datetime
    return jsonify({
        'status': 'API funcionando',
        'timestamp': datetime.datetime.now().isoformat(),
        'debug': True,
        'message': 'Rota de debug ativa',
        'fase': 2
    })

@equipe_bp.route('/debug/obras-count')
@login_required  # Esta precisa de auth
def debug_obras_count():
    """Conta obras - com autenticação"""
    try:
        admin_id = get_current_admin_id()
        
        # Teste básico de query
        from models import Obra
        total_obras = Obra.query.count()
        obras_admin = Obra.query.filter_by(admin_id=admin_id).count()
        obras_ativas = Obra.query.filter_by(admin_id=admin_id, ativo=True).count()
        
        return jsonify({
            'admin_id': admin_id,
            'total_obras_sistema': total_obras,
            'obras_do_admin': obras_admin,
            'obras_ativas': obras_ativas,
            'status': 'ok',
            'fase': 2
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'status': 'error',
            'fase': 2
        })