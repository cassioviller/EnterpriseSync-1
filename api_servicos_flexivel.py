# API PARA SISTEMA FLEXÍVEL DE SERVIÇOS RDO
from flask import Blueprint, jsonify, request
from models import db, Obra, ConfiguracaoServicoObra
from bypass_auth import obter_admin_id
import logging

api_servicos_bp = Blueprint('api_servicos', __name__)
logger = logging.getLogger(__name__)

# CONFIGURAÇÕES PADRÃO DE SERVIÇOS POR TIPO DE OBRA
TEMPLATES_SERVICOS = {
    'basico_2_servicos': {
        'nome': 'Básico - 2 Serviços (5 subatividades cada)',
        'servicos': [
            {
                'nome': 'Estrutura Metálica',
                'categoria': 'estrutural',
                'cor_badge': 'success',
                'subatividades': [
                    'Montagem de Formas',
                    'Armação de Ferro', 
                    'Concretagem',
                    'Cura do Concreto',
                    'Desmontagem'
                ]
            },
            {
                'nome': 'Manta PVC',
                'categoria': 'cobertura',
                'cor_badge': 'info',
                'subatividades': [
                    'Preparação da Superfície',
                    'Aplicação do Primer',
                    'Instalação da Manta',
                    'Acabamento e Vedação',
                    'Teste de Estanqueidade'
                ]
            }
        ]
    },
    'completo_3_servicos': {
        'nome': 'Completo - 3 Serviços (variação 3-4-4)',
        'servicos': [
            {
                'nome': 'Estrutura Metálica',
                'categoria': 'estrutural', 
                'cor_badge': 'success',
                'subatividades': [
                    'Medição e Marcação',
                    'Montagem Estrutural',
                    'Concretagem Final'
                ]
            },
            {
                'nome': 'Manta PVC',
                'categoria': 'cobertura',
                'cor_badge': 'info', 
                'subatividades': [
                    'Preparação da Superfície',
                    'Aplicação do Primer',
                    'Instalação da Manta',
                    'Acabamento e Vedação'
                ]
            },
            {
                'nome': 'Beiral Metálico',
                'categoria': 'acabamento',
                'cor_badge': 'warning',
                'subatividades': [
                    'Medição e Marcação',
                    'Corte das Peças',
                    'Fixação dos Suportes', 
                    'Instalação do Beiral'
                ]
            }
        ]
    }
}

@api_servicos_bp.route('/api/obras/<int:obra_id>/servicos', methods=['GET'])
def obter_servicos_obra(obra_id):
    """Retorna configuração de serviços para uma obra específica"""
    try:
        admin_id = obter_admin_id()
        
        # Verificar se obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        # Buscar configuração específica da obra
        configuracao = ConfiguracaoServicoObra.query.filter_by(obra_id=obra_id).first()
        
        if configuracao and configuracao.servicos_config:
            # Usar configuração personalizada
            servicos_data = configuracao.servicos_config
            template_usado = 'personalizado'
        else:
            # Usar template padrão baseado no tipo da obra ou fallback
            template_key = getattr(obra, 'tipo_servicos', 'basico_2_servicos')
            if template_key not in TEMPLATES_SERVICOS:
                template_key = 'basico_2_servicos'
            
            servicos_data = TEMPLATES_SERVICOS[template_key]
            template_usado = template_key
        
        logger.info(f"Serviços carregados para obra {obra_id}: template={template_usado}")
        
        return jsonify({
            'success': True,
            'obra_id': obra_id,
            'obra_nome': obra.nome,
            'template_usado': template_usado,
            'servicos': servicos_data['servicos'],
            'total_servicos': len(servicos_data['servicos']),
            'total_subatividades': sum(len(s['subatividades']) for s in servicos_data['servicos'])
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter serviços da obra {obra_id}: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@api_servicos_bp.route('/api/obras/<int:obra_id>/servicos', methods=['POST'])  
def configurar_servicos_obra(obra_id):
    """Configura serviços personalizados para uma obra"""
    try:
        admin_id = obter_admin_id()
        
        # Verificar se obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        dados = request.get_json()
        
        # Validar dados recebidos
        if not dados or 'servicos' not in dados:
            return jsonify({'error': 'Dados de serviços inválidos'}), 400
        
        # Buscar ou criar configuração
        configuracao = ConfiguracaoServicoObra.query.filter_by(obra_id=obra_id).first()
        if not configuracao:
            configuracao = ConfiguracaoServicoObra(obra_id=obra_id)
        
        # Atualizar configuração
        configuracao.servicos_config = {
            'servicos': dados['servicos'],
            'configurado_em': str(datetime.now()),
            'configurado_por': admin_id
        }
        
        db.session.add(configuracao)
        db.session.commit()
        
        logger.info(f"Configuração de serviços salva para obra {obra_id}")
        
        return jsonify({
            'success': True,
            'message': 'Configuração salva com sucesso',
            'total_servicos': len(dados['servicos'])
        })
        
    except Exception as e:
        logger.error(f"Erro ao configurar serviços da obra {obra_id}: {str(e)}")
        return jsonify({'error': 'Erro ao salvar configuração'}), 500

@api_servicos_bp.route('/api/templates-servicos', methods=['GET'])
def listar_templates():
    """Lista todos os templates disponíveis"""
    try:
        templates = []
        for key, template in TEMPLATES_SERVICOS.items():
            templates.append({
                'id': key,
                'nome': template['nome'],
                'total_servicos': len(template['servicos']),
                'total_subatividades': sum(len(s['subatividades']) for s in template['servicos']),
                'servicos_resumo': [s['nome'] for s in template['servicos']]
            })
        
        return jsonify({
            'success': True,
            'templates': templates
        })
        
    except Exception as e:
        logger.error(f"Erro ao listar templates: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

# Modelo para configuração flexível
class ConfiguracaoServicoObra(db.Model):
    __tablename__ = 'configuracao_servico_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    servicos_config = db.Column(db.JSON)  # Configuração flexível em JSON
    template_base = db.Column(db.String(100))  # Template usado como base
    criado_em = db.Column(db.DateTime, default=db.func.current_timestamp())
    atualizado_em = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Relacionamento
    obra = db.relationship('Obra', backref='configuracao_servicos')