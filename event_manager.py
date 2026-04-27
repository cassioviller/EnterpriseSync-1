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
    def emit(cls, event_name: str, data: dict, admin_id: int, raise_on_error: bool = False):
        """Emitir evento para todos os handlers registrados.

        Task #102: parâmetro `raise_on_error=True` propaga a primeira exceção
        de handler para o caller (modo atômico). Default mantém comportamento
        legado (engole exceções e retorna sucesso parcial).
        """
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
                    if raise_on_error:
                        raise
            
            logger.info(f"📊 Evento {event_name}: {success_count}/{len(handlers)} handlers OK")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erro ao emitir evento {event_name}: {e}", exc_info=True)
            if raise_on_error:
                raise
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
    """
    Handler: Registro de saída de material do estoque (controle físico apenas).

    REENGENHARIA SUPRIMENTOS — princípio central:
    O custo de material é reconhecido UMA ÚNICA VEZ, na compra (GestaoCustoPai MATERIAL
    criado em nova_post). A SAÍDA é exclusivamente controle físico de estoque —
    nenhum lançamento financeiro ou contábil adicional é criado aqui.

    Rastreabilidade de atribuição por obra (T5 — TRANSFERENCIA) deve ser implementada
    em um fluxo explícito de transferência central→obra, com evento e handler próprios,
    para não conflatar consumo genérico com transferência intencional.
    """
    try:
        from models import db, AlmoxarifadoMovimento, AlmoxarifadoItem
        from datetime import datetime

        movimento_id = data.get('movimento_id')
        if not movimento_id:
            logger.warning("⚠️ movimento_id não fornecido no evento material_saida")
            return

        movimento = AlmoxarifadoMovimento.query.filter_by(
            id=movimento_id,
            admin_id=admin_id,
            tipo_movimento='SAIDA',
        ).first()
        if not movimento:
            logger.info(f"⏭️ [SAIDA] AlmoxarifadoMovimento #{movimento_id} não encontrado")
            return

        item = AlmoxarifadoItem.query.get(movimento.item_id)
        item_nome = item.nome if item else f'Item #{movimento.item_id}'
        quantidade = float(movimento.quantidade or 0)
        obra_info = f"→ obra {movimento.obra_id}" if movimento.obra_id else "(sem obra)"
        logger.info(f"✅ [SAIDA] {item_nome} x{quantidade} {obra_info} — controle físico registrado (sem lançamento financeiro)")

    except Exception as e:
        logger.error(f"❌ Erro no handler material_saida: {e}", exc_info=True)


