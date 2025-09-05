"""
RDO API Refatorada - Aplicando Princípios de Joris Kuypers
=========================================================

Arquitetura robusta para salvamento de RDO com separação clara de responsabilidades:
- Identificação de Contexto (descobrir qual serviço usar)
- Processamento de Dados (extrair subatividades do formulário)
- Persistência Consistente (salvar no serviço correto)

Princípio: "KAIPA DA PRIMEIRA VEZ CERTO"
"""

from flask import Blueprint, request, jsonify, session
from models import RDO, RDOServicoSubatividade, Obra, Servico, db
from auth import funcionario_required
import logging
from datetime import datetime

# Configurar logging detalhado
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

rdo_api_bp = Blueprint('rdo_api_refactored', __name__)


class RDOServiceContext:
    """
    Classe para identificar e gerenciar o contexto do serviço correto para uma RDO.
    Responsabilidade única: descobrir qual serviço usar baseado no histórico.
    """
    
    def __init__(self, obra_id: int, admin_id: int):
        self.obra_id = obra_id
        self.admin_id = admin_id
        self.servico_id = None
        self.servico_nome = None
        
    def discover_service_from_history(self) -> bool:
        """
        Descobre o serviço correto baseado na última RDO desta obra.
        Retorna True se conseguiu identificar, False caso contrário.
        """
        try:
            # Buscar última RDO desta obra
            ultimo_servico = db.session.query(RDOServicoSubatividade)\
                .join(RDO)\
                .filter(
                    RDO.obra_id == self.obra_id,
                    RDO.admin_id == self.admin_id
                )\
                .order_by(RDO.data_relatorio.desc())\
                .first()
            
            if ultimo_servico:
                self.servico_id = ultimo_servico.servico_id
                
                # Buscar nome do serviço
                servico = Servico.query.get(self.servico_id)
                if servico:
                    self.servico_nome = servico.nome
                    logger.info(f"✅ Serviço descoberto do histórico: {self.servico_nome} (ID: {self.servico_id})")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Erro ao descobrir serviço do histórico: {e}")
            
        return False
        
    def discover_service_from_work_services(self) -> bool:
        """
        Fallback: buscar primeiro serviço ativo da obra.
        """
        try:
            from models import ServicoObraReal
            
            servico_obra = db.session.query(ServicoObraReal)\
                .join(Servico)\
                .filter(
                    ServicoObraReal.obra_id == self.obra_id,
                    ServicoObraReal.ativo == True,
                    Servico.admin_id == self.admin_id,
                    Servico.ativo == True
                )\
                .first()
                
            if servico_obra and servico_obra.servico:
                self.servico_id = servico_obra.servico.id
                self.servico_nome = servico_obra.servico.nome
                logger.info(f"✅ Serviço descoberto da obra: {self.servico_nome} (ID: {self.servico_id})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao descobrir serviço da obra: {e}")
            
        return False
        
    def get_service_context(self) -> tuple:
        """
        Método principal: descobre o serviço correto usando estratégia em cascata.
        Retorna (servico_id, servico_nome) ou (None, None) se falhar.
        """
        # Estratégia 1: Histórico de RDOs
        if self.discover_service_from_history():
            return self.servico_id, self.servico_nome
            
        # Estratégia 2: Primeiro serviço da obra
        if self.discover_service_from_work_services():
            return self.servico_id, self.servico_nome
            
        logger.warning(f"⚠️ Não foi possível descobrir serviço para obra {self.obra_id}")
        return None, None


class RDOSubActivityProcessor:
    """
    Classe para processar dados de subatividades do formulário.
    Responsabilidade única: extrair e validar dados das subatividades.
    """
    
    def __init__(self, form_data: dict):
        self.form_data = form_data
        self.subactivities = []
        
    def extract_subactivities(self) -> list:
        """
        Extrai subatividades do formulário usando padrão consistente.
        Retorna lista de dicionários com dados das subatividades.
        """
        subactivities = []
        
        for field_name, field_value in self.form_data.items():
            # Padrão: subatividade_{servico_id}_{sub_id}_percentual
            if field_name.startswith('subatividade_') and field_name.endswith('_percentual'):
                try:
                    # Extrair IDs do nome do campo
                    parts = field_name.replace('subatividade_', '').replace('_percentual', '').split('_')
                    if len(parts) >= 2:
                        original_service_id = int(parts[0])
                        sub_id = parts[1]
                        
                        # Buscar percentual
                        percentual = float(field_value) if field_value else 0.0
                        
                        # Buscar observações
                        obs_field = f"subatividade_{original_service_id}_{sub_id}_observacoes"
                        observacoes = self.form_data.get(obs_field, "")
                        
                        # Buscar nome da subatividade
                        nome_field = f"nome_subatividade_{original_service_id}_{sub_id}"
                        nome = self.form_data.get(nome_field, f"Subatividade {sub_id}")
                        
                        subactivities.append({
                            'original_service_id': original_service_id,
                            'sub_id': sub_id,
                            'nome': nome,
                            'percentual': percentual,
                            'observacoes': observacoes
                        })
                        
                        logger.debug(f"📋 Subatividade extraída: {nome} - {percentual}%")
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"⚠️ Erro ao processar campo {field_name}: {e}")
                    continue
                    
        logger.info(f"✅ {len(subactivities)} subatividades extraídas do formulário")
        return subactivities


