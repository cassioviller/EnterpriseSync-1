"""
Handler de Eventos - Propostas Comerciais
Integração automática: Propostas → Contabilidade → Contas a Receber
"""

from event_manager import event_handler
from models import db, LancamentoContabil, PartidaContabil
from decimal import Decimal
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


def _propagar_proposta_para_obra(proposta_id: int, admin_id: int):
    """Task #82: ao aprovar proposta, materializar cada PropostaItem como
    ItemMedicaoComercial na obra vinculada (se houver). O listener after_insert
    em ItemMedicaoComercial cria automaticamente o ObraServicoCusto pareado
    (valor_orcado = valor_comercial; servico_catalogo_id = servico_id).

    Idempotente: se a obra já possui itens de medição vindos desta proposta,
    não duplica.
    """
    from models import Proposta, PropostaItem, ItemMedicaoComercial
    proposta = Proposta.query.filter_by(id=proposta_id, admin_id=admin_id).first()
    if not proposta or not getattr(proposta, 'obra_id', None):
        logger.info(f"#82: proposta {proposta_id} sem obra vinculada — pular propagação")
        return 0
    obra_id = proposta.obra_id

    # Idempotência: dedupe determinístico por proposta_item_id (não por nome)
    itens = PropostaItem.query.filter_by(proposta_id=proposta_id).all()
    if not itens:
        return 0
    ids_existentes = {
        row[0] for row in db.session.query(ItemMedicaoComercial.proposta_item_id).filter(
            ItemMedicaoComercial.admin_id == admin_id,
            ItemMedicaoComercial.obra_id == obra_id,
            ItemMedicaoComercial.proposta_item_id.in_([i.id for i in itens]),
        ).all()
    }
    criados = 0
    for it in itens:
        if it.id in ids_existentes:
            continue
        # Strict 1:1: criar SEMPRE um ItemMedicaoComercial por PropostaItem.
        # Se nome estiver vazio, fallback para "Item N"; se valor for 0,
        # cria assim mesmo (operador pode ajustar depois).
        nome_item = (getattr(it, 'descricao', None) or getattr(it, 'item', None) or '').strip()
        if not nome_item:
            nome_item = f'Item {getattr(it, "item_numero", None) or getattr(it, "ordem", None) or it.id}'
        valor_total = Decimal(str(it.subtotal or 0))
        if valor_total < 0:
            valor_total = Decimal('0')
        novo = ItemMedicaoComercial(
            admin_id=admin_id,
            obra_id=obra_id,
            nome=nome_item[:200],
            valor_comercial=valor_total,
            servico_id=getattr(it, 'servico_id', None),
            quantidade=Decimal(str(it.quantidade or 0)) if getattr(it, 'quantidade', None) is not None else None,
            proposta_item_id=it.id,
            status='PENDENTE',
        )
        db.session.add(novo)
        criados += 1
    if criados:
        db.session.flush()
        logger.info(f"#82: {criados} ItemMedicaoComercial criados para obra {obra_id} (proposta {proposta_id})")
    return criados


