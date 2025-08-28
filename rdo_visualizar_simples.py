"""
Sistema simplificado de visualização RDO - Sem duplicações
"""
from flask import Blueprint, render_template, request, flash, redirect
from models import *
from sqlalchemy.orm import joinedload
import traceback

rdo_visual_bp = Blueprint('rdo_visual', __name__)

@rdo_visual_bp.route('/rdo/<int:id>')
def visualizar_rdo_simples(id):
    """Visualizar RDO de forma simples - apenas subatividades executadas"""
    try:
        # Buscar RDO
        rdo = RDO.query.options(
            joinedload(RDO.obra),
            joinedload(RDO.criado_por)
        ).filter(RDO.id == id).first()
        
        if not rdo:
            flash('RDO não encontrado.', 'error')
            return redirect('/funcionario/rdo/consolidado')
        
        # Buscar subatividades executadas
        subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
        
        # Buscar funcionários
        funcionarios = RDOMaoObra.query.options(
            joinedload(RDOMaoObra.funcionario)
        ).filter_by(rdo_id=rdo.id).all()
        
        # Organizar subatividades por serviço (apenas executadas)
        subatividades_por_servico = {}
        
        for sub in subatividades:
            servico = Servico.query.get(sub.servico_id)
            if not servico:
                continue
            
            if servico.id not in subatividades_por_servico:
                subatividades_por_servico[servico.id] = {
                    'servico': servico,
                    'subatividades': [],
                    'subatividades_nao_executadas': []  # Vazio por enquanto
                }
            
            subatividades_por_servico[servico.id]['subatividades'].append(sub)
        
        # Calcular estatísticas
        total_subatividades = len(subatividades)
        total_funcionarios = len(funcionarios)
        total_horas_trabalhadas = sum(f.horas_trabalhadas or 0 for f in funcionarios)
        
        # Progresso simplificado
        progresso_obra = 100.0 if total_subatividades > 0 else 0
        total_subatividades_obra = total_subatividades
        peso_por_subatividade = 100.0 / max(total_subatividades, 1)
        
        print(f"DEBUG SIMPLES: RDO {id} - {len(subatividades)} subatividades executadas")
        print(f"DEBUG SIMPLES: {len(subatividades_por_servico)} serviços diferentes")
        
        return render_template('rdo/visualizar_rdo_moderno.html', 
                             rdo=rdo, 
                             subatividades=subatividades,
                             subatividades_por_servico=subatividades_por_servico,
                             funcionarios=funcionarios,
                             total_subatividades=total_subatividades,
                             total_funcionarios=total_funcionarios,
                             progresso_obra=progresso_obra,
                             total_subatividades_obra=total_subatividades_obra,
                             peso_por_subatividade=peso_por_subatividade,
                             total_horas_trabalhadas=total_horas_trabalhadas)
        
    except Exception as e:
        print(f"ERRO VISUALIZAR RDO SIMPLES: {str(e)}")
        traceback.print_exc()
        flash('Erro ao carregar RDO.', 'error')
        return redirect('/funcionario/rdo/consolidado')