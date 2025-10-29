"""
Event Manager - Sistema Central de Eventos do SIGE v9.0
Gerencia comunicação entre módulos via padrão Observer/PubSub
"""

import logging
from typing import Callable, Dict, List
from datetime import datetime
from utils import calcular_valor_hora_periodo

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
        
        # ✅ NOVO: Criar lançamento contábil (CMV - Custo de Materiais Vendidos)
        try:
            from models import LancamentoContabil, PartidaContabil
            from sqlalchemy import func
            
            # Gerar número sequencial do lançamento
            ultimo_numero = db.session.query(func.max(LancamentoContabil.numero)).filter_by(admin_id=admin_id).scalar()
            numero_lancamento = (ultimo_numero + 1) if ultimo_numero else 1
            
            # Criar lançamento principal
            lancamento = LancamentoContabil(
                admin_id=admin_id,
                numero=numero_lancamento,
                data_lancamento=movimento.data_movimentacao.date() if movimento.data_movimentacao else datetime.now().date(),
                historico=f"Saída de material para obra - {produto.nome if produto else 'Material'} (Movimento #{movimento_id})",
                origem='ALMOXARIFADO_SAIDA',
                origem_id=movimento_id,
                valor_total=Decimal(str(valor_total))
            )
            db.session.add(lancamento)
            db.session.flush()  # Gera lancamento.id
            
            # PARTIDA 1: DÉBITO - CMV (Despesa)
            partida_debito = PartidaContabil(
                admin_id=admin_id,
                lancamento_id=lancamento.id,
                conta_codigo='5.1.02.001',  # Custo de Materiais Vendidos (CMV)
                tipo_partida='DEBITO',
                valor=Decimal(str(valor_total)),
                historico_complementar=f"Consumo de material - {produto.nome if produto else 'Material'}",
                sequencia=1
            )
            db.session.add(partida_debito)
            
            # PARTIDA 2: CRÉDITO - Estoque (Ativo)
            partida_credito = PartidaContabil(
                admin_id=admin_id,
                lancamento_id=lancamento.id,
                conta_codigo='1.1.05.001',  # Estoque de Materiais
                tipo_partida='CREDITO',
                valor=Decimal(str(valor_total)),
                historico_complementar=f"Baixa de estoque - Obra: {movimento.obra.nome if movimento and movimento.obra else 'N/A'}",
                sequencia=2
            )
            db.session.add(partida_credito)
            
            db.session.commit()
            logger.info(f"✅ Lançamento contábil CMV criado: ID {lancamento.id} (#{numero_lancamento}) - D: 5.1.02.001 / C: 1.1.05.001 - R$ {valor_total}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar lançamento contábil saída: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
    except ValueError as e:
        logger.error(f"❌ Erro de validação ao lançar custo de material: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"❌ Erro ao lançar custo de material: {e}", exc_info=True)
        db.session.rollback()


@event_handler('material_entrada')
def criar_conta_pagar_entrada_material(data: dict, admin_id: int):
    """
    Handler: Criar conta a pagar quando material entra no estoque com fornecedor
    
    Fluxo:
    1. Buscar movimento de almoxarifado
    2. Verificar se tem fornecedor_id
    3. Calcular valor_total (quantidade * valor_unitario)
    4. Verificar se NF já tem conta criada (evitar duplicação)
    5. Criar ContaPagar automaticamente
    
    Args:
        data: {movimento_id: int, item_id: int, fornecedor_id: int}
        admin_id: ID do tenant
    """
    try:
        from models import db, AlmoxarifadoMovimento, ContaPagar, Fornecedor, AlmoxarifadoItem
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        movimento_id = data.get('movimento_id')
        
        if not movimento_id:
            logger.warning(f"⚠️ movimento_id não fornecido no evento material_entrada")
            return
        
        # Buscar movimento com validação multi-tenant
        movimento = AlmoxarifadoMovimento.query.filter_by(
            id=movimento_id,
            admin_id=admin_id,
            tipo_movimento='ENTRADA'
        ).first()
        
        if not movimento:
            logger.error(f"❌ Movimento {movimento_id} não encontrado ou tipo incorreto")
            return
        
        # CRÍTICO: Validar se tem fornecedor
        if not movimento.fornecedor_id:
            logger.info(f"⏭️ Movimento {movimento_id}: sem fornecedor, conta a pagar não criada")
            return
        
        # Calcular valor total
        quantidade = float(movimento.quantidade or 0)
        valor_unitario = float(movimento.valor_unitario or 0)
        valor_total = Decimal(str(quantidade * valor_unitario))
        
        if valor_total <= 0:
            logger.warning(f"⚠️ Movimento {movimento_id}: valor zerado, conta não criada")
            return
        
        # EVITAR DUPLICAÇÃO: Verificar se NF já tem conta
        if movimento.nota_fiscal:
            conta_existente = ContaPagar.query.filter_by(
                admin_id=admin_id,
                fornecedor_id=movimento.fornecedor_id,
                numero_documento=movimento.nota_fiscal
            ).first()
            
            if conta_existente:
                logger.info(f"⏭️ Conta a pagar já existe para NF {movimento.nota_fiscal} (ID: {conta_existente.id})")
                return
        
        # ✅ Buscar fornecedor com validação multi-tenant
        fornecedor = Fornecedor.query.filter_by(
            id=movimento.fornecedor_id,
            admin_id=admin_id
        ).first()
        
        if not fornecedor:
            logger.error(f"❌ Fornecedor {movimento.fornecedor_id} não encontrado ou não pertence ao tenant {admin_id}")
            return
        
        item = AlmoxarifadoItem.query.get(movimento.item_id)
        
        # Criar conta a pagar
        conta = ContaPagar(
            admin_id=admin_id,
            fornecedor_id=movimento.fornecedor_id,
            numero_documento=movimento.nota_fiscal or f"MOV-{movimento_id}",
            descricao=f"Compra de materiais - {item.nome if item else 'Material'} (Movimento #{movimento_id})",
            valor_original=valor_total,
            valor_pago=Decimal('0'),
            saldo=valor_total,
            data_emissao=movimento.data_movimento.date() if movimento.data_movimento else datetime.now().date(),
            data_vencimento=(movimento.data_movimento + timedelta(days=30)).date() if movimento.data_movimento else (datetime.now() + timedelta(days=30)).date(),
            status='PENDENTE',
            conta_contabil_codigo='2.1.01.001'
        )
        
        db.session.add(conta)
        db.session.commit()
        
        logger.info(f"✅ Conta a pagar criada: ID {conta.id} - R$ {valor_total} - Fornecedor: {fornecedor.razao_social if fornecedor else movimento.fornecedor_id}")
        
        # ✅ NOVO: Criar lançamento contábil (partidas dobradas)
        try:
            from models import LancamentoContabil, PartidaContabil
            from sqlalchemy import func
            
            # Gerar número sequencial do lançamento
            ultimo_numero = db.session.query(func.max(LancamentoContabil.numero)).filter_by(admin_id=admin_id).scalar()
            numero_lancamento = (ultimo_numero + 1) if ultimo_numero else 1
            
            # Criar lançamento principal
            lancamento = LancamentoContabil(
                admin_id=admin_id,
                numero=numero_lancamento,
                data_lancamento=movimento.data_movimento.date() if movimento.data_movimento else datetime.now().date(),
                historico=f"Entrada de material - {item.nome if item else 'Material'} (Movimento #{movimento_id})",
                origem='ALMOXARIFADO_ENTRADA',
                origem_id=movimento_id,
                valor_total=valor_total
            )
            db.session.add(lancamento)
            db.session.flush()  # Gera lancamento.id
            
            # PARTIDA 1: DÉBITO - Estoque de Materiais (Ativo)
            partida_debito = PartidaContabil(
                admin_id=admin_id,
                lancamento_id=lancamento.id,
                conta_codigo='1.1.05.001',  # Estoque de Materiais
                tipo_partida='DEBITO',
                valor=valor_total,
                historico_complementar=f"Entrada de material - {item.nome if item else 'Material'}",
                sequencia=1
            )
            db.session.add(partida_debito)
            
            # PARTIDA 2: CRÉDITO - Fornecedores a Pagar (Passivo)
            partida_credito = PartidaContabil(
                admin_id=admin_id,
                lancamento_id=lancamento.id,
                conta_codigo='2.1.01.001',  # Fornecedores a Pagar
                tipo_partida='CREDITO',
                valor=valor_total,
                historico_complementar=f"Compra de material - Fornecedor: {fornecedor.razao_social if fornecedor else movimento.fornecedor_id}",
                sequencia=2
            )
            db.session.add(partida_credito)
            
            db.session.commit()
            logger.info(f"✅ Lançamento contábil criado: ID {lancamento.id} (#{numero_lancamento}) - D: 1.1.05.001 / C: 2.1.01.001 - R$ {valor_total}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar lançamento contábil entrada: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar conta a pagar para movimento {data.get('movimento_id')}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


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
        
        # Calcular valor/hora baseado no período do registro
        data_inicio = registro.data
        data_fim = registro.data
        salario_hora = calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
        
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


@event_handler('rdo_finalizado')
def lancar_custos_rdo(data: dict, admin_id: int):
    """Handler: Lançar custos de mão de obra quando RDO é finalizado"""
    try:
        from models import db, RDO, RDOMaoObra, Funcionario, CustoObra
        from decimal import Decimal
        
        rdo_id = data.get('rdo_id')
        
        if not rdo_id:
            logger.warning(f"⚠️ rdo_id não fornecido no evento rdo_finalizado")
            return
        
        # Buscar RDO com validação multi-tenant
        rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
        
        if not rdo:
            logger.error(f"❌ RDO {rdo_id} não encontrado para admin {admin_id}")
            return
        
        # Validar se tem obra vinculada
        if not rdo.obra_id:
            logger.info(f"⏭️ Custos não lançados: RDO {rdo_id} sem obra vinculada")
            return
        
        # Buscar todos os registros de mão de obra do RDO
        mao_obra_registros = RDOMaoObra.query.filter_by(rdo_id=rdo_id).all()
        
        if not mao_obra_registros:
            logger.info(f"⏭️ Nenhuma mão de obra registrada no RDO {rdo_id}")
            return
        
        custos_criados = 0
        valor_total_custos = 0
        
        for mao_obra in mao_obra_registros:
            # Buscar funcionário para obter salário
            funcionario = Funcionario.query.get(mao_obra.funcionario_id)
            
            if not funcionario:
                logger.warning(f"⚠️ Funcionário {mao_obra.funcionario_id} não encontrado")
                continue
            
            # Calcular valor/hora do funcionário no período
            data_rdo = rdo.data_relatorio
            salario_hora = calcular_valor_hora_periodo(funcionario, data_rdo, data_rdo)
            
            if salario_hora <= 0:
                logger.warning(f"⚠️ Funcionário {funcionario.nome} sem salário configurado")
                salario_hora = 0
            
            # Calcular valores
            horas_trabalhadas = float(mao_obra.horas_trabalhadas or 0)
            horas_extras = float(mao_obra.horas_extras or 0)
            
            if horas_trabalhadas <= 0:
                logger.info(f"⏭️ Mão de obra sem horas trabalhadas - funcionário {funcionario.nome}")
                continue
            
            # Calcular custo total
            valor_horas_normais = horas_trabalhadas * salario_hora
            valor_horas_extras = horas_extras * salario_hora * 1.5
            valor_total = valor_horas_normais + valor_horas_extras
            
            # Criar descrição detalhada
            descricao = f"RDO #{rdo.numero_rdo} - {funcionario.nome}"
            if mao_obra.funcao_exercida:
                descricao += f" ({mao_obra.funcao_exercida})"
            descricao += f" - {data_rdo.strftime('%d/%m/%Y')}"
            
            if horas_extras > 0:
                descricao += f" ({horas_trabalhadas}h normais + {horas_extras}h extras)"
            else:
                descricao += f" ({horas_trabalhadas}h)"
            
            # Criar registro de custo
            custo = CustoObra(
                obra_id=rdo.obra_id,
                tipo='mao_obra',
                descricao=descricao,
                valor=valor_total,
                data=data_rdo,
                funcionario_id=mao_obra.funcionario_id,
                rdo_id=rdo.id,
                admin_id=admin_id,
                horas_trabalhadas=Decimal(str(horas_trabalhadas)),
                horas_extras=Decimal(str(horas_extras)),
                valor_unitario=Decimal(str(salario_hora)),
                quantidade=Decimal(str(horas_trabalhadas + horas_extras)),
                categoria='RDO'
            )
            
            db.session.add(custo)
            custos_criados += 1
            valor_total_custos += valor_total
        
        # Commit de todos os custos de uma vez
        db.session.commit()
        
        logger.info(f"✅ RDO {rdo.numero_rdo} finalizado: {custos_criados} custos de mão de obra lançados (Total: R$ {valor_total_custos:.2f})")
        
    except Exception as e:
        logger.error(f"❌ Erro ao lançar custos do RDO: {e}", exc_info=True)
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


# ================================
# HANDLER: FOLHA DE PAGAMENTO PROCESSADA
# ================================

@event_handler('folha_processada')
def criar_lancamento_folha_pagamento(data: dict, admin_id: int):
    """
    Cria lançamento contábil automaticamente quando a folha é processada.
    
    Lançamento:
    D - 5.1.01.001 - Despesas com Pessoal (Total Proventos)
    C - 2.1.03.001 - Salários a Pagar (Salário Líquido)
    C - 2.1.03.002 - INSS a Recolher (INSS Descontado)
    C - 2.1.03.003 - IRRF a Recolher (IRRF Descontado)
    C - 2.1.03.004 - FGTS a Recolher (FGTS)
    """
    try:
        from models import (db, FolhaPagamento, LancamentoContabil, PartidaContabil, 
                           PlanoContas, Funcionario)
        from datetime import datetime
        
        folha_id = data.get('folha_id')
        if not folha_id:
            logger.warning("⚠️ folha_id não fornecido no evento folha_processada")
            return
        
        logger.info(f"📊 Criando lançamento contábil para folha {folha_id}")
        
        # SEGURANÇA: Buscar folha com filtro de admin_id
        folha = FolhaPagamento.query.filter_by(id=folha_id, admin_id=admin_id).first()
        if not folha:
            logger.error(f"❌ Folha {folha_id} não encontrada ou sem permissão para admin {admin_id}")
            return
        
        # SEGURANÇA: Buscar funcionário com filtro de admin_id
        funcionario = Funcionario.query.filter_by(id=folha.funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            logger.error(f"❌ Funcionário {folha.funcionario_id} não encontrado ou sem permissão para admin {admin_id}")
            return
        
        # Buscar contas do plano de contas
        conta_despesa_pessoal = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='5.1.01.001',
            ativo=True
        ).first()
        
        conta_salarios_pagar = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.03.001',
            ativo=True
        ).first()
        
        conta_inss_recolher = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.03.002',
            ativo=True
        ).first()
        
        conta_irrf_recolher = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.03.003',
            ativo=True
        ).first()
        
        conta_fgts_recolher = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.03.004',
            ativo=True
        ).first()
        
        # Validar se contas essenciais existem
        if not conta_despesa_pessoal or not conta_salarios_pagar:
            logger.warning(f"⚠️ Plano de contas incompleto para admin {admin_id}. Lançamento não criado.")
            logger.warning(f"   Despesa Pessoal: {'OK' if conta_despesa_pessoal else 'FALTA'}")
            logger.warning(f"   Salários a Pagar: {'OK' if conta_salarios_pagar else 'FALTA'}")
            return
        
        # Verificar se já existe lançamento para esta folha
        lancamento_existente = LancamentoContabil.query.filter_by(
            admin_id=admin_id,
            origem='FOLHA_PAGAMENTO',
            origem_id=folha_id
        ).first()
        
        if lancamento_existente:
            logger.info(f"ℹ️ Lançamento já existe para folha {folha_id} (ID {lancamento_existente.id})")
            return
        
        # Gerar número sequencial do lançamento
        from sqlalchemy import func
        ultimo_numero = db.session.query(func.max(LancamentoContabil.numero)).filter_by(admin_id=admin_id).scalar()
        proximo_numero = (ultimo_numero or 0) + 1
        
        # Criar cabeçalho do lançamento
        # IMPORTANTE: valor_total = proventos + FGTS (encargo patronal)
        mes_ref = folha.mes_referencia.strftime('%B/%Y')
        valor_total_debito = (folha.total_proventos or 0) + (folha.fgts or 0)
        
        lancamento = LancamentoContabil(
            admin_id=admin_id,
            numero=proximo_numero,
            data_lancamento=folha.mes_referencia,
            historico=f"Folha de Pagamento - {funcionario.nome} - {mes_ref}",
            valor_total=valor_total_debito,  # Total = salário bruto + FGTS patronal
            origem='FOLHA_PAGAMENTO',
            origem_id=folha_id
        )
        db.session.add(lancamento)
        db.session.flush()  # Gerar ID do lançamento
        
        # Criar partidas com sequência
        sequencia = 1
        
        # DÉBITO: Despesas com Pessoal (Total Proventos + FGTS Patronal)
        valor_debito = (folha.total_proventos or 0) + (folha.fgts or 0)
        partida_debito = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=sequencia,
            conta_codigo=conta_despesa_pessoal.codigo,
            tipo_partida='DEBITO',
            valor=valor_debito,  # Salário bruto + FGTS (8%)
            historico_complementar=f"Despesas com pessoal + FGTS - {funcionario.nome}",
            admin_id=admin_id
        )
        db.session.add(partida_debito)
        sequencia += 1
        
        # CRÉDITO: Salários a Pagar (Salário Líquido)
        partida_credito_salario = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=sequencia,
            conta_codigo=conta_salarios_pagar.codigo,
            tipo_partida='CREDITO',
            valor=folha.salario_liquido or 0,
            historico_complementar=f"Salário líquido a pagar - {funcionario.nome}",
            admin_id=admin_id
        )
        db.session.add(partida_credito_salario)
        sequencia += 1
        
        # CRÉDITO: INSS a Recolher (se houver)
        if (folha.inss or 0) > 0 and conta_inss_recolher:
            partida_credito_inss = PartidaContabil(
                lancamento_id=lancamento.id,
                sequencia=sequencia,
                conta_codigo=conta_inss_recolher.codigo,
                tipo_partida='CREDITO',
                valor=folha.inss,
                historico_complementar=f"INSS descontado - {funcionario.nome}",
                admin_id=admin_id
            )
            db.session.add(partida_credito_inss)
            sequencia += 1
        
        # CRÉDITO: IRRF a Recolher (se houver)
        if (folha.irrf or 0) > 0 and conta_irrf_recolher:
            partida_credito_irrf = PartidaContabil(
                lancamento_id=lancamento.id,
                sequencia=sequencia,
                conta_codigo=conta_irrf_recolher.codigo,
                tipo_partida='CREDITO',
                valor=folha.irrf,
                historico_complementar=f"IRRF descontado - {funcionario.nome}",
                admin_id=admin_id
            )
            db.session.add(partida_credito_irrf)
            sequencia += 1
        
        # CRÉDITO: FGTS a Recolher (se houver)
        if (folha.fgts or 0) > 0 and conta_fgts_recolher:
            partida_credito_fgts = PartidaContabil(
                lancamento_id=lancamento.id,
                sequencia=sequencia,
                conta_codigo=conta_fgts_recolher.codigo,
                tipo_partida='CREDITO',
                valor=folha.fgts,
                historico_complementar=f"FGTS - {funcionario.nome}",
                admin_id=admin_id
            )
            db.session.add(partida_credito_fgts)
            sequencia += 1
        
        # Commit
        db.session.commit()
        
        logger.info(f"✅ Lançamento contábil {lancamento.id} criado com {sequencia-1} partidas")
        logger.info(f"   Folha: {folha_id} | Funcionário: {funcionario.nome}")
        logger.info(f"   Total: R$ {folha.total_proventos:,.2f}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar lançamento contábil para folha {data.get('folha_id')}: {e}")
        import traceback
        logger.error(traceback.format_exc())


