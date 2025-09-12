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
from sqlalchemy.exc import IntegrityError
import logging

equipe_bp = Blueprint('equipe', __name__, url_prefix='/equipe')

def get_admin_id():
    """Admin ID seguro - sem fallback perigoso"""
    if not current_user.is_authenticated:
        raise ValueError("Usuário não autenticado")
    
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    
    # Fallback seguro baseado no ID do usuário atual
    return current_user.id

def get_sunday_of_week(target_date):
    """Retorna domingo da semana (início da semana de 7 dias)"""
    # Python weekday(): 0=Monday, 6=Sunday
    # Queremos: domingo = início da semana
    days_since_sunday = (target_date.weekday() + 1) % 7
    sunday = target_date - timedelta(days=days_since_sunday)
    return sunday

def convert_to_sunday_weekday(python_weekday):
    """Converte Python weekday (0=Mon) para Sunday weekday (0=Sun)"""
    # Python: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    # Queremos: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
    return (python_weekday + 1) % 7

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
            'admin_id': get_admin_id(),
            'type': str(type(current_user)),
            'authenticated': current_user.is_authenticated
        }
        
        print("=== DEBUG TESTE-FASE1 FASE 2 ===")
        print(f"User info: {user_info}")
        
        # Teste básico de obras
        obras_count = 0
        try:
            from models import Obra
            admin_id = get_admin_id() 
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

# ===================================  
# ROTAS REMOVIDAS - Duplicadas e inseguras
# Mantendo apenas versões RESTful completas
# ===================================

