"""
API LIMPA para gerenciamento de serviços da obra
Sistema completamente funcional usando tabela servico_obra_real
"""

from flask import Blueprint, request, jsonify, session
from models import db, ServicoObraReal, Servico, Obra, Usuario
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

# Blueprint para as APIs
api_servicos_obra_bp = Blueprint('api_servicos_obra_limpa', __name__)

def get_admin_id():
    """Obtém admin_id do usuário logado"""
    try:
        if 'user_id' in session:
            user = Usuario.query.get(session['user_id'])
            if user:
                return user.admin_id or user.id
        return None
    except Exception as e:
        logger.error(f"Erro ao obter admin_id: {e}")
        return None

@api_servicos_obra_bp.route('/api/obra/<int:obra_id>/servicos', methods=['GET'])
def listar_servicos_obra(obra_id):
    """Lista serviços da obra (nova tabela)"""
    try:
        admin_id = get_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        logger.info(f"🔍 LISTANDO SERVIÇOS - obra_id={obra_id}, admin_id={admin_id}")
        
        # Buscar serviços da obra
        servicos_query = db.session.query(
            ServicoObraReal, Servico
        ).join(
            Servico, ServicoObraReal.servico_id == Servico.id
        ).filter(
            ServicoObraReal.obra_id == obra_id,
            ServicoObraReal.admin_id == admin_id,
            ServicoObraReal.ativo == True
        ).order_by(Servico.nome)
        
        servicos_lista = []
        for servico_obra, servico in servicos_query:
            servicos_lista.append({
                'id': servico_obra.id,
                'servico_id': servico.id,
                'nome': servico.nome,
                'categoria': servico.categoria,
                'descricao': servico.descricao or '',
                'quantidade_planejada': float(servico_obra.quantidade_planejada),
                'quantidade_executada': float(servico_obra.quantidade_executada),
                'percentual_concluido': float(servico_obra.percentual_concluido),
                'valor_unitario': float(servico_obra.valor_unitario or 0),
                'valor_total_planejado': float(servico_obra.valor_total_planejado or 0),
                'valor_total_executado': float(servico_obra.valor_total_executado or 0),
                'status': servico_obra.status,
                'prioridade': servico_obra.prioridade,
                'data_inicio_planejada': servico_obra.data_inicio_planejada.isoformat() if servico_obra.data_inicio_planejada else None,
                'data_fim_planejada': servico_obra.data_fim_planejada.isoformat() if servico_obra.data_fim_planejada else None,
                'observacoes': servico_obra.observacoes or ''
            })
        
        logger.info(f"✅ {len(servicos_lista)} serviços encontrados")
        return jsonify({
            'success': True,
            'servicos': servicos_lista,
            'total': len(servicos_lista)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar serviços: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_servicos_obra_bp.route('/api/obra/<int:obra_id>/servicos', methods=['POST'])
def adicionar_servico_obra(obra_id):
    """Adiciona serviço à obra (nova tabela)"""
    try:
        admin_id = get_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        data = request.get_json()
        servicos_ids = data.get('servicos_ids', [])
        
        logger.info(f"➕ ADICIONANDO SERVIÇOS - obra_id={obra_id}, servicos={servicos_ids}")
        
        if not servicos_ids:
            return jsonify({'success': False, 'error': 'Nenhum serviço selecionado'}), 400
        
        servicos_adicionados = 0
        
        for servico_id in servicos_ids:
            # Verificar se serviço existe
            servico = Servico.query.filter_by(
                id=servico_id, 
                admin_id=admin_id,
                ativo=True
            ).first()
            
            if not servico:
                logger.warning(f"⚠️ Serviço {servico_id} não encontrado")
                continue
            
            # Verificar se já existe
            existente = ServicoObraReal.query.filter_by(
                obra_id=obra_id,
                servico_id=servico_id,
                admin_id=admin_id,
                ativo=True
            ).first()
            
            if existente:
                logger.warning(f"⚠️ Serviço {servico.nome} já está na obra")
                continue
            
            # Criar novo registro
            novo_servico_obra = ServicoObraReal()
            novo_servico_obra.obra_id = obra_id
            novo_servico_obra.servico_id = servico_id
            novo_servico_obra.quantidade_planejada = 1.0
            novo_servico_obra.quantidade_executada = 0.0
            novo_servico_obra.percentual_concluido = 0.0
            novo_servico_obra.valor_unitario = servico.custo_unitario or 0.0
            novo_servico_obra.valor_total_planejado = servico.custo_unitario or 0.0
            novo_servico_obra.valor_total_executado = 0.0
            novo_servico_obra.status = 'Não Iniciado'
            novo_servico_obra.prioridade = 3
            novo_servico_obra.data_inicio_planejada = date.today()
            novo_servico_obra.observacoes = f'Adicionado em {date.today().strftime("%d/%m/%Y")}'
            novo_servico_obra.admin_id = admin_id
            novo_servico_obra.ativo = True
            
            db.session.add(novo_servico_obra)
            servicos_adicionados += 1
            logger.info(f"✅ Serviço {servico.nome} adicionado à obra")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{servicos_adicionados} serviços adicionados com sucesso',
            'adicionados': servicos_adicionados
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar serviços: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_servicos_obra_bp.route('/api/obra/<int:obra_id>/servico/<int:servico_obra_id>', methods=['PUT'])
def atualizar_servico_obra(obra_id, servico_obra_id):
    """Atualiza serviço da obra"""
    try:
        admin_id = get_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        servico_obra = ServicoObraReal.query.filter_by(
            id=servico_obra_id,
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not servico_obra:
            return jsonify({'success': False, 'error': 'Serviço não encontrado'}), 404
        
        data = request.get_json()
        
        # Atualizar campos permitidos
        if 'quantidade_executada' in data:
            servico_obra.quantidade_executada = float(data['quantidade_executada'])
        
        if 'percentual_concluido' in data:
            servico_obra.percentual_concluido = float(data['percentual_concluido'])
        
        if 'status' in data:
            servico_obra.status = data['status']
        
        if 'observacoes' in data:
            servico_obra.observacoes = data['observacoes']
        
        if 'data_inicio_real' in data and data['data_inicio_real']:
            servico_obra.data_inicio_real = datetime.fromisoformat(data['data_inicio_real']).date()
        
        if 'data_fim_real' in data and data['data_fim_real']:
            servico_obra.data_fim_real = datetime.fromisoformat(data['data_fim_real']).date()
        
        # Atualizar valor executado baseado na quantidade e valor unitário
        servico_obra.valor_total_executado = float(servico_obra.quantidade_executada) * float(servico_obra.valor_unitario)
        
        servico_obra.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Serviço da obra {servico_obra_id} atualizado")
        
        return jsonify({
            'success': True,
            'message': 'Serviço atualizado com sucesso'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar serviço: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_servicos_obra_bp.route('/api/obra/<int:obra_id>/servico/<int:servico_obra_id>', methods=['DELETE'])
def remover_servico_obra(obra_id, servico_obra_id):
    """Remove serviço da obra (desativa)"""
    try:
        admin_id = get_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        servico_obra = ServicoObraReal.query.filter_by(
            id=servico_obra_id,
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if not servico_obra:
            return jsonify({'success': False, 'error': 'Serviço não encontrado'}), 404
        
        # Desativar ao invés de deletar
        servico_obra.ativo = False
        servico_obra.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Serviço da obra {servico_obra_id} removido")
        
        return jsonify({
            'success': True,
            'message': 'Serviço removido com sucesso'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao remover serviço: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500