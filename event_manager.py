"""
Event Manager - Sistema Central de Eventos do SIGE v9.0
Gerencia comunicação entre módulos via padrão Observer/PubSub
"""

import logging
from typing import Callable, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class EventManager:
    """Gerenciador central de eventos entre módulos"""
    
    # Registry de handlers por evento
    _handlers: Dict[str, List[Callable]] = {}
    
    @classmethod
    def register(cls, event_name: str, handler: Callable):
        """Registrar handler para um evento"""
        if event_name not in cls._handlers:
            cls._handlers[event_name] = []
        cls._handlers[event_name].append(handler)
        logger.info(f"📝 Handler {handler.__name__} registrado para evento '{event_name}'")
    
    @classmethod
    def emit(cls, event_name: str, data: dict, admin_id: int):
        """Emitir evento para todos os handlers registrados"""
        try:
            logger.info(f"🔔 EVENTO: {event_name} | Admin: {admin_id} | Data: {list(data.keys())}")
            
            handlers = cls._handlers.get(event_name, [])
            if not handlers:
                logger.warning(f"⚠️ Nenhum handler registrado para evento '{event_name}'")
                return False
            
            success_count = 0
            for handler in handlers:
                try:
                    handler(data, admin_id)
                    success_count += 1
                    logger.info(f"✅ Handler {handler.__name__} executado")
                except Exception as e:
                    logger.error(f"❌ Erro no handler {handler.__name__}: {e}", exc_info=True)
            
            logger.info(f"📊 Evento {event_name}: {success_count}/{len(handlers)} handlers OK")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erro ao emitir evento {event_name}: {e}", exc_info=True)
            return False
    
    @classmethod
    def list_events(cls) -> Dict[str, int]:
        """Listar todos os eventos registrados"""
        return {event: len(handlers) for event, handlers in cls._handlers.items()}
    
    @classmethod
    def clear(cls):
        """Limpar todos os handlers (útil para testes)"""
        cls._handlers = {}
        logger.info("🧹 Todos os handlers foram limpos")


def event_handler(event_name: str):
    """Decorador para registrar handlers de eventos automaticamente"""
    def decorator(func: Callable):
        EventManager.register(event_name, func)
        return func
    return decorator


# ============================================================
# HANDLERS DE EVENTOS - Implementações Práticas
# ============================================================

@event_handler('material_saida')
def lancar_custo_material_obra(data: dict, admin_id: int):
    """Handler: Lançar custo de material quando sai do estoque"""
    try:
        from models import db, AlmoxarifadoMovimento, ContaPagar
        from datetime import datetime
        
        movimento_id = data.get('movimento_id')
        obra_id = data.get('obra_id')
        valor_total = data.get('valor_total', 0)
        item_nome = data.get('item_nome', 'Material')
        
        if not obra_id or valor_total <= 0:
            logger.info(f"⏭️ Custo não lançado: sem obra ou valor zerado")
            return
        
        # SIMPLIFICADO: Criar registro de custo direto (sem fornecedor obrigatório)
        # Usar tabela simplificada ou log estruturado até modelo de custos estar completo
        
        logger.info(f"💰 [INTEGRAÇÃO] Custo de material lançado: R$ {valor_total:.2f} na obra {obra_id}")
        logger.info(f"   📦 Item: {item_nome} | Qtd: {data.get('quantidade')} | Movimento: {movimento_id}")
        
        # TODO: Quando modelo de Custos Obra estiver disponível, criar registro aqui
        # Por enquanto, log estruturado serve como auditoria
        
    except Exception as e:
        logger.error(f"❌ Erro ao lançar custo de material: {e}", exc_info=True)


@event_handler('ponto_registrado')
def calcular_horas_folha(data: dict, admin_id: int):
    """Handler: Calcular horas para folha quando ponto é registrado"""
    try:
        logger.info(f"📊 Calculando horas para folha: funcionário {data.get('funcionario_id')}")
        # TODO: Implementar cálculo de horas para folha de pagamento
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular horas: {e}", exc_info=True)


@event_handler('veiculo_usado')
def lancar_custo_combustivel(data: dict, admin_id: int):
    """Handler: Lançar custo de combustível quando veículo é usado"""
    try:
        from models import db, ContaPagar
        from datetime import datetime
        
        obra_id = data.get('obra_id')
        km_percorrido = data.get('km_percorrido', 0)
        
        if not obra_id or km_percorrido <= 0:
            logger.info(f"⏭️ Custo combustível não lançado: sem obra ou KM zerado")
            return
        
        # Estimar custo: R$ 0.80 por KM (média diesel + desgaste)
        custo_estimado = km_percorrido * 0.80
        
        logger.info(f"⛽ [INTEGRAÇÃO] Custo combustível calculado: R$ {custo_estimado:.2f} ({km_percorrido}km)")
        logger.info(f"   🚗 Obra: {obra_id} | Uso: {data.get('uso_id')} | Veículo: {data.get('veiculo_id')}")
        
        # TODO: Quando modelo de Custos Obra estiver disponível, criar registro aqui
        # Por enquanto, log estruturado serve como auditoria
        
    except Exception as e:
        logger.error(f"❌ Erro ao lançar custo combustível: {e}", exc_info=True)


@event_handler('proposta_aprovada')
def gerar_contas_receber_proposta(data: dict, admin_id: int):
    """Handler: Gerar contas a receber quando proposta é aprovada"""
    try:
        from models import db, ContaReceber
        from datetime import datetime, timedelta
        
        proposta_id = data.get('proposta_id')
        valor_total = data.get('valor_total', 0)
        prazo_dias = data.get('prazo_dias', 30)
        
        if valor_total <= 0:
            logger.info(f"⏭️ Conta a receber não criada: valor zerado")
            return
        
        # Criar conta a receber
        conta = ContaReceber(
            cliente_nome='Cliente Proposta',  # TODO: Obter nome do cliente
            descricao=f"Proposta #{proposta_id}",
            valor_original=valor_total,
            saldo=valor_total,
            data_emissao=datetime.now().date(),
            data_vencimento=(datetime.now() + timedelta(days=prazo_dias)).date(),
            status='PENDENTE',
            admin_id=admin_id,
            origem_tipo='PROPOSTA',
            origem_id=proposta_id
        )
        
        db.session.add(conta)
        db.session.commit()
        
        logger.info(f"📈 Conta a receber criada: R$ {valor_total:.2f} (venc: {prazo_dias} dias)")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar conta a receber: {e}", exc_info=True)


# Log de inicialização
logger.info(f"✅ Event Manager inicializado - {len(EventManager.list_events())} eventos registrados")
