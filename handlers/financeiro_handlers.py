"""
Handler de Eventos - Financeiro
Integração automática: Financeiro → Contabilidade (Pagamento de Notas Fiscais)
"""

from event_manager import event_handler
from models import db, LancamentoContabil, PartidaContabil
from decimal import Decimal
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


@event_handler('nota_fiscal_paga')
def handle_nota_fiscal_paga(data: dict, admin_id: int):
    """
    Handler para nota fiscal paga - Cria lançamentos contábeis
    
    Quando uma nota fiscal é paga, este handler:
    1. Cria lançamento contábil (Despesas / Bancos)
    2. Determina conta de despesa baseada na categoria
    
    Args:
        data: Dados do evento contendo nota_fiscal_id, fornecedor_nome, valor_total, categoria, data_pagamento
        admin_id: ID do administrador/tenant
    """
    
    try:
        nota_fiscal_id = data.get('nota_fiscal_id')
        fornecedor_nome = data.get('fornecedor_nome')
        valor_total = Decimal(str(data.get('valor_total', 0)))
        categoria = data.get('categoria', 'OUTROS')
        data_pagamento = data.get('data_pagamento')
        
        logger.info(f"🔔 Processando evento nota_fiscal_paga - NF: {nota_fiscal_id}, Fornecedor: {fornecedor_nome}, Categoria: {categoria}")
        
        # Validações básicas
        if not nota_fiscal_id:
            logger.warning(f"⚠️ nota_fiscal_id não fornecido no evento nota_fiscal_paga")
            return
        
        if valor_total <= 0:
            logger.warning(f"⚠️ Valor total inválido ou zerado: {valor_total}")
            return
        
        if not fornecedor_nome:
            logger.warning(f"⚠️ fornecedor_nome não fornecido no evento nota_fiscal_paga")
            fornecedor_nome = "Fornecedor não identificado"
        
        # Converter data_pagamento se for string
        if isinstance(data_pagamento, str):
            try:
                data_pagamento = datetime.strptime(data_pagamento, '%Y-%m-%d').date()
            except ValueError:
                data_pagamento = date.today()
        elif not isinstance(data_pagamento, date):
            data_pagamento = date.today()
        
        # Determinar conta de despesa baseada na categoria
        conta_despesa = determinar_conta_despesa(categoria)
        categoria_nome = obter_nome_categoria(categoria)
        
        logger.info(f"   📊 Categoria: {categoria} → Conta: {conta_despesa} ({categoria_nome})")
        
        # 1. Criar lançamento contábil
        lancamento = LancamentoContabil(
            numero=gerar_numero_lancamento(admin_id),
            data_lancamento=data_pagamento,
            historico=f"Pagamento NF #{nota_fiscal_id} - {fornecedor_nome} ({categoria_nome})",
            valor_total=float(valor_total),
            origem='FINANCEIRO',
            origem_id=nota_fiscal_id,
            admin_id=admin_id
        )
        db.session.add(lancamento)
        db.session.flush()
        
        logger.info(f"✅ Lançamento contábil #{lancamento.numero} criado")
        
        # 2. Criar partidas contábeis (débito e crédito)
        # Débito: Conta de Despesa (conforme categoria)
        partida_debito = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=1,
            conta_codigo=conta_despesa,
            tipo_partida='DEBITO',
            valor=float(valor_total),
            historico_complementar=f"{categoria_nome} - {fornecedor_nome}",
            admin_id=admin_id
        )
        db.session.add(partida_debito)
        
        # Crédito: Bancos Conta Movimento (saída de caixa)
        partida_credito = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=2,
            conta_codigo='1.1.01.002',  # Bancos Conta Movimento
            tipo_partida='CREDITO',
            valor=float(valor_total),
            historico_complementar=f"Pagamento NF {nota_fiscal_id}",
            admin_id=admin_id
        )
        db.session.add(partida_credito)
        
        logger.info(f"✅ Partidas contábeis criadas - Débito: R$ {float(valor_total):.2f} ({conta_despesa}), Crédito: R$ {float(valor_total):.2f} (1.1.01.002)")
        
        # Commit das alterações
        db.session.commit()
        
        logger.info(f"✅ Handler nota_fiscal_paga executado com sucesso - NF #{nota_fiscal_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao processar evento nota_fiscal_paga: {e}", exc_info=True)


def determinar_conta_despesa(categoria: str) -> str:
    """
    Determina a conta de despesa baseada na categoria da nota fiscal
    
    Args:
        categoria: Categoria da despesa (MATERIAIS, SERVICOS, EQUIPAMENTOS, etc.)
        
    Returns:
        str: Código da conta contábil de despesa
    """
    mapeamento = {
        'MATERIAIS': '5.1.02.001',       # Materiais e Suprimentos
        'SUPRIMENTOS': '5.1.02.001',     # Materiais e Suprimentos
        'SERVICOS': '5.1.05.001',        # Despesas Comerciais (Serviços)
        'EQUIPAMENTOS': '5.1.02.001',    # Materiais e Suprimentos
        'MERCADORIAS': '5.1.03.001',     # CMV (Custo Mercadorias Vendidas)
        'ADMINISTRATIVO': '5.1.04.001',  # Despesas Administrativas
        'COMERCIAL': '5.1.05.001',       # Despesas Comerciais
        'FINANCEIRO': '5.2.01.001',      # Despesas Financeiras
        'OUTROS': '5.1.04.001',          # Despesas Administrativas (padrão)
    }
    
    return mapeamento.get(categoria.upper(), '5.1.04.001')


def obter_nome_categoria(categoria: str) -> str:
    """
    Retorna o nome descritivo da categoria
    
    Args:
        categoria: Código da categoria
        
    Returns:
        str: Nome descritivo da categoria
    """
    nomes = {
        'MATERIAIS': 'Materiais e Suprimentos',
        'SUPRIMENTOS': 'Materiais e Suprimentos',
        'SERVICOS': 'Serviços',
        'EQUIPAMENTOS': 'Equipamentos',
        'MERCADORIAS': 'Custo de Mercadorias Vendidas',
        'ADMINISTRATIVO': 'Despesas Administrativas',
        'COMERCIAL': 'Despesas Comerciais',
        'FINANCEIRO': 'Despesas Financeiras',
        'OUTROS': 'Outras Despesas',
    }
    
    return nomes.get(categoria.upper(), 'Despesas Diversas')


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