@equipe_bp.route('/api/test', methods=['GET'])
@login_required
def test_api():
    """API de teste para validar integração - FASE 1"""
    try:
        return jsonify({
            'status': 'ok',
            'user_id': current_user.id,
            'admin_id': get_admin_id(),
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
        admin_id = get_admin_id()
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
        admin_id = get_admin_id()
        week_start = request.args.get('week_start')
        
        print(f"=== DEBUG ALLOCATIONS: admin_id={admin_id}, week_start={week_start} ===")
        
        # Parse da data ou usa semana atual
        if week_start:
            start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
        else:
            today = date.today()
            start_date = get_sunday_of_week(today)
        
        end_date = start_date + timedelta(days=6)  # Sábado (7 dias total)
        
        # Query simples
        allocations = Allocation.query.filter(
            Allocation.admin_id == admin_id,
            Allocation.data_alocacao >= start_date,
            Allocation.data_alocacao <= end_date
        ).all()
        
        print(f"=== DEBUG: Encontradas {len(allocations)} alocações ===")
        
        result = []
        for alloc in allocations:
            # Buscar obra (COM VALIDAÇÃO DE ADMIN_ID)
            obra = Obra.query.filter_by(id=alloc.obra_id, admin_id=admin_id).first()
            obra_nome = obra.nome if obra else f"Obra ID {alloc.obra_id}"
            obra_codigo = obra.codigo if obra else f"#{alloc.obra_id}"
            
            result.append({
                'id': alloc.id,
                'obra_id': alloc.obra_id,
                'obra_codigo': obra_codigo,
                'obra_nome': obra_nome,
                'data_alocacao': alloc.data_alocacao.isoformat(),
                'day_of_week': convert_to_sunday_weekday(alloc.data_alocacao.weekday()),  # 0=Domingo
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
@login_required
@admin_required
def teste_sem_auth():
    """Teste básico - AGORA COM autenticação"""
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
@login_required
@admin_required
def debug_test_direct():
    """API de teste - AGORA COM autenticação"""
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
        admin_id = get_admin_id()
        
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

# ===================================  
# NOVAS APIs - IMPLEMENTAÇÃO COMPLETA
# CONFORME ESPECIFICAÇÃO
# ===================================

@equipe_bp.route('/api/allocations', methods=['POST'])
@login_required
@admin_required
def api_alocar_obra_restful():
    """API RESTful: Alocar obra em um dia específico"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        # Validações de input
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        obra_id = data.get('obra_id')
        day_of_week = data.get('day_of_week')
        data_alocacao_str = data.get('data_alocacao')
        
        if not all([obra_id, day_of_week is not None, data_alocacao_str]):
            return jsonify({
                'success': False, 
                'error': 'Campos obrigatórios: obra_id, day_of_week, data_alocacao'
            }), 400
        
        # Parse da data
        try:
            data_alocacao = datetime.strptime(data_alocacao_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False, 
                'error': 'Formato de data inválido. Use YYYY-MM-DD'
            }), 400
        
        # Verificar se obra existe e pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id, ativo=True).first()
        if not obra:
            return jsonify({
                'success': False, 
                'error': 'Obra não encontrada ou inativa'
            }), 404
        
        # Criar nova alocação
        allocation = Allocation()
        allocation.admin_id = admin_id
        allocation.obra_id = obra_id
        allocation.data_alocacao = data_alocacao
        allocation.turno_inicio = time(8, 0)  # Padrão 08:00
        allocation.turno_fim = time(17, 0)    # Padrão 17:00
        allocation.nota = data.get('nota', '')
        
        db.session.add(allocation)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Obra {obra.codigo} já está alocada neste dia'
            }), 409
        
        return jsonify({
            'success': True,
            'allocation_id': allocation.id,
            'obra_codigo': obra.codigo,
            'obra_nome': obra.nome,
            'data_alocacao': data_alocacao.isoformat(),
            'message': f'Obra {obra.codigo} alocada com sucesso'
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Obra já está alocada neste dia'
        }), 409
    except Exception as e:
        db.session.rollback()
        logging.error(f"API ALOCAR OBRA ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': 'Erro interno do servidor'
        }), 500

@equipe_bp.route('/api/allocations/<int:obra_id>/<data_alocacao>', methods=['DELETE'])
@login_required
@admin_required
def api_remover_obra_restful(obra_id, data_alocacao):
    """API RESTful: Remover obra de um dia específico"""
    try:
        admin_id = get_admin_id()
        
        # Parse da data
        try:
            data_alocacao_parsed = datetime.strptime(data_alocacao, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False, 
                'error': 'Formato de data inválido. Use YYYY-MM-DD'
            }), 400
        
        # Buscar alocação
        allocation = Allocation.query.filter_by(
            admin_id=admin_id,
            obra_id=obra_id,
            data_alocacao=data_alocacao_parsed
        ).first()
        
        if not allocation:
            return jsonify({
                'success': False, 
                'error': 'Alocação não encontrada'
            }), 404
        
        # Buscar dados da obra para retorno - COM VALIDAÇÃO DE ADMIN_ID
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        obra_codigo = obra.codigo if obra else f"#{obra_id}"
        
        # Deletar alocação
        db.session.delete(allocation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'obra_codigo': obra_codigo,
            'data_alocacao': data_alocacao_parsed.isoformat(),
            'message': f'Obra {obra_codigo} removida com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API REMOVER OBRA ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': 'Erro interno do servidor'
        }), 500

@equipe_bp.route('/api/allocations-week', methods=['GET'])
@login_required
def api_allocations_week():
    """API: Carregar alocações da semana"""
    try:
        admin_id = get_admin_id()
        week_param = request.args.get('week')
        
        # Parse da data ou usa semana atual
        if week_param:
            try:
                start_date = datetime.strptime(week_param, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False, 
                    'error': 'Formato de data inválido. Use YYYY-MM-DD'
                }), 400
        else:
            today = date.today()
            start_date = get_sunday_of_week(today)
        
        # Garantir que seja domingo
        start_date = get_sunday_of_week(start_date)
        end_date = start_date + timedelta(days=6)  # Sábado (7 dias total)
        
        # Query das alocações
        allocations = db.session.query(Allocation, Obra).join(
            Obra, Allocation.obra_id == Obra.id
        ).filter(
            Allocation.admin_id == admin_id,
            Allocation.data_alocacao >= start_date,
            Allocation.data_alocacao <= end_date
        ).order_by(Allocation.data_alocacao, Obra.codigo).all()
        
        # Organizar por dia da semana
        week_data = {}
        day_names = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
        for i in range(7):  # Domingo a Sábado (0-6)
            day_date = start_date + timedelta(days=i)
            week_data[i] = {
                'date': day_date.isoformat(),
                'day_name': day_names[i],
                'allocations': []
            }
        
        # Processar alocações
        for allocation, obra in allocations:
            # Converter weekday do Python (0=Mon) para nosso sistema (0=Sun)
            sunday_day_of_week = convert_to_sunday_weekday(allocation.data_alocacao.weekday())
            if sunday_day_of_week in week_data:  # Domingo a Sábado (0-6)
                week_data[sunday_day_of_week]['allocations'].append({
                    'id': allocation.id,
                    'obra_id': allocation.obra_id,
                    'obra_codigo': obra.codigo,
                    'obra_nome': obra.nome,
                    'data_alocacao': allocation.data_alocacao.isoformat(),
                    'turno_inicio': allocation.turno_inicio.strftime('%H:%M') if allocation.turno_inicio else '08:00',
                    'turno_fim': allocation.turno_fim.strftime('%H:%M') if allocation.turno_fim else '17:00',
                    'nota': allocation.nota or ''
                })
        
        return jsonify({
            'success': True,
            'week_start': start_date.isoformat(),
            'week_end': end_date.isoformat(),
            'data': week_data,
            'total_allocations': len(allocations),
            'admin_id': admin_id
        })
        
    except Exception as e:
        logging.error(f"API ALLOCATIONS WEEK ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': 'Erro interno do servidor'
        }), 500

# ===================================  
# MÓDULO GESTÃO DE FUNCIONÁRIOS EM ALOCAÇÕES
# APIs REST para gerenciar funcionários nas alocações de equipe
# ===================================

@equipe_bp.route('/api/allocation/<int:allocation_id>/funcionarios', methods=['GET'])
@login_required
@admin_required
def api_get_allocation_funcionarios(allocation_id):
    """API REST: Listar funcionários de uma alocação específica"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se allocation existe e pertence ao admin
        allocation = Allocation.query.filter_by(
            id=allocation_id, 
            admin_id=admin_id
        ).first()
        
        if not allocation:
            return jsonify({
                'success': False,
                'error': 'Alocação não encontrada'
            }), 404
        
        # Buscar obra para informações adicionais - COM VALIDAÇÃO DE ADMIN_ID
        obra = Obra.query.filter_by(id=allocation.obra_id, admin_id=admin_id).first()
        
        # Funcionários já alocados nesta allocation
        funcionarios_alocados = db.session.query(AllocationEmployee, Funcionario).join(
            Funcionario, AllocationEmployee.funcionario_id == Funcionario.id
        ).filter(
            AllocationEmployee.allocation_id == allocation_id
        ).order_by(Funcionario.nome).all()
        
        # Funcionários disponíveis (ativos do admin)
        funcionarios_disponiveis = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Serializar funcionários alocados
        alocados_data = []
        for alloc_emp, funcionario in funcionarios_alocados:
            alocados_data.append({
                'allocation_employee_id': alloc_emp.id,
                'funcionario_id': funcionario.id,
                'funcionario_nome': funcionario.nome,
                'funcionario_codigo': funcionario.codigo,
                'turno_inicio': alloc_emp.turno_inicio.strftime('%H:%M') if alloc_emp.turno_inicio else '08:00',
                'turno_fim': alloc_emp.turno_fim.strftime('%H:%M') if alloc_emp.turno_fim else '17:00',
                'papel': alloc_emp.papel or '',
                'observacao': alloc_emp.observacao or '',
                'created_at': alloc_emp.created_at.isoformat()
            })
        
        # Serializar funcionários disponíveis
        disponiveis_data = []
        for funcionario in funcionarios_disponiveis:
            disponiveis_data.append({
                'id': funcionario.id,
                'nome': funcionario.nome,
                'codigo': funcionario.codigo,
                'funcao': funcionario.funcao_ref.nome if funcionario.funcao_ref else '',
                'departamento': funcionario.departamento_ref.nome if funcionario.departamento_ref else ''
            })
        
        return jsonify({
            'success': True,
            'allocation': {
                'id': allocation.id,
                'obra_id': allocation.obra_id,
                'obra_codigo': obra.codigo if obra else f"#{allocation.obra_id}",
                'obra_nome': obra.nome if obra else "Obra não encontrada",
                'data_alocacao': allocation.data_alocacao.isoformat(),
                'turno_inicio': allocation.turno_inicio.strftime('%H:%M') if allocation.turno_inicio else '08:00',
                'turno_fim': allocation.turno_fim.strftime('%H:%M') if allocation.turno_fim else '17:00',
                'nota': allocation.nota or ''
            },
            'funcionarios_alocados': alocados_data,
            'funcionarios_disponiveis': disponiveis_data,
            'total_alocados': len(alocados_data),
            'total_disponiveis': len(disponiveis_data)
        })
        
    except Exception as e:
        logging.error(f"API GET ALLOCATION FUNCIONARIOS ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

@equipe_bp.route('/api/allocation-employee', methods=['POST'])
@login_required
@admin_required
def api_create_allocation_employee():
    """API REST: Adicionar funcionário à alocação"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        # Validações de input
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        allocation_id = data.get('allocation_id')
        funcionario_id = data.get('funcionario_id')
        
        if not allocation_id or not funcionario_id:
            return jsonify({
                'success': False,
                'error': 'Campos obrigatórios: allocation_id, funcionario_id'
            }), 400
        
        # Verificar se allocation existe e pertence ao admin
        allocation = Allocation.query.filter_by(
            id=allocation_id,
            admin_id=admin_id
        ).first()
        
        if not allocation:
            return jsonify({
                'success': False,
                'error': 'Alocação não encontrada'
            }), 404
        
        # Verificar se funcionário existe, ativo e pertence ao admin
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not funcionario:
            return jsonify({
                'success': False,
                'error': 'Funcionário não encontrado ou inativo'
            }), 404
        
        # Verificar duplicação (mesmo funcionário na mesma allocation)
        existing = AllocationEmployee.query.filter_by(
            allocation_id=allocation_id,
            funcionario_id=funcionario_id
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': f'Funcionário {funcionario.nome} já está alocado nesta obra/dia'
            }), 409
        
        # Verificar conflito de data (funcionário em outra obra no mesmo dia)
        conflicting_allocation = db.session.query(AllocationEmployee, Allocation).join(
            Allocation, AllocationEmployee.allocation_id == Allocation.id
        ).filter(
            AllocationEmployee.funcionario_id == funcionario_id,
            Allocation.data_alocacao == allocation.data_alocacao,
            Allocation.admin_id == admin_id,
            AllocationEmployee.allocation_id != allocation_id
        ).first()
        
        if conflicting_allocation:
            conflicting_obra = Obra.query.filter_by(id=conflicting_allocation[1].obra_id, admin_id=admin_id).first()
            obra_nome = conflicting_obra.codigo if conflicting_obra else f"Obra #{conflicting_allocation[1].obra_id}"
            return jsonify({
                'success': False,
                'error': f'Funcionário {funcionario.nome} já está alocado na obra {obra_nome} neste dia'
            }), 409
        
        # Validar e processar horários
        turno_inicio_str = data.get('turno_inicio', '08:00')
        turno_fim_str = data.get('turno_fim', '17:00')
        
        try:
            turno_inicio = datetime.strptime(turno_inicio_str, '%H:%M').time()
            turno_fim = datetime.strptime(turno_fim_str, '%H:%M').time()
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Formato de horário inválido. Use HH:MM (ex: 08:00)'
            }), 400
        
        # Criar AllocationEmployee
        allocation_employee = AllocationEmployee()
        allocation_employee.allocation_id = allocation_id
        allocation_employee.funcionario_id = funcionario_id
        allocation_employee.turno_inicio = turno_inicio
        allocation_employee.turno_fim = turno_fim
        allocation_employee.papel = data.get('papel', funcionario.funcao_ref.nome if funcionario.funcao_ref else '')
        allocation_employee.observacao = data.get('observacao', '')
        
        db.session.add(allocation_employee)
        db.session.commit()
        
        # Buscar dados da obra para retorno - COM VALIDAÇÃO DE ADMIN_ID
        obra = Obra.query.filter_by(id=allocation.obra_id, admin_id=admin_id).first()
        
        return jsonify({
            'success': True,
            'allocation_employee_id': allocation_employee.id,
            'funcionario_nome': funcionario.nome,
            'funcionario_codigo': funcionario.codigo,
            'obra_codigo': obra.codigo if obra else f"#{allocation.obra_id}",
            'data_alocacao': allocation.data_alocacao.isoformat(),
            'turno_inicio': allocation_employee.turno_inicio.strftime('%H:%M'),
            'turno_fim': allocation_employee.turno_fim.strftime('%H:%M'),
            'papel': allocation_employee.papel,
            'message': f'Funcionário {funcionario.nome} adicionado com sucesso'
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Erro de integridade: funcionário já pode estar alocado'
        }), 409
    except Exception as e:
        db.session.rollback()
        logging.error(f"API CREATE ALLOCATION EMPLOYEE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

@equipe_bp.route('/api/allocation-employee/<int:allocation_employee_id>', methods=['PUT'])
@login_required
@admin_required
def api_update_allocation_employee(allocation_employee_id):
    """API REST: Atualizar funcionário alocado"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        # Buscar AllocationEmployee e verificar se pertence ao admin
        allocation_employee = db.session.query(AllocationEmployee, Allocation).join(
            Allocation, AllocationEmployee.allocation_id == Allocation.id
        ).filter(
            AllocationEmployee.id == allocation_employee_id,
            Allocation.admin_id == admin_id
        ).first()
        
        if not allocation_employee:
            return jsonify({
                'success': False,
                'error': 'Funcionário alocado não encontrado'
            }), 404
        
        alloc_emp, allocation = allocation_employee
        
        # Validar e processar horários se fornecidos
        if 'turno_inicio' in data:
            try:
                turno_inicio = datetime.strptime(data['turno_inicio'], '%H:%M').time()
                alloc_emp.turno_inicio = turno_inicio
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Formato de turno_inicio inválido. Use HH:MM'
                }), 400
        
        if 'turno_fim' in data:
            try:
                turno_fim = datetime.strptime(data['turno_fim'], '%H:%M').time()
                alloc_emp.turno_fim = turno_fim
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Formato de turno_fim inválido. Use HH:MM'
                }), 400
        
        # Atualizar outros campos se fornecidos
        if 'papel' in data:
            alloc_emp.papel = data['papel']
        
        if 'observacao' in data:
            alloc_emp.observacao = data['observacao']
        
        db.session.commit()
        
        # Buscar dados do funcionário e obra para retorno - COM VALIDAÇÃO DE ADMIN_ID
        funcionario = Funcionario.query.filter_by(id=alloc_emp.funcionario_id, admin_id=admin_id).first()
        obra = Obra.query.filter_by(id=allocation.obra_id, admin_id=admin_id).first()
        
        return jsonify({
            'success': True,
            'allocation_employee_id': alloc_emp.id,
            'funcionario_nome': funcionario.nome if funcionario else 'Funcionário não encontrado',
            'funcionario_codigo': funcionario.codigo if funcionario else '',
            'obra_codigo': obra.codigo if obra else f"#{allocation.obra_id}",
            'data_alocacao': allocation.data_alocacao.isoformat(),
            'turno_inicio': alloc_emp.turno_inicio.strftime('%H:%M'),
            'turno_fim': alloc_emp.turno_fim.strftime('%H:%M'),
            'papel': alloc_emp.papel or '',
            'observacao': alloc_emp.observacao or '',
            'message': 'Funcionário alocado atualizado com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API UPDATE ALLOCATION EMPLOYEE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

@equipe_bp.route('/api/allocation-employee/<int:allocation_employee_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_allocation_employee(allocation_employee_id):
    """API REST: Remover funcionário da alocação"""
    try:
        admin_id = get_admin_id()
        
        # Buscar AllocationEmployee e verificar se pertence ao admin
        allocation_employee = db.session.query(AllocationEmployee, Allocation, Funcionario).join(
            Allocation, AllocationEmployee.allocation_id == Allocation.id
        ).join(
            Funcionario, AllocationEmployee.funcionario_id == Funcionario.id
        ).filter(
            AllocationEmployee.id == allocation_employee_id,
            Allocation.admin_id == admin_id
        ).first()
        
        if not allocation_employee:
            return jsonify({
                'success': False,
                'error': 'Funcionário alocado não encontrado'
            }), 404
        
        alloc_emp, allocation, funcionario = allocation_employee
        
        # Buscar dados da obra para retorno - COM VALIDAÇÃO DE ADMIN_ID
        obra = Obra.query.filter_by(id=allocation.obra_id, admin_id=admin_id).first()
        
        # Preparar dados para retorno antes da deleção
        response_data = {
            'success': True,
            'funcionario_nome': funcionario.nome,
            'funcionario_codigo': funcionario.codigo,
            'obra_codigo': obra.codigo if obra else f"#{allocation.obra_id}",
            'data_alocacao': allocation.data_alocacao.isoformat(),
            'message': f'Funcionário {funcionario.nome} removido da alocação com sucesso'
        }
        
        # Deletar AllocationEmployee
        db.session.delete(alloc_emp)
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API DELETE ALLOCATION EMPLOYEE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500