@event_handler('material_entrada')
def criar_conta_pagar_entrada_material(data: dict, admin_id: int):
    """
    Handler: Registrar GestaoCustoPai quando material entra no estoque com fornecedor.
    ContaPagar foi descontinuado; este handler agora usa GestaoCustoPai como fonte única.

    Args:
        data: {movimento_id: int, item_id: int, fornecedor_id: int}
        admin_id: ID do tenant
    """
    try:
        from models import (db, AlmoxarifadoMovimento, Fornecedor, AlmoxarifadoItem,
                            GestaoCustoPai, GestaoCustoFilho)
        from datetime import datetime, timedelta
        from decimal import Decimal

        movimento_id = data.get('movimento_id')

        if not movimento_id:
            logger.warning("⚠️ movimento_id não fornecido no evento material_entrada")
            return

        movimento = AlmoxarifadoMovimento.query.filter_by(
            id=movimento_id,
            admin_id=admin_id,
            tipo_movimento='ENTRADA'
        ).first()

        if not movimento:
            logger.error(f"❌ Movimento {movimento_id} não encontrado ou tipo incorreto")
            return

        # REENGENHARIA SUPRIMENTOS (T4): Se a entrada veio de um PedidoCompra,
        # o GestaoCustoPai já foi criado pelo módulo de Compras. Não duplicar.
        if movimento.pedido_compra_id:
            logger.info(f"⏭️ Movimento {movimento_id}: vinculado a PedidoCompra #{movimento.pedido_compra_id} "
                        f"— GestaoCusto já registrado na compra, ignorando entrada")
            return

        if not movimento.fornecedor_id:
            logger.info(f"⏭️ Movimento {movimento_id}: sem fornecedor, GestaoCusto não criado")
            return

        quantidade = float(movimento.quantidade or 0)
        valor_unitario = float(movimento.valor_unitario or 0)
        valor_total = Decimal(str(quantidade * valor_unitario))

        if valor_total <= 0:
            logger.warning(f"⚠️ Movimento {movimento_id}: valor zerado, GestaoCusto não criado")
            return

        # Evitar duplicação: verificar se já existe GestaoCustoPai para este movimento
        existente = GestaoCustoFilho.query.filter_by(
            origem_tabela='almoxarifado_movimento',
            origem_id=movimento_id,
            admin_id=admin_id,
        ).first()
        if existente:
            logger.info(f"⏭️ GestaoCusto já existe para movimento {movimento_id}")
            return

        fornecedor = Fornecedor.query.filter_by(
            id=movimento.fornecedor_id,
            admin_id=admin_id
        ).first()
        if not fornecedor:
            logger.error(f"❌ Fornecedor {movimento.fornecedor_id} não encontrado para admin {admin_id}")
            return

        item = AlmoxarifadoItem.query.get(movimento.item_id)
        item_nome = item.nome if item else 'Material'
        data_mov = movimento.data_movimento.date() if movimento.data_movimento else datetime.now().date()
        data_venc = data_mov + timedelta(days=30)
        nf = movimento.nota_fiscal or f"MOV-{movimento_id}"

        gcp = GestaoCustoPai(
            admin_id=admin_id,
            tipo_categoria='MATERIAL',
            entidade_nome=fornecedor.razao_social or fornecedor.nome,
            entidade_id=fornecedor.id,
            fornecedor_id=fornecedor.id,
            valor_total=valor_total,
            valor_pago=0,
            saldo=valor_total,
            status='PENDENTE',
            data_emissao=data_mov,
            data_vencimento=data_venc,
            numero_documento=nf,
            numero_parcela=1,
            total_parcelas=1,
            observacoes=f"Entrada almoxarifado: {item_nome} (Movimento #{movimento_id})",
        )
        db.session.add(gcp)
        db.session.flush()

        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=data_mov,
            descricao=f"Entrada de material - {item_nome} (Movimento #{movimento_id})",
            valor=valor_total,
            origem_tabela='almoxarifado_movimento',
            origem_id=movimento_id,
        )
        db.session.add(gcf)
        db.session.commit()

        logger.info(f"✅ GestaoCustoPai COMPRA criado (ID {gcp.id}) para movimento {movimento_id} - R$ {valor_total}")

        # Lançamento contábil automático
        try:
            from models import LancamentoContabil, PartidaContabil, PlanoContas
            from sqlalchemy import func

            conta_estoque = PlanoContas.query.filter_by(codigo='1.1.05.001', admin_id=admin_id).first()
            conta_fornecedores = PlanoContas.query.filter_by(codigo='2.1.01.001', admin_id=admin_id).first()

            if not conta_estoque or not conta_fornecedores:
                logger.warning(f"⚠️ Contas contábeis não configuradas — lançamento não criado para movimento {movimento_id}")
            else:
                ultimo_numero = db.session.query(func.max(LancamentoContabil.numero)).filter_by(admin_id=admin_id).scalar()
                numero_lancamento = (ultimo_numero + 1) if ultimo_numero else 1

                lancamento = LancamentoContabil(
                    admin_id=admin_id,
                    numero=numero_lancamento,
                    data_lancamento=data_mov,
                    historico=f"Entrada de material - {item_nome} (Movimento #{movimento_id})",
                    origem='ALMOXARIFADO_ENTRADA',
                    origem_id=movimento_id,
                    valor_total=valor_total
                )
                db.session.add(lancamento)
                db.session.flush()

                db.session.add(PartidaContabil(
                    admin_id=admin_id, lancamento_id=lancamento.id,
                    conta_codigo='1.1.05.001', tipo_partida='DEBITO',
                    valor=valor_total,
                    historico_complementar=f"Entrada de material - {item_nome}",
                    sequencia=1
                ))
                db.session.add(PartidaContabil(
                    admin_id=admin_id, lancamento_id=lancamento.id,
                    conta_codigo='2.1.01.001', tipo_partida='CREDITO',
                    valor=valor_total,
                    historico_complementar=f"Compra de material - {fornecedor.razao_social or fornecedor.nome}",
                    sequencia=2
                ))
                db.session.commit()
                logger.info(f"✅ Lançamento contábil #{numero_lancamento} criado para movimento {movimento_id}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar lançamento contábil entrada: {e}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao processar evento material_entrada para movimento {data.get('movimento_id')}: {e}")
        import traceback
        logger.error(traceback.format_exc())


