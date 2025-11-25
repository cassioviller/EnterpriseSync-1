"""
Sistema de Fluxo de Dados Automático SIGE v8.0
Implementa triggers e webhooks para integração end-to-end entre módulos
Baseado no documento: FLUXO COMPLETO DE DADOS DO SIGE v8.0
"""

from datetime import datetime, date
import logging
from models import AlocacaoEquipe, Proposta
from app import db

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TriggerAutomatico:
    """
    Classe para gerenciar triggers automáticos entre módulos
    Implementa a jornada end-to-end conforme especificação técnica
    """
    
    @staticmethod
    def on_proposta_aprovada(proposta_id):
        """
        TRIGGER: Proposta Aprovada → Cascata de Processos Automáticos
        
        Fase 2: Aprovação e Transformação - De Proposta a Obra
        Conforme documentação: "desencadeia uma cascata de processos automatizados"
        """
        try:
            from integracoes_automaticas import processar_aprovacao_proposta
            sucesso = processar_aprovacao_proposta(proposta_id)
            
            if sucesso:
                logger.info(f"✅ TRIGGER executado: Proposta {proposta_id} aprovada")
                return True
            else:
                logger.error(f"❌ TRIGGER falhou: Proposta {proposta_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no trigger de aprovação: {e}")
            return False
    
    @staticmethod
    def on_equipe_alocada(alocacao_id):
        """
        TRIGGER: Equipe Alocada → RDO Automático + Tracking
        
        Fase 3: Execução e Monitoramento - Dados em Tempo Real
        """
        try:
            from integracoes_automaticas import processar_alocacao_equipe
            sucesso = processar_alocacao_equipe(alocacao_id)
            
            if sucesso:
                logger.info(f"✅ TRIGGER executado: Equipe alocada {alocacao_id}")
                return True
            else:
                logger.error(f"❌ TRIGGER falhou: Alocação {alocacao_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no trigger de alocação: {e}")
            return False
    
    @staticmethod
    def on_material_movimentado(movimento_id):
        """
        TRIGGER: Material Movimentado → Contabilização + Alertas
        
        Integração Módulo 4 (Almoxarifado) com Módulo 7 (Contabilidade)
        """
        try:
            from integracoes_automaticas import processar_movimento_estoque
            sucesso = processar_movimento_estoque(movimento_id)
            
            if sucesso:
                logger.info(f"✅ TRIGGER executado: Material movimentado {movimento_id}")
                return True
            else:
                logger.error(f"❌ TRIGGER falhou: Movimento {movimento_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no trigger de movimento: {e}")
            return False
    
    @staticmethod
    def on_ponto_registrado(registro_id):
        """
        TRIGGER: Ponto Registrado → Produtividade + RDO
        
        Integração Módulo 5 (Reconhecimento Facial) com demais módulos
        """
        try:
            from integracoes_automaticas import processar_registro_ponto
            sucesso = processar_registro_ponto(registro_id)
            
            if sucesso:
                logger.info(f"✅ TRIGGER executado: Ponto registrado {registro_id}")
                return True
            else:
                logger.error(f"❌ TRIGGER falhou: Registro {registro_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no trigger de ponto: {e}")
            return False
    
    @staticmethod
    def on_fechamento_mensal(admin_id, mes_referencia):
        """
        TRIGGER: Fechamento Mensal → Processamento Completo
        
        Fase 4: Processamento Financeiro - Automação Contábil
        """
        try:
            from integracoes_automaticas import processar_fechamento_mensal
            sucesso = processar_fechamento_mensal(admin_id, mes_referencia)
            
            if sucesso:
                logger.info(f"✅ TRIGGER executado: Fechamento {mes_referencia}")
                return True
            else:
                logger.error(f"❌ TRIGGER falhou: Fechamento {mes_referencia}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no trigger de fechamento: {e}")
            return False

class WebhookManager:
    """
    Gerenciador de webhooks para notificações externas
    Implementa comunicação com sistemas externos conforme necessário
    """
    
    @staticmethod
    def notificar_cliente_aprovacao(proposta_id):
        """Webhook para notificar cliente sobre aprovação de proposta"""
        # Implementar notificação via email/SMS
        # Atualizar CRM externo se integrado
        pass
    
    @staticmethod
    def notificar_progresso_obra(obra_id, percentual):
        """Webhook para notificar progresso de obra"""
        # Atualizar sistemas externos
        # Enviar relatórios automáticos
        pass
    
    @staticmethod
    def alerta_estoque_minimo(produto_id):
        """Webhook para alertar sobre estoque mínimo"""
        # Integrar com sistemas de compras
        # Notificar fornecedores automaticamente
        pass

