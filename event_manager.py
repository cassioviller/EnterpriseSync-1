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
        from models import db, MovimentacaoEstoque, CustoObra, Produto
        from datetime import datetime
        from decimal import Decimal
        
        movimento_id = data.get('movimento_id')
        
        if not movimento_id:
            logger.warning(f"⚠️ movimento_id não fornecido no evento material_saida")
            return
        
        # Buscar movimento do almoxarifado
        movimento = MovimentacaoEstoque.query.filter_by(
            id=movimento_id,
            admin_id=admin_id
        ).first()
        
        if not movimento:
            logger.error(f"❌ Movimento {movimento_id} não encontrado para admin {admin_id}")
            return
        
        # Validar se tem obra vinculada
        if not movimento.obra_id:
            logger.info(f"⏭️ Custo não lançado: movimento {movimento_id} sem obra vinculada")
            return
        
        # Calcular valores
        quantidade = float(movimento.quantidade or 0)
        valor_unitario = float(movimento.valor_unitario or 0)
        valor_total = quantidade * valor_unitario
        
        if valor_total <= 0:
            logger.info(f"⏭️ Custo não lançado: valor zerado (qtd={quantidade}, unit={valor_unitario})")
            return
        
        # Buscar nome do produto para descrição
        produto = Produto.query.get(movimento.produto_id)
        descricao = f"Material: {produto.nome if produto else 'Item'} - Movimento #{movimento_id}"
        
        # Criar registro de custo na obra
        custo = CustoObra(
            obra_id=movimento.obra_id,
            tipo='material',
            descricao=descricao,
            valor=valor_total,
            data=movimento.data_movimentacao.date() if movimento.data_movimentacao else datetime.now().date(),
            item_almoxarifado_id=movimento.produto_id,
            admin_id=admin_id,
            quantidade=Decimal(str(quantidade)),
            valor_unitario=Decimal(str(valor_unitario)),
            categoria='ALMOXARIFADO'
        )
        
        db.session.add(custo)
        db.session.commit()
        
        logger.info(f"✅ Custo de material lançado: R$ {valor_total:.2f} na obra {movimento.obra_id}")
        logger.info(f"   📦 Produto: {produto.nome if produto else movimento.produto_id} | Qtd: {quantidade} | Movimento: {movimento_id}")
        
    except ValueError as e:
        logger.error(f"❌ Erro de validação ao lançar custo de material: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"❌ Erro ao lançar custo de material: {e}", exc_info=True)
        db.session.rollback()


@event_handler('ponto_registrado')
def calcular_horas_folha(data: dict, admin_id: int):
    """Handler: Calcular horas para folha quando ponto é registrado"""
    try:
        from models import db, RegistroPonto, CustoObra, Funcionario
        from datetime import datetime
        from decimal import Decimal
        
        registro_id = data.get('registro_id')
        
        if not registro_id:
            logger.warning(f"⚠️ registro_id não fornecido no evento ponto_registrado")
            return
        
        # Buscar registro de ponto
        registro = RegistroPonto.query.filter_by(
            id=registro_id,
            admin_id=admin_id
        ).first()
        
        if not registro:
            logger.error(f"❌ Registro de ponto {registro_id} não encontrado para admin {admin_id}")
            return
        
        # Validar se tem obra vinculada
        if not registro.obra_id:
            logger.info(f"⏭️ Custo não lançado: registro {registro_id} sem obra vinculada")
            return
        
        # Validar horas trabalhadas
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        horas_extras = float(registro.horas_extras or 0)
        
        if horas_trabalhadas <= 0:
            logger.info(f"⏭️ Custo não lançado: sem horas trabalhadas no registro {registro_id}")
            return
        
        # Buscar funcionário para obter salário
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        if not funcionario:
            logger.error(f"❌ Funcionário {registro.funcionario_id} não encontrado")
            return
        
        # Calcular salário por hora (assumindo 220h/mês)
        salario_mensal = float(funcionario.salario or 0)
        salario_hora = salario_mensal / 220 if salario_mensal > 0 else 0
        
        if salario_hora <= 0:
            logger.warning(f"⚠️ Funcionário {funcionario.nome} sem salário configurado")
            salario_hora = 0
        
        # Calcular valor do custo
        # Horas normais + horas extras (50% adicional)
        valor_horas_normais = horas_trabalhadas * salario_hora
        valor_horas_extras = horas_extras * salario_hora * 1.5
        valor_total = valor_horas_normais + valor_horas_extras
        
        # Criar descrição detalhada
        descricao = f"Mão de obra: {funcionario.nome} - {registro.data.strftime('%d/%m/%Y')}"
        if horas_extras > 0:
            descricao += f" ({horas_trabalhadas}h normais + {horas_extras}h extras)"
        else:
            descricao += f" ({horas_trabalhadas}h trabalhadas)"
        
        # Criar registro de custo na obra
        custo = CustoObra(
            obra_id=registro.obra_id,
            tipo='mao_obra',
            descricao=descricao,
            valor=valor_total,
            data=registro.data,
            funcionario_id=registro.funcionario_id,
            admin_id=admin_id,
            horas_trabalhadas=Decimal(str(horas_trabalhadas)),
            horas_extras=Decimal(str(horas_extras)),
            valor_unitario=Decimal(str(salario_hora)),
            quantidade=Decimal(str(horas_trabalhadas + horas_extras)),
            categoria='PONTO_ELETRONICO'
        )
        
        db.session.add(custo)
        db.session.commit()
        
        logger.info(f"✅ Custo de mão de obra lançado: R$ {valor_total:.2f} na obra {registro.obra_id}")
        logger.info(f"   👷 Funcionário: {funcionario.nome} | Horas: {horas_trabalhadas}h + {horas_extras}h extras | Registro: {registro_id}")
        
    except ValueError as e:
        logger.error(f"❌ Erro de validação ao calcular horas: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"❌ Erro ao calcular horas: {e}", exc_info=True)
        db.session.rollback()


@event_handler('veiculo_usado')
def lancar_custo_combustivel(data: dict, admin_id: int):
    """Handler: Lançar custo de combustível quando veículo é usado"""
    try:
        from models import db, UsoVeiculo, CustoObra, Veiculo
        from datetime import datetime
        from decimal import Decimal
        
        uso_id = data.get('uso_id')
        
        if not uso_id:
            logger.warning(f"⚠️ uso_id não fornecido no evento veiculo_usado")
            return
        
        # Buscar registro de uso de veículo (com filtro multi-tenant)
        uso = UsoVeiculo.query.filter_by(id=uso_id, admin_id=admin_id).first()
        
        if not uso:
            logger.error(f"❌ Uso de veículo {uso_id} não encontrado")
            return
        
        # Validar se tem obra vinculada
        if not uso.obra_id:
            logger.info(f"⏭️ Custo não lançado: uso {uso_id} sem obra vinculada")
            return
        
        # Validar km percorrido
        km_percorrido = int(uso.km_percorrido or 0)
        
        if km_percorrido <= 0:
            logger.info(f"⏭️ Custo não lançado: sem KM percorrido no uso {uso_id}")
            return
        
        # Calcular custo: R$ 0.80 por KM (diesel + desgaste)
        valor_unitario = 0.80
        custo_total = km_percorrido * valor_unitario
        
        # Buscar veículo para descrição
        veiculo = Veiculo.query.get(uso.veiculo_id) if uso.veiculo_id else None
        veiculo_nome = veiculo.modelo if veiculo else f"Veículo ID {uso.veiculo_id}"
        
        # Criar descrição detalhada
        data_uso = uso.data_uso.strftime('%d/%m/%Y') if uso.data_uso else 'Data não informada'
        descricao = f"Combustível/Desgaste: {veiculo_nome} - {data_uso} ({km_percorrido} km)"
        
        # Criar registro de custo na obra
        custo = CustoObra(
            obra_id=uso.obra_id,
            tipo='veiculo',
            descricao=descricao,
            valor=custo_total,
            data=uso.data_uso if uso.data_uso else datetime.now().date(),
            veiculo_id=uso.veiculo_id,
            admin_id=admin_id,
            quantidade=Decimal(str(km_percorrido)),
            valor_unitario=Decimal(str(valor_unitario)),
            categoria='FROTA'
        )
        
        db.session.add(custo)
        db.session.commit()
        
        logger.info(f"✅ Custo de combustível lançado: R$ {custo_total:.2f} na obra {uso.obra_id}")
        logger.info(f"   🚗 Veículo: {veiculo_nome} | KM: {km_percorrido} | Uso: {uso_id}")
        
    except ValueError as e:
        logger.error(f"❌ Erro de validação ao lançar custo combustível: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"❌ Erro ao lançar custo combustível: {e}", exc_info=True)
        db.session.rollback()


@event_handler('proposta_aprovada')
def gerar_contas_receber_proposta(data: dict, admin_id: int):
    """Handler: Gerar contas a receber quando proposta é aprovada"""
    try:
        from models import db, Proposta, ContaReceber, Obra
        from datetime import datetime, timedelta
        from decimal import Decimal
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError
        
        proposta_id = data.get('proposta_id')
        
        if not proposta_id:
            logger.warning(f"⚠️ proposta_id não fornecido no evento proposta_aprovada")
            return
        
        # Buscar proposta
        proposta = Proposta.query.filter_by(
            id=proposta_id,
            admin_id=admin_id
        ).first()
        
        if not proposta:
            logger.error(f"❌ Proposta {proposta_id} não encontrada para admin {admin_id}")
            return
        
        # Validar valor total
        valor_total = float(proposta.valor_total or 0)
        
        if valor_total <= 0:
            logger.info(f"⏭️ Conta a receber não criada: proposta {proposta_id} com valor zerado")
            return
        
        # Obter cliente_nome real da proposta
        cliente_nome = proposta.cliente_nome or 'Cliente não identificado'
        
        # Verificar se já existe obra vinculada à proposta
        obra = Obra.query.filter_by(
            proposta_origem_id=proposta_id,
            admin_id=admin_id
        ).first()
        
        # Se não existe, criar obra para a proposta
        if not obra:
            # Gerar código único para a obra
            ultimo_codigo = db.session.query(func.max(Obra.codigo)).filter_by(admin_id=admin_id).scalar()
            if ultimo_codigo and ultimo_codigo.startswith('OBR'):
                numero = int(ultimo_codigo[3:]) + 1
            else:
                numero = 1
            
            codigo_obra = f"OBR{numero:04d}"
            
            obra = Obra(
                nome=f"Obra - {proposta.titulo or proposta.numero}",
                codigo=codigo_obra,
                cliente=cliente_nome,
                cliente_nome=cliente_nome,
                cliente_email=proposta.cliente_email,
                cliente_telefone=proposta.cliente_telefone,
                endereco=proposta.cliente_endereco,
                data_inicio=datetime.now().date(),
                valor_contrato=valor_total,
                orcamento=valor_total,
                status='Em andamento',
                proposta_origem_id=proposta_id,
                admin_id=admin_id,
                ativo=True
            )
            
            db.session.add(obra)
            db.session.flush()  # CRITICAL: Gerar obra.id antes de criar ContaReceber
            logger.info(f"📋 Obra {codigo_obra} criada para proposta {proposta.numero}")
        
        # Criar conta a receber
        # Nota: Se houver necessidade de dividir em parcelas, isso pode ser implementado
        # parseando o campo condicoes_pagamento da proposta
        
        conta = ContaReceber(
            cliente_nome=cliente_nome,
            cliente_cpf_cnpj=None,  # Pode ser adicionado se disponível
            obra_id=obra.id,
            numero_documento=proposta.numero,
            descricao=f"Recebimento - Proposta {proposta.numero} - {proposta.titulo or 'Serviços'}",
            valor_original=Decimal(str(valor_total)),
            valor_recebido=Decimal('0'),
            saldo=Decimal(str(valor_total)),
            data_emissao=datetime.now().date(),
            data_vencimento=(datetime.now() + timedelta(days=proposta.prazo_entrega_dias or 30)).date(),
            status='PENDENTE',
            origem_tipo='PROPOSTA',
            origem_id=proposta_id,
            admin_id=admin_id
        )
        
        db.session.add(conta)
        
        # Atualizar status da proposta para APROVADA
        proposta.status = 'APROVADA'
        
        db.session.commit()
        
        logger.info(f"✅ Conta a receber criada: R$ {valor_total:.2f} - {cliente_nome}")
        logger.info(f"   📄 Proposta: {proposta.numero} | Obra: {obra.codigo} | Status: APROVADA")
        
    except IntegrityError as e:
        logger.error(f"❌ Erro de integridade ao criar conta a receber: {e}")
        db.session.rollback()
    except ValueError as e:
        logger.error(f"❌ Erro de validação ao criar conta a receber: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"❌ Erro ao criar conta a receber: {e}", exc_info=True)
        db.session.rollback()


# Log de inicialização
logger.info(f"✅ Event Manager inicializado - {len(EventManager.list_events())} eventos registrados")
