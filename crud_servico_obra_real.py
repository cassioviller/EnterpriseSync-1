#!/usr/bin/env python3
"""
CRUD para ServicoObraReal - Nova tabela de serviços reais na obra
SIGE v8.3 - Sistema Integrado de Gestão Empresarial
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, ServicoObraReal, Obra, Servico, Funcionario
from datetime import datetime, date
from multitenant_helper import get_admin_id
from sqlalchemy import and_, or_
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprint
servico_obra_real_bp = Blueprint('servico_obra_real', __name__)

@servico_obra_real_bp.route('/obra/<int:obra_id>/servicos-reais')
@login_required
def listar_servicos_reais(obra_id):
    """Lista todos os serviços reais vinculados à obra"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se a obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada.', 'error')
            return redirect(url_for('main.obras'))
        
        # Buscar serviços reais da obra
        servicos_reais = db.session.query(ServicoObraReal, Servico, Funcionario).outerjoin(
            Servico, ServicoObraReal.servico_id == Servico.id
        ).outerjoin(
            Funcionario, ServicoObraReal.responsavel_id == Funcionario.id
        ).filter(
            ServicoObraReal.obra_id == obra_id,
            ServicoObraReal.admin_id == admin_id,
            ServicoObraReal.ativo == True
        ).all()
        
        logger.info(f"[OK] Encontrados {len(servicos_reais)} serviços reais para obra {obra_id}")
        
        return render_template('obras/servicos_reais.html', 
                             obra=obra, 
                             servicos_reais=servicos_reais)
    
    except Exception as e:
        logger.error(f"[ERROR] Erro ao listar serviços reais: {e}")
        flash('Erro ao carregar serviços reais.', 'error')
        return redirect(url_for('main.obras'))