class RDOPersistenceManager:
    """
    Classe para gerenciar a persistência robusta de RDO.
    Responsabilidade única: salvar dados no banco de forma consistente.
    """
    
    def __init__(self, admin_id: int):
        self.admin_id = admin_id
        
    def save_rdo_with_subactivities(self, rdo: RDO, subactivities: list, target_service_id: int) -> bool:
        """
        Salva RDO com todas as subatividades no serviço correto.
        Usa transação para garantir consistência.
        """
        try:
            db.session.begin()
            
            # Salvar RDO principal
            db.session.add(rdo)
            db.session.flush()  # Para obter o ID
            
            logger.info(f"💾 RDO {rdo.numero_rdo} criado com ID {rdo.id}")
            
            # Salvar todas as subatividades no serviço correto
            for sub_data in subactivities:
                subatividade = RDOServicoSubatividade(
                    rdo_id=rdo.id,
                    servico_id=target_service_id,  # SEMPRE usar o serviço descoberto
                    nome_subatividade=sub_data['nome'],
                    percentual_conclusao=sub_data['percentual'],
                    observacoes_tecnicas=sub_data['observacoes'],
                    admin_id=self.admin_id,
                    ativo=True
                )
                
                db.session.add(subatividade)
                logger.debug(f"💾 Subatividade salva: {sub_data['nome']} -> Serviço {target_service_id}")
            
            # Commit da transação
            db.session.commit()
            logger.info(f"✅ RDO {rdo.numero_rdo} salvo com {len(subactivities)} subatividades")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao salvar RDO: {e}")
            return False


@rdo_api_bp.route('/api/rdo/save', methods=['POST'])
@funcionario_required
def save_rdo_refactored():
    """
    API refatorada para salvamento de RDO.
    Arquitetura robusta aplicando princípios de Joris Kuypers.
    """
    try:
        # Obter dados básicos
        funcionario_id = session.get('funcionario_id')
        admin_id = session.get('admin_id')
        obra_id = request.form.get('obra_id', type=int)
        
        if not all([funcionario_id, admin_id, obra_id]):
            return jsonify({
                'success': False,
                'error': 'Dados de sessão ou obra inválidos'
            }), 400
            
        logger.info(f"🎯 Iniciando salvamento RDO - Obra: {obra_id}, Admin: {admin_id}")
        
        # FASE 1: Descobrir Contexto do Serviço
        service_context = RDOServiceContext(obra_id, admin_id)
        target_service_id, service_name = service_context.get_service_context()
        
        if not target_service_id:
            return jsonify({
                'success': False,
                'error': 'Não foi possível identificar o serviço para esta obra'
            }), 400
            
        logger.info(f"🎯 Serviço identificado: {service_name} (ID: {target_service_id})")
        
        # FASE 2: Processar Dados das Subatividades
        processor = RDOSubActivityProcessor(request.form.to_dict())
        subactivities = processor.extract_subactivities()
        
        if not subactivities:
            return jsonify({
                'success': False,
                'error': 'Nenhuma subatividade encontrada no formulário'
            }), 400
        
        # FASE 3: Criar RDO Principal
        data_relatorio = request.form.get('data_relatorio')
        if data_relatorio:
            data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
        else:
            data_relatorio = datetime.now().date()
            
        # Gerar número RDO
        count_rdos = RDO.query.filter_by(admin_id=admin_id).count()
        numero_rdo = f"RDO-{admin_id}-{data_relatorio.year}-{count_rdos + 1:03d}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            obra_id=obra_id,
            funcionario_id=funcionario_id,
            data_relatorio=data_relatorio,
            observacoes_gerais=request.form.get('observacoes_finais', ''),
            local=request.form.get('local', 'Campo'),
            admin_id=admin_id
        )
        
        # FASE 4: Persistir com Transação
        persistence_manager = RDOPersistenceManager(admin_id)
        success = persistence_manager.save_rdo_with_subactivities(
            rdo, subactivities, target_service_id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': f'RDO {numero_rdo} salvo com sucesso',
                'rdo_id': rdo.id,
                'numero_rdo': numero_rdo,
                'servico_usado': service_name,
                'total_subatividades': len(subactivities)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro interno ao salvar RDO'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro crítico na API RDO: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500