@event_handler('ponto_registrado')
def calcular_horas_folha(data: dict, admin_id: int):
    """Handler: Calcular horas para folha quando ponto é registrado (suporta diaristas V2)"""
    try:
        from models import db, RegistroPonto, CustoObra, Funcionario
        from datetime import datetime
        from decimal import Decimal
        
        registro_id = data.get('registro_id')
        tipo_ponto = data.get('tipo_ponto', '')
        
        if not registro_id:
            logger.warning(f"[WARN] registro_id não fornecido no evento ponto_registrado")
            return
        
        # Buscar registro de ponto
        registro = RegistroPonto.query.filter_by(
            id=registro_id,
            admin_id=admin_id
        ).first()
        
        if not registro:
            logger.error(f"[ERROR] Registro de ponto {registro_id} não encontrado para admin {admin_id}")
            return
        
        # Validar se tem obra vinculada
        if not registro.obra_id:
            logger.info(f"[INFO] Custo não lançado: registro {registro_id} sem obra vinculada")
            return
        
        # Buscar funcionário
        funcionario = Funcionario.query.get(registro.funcionario_id)
        if not funcionario:
            logger.error(f"[ERROR] Funcionário {registro.funcionario_id} não encontrado")
            return

        # ── V2: DIARISTA ──────────────────────────────────────────────────
        if getattr(funcionario, 'tipo_remuneracao', 'salario') == 'diaria':
            valor_diaria = float(getattr(funcionario, 'valor_diaria', 0) or 0)
            if valor_diaria <= 0:
                logger.warning(f"[WARN] Diarista {funcionario.nome} sem valor_diaria configurado")
                return

            # Só criar custo na entrada (não duplicar em saída/almoço)
            if tipo_ponto != 'entrada':
                logger.info(f"[INFO] Diarista {funcionario.nome}: custo só criado na entrada, ignorando {tipo_ponto}")
                return

            # Idempotência dupla: por registro_id E por (funcionário+data) para cobrir edge cases
            # de múltiplos RegistroPonto no mesmo dia (ex: imports manuais)
            from models import GestaoCustoFilho, GestaoCustoPai
            # Verificação primária: mesmo registro_id
            ja_existe = GestaoCustoFilho.query.filter_by(
                origem_tabela='registro_ponto',
                origem_id=registro.id,
                admin_id=admin_id
            ).first()
            if not ja_existe:
                # Verificação secundária: mesmo funcionário + mesma data (data_referencia)
                ja_existe = (
                    GestaoCustoFilho.query
                    .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
                    .filter(
                        GestaoCustoFilho.origem_tabela == 'registro_ponto',
                        GestaoCustoFilho.data_referencia == registro.data,
                        GestaoCustoPai.entidade_id == funcionario.id,
                        GestaoCustoFilho.admin_id == admin_id,
                    )
                    .first()
                )
            if ja_existe:
                logger.info(f"[INFO] Custo diária de {funcionario.nome} em {registro.data} já existe — skip (idempotência)")
                return

            descricao = f"Diária - {funcionario.nome} - {registro.data.strftime('%d/%m/%Y')}"

            # Usar registrar_custo_automatico para criar GestaoCustoPai + Filho
            # Assim o custo aparece na tela Gestão de Custos V2
            from utils.financeiro_integration import registrar_custo_automatico
            filho = registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria='SALARIO',
                entidade_nome=funcionario.nome,
                entidade_id=funcionario.id,
                data=registro.data,
                descricao=descricao,
                valor=valor_diaria,
                obra_id=registro.obra_id,
                origem_tabela='registro_ponto',
                origem_id=registro.id,
            )
            if filho:
                logger.info(f"[OK] Custo diária pendente: R$ {valor_diaria:.2f} na obra {registro.obra_id} — {funcionario.nome}")
            else:
                logger.warning(f"[WARN] registrar_custo_automatico retornou None para diarista {funcionario.nome}")

            # ── AUTO-LANÇAMENTO VA (Vale Alimentação) ─────────────────────
            valor_va = float(getattr(funcionario, 'valor_va', 0) or 0)
            if valor_va > 0:
                ja_existe_va = GestaoCustoFilho.query.filter_by(
                    origem_tabela='registro_ponto_va',
                    origem_id=registro.id,
                    admin_id=admin_id
                ).first()
                if not ja_existe_va:
                    filho_va = registrar_custo_automatico(
                        admin_id=admin_id,
                        tipo_categoria='ALIMENTACAO',
                        entidade_nome=funcionario.nome,
                        entidade_id=funcionario.id,
                        data=registro.data,
                        descricao=f"VA - {funcionario.nome} - {registro.data.strftime('%d/%m/%Y')}",
                        valor=valor_va,
                        obra_id=registro.obra_id,
                        origem_tabela='registro_ponto_va',
                        origem_id=registro.id,
                    )
                    if filho_va:
                        logger.info(f"[OK] VA pendente: R$ {valor_va:.2f} — {funcionario.nome}")
                    else:
                        logger.warning(f"[WARN] VA não lançado para {funcionario.nome}")
                else:
                    logger.info(f"[INFO] VA {funcionario.nome} em {registro.data} já existe — skip")

            # ── AUTO-LANÇAMENTO VT (Vale Transporte) ──────────────────────
            valor_vt = float(getattr(funcionario, 'valor_vt', 0) or 0)
            if valor_vt > 0:
                ja_existe_vt = GestaoCustoFilho.query.filter_by(
                    origem_tabela='registro_ponto_vt',
                    origem_id=registro.id,
                    admin_id=admin_id
                ).first()
                if not ja_existe_vt:
                    filho_vt = registrar_custo_automatico(
                        admin_id=admin_id,
                        tipo_categoria='TRANSPORTE',
                        entidade_nome=funcionario.nome,
                        entidade_id=funcionario.id,
                        data=registro.data,
                        descricao=f"VT - {funcionario.nome} - {registro.data.strftime('%d/%m/%Y')}",
                        valor=valor_vt,
                        obra_id=registro.obra_id,
                        origem_tabela='registro_ponto_vt',
                        origem_id=registro.id,
                    )
                    if filho_vt:
                        logger.info(f"[OK] VT pendente: R$ {valor_vt:.2f} — {funcionario.nome}")
                    else:
                        logger.warning(f"[WARN] VT não lançado para {funcionario.nome}")
                else:
                    logger.info(f"[INFO] VT {funcionario.nome} em {registro.data} já existe — skip")

            # ── Commit único para diária + VA + VT ────────────────────────
            db.session.commit()
            logger.info(f"[OK] Lançamentos diarista commitados: diária={valor_diaria:.2f} VA={valor_va:.2f} VT={valor_vt:.2f} — {funcionario.nome}")
            return
        # ── FIM V2: DIARISTA ──────────────────────────────────────────────

        # ── HORISTAS (comportamento original) ─────────────────────────────
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        horas_extras = float(registro.horas_extras or 0)
        
        if horas_trabalhadas <= 0:
            logger.info(f"[INFO] Custo não lançado: sem horas trabalhadas no registro {registro_id}")
            return
        
        # Calcular valor/hora baseado no período do registro
        data_inicio = registro.data
        data_fim = registro.data
        salario_hora = calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
        
        if salario_hora <= 0:
            logger.warning(f"[WARN] Funcionário {funcionario.nome} sem salário configurado")
            salario_hora = 0
        
        # Calcular valor do custo: horas normais + horas extras (50% adicional)
        valor_horas_normais = horas_trabalhadas * salario_hora
        valor_horas_extras = horas_extras * salario_hora * 1.5
        valor_total = valor_horas_normais + valor_horas_extras
        
        descricao = f"Mão de obra: {funcionario.nome} - {registro.data.strftime('%d/%m/%Y')}"
        if horas_extras > 0:
            descricao += f" ({horas_trabalhadas}h normais + {horas_extras}h extras)"
        else:
            descricao += f" ({horas_trabalhadas}h trabalhadas)"
        
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
        
        logger.info(f"[OK] Custo mão de obra lançado: R$ {valor_total:.2f} na obra {registro.obra_id}")
        logger.info(f"     Funcionário: {funcionario.nome} | {horas_trabalhadas}h + {horas_extras}h extras | Registro: {registro_id}")
        
    except ValueError as e:
        logger.error(f"[ERROR] Validação ao calcular horas: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"[ERROR] Erro ao calcular horas: {e}", exc_info=True)
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
    """Handler: Lançar custos de mão de obra quando RDO é finalizado.

    Regras de negócio (v2):
    - Custo base = funcionario.valor_diaria — sem fallback; se zero/nulo → skip
    - UMA diária por funcionário por data_rdo (deduplicação por funcionário, não por registro)
    - CustoObra: idempotente por rdo_id + funcionario_id + data + admin_id
    - GestaoCustoPai/Filho: via registrar_custo_automatico (tipo_categoria='SALARIO')
      deduplicado por origem_tabela + data_referencia + entidade_id + admin_id (sem orig_id)
    - Descrição inclui RDO# + nome + cargo + data + subatividades trabalhadas
    - Tenant-safe: funcionários validados com admin_id
    """
    try:
        from models import db, RDO, RDOMaoObra, RDOServicoSubatividade, Funcionario, CustoObra, GestaoCustoPai, GestaoCustoFilho
        from decimal import Decimal
        from utils.financeiro_integration import (
            registrar_custo_automatico,
            resolver_obra_servico_custo_id,
        )

        rdo_id = data.get('rdo_id')
        if not rdo_id:
            logger.warning("⚠️ rdo_id não fornecido no evento rdo_finalizado")
            return

        rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
        if not rdo:
            logger.error(f"❌ RDO {rdo_id} não encontrado para admin {admin_id}")
            return

        if not rdo.obra_id:
            logger.info(f"⏭️ Custos não lançados: RDO {rdo_id} sem obra vinculada")
            return

        mao_obra_registros = RDOMaoObra.query.filter_by(rdo_id=rdo_id).all()
        if not mao_obra_registros:
            logger.info(f"⏭️ Nenhuma mão de obra registrada no RDO {rdo_id}")
            return

        data_rdo = rdo.data_relatorio

        # Agrupar por funcionário (dedup) + coletar subatividades por funcionário
        func_mo_map = {}  # func_id → [RDOMaoObra]
        for mo in mao_obra_registros:
            if mo.funcionario_id:
                func_mo_map.setdefault(mo.funcionario_id, []).append(mo)

        custos_criados = 0
        gestao_criados = 0
        valor_total_custos = 0.0

        for func_id, mo_list in func_mo_map.items():
            # Tenant-safe: verificar que o funcionário pertence ao mesmo admin
            funcionario = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
            if not funcionario:
                logger.warning(f"⚠️ Funcionário {func_id} não encontrado para admin {admin_id} — ignorado")
                continue

            # Custo base: valor_diaria — sem fallback para horário
            valor_diaria = float(getattr(funcionario, 'valor_diaria', 0) or 0)
            if valor_diaria <= 0:
                logger.warning(f"⚠️ {funcionario.nome}: valor_diaria não configurado (={valor_diaria}) — custo RDO não lançado")
                continue

            # Coletar nomes de subatividades trabalhadas por este funcionário
            # e os ``servico_id`` distintos — usados para auto-vincular o
            # custo gerado ao ``ObraServicoCusto`` correspondente.
            sub_nomes = []
            servico_ids_distintos = set()
            for mo in mo_list:
                if mo.subatividade_id:
                    try:
                        sub = RDOServicoSubatividade.query.get(mo.subatividade_id)
                        if sub and sub.nome_subatividade and sub.nome_subatividade not in sub_nomes:
                            sub_nomes.append(sub.nome_subatividade)
                        if sub and sub.servico_id:
                            servico_ids_distintos.add(sub.servico_id)
                    except Exception as sub_err:
                        logger.warning(f"⚠️ Erro ao ler subatividade {mo.subatividade_id} para {funcionario.nome}: {sub_err}")

            # Auto-vínculo custo→serviço (Task #78): só preenche quando o
            # funcionário trabalhou em UM único serviço no RDO — caso
            # contrário, o custo fica sem vínculo e segue para rateio.
            obra_servico_custo_id_auto = None
            if len(servico_ids_distintos) == 1:
                (servico_id_unico,) = tuple(servico_ids_distintos)
                obra_servico_custo_id_auto = resolver_obra_servico_custo_id(
                    obra_id=rdo.obra_id,
                    servico_id=servico_id_unico,
                    admin_id=admin_id,
                )

            funcao = 'Diarista'
            try:
                if hasattr(funcionario, 'funcao_ref') and funcionario.funcao_ref:
                    funcao = funcionario.funcao_ref.nome
                elif hasattr(funcionario, 'funcao') and funcionario.funcao:
                    funcao = funcionario.funcao
            except Exception as funcao_err:
                logger.warning(f"⚠️ Erro ao ler função do funcionário {funcionario.nome}: {funcao_err}")

            sub_str = f" | {', '.join(sub_nomes)}" if sub_nomes else ""
            descricao = (
                f"RDO #{rdo.numero_rdo} - {funcionario.nome} ({funcao})"
                f" - {data_rdo.strftime('%d/%m/%Y')} - 1 diária{sub_str}"
            )

            # CustoObra — idempotente por rdo_id + funcionario_id + data + admin_id
            existing_custo = CustoObra.query.filter_by(
                rdo_id=rdo.id,
                funcionario_id=func_id,
                data=data_rdo,
                admin_id=admin_id
            ).first()
            if not existing_custo:
                custo = CustoObra(
                    obra_id=rdo.obra_id,
                    tipo='mao_obra',
                    descricao=descricao,
                    valor=valor_diaria,
                    data=data_rdo,
                    funcionario_id=func_id,
                    rdo_id=rdo.id,
                    admin_id=admin_id,
                    horas_trabalhadas=Decimal('0'),    # Custo por diária (não por hora)
                    horas_extras=Decimal('0'),
                    valor_unitario=Decimal(str(valor_diaria)),
                    quantidade=Decimal('1'),            # 1 diária
                    categoria='RDO'
                )
                db.session.add(custo)
                custos_criados += 1
            
            # GestaoCustoPai/Filho via registrar_custo_automatico (tipo_categoria='SALARIO')
            # Idempotência: origem_tabela + data_referencia + entidade_id + admin_id (sem origem_id)
            existing_filho = (
                db.session.query(GestaoCustoFilho)
                .filter(
                    GestaoCustoFilho.origem_tabela == 'rdo_mao_obra',
                    GestaoCustoFilho.data_referencia == data_rdo,
                    GestaoCustoFilho.admin_id == admin_id,
                )
                .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
                .filter(
                    GestaoCustoPai.entidade_id == func_id,
                    # Aceita tanto a categoria legada (SALARIO) quanto a normalizada
                    # (MAO_OBRA_DIRETA) — pais antigos podem estar em qualquer forma.
                    GestaoCustoPai.tipo_categoria.in_(['SALARIO', 'MAO_OBRA_DIRETA']),
                    GestaoCustoPai.admin_id == admin_id,
                )
                .first()
            )

            if not existing_filho:
                filho = registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='SALARIO',
                    entidade_nome=funcionario.nome,
                    entidade_id=func_id,
                    data=data_rdo,
                    descricao=descricao,
                    valor=valor_diaria,
                    obra_id=rdo.obra_id,
                    origem_tabela='rdo_mao_obra',
                    origem_id=rdo.id,
                    obra_servico_custo_id=obra_servico_custo_id_auto,
                )
                if filho:
                    gestao_criados += 1
                else:
                    logger.warning(f"⚠️ registrar_custo_automatico retornou None para {funcionario.nome}")
            else:
                logger.info(f"⏭️ GestaoCustoFilho já existe para {funcionario.nome} em {data_rdo} — skip")

            valor_total_custos += valor_diaria

        db.session.commit()
        logger.info(
            f"✅ RDO {rdo.numero_rdo}: {custos_criados} CustoObra + {gestao_criados} GestaoCustoFilho "
            f"lançados para {len(func_mo_map)} funcionário(s) únicos "
            f"(Total: R$ {valor_total_custos:.2f})"
        )

    except Exception as e:
        logger.error(f"❌ Erro ao lançar custos do RDO: {e}", exc_info=True)
        db.session.rollback()


