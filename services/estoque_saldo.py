"""O saldo de um lote de estoque, mantido num lugar só.

`AlmoxarifadoEstoque` tem três colunas de quantidade e elas precisam andar
juntas:

- `quantidade_inicial` — histórico do lote, nunca muda depois de criado;
- `quantidade` — o que resta, e o que as telas mostram;
- `quantidade_disponivel` — o que a SAÍDA valida
  (`views/almoxarifado/movimentos.py:597`, `func.sum(quantidade_disponivel)`).

O caminho de entrada por nota (`movimentos.py:400-406`) mantinha as três. O
caminho manual (`almoxarifado_utils.apply_movimento_manual`) e o de devolução
mantinham só `quantidade` — e o resultado era o pior dos dois mundos: entrada
manual criava lote com `quantidade_disponivel = NULL` (a saída recusava
material que existia) e saída manual baixava `quantidade` deixando
`quantidade_disponivel` intacta (**as mesmas unidades saíam de novo**).

A invariante existia; metade do código a ignorava. Aqui ela tem um dono.
"""
from decimal import Decimal

from app import db
from models import AlmoxarifadoEstoque

__all__ = ['SaldoInsuficiente', 'creditar', 'criar_lote', 'debitar',
           'disponivel_de']


class SaldoInsuficiente(ValueError):
    """Pediram mais do que o lote tem disponível."""


def _d(valor):
    """Decimal tolerante a None e a float.

    Os caminhos de escrita misturam `Decimal`, `float` e coluna NULL — somar
    os três direto é `TypeError` ou perda de precisão binária.
    """
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


def disponivel_de(estoque):
    """O disponível do lote, curando o legado na primeira escrita.

    ⚠️ Produção tem lotes criados pelo caminho manual defeituoso: com
    `quantidade_disponivel` NULL e `quantidade > 0`. **É material que existe.**
    Tratá-los como zero faria esta correção RECUSAR material real — trocaria um
    defeito (a unidade sai duas vezes) por outro (a unidade não sai nenhuma).

    Então NULL não é zero aqui: é "nunca foi preenchido", e o valor verdadeiro
    é o que a outra coluna sempre manteve. O lote se cura ao ser tocado, sem
    migration e sem varredura.
    """
    if estoque.quantidade_disponivel is None:
        estoque.quantidade_disponivel = _d(estoque.quantidade)
    return _d(estoque.quantidade_disponivel)


def criar_lote(item_id, quantidade, admin_id, **campos):
    """Um lote novo, com as três colunas coerentes desde o nascimento."""
    qtd = _d(quantidade)
    lote = AlmoxarifadoEstoque(
        item_id=item_id,
        admin_id=admin_id,
        quantidade=qtd,
        quantidade_inicial=qtd,
        quantidade_disponivel=qtd,
        status=campos.pop('status', 'DISPONIVEL'),
        **campos)
    db.session.add(lote)
    return lote


def creditar(estoque, quantidade):
    """Devolução ou entrada num lote que já existe.

    `quantidade_inicial` NÃO se mexe: ela é o histórico da entrada original.
    """
    qtd = _d(quantidade)
    disponivel = disponivel_de(estoque)
    estoque.quantidade = _d(estoque.quantidade) + qtd
    estoque.quantidade_disponivel = disponivel + qtd


def debitar(estoque, quantidade):
    """Saída. Levanta se o disponível não cobre.

    Devolve o quanto foi efetivamente debitado — sempre `quantidade`, já que
    o caso insuficiente levanta. O retorno existe para o consumo em FIFO
    sobre vários lotes poder somar sem reler as colunas.
    """
    qtd = _d(quantidade)
    disponivel = disponivel_de(estoque)
    if qtd > disponivel:
        raise SaldoInsuficiente(
            f'lote {estoque.id}: pedido {qtd}, disponível {disponivel}')
    estoque.quantidade = _d(estoque.quantidade) - qtd
    estoque.quantidade_disponivel = disponivel - qtd
    return qtd
