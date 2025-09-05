"""
Sistema de Validações Avançadas para RDO
Implementa todas as regras de negócio e validações críticas
"""
from datetime import datetime, date, timedelta
from flask import flash
from models import RDO, RDOServicoSubatividade, Obra, db
from sqlalchemy import func

class RDOValidationError(Exception):
    """Exceção específica para erros de validação de RDO"""
    pass

class RDOValidator:
    """Validador principal para todas as operações de RDO"""
    
    @staticmethod
    def validate_percentage(percentage_value):
        """Validar se a porcentagem está em um range válido"""
        if percentage_value is None:
            return True  # Permitir valores nulos
            
        try:
            value = float(percentage_value)
            if value < 0 or value > 100:
                raise RDOValidationError(f"Porcentagem deve estar entre 0 e 100%. Valor informado: {value}%")
            return True
        except (ValueError, TypeError):
            raise RDOValidationError(f"Porcentagem inválida: {percentage_value}")
    
    @staticmethod
    def validate_date_rules(data_relatorio, obra_id):
        """Validar regras relacionadas à data do RDO"""
        # Não permitir data futura
        if data_relatorio > date.today():
            raise RDOValidationError("Não é possível criar RDO para data futura")
        
        # Verificar se já existe RDO para a mesma obra na mesma data
        existing_rdo = RDO.query.filter_by(
            obra_id=obra_id,
            data_relatorio=data_relatorio
        ).first()
        
        if existing_rdo:
            raise RDOValidationError(f"Já existe RDO para esta obra na data {data_relatorio.strftime('%d/%m/%Y')}")
        
        return True
    
    @staticmethod
    def validate_percentage_progression(obra_id, subatividade_id, novo_percentual, servico_nome, subatividade_nome):
        """Validar se o progresso não está regredindo"""
        # Buscar último RDO com esta subatividade
        last_entry = db.session.query(RDOServicoSubatividade).join(RDO).filter(
            RDO.obra_id == obra_id,
            RDOServicoSubatividade.servico_id == subatividade_id,
            RDOServicoSubatividade.nome_subatividade == subatividade_nome
        ).order_by(RDO.data_relatorio.desc()).first()
        
        if last_entry and last_entry.percentual_conclusao:
            ultimo_percentual = float(last_entry.percentual_conclusao)
            if novo_percentual < ultimo_percentual:
                raise RDOValidationError(
                    f"Progresso não pode regredir! "
                    f"{servico_nome} - {subatividade_nome}: "
                    f"último valor era {ultimo_percentual}%, "
                    f"novo valor: {novo_percentual}%"
                )
        
        return True
    
    @staticmethod
    def validate_obra_status(obra_id, admin_id):
        """Validar se a obra está ativa e acessível"""
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        
        if not obra:
            raise RDOValidationError("Obra não encontrada ou sem permissão de acesso")
        
        # Verificar se obra está ativa
        if obra.status in ['finalizada', 'cancelada', 'pausada']:
            raise RDOValidationError(f"Não é possível criar RDO para obra com status: {obra.status}")
        
        return True
    
    @staticmethod
    def validate_long_gap_warning(obra_id):
        """Verificar se há um longo intervalo desde o último RDO"""
        last_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
        
        if last_rdo:
            days_gap = (date.today() - last_rdo.data_relatorio).days
            if days_gap > 7:  # Mais de 7 dias
                return {
                    'warning': True,
                    'days_gap': days_gap,
                    'message': f"Último RDO foi há {days_gap} dias. Considere revisar o progresso das subatividades."
                }
        
        return {'warning': False}
    
    @staticmethod
    def validate_concurrency_check(rdo_id, last_modified_by_client):
        """Verificar se RDO foi modificado por outro usuário (controle de concorrência)"""
        rdo = RDO.query.get(rdo_id)
        if not rdo:
            raise RDOValidationError("RDO não encontrado")
        
        # Comparar timestamp de última modificação
        if rdo.updated_at and last_modified_by_client:
            server_timestamp = rdo.updated_at.timestamp()
            client_timestamp = datetime.fromisoformat(last_modified_by_client).timestamp()
            
            if server_timestamp > client_timestamp:
                raise RDOValidationError(
                    "Este RDO foi modificado por outro usuário. "
                    "Por favor, recarregue a página para ver as alterações mais recentes."
                )
        
        return True
    
    @staticmethod
    def get_completion_alerts(subatividades_data):
        """Gerar alertas para subatividades que atingiram 100%"""
        alerts = []
        
        for sub in subatividades_data:
            percentual = float(sub.get('percentual_conclusao', 0))
            if percentual >= 100:
                alerts.append({
                    'type': 'success',
                    'message': f"🎉 Subatividade '{sub.get('nome_subatividade')}' foi concluída (100%)!"
                })
        
        return alerts
    
    @staticmethod
    def validate_logical_sequence(subatividades_data, servico_nome):
        """Validar sequência lógica das subatividades (regras específicas por tipo de serviço)"""
        # Regras específicas para diferentes tipos de serviço
        sequence_rules = {
            'alvenaria': ['marcacao', 'levantamento', 'chapisco', 'reboco'],
            'pintura': ['preparacao', 'primer', 'primeira_demao', 'demao_final'],
            'concretagem': ['armacao', 'forma', 'concretagem', 'acabamento']
        }
        
        warnings = []
        
        # Verificar sequência lógica se aplicável
        categoria = servico_nome.lower()
        for rule_category, expected_sequence in sequence_rules.items():
            if rule_category in categoria:
                # Verificar se etapas anteriores estão concluídas
                for i, sub in enumerate(subatividades_data):
                    percentual = float(sub.get('percentual_conclusao', 0))
                    nome_sub = sub.get('nome_subatividade', '').lower()
                    
                    if percentual > 0:
                        # Verificar se etapas anteriores estão adequadamente avançadas
                        for j, expected_step in enumerate(expected_sequence):
                            if expected_step in nome_sub and j > 0:
                                # Verificar etapa anterior
                                prev_step = expected_sequence[j-1]
                                prev_completed = any(
                                    prev_step in other_sub.get('nome_subatividade', '').lower() 
                                    and float(other_sub.get('percentual_conclusao', 0)) >= percentual * 0.8
                                    for other_sub in subatividades_data
                                )
                                
                                if not prev_completed:
                                    warnings.append({
                                        'type': 'warning',
                                        'message': f"⚠️ {servico_nome}: Considere avançar etapas anteriores antes de {sub.get('nome_subatividade')}"
                                    })
        
        return warnings

