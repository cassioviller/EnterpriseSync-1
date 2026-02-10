#!/usr/bin/env python3
"""
Rota para cadastrar serviços específicos em uma obra
"""

from flask import Blueprint, request, redirect, url_for, flash, render_template_string
from models import db, Obra, Servico
from sqlalchemy import text
import logging
logger = logging.getLogger(__name__)

cadastrar_servico_bp = Blueprint('cadastrar_servico', __name__)

@cadastrar_servico_bp.route('/obra/<int:obra_id>/cadastrar-servico', methods=['GET', 'POST'])
def cadastrar_servico_obra(obra_id):
    """Cadastrar um serviço específico em uma obra"""
    obra = Obra.query.get_or_404(obra_id)
    
    if request.method == 'POST':
        servico_id = request.form.get('servico_id')
        quantidade_planejada = request.form.get('quantidade_planejada', 1.0)
        
        if not servico_id:
            flash('Selecione um serviço', 'error')
            return redirect(request.url)
        
        try:
            # Verificar se serviço já está cadastrado na obra
            existing = db.session.execute(text(
                "SELECT id FROM servico_obra WHERE obra_id = :obra_id AND servico_id = :servico_id"
            ), {'obra_id': obra_id, 'servico_id': servico_id}).fetchone()
            
            if existing:
                flash('Serviço já cadastrado nesta obra', 'warning')
                return redirect(url_for('main.detalhes_obra', id=obra_id))
            
            # Cadastrar serviço na obra
            db.session.execute(text("""
                INSERT INTO servico_obra (obra_id, servico_id, admin_id, quantidade_planejada, quantidade_executada, ativo, created_at)
                VALUES (:obra_id, :servico_id, :admin_id, :quantidade_planejada, 0, true, NOW())
            """), {
                'obra_id': obra_id,
                'servico_id': servico_id, 
                'admin_id': obra.admin_id,
                'quantidade_planejada': float(quantidade_planejada)
            })
            
            db.session.commit()
            
            servico = Servico.query.get(servico_id)
            flash(f'Serviço "{servico.nome}" cadastrado na obra com sucesso!', 'success')
            return redirect(url_for('main.detalhes_obra', id=obra_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar serviço: {str(e)}', 'error')
    
    # GET - Listar serviços disponíveis para cadastro
    try:
        # Buscar serviços não cadastrados nesta obra
        servicos_disponiveis = db.session.execute(text("""
            SELECT s.id, s.nome, s.categoria, s.custo_unitario, s.unidade_medida
            FROM servico s
            WHERE s.admin_id = :admin_id AND s.ativo = true
            AND s.id NOT IN (
                SELECT so.servico_id FROM servico_obra so 
                WHERE so.obra_id = :obra_id AND so.ativo = true
            )
            ORDER BY s.nome
        """), {'admin_id': obra.admin_id, 'obra_id': obra_id}).fetchall()
        
    except Exception as e:
        logger.error(f"Erro ao buscar serviços disponíveis: {e}")
        servicos_disponiveis = []
    
    # Template simples para o modal
    template = '''
    <div class="modal fade" id="cadastrarServicoModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Cadastrar Serviço na Obra</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST">
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Serviço:</label>
                            <select name="servico_id" class="form-select" required>
                                <option value="">Selecione um serviço...</option>
                                {% for servico in servicos_disponiveis %}
                                <option value="{{ servico.id }}">{{ servico.nome }} - {{ servico.categoria }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Quantidade Planejada:</label>
                            <input type="number" name="quantidade_planejada" class="form-control" step="0.01" value="1.00" required>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="submit" class="btn btn-primary">Cadastrar Serviço</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    '''
    
    return render_template_string(template, servicos_disponiveis=servicos_disponiveis, obra=obra)