@event_handler('proposta_aprovada')
def handle_proposta_aprovada(data: dict, admin_id: int):
    """
    Handler para proposta aprovada - Cria lançamentos contábeis e conta a receber
    
    Quando uma proposta é aprovada, este handler:
    1. Cria lançamento contábil com partidas dobradas (Clientes a Receber / Receita de Serviços)
    2. Cria entrada em Contas a Receber do módulo financeiro
    
    Args:
        data: Dados do evento contendo proposta_id, cliente_nome, valor_total, data_aprovacao
        admin_id: ID do administrador/tenant
    """
    
    try:
        proposta_id = data.get('proposta_id')
        cliente_nome = data.get('cliente_nome')
        valor_total = Decimal(str(data.get('valor_total', 0)))
        data_aprovacao = data.get('data_aprovacao')
        
        logger.info(f"🔔 Processando evento proposta_aprovada - Proposta: {proposta_id}, Cliente: {cliente_nome}")
        
        # Validações básicas
        if not proposta_id:
            logger.warning(f"⚠️ proposta_id não fornecido no evento proposta_aprovada")
            return
        
        if not cliente_nome:
            logger.warning(f"⚠️ cliente_nome não fornecido no evento proposta_aprovada")
            cliente_nome = "Cliente não identificado"

        # Converter data_aprovacao se for string
        if isinstance(data_aprovacao, str):
            try:
                data_aprovacao = datetime.strptime(data_aprovacao, '%Y-%m-%d').date()
            except ValueError:
                data_aprovacao = date.today()
        elif not isinstance(data_aprovacao, date):
            data_aprovacao = date.today()

        # Task #94: lançamento contábil + ContaReceber só fazem sentido para
        # propostas com valor > 0. Mesmo com valor 0, propagamos os itens
        # comerciais para a obra (operador pode ajustar valores depois).
        if valor_total <= 0:
            logger.info(
                f"⏭️ Proposta {proposta_id}: valor zerado — pulando lançamento contábil; "
                f"propagação proposta→obra continua."
            )
            _propagar_proposta_para_obra(proposta_id, admin_id)
            # Task #102: cronograma também é materializado em propostas zeradas.
            try:
                from models import Proposta as _Proposta
                from services.cronograma_proposta import materializar_cronograma
                _proposta_obj = _Proposta.query.filter_by(
                    id=proposta_id, admin_id=admin_id
                ).first()
                if _proposta_obj and _proposta_obj.obra_id:
                    materializar_cronograma(
                        _proposta_obj, admin_id, _proposta_obj.obra_id, arvore_marcada=None
                    )
            except Exception as _e:
                logger.error(f"#102: falha ao materializar cronograma (proposta zerada) {proposta_id}: {_e}")
                raise
            db.session.commit()
            return

        # 1. Criar lançamento contábil
        lancamento = LancamentoContabil(
            numero=gerar_numero_lancamento(admin_id),
            data_lancamento=data_aprovacao,
            historico=f"Proposta aprovada #{proposta_id} - {cliente_nome}",
            valor_total=float(valor_total),
            origem='PROPOSTAS',
            origem_id=proposta_id,
            admin_id=admin_id
        )
        db.session.add(lancamento)
        db.session.flush()
        
        logger.info(f"✅ Lançamento contábil #{lancamento.numero} criado")
        
        # 2. Criar partidas contábeis (débito e crédito)
        # Débito: Clientes a Receber (Ativo)
        partida_debito = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=1,
            conta_codigo='1.1.02.001',  # Clientes (Contas a Receber)
            tipo_partida='DEBITO',
            valor=float(valor_total),
            admin_id=admin_id
        )
        db.session.add(partida_debito)
        
        # Crédito: Receita de Serviços
        partida_credito = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=2,
            conta_codigo='4.1.01.001',  # Receita de Serviços
            tipo_partida='CREDITO',
            valor=float(valor_total),
            admin_id=admin_id
        )
        db.session.add(partida_credito)
        
        logger.info(f"✅ Partidas contábeis criadas - Débito: R$ {float(valor_total):.2f} (1.1.02.001), Crédito: R$ {float(valor_total):.2f} (4.1.01.001)")

        # Task #94: ContaReceber NÃO é mais criada na aprovação. Ela é
        # gerada/atualizada automaticamente via UPSERT em
        # `services.medicao_service.recalcular_medicao_obra` à medida que o
        # avanço de obra é registrado (RDO finalizado ou medição quinzenal
        # fechada). origem_tipo='OBRA_MEDICAO', origem_id=obra.id.

        # Task #82: propagar para obra (ItemMedicaoComercial → ObraServicoCusto)
        # Propagação é MANDATÓRIA — se falhar, a aprovação inteira é revertida
        # pelo except externo. Isso garante o ciclo proposta → custos para
        # qualquer admin que use o catálogo. Caller pode tratar o ValueError.
        _propagar_proposta_para_obra(proposta_id, admin_id)

        # Task #102: materializar cronograma automático na obra a partir do
        # snapshot revisado (`Proposta.cronograma_default_json`) ou — caso
        # ausente — a partir da árvore default derivada de
        # `Servico.template_padrao_id`. Idempotente: tarefas já criadas para
        # um proposta_item_id são puladas. Falha aqui também reverte tudo.
        try:
            from models import Proposta as _Proposta
            from services.cronograma_proposta import materializar_cronograma
            _proposta_obj = _Proposta.query.filter_by(
                id=proposta_id, admin_id=admin_id
            ).first()
            if _proposta_obj and _proposta_obj.obra_id:
                materializar_cronograma(
                    _proposta_obj, admin_id, _proposta_obj.obra_id, arvore_marcada=None
                )
        except Exception as _e:
            logger.error(f"#102: falha ao materializar cronograma da proposta {proposta_id}: {_e}")
            raise

        # Commit das alterações
        db.session.commit()
        
        logger.info(f"✅ Handler proposta_aprovada executado com sucesso - Proposta #{proposta_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao processar evento proposta_aprovada: {e}", exc_info=True)
        # Re-raise para o caller (event manager) ter visibilidade da falha;
        # propagação proposta→obra é parte do contrato e não deve falhar
        # silenciosamente. Quem dispara o evento pode capturar e alertar.
        raise


def gerar_numero_lancamento(admin_id: int) -> int:
    """
    Gera número sequencial para lançamento contábil
    
    Args:
        admin_id: ID do administrador/tenant
        
    Returns:
        int: Próximo número sequencial
    """
    try:
        ultimo = LancamentoContabil.query.filter_by(
            admin_id=admin_id
        ).order_by(LancamentoContabil.numero.desc()).first()
        
        return (ultimo.numero + 1) if ultimo else 1
    except Exception as e:
        logger.error(f"❌ Erro ao gerar número de lançamento: {e}")
        return 1