class RDOBusinessRules:
    """Regras de negócio específicas para RDO"""
    
    @staticmethod
    def generate_rdo_number(obra_id):
        """Gerar número sequencial para RDO"""
        try:
            # Buscar último número de RDO para esta obra
            last_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.numero_rdo.desc()).first()
        except RuntimeError:
            # Se não há contexto da aplicação, retornar número padrão
            return "RDO-001"
        
        if last_rdo and last_rdo.numero_rdo:
            try:
                # Extrair número da string (formato: RDO-001, RDO-002, etc.)
                last_number = int(last_rdo.numero_rdo.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        return f"RDO-{new_number:03d}"
    
    @staticmethod
    def calculate_overall_progress(obra_id):
        """Calcular progresso geral da obra baseado em todas as RDOs"""
        # Buscar última RDO da obra
        latest_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
        
        if not latest_rdo:
            return 0.0
        
        # Buscar todas as subatividades da última RDO
        subatividades = RDOServicoSubatividade.query.filter_by(
            rdo_id=latest_rdo.id,
            ativo=True
        ).all()
        
        if not subatividades:
            return 0.0
        
        # FÓRMULA UNIFICADA PROGRESSO (consistente com visualização)
        total_progress = sum(float(sub.percentual_conclusao or 0) for sub in subatividades)
        total_sub = len(subatividades)
        resultado = round((total_progress / (100 * total_sub)) * 100, 2) if total_sub > 0 else 0.0
        print(f"🎯 VALIDATIONS PROGRESSO: {total_progress}÷(100×{total_sub})×100 = {resultado}%")
        return resultado
    
    @staticmethod
    def suggest_next_activities(obra_id):
        """Sugerir próximas atividades baseado no histórico"""
        # Buscar subatividades que não estão em 100%
        latest_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
        
        if not latest_rdo:
            return []
        
        incomplete_activities = db.session.query(RDOServicoSubatividade).filter(
            RDOServicoSubatividade.rdo_id == latest_rdo.id,
            RDOServicoSubatividade.percentual_conclusao < 100,
            RDOServicoSubatividade.ativo == True
        ).all()
        
        suggestions = []
        for activity in incomplete_activities:
            current_progress = float(activity.percentual_conclusao or 0)
            suggested_increment = min(25.0, 100.0 - current_progress)  # Sugerir incremento de até 25%
            
            suggestions.append({
                'servico_nome': activity.servico.nome if activity.servico else 'N/A',
                'subatividade_nome': activity.nome_subatividade,
                'current_progress': current_progress,
                'suggested_increment': suggested_increment,
                'suggested_new_value': current_progress + suggested_increment
            })
        
        return suggestions

# Classe para auditoria e histórico
class RDOAuditLog:
    """Sistema de auditoria para RDOs"""
    
    @staticmethod
    def log_rdo_creation(rdo_id, user_id, ip_address=None):
        """Log da criação de RDO"""
        # Implementar log de auditoria aqui
        print(f"AUDIT: RDO {rdo_id} criado pelo usuário {user_id} from {ip_address}")
    
    @staticmethod
    def log_rdo_modification(rdo_id, user_id, changes, ip_address=None):
        """Log das modificações em RDO"""
        # Implementar log de auditoria aqui
        print(f"AUDIT: RDO {rdo_id} modificado pelo usuário {user_id}: {changes}")
    
    @staticmethod
    def log_rdo_deletion(rdo_id, user_id, reason=None, ip_address=None):
        """Log da exclusão de RDO"""
        # Implementar log de auditoria aqui
        print(f"AUDIT: RDO {rdo_id} excluído pelo usuário {user_id}: {reason}")