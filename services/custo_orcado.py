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


def _servicos_e_somas(obra_id: int, admin_id=None):
    """`(servicos, {osc_id: soma_das_linhas})` — DUAS queries, nunca por serviço.

    Ponto único da agregação. Existe para que `custo_orcado_por_servico` e
    `projecao_de_custo_por_servico` não façam a mesma pergunta ao banco de dois
    jeitos — foi assim que a regra "linha vence agregado" se espalhou antes de
    virar este módulo.
    """
    from models import ObraServicoCusto, ObraServicoCustoItem, db
    from sqlalchemy import func as sqlfunc

    q = ObraServicoCusto.query.filter_by(obra_id=obra_id)
    if admin_id is not None:
        q = q.filter_by(admin_id=admin_id)
    servicos = q.all()
    if not servicos:
        return [], {}

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
    return servicos, somas


def custo_orcado_por_servico(obra_id: int, admin_id=None) -> dict:
    """`{obra_servico_custo_id: custo}` pela mesma regra, serviço a serviço.

    Existe para quem precisa do orçado POR ETAPA — o painel físico-financeiro
    é o caso — sem ter que repetir a decisão "linha vence agregado" em cada
    consumidor. A decisão de fallback é **por serviço**: um serviço com
    linhas usa as linhas, o irmão sem linhas usa o agregado dele.
    """
    resultado: dict = {}
    try:
        servicos, somas = _servicos_e_somas(obra_id, admin_id)
        for s in servicos:
            linhas = _f(somas.get(s.id))
            resultado[s.id] = linhas if linhas > 0 else _f(s.valor_orcado)
    except Exception:
        logger.exception('custo_orcado_por_servico falhou (obra=%s)', obra_id)
    return resultado


def projecao_de_custo_por_servico(obra_id: int, admin_id=None) -> dict:
    """`{osc_id: {orcado, tem_linhas, realizado, a_realizar_efetivo, projetado, saldo}}`.

    ## O fato que este helper existe para não deixar ninguém esquecer

    **Quando um serviço TEM linhas de custo, o `a_realizar_total` gravado É o
    próprio orçado.** Não é coincidência, é identidade:
    `services/cronograma_fisico_financeiro.py` (`recalcular_osc_dos_itens`)
    grava `mao_obra_a_realizar = Σ linhas fonte != 'fat_direto'`,
    `material_a_realizar = Σ linhas fonte == 'fat_direto'` e
    `outros_a_realizar = 0` — logo `a_realizar_total == Σ linhas == orcado`.

    Quem então calcula `projetado = realizado + a_realizar_total` está somando
    `realizado + orcado`, e **qualquer** realizado > 0 estoura o orçamento. É a
    armadilha central do A13, e é por isso que trocar a base de comparação sem
    passar por aqui vira avalanche de alarme falso.

    ## A regra

    * `orcado` — a mesma de `custo_orcado_por_servico`: linha vence agregado.
    * `tem_linhas` — soma das linhas > 0. É o divisor entre os dois regimes.
    * `a_realizar_efetivo` — **`max(orcado - realizado, 0)` quando há linhas**,
      porque ali o campo gravado é o orçado e o que falta gastar é o que sobra
      dele; e o `a_realizar_total` gravado quando NÃO há linhas, que é o fluxo
      manual, onde o gestor mantém o campo à mão e ninguém o recalcula.
    * `projetado = realizado + a_realizar_efetivo`; `saldo = orcado - projetado`.

    O `max(..., 0)` é o que impede projeção menor que o realizado: estourar o
    orçado não faz o que já foi gasto desaparecer — faz o saldo ficar negativo,
    que é o que se quer mostrar.

    Duas queries por obra, nada por serviço (`realizado_total` e
    `a_realizar_total` são properties sobre colunas já carregadas).

    **Dict vazio significa "não sei", nunca zero** — o `except` devolve `{}`
    tanto para obra sem serviço quanto para falha, e o chamador tem de tratar a
    ausência da chave como ausência de informação.
    """
    resultado: dict = {}
    try:
        servicos, somas = _servicos_e_somas(obra_id, admin_id)
        for s in servicos:
            linhas = _f(somas.get(s.id))
            tem_linhas = linhas > 0
            orcado = linhas if tem_linhas else _f(s.valor_orcado)
            realizado = _f(s.realizado_total)

            if tem_linhas:
                a_realizar_efetivo = max(orcado - realizado, 0.0)
            else:
                a_realizar_efetivo = _f(s.a_realizar_total)

            projetado = realizado + a_realizar_efetivo
            resultado[s.id] = {
                'orcado': orcado,
                'tem_linhas': tem_linhas,
                'realizado': realizado,
                'a_realizar_efetivo': a_realizar_efetivo,
                'projetado': projetado,
                'saldo': orcado - projetado,
            }
    except Exception:
        logger.exception('projecao_de_custo_por_servico falhou (obra=%s)', obra_id)
        return {}
    return resultado
