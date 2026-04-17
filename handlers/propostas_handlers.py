"""
Handler de Eventos - Propostas Comerciais
Integração automática: Propostas → Contabilidade → Contas a Receber
"""

from event_manager import event_handler
from models import db, LancamentoContabil, PartidaContabil, ContaReceber
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
        nome_item = (getattr(it, 'descricao', None) or getattr(it, 'item', None) or '').strip()
        if not nome_item:
            continue
        valor_total = Decimal(str(it.subtotal or 0))
        if valor_total <= 0:
            continue
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
        
        if valor_total <= 0:
            logger.warning(f"⚠️ Valor total inválido ou zerado: {valor_total}")
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
        
        # 3. Criar entrada em Contas a Receber
        # Calcular data de vencimento (30 dias após aprovação por padrão)
        from datetime import timedelta
        data_vencimento = data_aprovacao + timedelta(days=30)
        
        conta_receber = ContaReceber(
            cliente_nome=cliente_nome,
            cliente_cpf_cnpj=data.get('cliente_cpf_cnpj', ''),
            obra_id=data.get('obra_id'),
            numero_documento=f"PROP-{proposta_id}",
            descricao=f"Proposta comercial #{proposta_id} aprovada",
            valor_original=float(valor_total),
            valor_recebido=0,
            saldo=float(valor_total),
            data_emissao=data_aprovacao,
            data_vencimento=data_vencimento,
            status='PENDENTE',
            conta_contabil_codigo='1.1.02.001',
            origem_tipo='PROPOSTA',
            origem_id=proposta_id,
            admin_id=admin_id
        )
        db.session.add(conta_receber)
        
        logger.info(f"✅ Conta a receber criada: R$ {float(valor_total):.2f} - Vencimento: {data_vencimento.strftime('%d/%m/%Y')}")

        # 4. Task #82: propagar para obra (ItemMedicaoComercial → ObraServicoCusto)
        try:
            _propagar_proposta_para_obra(proposta_id, admin_id)
        except Exception as e_prop:
            logger.error(f"#82: erro ao propagar proposta {proposta_id} para obra: {e_prop}", exc_info=True)
            # Não derruba a transação principal — propagação é opcional

        # Commit das alterações
        db.session.commit()
        
        logger.info(f"✅ Handler proposta_aprovada executado com sucesso - Proposta #{proposta_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao processar evento proposta_aprovada: {e}", exc_info=True)


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