class MonitoramentoFluxo:
    """
    Classe para monitoramento do fluxo de dados
    Implementa métricas e alertas sobre a saúde do sistema
    """
    
    @staticmethod
    def verificar_integridade_fluxo():
        """Verifica a integridade do fluxo de dados entre módulos"""
        verificacoes = {
            'propostas_sem_obra': 0,
            'alocacoes_sem_rdo': 0,
            'movimentos_sem_contabilizacao': 0,
            'registros_sem_processamento': 0
        }
        
        try:
            # Verificar propostas aprovadas sem obra criada
            propostas_orphans = Proposta.query.filter(
                Proposta.status == 'APROVADA',
                Proposta.obra_id.is_(None)
            ).count()
            verificacoes['propostas_sem_obra'] = propostas_orphans
            
            # Verificar alocações sem RDO gerado
            alocacoes_orphans = AlocacaoEquipe.query.filter(
                AlocacaoEquipe.status == 'ATIVA',
                AlocacaoEquipe.rdo_gerado == False
            ).count()
            verificacoes['alocacoes_sem_rdo'] = alocacoes_orphans
            
            # Mais verificações podem ser adicionadas aqui
            
            return verificacoes
            
        except Exception as e:
            logger.error(f"Erro na verificação de integridade: {e}")
            return None
    
    @staticmethod
    def gerar_relatorio_fluxo(admin_id, periodo):
        """Gera relatório detalhado do fluxo de dados"""
        relatorio = {
            'periodo': periodo,
            'admin_id': admin_id,
            'total_propostas': 0,
            'total_obras_ativas': 0,
            'total_alocacoes': 0,
            'total_movimentos': 0,
            'eficiencia_fluxo': 0
        }
        
        # Implementar cálculos do relatório
        # Baseado nos dados coletados dos módulos
        
        return relatorio

# ===============================================================
# == FUNCÕES DE CONVENIÊNCIA PARA USO NOS VIEWS
# ===============================================================

def executar_trigger_aprovacao(proposta_id):
    """Executa trigger de aprovação de proposta"""
    return TriggerAutomatico.on_proposta_aprovada(proposta_id)

def executar_trigger_alocacao(alocacao_id):
    """Executa trigger de alocação de equipe"""
    return TriggerAutomatico.on_equipe_alocada(alocacao_id)

def executar_trigger_movimento(movimento_id):
    """Executa trigger de movimento de estoque"""
    return TriggerAutomatico.on_material_movimentado(movimento_id)

def executar_trigger_ponto(registro_id):
    """Executa trigger de registro de ponto"""
    return TriggerAutomatico.on_ponto_registrado(registro_id)

def executar_trigger_fechamento(admin_id, mes_referencia):
    """Executa trigger de fechamento mensal"""
    return TriggerAutomatico.on_fechamento_mensal(admin_id, mes_referencia)

def verificar_saude_sistema():
    """Verifica a saúde geral do sistema de fluxo de dados"""
    return MonitoramentoFluxo.verificar_integridade_fluxo()

def gerar_relatorio_eficiencia(admin_id, periodo):
    """Gera relatório de eficiência do fluxo de dados"""
    return MonitoramentoFluxo.gerar_relatorio_fluxo(admin_id, periodo)

# ===============================================================
# == DECORATORS PARA AUTOMATIZAÇÃO
# ===============================================================

def auto_trigger(trigger_func):
    """
    Decorator para executar triggers automaticamente após operações
    
    Uso:
    @auto_trigger(executar_trigger_aprovacao)
    def aprovar_proposta(proposta_id):
        # Lógica de aprovação
        return proposta_id
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if result:
                trigger_func(result)
            return result
        return wrapper
    return decorator

# Exemplo de uso do decorator:
# from fluxo_dados_automatico import auto_trigger, executar_trigger_aprovacao
#
# @auto_trigger(executar_trigger_aprovacao)
# def aprovar_proposta_automatico(proposta_id):
#     # Lógica de aprovação da proposta
#     proposta = Proposta.query.get(proposta_id)
#     proposta.status = 'APROVADA'
#     db.session.commit()
#     return proposta_id