@event_handler('proposta_aprovada')
def propagar_proposta_para_obra(data: dict, admin_id: int):
    """Handler Task #94: ao aprovar proposta, garantir Obra + token_cliente +
    back-link Proposta.obra_id/convertida_em_obra. **NÃO cria ContaReceber**
    (regra v2: ContaReceber nasce/atualiza apenas via avanço de medição
    com origem_tipo='OBRA_MEDICAO' a partir de RDO/fechamento de medição).

    Itens de medição (IMC) e snapshots de custo (OSC) são criados pelo
    handler `handlers.propostas_handlers.handle_proposta_aprovada` que roda
    em sequência (ver app.py, ordem de import).

    Task #102 (atomicidade real): este handler NÃO commita nem faz rollback.
    A rota chamadora é dona da transação e decide commit/rollback após o
    `EventManager.emit(..., raise_on_error=True)` retornar com sucesso.
    Qualquer exceção é propagada para a rota fazer rollback completo
    (Obra + IMC + lançamento contábil + cronograma — tudo ou nada).
    """
    from models import db, Proposta, Obra
    from datetime import datetime
    from sqlalchemy import func
    import secrets

    proposta_id = data.get('proposta_id')
    if not proposta_id:
        logger.warning("⚠️ proposta_id não fornecido no evento proposta_aprovada")
        return

    proposta = Proposta.query.filter_by(id=proposta_id, admin_id=admin_id).first()
    if not proposta:
        logger.error(f"❌ Proposta {proposta_id} não encontrada para admin {admin_id}")
        return

    valor_total = float(proposta.valor_total or 0)
    cliente_nome = proposta.cliente_nome or 'Cliente não identificado'

    # Task #172 — resolver Cliente preferindo o vínculo já presente na
    # proposta; senão, dedup por nome/e-mail. Tudo na mesma transação da
    # rota chamadora — propagamos qualquer erro para garantir rollback
    # atômico (não vinculamos Obra silenciosamente sem cliente_id).
    from services.cliente_resolver import obter_ou_criar_cliente
    cliente_obj = obter_ou_criar_cliente(
        admin_id=admin_id,
        nome=proposta.cliente_nome,
        email=proposta.cliente_email,
        telefone=proposta.cliente_telefone,
        cliente_id=getattr(proposta, 'cliente_id', None),
    )

    # 1) Localizar (ou criar) a Obra vinculada à proposta
    obra = None
    if proposta.obra_id:
        obra = Obra.query.filter_by(id=proposta.obra_id, admin_id=admin_id).first()
    if not obra:
        obra = Obra.query.filter_by(
            proposta_origem_id=proposta_id, admin_id=admin_id
        ).first()

    if not obra:
        ultimo_codigo = db.session.query(func.max(Obra.codigo)).filter(
            Obra.admin_id == admin_id,
            Obra.codigo.like('OBR%'),
        ).scalar()
        if ultimo_codigo and ultimo_codigo.startswith('OBR'):
            try:
                numero = int(ultimo_codigo[3:]) + 1
            except ValueError:
                numero = 1
        else:
            numero = 1
        codigo_obra = f"OBR{numero:04d}"
        for _ in range(50):
            exists = db.session.query(Obra.id).filter_by(
                admin_id=admin_id, codigo=codigo_obra
            ).first()
            if not exists:
                break
            numero += 1
            codigo_obra = f"OBR{numero:04d}"

        # Task #176 — Obra exige cliente_id (FK NOT NULL). Se a Proposta
        # não tem cliente cadastrado, abortamos a propagação para evitar
        # inserir uma Obra órfã.
        if not cliente_obj:
            raise ValueError(
                f"Proposta {proposta.numero} sem cliente cadastrado "
                f"— não é possível criar a Obra correspondente."
            )
        obra = Obra(
            nome=f"Obra - {proposta.titulo or proposta.numero}",
            codigo=codigo_obra,
            cliente_id=cliente_obj.id,
            endereco=proposta.cliente_endereco,
            data_inicio=datetime.now().date(),
            valor_contrato=valor_total,
            orcamento=valor_total,
            status='Em andamento',
            proposta_origem_id=proposta_id,
            admin_id=admin_id,
            ativo=True,
            portal_ativo=True,
        )
        db.session.add(obra)
        db.session.flush()
        logger.info(
            f"📋 Obra {codigo_obra} criada para proposta {proposta.numero} "
            f"(cliente_id={obra.cliente_id})"
        )
    else:
        # Task #176 — popula cliente_id em obras pré-existentes (legado).
        if not obra.cliente_id and cliente_obj:
            obra.cliente_id = cliente_obj.id
        if (obra.valor_contrato or 0) <= 0 and valor_total > 0:
            obra.valor_contrato = valor_total
        if (obra.orcamento or 0) <= 0 and valor_total > 0:
            obra.orcamento = valor_total

    # 2) Garantir token_cliente para portal público
    if not obra.token_cliente:
        obra.token_cliente = secrets.token_urlsafe(32)

    # 3) Back-link Proposta → Obra
    proposta.obra_id = obra.id
    proposta.convertida_em_obra = True
    if proposta.status not in ('APROVADA', 'aprovada'):
        proposta.status = 'APROVADA'

    db.session.flush()
    logger.info(
        f"✅ Proposta {proposta.numero} propagada para Obra {obra.codigo} "
        f"(token_cliente={'ok' if obra.token_cliente else 'AUSENTE'}, "
        f"valor_contrato={float(obra.valor_contrato or 0):.2f}) — "
        f"aguardando commit da rota chamadora"
    )


