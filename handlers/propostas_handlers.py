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