@event_handler('alimentacao_lancamento_criado')
def criar_conta_pagar_alimentacao(data: dict, admin_id: int):
    """Handler: Criar conta a pagar quando lançamento de alimentação for criado"""
    try:
        from models import db, AlimentacaoLancamento, Restaurante, Fornecedor, ContaPagar
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        lancamento_id = data.get('lancamento_id')
        
        if not lancamento_id:
            logger.warning(f"⚠️ lancamento_id não fornecido no evento alimentacao_lancamento_criado")
            return
        
        # Buscar lançamento de alimentação
        lancamento = AlimentacaoLancamento.query.filter_by(
            id=lancamento_id,
            admin_id=admin_id
        ).first()
        
        if not lancamento:
            logger.error(f"❌ Lançamento {lancamento_id} não encontrado para admin {admin_id}")
            return
        
        # Buscar restaurante
        restaurante = Restaurante.query.filter_by(
            id=lancamento.restaurante_id,
            admin_id=admin_id
        ).first()
        
        if not restaurante:
            logger.error(f"❌ Restaurante {lancamento.restaurante_id} não encontrado para admin {admin_id}")
            return
        
        # Verificar se já existe fornecedor para este restaurante (via CNPJ)
        fornecedor = None
        if restaurante.cnpj:
            fornecedor = Fornecedor.query.filter_by(
                cnpj=restaurante.cnpj,
                admin_id=admin_id
            ).first()
        
        # Se não existir, criar fornecedor automaticamente
        if not fornecedor:
            fornecedor = Fornecedor(
                razao_social=restaurante.razao_social or restaurante.nome,
                nome_fantasia=restaurante.nome,
                cnpj=restaurante.cnpj or f"SEM_CNPJ_{restaurante.id}",
                endereco=restaurante.endereco or '',
                telefone=restaurante.telefone or '',
                tipo='SERVICO',
                admin_id=admin_id
            )
            db.session.add(fornecedor)
            db.session.flush()  # Gera fornecedor.id
            logger.info(f"✅ Fornecedor {fornecedor.id} criado automaticamente para restaurante {restaurante.nome}")
        
        # Criar conta a pagar
        data_vencimento = lancamento.data + timedelta(days=7)  # Vence em 7 dias
        
        conta = ContaPagar(
            fornecedor_id=fornecedor.id,
            obra_id=lancamento.obra_id,
            numero_documento=f"ALIM-{lancamento_id}",
            descricao=f"Alimentação - {restaurante.nome} - {lancamento.data.strftime('%d/%m/%Y')}",
            valor_original=Decimal(str(lancamento.valor_total)),
            valor_pago=Decimal('0'),
            saldo=Decimal(str(lancamento.valor_total)),
            data_emissao=lancamento.data,
            data_vencimento=data_vencimento,
            status='PENDENTE',
            origem_tipo='ALIMENTACAO',
            origem_id=lancamento_id,
            admin_id=admin_id
        )
        
        db.session.add(conta)
        db.session.commit()
        
        logger.info(f"✅ Conta a pagar criada: R$ {lancamento.valor_total:.2f} para {restaurante.nome}")
        logger.info(f"   Lançamento: {lancamento_id} | Fornecedor: {fornecedor.id} | Vencimento: {data_vencimento}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar conta a pagar para lançamento {data.get('lancamento_id')}: {e}")
        import traceback
        logger.error(traceback.format_exc())


# Log de inicialização
logger.info(f"✅ Event Manager inicializado - {len(EventManager.list_events())} eventos registrados")
