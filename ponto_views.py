# ================================
# BLUEPRINT DE PONTO - CELULAR COMPARTILHADO
# Sistema de Ponto Eletrônico SIGE v8.0
# ================================

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from app import db
from models import Obra, Funcionario, RegistroPonto, ConfiguracaoHorario, DispositivoObra, FuncionarioObrasPonto
from ponto_service import PontoService
from multitenant_helper import get_admin_id as get_tenant_admin_id
from decorators import admin_required
import logging

logger = logging.getLogger(__name__)

ponto_bp = Blueprint('ponto', __name__, url_prefix='/ponto')


@ponto_bp.route('/')
@login_required
def index():
    """Página inicial do ponto - lista todos os funcionários ativos"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar todos os funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Para cada funcionário, verificar se já bateu ponto hoje
        hoje = date.today()
        funcionarios_com_status = []
        
        for func in funcionarios:
            registro_hoje = RegistroPonto.query.filter_by(
                funcionario_id=func.id,
                data=hoje,
                admin_id=admin_id
            ).first()
            
            funcionarios_com_status.append({
                'funcionario': func,
                'registro_hoje': registro_hoje
            })
        
        return render_template('ponto/lista_funcionarios.html',
                             funcionarios=funcionarios_com_status,
                             hoje=hoje)
        
    except Exception as e:
        logger.error(f"Erro ao listar funcionários: {e}")
        flash(f'Erro ao carregar funcionários: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@ponto_bp.route('/funcionario/<int:funcionario_id>')
@login_required
def bater_ponto_funcionario(funcionario_id):
    """Página de batida de ponto individual - mostra horário e dropdown de obras"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se funcionário existe e pertence ao admin
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first_or_404()
        
        # Buscar registro de ponto de hoje
        hoje = date.today()
        registro_hoje = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=hoje,
            admin_id=admin_id
        ).first()
        
        # Buscar obras configuradas para o funcionário
        obras_configuradas = FuncionarioObrasPonto.query.filter_by(
            funcionario_id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).all()
        
        # Se tem obras configuradas, mostrar apenas essas. Caso contrário, todas as ativas
        if obras_configuradas:
            obras_ids = [config.obra_id for config in obras_configuradas]
            obras = Obra.query.filter(
                Obra.id.in_(obras_ids),
                Obra.admin_id == admin_id,
                Obra.ativo == True
            ).order_by(Obra.nome).all()
        else:
            # Sem configuração específica: mostrar todas as obras ativas
            obras = Obra.query.filter_by(
                admin_id=admin_id,
                ativo=True
            ).order_by(Obra.nome).all()
        
        # Horário atual
        agora = datetime.now()
        
        return render_template('ponto/bater_ponto_individual.html',
                             funcionario=funcionario,
                             registro_hoje=registro_hoje,
                             obras=obras,
                             agora=agora,
                             hoje=hoje)
        
    except Exception as e:
        logger.error(f"Erro ao carregar página de batida de ponto: {e}")
        flash(f'Erro ao carregar página: {str(e)}', 'error')
        return redirect(url_for('ponto.index'))


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
        
        # ✅ FIX: Aceitar 'motivo' OU 'tipo_registro' para compatibilidade
        motivo = data.get('motivo') or data.get('tipo_registro', 'falta')  # 'falta' ou 'falta_justificada'
        observacoes = data.get('observacoes')
        
        logger.info(f"📝 Registrando falta: funcionario={funcionario_id}, data={data_falta}, tipo={motivo}")
        
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
        
        # Buscar obras ativas
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Total de funcionários ativos (qualquer um pode bater ponto em qualquer obra)
        total_funcionarios_ativos = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).count()
        
        # Contar funcionários que já bateram ponto hoje em cada obra
        obras_com_dados = []
        hoje = date.today()
        
        for obra in obras:
            registros_hoje = RegistroPonto.query.filter_by(
                obra_id=obra.id,
                data=hoje,
                admin_id=admin_id
            ).count()
            
            obras_com_dados.append({
                'obra': obra,
                'registros_hoje': registros_hoje,
                'total_funcionarios': total_funcionarios_ativos
            })
        
        return render_template('ponto/lista_obras.html',
                             obras_com_dados=obras_com_dados)
        
    except Exception as e:
        logger.error(f"Erro ao listar obras: {e}")
        flash(f'Erro ao carregar obras: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@ponto_bp.route('/configuracao/funcionario/<int:funcionario_id>/obras', methods=['GET', 'POST'])
@login_required
@admin_required
def configurar_obras_funcionario(funcionario_id):
    """Configurar quais obras aparecem no dropdown de ponto para o funcionário"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se funcionário existe e pertence ao admin
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first_or_404()
        
        if request.method == 'POST':
            # Receber lista de obras selecionadas
            obras_selecionadas = request.form.getlist('obras_ids')
            
            # Remover configurações antigas
            FuncionarioObrasPonto.query.filter_by(
                funcionario_id=funcionario_id,
                admin_id=admin_id
            ).delete()
            
            # Adicionar novas configurações
            for obra_id in obras_selecionadas:
                config = FuncionarioObrasPonto(
                    funcionario_id=funcionario_id,
                    obra_id=int(obra_id),
                    admin_id=admin_id,
                    ativo=True
                )
                db.session.add(config)
            
            db.session.commit()
            flash('Obras configuradas com sucesso!', 'success')
            return redirect(url_for('ponto.configurar_obras_funcionario', funcionario_id=funcionario_id))
        
        # GET - Mostrar formulário
        # Buscar todas as obras ativas
        todas_obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        # Buscar obras já configuradas para o funcionário
        obras_configuradas = FuncionarioObrasPonto.query.filter_by(
            funcionario_id=funcionario_id,
            admin_id=admin_id,
            ativo=True
        ).all()
        
        obras_ids_selecionadas = [config.obra_id for config in obras_configuradas]
        
        return render_template('ponto/configurar_obras_funcionario.html',
                             funcionario=funcionario,
                             todas_obras=todas_obras,
                             obras_ids_selecionadas=obras_ids_selecionadas)
        
    except Exception as e:
        logger.error(f"Erro ao configurar obras do funcionário: {e}")
        flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('ponto.index'))


@ponto_bp.route('/configuracao/obras-funcionarios')
@login_required
@admin_required
def listar_configuracoes():
    """Lista todos os funcionários com suas obras configuradas"""
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar todos os funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Para cada funcionário, buscar obras configuradas
        funcionarios_configs = []
        for func in funcionarios:
            configs = FuncionarioObrasPonto.query.filter_by(
                funcionario_id=func.id,
                admin_id=admin_id,
                ativo=True
            ).all()
            
            obras = [config.obra for config in configs]
            
            funcionarios_configs.append({
                'funcionario': func,
                'obras_configuradas': obras,
                'total_obras': len(obras)
            })
        
        return render_template('ponto/listar_configuracoes.html',
                             funcionarios_configs=funcionarios_configs)
        
    except Exception as e:
        logger.error(f"Erro ao listar configurações: {e}")
        flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


# ================================
# IMPORTAÇÃO DE PONTOS VIA EXCEL
# ================================

@ponto_bp.route('/importar')
@login_required
@admin_required
def pagina_importar():
    """Página de importação de pontos via Excel"""
    return render_template('ponto/importar_ponto.html')


@ponto_bp.route('/importar/download-modelo')
@login_required
@admin_required
def download_modelo():
    """Gera e faz download da planilha modelo Excel"""
    from services.ponto_importacao import PontoExcelService
    from flask import make_response
    
    try:
        admin_id = get_tenant_admin_id()
        
        # Buscar funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.codigo).all()
        
        if not funcionarios:
            flash('Nenhum funcionário ativo encontrado para gerar o modelo.', 'warning')
            return redirect(url_for('ponto.pagina_importar'))
        
        # Buscar obras ativas
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativa=True
        ).order_by(Obra.nome).all()
        
        # Gerar planilha com obras
        excel_buffer = PontoExcelService.gerar_planilha_modelo(funcionarios, obras)
        
        # Criar response
        response = make_response(excel_buffer.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=modelo_ponto_{date.today().strftime("%Y%m")}.xlsx'
        
        logger.info(f"Admin {admin_id} baixou modelo de importação com {len(funcionarios)} funcionários")
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao gerar planilha modelo: {e}", exc_info=True)
        flash(f'Erro ao gerar planilha modelo: {str(e)}', 'error')
        return redirect(url_for('ponto.pagina_importar'))


@ponto_bp.route('/importar/processar', methods=['POST'])
@login_required
@admin_required
def processar_importacao():
    """Processa upload e importação da planilha Excel"""
    from services.ponto_importacao import PontoExcelService
    from werkzeug.utils import secure_filename
    from io import BytesIO
    
    try:
        admin_id = get_tenant_admin_id()
        
        # Verificar se arquivo foi enviado
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo foi enviado.', 'error')
            return redirect(url_for('ponto.pagina_importar'))
        
        file = request.files['arquivo']
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('ponto.pagina_importar'))
        
        # Validar extensão
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            flash('Formato de arquivo inválido. Envie um arquivo Excel (.xlsx ou .xls).', 'error')
            return redirect(url_for('ponto.pagina_importar'))
        
        # Ler arquivo
        excel_file = BytesIO(file.read())
        
        # Criar mapa de funcionários ativos (código -> id)
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).all()
        
        funcionarios_map = {func.codigo: func.id for func in funcionarios}
        
        # Validar e preparar dados
        registros_validos, erros = PontoExcelService.validar_e_importar(
            excel_file,
            funcionarios_map,
            admin_id
        )
        
        # Importar registros válidos
        total_importados = 0
        total_duplicados = 0
        total_atualizados = 0
        
        for registro in registros_validos:
            # Verificar se já existe registro para este funcionário nesta data
            registro_existente = RegistroPonto.query.filter_by(
                funcionario_id=registro['funcionario_id'],
                data=registro['data'],
                admin_id=admin_id
            ).first()
            
            if registro_existente:
                # Atualizar registro existente
                registro_existente.hora_entrada = registro['hora_entrada']
                registro_existente.hora_saida = registro['hora_saida']
                registro_existente.hora_almoco_saida = registro['hora_almoco_saida']
                registro_existente.hora_almoco_retorno = registro['hora_almoco_retorno']
                total_atualizados += 1
            else:
                # Criar novo registro
                novo_registro = RegistroPonto(**registro)
                db.session.add(novo_registro)
                total_importados += 1
        
        # Commit
        db.session.commit()
        
        # Mensagem de resultado
        mensagens = []
        if total_importados > 0:
            mensagens.append(f"{total_importados} novos registros importados")
        if total_atualizados > 0:
            mensagens.append(f"{total_atualizados} registros atualizados")
        if erros:
            mensagens.append(f"{len(erros)} erros encontrados")
        
        if total_importados > 0 or total_atualizados > 0:
            flash(f"✅ Importação concluída: {', '.join(mensagens)}", 'success')
        
        if erros:
            # Limitar erros exibidos para não sobrecarregar a interface
            erros_exibir = erros[:10]
            for erro in erros_exibir:
                flash(f"⚠️ {erro}", 'warning')
            
            if len(erros) > 10:
                flash(f"... e mais {len(erros) - 10} erros.", 'warning')
        
        logger.info(
            f"Admin {admin_id} importou pontos: "
            f"{total_importados} novos, {total_atualizados} atualizados, {len(erros)} erros"
        )
        
        return redirect(url_for('ponto.pagina_importar'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao processar importação: {e}", exc_info=True)
        flash(f'Erro ao processar importação: {str(e)}', 'error')
        return redirect(url_for('ponto.pagina_importar'))
