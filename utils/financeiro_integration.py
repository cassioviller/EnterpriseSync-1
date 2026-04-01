"""
utils/financeiro_integration.py
Funções de integração para o módulo Gestão de Custos V2.
Chamada automaticamente pelos módulos operacionais (Alimentação, Transporte, etc.)
"""

import logging
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


def registrar_custo_automatico(
    admin_id: int,
    tipo_categoria: str,
    entidade_nome: str,
    entidade_id,
    data,
    descricao: str,
    valor,
    obra_id=None,
    centro_custo_id=None,
    origem_tabela: str = None,
    origem_id: int = None,
):
    """
    Coração da integração: registra automaticamente um custo no módulo
    Gestão de Custos V2 quando um módulo operacional gera uma despesa.

    Fluxo:
    1. Busca um GestaoCustoPai PENDENTE para a mesma (admin_id, tipo_categoria, entidade_id/nome)
    2. Se não existir, cria um novo
    3. Adiciona um GestaoCustoFilho com o lançamento
    4. Recalcula o valor_total do Pai
    5. Faz flush (sem commit — o módulo chamador faz o commit)

    Retorna o objeto GestaoCustoFilho criado, ou None em caso de erro.
    """
    try:
        from utils.tenant import is_v2_active
        if not is_v2_active():
            return None

        from app import db
        from models import GestaoCustoPai, GestaoCustoFilho
        from sqlalchemy import func

        valor_dec = Decimal(str(valor))
        if isinstance(data, str):
            data = datetime.strptime(data, '%Y-%m-%d').date()

        # Busca pai PENDENTE para a mesma categoria+entidade
        pai = GestaoCustoPai.query.filter_by(
            admin_id=admin_id,
            tipo_categoria=tipo_categoria,
            entidade_id=entidade_id if entidade_id else None,
            status='PENDENTE',
        ).filter(
            GestaoCustoPai.entidade_nome == entidade_nome,
        ).first()

        if not pai:
            pai = GestaoCustoPai(
                admin_id=admin_id,
                tipo_categoria=tipo_categoria,
                entidade_nome=entidade_nome,
                entidade_id=entidade_id,
                valor_total=Decimal('0.00'),
                status='PENDENTE',
            )
            db.session.add(pai)
            db.session.flush()
            logger.info(f"[OK] GestaoCustoPai criado: {tipo_categoria} / {entidade_nome}")

        filho = GestaoCustoFilho(
            pai_id=pai.id,
            data_referencia=data,
            descricao=descricao,
            valor=valor_dec,
            obra_id=obra_id,
            centro_custo_id=centro_custo_id,
            origem_tabela=origem_tabela,
            origem_id=origem_id,
            admin_id=admin_id,
        )
        db.session.add(filho)

        # Recalcula valor_total a partir de todos os filhos + novo
        total_atual = (
            db.session.query(func.coalesce(func.sum(GestaoCustoFilho.valor), 0))
            .filter_by(pai_id=pai.id)
            .scalar()
        ) or Decimal('0.00')
        pai.valor_total = Decimal(str(total_atual)) + valor_dec

        db.session.flush()
        logger.info(
            f"[OK] GestaoCustoFilho adicionado: pai={pai.id} valor={valor_dec} desc={descricao[:50]}"
        )
        return filho

    except Exception as e:
        logger.error(f"[ERROR] registrar_custo_automatico falhou: {e}", exc_info=True)
        return None


# Mapeamento legível de categorias
CATEGORIA_LABELS = {
    'SALARIO': 'Pagamento Salário',
    'ALIMENTACAO': 'Despesa Alimentação',
    'TRANSPORTE': 'Despesa Transporte',
    'VEICULO': 'Despesa de Frota',
    'COMPRA': 'Compra de Material',
    'REEMBOLSO': 'Reembolso a Pagar',
    'OUTROS': 'Outros Custos',
}

# Cores de status para a UI
STATUS_BADGES = {
    'PENDENTE': 'secondary',
    'SOLICITADO': 'warning',
    'AUTORIZADO': 'success',
    'PAGO': 'primary',
    'RECUSADO': 'danger',
}
