"""
API para sistema de organização avançada de propostas
"""

from flask import Blueprint, request, jsonify
from models import db, PropostaTemplate, PropostaComercialSIGE, PropostaItem
try:
    from bypass_auth import get_current_user_bypass
except ImportError:
    def get_current_user_bypass():
        from flask_login import current_user
        return current_user

api_organizer = Blueprint('api_organizer', __name__, url_prefix='/api')

@api_organizer.route('/templates/listar', methods=['GET'])
def listar_templates():
    """Lista todos os templates disponíveis"""
    try:
        current_user = get_current_user_bypass()
        admin_id = getattr(current_user, 'admin_id', None) or current_user.id
        
        templates = PropostaTemplate.query.filter_by(
            admin_id=admin_id, 
            ativo=True
        ).order_by(PropostaTemplate.categoria, PropostaTemplate.nome).all()
        
        templates_data = []
        for template in templates:
            templates_data.append({
                'id': template.id,
                'nome': template.nome,
                'categoria': template.categoria,
                'total_itens': len(template.itens_padrao) if template.itens_padrao else 0,
                'descricao': template.descricao
            })
        
        return jsonify({
            'success': True,
            'templates': templates_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao listar templates: {str(e)}'
        }), 500

@api_organizer.route('/templates/carregar-multiplos', methods=['POST'])
def carregar_templates_multiplos():
    """Carrega múltiplos templates em uma proposta"""
    try:
        data = request.get_json()
        template_ids = data.get('template_ids', [])
        proposta_id = data.get('proposta_id')
        
        if not template_ids or not proposta_id:
            return jsonify({
                'success': False,
                'message': 'IDs dos templates e da proposta são obrigatórios'
            }), 400
        
        # Buscar proposta
        proposta = PropostaComercialSIGE.query.get(proposta_id)
        if not proposta:
            return jsonify({
                'success': False,
                'message': 'Proposta não encontrada'
            }), 404
        
        # Buscar próximo número de item
        ultimo_item = PropostaItem.query.filter_by(proposta_id=proposta_id).order_by(PropostaItem.item_numero.desc()).first()
        proximo_numero = (ultimo_item.item_numero + 1) if ultimo_item else 1
        
        novos_itens = []
        grupo_ordem = 1
        
        # Para cada template selecionado
        for template_id in template_ids:
            template = PropostaTemplate.query.get(template_id)
            if not template or not template.itens_padrao:
                continue
            
            # Incrementar contador de uso
            template.incrementar_uso()
            
            item_ordem = 1
            # Adicionar itens do template
            for item_template in template.itens_padrao:
                novo_item = PropostaItem(
                    proposta_id=proposta_id,
                    item_numero=proximo_numero,
                    descricao=item_template.get('descricao', ''),
                    quantidade=float(item_template.get('quantidade', 1)),
                    unidade=item_template.get('unidade', 'un'),
                    preco_unitario=float(item_template.get('preco_unitario', 0)),
                    ordem=proximo_numero,
                    # Novos campos de organização
                    categoria_titulo=template.categoria,
                    template_origem_id=template.id,
                    template_origem_nome=template.nome,
                    grupo_ordem=grupo_ordem,
                    item_ordem_no_grupo=item_ordem
                )
                
                db.session.add(novo_item)
                novos_itens.append(novo_item.to_dict())
                
                proximo_numero += 1
                item_ordem += 1
            
            grupo_ordem += 1
        
        # Recalcular valor total
        proposta.calcular_valor_total()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{len(novos_itens)} itens adicionados com sucesso',
            'novos_itens': novos_itens
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao carregar templates: {str(e)}'
        }), 500

@api_organizer.route('/propostas/salvar-organizacao', methods=['POST'])
def salvar_organizacao():
    """Salva a organização personalizada da proposta"""
    try:
        data = request.get_json()
        proposta_id = data.get('proposta_id')
        organizacao = data.get('organizacao', [])
        
        if not proposta_id:
            return jsonify({
                'success': False,
                'message': 'ID da proposta é obrigatório'
            }), 400
        
        # Atualizar organização dos itens
        for categoria_data in organizacao:
            for item_data in categoria_data.get('itens', []):
                item = PropostaItem.query.get(item_data['item_id'])
                if item:
                    item.categoria_titulo = item_data['categoria_titulo']
                    item.grupo_ordem = item_data['grupo_ordem']
                    item.item_ordem_no_grupo = item_data['item_ordem_no_grupo']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Organização salva com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao salvar organização: {str(e)}'
        }), 500

@api_organizer.route('/propostas/<int:proposta_id>/itens-organizados', methods=['GET'])
def obter_itens_organizados(proposta_id):
    """Obtém itens da proposta organizados por categoria"""
    try:
        itens = PropostaItem.query.filter_by(proposta_id=proposta_id).order_by(
            PropostaItem.grupo_ordem.asc(),
            PropostaItem.item_ordem_no_grupo.asc()
        ).all()
        
        # Organizar por categoria
        categorias = {}
        for item in itens:
            categoria = item.categoria_titulo or item.template_origem_nome or 'Itens Gerais'
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(item.to_dict())
        
        return jsonify({
            'success': True,
            'categorias': categorias
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao obter itens organizados: {str(e)}'
        }), 500