@servico_obra_real_bp.route('/obra/<int:obra_id>/servico-real/novo', methods=['GET', 'POST'])
@login_required
def novo_servico_real(obra_id):
    """Adiciona novo serviço real à obra"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se a obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada.', 'error')
            return redirect(url_for('main.obras'))
        
        if request.method == 'GET':
            # Buscar serviços disponíveis
            servicos_disponiveis = Servico.query.filter_by(admin_id=admin_id, ativo=True).all()
            funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
            
            return render_template('obras/novo_servico_real.html',
                                 obra=obra,
                                 servicos_disponiveis=servicos_disponiveis,
                                 funcionarios=funcionarios)
        
        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            
            servico_id = data.get('servico_id')
            quantidade_planejada = float(data.get('quantidade_planejada', 0))
            valor_unitario = float(data.get('valor_unitario', 0))
            responsavel_id = data.get('responsavel_id') or None
            data_inicio_planejada = data.get('data_inicio_planejada')
            data_fim_planejada = data.get('data_fim_planejada')
            observacoes = data.get('observacoes', '')
            prioridade = int(data.get('prioridade', 3))
            
            # Verificar se já existe
            servico_existente = ServicoObraReal.query.filter_by(
                obra_id=obra_id,
                servico_id=servico_id,
                admin_id=admin_id
            ).first()
            
            if servico_existente:
                if request.is_json:
                    return jsonify({'success': False, 'message': 'Serviço já vinculado a esta obra'})
                flash('Serviço já vinculado a esta obra.', 'warning')
                return redirect(url_for('servico_obra_real.novo_servico_real', obra_id=obra_id))
            
            # Criar novo serviço real
            novo_servico = ServicoObraReal(
                obra_id=obra_id,
                servico_id=servico_id,
                quantidade_planejada=quantidade_planejada,
                valor_unitario=valor_unitario,
                valor_total_planejado=quantidade_planejada * valor_unitario,
                responsavel_id=responsavel_id,
                data_inicio_planejada=datetime.strptime(data_inicio_planejada, '%Y-%m-%d').date() if data_inicio_planejada else None,
                data_fim_planejada=datetime.strptime(data_fim_planejada, '%Y-%m-%d').date() if data_fim_planejada else None,
                observacoes=observacoes,
                prioridade=prioridade,
                admin_id=admin_id
            )
            
            db.session.add(novo_servico)
            db.session.commit()
            
            logger.info(f"[OK] Serviço real {servico_id} adicionado à obra {obra_id}")
            
            if request.is_json:
                return jsonify({'success': True, 'message': 'Serviço real adicionado com sucesso'})
            
            flash('Serviço real adicionado com sucesso!', 'success')
            return redirect(url_for('servico_obra_real.listar_servicos_reais', obra_id=obra_id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao adicionar serviço real: {e}")
        if request.is_json:
            return jsonify({'success': False, 'message': f'Erro: {str(e)}'})
        flash('Erro ao adicionar serviço real.', 'error')
        return redirect(url_for('servico_obra_real.listar_servicos_reais', obra_id=obra_id))

@servico_obra_real_bp.route('/servico-real/<int:servico_real_id>/atualizar-progresso', methods=['POST'])
@login_required
def atualizar_progresso(servico_real_id):
    """Atualiza o progresso do serviço real"""
    try:
        admin_id = get_admin_id()
        
        servico_real = ServicoObraReal.query.filter_by(
            id=servico_real_id,
            admin_id=admin_id
        ).first()
        
        if not servico_real:
            return jsonify({'success': False, 'message': 'Serviço não encontrado'})
        
        data = request.get_json()
        quantidade_executada = float(data.get('quantidade_executada', 0))
        valor_executado = float(data.get('valor_executado', 0))
        status = data.get('status', servico_real.status)
        
        # Calcular percentual
        if servico_real.quantidade_planejada > 0:
            percentual = (quantidade_executada / float(servico_real.quantidade_planejada)) * 100
            percentual = min(percentual, 100)  # Limitar a 100%
        else:
            percentual = 0
        
        # Atualizar campos
        servico_real.quantidade_executada = quantidade_executada
        servico_real.valor_total_executado = valor_executado
        servico_real.percentual_concluido = percentual
        servico_real.status = status
        servico_real.updated_at = datetime.utcnow()
        
        # Se iniciou execução, marcar data de início real
        if quantidade_executada > 0 and not servico_real.data_inicio_real:
            servico_real.data_inicio_real = date.today()
        
        # Se concluído 100%, marcar data de fim real
        if percentual >= 100 and not servico_real.data_fim_real:
            servico_real.data_fim_real = date.today()
            servico_real.status = 'Concluído'
        
        db.session.commit()
        
        logger.info(f"[OK] Progresso atualizado: Serviço {servico_real_id} - {percentual:.1f}%")
        
        return jsonify({
            'success': True, 
            'message': 'Progresso atualizado com sucesso',
            'percentual': f"{percentual:.1f}%",
            'status': servico_real.status
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao atualizar progresso: {e}")
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@servico_obra_real_bp.route('/servico-real/<int:servico_real_id>/aprovar', methods=['POST'])
@login_required
def aprovar_servico(servico_real_id):
    """Aprova um serviço real concluído"""
    try:
        admin_id = get_admin_id()
        
        servico_real = ServicoObraReal.query.filter_by(
            id=servico_real_id,
            admin_id=admin_id
        ).first()
        
        if not servico_real:
            return jsonify({'success': False, 'message': 'Serviço não encontrado'})
        
        servico_real.aprovado = True
        servico_real.data_aprovacao = datetime.utcnow()
        servico_real.aprovado_por_id = current_user.id
        servico_real.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"[OK] Serviço {servico_real_id} aprovado por {current_user.nome}")
        
        return jsonify({'success': True, 'message': 'Serviço aprovado com sucesso'})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao aprovar serviço: {e}")
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@servico_obra_real_bp.route('/api/obra/<int:obra_id>/servicos-reais')
@login_required
def api_servicos_reais(obra_id):
    """API para buscar serviços reais da obra"""
    try:
        admin_id = get_admin_id()
        
        servicos_reais = db.session.query(ServicoObraReal, Servico).join(
            Servico, ServicoObraReal.servico_id == Servico.id
        ).filter(
            ServicoObraReal.obra_id == obra_id,
            ServicoObraReal.admin_id == admin_id,
            ServicoObraReal.ativo == True
        ).all()
        
        resultado = []
        for servico_real, servico in servicos_reais:
            resultado.append({
                'id': servico_real.id,
                'servico_nome': servico.nome,
                'categoria': servico.categoria,
                'quantidade_planejada': float(servico_real.quantidade_planejada),
                'quantidade_executada': float(servico_real.quantidade_executada),
                'percentual_concluido': float(servico_real.percentual_concluido),
                'valor_total_planejado': float(servico_real.valor_total_planejado),
                'valor_total_executado': float(servico_real.valor_total_executado),
                'status': servico_real.status,
                'prioridade': servico_real.prioridade,
                'aprovado': servico_real.aprovado,
                'data_inicio_planejada': servico_real.data_inicio_planejada.isoformat() if servico_real.data_inicio_planejada else None,
                'data_fim_planejada': servico_real.data_fim_planejada.isoformat() if servico_real.data_fim_planejada else None,
                'data_inicio_real': servico_real.data_inicio_real.isoformat() if servico_real.data_inicio_real else None,
                'data_fim_real': servico_real.data_fim_real.isoformat() if servico_real.data_fim_real else None
            })
        
        return jsonify({
            'success': True,
            'servicos_reais': resultado,
            'total': len(resultado)
        })
    
    except Exception as e:
        logger.error(f"[ERROR] Erro na API de serviços reais: {e}")
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

# Registrar blueprint
def register_servico_obra_real_bp(app):
    """Registra o blueprint no app principal"""
    app.register_blueprint(servico_obra_real_bp)
    logger.info("[OK] Blueprint ServicoObraReal registrado com sucesso")
