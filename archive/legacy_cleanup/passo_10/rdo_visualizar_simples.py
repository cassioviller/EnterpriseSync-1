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
            joinedload(RDO.criado_por),
            joinedload(RDO.fotos)
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
        
        # Progresso baseado na nova lógica corrigida
        try:
            # Buscar total de subatividades planejadas para a obra
            from models import ServicoObra, SubatividadeMestre
            servicos_da_obra = ServicoObra.query.filter_by(obra_id=rdo.obra_id).all()
            total_subatividades_obra = 0
            
            for servico_obra in servicos_da_obra:
                subatividades_servico = SubatividadeMestre.query.filter_by(
                    servico_id=servico_obra.servico_id
                ).all()
                total_subatividades_obra += len(subatividades_servico)
            
            # Fallback: usar subatividades únicas executadas
            if total_subatividades_obra == 0:
                subatividades_unicas = db.session.query(
                    RDOServicoSubatividade.servico_id,
                    RDOServicoSubatividade.nome_subatividade
                ).join(RDO).filter(RDO.obra_id == rdo.obra_id).distinct().all()
                total_subatividades_obra = len(subatividades_unicas)
            
            # Calcular progresso: soma dos percentuais / total de subatividades
            if total_subatividades_obra > 0:
                soma_percentuais = sum(sub.percentual_conclusao or 0 for sub in subatividades)
                progresso_obra = round(soma_percentuais / total_subatividades_obra, 1)
                peso_por_subatividade = 100.0 / total_subatividades_obra
            else:
                progresso_obra = 0
                peso_por_subatividade = 0
                
        except Exception as e:
            print(f"ERRO CÁLCULO PROGRESSO SIMPLES: {str(e)}")
            # Fallback básico
            progresso_obra = 0
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