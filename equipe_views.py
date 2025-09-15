"""
EQUIPE VIEWS - SISTEMA SIMPLIFICADO
===================================
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from auth import admin_required
from datetime import datetime, date, timedelta, time
from app import db
from models import Allocation, AllocationEmployee, Funcionario, Obra, TipoUsuario
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
def alocacao_semanal():
    """Redirecionar para alocação principal"""
    return redirect(url_for('equipe.alocacao_principal'))

@equipe_bp.route('/alocacao-principal')
@login_required  
def alocacao_principal():
    """Rota principal de alocação - FASE 2B"""
    try:
        # Debug de usuário
        user_info = {
            'id': current_user.id,
            'admin_id': get_admin_id(),
            'type': str(type(current_user)),
            'authenticated': current_user.is_authenticated
        }
        
        
        # Teste básico de obras
        obras_count = 0
        try:
            from models import Obra
            admin_id = get_admin_id() 
            obras_count = Obra.query.filter_by(admin_id=admin_id, ativo=True).count()
        except Exception as e:
            logging.error(f"Erro ao contar obras: {e}")
        
        # Teste de template
        return render_template('equipe/alocacao_simples.html', 
                             debug_info=user_info,
                             obras_count=obras_count)
        
    except Exception as e:
        logging.error(f"Erro na alocação teste fase 1: {e}")
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
                <a href="/equipe" class="btn btn-primary">← Voltar ao dashboard</a>
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
        
        # Funcionários já alocados (através do relacionamento AllocationEmployee)
        funcionarios_alocados = []
        try:
            allocation_employees = AllocationEmployee.query.filter_by(allocation_id=allocation_id).all()
            for ae in allocation_employees:
                funcionario = Funcionario.query.filter_by(id=ae.funcionario_id, admin_id=admin_id, ativo=True).first()
                if funcionario:  # Validação adicional de segurança
                    funcionarios_alocados.append({
                        'allocation_employee_id': ae.id,
                        'funcionario': funcionario,
                        'papel': ae.papel or 'Sem função',
                        'turno_inicio': ae.turno_inicio.strftime('%H:%M') if ae.turno_inicio else '08:00',
                        'turno_fim': ae.turno_fim.strftime('%H:%M') if ae.turno_fim else '17:00',
                        'hora_almoco_saida': ae.hora_almoco_saida.strftime('%H:%M') if ae.hora_almoco_saida else '12:00',
                        'hora_almoco_retorno': ae.hora_almoco_retorno.strftime('%H:%M') if ae.hora_almoco_retorno else '13:00',
                        'percentual_extras': ae.percentual_extras if hasattr(ae, 'percentual_extras') else 0.0,
                        'tipo_lancamento': ae.tipo_lancamento if hasattr(ae, 'tipo_lancamento') else 'trabalho_normal',
                        'observacao': ae.observacao or ''
                    })
        except Exception as e:
            logging.error(f"Erro ao buscar funcionários alocados para allocation {allocation_id}: {e}")
            funcionarios_alocados = []
        
        return render_template('equipe/allocation_funcionarios.html',
                             allocation=allocation,
                             funcionarios_disponiveis=funcionarios_disponiveis,
                             funcionarios_alocados=funcionarios_alocados)
        
    except Exception as e:
        logging.error(f"FUNCIONARIOS ERROR: {str(e)}")
        flash('Erro ao carregar funcionários', 'error')
        return redirect(url_for('equipe.alocacao_semanal'))


@equipe_bp.route('/api/allocations/<int:allocation_id>/funcionarios', methods=['GET'])
@login_required
def get_funcionarios_allocation_json(allocation_id):
    """API JSON para funcionários de uma alocação específica (para os cards)"""
    try:
        admin_id = get_admin_id()
        
        # Validar que a alocação pertence ao admin
        allocation = Allocation.query.filter_by(id=allocation_id, admin_id=admin_id).first()
        if not allocation:
            return jsonify({
                'success': False,
                'error': 'Alocação não encontrada',
                'funcionarios': []
            }), 404
        
        # Buscar funcionários alocados
        funcionarios_list = []
        try:
            allocation_employees = AllocationEmployee.query.filter_by(allocation_id=allocation_id).all()
            
            for ae in allocation_employees:
                funcionario = Funcionario.query.filter_by(
                    id=ae.funcionario_id, 
                    admin_id=admin_id, 
                    ativo=True
                ).first()
                
                if funcionario:  # Validação adicional
                    funcionarios_list.append({
                        'id': funcionario.id,
                        'nome': funcionario.nome,
                        'nome_curto': ' '.join(funcionario.nome.split()[:2]),  # Primeiros 2 nomes
                        'codigo': funcionario.codigo,
                        'papel': ae.papel or 'Sem função',
                        'entrada': ae.turno_inicio.strftime('%H:%M') if ae.turno_inicio else '08:00',
                        'saida': ae.turno_fim.strftime('%H:%M') if ae.turno_fim else '17:00',
                        'almoco_saida': ae.hora_almoco_saida.strftime('%H:%M') if ae.hora_almoco_saida else '12:00',
                        'almoco_retorno': ae.hora_almoco_retorno.strftime('%H:%M') if ae.hora_almoco_retorno else '13:00',
                        'percentual_extras': ae.percentual_extras if hasattr(ae, 'percentual_extras') else 0.0,
                        'tipo_lancamento': ae.tipo_lancamento if hasattr(ae, 'tipo_lancamento') else 'trabalho_normal'
                    })
        
        except Exception as e:
            logging.error(f"Erro ao buscar funcionários da alocação {allocation_id}: {e}")
        
        return jsonify({
            'success': True,
            'allocation_id': allocation_id,
            'total_alocados': len(funcionarios_list),  # Para os badges
            'count': len(funcionarios_list),  # Mantém compatibilidade
            'funcionarios': funcionarios_list,  # Para lista detalhada
            'funcionarios_alocados': funcionarios_list,  # Para o modal
            'funcionarios_disponiveis': [],  # Modal espera isso também
            'allocation': {  # Dados da alocação para o modal
                'id': allocation.id,
                'obra_codigo': allocation.obra.codigo if allocation.obra else f"#{allocation.obra_id}",
                'obra_nome': allocation.obra.nome if allocation.obra else "Obra não encontrada",
                'data_alocacao': allocation.data_alocacao.isoformat(),
                'local_trabalho': allocation.local_trabalho
            }
        })
        
    except Exception as e:
        logging.error(f"API FUNCIONARIOS ERROR para allocation {allocation_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor',
            'funcionarios': []
        }), 500


@equipe_bp.route('/api/obras-simples', methods=['GET'])
@login_required
def get_obras_simples():
    """Lista obras disponíveis"""
    try:
        admin_id = get_admin_id()
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.codigo).all()
        
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
            'message': 'Obras carregadas com sucesso'
        })
        
    except Exception as e:
        logging.error(f"Erro API obras: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@equipe_bp.route('/api/allocations-simples', methods=['GET'])
@login_required
def get_allocations_simples():
    """Lista alocações da semana"""
    try:
        admin_id = get_admin_id()
        week_start = request.args.get('week_start')
        
        
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
        
        
        result = []
        for alloc in allocations:
            # Buscar obra (COM VALIDAÇÃO DE ADMIN_ID)
            obra = Obra.query.filter_by(id=alloc.obra_id, admin_id=admin_id).first()
            obra_nome = obra.nome if obra else f"Obra ID {alloc.obra_id}"
            obra_codigo = obra.codigo if obra else f"#{alloc.obra_id}"
            
            # Buscar funcionários alocados
            funcionarios_data = []
            try:
                funcionarios_alocados = AllocationEmployee.query.filter_by(allocation_id=alloc.id).all()
                for emp in funcionarios_alocados:
                    funcionario = Funcionario.query.filter_by(id=emp.funcionario_id, admin_id=admin_id).first()
                    if funcionario:  # Validação adicional de segurança
                        funcionarios_data.append({
                            'id': funcionario.id,
                            'nome': funcionario.nome,
                            'nome_curto': ' '.join(funcionario.nome.split()[:2]),  # Primeiros 2 nomes
                            'codigo': funcionario.codigo,
                            'papel': emp.papel or 'Sem função',
                            'entrada': emp.turno_inicio.strftime('%H:%M') if emp.turno_inicio else '08:00',
                            'saida': emp.turno_fim.strftime('%H:%M') if emp.turno_fim else '17:00',
                            # LEGACY: Manter compatibilidade temporária
                            'turno_inicio': emp.turno_inicio.strftime('%H:%M') if emp.turno_inicio else '08:00',
                            'turno_fim': emp.turno_fim.strftime('%H:%M') if emp.turno_fim else '17:00',
                            # FASE 2B: Campos lunch padronizados
                            'almoco_saida': emp.hora_almoco_saida.strftime('%H:%M') if emp.hora_almoco_saida else '12:00',
                            'almoco_retorno': emp.hora_almoco_retorno.strftime('%H:%M') if emp.hora_almoco_retorno else '13:00',
                            # LEGACY: Compatibilidade temporária
                            'inicio_almoco': emp.hora_almoco_saida.strftime('%H:%M') if emp.hora_almoco_saida else '12:00',
                            'fim_almoco': emp.hora_almoco_retorno.strftime('%H:%M') if emp.hora_almoco_retorno else '13:00',
                            'percentual_extras': emp.percentual_extras if hasattr(emp, 'percentual_extras') else 0.0,
                            'tipo_lancamento': emp.tipo_lancamento if hasattr(emp, 'tipo_lancamento') else 'trabalho_normal',
                            'observacao': emp.observacao or ''
                        })
            except Exception as e:
                logging.error(f"Erro ao buscar funcionários da alocação {alloc.id}: {e}")
                funcionarios_data = []
            
            result.append({
                'id': alloc.id,
                'obra_id': alloc.obra_id,
                'obra_codigo': obra_codigo,
                'obra_nome': obra_nome,
                'data_alocacao': alloc.data_alocacao.isoformat(),
                'day_of_week': convert_to_sunday_weekday(alloc.data_alocacao.weekday()),  # 0=Domingo
                'entrada': alloc.turno_inicio.strftime('%H:%M') if alloc.turno_inicio else '08:00',
                'saida': alloc.turno_fim.strftime('%H:%M') if alloc.turno_fim else '17:00',
                # LEGACY: Manter compatibilidade temporária
                'turno_inicio': alloc.turno_inicio.strftime('%H:%M') if alloc.turno_inicio else '08:00',
                'turno_fim': alloc.turno_fim.strftime('%H:%M') if alloc.turno_fim else '17:00',
                'local_trabalho': alloc.local_trabalho or 'campo',  # Campo requerido para renderização correta
                'funcionarios': funcionarios_data,
                'funcionarios_count': len(funcionarios_data)
            })
        
        return jsonify({
            'success': True,
            'data': result,
            'count': len(result),
            'week_start': start_date.isoformat(),
            'week_end': end_date.isoformat(),
            'message': 'Alocações carregadas com sucesso'
        })
        
    except Exception as e:
        logging.error(f"Erro API allocations: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})




# ===================================
# FASE 4: INTEGRAÇÃO HORÁRIOS AUTOMÁTICOS  
# ===================================

@equipe_bp.route('/api/funcionario/<int:funcionario_id>/horarios', methods=['GET'])
@login_required
@admin_required
def api_get_funcionario_horarios(funcionario_id):
    """API para buscar horários padrão de funcionário baseado no dia da semana"""
    try:
        admin_id = get_admin_id()
        dia_semana = request.args.get('dia_semana', type=int)  # 0=Domingo, 1=Segunda, etc.
        
        # Buscar funcionário
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id, 
            admin_id=admin_id, 
            ativo=True
        ).first()
        
        if not funcionario:
            return jsonify({
                'success': False, 
                'error': 'Funcionário não encontrado'
            }), 404
        
        # Buscar horário de trabalho associado
        horario_trabalho = funcionario.horario_trabalho
        
        if not horario_trabalho:
            # Se não tem horário configurado, retornar padrão
            return jsonify({
                'success': True,
                'funcionario': {
                    'id': funcionario.id,
                    'nome': funcionario.nome,
                    'codigo': funcionario.codigo
                },
                'horarios': {
                    'entrada': '08:00',
                    'saida': '17:00',
                    # LEGACY: Compatibilidade temporária
                    'turno_inicio': '08:00',
                    'turno_fim': '17:00',
                    'tipo_lancamento': 'trabalho_normal',
                    'possui_horario_customizado': False,
                    'observacao': 'Horário padrão aplicado (funcionário sem horário específico configurado)'
                }
            })
        
        # Verificar se funcionário trabalha no dia da semana solicitado
        if dia_semana is not None:
            dias_trabalho = [int(d.strip()) for d in horario_trabalho.dias_semana.split(',') if d.strip()]
            
            trabalha_no_dia = dia_semana in dias_trabalho
            
            # Determinar tipo de lançamento automaticamente
            if not trabalha_no_dia:
                if dia_semana == 0:  # Domingo
                    tipo_lancamento = 'domingo_folga'
                elif dia_semana == 6:  # Sábado
                    tipo_lancamento = 'sabado_folga'
                else:
                    tipo_lancamento = 'falta'  # Dia útil que não trabalha
            else:
                if dia_semana == 0:  # Domingo trabalhado
                    tipo_lancamento = 'domingo_trabalhado'
                elif dia_semana == 6:  # Sábado trabalhado
                    tipo_lancamento = 'sabado_trabalhado'
                else:
                    tipo_lancamento = 'trabalho_normal'
        else:
            # Se não especificou dia, assumir trabalho normal
            tipo_lancamento = 'trabalho_normal'
            trabalha_no_dia = True
        
        # Preparar resposta
        response_data = {
            'success': True,
            'funcionario': {
                'id': funcionario.id,
                'nome': funcionario.nome,
                'codigo': funcionario.codigo
            },
            'horarios': {
                'entrada': horario_trabalho.entrada.strftime('%H:%M'),
                'saida': horario_trabalho.saida.strftime('%H:%M'),
                'almoco_saida': horario_trabalho.saida_almoco.strftime('%H:%M'),
                'almoco_retorno': horario_trabalho.retorno_almoco.strftime('%H:%M'),
                # LEGACY: Compatibilidade temporária
                'turno_inicio': horario_trabalho.entrada.strftime('%H:%M'),
                'turno_fim': horario_trabalho.saida.strftime('%H:%M'),
                'saida_almoco': horario_trabalho.saida_almoco.strftime('%H:%M'),
                'retorno_almoco': horario_trabalho.retorno_almoco.strftime('%H:%M'),
                'horas_diarias': horario_trabalho.horas_diarias,
                'valor_hora': horario_trabalho.valor_hora,
                'tipo_lancamento': tipo_lancamento,
                'trabalha_no_dia': trabalha_no_dia,
                'possui_horario_customizado': True,
                'nome_horario': horario_trabalho.nome,
                'observacao': f'Horários baseados no esquema "{horario_trabalho.nome}"'
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Erro API horários funcionário: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': 'Erro interno do servidor'
        }), 500

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
        allocation.local_trabalho = data.get('local_trabalho', 'campo')  # 'campo' ou 'oficina'
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
        
        # Retornar payload completo para renderização imediata do card
        return jsonify({
            'success': True,
            'allocation': {
                'id': allocation.id,
                'obra_id': allocation.obra_id,
                'obra_codigo': obra.codigo,
                'obra_nome': obra.nome,
                'data_alocacao': data_alocacao.isoformat(),
                'day_of_week': convert_to_sunday_weekday(data_alocacao.weekday()),  # 0=Domingo
                'local_trabalho': allocation.local_trabalho,
                'turno_inicio': allocation.turno_inicio.strftime('%H:%M'),
                'turno_fim': allocation.turno_fim.strftime('%H:%M')
            },
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


@equipe_bp.route('/api/allocation/<int:allocation_id>/funcionarios', methods=['GET'])
@login_required
@admin_required
def api_get_allocation_funcionarios(allocation_id):
    """API REST: Listar funcionários de uma alocação específica"""
    try:
        admin_id = get_admin_id()
        

        allocation = Allocation.query.filter_by(
            id=allocation_id, 
            admin_id=admin_id
        ).first()
        
        if not allocation:
            return jsonify({
                'success': False,
                'error': 'Alocação não encontrada'
            }), 404
        
        # Buscar obra
        obra = Obra.query.filter_by(id=allocation.obra_id, admin_id=admin_id).first()
        
        funcionarios_alocados = db.session.query(AllocationEmployee, Funcionario).join(
            Funcionario, AllocationEmployee.funcionario_id == Funcionario.id
        ).filter(
            AllocationEmployee.allocation_id == allocation_id
        ).order_by(Funcionario.nome).all()
        
        funcionarios_disponiveis = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
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
    """API REST: FASE 2B - Adicionar funcionário com horários completos"""
    try:
        admin_id = get_admin_id()
        data = request.get_json()
        
        logging.info(f"📥 API FASE 2B: Recebendo dados: {data}")

        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        # VALIDAÇÕES BÁSICAS
        allocation_id = data.get('allocation_id')
        funcionario_id = data.get('funcionario_id')
        
        if not allocation_id or not funcionario_id:
            return jsonify({
                'success': False,
                'error': 'Campos obrigatórios: allocation_id, funcionario_id'
            }), 400
        
        # NOVOS CAMPOS FASE 2B
        entrada_str = data.get('entrada')
        inicio_almoco_str = data.get('inicio_almoco')
        fim_almoco_str = data.get('fim_almoco')
        saida_str = data.get('saida')
        percentual_extras = data.get('percentual_extras', 0.0)
        tipo_lancamento = data.get('tipo_lancamento', 'trabalho_normal')
        papel = data.get('papel', '').strip()
        
        # VALIDAÇÕES FASE 2B
        if not entrada_str or not saida_str:
            return jsonify({
                'success': False,
                'error': 'Horários de entrada e saída são obrigatórios'
            }), 400
        
        # Validar percentual de extras
        try:
            percentual_extras = float(percentual_extras)
            if percentual_extras < 0 or percentual_extras > 100:
                raise ValueError("Percentual fora da faixa válida")
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': 'Percentual de extras deve ser um número entre 0 e 100'
            }), 400
        
        # CONVERTER HORÁRIOS
        try:
            entrada = datetime.strptime(entrada_str, '%H:%M').time()
            saida = datetime.strptime(saida_str, '%H:%M').time()
            
            inicio_almoco = None
            fim_almoco = None
            
            if inicio_almoco_str:
                inicio_almoco = datetime.strptime(inicio_almoco_str, '%H:%M').time()
            if fim_almoco_str:
                fim_almoco = datetime.strptime(fim_almoco_str, '%H:%M').time()
                
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Formato de horário inválido. Use HH:MM (ex: 08:00)'
            }), 400
        
        # VALIDAÇÕES DE SEQUÊNCIA DE HORÁRIOS
        if saida <= entrada:
            return jsonify({
                'success': False,
                'error': 'Horário de saída deve ser após entrada'
            }), 400
        
        # Validar almoço se fornecido
        if (inicio_almoco and not fim_almoco) or (not inicio_almoco and fim_almoco):
            return jsonify({
                'success': False,
                'error': 'Preencha ambos os horários de almoço ou deixe ambos vazios'
            }), 400
        
        if inicio_almoco and fim_almoco:
            if inicio_almoco <= entrada:
                return jsonify({
                    'success': False,
                    'error': 'Início do almoço deve ser após entrada'
                }), 400
            if fim_almoco <= inicio_almoco:
                return jsonify({
                    'success': False,
                    'error': 'Fim do almoço deve ser após início'
                }), 400
            if saida <= fim_almoco:
                return jsonify({
                    'success': False,
                    'error': 'Saída deve ser após fim do almoço'
                }), 400

        # VERIFICAR ALOCAÇÃO
        allocation = Allocation.query.filter_by(
            id=allocation_id,
            admin_id=admin_id
        ).first()
        
        if not allocation:
            return jsonify({
                'success': False,
                'error': 'Alocação não encontrada'
            }), 404
        
        # VERIFICAR FUNCIONÁRIO
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
        
        # VERIFICAR DUPLICAÇÃO
        existing = AllocationEmployee.query.filter_by(
            allocation_id=allocation_id,
            funcionario_id=funcionario_id
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': f'Funcionário {funcionario.nome} já está alocado nesta obra/dia'
            }), 409
        
        # VERIFICAR CONFLITO DE DATA
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
        
        # CRIAR ALLOCATION EMPLOYEE FASE 2B
        allocation_employee = AllocationEmployee()
        allocation_employee.allocation_id = allocation_id
        allocation_employee.funcionario_id = funcionario_id
        
        # HORÁRIOS COMPLETOS FASE 2B
        allocation_employee.turno_inicio = entrada  # Manter compatibilidade
        allocation_employee.turno_fim = saida      # Manter compatibilidade
        
        # MAPPING CORRETO PARA CAMPOS DO BANCO - FASE 2B
        # Campo lunch mapping correto: inicio_almoco→hora_almoco_saida, fim_almoco→hora_almoco_retorno
        allocation_employee.hora_almoco_saida = inicio_almoco      # Campo correto do modelo
        allocation_employee.hora_almoco_retorno = fim_almoco       # Campo correto do modelo
        allocation_employee.percentual_extras = percentual_extras  # Campo existe no modelo
        allocation_employee.tipo_lancamento = tipo_lancamento      # Campo existe no modelo
        
        allocation_employee.papel = papel or (funcionario.funcao_ref.nome if funcionario.funcao_ref else '')
        allocation_employee.observacao = data.get('observacao', '')
        
        # CÁLCULO AUTOMÁTICO DE HORAS (para logs)
        entrada_minutes = entrada.hour * 60 + entrada.minute
        saida_minutes = saida.hour * 60 + saida.minute
        total_minutes = saida_minutes - entrada_minutes
        
        pausa_minutes = 0
        if inicio_almoco and fim_almoco:
            pausa_minutes = (fim_almoco.hour * 60 + fim_almoco.minute) - (inicio_almoco.hour * 60 + inicio_almoco.minute)
        
        liquido_minutes = total_minutes - pausa_minutes
        com_extras_minutes = liquido_minutes * (1 + percentual_extras / 100)
        
        logging.info(f"💰 FASE 2B: Cálculo de horas para {funcionario.nome}:")
        logging.info(f"   - Total: {total_minutes//60}h{total_minutes%60:02d}m")
        logging.info(f"   - Pausa: {pausa_minutes//60}h{pausa_minutes%60:02d}m")
        logging.info(f"   - Líquido: {liquido_minutes//60}h{liquido_minutes%60:02d}m")
        logging.info(f"   - Com extras ({percentual_extras}%): {com_extras_minutes//60:.0f}h{com_extras_minutes%60:02.0f}m")
        
        db.session.add(allocation_employee)
        db.session.commit()
        
        # BUSCAR OBRA PARA RETORNO
        obra = Obra.query.filter_by(id=allocation.obra_id, admin_id=admin_id).first()
        
        # RETORNO COMPLETO FASE 2B
        response_data = {
            'success': True,
            'allocation_employee_id': allocation_employee.id,
            'funcionario_nome': funcionario.nome,
            'funcionario_codigo': funcionario.codigo,
            'obra_codigo': obra.codigo if obra else f"#{allocation.obra_id}",
            'data_alocacao': allocation.data_alocacao.isoformat(),
            # Horários completos
            'entrada': allocation_employee.turno_inicio.strftime('%H:%M'),
            'inicio_almoco': allocation_employee.hora_almoco_saida.strftime('%H:%M') if allocation_employee.hora_almoco_saida else None,
            'fim_almoco': allocation_employee.hora_almoco_retorno.strftime('%H:%M') if allocation_employee.hora_almoco_retorno else None,
            'saida': allocation_employee.turno_fim.strftime('%H:%M'),
            'percentual_extras': percentual_extras,
            'tipo_lancamento': tipo_lancamento,
            'papel': allocation_employee.papel,
            # Para compatibilidade
            'turno_inicio': allocation_employee.turno_inicio.strftime('%H:%M'),
            'turno_fim': allocation_employee.turno_fim.strftime('%H:%M'),
            # Cálculos de horas
            'total_horas': f"{total_minutes//60}h{total_minutes%60:02d}m",
            'horas_liquidas': f"{liquido_minutes//60}h{liquido_minutes%60:02d}m",
            'horas_com_extras': f"{com_extras_minutes//60:.0f}h{com_extras_minutes%60:02.0f}m",
            'message': f'Funcionário {funcionario.nome} adicionado com horários completos!'
        }
        
        logging.info(f"✅ FASE 2B: Funcionário {funcionario.nome} alocado com sucesso!")
        
        return jsonify(response_data), 201
        
    except IntegrityError:
        db.session.rollback()
        logging.error(f"❌ FASE 2B: Erro de integridade")
        return jsonify({
            'success': False,
            'error': 'Erro de integridade: funcionário já pode estar alocado'
        }), 409
    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ FASE 2B API ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro interno do servidor: {str(e)}'
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
            'entrada': alloc_emp.turno_inicio.strftime('%H:%M'),
            'saida': alloc_emp.turno_fim.strftime('%H:%M'),
            # LEGACY: Compatibilidade temporária
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

@equipe_bp.route('/api/sync-ponto', methods=['POST'])
@login_required
@admin_required
def api_sincronizar_ponto_manual():
    """API: Sincronização manual de ponto para funcionários alocados"""
    try:
        from models import processar_lancamentos_automaticos
        
        admin_id = get_admin_id()
        data = request.get_json() or {}
        
        # Data opcional para processamento (padrão: ontem)
        data_processamento = None
        if data.get('data_processamento'):
            try:
                data_processamento = datetime.strptime(data['data_processamento'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Formato de data inválido. Use YYYY-MM-DD'
                }), 400
        
        # Executar processamento automático com admin_id para isolamento
        sucesso = processar_lancamentos_automaticos(data_processamento, admin_id)
        
        if sucesso:
            data_str = data_processamento.isoformat() if data_processamento else 'ontem'
            return jsonify({
                'success': True,
                'message': f'Sincronização de ponto processada com sucesso para {data_str}',
                'data_processada': data_str
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar sincronização automática de ponto'
            }), 500
            
    except Exception as e:
        logging.error(f"API SYNC PONTO ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

@equipe_bp.route('/api/allocation-employee/<int:allocation_employee_id>/sync-horario', methods=['POST'])
@login_required
@admin_required
def api_sincronizar_horario_funcionario(allocation_employee_id):
    """API: Aplicar horário do funcionário na alocação"""
    try:
        from models import sincronizar_alocacao_com_horario_funcionario
        
        admin_id = get_admin_id()
        
        # Verificar se allocation_employee pertence ao admin
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
        funcionario = Funcionario.query.get(alloc_emp.funcionario_id)
        
        if not funcionario or not funcionario.horario_trabalho:
            return jsonify({
                'success': False,
                'error': 'Funcionário não possui horário de trabalho cadastrado'
            }), 400
        
        # Sincronizar horário com admin_id para isolamento
        sucesso = sincronizar_alocacao_com_horario_funcionario(allocation_employee_id, admin_id)
        
        if sucesso:
            # Buscar dados atualizados
            alloc_emp_updated = AllocationEmployee.query.get(allocation_employee_id)
            if alloc_emp_updated:
                return jsonify({
                    'success': True,
                    'entrada': alloc_emp_updated.turno_inicio.strftime('%H:%M'),
                    'saida': alloc_emp_updated.turno_fim.strftime('%H:%M'),
                    # LEGACY: Compatibilidade temporária
                    'turno_inicio': alloc_emp_updated.turno_inicio.strftime('%H:%M'),
                    'turno_fim': alloc_emp_updated.turno_fim.strftime('%H:%M'),
                    'tipo_lancamento': alloc_emp_updated.tipo_lancamento,
                    'message': f'Horário do funcionário {funcionario.nome} aplicado com sucesso'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Erro ao buscar dados atualizados'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao aplicar horário do funcionário'
            }), 500
            
    except Exception as e:
        logging.error(f"API SYNC HORARIO ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500