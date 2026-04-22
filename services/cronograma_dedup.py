"""
Task #144 — Deduplicação de TarefaCronograma + chave natural reutilizável.

Quando `materializar_cronograma` (ou `gerar_cronograma_cliente`) é chamado em
condições degeneradas (snapshot sem `proposta_item_id`, re-aprovação de
proposta com `gerada_por_proposta_item_id` nulo, propagação proposta→obra
com valor zerado, etc), as mesmas tarefas podem ser inseridas mais de uma
vez no cronograma da obra. O front-end (`/cronograma/obra/<id>/tarefas-rdo`,
card "Apontamento de Produção — Cronograma" no novo RDO) apenas lista o que
existe — então as duplicatas aparecem como "Aço Laminado" 2x, "Concretagem
de laje (PWA)" 2x, etc.

Este módulo expõe:

- ``natural_key(t, *, is_cliente=None)``: tupla `(obra_id, admin_id,
  is_cliente, subatividade_mestre_id, nome_tarefa, tarefa_pai_id)` usada como
  chave natural para detectar duplicatas. Quando há `subatividade_mestre_id`
  ele tem precedência sobre o nome — duas folhas com o mesmo
  `subatividade_mestre_id` no mesmo pai são consideradas a mesma tarefa.

- ``deduplicar_tarefas_cronograma(obra_id, admin_id, is_cliente=False)``:
  varre `TarefaCronograma` da obra agrupando por chave natural, escolhe a
  tarefa canônica (preferindo a que tem `gerada_por_proposta_item_id`
  preenchido; em empate, menor `id`), reaponta FKs em
  `RDOApontamentoCronograma`, `RDOSubempreitadaApontamento`,
  `ItemMedicaoCronogramaTarefa`, `tarefa_pai_id` e `predecessora_id` para a
  canônica, e apaga as duplicatas. Faz isso em níveis (root → folhas) para
  garantir que filhos sejam reapontados ao pai canônico antes de serem
  agrupados.

- ``natural_key_index(obra_id, admin_id, is_cliente)``: mapa
  ``{chave_natural: TarefaCronograma}`` reaproveitado por
  `materializar_cronograma` para evitar inserir duplicatas (defesa em
  profundidade — combina com a checagem por `gerada_por_proposta_item_id`).

Idempotência: rodar `deduplicar_tarefas_cronograma` numa obra sem duplicatas
é um no-op e devolve 0.
"""
from __future__ import annotations

import logging
from typing import Iterable

from app import db
from models import (
    ItemMedicaoCronogramaTarefa,
    RDOApontamentoCronograma,
    RDOSubempreitadaApontamento,
    TarefaCronograma,
)

logger = logging.getLogger(__name__)


def _key_for(
    sub_id: int | None,
    nome: str | None,
    pai_id: int | None,
) -> tuple:
    """Chave natural local de uma tarefa (sem obra/admin/is_cliente).

    Quando `subatividade_mestre_id` existe, ele é a chave (junto com o pai).
    Sem ele, caímos no par (nome_tarefa.lower(), pai). Isso garante que dois
    serviços-raiz com o mesmo nome (ex.: "Aço Laminado" duas vezes em pai_id
    NULL) sejam considerados duplicados, e que duas folhas vinculadas ao
    mesmo SubatividadeMestre dentro do mesmo grupo também sejam.
    """
    if sub_id is not None:
        return ('sub', int(sub_id), pai_id)
    nome_norm = (nome or '').strip().lower()
    return ('nome', nome_norm, pai_id)


def natural_key(t: TarefaCronograma) -> tuple:
    """Chave natural pública de uma tarefa, qualificada por obra/admin/escopo."""
    return (
        int(t.obra_id),
        int(t.admin_id),
        bool(t.is_cliente),
        *_key_for(t.subatividade_mestre_id, t.nome_tarefa, t.tarefa_pai_id),
    )


def natural_key_index(
    obra_id: int,
    admin_id: int,
    is_cliente: bool = False,
) -> dict[tuple, TarefaCronograma]:
    """Indexa todas as tarefas de uma obra/escopo pela chave natural.

    Em caso de duplicatas pré-existentes, mantém a primeira encontrada
    (ordenada por id) — a chamada de
    `deduplicar_tarefas_cronograma` se encarrega de remover duplicatas
    persistidas. O índice é usado para impedir que NOVAS duplicatas sejam
    criadas durante a materialização.
    """
    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=is_cliente)
        .order_by(TarefaCronograma.id.asc())
        .all()
    )
    idx: dict[tuple, TarefaCronograma] = {}
    for t in tarefas:
        k = _key_for(t.subatividade_mestre_id, t.nome_tarefa, t.tarefa_pai_id)
        idx.setdefault(k, t)
    return idx


def _escolher_canonica(grupo: list[TarefaCronograma]) -> TarefaCronograma:
    """Prefere a tarefa com `gerada_por_proposta_item_id` preenchido;
    em empate, a de menor id (mais antiga)."""
    grupo_sorted = sorted(
        grupo,
        key=lambda t: (
            0 if t.gerada_por_proposta_item_id is not None else 1,
            t.id,
        ),
    )
    return grupo_sorted[0]


