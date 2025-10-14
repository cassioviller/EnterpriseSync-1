# ================================
# BLUEPRINT DE PONTO - CELULAR COMPARTILHADO
# Sistema de Ponto Eletrônico SIGE v8.0
# ================================

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from app import db
from models import Obra, Funcionario, RegistroPonto, ConfiguracaoHorario, DispositivoObra
from ponto_service import PontoService
from multitenant_helper import get_admin_id as get_tenant_admin_id
from decorators import admin_required
import logging

logger = logging.getLogger(__name__)

ponto_bp = Blueprint('ponto', __name__, url_prefix='/ponto')


@ponto_bp.route('/')
@login_required
def index():
    """Rota raiz do ponto - redireciona para lista de obras"""
    return redirect(url_for('ponto.lista_obras'))


@ponto_bp.route('/obra/<int:obra_id>')
@login_required
def obra_dashboard(obra_id):
    """Tela principal do celular da obra - mostra todos os funcionários"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se obra existe e pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
        
        # Obter status de todos os funcionários
        status_funcionarios = PontoService.obter_status_obra(obra_id)
        
        # Estatísticas do dia
        total_funcionarios = len(status_funcionarios)
        presentes = len([f for f in status_funcionarios if f['registro'] and f['registro'].hora_entrada])
        faltaram = total_funcionarios - presentes
        atrasados = len([f for f in status_funcionarios if f['registro'] and f['registro'].minutos_atraso_entrada and f['registro'].minutos_atraso_entrada > 0])
        
        estatisticas = {
            'total_funcionarios': total_funcionarios,
            'presentes': presentes,
            'faltaram': faltaram,
            'atrasados': atrasados
        }
        
        return render_template('ponto/obra_dashboard.html',
                             obra=obra,
                             funcionarios=status_funcionarios,
                             estatisticas=estatisticas,
                             hoje=date.today())
        
    except Exception as e:
        logger.error(f"Erro no dashboard da obra: {e}")
        flash(f'Erro ao carregar dashboard: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@ponto_bp.route('/api/bater-ponto', methods=['POST'])
@login_required
def api_bater_ponto():
    """API para registrar ponto via celular da obra"""
    try:
        data = request.get_json()
        
        funcionario_id = data.get('funcionario_id')
        tipo_ponto = data.get('tipo_ponto')
        obra_id = data.get('obra_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not all([funcionario_id, tipo_ponto, obra_id]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios não informados'}), 400
        
        resultado = PontoService.bater_ponto_obra(
            funcionario_id=funcionario_id,
            tipo_ponto=tipo_ponto,
            obra_id=obra_id,
            latitude=latitude,
            longitude=longitude
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Erro na API de bater ponto: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/api/status-obra/<int:obra_id>')
@login_required
def api_status_obra(obra_id):
    """API para obter status atualizado da obra"""
    try:
        status_funcionarios = PontoService.obter_status_obra(obra_id)
        
        # Serializar dados para JSON
        funcionarios_json = []
        for item in status_funcionarios:
            funcionario_data = {
                'id': item['funcionario'].id,
                'nome': item['funcionario'].nome,
                'funcao': item['funcionario'].funcao.nome if item['funcionario'].funcao else 'N/A',
                'proximo_ponto': item['proximo_ponto'],
                'status_visual': item['status_visual'],
                'horas_ate_agora': str(item['horas_ate_agora']) if item['horas_ate_agora'] else '0:00:00'
            }
            
            if item['registro']:
                funcionario_data['registro'] = {
                    'entrada': item['registro'].hora_entrada.strftime('%H:%M') if item['registro'].hora_entrada else None,
                    'saida_almoco': item['registro'].hora_almoco_saida.strftime('%H:%M') if item['registro'].hora_almoco_saida else None,
                    'volta_almoco': item['registro'].hora_almoco_retorno.strftime('%H:%M') if item['registro'].hora_almoco_retorno else None,
                    'saida': item['registro'].hora_saida.strftime('%H:%M') if item['registro'].hora_saida else None,
                    'horas_trabalhadas': f"{item['registro'].horas_trabalhadas:.2f}" if item['registro'].horas_trabalhadas else None,
                    'horas_extras': f"{item['registro'].horas_extras:.2f}" if item['registro'].horas_extras else None,
                    'minutos_atraso': item['registro'].minutos_atraso_entrada if item['registro'].minutos_atraso_entrada else 0
                }
            else:
                funcionario_data['registro'] = None
            
            funcionarios_json.append(funcionario_data)
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_json,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro na API de status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/api/registrar-falta', methods=['POST'])
@login_required
@admin_required
def api_registrar_falta():
    """API para registrar falta de funcionário"""
    try:
        data = request.get_json()
        
        funcionario_id = data.get('funcionario_id')
        data_falta_str = data.get('data')
        data_falta = datetime.strptime(data_falta_str, '%Y-%m-%d').date()
        motivo = data.get('motivo', 'falta')  # 'falta' ou 'falta_justificada'
        observacoes = data.get('observacoes')
        
        resultado = PontoService.registrar_falta(
            funcionario_id=funcionario_id,
            data_falta=data_falta,
            motivo=motivo,
            observacoes=observacoes
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Erro ao registrar falta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/relatorio/obra/<int:obra_id>')
@login_required
def relatorio_obra(obra_id):
    """Relatório de ponto da obra"""
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
        
        # Filtros de data
        data_inicio_str = request.args.get('data_inicio')
        data_fim_str = request.args.get('data_fim')
        
        if not data_inicio_str:
            data_inicio = date.today().replace(day=1)  # Primeiro dia do mês
        else:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        
        if not data_fim_str:
            data_fim = date.today()
        else:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        # Buscar registros do período
        registros = RegistroPonto.query.filter(
            RegistroPonto.obra_id == obra_id,
            RegistroPonto.admin_id == admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(
            RegistroPonto.data.desc(),
            RegistroPonto.funcionario_id
        ).all()
        
        # Agrupar por funcionário
        funcionarios_dados = {}
        for registro in registros:
            func_id = registro.funcionario_id
            if func_id not in funcionarios_dados:
                funcionarios_dados[func_id] = {
                    'funcionario': registro.funcionario,
                    'registros': [],
                    'total_horas': 0.0,
                    'total_extras': 0.0,
                    'total_faltas': 0,
                    'total_atrasados': 0
                }
            
            funcionarios_dados[func_id]['registros'].append(registro)
            
            if registro.horas_trabalhadas:
                funcionarios_dados[func_id]['total_horas'] += registro.horas_trabalhadas
            
            if registro.horas_extras:
                funcionarios_dados[func_id]['total_extras'] += registro.horas_extras
            
            if registro.tipo_registro in ['falta', 'falta_justificada']:
                funcionarios_dados[func_id]['total_faltas'] += 1
            
            if registro.minutos_atraso_entrada and registro.minutos_atraso_entrada > 0:
                funcionarios_dados[func_id]['total_atrasados'] += 1
        
        return render_template('ponto/relatorio_obra.html',
                             obra=obra,
                             funcionarios_dados=funcionarios_dados,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"Erro no relatório da obra: {e}")
        flash(f'Erro ao gerar relatório: {str(e)}', 'error')
        return redirect(url_for('ponto.obra_dashboard', obra_id=obra_id))


@ponto_bp.route('/configuracao/obra/<int:obra_id>')
@login_required
@admin_required
def configuracao_obra(obra_id):
    """Configuração de horários da obra"""
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
        
        # Buscar ou criar configuração
        config = ConfiguracaoHorario.query.filter_by(
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not config:
            config = ConfiguracaoHorario(
                obra_id=obra_id,
                admin_id=admin_id
            )
        
        return render_template('ponto/configuracao_obra.html',
                             obra=obra,
                             config=config)
        
    except Exception as e:
        logger.error(f"Erro na configuração da obra: {e}")
        flash(f'Erro ao carregar configuração: {str(e)}', 'error')
        return redirect(url_for('ponto.obra_dashboard', obra_id=obra_id))


@ponto_bp.route('/api/salvar-configuracao', methods=['POST'])
@login_required
@admin_required
def api_salvar_configuracao():
    """API para salvar configuração de horários"""
    try:
        data = request.get_json()
        admin_id = get_tenant_admin_id()
        
        obra_id = data.get('obra_id')
        entrada_padrao = datetime.strptime(data.get('entrada_padrao'), '%H:%M').time()
        saida_padrao = datetime.strptime(data.get('saida_padrao'), '%H:%M').time()
        almoco_inicio = datetime.strptime(data.get('almoco_inicio'), '%H:%M').time()
        almoco_fim = datetime.strptime(data.get('almoco_fim'), '%H:%M').time()
        tolerancia_atraso = int(data.get('tolerancia_atraso', 15))
        carga_horaria_diaria = int(data.get('carga_horaria_diaria', 480))
        
        # Buscar ou criar configuração
        config = ConfiguracaoHorario.query.filter_by(
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not config:
            config = ConfiguracaoHorario(
                obra_id=obra_id,
                admin_id=admin_id
            )
            db.session.add(config)
        
        config.entrada_padrao = entrada_padrao
        config.saida_padrao = saida_padrao
        config.almoco_inicio = almoco_inicio
        config.almoco_fim = almoco_fim
        config.tolerancia_atraso = tolerancia_atraso
        config.carga_horaria_diaria = carga_horaria_diaria
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuração salva com sucesso'})
        
    except Exception as e:
        logger.error(f"Erro ao salvar configuração: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@ponto_bp.route('/lista-obras')
@login_required
def lista_obras():
    """Lista de obras para seleção do ponto"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar obras ativas com funcionários
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Contar funcionários por obra
        obras_com_dados = []
        for obra in obras:
            total_func = Funcionario.query.filter_by(
                obra_atual_id=obra.id,
                admin_id=admin_id,
                ativo=True
            ).count()
            
            obras_com_dados.append({
                'obra': obra,
                'total_funcionarios': total_func
            })
        
        return render_template('ponto/lista_obras.html',
                             obras_com_dados=obras_com_dados)
        
    except Exception as e:
        logger.error(f"Erro ao listar obras: {e}")
        flash(f'Erro ao carregar obras: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))
