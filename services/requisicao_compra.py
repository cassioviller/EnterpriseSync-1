"""Serviço da RequisicaoCompra — Fase 3.

Único caminho de escrita do estado e do valor da requisição. O modelo
(models.RequisicaoCompra) é deliberadamente burro: nenhuma regra mora
lá, para que não existam dois lugares onde uma transição possa
acontecer.
"""
import logging
from datetime import datetime
from decimal import Decimal

from models import EstadoRequisicao, RequisicaoCompra, db

logger = logging.getLogger('requisicao_compra')


def recalcular_valor(requisicao):
    """Soma os itens em `valor_estimado`. NÃO commita.

    Chamada em todo ponto que mexe em item. O valor é a base da alçada
    (services/alcada_compras.py), então deixá-lo desatualizado é deixar a
    requisição cair na faixa errada.
    """
    total = Decimal('0.00')
    for item in requisicao.itens:
        total += item.subtotal
    requisicao.valor_estimado = total
    requisicao.updated_at = datetime.utcnow()
    return total


def proximo_numero(admin_id, ano=None):
    """Próximo `RC-<ano>-<NNNN>` do tenant.

    Sequencial por tenant e por ano. Há corrida possível entre dois
    requests simultâneos; ela é fechada pelo UNIQUE (admin_id, numero) e
    pelo retry em `compras_views.requisicao_nova_post`. Mesmo padrão já
    usado no versionamento do relatório de mapa (views/obras.py:3279).
    """
    ano = ano or datetime.utcnow().year
    prefixo = f'RC-{ano}-'
    ultimo = (
        db.session.query(RequisicaoCompra.numero)
        .filter(RequisicaoCompra.admin_id == admin_id)
        .filter(RequisicaoCompra.numero.like(f'{prefixo}%'))
        .order_by(RequisicaoCompra.numero.desc())
        .first()
    )
    if not ultimo:
        return f'{prefixo}0001'
    try:
        seq = int(ultimo[0].rsplit('-', 1)[1]) + 1
    except (IndexError, ValueError):
        logger.warning('numero fora do padrão no tenant %s: %r', admin_id, ultimo[0])
        seq = 1
    return f'{prefixo}{seq:04d}'


class TransicaoInvalida(Exception):
    """Transição de estado não permitida pela máquina."""


# Máquina de estados da requisição. Ler assim: "de X, pode-se ir para".
# Estado ausente do dicionário (ou com tupla vazia) é TERMINAL.
#
# Duas escolhas que valem comentário:
#   * REJEITADA → RASCUNHO existe porque rejeitar não é matar. O gestor
#     rejeita "3 chapas é pouco, peça 5"; o solicitante corrige e reenvia,
#     e o histórico guarda os dois momentos.
#   * De CONVERTIDA não se volta. Nesse ponto o PedidoCompra já existe e
#     já gerou GestaoCustoPai e ContaPagar (compras_views.py:193-254).
#     Desfazer é excluir o pedido (compras_views.py:1023), que é outra
#     operação, com outra trilha.
TRANSICOES_VALIDAS = {
    EstadoRequisicao.RASCUNHO: (
        EstadoRequisicao.AGUARDANDO_APROVACAO,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.AGUARDANDO_APROVACAO: (
        EstadoRequisicao.APROVADA,
        EstadoRequisicao.REJEITADA,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.APROVADA: (
        EstadoRequisicao.CONVERTIDA,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.REJEITADA: (
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.CONVERTIDA: (),
    EstadoRequisicao.CANCELADA: (),
}


def _papel_de(usuario, requisicao):
    """Com que chapéu a pessoa está agindo. Congelado no histórico porque o
    vínculo em usuario_obra pode mudar depois — e a trilha não pode."""
    from models import TipoUsuario

    if usuario is None:
        return None
    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return 'ADMIN'
    try:
        from utils.autorizacao import papel_na_obra
        papel = papel_na_obra(requisicao.obra_id)
        return papel.name if papel is not None else None
    except Exception:
        logger.warning('papel_na_obra indisponível para requisicao %s',
                       requisicao.id)
        return None


def transicionar(requisicao, novo_estado, usuario, motivo=None):
    """ÚNICO caminho de mudança de estado. NÃO commita.

    Valida contra TRANSICOES_VALIDAS, grava a RequisicaoTransicao com
    quem/quando/valor/papel, e só então muda o estado. A ordem importa:
    se a validação falhar, nada foi escrito.

    Não decide PERMISSÃO — isso é de services/alcada_compras.py e das
    rotas. Aqui só se decide LEGALIDADE da transição. Separar os dois é o
    que permite testar a máquina sem montar um request.
    """
    from models import RequisicaoTransicao

    atual = requisicao.estado
    permitidos = TRANSICOES_VALIDAS.get(atual, ())
    if novo_estado not in permitidos:
        nomes = ', '.join(e.name for e in permitidos) or '(nenhum — terminal)'
        raise TransicaoInvalida(
            f'Requisição {requisicao.numero}: {atual.name} → '
            f'{novo_estado.name} não é permitido. Permitidos: {nomes}')

    db.session.add(RequisicaoTransicao(
        requisicao_id=requisicao.id,
        admin_id=requisicao.admin_id,
        de_estado=atual,
        para_estado=novo_estado,
        usuario_id=getattr(usuario, 'id', None),
        papel_aplicado=_papel_de(usuario, requisicao),
        valor_no_momento=requisicao.valor_estimado,
        motivo=motivo,
    ))
    requisicao.estado = novo_estado
    requisicao.updated_at = datetime.utcnow()
    db.session.flush()

    logger.info('requisicao %s %s → %s por usuario=%s valor=%s',
                requisicao.numero, atual.name, novo_estado.name,
                getattr(usuario, 'id', None), requisicao.valor_estimado)
    return requisicao