# ================================
# HANDLER: FOLHA DE PAGAMENTO PROCESSADA
# ================================

@event_handler('folha_processada')
def criar_lancamento_folha_pagamento(data: dict, admin_id: int):
    """
    Cria lançamento contábil automaticamente quando a folha é processada.
    
    Lançamento:
    D - 5.1.01.001 - Salários (Total Proventos + FGTS)
    C - 2.1.02.001 - Salários a Pagar (Salário Líquido)
    C - 2.1.02.002 - INSS a Recolher (INSS Descontado)
    C - 2.1.03.001 - IRRF a Recolher (IRRF Descontado)
    C - 2.1.02.003 - FGTS a Recolher (FGTS)
    """
    try:
        from models import (db, FolhaPagamento, LancamentoContabil, PartidaContabil, 
                           PlanoContas, Funcionario)
        from datetime import datetime
        
        logger.info(f"🔔 HANDLER FOLHA_PROCESSADA CHAMADO! admin_id={admin_id}, data={data}")
        
        folha_id = data.get('folha_id')
        if not folha_id:
            logger.warning("⚠️ folha_id não fornecido no evento folha_processada")
            return
        
        logger.info(f"📊 Criando lançamento contábil para folha {folha_id} | admin_id={admin_id}")
        
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
            codigo='2.1.02.001',
            ativo=True
        ).first()
        
        conta_inss_recolher = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.02.002',
            ativo=True
        ).first()
        
        conta_irrf_recolher = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.03.001',
            ativo=True
        ).first()
        
        conta_fgts_recolher = PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo='2.1.02.003',
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


@event_handler('rdo_finalizado')
def recalcular_medicao_apos_rdo(data: dict, admin_id: int):
    """Task #94 — após RDO finalizado, atualiza a ContaReceber única da obra
    (origem_tipo='OBRA_MEDICAO') refletindo o avanço do medido.

    Roda em paralelo a `lancar_custos_rdo` (mesmo evento) sem interferir:
    o handler de custos cria GestaoCustoFilho + CustoObra; este aqui só
    olha para os ItemMedicaoComercial.valor_executado_acumulado da obra.
    """
    try:
        obra_id = data.get('obra_id')
        if not obra_id:
            logger.warning("⚠️ obra_id ausente em rdo_finalizado — recalcular_medicao_obra pulado")
            return
        from services.medicao_service import recalcular_medicao_obra
        recalcular_medicao_obra(obra_id, admin_id)
    except Exception as e:
        logger.error(f"❌ Erro em recalcular_medicao_apos_rdo: {e}", exc_info=True)


# Log de inicialização
logger.info(f"✅ Event Manager inicializado - {len(EventManager.list_events())} eventos registrados")