def _reapontar_fks(canonica_id: int, dup_ids: Iterable[int]) -> None:
    """Reaponta toda FK que referencia uma tarefa duplicada para a canônica."""
    dup_list = list(dup_ids)
    if not dup_list:
        return

    # Apontamentos de produção (RDO ↔ tarefa)
    RDOApontamentoCronograma.query.filter(
        RDOApontamentoCronograma.tarefa_cronograma_id.in_(dup_list)
    ).update(
        {RDOApontamentoCronograma.tarefa_cronograma_id: canonica_id},
        synchronize_session=False,
    )

    # Apontamentos de subempreitada (RDO ↔ tarefa)
    RDOSubempreitadaApontamento.query.filter(
        RDOSubempreitadaApontamento.tarefa_cronograma_id.in_(dup_list)
    ).update(
        {RDOSubempreitadaApontamento.tarefa_cronograma_id: canonica_id},
        synchronize_session=False,
    )

    # Pesos de medição (ItemMedicaoComercial ↔ tarefa). Existe um
    # UniqueConstraint em (item_medicao_id, cronograma_tarefa_id) — se já
    # existe um vínculo entre o IMC e a canônica, devemos APAGAR o duplicado
    # ao invés de remapear (senão o UPDATE quebra a constraint).
    vinculos_dup = ItemMedicaoCronogramaTarefa.query.filter(
        ItemMedicaoCronogramaTarefa.cronograma_tarefa_id.in_(dup_list)
    ).all()
    for v in vinculos_dup:
        ja_existe = ItemMedicaoCronogramaTarefa.query.filter_by(
            item_medicao_id=v.item_medicao_id,
            cronograma_tarefa_id=canonica_id,
        ).first()
        if ja_existe:
            db.session.delete(v)
        else:
            v.cronograma_tarefa_id = canonica_id

    # Hierarquia (filhos cuja tarefa_pai_id é uma duplicata) → canônica
    TarefaCronograma.query.filter(
        TarefaCronograma.tarefa_pai_id.in_(dup_list)
    ).update(
        {TarefaCronograma.tarefa_pai_id: canonica_id},
        synchronize_session=False,
    )

    # Predecessoras
    TarefaCronograma.query.filter(
        TarefaCronograma.predecessora_id.in_(dup_list)
    ).update(
        {TarefaCronograma.predecessora_id: canonica_id},
        synchronize_session=False,
    )

    db.session.flush()


def deduplicar_tarefas_cronograma(
    obra_id: int,
    admin_id: int,
    is_cliente: bool = False,
) -> int:
    """Remove duplicatas de TarefaCronograma agrupando por chave natural.

    Retorna o número de tarefas REMOVIDAS. Idempotente.
    """
    removidas_total = 0

    # Loop top-down. Em cada iteração, agrupamos por (sub_id, nome, pai_id).
    # Quando colapsamos um nível, filhos são reapontados — o que pode criar
    # NOVAS duplicatas no nível seguinte (mesma sub no mesmo pai canônico).
    # Continuamos até estabilizar.
    while True:
        tarefas = (
            TarefaCronograma.query
            .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=is_cliente)
            .order_by(TarefaCronograma.id.asc())
            .all()
        )
        grupos: dict[tuple, list[TarefaCronograma]] = {}
        for t in tarefas:
            k = _key_for(t.subatividade_mestre_id, t.nome_tarefa, t.tarefa_pai_id)
            grupos.setdefault(k, []).append(t)

        dups_iter = [g for g in grupos.values() if len(g) > 1]
        if not dups_iter:
            break

        for grupo in dups_iter:
            canonica = _escolher_canonica(grupo)
            duplicatas = [t for t in grupo if t.id != canonica.id]
            dup_ids = [t.id for t in duplicatas]

            # Se a canônica não tem `gerada_por_proposta_item_id` mas alguma
            # duplicata tem, copia para a canônica (fortalece idempotência).
            if canonica.gerada_por_proposta_item_id is None:
                for d in duplicatas:
                    if d.gerada_por_proposta_item_id is not None:
                        canonica.gerada_por_proposta_item_id = d.gerada_por_proposta_item_id
                        break

            _reapontar_fks(canonica.id, dup_ids)

            for d in duplicatas:
                db.session.delete(d)
            db.session.flush()
            removidas_total += len(duplicatas)
            logger.info(
                f"#144 dedup obra={obra_id} admin={admin_id} is_cliente={is_cliente}: "
                f"colapsou {len(grupo)} tarefas em canonica={canonica.id} "
                f"(removidas={len(duplicatas)}) — chave={grupo[0].nome_tarefa!r}"
            )

    if removidas_total:
        logger.info(
            f"#144 dedup OBRA={obra_id} (cliente={is_cliente}) — "
            f"{removidas_total} tarefa(s) duplicada(s) removida(s)"
        )
    return removidas_total


def deduplicar_todas_obras() -> dict[int, dict[str, int]]:
    """Rotina de manutenção — passa em todas as obras/admins do banco.

    Retorna ``{obra_id: {'interno': N, 'cliente': M}}`` para auditoria/log.
    """
    from models import Obra

    relatorio: dict[int, dict[str, int]] = {}
    obras = Obra.query.all()
    for obra in obras:
        interno = deduplicar_tarefas_cronograma(obra.id, obra.admin_id, is_cliente=False)
        cliente = deduplicar_tarefas_cronograma(obra.id, obra.admin_id, is_cliente=True)
        if interno or cliente:
            relatorio[obra.id] = {'interno': interno, 'cliente': cliente}
    if relatorio:
        db.session.commit()
        logger.info(f"#144 dedup global concluído — relatório: {relatorio}")
    else:
        logger.info("#144 dedup global concluído — nenhuma duplicata encontrada")
    return relatorio
