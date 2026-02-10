from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, send_file, session, Response
from flask_login import login_required, current_user
from models import db, Usuario, TipoUsuario, Funcionario, Funcao, Departamento, HorarioTrabalho, Obra, RDO, RDOMaoObra, RDOEquipamento, RDOOcorrencia, RDOFoto, AlocacaoEquipe, Servico, ServicoObra, ServicoObraReal, RDOServicoSubatividade, SubatividadeMestre, RegistroPonto, NotificacaoCliente
from auth import admin_required
from utils.tenant import get_tenant_admin_id
from utils import calcular_valor_hora_periodo
from utils.database_diagnostics import capture_db_errors
from views.helpers import safe_db_operation, get_admin_id_robusta, get_admin_id_dinamico
from datetime import datetime, date, timedelta
import calendar
from sqlalchemy import func, desc, or_, and_, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
import os
import json
import logging

from views import main_bp

logger = logging.getLogger(__name__)

try:
    from utils.circuit_breaker import circuit_breaker, pdf_generation_fallback, database_query_fallback
except ImportError:
    def circuit_breaker(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# ===== APIs PARA FRONTEND =====
@main_bp.route('/api/funcionarios')
def api_funcionarios_consolidada():
    """API CONSOLIDADA para funcionários - Unifica admin e mobile"""
    try:
        # Determinar admin_id usando lógica unificada
        admin_id = None
        formato_retorno = request.args.get('formato', 'admin')  # 'admin' ou 'mobile'
        
        if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
            if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
                # Super Admin pode escolher admin_id via parâmetro
                admin_id_param = request.args.get('admin_id')
                if admin_id_param:
                    try:
                        admin_id = int(admin_id_param)
                    except:
                        # Se não conseguir converter, buscar todos
                        admin_id = None
                else:
                    # Buscar admin com mais funcionários ativos
                    from sqlalchemy import text
                    admin_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
                    admin_id = admin_counts[0] if admin_counts else 10
                    
                # Super Admin vê funcionários de admin específico ou todos
                if admin_id:
                    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
                else:
                    funcionarios = Funcionario.query.filter_by(ativo=True).all()
                    
            elif current_user.tipo_usuario == TipoUsuario.ADMIN:
                admin_id = current_user.id
                funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
            else:
                admin_id = current_user.admin_id or 10
                funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        else:
            # Sistema de bypass para produção - buscar admin com mais funcionários
            try:
                from sqlalchemy import text
                admin_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
                admin_id = admin_counts[0] if admin_counts else 10
                funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
            except Exception as e:
                logger.error(f"Erro ao detectar admin_id automaticamente: {e}")
                admin_id = 10
                funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        
                logger.debug(f"DEBUG API FUNCIONÁRIOS: {len(funcionarios)} funcionários para admin_id={admin_id}, formato={formato_retorno}")
        
        # Converter para JSON baseado no formato solicitado
        funcionarios_json = []
        for f in funcionarios:
            try:
                if formato_retorno == 'mobile':
                    # Formato mobile simplificado
                    # PROTEÇÃO: Verificar referências com segurança
                    funcao_nome = 'N/A'
                    departamento_nome = 'N/A'
                    
                    try:
                        funcao_nome = f.funcao_ref.nome if hasattr(f, 'funcao_ref') and f.funcao_ref else 'N/A'
                    except:
                        funcao_nome = 'N/A'
                    
                    try:
                        departamento_nome = f.departamento_ref.nome if hasattr(f, 'departamento_ref') and f.departamento_ref else 'N/A'
                    except:
                        departamento_nome = 'N/A'
                    
                    funcionarios_json.append({
                        'id': f.id,
                        'nome': f.nome or 'Sem nome',
                        'funcao': funcao_nome,
                        'departamento': departamento_nome
                    })
                else:
                    # Formato admin completo (padrão) - PROTEGIDO
                    cargo_nome = 'Sem cargo'
                    departamento_nome = 'Sem departamento'
                    
                    try:
                        cargo_nome = f.funcao_ref.nome if hasattr(f, 'funcao_ref') and f.funcao_ref else 'Sem cargo'
                    except:
                        cargo_nome = 'Sem cargo'
                        
                    try:
                        departamento_nome = f.departamento_ref.nome if hasattr(f, 'departamento_ref') and f.departamento_ref else 'Sem departamento'
                    except:
                        departamento_nome = 'Sem departamento'
                    
                    funcionarios_json.append({
                        'id': f.id,
                        'nome': f.nome or 'Sem nome',
                        'email': f.email or '',
                        'departamento': departamento_nome,
                        'cargo': cargo_nome,
                        'salario': f.salario or 0,
                        'admin_id': f.admin_id,
                        'ativo': f.ativo
                    })
            except Exception as e:
                logger.error(f"[WARN] ERRO ao processar funcionário {f.id}: {e}")
                # Adicionar funcionário básico mesmo com erro
                funcionarios_json.append({
                    'id': f.id,
                    'nome': f.nome or 'Funcionário',
                    'cargo': 'Funcionário',
                    'departamento': 'Sem departamento',
                    'email': '',
                    'salario': 0,
                    'admin_id': f.admin_id,
                    'ativo': f.ativo
                })
                continue
        
        # Retorno adaptado ao formato - SEMPRE COM SUCCESS
        if formato_retorno == 'mobile':
            return jsonify({
                'success': True,
                'funcionarios': funcionarios_json,
                'total': len(funcionarios_json)
            })
        else:
            # [OK] CORREÇÃO: Frontend espera formato com success
            return jsonify({
                'success': True,
                'funcionarios': funcionarios_json,
                'total': len(funcionarios_json)
            })
        
    except Exception as e:
        logger.error(f"ERRO API FUNCIONÁRIOS CONSOLIDADA: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if formato_retorno == 'mobile':
            return jsonify({
                'success': False,
                'error': str(e),
                'funcionarios': []
            }), 500
        else:
            # [OK] CORREÇÃO: Retornar erro padronizado também para admin
            return jsonify({
                'success': False,
                'error': str(e),
                'funcionarios': []
            }), 500

@main_bp.route('/api/funcao/<int:funcao_id>')
@login_required
def api_funcao(funcao_id):
    """API para retornar dados de uma função específica"""
    try:
        # Funcao não tem admin_id - é compartilhado entre todos os tenants
        funcao = Funcao.query.filter_by(id=funcao_id).first()
        
        if not funcao:
            return jsonify({
                'success': False,
                'error': 'Função não encontrada'
            }), 404
        
        return jsonify({
            'success': True,
            'funcao': {
                'id': funcao.id,
                'nome': funcao.nome,
                'descricao': funcao.descricao,
                'salario_base': float(funcao.salario_base) if funcao.salario_base else 0.0
            }
        })
        
    except Exception as e:
        logger.error(f"ERRO API FUNCAO: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== NOVAS ROTAS PARA CORRIGIR FUNCIONÁRIOS =====

@main_bp.route('/api/ponto/lancamento-multiplo', methods=['POST'])
@login_required
def api_ponto_lancamento_multiplo():
    """API para lançamento múltiplo de ponto - processa período de datas para múltiplos funcionários"""
    try:
        data = request.get_json()
        logger.debug(f"[CONFIG] DEBUG LANÇAMENTO MÚLTIPLO: Dados recebidos: {data}")
        
        # Aceitar tanto 'funcionarios' (frontend) quanto 'funcionarios_ids' (legacy)
        funcionarios_ids = data.get('funcionarios', []) or data.get('funcionarios_ids', [])
        obra_id = data.get('obra_id')
        
        # Aceitar período (frontend) ou data única (legacy)
        periodo_inicio = data.get('periodo_inicio')
        periodo_fim = data.get('periodo_fim')
        data_unica = data.get('data')
        
        if not funcionarios_ids:
            return jsonify({'success': False, 'message': 'Nenhum funcionário selecionado'}), 400
        
        if not obra_id:
            return jsonify({'success': False, 'message': 'Obra não selecionada'}), 400
        
        # Determinar datas a processar
        if periodo_inicio and periodo_fim:
            data_inicio = datetime.strptime(periodo_inicio, '%Y-%m-%d').date()
            data_final = datetime.strptime(periodo_fim, '%Y-%m-%d').date()
        elif data_unica:
            data_inicio = datetime.strptime(data_unica, '%Y-%m-%d').date()
            data_final = data_inicio
        else:
            return jsonify({'success': False, 'message': 'Período ou data não informado'}), 400
        
        # Obter admin_id
        admin_id = get_tenant_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        # Validar obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            return jsonify({'success': False, 'message': 'Obra não encontrada ou não pertence ao seu cadastro'}), 403
        
            logger.debug(f"[CONFIG] DEBUG: admin_id={admin_id}, obra_id={obra_id}, funcionarios={funcionarios_ids}, periodo={data_inicio} a {data_final}")
        
        # Extrair horários do request
        hora_entrada = data.get('hora_entrada') or None
        hora_saida = data.get('hora_saida') or None
        hora_almoco_inicio = data.get('hora_almoco_inicio') or None
        hora_almoco_fim = data.get('hora_almoco_fim') or None
        tipo_lancamento = data.get('tipo_lancamento', 'trabalho_normal')
        # Tratar sem_intervalo corretamente (pode vir como True, False, 'true', 'false', None)
        sem_intervalo_raw = data.get('sem_intervalo', False)
        sem_intervalo = sem_intervalo_raw in [True, 'true', 'True', 1, '1']
        observacoes = data.get('observacoes', '')
        
        logger.debug(f"[INFO] HORARIOS RECEBIDOS: entrada={hora_entrada}, saida={hora_saida}, "
              f"almoco_inicio={hora_almoco_inicio}, almoco_fim={hora_almoco_fim}, "
              f"sem_intervalo_raw={sem_intervalo_raw}, sem_intervalo={sem_intervalo}")
        
        # Processar lançamentos
        registros_criados = 0
        registros_existentes = 0
        erros = []
        
        # Gerar lista de datas no período
        from datetime import timedelta
        datas_periodo = []
        data_atual = data_inicio
        while data_atual <= data_final:
            datas_periodo.append(data_atual)
            data_atual += timedelta(days=1)
        
            logger.debug(f"[DATE] Processando {len(datas_periodo)} datas para {len(funcionarios_ids)} funcionários")
        
        for funcionario_id in funcionarios_ids:
            try:
                # Converter para int se necessário
                funcionario_id = int(funcionario_id)
                
                # Verificar se funcionário existe e pertence ao admin
                funcionario = Funcionario.query.filter_by(
                    id=funcionario_id, 
                    ativo=True,
                    admin_id=admin_id
                ).first()
                
                if not funcionario:
                    erros.append(f"Funcionário ID {funcionario_id} não encontrado ou inativo")
                    continue
                
                # Processar cada data do período
                for data_obj in datas_periodo:
                    try:
                        # Verificar se já existe registro para esta data
                        registro_existente = RegistroPonto.query.filter_by(
                            funcionario_id=funcionario_id,
                            data=data_obj
                        ).first()
                        
                        if registro_existente:
                            registros_existentes += 1
                            continue
                        
                        # Determinar se é final de semana (sábado=5, domingo=6)
                        dia_semana = data_obj.weekday()
                        if dia_semana == 5:  # Sábado
                            tipo_reg = 'sabado_folga' if tipo_lancamento == 'trabalho_normal' else tipo_lancamento
                        elif dia_semana == 6:  # Domingo
                            tipo_reg = 'domingo_folga' if tipo_lancamento == 'trabalho_normal' else tipo_lancamento
                        else:
                            tipo_reg = tipo_lancamento
                        
                        # Criar registro de ponto
                        registro = RegistroPonto(
                            funcionario_id=funcionario_id,
                            obra_id=obra_id,
                            data=data_obj,
                            tipo_registro=tipo_reg,
                            observacoes=observacoes,
                            admin_id=admin_id
                        )
                        
                        # Adicionar horários se não for folga e não for final de semana
                        if tipo_reg == 'trabalho_normal' and dia_semana < 5:
                            if hora_entrada:
                                registro.hora_entrada = datetime.strptime(hora_entrada, '%H:%M').time()
                            if hora_saida:
                                registro.hora_saida = datetime.strptime(hora_saida, '%H:%M').time()
                            if not sem_intervalo:
                                if hora_almoco_inicio:
                                    registro.hora_almoco_saida = datetime.strptime(hora_almoco_inicio, '%H:%M').time()
                                if hora_almoco_fim:
                                    registro.hora_almoco_retorno = datetime.strptime(hora_almoco_fim, '%H:%M').time()
                            
                            # Calcular horas trabalhadas
                            if registro.hora_entrada and registro.hora_saida:
                                try:
                                    from utils import calcular_horas_trabalhadas
                                    horas_calc = calcular_horas_trabalhadas(
                                        registro.hora_entrada,
                                        registro.hora_saida,
                                        registro.hora_almoco_saida,
                                        registro.hora_almoco_retorno,
                                        registro.data
                                    )
                                    registro.horas_trabalhadas = horas_calc.get('total', 0)
                                    registro.horas_extras = horas_calc.get('extras', 0)
                                except Exception as calc_e:
                                    logger.error(f"[WARN] Erro ao calcular horas: {calc_e}")
                                    registro.horas_trabalhadas = 8.0
                                    registro.horas_extras = 0.0
                        
                        db.session.add(registro)
                        registros_criados += 1
                        
                    except Exception as e:
                        erros.append(f"Erro ao processar {funcionario.nome} em {data_obj}: {str(e)}")
                        logger.error(f"[ERROR] Erro processando {funcionario.nome} em {data_obj}: {e}")
                
            except Exception as e:
                erros.append(f"Erro ao processar funcionário ID {funcionario_id}: {str(e)}")
                logger.error(f"[ERROR] Erro funcionário {funcionario_id}: {e}")
        
        # Commit se houver registros criados
        if registros_criados > 0:
            db.session.commit()
            logger.info(f"[OK] {registros_criados} registros salvos no banco")
        
        return jsonify({
            'success': True,
            'message': f'{registros_criados} lançamentos criados com sucesso',
            'total_lancamentos': registros_criados,
            'registros_existentes': registros_existentes,
            'erros': erros
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] ERRO CRÍTICO NO LANÇAMENTO MÚLTIPLO: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

# ===== API PARA SERVIR FOTO DO FUNCIONÁRIO =====
@main_bp.route('/api/funcionario/<int:id>/foto')
@login_required
def get_funcionario_foto(id):
    try:
        admin_id = get_tenant_admin_id()
        funcionario = Funcionario.query.filter_by(id=id, admin_id=admin_id).first()
        if not funcionario:
            return _foto_placeholder_svg("?"), 200

        if funcionario.foto_base64 and funcionario.foto_base64.startswith("data:"):
            import base64
            header, b64data = funcionario.foto_base64.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            image_data = base64.b64decode(b64data)
            return Response(image_data, content_type=mime_type)

        if funcionario.foto:
            import os
            for base_dir in ['static', '']:
                filepath = os.path.join(base_dir, funcionario.foto) if base_dir else funcionario.foto
                if os.path.isfile(filepath):
                    return send_file(filepath)

        return _foto_placeholder_svg(funcionario.nome if funcionario.nome else "?"), 200
    except Exception as e:
        logger.error(f"Erro ao servir foto do funcionário {id}: {e}")
        return _foto_placeholder_svg("?"), 200


def _foto_placeholder_svg(nome):
    initials = ""
    if nome and nome != "?":
        parts = nome.strip().split()
        if len(parts) >= 2:
            initials = (parts[0][0] + parts[-1][0]).upper()
        elif parts:
            initials = parts[0][0].upper()
    else:
        initials = "?"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
<rect width="120" height="120" rx="60" fill="#6c757d"/>
<text x="60" y="60" text-anchor="middle" dominant-baseline="central" fill="white" font-size="40" font-family="Arial,sans-serif" font-weight="bold">{initials}</text>
</svg>'''
    from flask import Response
    return Response(svg, content_type="image/svg+xml")


# ===== API PARA BUSCAR FUNCIONÁRIO INDIVIDUAL =====
@main_bp.route('/api/funcionario/<int:funcionario_id>', methods=['GET'])
@login_required
def get_funcionario(funcionario_id):
    """API para buscar dados de um funcionário específico"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first()
        
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        return jsonify({
            'success': True,
            'funcionario': {
                'id': funcionario.id,
                'nome': funcionario.nome,
                'cpf': funcionario.cpf,
                'rg': funcionario.rg or '',
                'data_nascimento': funcionario.data_nascimento.strftime('%Y-%m-%d') if funcionario.data_nascimento else '',
                'email': funcionario.email or '',
                'telefone': funcionario.telefone or '',
                'endereco': funcionario.endereco or '',
                'data_admissao': funcionario.data_admissao.strftime('%Y-%m-%d') if funcionario.data_admissao else '',
                'salario': float(funcionario.salario) if funcionario.salario else 0,
                'departamento_id': funcionario.departamento_id or 0,
                'funcao_id': funcionario.funcao_id or 0,
                'horario_trabalho_id': funcionario.horario_trabalho_id or 0,
                'ativo': funcionario.ativo,
                'foto': funcionario.foto or ''
            }
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Erro ao buscar funcionário: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ===== ROTA PARA EDITAR FUNCIONÁRIO =====
@main_bp.route('/funcionarios/<int:funcionario_id>/editar', methods=['POST'])
@login_required
def editar_funcionario(funcionario_id):
    """Editar dados de um funcionário"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first()
        
        if not funcionario:
            flash('[ERROR] Funcionário não encontrado', 'error')
            return redirect(url_for('main.funcionarios'))
        
        # Atualizar dados
        funcionario.nome = request.form.get('nome', '').strip()
        funcionario.cpf = request.form.get('cpf', '').strip()
        funcionario.rg = request.form.get('rg', '').strip()
        
        if request.form.get('data_nascimento'):
            funcionario.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date()
        
        funcionario.email = request.form.get('email', '').strip()
        funcionario.telefone = request.form.get('telefone', '').strip()
        funcionario.endereco = request.form.get('endereco', '').strip()
        
        if request.form.get('data_admissao'):
            funcionario.data_admissao = datetime.strptime(request.form['data_admissao'], '%Y-%m-%d').date()
        
        if request.form.get('salario'):
            funcionario.salario = float(request.form['salario'])
        
        # Atualizar IDs de relacionamentos
        funcionario.departamento_id = int(request.form['departamento_id']) if request.form.get('departamento_id') and request.form['departamento_id'] != '0' else None
        funcionario.funcao_id = int(request.form['funcao_id']) if request.form.get('funcao_id') and request.form['funcao_id'] != '0' else None
        funcionario.horario_trabalho_id = int(request.form['horario_trabalho_id']) if request.form.get('horario_trabalho_id') and request.form['horario_trabalho_id'] != '0' else None
        
        funcionario.ativo = 'ativo' in request.form
        
        # Processar foto se enviada
        if 'foto' in request.files and request.files['foto'].filename:
            from werkzeug.utils import secure_filename
            import os
            
            foto = request.files['foto']
            filename = secure_filename(f"{funcionario.codigo}_{foto.filename}")
            foto_path = os.path.join('static/fotos_funcionarios', filename)
            
            # Criar diretório se não existir
            os.makedirs(os.path.dirname(foto_path), exist_ok=True)
            foto.save(foto_path)
            funcionario.foto = filename
        
        db.session.commit()
        
        flash(f'[OK] Funcionário {funcionario.nome} atualizado com sucesso!', 'success')
        return redirect(url_for('main.funcionarios'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao editar funcionário: {str(e)}")
        flash(f'[ERROR] Erro ao editar funcionário: {str(e)}', 'error')
        return redirect(url_for('main.funcionarios'))

@main_bp.route('/api/funcionario/<int:funcionario_id>/toggle-ativo', methods=['POST'])
@login_required
def toggle_funcionario_ativo(funcionario_id):
    """Toggle status ativo/inativo do funcionário"""
    try:
        admin_id = get_tenant_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=admin_id
        ).first()
        
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        # Toggle status
        funcionario.ativo = not funcionario.ativo
        
        # Registrar data de desativação se necessário
        if not funcionario.ativo:
            funcionario.data_desativacao = datetime.now().date()
        else:
            funcionario.data_desativacao = None
        
        db.session.commit()
        
        status_texto = "ativado" if funcionario.ativo else "desativado"
        logger.info(f"[OK] Funcionário {funcionario.nome} {status_texto}")
        
        return jsonify({
            'success': True,
            'message': f'Funcionário {status_texto} com sucesso',
            'ativo': funcionario.ativo
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] ERRO AO TOGGLE FUNCIONÁRIO: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/api/ponto/lancamento-finais-semana', methods=['POST'])
def lancamento_finais_semana():
    """Lança automaticamente sábados e domingos como folga para todos os funcionários ativos"""
    logger.info("[START] INÍCIO da função lancamento_finais_semana")
    
    try:
        # Obter dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados não fornecidos'}), 400
            
        competencia = data.get('competencia')  # formato: '2025-08'
        if not competencia:
            return jsonify({'success': False, 'message': 'Competência não fornecida'}), 400
            
            logger.debug(f"[DATE] Processando competência: {competencia}")
        
        # Obter admin_id (usar fallback para desenvolvimento)
        from utils.tenant import get_safe_admin_id
        admin_id = get_safe_admin_id()
        logger.debug(f"[CORP] Admin ID: {admin_id}")
        
        # Se ainda for None, usar fallback direto para desenvolvimento
        if admin_id is None:
            logger.warning("[WARN] Admin ID None - tentando fallback direto...")
            primeiro_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
            if primeiro_admin:
                admin_id = primeiro_admin.id
                logger.info(f"[CONFIG] Fallback aplicado - Admin ID: {admin_id}")
            else:
                logger.error("[ERROR] Nenhum admin encontrado no sistema!")
                return jsonify({'success': False, 'message': 'Nenhum administrador encontrado no sistema'}), 500
        
        # Buscar funcionários ativos  
        funcionarios_ativos = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).all()
        
        logger.debug(f"[USERS] Funcionários ativos encontrados: {len(funcionarios_ativos)}")
        
        # Parse da competência (ano-mes)
        ano, mes = competencia.split('-')
        ano = int(ano)
        mes = int(mes)
        
        # Gerar todos os dias do mês
        # Último dia do mês
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        
        sabados_domingos = []
        for dia in range(1, ultimo_dia + 1):
            data_atual = date(ano, mes, dia)
            # 5 = sábado, 6 = domingo (weekday)
            if data_atual.weekday() in [5, 6]:
                sabados_domingos.append(data_atual)
        
                logger.debug(f"[DATE] Finais de semana encontrados: {len(sabados_domingos)} dias")
        
        registros_criados = 0
        registros_existentes = 0
        erros = []
        
        # Processar cada funcionário
        for funcionario in funcionarios_ativos:
            logger.debug(f"[USER] Processando: {funcionario.nome} (ID: {funcionario.id})")
            
            for data_folga in sabados_domingos:
                # Determinar tipo de folga
                tipo_folga = 'sabado_folga' if data_folga.weekday() == 5 else 'domingo_folga'
                
                # Verificar se já existe registro
                registro_existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_folga
                ).first()
                
                if registro_existente:
                    registros_existentes += 1
                    logger.info(f" [OK] Já existe: {data_folga} ({tipo_folga})")
                else:
                    # Criar novo registro
                    try:
                        novo_registro = RegistroPonto(
                            funcionario_id=funcionario.id,
                            data=data_folga,
                            tipo_registro=tipo_folga,
                            horas_trabalhadas=0.0,
                            observacoes=f'Lançamento automático - {competencia}',
                            admin_id=admin_id
                        )
                        
                        db.session.add(novo_registro)
                        registros_criados += 1
                        logger.info(f" [+] Criado: {data_folga} ({tipo_folga})")
                        
                    except Exception as e:
                        erro_msg = f"Erro ao criar registro para {funcionario.nome} em {data_folga}: {str(e)}"
                        erros.append(erro_msg)
                        logger.error(f" [ERROR] ERRO: {erro_msg}")
        
        # Salvar todas as alterações
        if registros_criados > 0:
            db.session.commit()
            logger.info(f"[SAVE] {registros_criados} registros salvos no banco")
        
        return jsonify({
            'success': True,
            'message': f'Lançamento concluído para {competencia.replace("-", "/")}!',
            'detalhes': {
                'funcionarios_processados': len(funcionarios_ativos),
                'registros_criados': registros_criados,
                'registros_existentes': registros_existentes,
                'finais_semana_encontrados': len(sabados_domingos),
                'erros': erros
            }
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Erro interno: {str(e)}"
        logger.error(f"[ERROR] ERRO GERAL: {error_msg}")
        return jsonify({
            'success': False,
            'message': 'Erro ao processar lançamento de finais de semana',
            'error': error_msg
        }), 500

@main_bp.route('/api/obras/ativas')
@login_required
def api_obras_ativas():
    """API para listar obras ativas para seleção no modal"""
    try:
        admin_id = get_tenant_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        obras = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Obra.nome).all()
        
        logger.debug(f"[BUILD] DEBUG: Encontradas {len(obras)} obras ativas para admin_id={admin_id}")
        
        obras_json = []
        for obra in obras:
            obras_json.append({
                'id': obra.id,
                'nome': obra.nome,
                'codigo': obra.codigo if obra.codigo else '',
                'endereco': obra.endereco if obra.endereco else ''
            })
        
        return jsonify({
            'success': True,
            'obras': obras_json,
            'total': len(obras_json)
        })
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO AO LISTAR OBRAS: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/api/obras/servicos-rdo', methods=['POST'])
@login_required
def api_adicionar_servico_obra():
    """API para adicionar serviço à obra via modal de detalhes"""
    try:
        data = request.get_json()
        obra_id = data.get('obra_id')
        servico_id = data.get('servico_id')
        
        if not obra_id or not servico_id:
            return jsonify({
                'success': False,
                'message': 'obra_id e servico_id são obrigatórios'
            }), 400
        
        # Obter admin_id do usuário logado
        admin_id = get_tenant_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        # Validar que a obra pertence ao admin (segurança multi-tenant)
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id, ativo=True).first()
        if not obra:
            return jsonify({
                'success': False,
                'message': 'Obra não encontrada ou sem permissão de acesso'
            }), 404
        
        # Validar que o serviço pertence ao admin (segurança multi-tenant)
        servico = Servico.query.filter_by(id=servico_id, admin_id=admin_id, ativo=True).first()
        if not servico:
            return jsonify({
                'success': False,
                'message': 'Serviço não encontrado ou sem permissão de acesso'
            }), 404
        
        # Verificar se serviço já existe na obra
        servico_existente = ServicoObraReal.query.filter_by(
            obra_id=obra_id,
            servico_id=servico_id,
            admin_id=admin_id
        ).first()
        
        if servico_existente:
            if servico_existente.ativo:
                return jsonify({
                    'success': False,
                    'message': 'Serviço já está associado a esta obra'
                }), 409
            else:
                # Reativar serviço
                servico_existente.ativo = True
                servico_existente.observacoes = f'Serviço reativado em {date.today().strftime("%d/%m/%Y")}'
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Serviço reativado com sucesso',
                    'servico': {
                        'id': servico.id,
                        'nome': servico.nome,
                        'descricao': servico.descricao
                    }
                })
        
        # Criar novo registro em servico_obra_real
        novo_servico_obra = ServicoObraReal(
            obra_id=obra_id,
            servico_id=servico_id,
            quantidade_planejada=1.0,
            quantidade_executada=0.0,
            percentual_concluido=0.0,
            valor_unitario=servico.custo_unitario or 0.0,
            valor_total_planejado=servico.custo_unitario or 0.0,
            valor_total_executado=0.0,
            status='Não Iniciado',
            prioridade=3,
            data_inicio_planejada=date.today(),
            observacoes=f'Serviço adicionado em {date.today().strftime("%d/%m/%Y")}',
            admin_id=admin_id,
            ativo=True
        )
        
        db.session.add(novo_servico_obra)
        db.session.commit()
        
        logger.info(f"[OK] Serviço {servico.nome} adicionado à obra {obra.nome}")
        
        return jsonify({
            'success': True,
            'message': 'Serviço adicionado com sucesso',
            'servico': {
                'id': servico.id,
                'nome': servico.nome,
                'descricao': servico.descricao
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] ERRO AO ADICIONAR SERVIÇO À OBRA: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao adicionar serviço: {str(e)}'
        }), 500

@main_bp.route('/api/obras/servicos', methods=['DELETE'])
@login_required
def api_remover_servico_obra():
    """API para remover serviço da obra"""
    try:
        data = request.get_json()
        obra_id = data.get('obra_id')
        servico_id = data.get('servico_id')
        
        if not obra_id or not servico_id:
            return jsonify({
                'success': False,
                'message': 'obra_id e servico_id são obrigatórios'
            }), 400
        
        # Obter admin_id do usuário logado
        admin_id = get_tenant_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        # Validar que a obra pertence ao admin (segurança multi-tenant)
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            return jsonify({
                'success': False,
                'message': 'Obra não encontrada ou sem permissão de acesso'
            }), 404
        
        # Buscar serviço na obra
        servico_obra = ServicoObraReal.query.filter_by(
            obra_id=obra_id,
            servico_id=servico_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not servico_obra:
            return jsonify({
                'success': False,
                'message': 'Serviço não encontrado nesta obra'
            }), 404
        
        # Desativar (soft delete)
        servico_obra.ativo = False
        servico_obra.observacoes = f'Serviço removido em {date.today().strftime("%d/%m/%Y")}'
        
        # Remover registros de RDO relacionados (cascata)
        rdos_deletados = RDOServicoSubatividade.query.filter_by(
            servico_id=servico_id,
            admin_id=admin_id
        ).delete()
        
        db.session.commit()
        
        logger.info(f"[OK] Serviço ID {servico_id} removido da obra {obra.nome} ({rdos_deletados} registros RDO removidos)")
        
        return jsonify({
            'success': True,
            'message': 'Serviço removido com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] ERRO AO REMOVER SERVIÇO DA OBRA: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao remover serviço: {str(e)}'
        }), 500

def get_admin_id_dinamico():
    """Função helper para detectar admin_id dinamicamente no sistema multi-tenant"""
    try:
        from sqlalchemy import text
        
        # 1. Se usuário autenticado, usar sua lógica
        if current_user.is_authenticated:
            if current_user.tipo_usuario == TipoUsuario.ADMIN:
                return current_user.id
            elif current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
                # SUPER_ADMIN pode ver tudo - buscar admin_id com mais dados
                obra_counts = db.session.execute(
                    text("SELECT admin_id, COUNT(*) as total FROM obra WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
                ).fetchone()
                if obra_counts and obra_counts[0]:
                    logger.info(f"[OK] SUPER_ADMIN: usando admin_id={obra_counts[0]} ({obra_counts[1]} obras)")
                    return obra_counts[0]
                # Fallback para funcionários
                func_counts = db.session.execute(
                    text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
                ).fetchone()
                if func_counts and func_counts[0]:
                    return func_counts[0]
                return current_user.id
            elif current_user.admin_id:
                return current_user.admin_id
            else:
                # Funcionário sem admin_id definido - buscar dinamicamente
                pass
        
        # 2. Sistema de bypass - detectar admin_id baseado nos dados disponíveis
        from sqlalchemy import text
        
        # Primeiro: verificar se existe admin_id com funcionários
        admin_funcionarios = db.session.execute(
            text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 3")
        ).fetchall()
        
        logger.debug(f"[DEBUG] ADMINS DISPONÍVEIS: {admin_funcionarios}")
        
        # Priorizar admin com mais funcionários (mas pelo menos 1)
        for admin_info in admin_funcionarios:
            admin_id, total = admin_info
            if total >= 1:  # Qualquer admin com pelo menos 1 funcionário
                logger.info(f"[OK] SELECIONADO: admin_id={admin_id} ({total} funcionários)")
                return admin_id
        
        # Fallback: qualquer admin com serviços
        admin_servicos = db.session.execute(
            text("SELECT admin_id, COUNT(*) as total FROM servico WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
        ).fetchone()
        
        if admin_servicos:
            logger.info(f"[OK] FALLBACK SERVIÇOS: admin_id={admin_servicos[0]} ({admin_servicos[1]} serviços)")
            return admin_servicos[0]
            
        # Último fallback: primeiro admin_id encontrado na tabela funcionario
        primeiro_admin = db.session.execute(
            text("SELECT DISTINCT admin_id FROM funcionario ORDER BY admin_id LIMIT 1")
        ).fetchone()
        
        if primeiro_admin:
            logger.info(f"[OK] ÚLTIMO FALLBACK: admin_id={primeiro_admin[0]}")
            return primeiro_admin[0]
            
        # Se nada funcionar, retornar 1
            logger.warning("[WARN] USANDO DEFAULT: admin_id=1")
        return 1
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO GET_ADMIN_ID_DINAMICO: {str(e)}")
        # Em caso de erro, tentar um fallback mais simples
        try:
            primeiro_admin = db.session.execute(text("SELECT MIN(admin_id) FROM funcionario")).fetchone()
            return primeiro_admin[0] if primeiro_admin and primeiro_admin[0] else 1
        except:
            return 1

@main_bp.route('/api/servicos')
@login_required
def api_servicos():
    """API para buscar serviços - Multi-tenant com sistema robusto"""
    try:
        # CORREÇÃO CRÍTICA: Obter admin_id do usuário autenticado
        admin_id = None
        user_status = "Usuário não autenticado"
        
        logger.debug(f"[DEBUG] DEBUG API: current_user exists={current_user is not None}")
        logger.debug(f"[DEBUG] DEBUG API: is_authenticated={getattr(current_user, 'is_authenticated', False)}")
        if hasattr(current_user, 'id'):
            logger.debug(f"[DEBUG] DEBUG API: current_user.id={current_user.id}")
        if hasattr(current_user, 'admin_id'):
            logger.debug(f"[DEBUG] DEBUG API: current_user.admin_id={current_user.admin_id}")
        if hasattr(current_user, 'tipo_usuario'):
            logger.debug(f"[DEBUG] DEBUG API: current_user.tipo_usuario={current_user.tipo_usuario}")
        
        if current_user and current_user.is_authenticated:
            # Funcionário sempre tem admin_id
            if hasattr(current_user, 'admin_id') and current_user.admin_id:
                admin_id = current_user.admin_id
                user_status = f"Funcionário autenticado (admin_id={admin_id})"
                logger.info(f"[OK] API SERVIÇOS: Admin_id do funcionário - admin_id={admin_id}")
            # Se não tem admin_id, é um admin
            elif hasattr(current_user, 'id'):
                admin_id = current_user.id
                user_status = f"Admin autenticado (id={admin_id})"
                logger.info(f"[OK] API SERVIÇOS: Admin_id do usuário logado - admin_id={admin_id}")
            else:
                logger.warning("[WARN] API SERVIÇOS: Usuário autenticado mas sem ID válido")
        
        # Se não conseguiu obter do usuário autenticado, usar fallback
        if admin_id is None:
            admin_id = get_admin_id_robusta()
            user_status = f"Fallback sistema robusto (admin_id={admin_id})"
            logger.warning(f"[WARN] API SERVIÇOS FALLBACK: Admin_id via sistema robusto - admin_id={admin_id}")
            
            # Se ainda não conseguiu determinar, usar fallback adicional
            if admin_id is None:
                logger.warning("[WARN] DESENVOLVIMENTO: Usando fallback inteligente")
                
                # Primeiro tenta admin_id=2 (produção simulada)
                servicos_admin_2 = db.session.execute(
                    text("SELECT COUNT(*) FROM servico WHERE admin_id = 2 AND ativo = true")
                ).fetchone()
                
                if servicos_admin_2 and servicos_admin_2[0] > 0:
                    admin_id = 2
                    user_status = f"Fallback admin_id=2 ({servicos_admin_2[0]} serviços)"
                    logger.info(f"[OK] DESENVOLVIMENTO: {user_status}")
                else:
                    # Fallback para admin com mais funcionários
                    admin_id = get_admin_id_dinamico()
                    user_status = f"Fallback dinâmico (admin_id={admin_id})"
                    logger.info(f"[OK] DESENVOLVIMENTO: {user_status}")
        
                    logger.debug(f"[TARGET] API SERVIÇOS FINAL: admin_id={admin_id}")
        
        # DEBUG DETALHADO DA CONSULTA
                    logger.debug(f"[DEBUG] DEBUG CONSULTA: admin_id={admin_id} (tipo: {type(admin_id)})")
        
        # Primeiro: verificar se existem serviços para esse admin_id
        total_servicos_admin = Servico.query.filter_by(admin_id=admin_id).count()
        logger.info(f"[STATS] Total de serviços para admin_id={admin_id}: {total_servicos_admin}")
        
        # Segundo: verificar quantos estão ativos
        servicos_ativos_count = Servico.query.filter_by(admin_id=admin_id, ativo=True).count()
        logger.info(f"[OK] Serviços ativos para admin_id={admin_id}: {servicos_ativos_count}")
        
        # Terceiro: buscar os serviços ativos
        servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
        logger.debug(f"[TARGET] Query result: {len(servicos)} serviços encontrados")
        
        # Se ainda não encontrou, fazer debug da consulta raw
        if len(servicos) == 0 and servicos_ativos_count > 0:
            logger.warning("[WARN] INCONSISTÊNCIA: Count diz que há serviços, mas query retorna vazio")
            # Tentar consulta alternativa
            servicos_raw = db.session.execute(
                text("SELECT * FROM servico WHERE admin_id = :admin_id AND ativo = true ORDER BY nome"),
                {"admin_id": admin_id}
            ).fetchall()
            logger.info(f"[CONFIG] Query RAW encontrou: {len(servicos_raw)} serviços")
            
            if len(servicos_raw) > 0:
                logger.info("[ALERT] PROBLEMA NO ORM - usando consulta raw")
                # Converter resultado raw para objetos Servico
                servicos = Servico.query.filter(
                    Servico.id.in_([row[0] for row in servicos_raw])
                ).order_by(Servico.nome).all()
        
        # Processar para JSON
        servicos_json = []
        for servico in servicos:
            servico_data = {
                'id': servico.id,
                'nome': servico.nome or 'Serviço sem nome',
                'descricao': servico.descricao or '',
                'categoria': servico.categoria or 'Geral',
                'unidade_medida': servico.unidade_medida or 'un',
                'unidade_simbolo': servico.unidade_simbolo or 'un',
                'valor_unitario': float(servico.custo_unitario) if hasattr(servico, 'custo_unitario') and servico.custo_unitario else 0.0,
                'admin_id': servico.admin_id
            }
            servicos_json.append(servico_data)
        
            logger.info(f"[START] RETORNANDO: {len(servicos_json)} serviços em JSON para admin_id={admin_id}")
        
        return jsonify({
            'success': True, 
            'servicos': servicos_json, 
            'total': len(servicos_json),
            'admin_id': admin_id,
            'user_status': user_status
        })
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[ERROR] ERRO CRÍTICO API SERVIÇOS: {error_msg}")
        return jsonify({
            'success': False, 
            'servicos': [], 
            'error': error_msg,
            'admin_id': None
        }), 500

@main_bp.route('/api/servicos-disponiveis-obra/<int:obra_id>')
@login_required
def api_servicos_disponiveis_obra(obra_id):
    """API para buscar serviços disponíveis para uma obra específica - Multi-tenant seguro"""
    try:
        # Obter admin_id do usuário autenticado
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            admin_id = current_user.id
        else:
            admin_id = current_user.admin_id
            
            logger.info(f"[OK] API SERVIÇOS OBRA: Admin_id={admin_id}, Obra_id={obra_id}")
        
        # Verificar se a obra pertence ao admin correto
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            logger.error(f"[ERROR] Obra {obra_id} não encontrada ou não pertence ao admin_id {admin_id}")
            return jsonify({
                'success': False,
                'error': 'Obra não encontrada ou sem permissão',
                'servicos': []
            }), 403
            
        # Buscar serviços disponíveis do admin
        servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
        logger.debug(f"[TARGET] Encontrados {len(servicos)} serviços para admin_id={admin_id}")
        
        # Processar para JSON
        servicos_json = []
        for servico in servicos:
            servico_data = {
                'id': servico.id,
                'nome': servico.nome or 'Serviço sem nome',
                'descricao': servico.descricao or '',
                'categoria': servico.categoria or 'Geral',
                'unidade_medida': servico.unidade_medida or 'un',
                'unidade_simbolo': servico.unidade_simbolo or 'un',
                'valor_unitario': float(servico.custo_unitario) if hasattr(servico, 'custo_unitario') and servico.custo_unitario else 0.0,
                'admin_id': servico.admin_id
            }
            servicos_json.append(servico_data)
        
            logger.info(f"[START] API OBRA: Retornando {len(servicos_json)} serviços seguros")
        
        return jsonify({
            'success': True,
            'servicos': servicos_json,
            'total': len(servicos_json),
            'obra_id': obra_id,
            'admin_id': admin_id
        })
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[ERROR] ERRO API SERVIÇOS OBRA: {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg,
            'servicos': []
        }), 500

