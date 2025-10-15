"""
Handler de Eventos - Folha de Pagamento
Integração automática: Folha de Pagamento → Contabilidade → Custos
"""

from event_manager import event_handler
from models import db, FolhaPagamento, Funcionario, LancamentoContabil, PartidaContabil, CustoObra
from decimal import Decimal
from datetime import date
import logging

logger = logging.getLogger(__name__)


@event_handler('folha_processada')
def handle_folha_processada(data: dict, admin_id: int):
    """
    Handler para folha processada - Cria lançamentos contábeis e custos
    
    Quando uma folha é processada, este handler:
    1. Cria lançamento contábil com partidas dobradas
    2. Cria custo na obra (se funcionário alocado)
    
    Args:
        data: Dados do evento contendo folha_id, funcionario_id, valor_total, encargos
        admin_id: ID do administrador/tenant
    """
    
    try:
        folha_id = data.get('folha_id')
        funcionario_id = data.get('funcionario_id')
        valor_total = Decimal(str(data.get('valor_total', 0)))
        encargos = Decimal(str(data.get('encargos', 0)))
        
        logger.info(f"🔔 Processando evento folha_processada - Folha: {folha_id}, Funcionário: {funcionario_id}")
        
        # 1. Buscar folha de pagamento
        folha = FolhaPagamento.query.get(folha_id)
        if not folha:
            logger.warning(f"⚠️ Folha {folha_id} não encontrada")
            return
        
        # Buscar funcionário
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            logger.warning(f"⚠️ Funcionário {funcionario_id} não encontrado")
            return
        
        # 2. Criar lançamento contábil
        lancamento = LancamentoContabil(
            numero=gerar_numero_lancamento(admin_id),
            data_lancamento=date.today(),
            historico=f"Folha de pagamento {folha.mes_referencia.strftime('%m/%Y')} - {funcionario.nome}",
            valor_total=float(valor_total),
            origem='FOLHA_PAGAMENTO',
            origem_id=folha_id,
            admin_id=admin_id
        )
        db.session.add(lancamento)
        db.session.flush()  # Para pegar o ID
        
        logger.info(f"✅ Lançamento contábil #{lancamento.numero} criado")
        
        # 3. Criar partidas contábeis (débito e crédito)
        # Débito: Despesa com Salários
        partida_debito = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=1,
            conta_codigo='3.1.01.001',  # Salários e Ordenados
            tipo_partida='DEBITO',
            valor=float(valor_total),
            admin_id=admin_id
        )
        db.session.add(partida_debito)
        
        # Crédito: Salários a Pagar
        inss = Decimal(str(folha.inss or 0))
        irrf = Decimal(str(folha.irrf or 0))
        salario_liquido = valor_total - inss - irrf
        
        partida_credito1 = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=2,
            conta_codigo='2.1.02.001',  # Salários a Pagar
            tipo_partida='CREDITO',
            valor=float(salario_liquido),
            admin_id=admin_id
        )
        db.session.add(partida_credito1)
        
        # Crédito: INSS a Recolher (se houver)
        if inss > 0:
            partida_credito2 = PartidaContabil(
                lancamento_id=lancamento.id,
                sequencia=3,
                conta_codigo='2.1.03.001',  # INSS a Recolher
                tipo_partida='CREDITO',
                valor=float(inss),
                admin_id=admin_id
            )
            db.session.add(partida_credito2)
            logger.info(f"   💰 INSS: R$ {float(inss):.2f}")
        
        # Crédito: IRRF a Recolher (se houver)
        if irrf > 0:
            partida_credito3 = PartidaContabil(
                lancamento_id=lancamento.id,
                sequencia=4,
                conta_codigo='2.1.03.002',  # IRRF a Recolher
                tipo_partida='CREDITO',
                valor=float(irrf),
                admin_id=admin_id
            )
            db.session.add(partida_credito3)
            logger.info(f"   💰 IRRF: R$ {float(irrf):.2f}")
        
        logger.info(f"✅ Partidas contábeis criadas - Débito: R$ {float(valor_total):.2f}, Crédito: R$ {float(salario_liquido + inss + irrf):.2f}")
        
        # 4. Criar custo na obra (se funcionário vinculado a obra)
        if funcionario and hasattr(funcionario, 'obra_id') and funcionario.obra_id:
            custo_obra = CustoObra(
                obra_id=funcionario.obra_id,
                data=date.today(),
                tipo='MAO_OBRA',
                descricao=f"Folha {funcionario.nome} - {folha.mes_referencia.strftime('%m/%Y')}",
                valor=float(valor_total + encargos),
                funcionario_id=funcionario_id,
                admin_id=admin_id
            )
            db.session.add(custo_obra)
            logger.info(f"✅ Custo de obra criado: R$ {float(valor_total + encargos):.2f} na obra {funcionario.obra_id}")
        else:
            logger.info(f"ℹ️ Funcionário {funcionario.nome} não vinculado a obra - custo não lançado")
        
        # NÃO fazer commit aqui - deixar para o caller (integridade transacional)
        # O commit será feito em processar_folha_mes() após processar todos os funcionários
        
        logger.info(f"✅ Lançamento contábil #{lancamento.numero} preparado para folha {folha_id} - {funcionario.nome}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao processar evento folha_processada: {e}", exc_info=True)


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
