"""Fonte única do CUSTO orçado de uma obra — p3 do `PLANO-NUCLEO.md`.

## O problema que este módulo resolve

`ObraServicoCusto.valor_orcado` **não guarda custo — guarda venda.** O
listener de `ItemMedicaoComercial` (models.py:7466, Task #82) herda
`valor_comercial` para `valor_orcado` quando cria o par de custo, e duas rotas
reescrevem o campo com o mesmo valor comercial depois
(`medicao_views.py:308`, `views/catalogo_views.py:882`). O nome do campo diz
uma coisa e o conteúdo é outra.

Quem lê aquele campo achando que lê custo calcula margem contra o próprio
preço de venda — e o BAC do EVM (p10) nasceria com o mesmo vício.

## A decisão de 03/08 — consertar no CONSUMO

> Cássio, 03/08: consertar **no consumo**, não na origem.

`valor_orcado` continua gravado com venda; ninguém mais o lê como custo. A
regra que já existia e estava certa mora em `services/resumo_custos_obra.py`
(linhas 253-269): **quando há linhas de custo cadastradas, elas são a fonte
da verdade**; o campo agregado só vale no fluxo manual/legado sem linhas.
Aqui essa regra sai de dentro de uma função de resumo e vira o ponto único
que todo consumidor chama.

Consertar na origem — corrigir o listener e neutralizar os dois re-syncs —
continua sendo a saída definitiva, e ficou registrada na spec. Mas ela muda a
escrita de toda obra nova e exige backfill; esta rota entrega o número certo
sem tocar em nada que grava.

## O que este módulo NÃO faz

Não corrige `valor_orcado` no banco, e não é lugar de fazê-lo: enquanto o
listener herdar venda, qualquer correção seria desfeita na próxima edição de
item comercial.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def custo_orcado_da_obra(obra_id: int, admin_id=None) -> float:
    """Custo orçado da obra — soma das LINHAS de custo, não do agregado.

    Ordem, que é a regra testada de `resumo_custos_obra`:

    1. soma de `ObraServicoCustoItem.valor` dos serviços da obra — é o custo
       que alguém cadastrou linha a linha;
    2. **só se não houver linha nenhuma**, cai para a soma de
       `ObraServicoCusto.valor_orcado` — o fluxo manual/legado, onde aquele
       campo é o único número disponível (e onde, por não vir do listener
       comercial, costuma de fato ser custo).

    Requer app_context. Nunca levanta: obra sem custo cadastrado devolve 0.0.
    """
    try:
        from models import ObraServicoCusto, ObraServicoCustoItem, db
        from sqlalchemy import func as sqlfunc

        q = ObraServicoCusto.query.filter_by(obra_id=obra_id)
        if admin_id is not None:
            q = q.filter_by(admin_id=admin_id)
        servicos = q.all()
        if not servicos:
            return 0.0

        soma_linhas = _f(
            db.session.query(
                sqlfunc.coalesce(sqlfunc.sum(ObraServicoCustoItem.valor), 0)
            )
            .filter(ObraServicoCustoItem.obra_servico_custo_id.in_(
                [s.id for s in servicos]))
            .scalar() or 0
        )
        if soma_linhas > 0:
            return soma_linhas

        return sum(_f(s.valor_orcado) for s in servicos)
    except Exception:
        logger.exception('custo_orcado_da_obra falhou (obra=%s)', obra_id)
        return 0.0


def custo_orcado_por_servico(obra_id: int, admin_id=None) -> dict:
    """`{obra_servico_custo_id: custo}` pela mesma regra, serviço a serviço.

    Existe para quem precisa do orçado POR ETAPA — o painel físico-financeiro
    é o caso — sem ter que repetir a decisão "linha vence agregado" em cada
    consumidor. A decisão de fallback é **por serviço**: um serviço com
    linhas usa as linhas, o irmão sem linhas usa o agregado dele.
    """
    resultado: dict = {}
    try:
        from models import ObraServicoCusto, ObraServicoCustoItem, db
        from sqlalchemy import func as sqlfunc

        q = ObraServicoCusto.query.filter_by(obra_id=obra_id)
        if admin_id is not None:
            q = q.filter_by(admin_id=admin_id)
        servicos = q.all()
        if not servicos:
            return resultado

        somas = dict(
            db.session.query(
                ObraServicoCustoItem.obra_servico_custo_id,
                sqlfunc.coalesce(sqlfunc.sum(ObraServicoCustoItem.valor), 0),
            )
            .filter(ObraServicoCustoItem.obra_servico_custo_id.in_(
                [s.id for s in servicos]))
            .group_by(ObraServicoCustoItem.obra_servico_custo_id)
            .all()
        )
        for s in servicos:
            linhas = _f(somas.get(s.id))
            resultado[s.id] = linhas if linhas > 0 else _f(s.valor_orcado)
    except Exception:
        logger.exception('custo_orcado_por_servico falhou (obra=%s)', obra_id)
    return resultado
