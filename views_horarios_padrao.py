#!/usr/bin/env python3
"""
VIEWS PARA GERENCIAMENTO DE HORÁRIOS PADRÃO - SIGE v8.2
Data: 06 de Agosto de 2025
Routes para CRUD completo de horários padrão
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from models import Funcionario, HorarioPadrao, Usuario, TipoUsuario
from datetime import datetime, date, time
import logging

horarios_bp = Blueprint('horarios_padrao', __name__)
logging.basicConfig(level=logging.INFO)

@horarios_bp.route('/horarios_padrao')
@login_required
def gerenciar_horarios_padrao():
    """Página principal para gerenciar horários padrão"""
    try:
        # Verificar se usuário tem permissão (admin ou super admin)
        if current_user.tipo_usuario not in [TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN]:
            flash('Acesso negado. Apenas administradores podem gerenciar horários padrão.', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Buscar funcionários baseado no tipo de usuário
        if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            # Super Admin vê todos os funcionários
            funcionarios = Funcionario.query.filter_by(ativo=True).all()
        else:
            # Admin vê apenas seus funcionários
            funcionarios = Funcionario.query.filter_by(
                admin_id=current_user.id,
                ativo=True
            ).all()
        
        # Estatísticas para os cards
        total_funcionarios = len(funcionarios)
        com_horario_padrao = sum(1 for f in funcionarios if f.get_horario_padrao_ativo())
        sem_horario_padrao = total_funcionarios - com_horario_padrao
        
        return render_template('gerenciar_horarios_padrao.html',
                             funcionarios=funcionarios,
                             total_funcionarios=total_funcionarios,
                             com_horario_padrao=com_horario_padrao,
                             sem_horario_padrao=sem_horario_padrao)
        
    except Exception as e:
        logging.error(f"Erro ao carregar página de horários: {e}")
        flash('Erro ao carregar página de horários padrão', 'error')
        return redirect(url_for('main.dashboard'))

@horarios_bp.route('/horarios_padrao', methods=['POST'])
@login_required
def criar_horario_padrao():
    """Criar novo horário padrão"""
    try:
        data = request.get_json() or request.form.to_dict()
        
        # Validações
        funcionario_id = data.get('funcionario_id')
        if not funcionario_id:
            return jsonify({'success': False, 'message': 'ID do funcionário é obrigatório'}), 400
        
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        # Verificar permissão
        if (current_user.tipo_usuario == TipoUsuario.ADMIN and 
            funcionario.admin_id != current_user.id):
            return jsonify({'success': False, 'message': 'Sem permissão para este funcionário'}), 403
        
        # Verificar se já existe horário ativo
        horario_existente = funcionario.get_horario_padrao_ativo()
        if horario_existente:
            return jsonify({'success': False, 'message': 'Funcionário já possui horário padrão ativo'}), 400
        
        # Criar novo horário padrão
        horario = HorarioPadrao(
            funcionario_id=funcionario_id,
            entrada_padrao=datetime.strptime(data.get('entrada_padrao', '07:12'), '%H:%M').time(),
            saida_padrao=datetime.strptime(data.get('saida_padrao', '17:00'), '%H:%M').time(),
            saida_almoco_padrao=datetime.strptime(data.get('saida_almoco_padrao', '12:00'), '%H:%M').time() if data.get('saida_almoco_padrao') else None,
            retorno_almoco_padrao=datetime.strptime(data.get('retorno_almoco_padrao', '13:00'), '%H:%M').time() if data.get('retorno_almoco_padrao') else None,
            data_inicio=datetime.strptime(data.get('data_inicio', date.today().isoformat()), '%Y-%m-%d').date(),
            data_fim=datetime.strptime(data['data_fim'], '%Y-%m-%d').date() if data.get('data_fim') else None,
            ativo=True
        )
        
        db.session.add(horario)
        db.session.commit()
        
        logging.info(f"Horário padrão criado para {funcionario.nome} por {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Horário padrão criado para {funcionario.nome}',
            'horario_id': horario.id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar horário padrão: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

@horarios_bp.route('/horarios_padrao/<int:funcionario_id>', methods=['PUT'])
@login_required
def atualizar_horario_padrao(funcionario_id):
    """Atualizar horário padrão existente"""
    try:
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        # Verificar permissão
        if (current_user.tipo_usuario == TipoUsuario.ADMIN and 
            funcionario.admin_id != current_user.id):
            return jsonify({'success': False, 'message': 'Sem permissão para este funcionário'}), 403
        
        horario_ativo = funcionario.get_horario_padrao_ativo()
        if not horario_ativo:
            return jsonify({'success': False, 'message': 'Funcionário não possui horário padrão ativo'}), 404
        
        data = request.get_json() or request.form.to_dict()
        
        # Atualizar horário existente
        horario_ativo.entrada_padrao = datetime.strptime(data.get('entrada_padrao', '07:12'), '%H:%M').time()
        horario_ativo.saida_padrao = datetime.strptime(data.get('saida_padrao', '17:00'), '%H:%M').time()
        horario_ativo.saida_almoco_padrao = datetime.strptime(data.get('saida_almoco_padrao', '12:00'), '%H:%M').time() if data.get('saida_almoco_padrao') else None
        horario_ativo.retorno_almoco_padrao = datetime.strptime(data.get('retorno_almoco_padrao', '13:00'), '%H:%M').time() if data.get('retorno_almoco_padrao') else None
        
        if data.get('data_fim'):
            horario_ativo.data_fim = datetime.strptime(data['data_fim'], '%Y-%m-%d').date()
        
        db.session.commit()
        
        logging.info(f"Horário padrão atualizado para {funcionario.nome} por {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Horário padrão atualizado para {funcionario.nome}'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar horário padrão: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

@horarios_bp.route('/horarios_padrao/aplicar_todos', methods=['POST'])
@login_required
def aplicar_horario_padrao_todos():
    """Aplicar horário padrão comum para todos os funcionários sem horário"""
    try:
        data = request.get_json()
        
        # Buscar funcionários sem horário padrão
        if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            funcionarios = Funcionario.query.filter_by(ativo=True).all()
        else:
            funcionarios = Funcionario.query.filter_by(
                admin_id=current_user.id,
                ativo=True
            ).all()
        
        # Filtrar apenas funcionários sem horário padrão ativo
        funcionarios_sem_horario = [f for f in funcionarios if not f.get_horario_padrao_ativo()]
        
        if not funcionarios_sem_horario:
            return jsonify({'success': False, 'message': 'Todos os funcionários já possuem horário padrão'}), 400
        
        # Criar horários padrão
        horarios_criados = 0
        
        for funcionario in funcionarios_sem_horario:
            horario = HorarioPadrao(
                funcionario_id=funcionario.id,
                entrada_padrao=datetime.strptime(data.get('entrada_padrao', '07:12'), '%H:%M').time(),
                saida_padrao=datetime.strptime(data.get('saida_padrao', '17:00'), '%H:%M').time(),
                saida_almoco_padrao=datetime.strptime(data.get('saida_almoco_padrao', '12:00'), '%H:%M').time() if data.get('saida_almoco_padrao') else None,
                retorno_almoco_padrao=datetime.strptime(data.get('retorno_almoco_padrao', '13:00'), '%H:%M').time() if data.get('retorno_almoco_padrao') else None,
                data_inicio=date.today(),
                ativo=True
            )
            
            db.session.add(horario)
            horarios_criados += 1
        
        db.session.commit()
        
        logging.info(f"Horário padrão aplicado para {horarios_criados} funcionários por {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Horário padrão aplicado para {horarios_criados} funcionários',
            'count': horarios_criados
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao aplicar horários padrão em massa: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

@horarios_bp.route('/horarios_padrao/<int:funcionario_id>/historico')
@login_required
def historico_horarios_padrao(funcionario_id):
    """Buscar histórico de horários padrão de um funcionário"""
    try:
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        # Verificar permissão
        if (current_user.tipo_usuario == TipoUsuario.ADMIN and 
            funcionario.admin_id != current_user.id):
            return jsonify({'success': False, 'message': 'Sem permissão para este funcionário'}), 403
        
        # Buscar todos os horários do funcionário
        horarios = HorarioPadrao.query.filter_by(
            funcionario_id=funcionario_id
        ).order_by(HorarioPadrao.data_inicio.desc()).all()
        
        historico = []
        for horario in horarios:
            historico.append({
                'id': horario.id,
                'entrada': horario.entrada_padrao.strftime('%H:%M'),
                'saida': horario.saida_padrao.strftime('%H:%M'),
                'almoco_saida': horario.saida_almoco_padrao.strftime('%H:%M') if horario.saida_almoco_padrao else None,
                'almoco_retorno': horario.retorno_almoco_padrao.strftime('%H:%M') if horario.retorno_almoco_padrao else None,
                'data_inicio': horario.data_inicio.strftime('%d/%m/%Y'),
                'data_fim': horario.data_fim.strftime('%d/%m/%Y') if horario.data_fim else 'Atual',
                'ativo': horario.ativo,
                'created_at': horario.created_at.strftime('%d/%m/%Y %H:%M') if horario.created_at else ''
            })
        
        return jsonify({
            'success': True,
            'funcionario': funcionario.nome,
            'historico': historico
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar histórico: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

@horarios_bp.route('/horarios_padrao/<int:funcionario_id>/dados')
@login_required
def dados_horario_padrao(funcionario_id):
    """Buscar dados do horário padrão ativo de um funcionário"""
    try:
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        # Verificar permissão
        if (current_user.tipo_usuario == TipoUsuario.ADMIN and 
            funcionario.admin_id != current_user.id):
            return jsonify({'success': False, 'message': 'Sem permissão para este funcionário'}), 403
        
        horario_ativo = funcionario.get_horario_padrao_ativo()
        if not horario_ativo:
            return jsonify({'success': False, 'message': 'Funcionário não possui horário padrão ativo'}), 404
        
        dados = {
            'id': horario_ativo.id,
            'funcionario_nome': funcionario.nome,
            'entrada_padrao': horario_ativo.entrada_padrao.strftime('%H:%M'),
            'saida_padrao': horario_ativo.saida_padrao.strftime('%H:%M'),
            'saida_almoco_padrao': horario_ativo.saida_almoco_padrao.strftime('%H:%M') if horario_ativo.saida_almoco_padrao else '',
            'retorno_almoco_padrao': horario_ativo.retorno_almoco_padrao.strftime('%H:%M') if horario_ativo.retorno_almoco_padrao else '',
            'data_inicio': horario_ativo.data_inicio.strftime('%Y-%m-%d'),
            'data_fim': horario_ativo.data_fim.strftime('%Y-%m-%d') if horario_ativo.data_fim else ''
        }
        
        return jsonify({
            'success': True,
            'dados': dados
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar dados do horário: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

@horarios_bp.route('/horarios_padrao/estatisticas')
@login_required
def estatisticas_horarios_padrao():
    """Estatísticas gerais dos horários padrão"""
    try:
        # Buscar funcionários baseado no tipo de usuário
        if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            funcionarios = Funcionario.query.filter_by(ativo=True).all()
        else:
            funcionarios = Funcionario.query.filter_by(
                admin_id=current_user.id,
                ativo=True
            ).all()
        
        # Calcular estatísticas
        total_funcionarios = len(funcionarios)
        com_horario = sum(1 for f in funcionarios if f.get_horario_padrao_ativo())
        sem_horario = total_funcionarios - com_horario
        
        # Horários mais comuns
        horarios_comuns = {}
        for funcionario in funcionarios:
            horario = funcionario.get_horario_padrao_ativo()
            if horario:
                chave = f"{horario.entrada_padrao.strftime('%H:%M')} - {horario.saida_padrao.strftime('%H:%M')}"
                horarios_comuns[chave] = horarios_comuns.get(chave, 0) + 1
        
        # Ordenar por mais comum
        horarios_ordenados = sorted(horarios_comuns.items(), key=lambda x: x[1], reverse=True)
        
        estatisticas = {
            'total_funcionarios': total_funcionarios,
            'com_horario_padrao': com_horario,
            'sem_horario_padrao': sem_horario,
            'percentual_configurado': round((com_horario / total_funcionarios * 100) if total_funcionarios > 0 else 0, 1),
            'horarios_mais_comuns': horarios_ordenados[:5],
            'data_ultima_atualizacao': datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        
        return jsonify({
            'success': True,
            'estatisticas': estatisticas
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

# Função para registrar blueprint
def registrar_routes_horarios_padrao(app):
    """Registra as routes de horários padrão na aplicação"""
    app.register_blueprint(horarios_bp)
    logging.info("✅ Routes de horários padrão registradas")

if __name__ == "__main__":
    print("📋 Views de horários padrão criadas!")
    print("Para usar, adicione ao seu app principal:")
    print("from views_horarios_padrao import registrar_routes_horarios_padrao")
    print("registrar_routes_horarios_padrao(app)")